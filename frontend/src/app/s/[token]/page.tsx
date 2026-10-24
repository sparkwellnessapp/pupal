'use client'

/**
 * The student capture page (§8.2) — public, reached from the QR on the board.
 *
 * At the end of the exam, in class, each student photographs their own pages,
 * confirms their name, and saves. Five screens: the name, the instructions
 * (once), the pages, a review, done. Reopening the link on the SAME device
 * goes straight back to that device's submission (D1) — the device secret is
 * kept in localStorage per link and is the only thing that grants it.
 *
 * Nothing here sends a teacher's session, and no roster ever reaches this page:
 * identify answers one display name or nothing (SCN-9).
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams } from 'next/navigation'
import { Loader2 } from 'lucide-react'

import { CaptureFlow, type CaptureFlowState } from '@/components/capture/CaptureFlow'
import { S, STUDENT_FLOW, hhmm, longDate } from '@/copy/capture'
import { CaptureApiError, deviceKey, studentCaptureApi } from '@/lib/capture-api'
import type { StudentLinkInfo, SubmissionPages } from '@/types/capture'

type Step = 'loading' | 'state' | 'name' | 'confirm' | 'new' | 'instructions' | 'capture' | 'review' | 'done'

const SEEN_INSTRUCTIONS = 'vivi.capture.instructions'

function readLocal(key: string): string | null {
  try { return localStorage.getItem(key) } catch { return null }
}
function writeLocal(key: string, value: string) {
  try { localStorage.setItem(key, value) } catch { /* the page still works for this visit */ }
}

