import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import {
    attentionLine,
    downloadSummary,
    etaText,
    pileCardState,
    pileCardTarget,
    rollupOf,
    sessionSummary,
    stepsLine,
    type GradedItem,
} from './grade-dashboard';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES = path.resolve(HERE, '../../../backend/tests/fixtures/grade_review');
const feed = (state: string) =>
    JSON.parse(readFileSync(path.join(FIXTURES, `batch_feed_${state}.json`), 'utf-8'));

const item = (over: Partial<GradedItem> = {}): GradedItem => ({
    graded_test_id: 'g1', student_name: 'דן', status: 'draft',
    look_count: 0, opened_at: null, returned_exam_state: 'none', ...over,
});

const LABELS = {
    grading: (l: number, t: number) => `ויוי מנקדת · נחתו ${l} מתוך ${t}`,
    audit: 'ביקורת עקביות מול הכיתה',
    auditDone: (n: number) => `ביקורת עקביות · עודכנו ${n}`,
    approve: (a: number, t: number) => `אישור וחתימה · ${a} מתוך ${t}`,
};

const ETA_LABELS = {
    firstLanding: (m: number) => `כל המבחנים ינחתו בעוד כ-${m} דקות`,
    remaining: (m: number) => `עוד כ-${m} דקות`,
    unknown: 'עוד רגע',
};

// ===========================================================================
// pile-card-state-grammar
// ===========================================================================
describe('pile-card-state-grammar', () => {
    it('maps every status to its card state', () => {
        expect(pileCardState(item({ status: 'pending' }))).toBe('pending');
        expect(pileCardState(item({ status: 'grading' }))).toBe('grading');
        expect(pileCardState(item({ status: 'failed' }))).toBe('failed');
        expect(pileCardState(item({ status: 'approved' }))).toBe('approved');
        expect(pileCardState(item({ status: 'draft', look_count: 0 }))).toBe('landed');
        expect(pileCardState(item({ status: 'draft', look_count: 4 }))).toBe('landed_marked');
    });

    it('calls an OPENED draft «בעריכה», not «נחת»', () => {
        expect(pileCardState(item({ opened_at: '2026-09-01T10:00:00Z', look_count: 4 })))
            .toBe('draft');
    });

    /**
     * `look_count: null` means the draft would not parse — the number is not
     * computable. It must NOT read as 0, which says "nothing to check" about
     * precisely the test that most needs her eye (§3.5a).
     */
    it('never reads an uncomputable count as zero', () => {
        const unparseable = item({ look_count: null });
        expect(pileCardState(unparseable)).toBe('landed');       // not landed_marked
        // …and the caller gets nothing to render as a number.
        expect(unparseable.look_count).toBeNull();
    });

    it('sends each card where D6 says', () => {
        expect(pileCardTarget(item({ status: 'draft' }))).toBe('review');
        expect(pileCardTarget(item({ status: 'approved' }))).toBe('preview');
        expect(pileCardTarget(item({ status: 'failed' }))).toBe('retry');
        expect(pileCardTarget(item({ status: 'grading' }))).toBeNull();
        expect(pileCardTarget(item({ status: 'pending' }))).toBeNull();
    });
});

