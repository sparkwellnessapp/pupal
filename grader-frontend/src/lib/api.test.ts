import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiAuthError, ApiError, apiFetch, apiFetchRaw } from './api';

// getAuthHeaders reads localStorage; stub both without pulling in jsdom.
class MemoryStorage {
    private m = new Map<string, string>();
    getItem(k: string) { return this.m.has(k) ? this.m.get(k)! : null; }
    setItem(k: string, v: string) { this.m.set(k, String(v)); }
    removeItem(k: string) { this.m.delete(k); }
}

function jsonResponse(status: number, body: unknown): Response {
    return new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
    });
}

beforeEach(() => {
    (globalThis as unknown as { localStorage: MemoryStorage }).localStorage = new MemoryStorage();
    // getAuthToken() is SSR-guarded (`typeof window === 'undefined'` -> null), so a
    // browser-ish global must exist for the header to be attached. This mirrors the
    // real client, where it always does.
    (globalThis as unknown as { window: unknown }).window = globalThis;
    localStorage.setItem('pupal_auth_token', 'tok-123');
});

afterEach(() => {
    vi.unstubAllGlobals();
});

describe('apiFetch — the one seam (PR-2)', () => {
    it('attaches the auth header on every call', async () => {
        const spy = vi.fn(async (_url: string, _init?: RequestInit) => jsonResponse(200, { ok: true }));
        vi.stubGlobal('fetch', spy);

        await apiFetch('/api/v0/thing');

        const init = spy.mock.calls[0][1] as RequestInit;
        expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok-123');
    });

    it('returns the parsed body on 2xx', async () => {
        vi.stubGlobal('fetch', async () => jsonResponse(200, { id: 7 }));
        await expect(apiFetch<{ id: number }>('/x')).resolves.toEqual({ id: 7 });
    });

    it('throws ApiAuthError on 401 — TERMINAL, never a transient to back off on', async () => {
        vi.stubGlobal('fetch', async () => jsonResponse(401, { detail: 'Not authenticated' }));

        const err = await apiFetch('/x').catch((e: unknown) => e) as ApiError;
        expect(err).toBeInstanceOf(ApiAuthError);
        expect(err).toBeInstanceOf(ApiError);      // ApiAuthError IS an ApiError
        expect(err.status).toBe(401);
    });

    it('throws ApiAuthError on 403 too', async () => {
        vi.stubGlobal('fetch', async () => jsonResponse(403, { detail: 'Forbidden' }));
        const err = await apiFetch('/x').catch((e: unknown) => e) as ApiError;
        expect(err).toBeInstanceOf(ApiAuthError);
        expect(err.status).toBe(403);
    });

    it('normalizes a FastAPI `detail` string into ApiError.detail', async () => {
        vi.stubGlobal('fetch', async () => jsonResponse(409, { detail: 'המסמך כבר בעיבוד' }));

        const err = await apiFetch('/x').catch((e: unknown) => e) as ApiError;
        expect(err).toBeInstanceOf(ApiError);
        expect(err).not.toBeInstanceOf(ApiAuthError);
        expect(err.status).toBe(409);
        expect(err.detail).toBe('המסמך כבר בעיבוד');
    });

    it('normalizes a nested detail.message_he', async () => {
        vi.stubGlobal('fetch', async () =>
            jsonResponse(400, { detail: { message_he: 'שגיאת אימות' } }));
        const err = await apiFetch('/x').catch((e: unknown) => e) as ApiError;
        expect(err.detail).toBe('שגיאת אימות');
    });

    it('falls back to a readable message when the body is not JSON', async () => {
        vi.stubGlobal('fetch', async () => new Response('<html>502</html>', { status: 502 }));
        const err = await apiFetch('/x').catch((e: unknown) => e) as ApiError;
        expect(err).toBeInstanceOf(ApiError);
        expect(err.detail).toContain('502');
    });

    it('NEVER auto-retries — a mutation must not silently repeat', async () => {
        const spy = vi.fn(async (_url: string, _init?: RequestInit) => jsonResponse(500, { detail: 'boom' }));
        vi.stubGlobal('fetch', spy);

        await apiFetch('/x', { method: 'POST' }).catch(() => { /* expected */ });

        expect(spy).toHaveBeenCalledTimes(1);
    });
});

describe('apiFetchRaw — the carve-out for sites that own their status', () => {
    it('does NOT throw on a non-OK status (streaming + the warnings/RubricSaveError paths)', async () => {
        vi.stubGlobal('fetch', async () => jsonResponse(400, { detail: 'domain' }));

        const response = await apiFetchRaw('/x');   // must not throw
        expect(response.status).toBe(400);
        await expect(response.json()).resolves.toEqual({ detail: 'domain' });
    });

    it('still attaches auth headers', async () => {
        const spy = vi.fn(async (_url: string, _init?: RequestInit) => jsonResponse(200, {}));
        vi.stubGlobal('fetch', spy);
        await apiFetchRaw('/x');
        const init = spy.mock.calls[0][1] as RequestInit;
        expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok-123');
    });
});
