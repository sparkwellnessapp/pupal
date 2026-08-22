/**
 * R4 (decision 2) — the interstitial→dashboard skip-notice handoff: a
 * ONE-SHOT sessionStorage key (`vivi-skip-notice:{batchId}`), written by the
 * review interstitial's bulk accept when the server skipped items, read AND
 * CLEARED by the dashboard on mount. The App Router has no router state and a
 * query param would pollute the URL/history; sessionStorage is scoped and
 * transient. Storage failures are swallowed on both sides — the notice is a
 * courtesy, the refetch reconciles the data regardless.
 */

export const skipNoticeKey = (batchId: string) => `vivi-skip-notice:${batchId}`

export function handOffSkipNotice(batchId: string, notice: string): void {
  try {
    sessionStorage.setItem(skipNoticeKey(batchId), notice)
  } catch { /* storage unavailable → no notice; data still reconciles */ }
}

/** Read-and-clear (one-shot). Returns null when nothing was handed off. */
export function takeSkipNotice(batchId: string): string | null {
  try {
    const key = skipNoticeKey(batchId)
    const value = sessionStorage.getItem(key)
    if (value !== null) sessionStorage.removeItem(key)
    return value
  } catch {
    return null
  }
}


// ---------------------------------------------------------------------------
// D1 (closeout) — files that never became jobs.
//
// A batch has no memory of a file that failed to upload: B9.5 made JOBS the
// source of truth for the total, so 3-of-5 landing produces a coherent
// 3-item batch with no trace of the 2. The teacher continues, sees a tidy
// batch, and nothing tells her what is missing — a silent drop relocated
// from intake to navigation, which is exactly the class U4 exists to kill.
// Same one-shot, batch-scoped handoff as the skip notice above.
// ---------------------------------------------------------------------------

export const uploadFailuresKey = (batchId: string) => `vivi-upload-failures:${batchId}`

export function handOffUploadFailures(batchId: string, filenames: string[]): void {
  if (filenames.length === 0) return
  try {
    sessionStorage.setItem(uploadFailuresKey(batchId), JSON.stringify(filenames))
  } catch { /* storage unavailable → no notice; the files are still absent */ }
}

/** Read-and-clear (one-shot). Returns [] when nothing was handed off. */
export function takeUploadFailures(batchId: string): string[] {
  try {
    const key = uploadFailuresKey(batchId)
    const raw = sessionStorage.getItem(key)
    if (raw === null) return []
    sessionStorage.removeItem(key)
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === 'string') : []
  } catch {
    return []
  }
}
