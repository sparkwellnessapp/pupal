import { describe, expect, it } from 'vitest';

import { initialExpandedTerminals } from './criterion-disclosure';
import type { ReviewScope } from './grade-review-model';
import type { ReviewMarker } from './review-markers';

/**
 * The opening state.
 *
 * The stakes here are not cosmetic. Collapsing the breakdown is the one change
 * in this PR that could make «approve without reading» easier, and this
 * function is what holds that line: a folded header carries no signal of its
 * own (owner ruling 2026-09-11 — the chip roll-up read as noise), so what
 * opens ITSELF is the whole of the safety half of D1.
 */

type Check = ReviewScope['criteria'][number]['checks'][number];

const check = (over: Partial<Check> & { check_id: string }): Check => ({
    text: 'בדיקה', kind: 'required', canHighlight: false,
    aiVerdict: 'met', aiAwarded: '1', verdict: 'met', overridden: false,
    note: null, evidenceDisputed: false, awarded: '1', outOf: '1',
    terminalId: 'c1', ...over,
} as Check);

const scope = (criteria: ReviewScope['criteria']): ReviewScope => ({
    scopeId: 'q1.א', title: 'שאלה 1.א', questionText: null,
    answer: { kind: 'own', text: 'x' }, possible: '4', awarded: '4',
    overridden: false, gradedBy: 'llm', criteria,
    feedback: { text: '', state: 'absent' }, markerCount: 0,
} as unknown as ReviewScope);

const criterion = (terminalId: string, checks: Check[]) => ({
    terminalId, description: `קריטריון ${terminalId}`,
    awarded: '1', possible: '1', overridden: false, checks,
});

const marker = (over: Partial<ReviewMarker>): ReviewMarker => ({
    key: 'k', kind: 'check', id: 'x', scopeId: 'q1.א', reason: 'not_found', ...over,
});

describe('initialExpandedTerminals — collapsed, except where her eyes are needed', () => {
    const clean = criterion('c1', [check({ check_id: 'c1.k1' })]);

    it('collapses a criterion with nothing to say', () => {
        expect(initialExpandedTerminals([scope([clean])], [])).toEqual(new Set());
    });

    it('opens one carrying a CHECK marker — the same set F walks', () => {
        // Not a second "needs eyes" rule: `review-markers` is the one source,
        // and a fork would drift from the amber dot within a sprint.
        const markers = [marker({ kind: 'check', id: 'c1.k1', reason: 'not_found' })];
        expect(initialExpandedTerminals([scope([clean])], markers))
            .toEqual(new Set(['c1']));
    });

    it('opens one carrying a TERMINAL-anchored marker', () => {
        // A clamped or closed-world terminal produces a `scope`-kind marker
        // whose id is the TERMINAL, not a check. Matching on check ids alone
        // would silently hide exactly those.
        const markers = [marker({ kind: 'scope', id: 'c1', reason: 'bounds_clamped' })];
        expect(initialExpandedTerminals([scope([clean])], markers))
            .toEqual(new Set(['c1']));
    });

    it('opens one she has already decided herself', () => {
        const touched = criterion('c1', [check({ check_id: 'c1.k1', overridden: true })]);
        expect(initialExpandedTerminals([scope([touched])], []))
            .toEqual(new Set(['c1']));
    });

    it('opens one whose evidence she disputed', () => {
        const disputed = criterion('c1', [check({ check_id: 'c1.k1', evidenceDisputed: true })]);
        expect(initialExpandedTerminals([scope([disputed])], []))
            .toEqual(new Set(['c1']));
    });

    it('opens ONLY the criterion that carries the marker', () => {
        const flagged = criterion('c2', [check({ check_id: 'c2.k1', terminalId: 'c2' })]);
        const markers = [marker({ kind: 'check', id: 'c2.k1' })];
        expect(initialExpandedTerminals([scope([clean, flagged])], markers))
            .toEqual(new Set(['c2']));
    });

    it('ignores a marker that belongs to no criterion on the page', () => {
        // Scope-level markers (a failed or unanswered question) anchor on the
        // SCOPE id and must not open every box under it.
        const markers = [marker({ kind: 'scope', id: 'q1.א', reason: 'failed' })];
        expect(initialExpandedTerminals([scope([clean])], markers)).toEqual(new Set());
    });
});
