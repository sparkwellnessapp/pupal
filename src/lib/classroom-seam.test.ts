/**
 * P3 wave 0 (P2-review item 3) — the `_classroomFetch` seam's own safety net.
 *
 * The seam was rewritten from apiFetchChecked to a raw fetch + explicit
 * status ladder after the D4 journey exposed its 409 branch as dead code.
 * That ladder serves EVERY classroom consumer (StudentPicker, classes,
 * memberships) — each rung gets its own assertion here:
 *   401 → ApiAuthError (terminal) · 409 → typed ClassroomConflictError with
 *   the server detail · 500 → normalized ApiError with the server detail ·
 *   network failure → propagates. Plus the happy path.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ApiAuthError,
  ApiError,
  ClassroomConflictError,
  createStudent,
  VALIDATION_ERROR_HE,
} from '@/lib/api'

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

beforeEach(() => {
  vi.stubGlobal('localStorage', {
    getItem: () => 'stub-token',
    setItem: () => undefined,
    removeItem: () => undefined,
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('_classroomFetch status ladder (via createStudent)', () => {
  it('409 → typed ClassroomConflictError carrying the server detail', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      jsonResponse({ detail: 'כבר קיים תלמיד בשם זה' }, 409)))
    const err = await createStudent({ full_name: 'דנה לוי' }).catch((e) => e)
    expect(err).toBeInstanceOf(ClassroomConflictError)
    expect(err.detail).toBe('כבר קיים תלמיד בשם זה')
  })

  it('401 → ApiAuthError (terminal), never a conflict', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      jsonResponse({ detail: 'Not authenticated' }, 401)))
    const err = await createStudent({ full_name: 'דנה לוי' }).catch((e) => e)
    expect(err).toBeInstanceOf(ApiAuthError)
    expect(err).not.toBeInstanceOf(ClassroomConflictError)
  })

  it('500 → normalized ApiError carrying the server detail', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      jsonResponse({ detail: 'תקלה זמנית בשרת' }, 500)))
    const err = await createStudent({ full_name: 'דנה לוי' }).catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err).not.toBeInstanceOf(ClassroomConflictError)
    expect(err.message).toBe('תקלה זמנית בשרת')
  })

  it('network failure propagates (no swallow, no fake conflict)', async () => {
    const boom = new TypeError('Failed to fetch')
    vi.stubGlobal('fetch', vi.fn(async () => { throw boom }))
    const err = await createStudent({ full_name: 'דנה לוי' }).catch((e) => e)
    expect(err).toBe(boom)
  })

  it('201 happy path returns the created student', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      jsonResponse({ id: 's1', full_name: 'דנה לוי' }, 201)))
    await expect(createStudent({ full_name: 'דנה לוי' })).resolves.toMatchObject({
      id: 's1', full_name: 'דנה לוי',
    })
  })
})

// ---------------------------------------------------------------------------
// E3 (closeout) — the ladder's MIDDLE cases. Hand-rolled status ladders
// characteristically cover the ends (auth, conflict, happy path) and miss what
// sits between them.
// ---------------------------------------------------------------------------

describe('_classroomFetch — 404 and 422 (the middle rungs)', () => {
  it('404 is NOT swallowed as a generic failure: status preserved, server detail kept', async () => {
    // §9: cross-tenant access returns 404 (403 would leak existence). The
    // client must be able to tell "not yours / not found" from "server broke".
    vi.stubGlobal('fetch', vi.fn(async () =>
      jsonResponse({ detail: 'התלמיד לא נמצא' }, 404)))
    const err = await createStudent({ full_name: 'רז' }).catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err).not.toBeInstanceOf(ClassroomConflictError)
    expect((err as ApiError).status).toBe(404)
    expect((err as ApiError).detail).toBe('התלמיד לא נמצא')
  })

  it('422 renders HEBREW, never FastAPI\'s English validation list', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({
      detail: [{ type: 'string_too_short', loc: ['body', 'full_name'],
                 msg: 'String should have at least 1 character', input: '' }],
    }, 422)))
    const err = await createStudent({ full_name: '' }).catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).status).toBe(422)
    expect((err as ApiError).detail).toBe(VALIDATION_ERROR_HE)
    expect((err as ApiError).detail).not.toMatch(/[A-Za-z]{4,}/)   // no English leak
  })
})