// ===========================================================================
// steps-line-states
// ===========================================================================
describe('steps-line-states', () => {
    it('renders TWO steps while the audit is disabled (R-1)', () => {
        const steps = stepsLine(rollupOf([item(), item({ status: 'grading' })]),
            'disabled', LABELS);
        expect(steps.map((s) => s.key)).toEqual(['grading', 'approve']);
        // Not a dark third step: a step nobody can reach teaches her the line
        // is decorative, and the next real one gets skimmed past.
        expect(steps.find((s) => s.key === 'audit')).toBeUndefined();
    });

    it('adds the audit step when it is no longer disabled', () => {
        const steps = stepsLine(rollupOf([item()]), 'running', LABELS);
        expect(steps.map((s) => s.key)).toEqual(['grading', 'audit', 'approve']);
        expect(steps[1].state).toBe('active');
    });

    it('walks grading → approve as the batch progresses', () => {
        const landing = stepsLine(rollupOf([item({ status: 'grading' })]), 'disabled', LABELS);
        expect(landing[0].state).toBe('active');
        expect(landing[1].state).toBe('todo');

        const allLanded = stepsLine(rollupOf([item(), item()]), 'disabled', LABELS);
        expect(allLanded[0].state).toBe('done');
        expect(allLanded[1].state).toBe('active');

        const done = stepsLine(
            rollupOf([item({ status: 'approved' }), item({ status: 'approved' })]),
            'disabled', LABELS);
        expect(done.every((s) => s.state === 'done')).toBe(true);
    });

    it('counts a FAILED test as landed for the grading step — it will never land', () => {
        // Otherwise the first step sits at "4 of 5" forever and she waits for a
        // test that is not coming.
        const steps = stepsLine(
            rollupOf([item(), item({ status: 'failed' })]), 'disabled', LABELS);
        expect(steps[0].state).toBe('done');
    });

    it('matches every published fixture state', () => {
        for (const [state, expected] of Object.entries({
            landing: ['active', 'todo'],
            running: ['active', 'todo'],
            done: ['done', 'active'],
            complete: ['done', 'done'],
        })) {
            const payload = feed(state);
            const steps = stepsLine(
                rollupOf(payload.graded_tests), payload.audit_status, LABELS);
            expect(steps.map((s) => s.state), state).toEqual(expected);
        }
    });
});

// ===========================================================================
// the ETA
// ===========================================================================
describe('the ETA line', () => {
    it('says «עוד רגע» rather than a figure nothing supports', () => {
        expect(etaText({ kind: 'unknown', seconds: null }, ETA_LABELS)).toBe('עוד רגע');
        expect(etaText({ kind: 'remaining', seconds: null }, ETA_LABELS)).toBe('עוד רגע');
        expect(etaText(null, ETA_LABELS)).toBeNull();
    });

    it('rounds UP to whole minutes', () => {
        // 68s is "about 2 minutes", not "about 1" — the round that makes her
        // wait is smaller than the one that makes the product look late.
        expect(etaText({ kind: 'remaining', seconds: 68 }, ETA_LABELS)).toBe('עוד כ-2 דקות');
        expect(etaText({ kind: 'remaining', seconds: 10 }, ETA_LABELS)).toBe('עוד כ-1 דקות');
        expect(etaText({ kind: 'first_landing', seconds: 204 }, ETA_LABELS))
            .toBe('כל המבחנים ינחתו בעוד כ-4 דקות');
    });

    it('reads every published fixture', () => {
        expect(etaText(feed('landing').eta, ETA_LABELS)).toContain('4');
        expect(etaText(feed('running').eta, ETA_LABELS)).toContain('2');
        expect(etaText(feed('done').eta, ETA_LABELS)).toBe('עוד רגע');
        expect(etaText(feed('complete').eta, ETA_LABELS)).toBe('עוד רגע');
    });
});

// ===========================================================================
// attention-line-priority
// ===========================================================================
describe('attention-line-priority', () => {
    it('names the landed test with the most markers', () => {
        const worst = item({ graded_test_id: 'w', student_name: 'דין', look_count: 4 });
        const a = attentionLine([item({ look_count: 1 }), worst, item({ look_count: 2 })]);
        expect(a.kind).toBe('worst');
        expect(a.item?.graded_test_id).toBe('w');
        expect(a.markers).toBe(4);
    });

    it('never re-nominates a test she has already opened', () => {
        const opened = item({ look_count: 9, opened_at: '2026-09-01T10:00:00Z' });
        const fresh = item({ graded_test_id: 'f', look_count: 2 });
        expect(attentionLine([opened, fresh]).item?.graded_test_id).toBe('f');
    });

    /** No number to rank by, and inventing one to make it sortable is the
     *  substitution §3.5a forbids. */
    it('never nominates a test whose count is not computable', () => {
        expect(attentionLine([item({ look_count: null })]).kind).toBe('none');
    });

    it('says nothing when every landed test is clean', () => {
        expect(attentionLine([item({ look_count: 0 }), item({ look_count: 0 })]).kind)
            .toBe('none');
    });

    it('switches to DONE when the batch is finished', () => {
        expect(attentionLine([
            item({ status: 'approved' }), item({ status: 'approved' }),
        ]).kind).toBe('done');
    });

    it('counts a failed test toward completion — a batch completes with its hole showing', () => {
        expect(attentionLine([
            item({ status: 'approved' }), item({ status: 'failed' }),
        ]).kind).toBe('done');
    });

    it('reads the published fixtures the way the states are named', () => {
        expect(attentionLine(feed('landing').graded_tests).kind).toBe('none');
        expect(attentionLine(feed('running').graded_tests).item?.student_name)
            .toBe('דין עזרא');
        expect(attentionLine(feed('complete').graded_tests).kind).toBe('done');
    });
});

