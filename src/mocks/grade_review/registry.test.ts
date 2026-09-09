import { describe, it, expect } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import {
    BATCH_FEED_STATES,
    COVERAGE_GAPS,
    FIXTURE_STUDENTS,
    MANIFEST_STALE_PENDING,
    PENDING_FIXTURES,
    PRESENT_FIXTURES,
    PendingFixtureError,
    assertFixturePublished,
    fixtureUrl,
} from './registry';

/**
 * The registry is a MIRROR of the backend's `MANIFEST.json`, and this test is
 * what stops it lying — the same structural-mirror discipline as
 * `test_payload_fidelity` on the backend, where a hand-maintained mirror
 * silently dropped four fields and shipped three nulls to a live screen.
 *
 * The failure it prevents is specific: PR-G5 publishes `overlay_examples.json`,
 * nobody updates this file, and the mock layer keeps refusing a fixture that
 * now exists — so F2 gets built against AI-only state and the override path
 * meets its first real data at integration.
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES = path.resolve(HERE, '../../../../backend/tests/fixtures/grade_review');
const manifest = JSON.parse(readFileSync(path.join(FIXTURES, 'MANIFEST.json'), 'utf-8'));

describe('grade-review fixture registry mirrors the backend manifest', () => {
    it('lists the backend pending entries, minus the ones since published', () => {
        // Not a blind toEqual: the manifest is written by
        // gen_grade_review_fixtures.py and the batch feed by a second script
        // that does not update it, so the manifest can be stale. The registry
        // follows DISK and records the disagreement (see below).
        const expected = Object.fromEntries(
            Object.entries(manifest.pending as Record<string, string>)
                .filter(([key]) => !MANIFEST_STALE_PENDING.includes(key)),
        );
        expect(PENDING_FIXTURES).toEqual(expected);
    });

    it('invents no pending entry the backend never declared', () => {
        for (const key of Object.keys(PENDING_FIXTURES)) {
            expect(Object.keys(manifest.pending)).toContain(key);
        }
    });

    /**
     * THE tripwire. A fixture that lands while the manifest still calls it
     * pending would leave the mock refusing an endpoint that now has real
     * data — F1 would be built against a gap that had already closed.
     */
    it('claims pending only what is genuinely absent from disk', () => {
        const published = Object.keys(PENDING_FIXTURES)
            .filter((f) => existsSync(path.join(FIXTURES, f)));
        expect(published).toEqual([]);
    });

    it('records exactly which manifest entries have gone stale', () => {
        // When the backend regenerates MANIFEST.json this fails, and the
        // MANIFEST_STALE_PENDING block gets deleted. Failing on the FIX is the
        // point: the exception must not outlive the disagreement.
        for (const stale of MANIFEST_STALE_PENDING) {
            expect(Object.keys(manifest.pending)).toContain(stale);
        }
    });

    it('has all four dashboard states on disk', () => {
        for (const state of BATCH_FEED_STATES) {
            expect(existsSync(path.join(FIXTURES, `batch_feed_${state}.json`))).toBe(true);
        }
    });

    /**
     * `running` carries a null look_count on purpose (owner, 2026-08-31): the
     * unparseable draft gets NO number, not a reassuring 0, because 0 reads as
     * "nothing to check" on precisely the test that most needs her eye. If a
     * regeneration ever turns that null into a 0, the honest-rendering
     * requirement silently disappears — so it is asserted here, not trusted.
     */
    it('keeps the null look_count that the running state exists to prove', () => {
        const running = JSON.parse(
            readFileSync(path.join(FIXTURES, 'batch_feed_running.json'), 'utf-8'));
        const nulls = running.graded_tests
            .filter((t: { status: string; look_count: number | null }) =>
                t.status === 'draft' && t.look_count === null);
        expect(nulls.length).toBeGreaterThan(0);
    });

    it('repeats the backend coverage gaps verbatim, so absence reads as observed', () => {
        for (const [gap, reason] of Object.entries(COVERAGE_GAPS)) {
            expect(manifest.coverage_gap[gap]).toBe(reason);
        }
    });

    it('claims present only what is actually on disk', () => {
        const missing = PRESENT_FIXTURES.filter((f) => !existsSync(path.join(FIXTURES, f)));
        expect(missing).toEqual([]);
    });

    it('names the five pilot students the drafts were generated for', () => {
        expect(FIXTURE_STUDENTS.length).toBe(5);
        for (const student of FIXTURE_STUDENTS) {
            expect(existsSync(path.join(FIXTURES, `draft_${student}.json`))).toBe(true);
        }
    });

    it('is pinned to the v5 provenance the review module requires', () => {
        // The review module renders `checks` and nothing else. A fixture set
        // regenerated from a pre-G1 run would carry none, and every card would
        // render empty rather than fail — so the pin is asserted, not assumed.
        expect(manifest.provenance.plan_version).toBe('hobby_tvshow/v5');
        expect(manifest.coverage.terminals_with_checks).toBeGreaterThan(0);
    });
});

describe('a pending fixture refuses instead of inventing a shape', () => {
    it('throws with the backend reason for a named pending fixture', () => {
        expect(() => assertFixturePublished('overlay_examples.json'))
            .toThrow(/PR-G5/);
    });

    it('no longer refuses the batch feed — PR-G8 published it', () => {
        for (const state of BATCH_FEED_STATES) {
            expect(() => assertFixturePublished(`batch_feed_${state}.json`)).not.toThrow();
        }
    });

    it('throws a typed error, so a caller can tell a gap from a bug', () => {
        try {
            assertFixturePublished('audit_deltas_example.json');
            expect.unreachable('should have refused');
        } catch (error) {
            expect(error).toBeInstanceOf(PendingFixtureError);
            expect((error as PendingFixtureError).fixture).toBe('audit_deltas_example.json');
        }
    });

    it('passes a published fixture straight through', () => {
        expect(() => assertFixturePublished('draft_dan_basiuk.json')).not.toThrow();
        expect(() => assertFixturePublished('pricing_vectors.json')).not.toThrow();
    });

    it('routes the browser at the dev handler, never at a copy in src/', () => {
        expect(fixtureUrl('draft_din_ezra.json'))
            .toBe('/api/dev-fixtures/grade_review/draft_din_ezra.json');
    });
});
