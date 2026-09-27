/**
 * CWV-2 / GATE-1 — the client half, on the production row's shape
 * (graded_test 271813b4): the verifier addressed `q1.a.1.c0.k1`, the real check
 * `q1.א.1.c0.k1` therefore got no verdict (the pricer's `unverified_check`,
 * keyed by `metadata.check_id`), and an ERROR `closed_world_violation` whose
 * target exists nowhere made Approve a dead end.
 *
 * Under GATE-1 a blocker names something she can fix ON THIS SCREEN and takes
 * her there. So: the stray is never a blocker; the real check reads UNDECIDED
 * in place and blocks until she decides it, like any undecided check.
 */
import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

import { buildReviewModel, type WireDraft, type WireScope } from './grade-review-model';
import { cycleVerdict, emptyOverlay, setTerminalPoints, type Overlay } from './verdict-cycle';
import type { NumericPolicy } from '@/lib/pricing';
import { VerdictButton } from '@/components/grade-review/VerdictButton';

const POLICY: NumericPolicy = { precision: '0.25', rounding_mode: 'half_up', sum_tolerance: '0.01' };
const INTERNAL_ID = /\bq\d+\./;

const scope: WireScope = {
    question_id: 'q1', sub_question_id: 'א.1', points_possible: '12', points_awarded: '0',
    graded_by: 'llm',
    criterion_outcomes: [{
        criterion_id: 'q1.א.1.c0', description: 'טבלת מעקב',
        points_possible: '12', points_awarded: '0',
        checks: [{
            check_id: 'q1.א.1.c0.k1', text: 'כל 17 התאים בטבלת המעקב מלאים ונכונים',
            kind: 'counted', points: '12', partial_fraction: '0.5', verdict: 'not_met',
            quote: null, quote_status: null, tariff: null, unit_count: 17,
            units_correct: null, basis_he: 'לא אומת על ידי המודל',
        }],
    }],
} as WireScope;

const STRAY = {
    severity: 'error', annotation_type: 'closed_world_violation',
    target_id: 'q1.a.1.c0.k1', message: 'המודל החזיר פסיקה לבדיקה לא מוכרת: q1.a.1.c0.k1',
    metadata: { extra_id: 'q1.a.1.c0.k1', scope: 'q1.א.1' },
};
const NO_VERDICT = {
    severity: 'warning', annotation_type: 'unverified_check', target_id: 'q1.א.1.c0',
    message: "הבדיקה 'כל 17 התאים' לא אומתה על ידי המודל — לא ניתן זיכוי",
    metadata: { check_id: 'q1.א.1.c0.k1' },
};

const draft = (annotations: unknown[]): WireDraft =>
    ({ scope_outcomes: [scope], annotations, plan_version: 'p/v5' } as WireDraft);
const build = (d: WireDraft, overlay: Overlay = emptyOverlay()) =>
    buildReviewModel({ draft: d, overlay, policy: POLICY, questions: [] });
const theCheck = (d: WireDraft, overlay?: Overlay) =>
    build(d, overlay).scopes[0].criteria[0].checks[0];

describe('a stray verdict is never a blocker', () => {
    it('a legacy ERROR closed_world_violation does not block', () => {
        expect(build(draft([STRAY])).blockers).toEqual([]);
    });
    it('the new INFO form does not block either', () => {
        expect(build(draft([{ ...STRAY, severity: 'info' }])).blockers).toEqual([]);
    });
});

describe('the check it displaced reads UNDECIDED, in place', () => {
    it('is marked no-verdict, not an ordinary ✗', () => {
        expect(theCheck(draft([STRAY, NO_VERDICT])).noVerdict).toBe(true);
    });

    it('blocks Approve, anchored to its scope, in her words', () => {
        const { blockers } = build(draft([STRAY, NO_VERDICT]));
        expect(blockers).toHaveLength(1);
        expect(blockers[0].scopeId).toBe('q1.א.1');
        expect(blockers[0].message).not.toMatch(INTERNAL_ID);
        expect(blockers[0].message).not.toMatch(/מודל/);
    });

    it('deciding it clears the block and the undecided state', () => {
        const decided = cycleVerdict(emptyOverlay(), 'q1.א.1.c0', 'q1.א.1.c0.k1', 'not_met', 'counted');
        expect(build(draft([STRAY, NO_VERDICT]), decided).blockers).toEqual([]);
        expect(theCheck(draft([STRAY, NO_VERDICT]), decided).noVerdict).toBe(false);
    });

    it('choosing ✗ is kept as HER decision, not dropped as "same as Vivi"', () => {
        // The stored ✗ is the pricer's default, not a verdict, so the surface
        // cycles a no-verdict row on the confirm path (as it does an unverified
        // ✓): the first press records ✗ as hers, and returning to ✗ keeps it.
        const T = 'q1.א.1.c0', C = 'q1.א.1.c0.k1';
        const first = cycleVerdict(emptyOverlay(), T, C, 'not_met', 'counted', undefined, true);
        expect(build(draft([NO_VERDICT]), first).blockers).toEqual([]);
        const round = [1, 2, 3].reduce(
            (o) => cycleVerdict(o, T, C, 'not_met', 'counted', undefined, true), first);
        expect(theCheck(draft([NO_VERDICT]), round).verdict).toBe('not_met');
        expect(build(draft([NO_VERDICT]), round).blockers).toEqual([]);
    });

    it('a typed criterion amount decides it too (OD-R2 pin)', () => {
        const pinned = setTerminalPoints(emptyOverlay(), 'q1.א.1.c0', '6', () => 'not_met');
        expect(build(draft([NO_VERDICT]), pinned).blockers).toEqual([]);
    });

    it('the glyph says undecided, and names no machine', () => {
        const html = renderToStaticMarkup(
            <VerdictButton verdict="not_met" overridden={false} noVerdict onCycle={() => undefined} />);
        expect(html).toContain('data-verdict-shown="undecided"');
        expect(html).not.toMatch(/מודל/);
    });
});
