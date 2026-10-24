/**
 * In-house scanning — the API, as THREE adapters over one shape (§8.5).
 *
 *   authenticated   the teacher's normal session — the link, the handoff, the
 *                   submissions panel. Rides `apiFetch` (the one seam).
 *   capture session the teacher capture page on a phone that exchanged the
 *                   desktop's QR: `Authorization: CaptureSession <token>`, and
 *                   nothing else is sent.
 *   student token   the public link: the token in the PATH, the device secret
 *                   as `X-Capture-Device`, and NEVER a teacher's Bearer — a
 *                   logged-in teacher testing her own link must not leak her
 *                   session into it, so these calls do not touch getAuthHeaders.
 *
 * `CapturePagesApi` is what CaptureFlow needs; both the teacher and the
 * student adapters implement it, so the flow owns no auth (§8.1).
 */
import { apiFetch, jsonInit } from './api'
import { getAuthHeaders } from './auth'
import type {
  CaptureContentType, CaptureHandoff, CaptureLink, CaptureSubmissionsResponse,
  IdentifyResponse, NameSuggestResponse, PageCreateResponse, PageView, Quad, RosterStudent,
  Rotation, SaveResponse, StudentLinkInfo, SubmissionPages, SubmissionView, TeacherCaptureState,
} from '@/types/capture'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080'

/** A capture refusal: the server's machine `code`, its Hebrew line, and any
 *  extra fields of the detail (e.g. `page_ids`, `existing_submission_id`). */
export class CaptureApiError extends Error {
  status: number
  code: string
  messageHe: string
  extra: Record<string, unknown>
  constructor(status: number, code: string, messageHe: string, extra: Record<string, unknown> = {}) {
    super(messageHe || code)
    this.name = 'CaptureApiError'
    this.status = status
    this.code = code
    this.messageHe = messageHe
    this.extra = extra
  }
}

/** Every capture call is BOUNDED: a fetch that stalls (a phone backgrounded
 *  mid-request, a dead school WiFi) must reject, or the item it belongs to
 *  sits «בהעלאה» forever and blocks the save. 45 s covers the server's own
 *  10 s analysis bound with room; an abort is a NETWORK failure (retryable). */
const CALL_TIMEOUT_MS = 45_000
/** A photo PUT: up to 50 MB on a slow uplink. */
const PUT_TIMEOUT_MS = 300_000

async function timedFetch(url: string, init: RequestInit, ms: number): Promise<Response> {
  const ctrl = new AbortController()
  const t = setTimeout(() => ctrl.abort(), ms)
  try {
    return await fetch(url, { ...init, signal: ctrl.signal })
  } finally {
    clearTimeout(t)
  }
}

async function captureFetch<T>(path: string, init: RequestInit, headers: Record<string, string>): Promise<T> {
  let res: Response
  try {
    res = await timedFetch(`${API_BASE}${path}`, {
      ...init,
      headers: { ...headers, ...((init.headers as Record<string, string>) || {}) },
      referrerPolicy: 'no-referrer',
    }, CALL_TIMEOUT_MS)
  } catch {
    throw new CaptureApiError(0, 'network', 'אין חיבור לרשת — נסו שוב')
  }
  if (res.status === 204) return undefined as T
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const d = body?.detail
    if (d && typeof d === 'object' && !Array.isArray(d)) {
      const { code, message_he, ...extra } = d as Record<string, unknown>
      throw new CaptureApiError(res.status, String(code ?? 'error'), String(message_he ?? ''), extra)
    }
    throw new CaptureApiError(res.status, res.status === 404 ? 'not_found' : 'error',
      typeof d === 'string' ? d : '')
  }
  return body as T
}

