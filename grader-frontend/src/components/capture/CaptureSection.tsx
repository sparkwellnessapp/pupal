'use client'

/**
 * The batch detail's capture section (§8.4): the «צילום מבחנים» entry, the
 * student-link panel, and the submissions panel. Teacher-facing, feminine.
 *
 *  * «צילום מבחנים» — on a desktop, a dialog with the handoff QR (D2) to scan
 *    with her phone, and «או העלי תמונות מהמחשב» which opens the same capture
 *    page in this browser (the Desktop ruling); on a phone, straight there.
 *  * The link panel — one link per class (R6): a date, a class if the batch
 *    has none, then the link's state, a full-screen QR for the board (D3),
 *    copy, WhatsApp, close / reopen (same day only, R5).
 *  * The submissions panel — what arrived, with its badges, the pending (R1)
 *    and conflict resolutions, retry on a failed one; polled every 10 s while
 *    the link is open or anything is processing, else every 60 s (R7).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { Camera, Copy, Link2, Loader2, MessageCircle, QrCode as QrIcon, RotateCcw, X } from 'lucide-react'
import { toast } from 'sonner'

import { Modal } from '@/components/batch/Modal'
import { StudentPicker } from '@/components/StudentPicker'
import { P, hhmm } from '@/copy/capture'
import { listClasses, listStudents, retryBatchJob } from '@/lib/api'
import { addStudentsToClass } from '@/lib/class-membership'
import {
  CaptureApiError, closeCaptureLink, createCaptureHandoff, createCaptureLink, getCaptureLink,
  listCaptureSubmissions, reopenCaptureLink, resolveConflict, resolvePending,
} from '@/lib/capture-api'
import type { CaptureLink, CaptureSubmissionRow, CaptureSubmissionsResponse } from '@/types/capture'
import { normalizeName } from '@/utils/batch-partition'

import { NewClassStudents, type RosterOption } from './NewClassStudents'
import { QrCode } from './QrCode'

/** The class dropdown's «create one here» entry. */
const NEW_CLASS = '__new__'

function todayIsrael(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Jerusalem' }).format(new Date())
}

