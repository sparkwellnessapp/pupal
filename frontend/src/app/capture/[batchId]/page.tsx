'use client'

/**
 * The teacher capture page (§8.3) — on her phone or her desktop, the same
 * flow: one student's pages, the name confirmed, «התלמיד הבא», and «שמירה»
 * sends every complete group to scanning.
 *
 * AUTH. Her normal session (a logged-in desktop), or `?handoff=` — the
 * one-time token from the desktop's QR — exchanged ONCE for a capture session
 * scoped to this batch (D2/OD-5). The session lives in sessionStorage and the
 * handoff token is removed from the URL the moment it has been exchanged.
 *
 * THE TEACHER IS THE AUTHORITY (OD-S2/OD-S4). Page 1's name is READ and
 * offered; nothing is assigned until she clicks a student or «יצירת תלמיד/ה».
 * «התלמיד הבא» and «שמירה» are blocked-but-clickable (CLAUDE.md §11): a click
 * on an incomplete group shows what is missing and never advances.
 */
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowRight, Loader2, Plus, Save } from 'lucide-react'
import { toast } from 'sonner'

import { Modal } from '@/components/batch/Modal'
import { CaptureFlow, type CaptureFlowState } from '@/components/capture/CaptureFlow'
import { StudentPicker, type StudentSource } from '@/components/StudentPicker'
import { T, TEACHER_FLOW, hhmm } from '@/copy/capture'
import { useAuth } from '@/lib/auth'
import {
  CaptureApiError, exchangeHandoff, teacherCaptureApi, type TeacherCaptureAuth,
} from '@/lib/capture-api'
import type { NameSuggestResponse, SubmissionView } from '@/types/capture'

const sessionKey = (batchId: string) => `vivi.capture.session.${batchId}`

function readSession(batchId: string): string | null {
  try { return sessionStorage.getItem(sessionKey(batchId)) } catch { return null }
}

function dropSession(batchId: string): void {
  try { sessionStorage.removeItem(sessionKey(batchId)) } catch { /* nothing kept */ }
}

type Duplicate = { studentId: string; name: string; pages: number; savedAt: string | null }

export default function TeacherCapturePageRoute() {
  // useSearchParams needs a Suspense boundary in the App Router.
  return <Suspense fallback={<Shell><Loading /></Shell>}><TeacherCapturePage /></Suspense>
}

function TeacherCapturePage() {
  const { batchId } = useParams<{ batchId: string }>()
  const search = useSearchParams()
  const router = useRouter()
  const { isAuthenticated, isLoading: authLoading } = useAuth()

  const [auth, setAuth] = useState<TeacherCaptureAuth | null>(null)
  const [authError, setAuthError] = useState<string | null>(null)
  // The handoff token is SINGLE-USE: this effect re-runs when the auth
  // provider settles, and a second exchange would answer 410 over a first
  // one that succeeded.
  const exchanged = useRef(false)

  // ── resolve WHO is capturing (once) ─────────────────────────────────────
  useEffect(() => {
    if (auth) return
    const handoff = search.get('handoff')
    if (handoff) {
      if (exchanged.current) return
      exchanged.current = true
      exchangeHandoff(handoff)
        .then((r) => {
          try { sessionStorage.setItem(sessionKey(batchId), r.capture_session) } catch { /* in memory only */ }
          setAuth({ kind: 'capture', token: r.capture_session })
          router.replace(`/capture/${batchId}`)        // the one-time token leaves the URL
        })
        .catch((e) => setAuthError(e instanceof CaptureApiError && e.messageHe ? e.messageHe : T.sessionExpired))
      return
    }
    const stored = readSession(batchId)
    if (stored) { setAuth({ kind: 'capture', token: stored }); return }
    if (!authLoading) {
      if (isAuthenticated) setAuth({ kind: 'session' })
      // A desktop with no session and no handoff: she simply is not logged in.
      else router.replace('/login')
    }
  }, [auth, batchId, search, router, isAuthenticated, authLoading])

  const api = useMemo(() => (auth ? teacherCaptureApi(batchId, auth) : null), [batchId, auth])

  if (authError) return <Shell><p className="py-10 text-center text-gray-700">{authError}</p></Shell>
  if (!api) return <Shell><Loading /></Shell>
  return <CaptureSession api={api} batchId={batchId} desktopBack={auth?.kind === 'session'}
                         onSessionLost={() => { if (auth?.kind === 'capture') dropSession(batchId) }} />
}

