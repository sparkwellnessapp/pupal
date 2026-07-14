import { beforeEach, describe, expect, it } from 'vitest';

import {
    RENEW_WHEN_REMAINING_MS,
    clearUnsavedWork,
    decodeJwt,
    isTokenExpired,
    msUntilExpiry,
    peekUnsavedWork,
    shouldRenew,
    stashUnsavedWork,
} from './session';

// A minimal localStorage so the stash can be tested without jsdom.
class MemoryStorage {
    private m = new Map<string, string>();
    getItem(k: string) { return this.m.has(k) ? this.m.get(k)! : null; }
    setItem(k: string, v: string) { this.m.set(k, String(v)); }
    removeItem(k: string) { this.m.delete(k); }
    clear() { this.m.clear(); }
}

/** Build an unsigned JWT with the given claims — we only ever READ `exp`. */
function makeToken(claims: Record<string, unknown>): string {
    const b64 = (o: unknown) =>
        Buffer.from(JSON.stringify(o)).toString('base64')
            .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    return `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64(claims)}.sig`;
}

const NOW = 1_800_000_000_000;          // fixed clock
const HOUR = 60 * 60 * 1000;
const DAY = 24 * HOUR;

beforeEach(() => {
    (globalThis as unknown as { localStorage: MemoryStorage }).localStorage = new MemoryStorage();
});

describe('JWT reading (the client CAN tell expired from malformed — the backend cannot)', () => {
    it('decodes exp', () => {
        const t = makeToken({ exp: Math.floor((NOW + DAY) / 1000), sub: 'u1' });
        expect(decodeJwt(t)?.sub).toBe('u1');
        expect(msUntilExpiry(t, NOW)).toBeGreaterThan(DAY - 1000);
    });

    it('returns null for garbage rather than throwing', () => {
        expect(decodeJwt('not-a-jwt')).toBeNull();
        expect(decodeJwt(null)).toBeNull();
        expect(msUntilExpiry('garbage', NOW)).toBeNull();
    });

    it('detects an EXPIRED token (this is what makes the "session expired" message honest)', () => {
        const expired = makeToken({ exp: Math.floor((NOW - HOUR) / 1000) });
        const live = makeToken({ exp: Math.floor((NOW + HOUR) / 1000) });
        expect(isTokenExpired(expired, NOW)).toBe(true);
        expect(isTokenExpired(live, NOW)).toBe(false);
        // a malformed token is NOT "expired" — it's simply unreadable
        expect(isTokenExpired('garbage', NOW)).toBe(false);
    });
});

describe('sliding renewal window (C9: renew BEFORE expiry — /auth/refresh cannot rescue an expired token)', () => {
    it('does NOT renew a fresh 7-day token', () => {
        const fresh = makeToken({ exp: Math.floor((NOW + 7 * DAY) / 1000) });
        expect(shouldRenew(fresh, NOW)).toBe(false);
    });

    it('DOES renew once inside the 48h window', () => {
        const soon = makeToken({ exp: Math.floor((NOW + 47 * HOUR) / 1000) });
        expect(RENEW_WHEN_REMAINING_MS).toBe(48 * HOUR);
        expect(shouldRenew(soon, NOW)).toBe(true);
    });

    it('does NOT try to renew an ALREADY-expired token (the endpoint would 401)', () => {
        const dead = makeToken({ exp: Math.floor((NOW - HOUR) / 1000) });
        expect(shouldRenew(dead, NOW)).toBe(false);
    });

    it('does not renew an unreadable token', () => {
        expect(shouldRenew('garbage', NOW)).toBe(false);
    });
});

describe('crash-stash round-trip (C10: a forced re-login must not destroy review work)', () => {
    it('stashes, peeks, and clears', () => {
        expect(peekUnsavedWork()).toBeNull();

        stashUnsavedWork({
            kind: 'rubric_review',
            rubricName: 'מבחן חצי שנתי',
            questions: [{ question_id: 'q1', criteria: [] }],
            declaredTotal: 100,
            extractionJobId: 'job-123',
        });

        const got = peekUnsavedWork();
        expect(got?.kind).toBe('rubric_review');
        expect(got?.rubricName).toBe('מבחן חצי שנתי');
        expect(got?.declaredTotal).toBe(100);
        expect(got?.extractionJobId).toBe('job-123');
        expect(got?.savedAt).toBeTypeOf('number');

        clearUnsavedWork();
        expect(peekUnsavedWork()).toBeNull();
    });

    it('ignores a corrupt stash instead of throwing', () => {
        localStorage.setItem('vivi_unsaved_work', '{not json');
        expect(peekUnsavedWork()).toBeNull();
    });

    it('rejects a stash with no questions (nothing worth restoring)', () => {
        localStorage.setItem('vivi_unsaved_work', JSON.stringify({ kind: 'rubric_review' }));
        expect(peekUnsavedWork()).toBeNull();
    });
});