export function CaptureSection({ batchId, hasClass, onChanged, focusLink = false }: {
  batchId: string
  hasClass: boolean
  onChanged: () => void
  /** Arrived to create the student link (the home page's card): open on its form. */
  focusLink?: boolean
}) {
  const [link, setLink] = useState<CaptureLink | null | undefined>(undefined)
  const [panel, setPanel] = useState<CaptureSubmissionsResponse | null>(null)

  // A failed read keeps what is on screen: reading a dropped poll as «no link»
  // would swap her live link for the create form (the next poll retries).
  const loadLink = useCallback(() => getCaptureLink(batchId).then(setLink).catch(() => undefined), [batchId])
  const loadPanel = useCallback(() => listCaptureSubmissions(batchId).then(setPanel).catch(() => undefined), [batchId])

  useEffect(() => { void loadLink(); void loadPanel() }, [loadLink, loadPanel])

  const busy = panel?.rows.some((r) => r.version_status === 'queued' || r.version_status === 'running') ?? false
  useEffect(() => {
    const every = link?.state === 'open' || busy ? 10_000 : 60_000
    // The link's state is polled too: it closes at midnight and after a close.
    const t = setInterval(() => { void loadPanel(); void loadLink() }, every)
    return () => clearInterval(t)
  }, [link?.state, busy, loadPanel, loadLink])

  const refreshAll = () => { void loadPanel(); onChanged() }

  return (
    <section className="space-y-4" data-testid="capture-section" dir="rtl">
      <CaptureEntry batchId={batchId} />
      {link !== undefined && (
        <LinkPanel batchId={batchId} link={link} hasClass={hasClass} focus={focusLink}
                   onLink={(l) => { setLink(l); onChanged() }} />
      )}
      {panel && (panel.rows.length > 0 || link) && (
        <SubmissionsPanel batchId={batchId} panel={panel} onPanel={(p) => { setPanel(p); onChanged() }}
                          onRefresh={refreshAll} />
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// «צילום מבחנים» — the handoff (D2)
// ---------------------------------------------------------------------------

// The handoff token lives 10 minutes (D2): an open dialog renews it before then.
const HANDOFF_RENEW_MS = 9 * 60_000

function CaptureEntry({ batchId }: { batchId: string }) {
  const [open, setOpen] = useState(false)
  const [handoff, setHandoff] = useState<string | null>(null)
  const [handoffFailed, setHandoffFailed] = useState(false)
  const phone = typeof window !== 'undefined' && window.matchMedia('(pointer: coarse)').matches

  const issue = useCallback(async () => {
    setHandoffFailed(false)
    try { setHandoff((await createCaptureHandoff(batchId)).handoff_url) } catch {
      setHandoff(null); setHandoffFailed(true)
    }
  }, [batchId])

  useEffect(() => {
    if (!open) return
    const t = setInterval(() => { void issue() }, HANDOFF_RENEW_MS)
    return () => clearInterval(t)
  }, [open, issue])

  const start = async () => {
    if (phone) { window.location.href = `/capture/${batchId}`; return }
    setOpen(true)
    setHandoff(null)
    await issue()
  }

  return (
    <>
      <button type="button" onClick={() => void start()} data-testid="capture-entry"
              className="flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700">
        <Camera size={16} />{P.captureButton}
      </button>
      <Modal open={open} onClose={() => setOpen(false)} labelledBy="handoff-title">
        <div className="space-y-4 p-6 text-center" dir="rtl">
          <h2 id="handoff-title" className="text-lg font-semibold text-gray-900">{P.handoffTitle}</h2>
          <p className="text-sm text-gray-700">{P.handoffScan}</p>
          {handoff ? <QrCode value={handoff} label={P.handoffScan} />
            : handoffFailed ? (
              <div className="mx-auto flex h-60 w-60 flex-col items-center justify-center gap-3 rounded bg-surface-50 p-4">
                <p className="text-sm text-batch-red-ink" role="alert">{P.handoffFailed}</p>
                <button type="button" onClick={() => void issue()}
                        className="min-h-[44px] rounded-lg border border-batch-line px-4 text-sm text-batch-ink">{P.retry}</button>
              </div>
            ) : <div className="mx-auto h-60 w-60 animate-pulse rounded bg-surface-100" />}
          <p className="text-xs text-gray-500">{P.handoffExpires}</p>
          <Link href={`/capture/${batchId}`} className="block text-sm text-primary-700 underline">{P.handoffDesktop}</Link>
        </div>
      </Modal>
    </>
  )
}

// ---------------------------------------------------------------------------
// the link panel (§8.4)
// ---------------------------------------------------------------------------

function LinkPanel({ batchId, link, hasClass, onLink, focus = false }: {
  batchId: string; link: CaptureLink | null; hasClass: boolean; onLink: (l: CaptureLink) => void
  focus?: boolean
}) {
  const formRef = useRef<HTMLDivElement>(null)
  const createRef = useRef<HTMLButtonElement>(null)
  const classRef = useRef<HTMLSelectElement>(null)
  const newNameRef = useRef<HTMLInputElement>(null)
  const [examDate, setExamDate] = useState(todayIsrael())
  // null until loaded. A teacher with no class yet starts on «כיתה חדשה».
  const [classes, setClasses] = useState<{ id: string; name: string }[] | null>(null)
  const [choice, setChoice] = useState<string>('')
  const [newClass, setNewClass] = useState('')
  const [roster, setRoster] = useState<RosterOption[]>([])
  const [assigned, setAssigned] = useState<Set<string>>(new Set())
  const [busy, setBusy] = useState(false)
  const creatingClass = choice === NEW_CLASS
  // Once, when the form is ready: bring it into view and put her on its FIRST
  // step — the class when the batch has none (the create button is disabled
  // until one is chosen; the new-class name when she has no class at all),
  // else the create button.
  const focused = useRef(false)
  const ready = hasClass || classes !== null
  useEffect(() => {
    if (!focus || link || !ready || focused.current || !formRef.current) return
    focused.current = true
    formRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
    const target = hasClass ? createRef.current : creatingClass ? newNameRef.current : classRef.current
    target?.focus({ preventScroll: true })
  }, [focus, link, ready, hasClass, creatingClass])
  const [error, setError] = useState<string | null>(null)
  const [qr, setQr] = useState(false)

  useEffect(() => {
    if (!qr) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setQr(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [qr])

  useEffect(() => {
    if (hasClass || link) return
    listClasses().then((r) => {
      const list = r.classes.map((c) => ({ id: c.id, name: c.name }))
      setClasses(list)
      if (list.length === 0) setChoice(NEW_CLASS)
    }).catch(() => setClasses([]))
  }, [hasClass, link])

  // Her students, for the new class's «which of them» step — loaded once she
  // chooses to create one.
  useEffect(() => {
    if (!creatingClass || roster.length > 0) return
    listStudents().then((r) => setRoster(r.students.map((s) => ({ id: s.id, full_name: s.full_name }))))
      .catch(() => undefined)
  }, [creatingClass, roster.length])

  const create = async () => {
    setBusy(true); setError(null)
    try {
      const made = await createCaptureLink(batchId, {
        exam_date: examDate,
        ...(hasClass ? {} : creatingClass ? { new_class_name: newClass.trim() } : { class_id: choice }),
      })
      // The class exists now (created with the link, in one transaction):
      // put her chosen students in it. A partial failure is said, never
      // hidden — and the link is created either way.
      if (creatingClass && assigned.size > 0 && made.class_id) {
        const { failed } = await addStudentsToClass(made.class_id, [...assigned])
        if (failed > 0) toast.error(P.assignFailed(failed))
      }
      onLink(made)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const act = async (fn: () => Promise<CaptureLink>) => {
    setBusy(true); setError(null)
    try { onLink(await fn()) } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  if (!link) {
    return (
      <div ref={formRef}
           className={`space-y-3 rounded-zone border bg-white p-4 ${focus ? 'border-primary-500 ring-2 ring-primary-200' : 'border-batch-line'}`}
           data-testid="capture-link-form">
        <h3 className="flex items-center gap-2 font-semibold text-batch-ink"><Link2 size={16} />{P.linkTitle}</h3>
        <p className="text-sm text-batch-muted">{P.linkExplain}</p>
        <label className="block text-sm text-batch-ink">
          {P.examDate}
          <input type="date" value={examDate} onChange={(e) => setExamDate(e.target.value)}
                 className="mt-1 block rounded-lg border border-batch-line px-3 py-2" />
        </label>
        {!hasClass && (
          <div className="space-y-2 text-sm">
            <label className="block text-batch-ink">
              {P.className}
              <select ref={classRef} value={choice} disabled={classes === null || busy}
                      onChange={(e) => setChoice(e.target.value)}
                      data-testid="capture-class-select"
                      className="mt-1 block w-full rounded-lg border border-batch-line px-3 py-2">
                <option value="" disabled>{P.pickClass}</option>
                {(classes ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                <option value={NEW_CLASS}>{P.newClassOption}</option>
              </select>
            </label>
            {creatingClass && (
              <>
                <input ref={newNameRef} value={newClass} onChange={(e) => setNewClass(e.target.value)}
                       placeholder={P.newClassName} aria-label={P.newClassName} disabled={busy}
                       data-testid="capture-new-class-name"
                       className="block w-full rounded-lg border border-batch-line px-3 py-2" />
                {roster.length > 0
                  ? <NewClassStudents roster={roster} selected={assigned} onChange={setAssigned} disabled={busy} />
                  : <p className="text-xs text-batch-muted">{P.newClassNoStudents}</p>}
              </>
            )}
          </div>
        )}
        {error && <p className="text-sm text-batch-red-ink" role="alert">{error}</p>}
        <button type="button" ref={createRef}
                disabled={busy || (!hasClass && (creatingClass ? !newClass.trim() : !choice))}
                onClick={() => void create()}
                className="flex min-h-[44px] items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm text-white disabled:opacity-50">
          {busy && <Loader2 size={14} className="animate-spin" />}{P.createLink}
        </button>
      </div>
    )
  }

  const copy = async () => {
    try { await navigator.clipboard.writeText(link.url); toast.success(P.copied) } catch { /* clipboard blocked */ }
  }

  return (
    <div className="space-y-3 rounded-zone border border-batch-line bg-white p-4" data-testid="capture-link-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 font-semibold text-batch-ink"><Link2 size={16} />{P.linkTitle}</h3>
        <span className={`rounded-full px-2.5 py-0.5 text-xs ${link.state === 'open'
          ? 'bg-batch-teal-soft text-batch-teal-ink' : 'bg-surface-100 text-batch-muted'}`}>
          {P.linkState[link.state]}
        </span>
      </div>
      <p className="text-sm text-batch-muted">{link.class_name ? `${link.class_name} · ` : ''}{link.exam_date}</p>
      <div className="flex flex-wrap gap-2 text-sm">
        <Tool onClick={() => setQr(true)} icon={<QrIcon size={14} />}>{P.showQr}</Tool>
        <Tool onClick={() => void copy()} icon={<Copy size={14} />}>{P.copyLink}</Tool>
        <a href={`https://wa.me/?text=${encodeURIComponent(link.url)}`} target="_blank" rel="noreferrer"
           className="flex min-h-[44px] items-center gap-1.5 rounded-lg border border-batch-line px-3 py-1.5 text-batch-ink hover:bg-surface-50">
          <MessageCircle size={14} />{P.shareWhatsapp}
        </a>
        {link.state === 'closed'
          ? <Tool disabled={busy} onClick={() => void act(() => reopenCaptureLink(batchId))} icon={<RotateCcw size={14} />}>{P.reopenLink}</Tool>
          : <Tool disabled={busy} onClick={() => void act(() => closeCaptureLink(batchId))} icon={<X size={14} />}>{P.closeLink}</Tool>}
      </div>
      {error && <p className="text-sm text-batch-red-ink" role="alert">{error}</p>}
      {qr && (
        // D3 — full screen, for the board.
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-6 bg-white p-6" role="dialog"
             aria-modal="true" aria-label={P.showQr}>
          <QrCode value={link.url} size={Math.min(560, typeof window !== 'undefined' ? window.innerHeight - 220 : 480)}
                  label={P.qrInstruction} />
          <p className="max-w-xl text-center text-2xl text-gray-900">{P.qrInstruction}</p>
          <button type="button" onClick={() => setQr(false)} className="rounded-lg border border-surface-300 px-6 py-2 text-gray-700">
            {P.closeQr}
          </button>
        </div>
      )}
    </div>
  )
}

function Tool({ children, onClick, icon, disabled }: {
  children: React.ReactNode; onClick: () => void; icon: React.ReactNode; disabled?: boolean
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled}
            className="flex min-h-[44px] items-center gap-1.5 rounded-lg border border-batch-line px-3 py-1.5 text-batch-ink hover:bg-surface-50 disabled:opacity-50">
      {icon}{children}
    </button>
  )
}

// ---------------------------------------------------------------------------
// the submissions panel (§8.4)
// ---------------------------------------------------------------------------

function badgeOf(r: CaptureSubmissionRow): { label: string; tone: string } {
  if (r.student_state === 'conflict') return { label: P.badge.conflict, tone: 'bg-batch-red-soft text-batch-red-ink' }
  if (r.student_state === 'pending') return { label: P.badge.pending, tone: 'bg-batch-amber-soft text-batch-amber-ink' }
  if (r.version_status === 'failed') return { label: P.badge.failed, tone: 'bg-batch-red-soft text-batch-red-ink' }
  if (r.version_status === 'completed') return { label: P.badge.ready, tone: 'bg-batch-teal-soft text-batch-teal-ink' }
  return { label: P.badge.processing, tone: 'bg-surface-100 text-batch-muted' }
}

const claimOf = (r: CaptureSubmissionRow) =>
  r.student ? `id:${r.student.student_id}` : `name:${normalizeName(r.pending_student_name ?? '')}`

function SubmissionsPanel({ batchId, panel, onPanel, onRefresh }: {
  batchId: string; panel: CaptureSubmissionsResponse
  onPanel: (p: CaptureSubmissionsResponse) => void; onRefresh: () => void
}) {
  const [linking, setLinking] = useState<string | null>(null)
  const [conflict, setConflict] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const run = async (fn: () => Promise<CaptureSubmissionsResponse>) => {
    setNotice(null)
    try { onPanel(await fn()) } catch (e) { setNotice((e as Error).message) }
  }

  const group = useMemo(() => {
    const row = panel.rows.find((r) => r.submission_id === conflict)
    return row ? panel.rows.filter((r) => claimOf(r) === claimOf(row)) : []
  }, [conflict, panel.rows])

  return (
    <div className="space-y-3 rounded-zone border border-batch-line bg-white p-4" data-testid="capture-submissions">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-batch-ink">{P.submissionsTitle}</h3>
        <span className="text-sm text-batch-muted">
          {P.counter(panel.counter.submitted_students, panel.counter.roster_size ?? null)}
        </span>
      </div>
      {notice && <p className="text-sm text-batch-red-ink" role="alert">{notice}</p>}
      {panel.rows.length === 0 ? (
        <p className="text-sm text-batch-muted">{P.empty}</p>
      ) : (
        <ul className="divide-y divide-batch-line">
          {panel.rows.map((r) => {
            const badge = badgeOf(r)
            return (
              <li key={r.submission_id} className="flex flex-wrap items-center gap-2 py-2.5 text-sm">
                <span className="min-w-0 flex-1 truncate text-batch-ink">
                  {r.student?.display_name ?? r.pending_student_name}
                  <span className="mr-2 text-batch-muted">{P.pages(r.page_count)}</span>
                  {(r.version_no ?? 1) > 1 && r.saved_at && (
                    <span className="mr-2 text-batch-muted">{P.updatedAt(hhmm(r.saved_at))}</span>
                  )}
                  {r.conflict_note === 'late_resubmission' && (
                    <span className="mr-2 text-batch-amber-ink">{P.lateResubmission}</span>
                  )}
                </span>
                <span className={`rounded-full px-2.5 py-0.5 text-xs ${badge.tone}`}>{badge.label}</span>
                {r.version_status === 'failed' && r.job_id && (
                  <button type="button" className="text-primary-700 underline"
                          onClick={() => { setNotice(null); void retryBatchJob(batchId, r.job_id!).then(onRefresh)
                            .catch((e) => setNotice((e as Error).message || P.retryFailed)) }}>{P.retry}</button>
                )}
                {r.student_state === 'pending' && (
                  <>
                    <button type="button" className="text-primary-700 underline" onClick={() => {
                      setNotice(null)
                      resolvePending(batchId, r.submission_id, { approve_new: true }).then(onPanel).catch((e) => {
                        // The name already exists: offer linking, not an error (ruling).
                        if (e instanceof CaptureApiError && e.code === 'student_exists') {
                          setNotice(P.studentExists); setLinking(r.submission_id)
                        } else setNotice(e instanceof CaptureApiError && e.messageHe ? e.messageHe : (e as Error).message)
                      })
                    }}>{P.approveNew}</button>
                    <button type="button" className="text-primary-700 underline"
                            onClick={() => setLinking(linking === r.submission_id ? null : r.submission_id)}>{P.linkExisting}</button>
                  </>
                )}
                {r.student_state === 'conflict' && (
                  <button type="button" className="text-primary-700 underline" onClick={() => setConflict(r.submission_id)}>{P.resolve}</button>
                )}
                {linking === r.submission_id && (
                  <div className="w-full">
                    <StudentPicker value={null} autoOpen suggestedName={r.pending_student_name}
                                   onChange={(id) => { setLinking(null); void run(() => resolvePending(batchId, r.submission_id, { student_id: id })) }} />
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}

      <Modal open={conflict !== null} onClose={() => setConflict(null)} labelledBy="conflict-title" size="lg">
        <div className="space-y-4 p-5" dir="rtl">
          <h2 id="conflict-title" className="text-lg font-semibold text-gray-900">{P.conflictTitle}</h2>
          <div className="grid grid-cols-2 gap-3">
            {group.map((r) => (
              <div key={r.submission_id} className="space-y-2 rounded-lg border border-surface-200 p-2 text-sm">
                {r.page1_preview_url
                  // eslint-disable-next-line @next/next/no-img-element
                  ? <img src={r.page1_preview_url} alt="" className="w-full rounded" />
                  : <div className="aspect-[1/1.414] w-full rounded bg-surface-100" />}
                <p>{P.pages(r.page_count)}{r.saved_at ? ` · ${hhmm(r.saved_at)}` : ''}</p>
                {r.student_state === 'conflict' && (
                  <div className="flex flex-col gap-1">
                    <button type="button" className="rounded bg-primary-600 py-1.5 text-white" onClick={() => {
                      setConflict(null)
                      void run(() => resolveConflict(batchId, r.submission_id, { action: 'keep_this' }))
                    }}>{P.keepThis}</button>
                    <button type="button" className="rounded border border-surface-300 py-1.5 text-gray-700" onClick={() => {
                      setConflict(null)
                      void run(() => resolveConflict(batchId, r.submission_id, { action: 'discard_this' }))
                    }}>{P.discardThis}</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </Modal>
    </div>
  )
}