function jsonBody(method: string, body?: unknown): RequestInit {
  return body === undefined
    ? { method }
    : { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
}

// ---------------------------------------------------------------------------
// the shape CaptureFlow consumes
// ---------------------------------------------------------------------------

export interface CapturePagesApi {
  getSubmission(submissionId: string): Promise<SubmissionPages>
  createPage(submissionId: string, contentType: CaptureContentType): Promise<PageCreateResponse>
  confirmUpload(submissionId: string, pageId: string): Promise<PageView>
  patchPage(submissionId: string, pageId: string, body: { corners?: Quad; rotation?: Rotation }): Promise<PageView>
  resetCorners(submissionId: string, pageId: string, to: 'auto' | 'full_frame'): Promise<PageView>
  deletePage(submissionId: string, pageId: string): Promise<void>
  reorder(submissionId: string, pageIds: string[]): Promise<void>
  save(submissionId: string): Promise<SaveResponse>
}

function pagesApi(base: string, call: <T>(path: string, init: RequestInit) => Promise<T>): CapturePagesApi {
  return {
    getSubmission: (s) => call(`${base}/submissions/${s}`, { method: 'GET' }),
    createPage: (s, contentType) => call(`${base}/submissions/${s}/pages`, jsonBody('POST', { content_type: contentType })),
    confirmUpload: (s, p) => call(`${base}/submissions/${s}/pages/${p}/uploaded`, { method: 'POST' }),
    patchPage: (s, p, body) => call(`${base}/submissions/${s}/pages/${p}`, jsonBody('PATCH', body)),
    resetCorners: (s, p, to) => call(`${base}/submissions/${s}/pages/${p}/reset-corners`, jsonBody('POST', { to })),
    deletePage: (s, p) => call(`${base}/submissions/${s}/pages/${p}`, { method: 'DELETE' }),
    reorder: (s, ids) => call(`${base}/submissions/${s}/order`, jsonBody('PUT', { page_ids: ids })),
    save: (s) => call(`${base}/submissions/${s}/save`, { method: 'POST' }),
  }
}

// ---------------------------------------------------------------------------
// teacher capture page — her normal session, or a capture session
// ---------------------------------------------------------------------------

export type TeacherCaptureAuth = { kind: 'session' } | { kind: 'capture'; token: string }

export interface TeacherCaptureApi extends CapturePagesApi {
  state(): Promise<TeacherCaptureState>
  roster(): Promise<RosterStudent[]>
  createSubmission(): Promise<SubmissionView>
  assignStudent(submissionId: string, body:
    { student_id: string; replace_existing?: boolean } | { create: { name: string } }): Promise<SubmissionView>
  nameSuggest(submissionId: string): Promise<NameSuggestResponse>
}

export function teacherCaptureApi(batchId: string, auth: TeacherCaptureAuth): TeacherCaptureApi {
  const base = `/api/v0/capture/teacher/${batchId}`
  // Her normal session rides the SAME auth headers apiFetch sends; it goes
  // through captureFetch only to keep the refusal's machine `code` (apiFetch
  // keeps just the Hebrew line, and the flow branches on the code).
  const call = <T>(path: string, init: RequestInit): Promise<T> =>
    captureFetch<T>(path, init, auth.kind === 'capture'
      ? { Authorization: `CaptureSession ${auth.token}` }
      : getAuthHeaders() as Record<string, string>)
  return {
    ...pagesApi(base, call),
    state: () => call(base, { method: 'GET' }),
    roster: async () => (await call<{ students: RosterStudent[] }>(`${base}/students`, { method: 'GET' })).students,
    createSubmission: () => call(`${base}/submissions`, { method: 'POST' }),
    assignStudent: (s, body) => call(`${base}/submissions/${s}/student`, jsonBody('PUT', body)),
    nameSuggest: (s) => call(`${base}/submissions/${s}/name-suggest`, { method: 'POST' }),
  }
}

export async function exchangeHandoff(handoffToken: string): Promise<{ capture_session: string; batch_id: string; expires_at: string }> {
  return captureFetch('/api/v0/capture/handoff/exchange', jsonBody('POST', { handoff_token: handoffToken }), {})
}

// ---------------------------------------------------------------------------
// the student link — the token in the path, the device secret in a header
// ---------------------------------------------------------------------------

export interface StudentCaptureApi extends CapturePagesApi {
  info(): Promise<StudentLinkInfo>
  identify(name: string): Promise<IdentifyResponse>
  createSubmission(name: string, confirmMatch: boolean): Promise<{ submission_id: string; device_secret: string }>
}

export function studentCaptureApi(token: string, getDevice: () => string | null): StudentCaptureApi {
  const base = `/api/v0/capture/s/${encodeURIComponent(token)}`
  const call = <T>(path: string, init: RequestInit): Promise<T> => {
    const device = getDevice()
    return captureFetch<T>(path, init, device ? { 'X-Capture-Device': device } : {})
  }
  return {
    ...pagesApi(base, call),
    info: () => call(base, { method: 'GET' }),
    identify: (name) => call(`${base}/identify`, jsonBody('POST', { name })),
    createSubmission: (name, confirmMatch) =>
      call(`${base}/submissions`, jsonBody('POST', { name, confirm_match: confirmMatch })),
  }
}

/** D1: the device secret lives in this browser, per link — `vivi.capture.{link}`. */
export const deviceKey = (token: string) => `vivi.capture.${token}`

// ---------------------------------------------------------------------------
// authenticated (batch detail) — the link, the handoff, the panel
// ---------------------------------------------------------------------------

const B = (batchId: string) => `/api/v0/batches/${batchId}`

/** Her session's Bearer, with the refusal's machine `code` kept (apiFetch
 *  keeps only the Hebrew line, and these callers branch on the code). */
const authed = <T>(path: string, init: RequestInit = { method: 'GET' }) =>
  captureFetch<T>(path, init, getAuthHeaders() as Record<string, string>)

/** null when the batch has no link — a 404 is an ANSWER here. Any other
 *  failure throws: reading a 500 or a dropped connection as "no link yet"
 *  would offer a create form the server then refuses. */
export async function getCaptureLink(batchId: string): Promise<CaptureLink | null> {
  try {
    return await authed<CaptureLink>(`${B(batchId)}/capture-link`)
  } catch (err) {
    if (err instanceof CaptureApiError && err.status === 404) return null
    throw err
  }
}

export const createCaptureLink = (batchId: string, body:
  { exam_date: string; class_id?: string | null; new_class_name?: string | null }) =>
  apiFetch<CaptureLink>(`${B(batchId)}/capture-link`, jsonInit('POST', body))
export const closeCaptureLink = (batchId: string) =>
  apiFetch<CaptureLink>(`${B(batchId)}/capture-link/close`, { method: 'POST' })
export const reopenCaptureLink = (batchId: string) =>
  apiFetch<CaptureLink>(`${B(batchId)}/capture-link/reopen`, { method: 'POST' })
export const rotateCaptureLink = (batchId: string) =>
  apiFetch<CaptureLink>(`${B(batchId)}/capture-link/rotate-token`, { method: 'POST' })
export const createCaptureHandoff = (batchId: string) =>
  apiFetch<CaptureHandoff>(`${B(batchId)}/capture-handoff`, { method: 'POST' })
export const listCaptureSubmissions = (batchId: string) =>
  apiFetch<CaptureSubmissionsResponse>(`${B(batchId)}/capture-submissions`)
export const resolvePending = (batchId: string, submissionId: string,
  body: { student_id: string } | { approve_new: true }) =>
  authed<CaptureSubmissionsResponse>(
    `${B(batchId)}/capture-submissions/${submissionId}/resolve-pending`, jsonBody('POST', body))
export const resolveConflict = (batchId: string, submissionId: string,
  body: { action: 'keep_this' | 'discard_this'; student_id?: string }) =>
  apiFetch<CaptureSubmissionsResponse>(
    `${B(batchId)}/capture-submissions/${submissionId}/resolve-conflict`, jsonInit('POST', body))

// ---------------------------------------------------------------------------
// the photo itself — straight to GCS on the signed URL (OD-S10)
// ---------------------------------------------------------------------------

/** PUT the photo to its signed URL. Network failures retry ×3 with backoff;
 *  an HTTP refusal (expired URL, a file over the silent cap) does not. The URL
 *  is WRITE-ONCE (x-goog-if-generation-match: 0) and belongs to ONE queued
 *  file (one page id), so a 412 means an earlier attempt of THIS file landed
 *  and only its answer was lost — success, whether it is this call's retry or
 *  the item's own retry after a failure. */
export async function putPhoto(url: string, headers: Record<string, string>, file: Blob): Promise<void> {
  let lastError: unknown = null
  for (let attempt = 0; attempt < 4; attempt++) {
    if (attempt > 0) await new Promise((r) => setTimeout(r, 1000 * 2 ** (attempt - 1)))
    let res: Response
    try {
      res = await timedFetch(url, { method: 'PUT', headers, body: file }, PUT_TIMEOUT_MS)
    } catch (err) {
      lastError = err
      continue
    }
    if (res.ok || res.status === 412) return
    throw new CaptureApiError(res.status, 'upload_refused', 'ההעלאה נדחתה — צלמו שוב')
  }
  throw new CaptureApiError(0, 'network', 'אין חיבור לרשת — נסו שוב', { cause: String(lastError) })
}
