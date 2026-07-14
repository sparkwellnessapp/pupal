'use client';

/**
 * PR-2 — the error-surface convention.
 *
 *   TRANSPORT / AUTH errors  -> sonner toast   (this module)
 *   DOMAIN / validation      -> existing inline banners + the wizard modal
 *
 * We adopt sonner because it ALREADY EXISTS and is already mounted, RTL-configured,
 * in app/layout.tsx (`<Toaster position="top-center" richColors dir="rtl" />`) —
 * it was simply never used outside one page. Picking from what exists beats
 * inventing a surface. The 54 inline `setError` sites are deliberately NOT migrated:
 * a rubric point-sum violation is not a network failure and should not be a toast.
 */

import { toast } from 'sonner';

import { ApiAuthError, ApiError } from './api';
import { getStoredToken, isTokenExpired } from './session';

/** The message shown when a session actually lapsed.
 * The BACKEND cannot tell expired from malformed (both -> 401 "Not authenticated"),
 * but the CLIENT can, by reading the JWT `exp` locally — so we say the true thing
 * without needing any backend change. */
export function authErrorMessage(): string {
    return isTokenExpired(getStoredToken())
        ? 'פג תוקף ההתחברות — יש להתחבר מחדש'
        : 'אין הרשאה לפעולה זו';
}

/** Normalize any thrown value into a human-facing Hebrew string. */
export function toMessage(err: unknown): string {
    if (err instanceof ApiAuthError) return authErrorMessage();
    if (err instanceof ApiError) return err.detail;
    if (err instanceof Error) return err.message;
    return 'אירעה שגיאה בלתי צפויה';
}

/** Surface a transport/auth failure. Returns true if it was an auth failure, so
 * callers can also stop polling / stash / redirect. */
export function surfaceError(err: unknown): boolean {
    const isAuth = err instanceof ApiAuthError;
    toast.error(toMessage(err));
    return isAuth;
}
