'use client';

/**
 * PR-2 — session lifetime + the crash-stash.
 *
 * Two independent problems, both rooted in the same finding:
 *
 *  (C9) A pre-expiry `POST /auth/refresh` endpoint ALREADY EXISTS on the backend
 *       and nothing ever called it. It is gated on get_current_user, so it can
 *       renew a *valid* token but cannot rescue an *expired* one. Therefore the
 *       cheapest correct fix is to renew BEFORE expiry, client-side, using the
 *       endpoint that already exists — no backend change at all.
 *
 *  (C10) There is ZERO client-side persistence of in-progress work. A forced
 *       re-login destroys everything the teacher just reviewed. With a 7-day TTL
 *       that is rare — but when it happens it costs exactly the after-school hour
 *       the product exists to give back. So: stash on auth failure, offer restore
 *       after login. This is the SMALLEST cut of the persistence gap — general
 *       draft autosave is PR-5.
 *
 * The backend cannot distinguish expired from malformed (both -> 401 "Not
 * authenticated", C8) — but the CLIENT can, because the JWT `exp` is readable
 * locally. So we never needed a backend change to say "your session expired".
 */

const TOKEN_KEY = 'pupal_auth_token';
const STASH_KEY = 'vivi_unsaved_work';

/** Renew when less than this remains. 7-day TTL => an active teacher is renewed
 * on any visit inside the last 2 days, which makes mid-session expiry
 * effectively unreachable without ever touching the backend. */
export const RENEW_WHEN_REMAINING_MS = 48 * 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// JWT (read-only; we never verify — the server does that. We only read `exp`.)
// ---------------------------------------------------------------------------

export interface JwtClaims {
    exp?: number;   // seconds since epoch
    sub?: string;
}

export function decodeJwt(token: string | null): JwtClaims | null {
    if (!token) return null;
    try {
        const payload = token.split('.')[1];
        if (!payload) return null;
        const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
        return JSON.parse(json) as JwtClaims;
    } catch {
        return null;   // malformed — indistinguishable from garbage, and that's fine
    }
}

/** ms until expiry; null when there is no readable exp. Negative => already expired. */
export function msUntilExpiry(token: string | null, now: number = Date.now()): number | null {
    const claims = decodeJwt(token);
    if (!claims?.exp) return null;
    return claims.exp * 1000 - now;
}

/** True when the token is readable AND its exp has passed — this is what lets us
 * say "פג תוקף ההתחברות" instead of a generic auth error, with no backend change. */
export function isTokenExpired(token: string | null, now: number = Date.now()): boolean {
    const ms = msUntilExpiry(token, now);
    return ms !== null && ms <= 0;
}

export function shouldRenew(token: string | null, now: number = Date.now()): boolean {
    const ms = msUntilExpiry(token, now);
    if (ms === null) return false;          // unreadable -> nothing useful to do
    return ms > 0 && ms < RENEW_WHEN_REMAINING_MS;
}

// ---------------------------------------------------------------------------
// The crash-stash (C10)
// ---------------------------------------------------------------------------

export interface UnsavedWork {
    kind: 'rubric_review';
    savedAt: number;
    rubricName?: string;
    /** ExtractRubricResponse-shaped question tree, mid-edit. */
    questions: unknown;
    annotations?: unknown;
    declaredTotal?: number | null;
    /** PR-3: must survive the stash, or restoring after an auth expiry drops the
     *  "choose k of N" groups and the rubric becomes unsaveable (INV-4). */
    selectionGroups?: unknown;
    /** PR-1: the extraction RESULT is already durable server-side (the job row).
     * What this stash protects is the teacher's EDITS on top of it. */
    extractionJobId?: string | null;
}

export function stashUnsavedWork(work: Omit<UnsavedWork, 'savedAt'>): void {
    try {
        const payload: UnsavedWork = { ...work, savedAt: Date.now() };
        localStorage.setItem(STASH_KEY, JSON.stringify(payload));
    } catch {
        // Storage full / disabled — losing the stash must never break the redirect.
    }
}

export function peekUnsavedWork(): UnsavedWork | null {
    try {
        const raw = localStorage.getItem(STASH_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw) as UnsavedWork;
        if (!parsed?.kind || !parsed?.questions) return null;
        return parsed;
    } catch {
        return null;
    }
}

export function clearUnsavedWork(): void {
    try {
        localStorage.removeItem(STASH_KEY);
    } catch {
        /* ignore */
    }
}

export function getStoredToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(TOKEN_KEY);
}