function CaptureSession({ api, batchId, desktopBack, onSessionLost }: {
  api: ReturnType<typeof teacherCaptureApi>; batchId: string; desktopBack: boolean
  onSessionLost: () => void
}) {
  const [batchName, setBatchName] = useState<string | null>(null)
  const [savedCount, setSavedCount] = useState(0)
  const [groups, setGroups] = useState<SubmissionView[]>([])
  const [current, setCurrent] = useState<string | null>(null)
  const [flow, setFlow] = useState<Record<string, CaptureFlowState>>({})
  const [suggest, setSuggest] = useState<Record<string, NameSuggestResponse | 'loading'>>({})
  const [blockers, setBlockers] = useState<string[]>([])
  const [duplicate, setDuplicate] = useState<Duplicate | null>(null)
  const [saving, setSaving] = useState(false)
  const [fatal, setFatal] = useState<string | null>(null)
  const asked = useRef(new Set<string>())

  const lost = useCallback(() => { onSessionLost(); setFatal(T.sessionExpired) }, [onSessionLost])
  const fail = useCallback((e: unknown) => {
    if (e instanceof CaptureApiError && e.status === 401) lost()
    else toast.error(e instanceof CaptureApiError && e.messageHe ? e.messageHe : 'משהו השתבש — נסי שוב')
  }, [lost])

  const newGroup = useCallback(async () => {
    const sub = await api.createSubmission()
    setGroups((g) => [...g, sub])
    setCurrent(sub.submission_id)
  }, [api])

  // ── load: resume her unsaved groups first (§8.3) ─────────────────────────
  useEffect(() => {
    api.state().then(async (s) => {
      setBatchName(s.batch_name ?? null)
      setSavedCount(s.saved_count)
      if (s.drafts.length > 0) {
        setGroups(s.drafts)
        setCurrent(s.drafts[s.drafts.length - 1].submission_id)
        // Only groups with something in them are "unsaved work" (the server
        // also returns the newest EMPTY group, to be reused).
        const unsaved = s.drafts.filter((d) => d.pages.length > 0 || d.student).length
        if (unsaved > 0) toast(T.unsavedResume(unsaved))
      } else {
        await newGroup()
      }
    }).catch((e) => {
      // Without its state the page has nothing to show: say so, never spin.
      if (e instanceof CaptureApiError && e.status === 401) lost()
      else setFatal(T.loadFailed)
    })
  }, [api, newGroup, lost])

  const group = groups.find((g) => g.submission_id === current) ?? null
  const state = current ? flow[current] : undefined

  // ── page 1 analyzed → read its name, once per group (SCN-10) ─────────────
  useEffect(() => {
    const first = state?.firstPage
    if (!group || !first || first.status !== 'analyzed') return
    if (group.student_state === 'confirmed' || asked.current.has(group.submission_id)) return
    asked.current.add(group.submission_id)
    const id = group.submission_id
    setSuggest((s) => ({ ...s, [id]: 'loading' }))
    api.nameSuggest(id)
      .then((r) => setSuggest((s) => ({ ...s, [id]: r })))
      .catch(() => setSuggest((s) => ({ ...s, [id]: { read_name: null, match: null, confidence: 'low' } })))
  }, [api, group, state?.firstPage])

  const replaceGroup = (sub: SubmissionView) =>
    setGroups((gs) => gs.map((g) => (g.submission_id === sub.submission_id ? { ...g, ...sub } : g)))

  const assign = useCallback(async (submissionId: string, studentId: string, replace = false) => {
    try {
      replaceGroup(await api.assignStudent(submissionId, { student_id: studentId, replace_existing: replace }))
      setBlockers([])
    } catch (e) {
      if (e instanceof CaptureApiError && e.code === 'student_already_submitted') {
        const roster = await api.roster().catch(() => [])
        setDuplicate({
          studentId, name: roster.find((r) => r.student_id === studentId)?.display_name ?? '',
          pages: Number(e.extra.page_count ?? 0), savedAt: (e.extra.saved_at as string) ?? null,
        })
      } else fail(e)
    }
  }, [api, fail])

  // The picker lists and creates through the capture API — a capture session
  // cannot call the classroom API. «יצירת תלמיד/ה» is immediate (R1, teacher
  // side) and goes through the assignment, so the D5 check runs on it too.
  const source: StudentSource = useMemo(() => ({
    list: async () => (await api.roster()).map((r) => ({ id: r.student_id, full_name: r.display_name })),
    create: async (name) => {
      if (!current) throw new Error('')
      try {
        const sub = await api.assignStudent(current, { create: { name } })
        replaceGroup(sub)
        return { id: sub.student!.student_id, full_name: sub.student!.display_name }
      } catch (e) {
        throw new Error(e instanceof CaptureApiError && e.messageHe ? e.messageHe : 'שגיאה ביצירת התלמיד')
      }
    },
  }), [api, current])

  const missing = (g: SubmissionView | null, live: CaptureFlowState | undefined): string[] => {
    const out: string[] = []
    if (!g) return out
    // A group she has not opened this visit has no flow state: judge it by the
    // server's own view of it (resumed groups must not be silently skipped).
    const s: CaptureFlowState = live ?? {
      pageCount: g.pages.length, pending: 0, failed: 0,
      awaiting: g.pages.filter((p) => p.status === 'awaiting_upload').length,
      firstPage: g.pages[0] ?? null,
    }
    if (s.pageCount === 0) out.push(T.missingPages)
    if (g.student_state !== 'confirmed') out.push(T.missingStudent)
    if (s.pending > 0 || s.awaiting > 0) out.push(T.waitingUploads)
    if (s.failed > 0) out.push(TEACHER_FLOW.failedUploads(s.failed))
    return out
  }
  const blocked = missing(group, state)

  const next = async () => {
    if (blocked.length) { setBlockers(blocked); return }
    setBlockers([])
    await newGroup().catch(fail)
  }

  // Switching away while this group's photos are still landing would leave
  // them unaccounted for on screen: finish (or remove) them first.
  const select = (id: string) => {
    if ((state?.pending ?? 0) > 0) { setBlockers([T.waitingUploads]); return }
    setCurrent(id); setBlockers([])
  }

  const saveAll = async () => {
    if (blocked.length && (state?.pageCount ?? 0) > 0) { setBlockers(blocked); return }
    const complete = groups.filter((g) => missing(g, flow[g.submission_id]).length === 0)
    if (complete.length === 0) { setBlockers([T.nothingToSave]); return }
    setBlockers([])
    setSaving(true)
    const failed: string[] = []
    const savedIds = new Set<string>()
    for (const g of complete) {
      try {
        await api.save(g.submission_id)
        savedIds.add(g.submission_id)
      } catch (e) {
        failed.push(g.student?.display_name ?? T.student(groups.indexOf(g) + 1))
        if (e instanceof CaptureApiError && e.status === 401) { lost(); break }
      }
    }
    const sent = savedIds.size
    setSaving(false)
    if (sent) toast.success(T.savedToast(sent))
    if (failed.length) toast.error(`${T.notSaved} ${failed.join(', ')}`)
    const left = groups.filter((g) => !savedIds.has(g.submission_id))
    setSavedCount((n) => n + sent)
    setGroups(left)
    if (left.length === 0) await newGroup().catch(fail)
    else setCurrent(left[left.length - 1].submission_id)
  }

  if (fatal) return <Shell><p className="py-10 text-center text-gray-700">{fatal}</p></Shell>
  if (!group) return <Shell><Loading /></Shell>

  const sug = suggest[group.submission_id]
  const suggestion = sug && sug !== 'loading' ? sug : null

  return (
    <Shell>
      <header className="mb-4 flex items-center justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">{batchName ?? ''}</h1>
          <p className="text-sm text-gray-600">{T.savedCount(savedCount)}</p>
        </div>
        {desktopBack && (
          <Link href={`/batches/${batchId}`} className="flex items-center gap-1 text-sm text-primary-700">
            <ArrowRight size={16} />חזרה לקבוצה
          </Link>
        )}
      </header>

      {groups.length > 1 && (
        <nav className="mb-3 flex flex-wrap gap-2" aria-label="תלמידים שלא נשמרו">
          {groups.map((g, i) => (
            <button key={g.submission_id} type="button" onClick={() => select(g.submission_id)}
                    className={`min-h-[44px] rounded-full border px-4 py-2 text-sm ${g.submission_id === current
                      ? 'border-primary-600 bg-primary-50 text-primary-800' : 'border-surface-300 text-gray-700'}`}>
              {g.student?.display_name ?? T.student(i + 1)}
            </button>
          ))}
        </nav>
      )}

      <section className="space-y-4 rounded-2xl border border-surface-200 bg-white p-4 shadow-sm">
        <div>
          <p className="mb-1 text-sm font-medium text-gray-700">{T.whoIsThis}</p>
          <StudentPicker
            key={group.submission_id}
            value={group.student?.student_id ?? null}
            onChange={(id) => { if (id !== group.student?.student_id) void assign(group.submission_id, id) }}
            source={source}
            suggestedName={suggestion?.match ? null : suggestion?.read_name}
            suggestedMatch={suggestion?.match ? { id: suggestion.match.student_id, name: suggestion.match.display_name } : null}
            suggestedMatchLabel={T.foundMatch}
            detecting={sug === 'loading'}
            detectingLabel={T.detecting}
            autoOpen={group.student_state !== 'confirmed' && sug !== undefined}
            placeholder="חיפוש תלמיד"
          />
        </div>

        <CaptureFlow
          key={group.submission_id}
          api={api}
          submissionId={group.submission_id}
          initialPages={group.pages}
          copy={TEACHER_FLOW}
          primaryCamera
          onState={(s) => setFlow((f) => (sameState(f[group.submission_id], s) ? f : { ...f, [group.submission_id]: s }))}
        />
      </section>

      {(state?.pending ?? 0) > 0 && (
        <p className="mt-2 text-center text-sm text-gray-600">{TEACHER_FLOW.uploading(state!.pending)}</p>
      )}
      {blockers.length > 0 && (
        <ul id="capture-blockers" className="mt-3 space-y-1 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900" role="alert">
          {blockers.map((b) => <li key={b}>{b}</li>)}
        </ul>
      )}

      <div className="sticky bottom-0 mt-4 flex gap-2 bg-surface-50 py-3">
        {/* Blocked-but-clickable (§11): a native `disabled` could not be clicked. */}
        <button type="button" onClick={() => void next()} aria-disabled={blocked.length > 0}
                aria-describedby={blocked.length ? 'capture-blockers' : undefined}
                className={`flex min-h-[48px] flex-1 items-center justify-center gap-2 rounded-xl border border-primary-600 px-4 text-primary-700 ${
                  blocked.length ? 'opacity-50' : 'hover:bg-primary-50'}`}>
          <Plus size={18} />{T.nextStudent}
        </button>
        <button type="button" onClick={() => void saveAll()} disabled={saving}
                aria-disabled={blocked.length > 0 && (state?.pageCount ?? 0) > 0}
                className={`flex min-h-[48px] flex-1 items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 text-white ${
                  blocked.length && (state?.pageCount ?? 0) > 0 ? 'opacity-50' : 'hover:bg-primary-700'}`}>
          {saving ? <Loader2 size={18} className="animate-spin" /> : <Save size={18} />}
          {saving ? T.saving : T.save}
        </button>
      </div>

      <Modal open={duplicate !== null} onClose={() => setDuplicate(null)} labelledBy="dup-title">
        {duplicate && (
          <div className="space-y-4 p-5" dir="rtl">
            <p id="dup-title" className="text-gray-900">
              {T.duplicateTitle(duplicate.name, duplicate.pages, duplicate.savedAt ? hhmm(duplicate.savedAt) : null)}
            </p>
            <div className="flex gap-2">
              <button type="button" data-autofocus onClick={() => setDuplicate(null)}
                      className="flex-1 rounded-lg border border-surface-300 py-2 text-gray-700">{T.cancel}</button>
              <button type="button" onClick={() => {
                const d = duplicate; setDuplicate(null)
                void assign(group.submission_id, d.studentId, true)
              }} className="flex-1 rounded-lg bg-primary-600 py-2 text-white">{T.replaceExisting}</button>
            </div>
          </div>
        )}
      </Modal>
    </Shell>
  )
}

function sameState(a: CaptureFlowState | undefined, b: CaptureFlowState): boolean {
  return !!a && a.pageCount === b.pageCount && a.pending === b.pending && a.awaiting === b.awaiting
    && a.firstPage?.page_id === b.firstPage?.page_id && a.firstPage?.status === b.firstPage?.status
}

function Shell({ children }: { children: React.ReactNode }) {
  return <main className="mx-auto min-h-screen max-w-xl px-4 py-5" dir="rtl">{children}</main>
}

function Loading() {
  return (
    <p className="flex items-center justify-center gap-2 py-10 text-gray-500">
      <Loader2 size={18} className="animate-spin" />{T.loading}
    </p>
  )
}