export default function StudentCapturePage() {
  const { token } = useParams<{ token: string }>()
  const [device, setDevice] = useState<string | null>(null)
  const api = useMemo(() => studentCaptureApi(token, () => device ?? readLocal(deviceKey(token))),
    [token, device])

  const [step, setStep] = useState<Step>('loading')
  const [info, setInfo] = useState<StudentLinkInfo | null>(null)
  const [invalid, setInvalid] = useState(false)
  const [name, setName] = useState('')
  const [match, setMatch] = useState<string | null>(null)
  const [sub, setSub] = useState<SubmissionPages | null>(null)
  // A load that failed for any reason but «no such link» is retried, never
  // reported as an invalid link (a dropped connection is not a bad QR).
  const [loadFailed, setLoadFailed] = useState(false)
  const [flow, setFlow] = useState<CaptureFlowState | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [resumed, setResumed] = useState(false)
  const [sentPages, setSentPages] = useState(0)

  const onError = useCallback((e: unknown) => {
    if (e instanceof CaptureApiError && e.status === 410) {
      setInfo((i) => (i ? { ...i, state: (e.extra.state as StudentLinkInfo['state']) ?? 'closed' } : i))
      setStep('state')
      return
    }
    if (e instanceof CaptureApiError && e.status === 404 && !info) { setInvalid(true); setStep('state'); return }
    setError(e instanceof CaptureApiError && e.messageHe ? e.messageHe : S.genericError)
  }, [info])

  const load = useCallback(() => {
    setStep('loading'); setLoadFailed(false)
    api.info().then((i) => {
      setInfo(i)
      if (i.state !== 'open') { setStep('state'); return }
      if (i.own_submission) {
        setSub(i.own_submission)
        setResumed(i.own_submission.pages.length > 0 && i.own_submission.status === 'saved')
        setStep('capture')
      } else setStep('name')
    }).catch((e) => {
      if (e instanceof CaptureApiError && e.status === 404) setInvalid(true)
      else setLoadFailed(true)
      setStep('state')
    })
  }, [api])

  useEffect(() => {
    setDevice(readLocal(deviceKey(token)))
    load()
  }, [token]) // eslint-disable-line react-hooks/exhaustive-deps

  const identify = async () => {
    if (!name.trim()) return
    setBusy(true); setError(null)
    try {
      const r = await api.identify(name.trim())
      setMatch(r.match?.display_name ?? null)
      setStep(r.match ? 'confirm' : 'new')
    } catch (e) { onError(e) } finally { setBusy(false) }
  }

  const create = async (confirmMatch: boolean) => {
    setBusy(true); setError(null)
    try {
      const r = await api.createSubmission(name.trim(), confirmMatch)
      writeLocal(deviceKey(token), r.device_secret)              // D1: this device, this link
      setDevice(r.device_secret)
      // A new submission is empty by definition — no second round trip that
      // could fail AFTER the device secret was already kept.
      setSub({ submission_id: r.submission_id, status: 'draft', pages: [], version_no: null,
               saved_at: null, updated_at: new Date().toISOString() })
      setStep(readLocal(SEEN_INSTRUCTIONS) ? 'capture' : 'instructions')
    } catch (e) { onError(e) } finally { setBusy(false) }
  }

  const save = async () => {
    if (!sub || !canSave) return
    setBusy(true); setError(null)
    try {
      const r = await api.save(sub.submission_id)
      setSentPages(r.page_count)
      // After an approval the server saved onto a NEW submission (D6): every
      // later edit continues there. The flow remounts on the id.
      setSub({ ...sub, submission_id: r.submission_id, status: 'saved', saved_at: r.saved_at,
               version_no: r.version_no })
      setStep('done')
    } catch (e) { onError(e) } finally { setBusy(false) }
  }

  const label = info?.exam_label
  const header = label ? [label.batch_name, label.class_name].filter(Boolean).join(' · ') : ''
  const pendingCount = (flow?.pending ?? 0) + (flow?.awaiting ?? 0)
  const failedCount = flow?.failed ?? 0
  const canSave = !!flow && flow.pageCount > 0 && pendingCount === 0 && failedCount === 0

  return (
    <main className="mx-auto min-h-screen max-w-xl px-4 py-6" dir="rtl">
      {header && <p className="mb-4 text-center text-sm text-gray-600">{header}</p>}
      {error && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{error}</p>}

      {step === 'loading' && (
        <p className="flex items-center justify-center gap-2 py-10 text-gray-500"><Loader2 className="animate-spin" size={18} />{S.loading}</p>
      )}

      {step === 'state' && (
        <p className="py-10 text-center text-lg text-gray-800">
          {loadFailed ? S.genericError
            : invalid || !info ? S.invalid
            : info.state === 'not_yet_open' ? S.notYetOpen(longDate(info.exam_label.exam_date))
            : S.closed}
        </p>
      )}
      {step === 'state' && loadFailed && (
        <Secondary onClick={load}>{S.tryAgain}</Secondary>
      )}

      {step === 'name' && (
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); void identify() }}>
          <label htmlFor="student-name" className="block text-lg font-medium text-gray-900">{S.askName}</label>
          <input id="student-name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name"
                 placeholder={S.namePlaceholder} maxLength={255}
                 className="w-full rounded-xl border border-surface-300 px-4 py-3 text-lg focus:outline-none focus:ring-2 focus:ring-primary-500" />
          <Primary disabled={busy || !name.trim()} busy={busy}>{S.continue}</Primary>
        </form>
      )}

      {step === 'confirm' && match && (
        <div className="space-y-4 text-center">
          <p className="text-2xl font-semibold text-gray-900">{S.isThisYou(match)}</p>
          <Primary onClick={() => void create(true)} disabled={busy} busy={busy}>{S.yesMe}</Primary>
          <Secondary onClick={() => setStep('new')}>{S.notMe}</Secondary>
        </div>
      )}

      {step === 'new' && (
        <div className="space-y-4">
          <p className="text-gray-800">{S.notOnRoster}</p>
          <Primary onClick={() => void create(false)} disabled={busy} busy={busy}>{S.addAsNew}</Primary>
          <Secondary onClick={() => setStep('name')}>{S.fixName}</Secondary>
        </div>
      )}

      {step === 'instructions' && (
        <div className="space-y-4">
          <h1 className="text-xl font-semibold text-gray-900">{S.instructionsTitle}</h1>
          <ul className="list-disc space-y-2 pr-5 text-gray-800">{S.instructions.map((l) => <li key={l}>{l}</li>)}</ul>
          <Primary onClick={() => { writeLocal(SEEN_INSTRUCTIONS, '1'); setStep('capture') }}>{S.continue}</Primary>
        </div>
      )}

      {(step === 'capture' || step === 'review') && sub && (
        <div className="space-y-4">
          {resumed && step === 'capture' && sub.saved_at && (
            <p className="rounded-lg bg-primary-50 px-3 py-2 text-sm text-primary-900">
              {S.resumed(sub.pages.length, hhmm(sub.saved_at))}
            </p>
          )}
          {step === 'review' && <h1 className="text-xl font-semibold text-gray-900">{S.reviewTitle}</h1>}
          <CaptureFlow key={sub.submission_id} api={api} submissionId={sub.submission_id}
                       initialPages={sub.pages} copy={STUDENT_FLOW} onState={setFlow} primaryCamera />
          {pendingCount > 0 && <p className="text-center text-sm text-gray-600">{STUDENT_FLOW.uploading(pendingCount)}</p>}
          {failedCount > 0 && <p className="text-center text-sm text-red-700">{STUDENT_FLOW.failedUploads(failedCount)}</p>}
          {step === 'capture' ? (
            <Primary onClick={() => setStep('review')} disabled={!flow || flow.pageCount === 0}>{S.done}</Primary>
          ) : (
            <Primary onClick={() => void save()} disabled={busy || !canSave} busy={busy}>
              {busy ? S.saving : S.save}
            </Primary>
          )}
        </div>
      )}

      {step === 'done' && (
        <div className="space-y-4 text-center">
          <p className="text-lg text-gray-900">{S.sent(sentPages)}</p>
          <Secondary onClick={() => { setResumed(true); setStep('capture') }}>{S.backToEdit}</Secondary>
        </div>
      )}
    </main>
  )
}

function Primary({ children, onClick, disabled, busy }: {
  children: React.ReactNode; onClick?: () => void; disabled?: boolean; busy?: boolean
}) {
  return (
    <button type={onClick ? 'button' : 'submit'} onClick={onClick} disabled={disabled}
            className="flex min-h-[52px] w-full items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 text-lg text-white disabled:opacity-50">
      {busy && <Loader2 size={18} className="animate-spin" />}{children}
    </button>
  )
}

function Secondary({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick}
            className="min-h-[48px] w-full rounded-xl border border-surface-300 px-4 text-gray-700">{children}</button>
  )
}