// ===========================================================================
// download-modal-reads-manifest
// ===========================================================================
describe('download-modal-reads-manifest', () => {
    it('counts approved-only, and says what it is leaving out', () => {
        expect(downloadSummary([
            item({ status: 'approved' }),
            item({ status: 'approved' }),
            item({ status: 'draft' }),
            item({ status: 'failed' }),
        ])).toEqual({
            included: 2, excludedNotApproved: 1, excludedUnavailable: 0, excludedFailed: 1,
        });
    });

    /**
     * A failed test is counted APART from an unapproved one. "N tests are not
     * yet approved" about a test that can never be approved sends her looking
     * for a review that does not exist — the fix is a retry, not a review.
     */
    it('never calls a FAILED test "not yet approved"', () => {
        const summary = downloadSummary([
            item({ status: 'approved' }), item({ status: 'failed' }),
        ]);
        expect(summary.excludedNotApproved).toBe(0);
        expect(summary.excludedFailed).toBe(1);
    });

    /**
     * THE REGRESSION GUARD. This used to exclude an approved test whose
     * returned exam was missing or outdated — and since NOTHING in the batch
     * flow ever rendered one, every approved test matched. A teacher who
     * approved five and clicked download was told she had approved none and
     * edited five. The download now renders what it needs, so neither state
     * excludes anything.
     */
    it('includes an approved test whose returned exam is missing or outdated', () => {
        expect(downloadSummary([
            item({ status: 'approved' }),
            item({ status: 'approved', returned_exam_state: 'stale' }),
            item({ status: 'approved', returned_exam_state: 'none' }),
        ])).toEqual({
            included: 3, excludedNotApproved: 0, excludedUnavailable: 0, excludedFailed: 0,
        });
    });

    it('reads the complete fixture', () => {
        // Four approved, one failed — the hole is excluded and counted.
        expect(downloadSummary(feed('complete').graded_tests))
            .toEqual({
                included: 4, excludedNotApproved: 0, excludedUnavailable: 0, excludedFailed: 1,
            });
    });
});

describe('sessionSummary', () => {
    it('reports what she did, and how long it took', () => {
        expect(sessionSummary(
            [item({ status: 'approved' }), item({ status: 'failed' })],
            '2026-09-01T18:00:00Z', '2026-09-01T18:41:00Z',
        )).toEqual({ approved: 1, failed: 1, minutes: 41 });
    });

    it('omits the duration rather than inventing one', () => {
        expect(sessionSummary([item()], null, null).minutes).toBeNull();
    });
});

describe('the denominator comes from the BATCH, not from the feed', () => {
    /**
     * `graded_tests` carries a row only for a test she has already accepted.
     * Counting the feed against itself reports «נחתו 2 מתוך 2» and «הכול מוכן»
     * on a ten-document batch with eight still ungraded — a dashboard grading
     * its own homework.
     */
    it('counts landed against the batch total, not the rows it has', () => {
        const two = [item({ status: 'approved' }), item({ status: 'approved' })];
        expect(rollupOf(two, 10).total).toBe(10);
        expect(attentionLine(two, 10).kind).not.toBe('done');
        // …and with every test accounted for, it IS done.
        expect(attentionLine(two, 2).kind).toBe('done');
    });

    it('never lets a stale batch total shrink below the rows it can see', () => {
        expect(rollupOf([item(), item(), item()], 1).total).toBe(3);
    });
});

describe('an all-failed batch is not "finished"', () => {
    it('refuses the done banner when nothing was actually signed', () => {
        // «הכול מוכן. 0 המבחנים המוחזרים נחתמו» is a sentence no teacher
        // should read: the arithmetic is satisfied and the outcome is the
        // opposite of complete.
        expect(attentionLine([item({ status: 'failed' }), item({ status: 'failed' })]).kind)
            .not.toBe('done');
    });

    it('still calls it done when at least one was signed', () => {
        expect(attentionLine([item({ status: 'approved' }), item({ status: 'failed' })]).kind)
            .toBe('done');
    });
});
