import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import {
    answerForScope,
    buildReviewModel,
    questionTextForScope,
    scopeBasisChecks,
    scopeIdOf,
    scopeTitle,
    type WireDraft,
    type WireScope,
} from './grade-review-model';
import { cycleVerdict, type OverlayTerminals } from './verdict-cycle';
import { basisHash } from './feedback-staleness';
import type { NumericPolicy } from '@/lib/pricing';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES = path.resolve(HERE, '../../../backend/tests/fixtures/grade_review');
const readFixture = (name: string) =>
    JSON.parse(readFileSync(path.join(FIXTURES, name), 'utf-8'));

const POLICY: NumericPolicy = {
    precision: '0.25', rounding_mode: 'half_up', sum_tolerance: '0.01',
};

const scope = (over: Partial<WireScope> = {}): WireScope => ({
    question_id: 'q1',
    sub_question_id: 'א',
    points_possible: '4',
    points_awarded: '4',
    graded_by: 'llm',
    criterion_outcomes: [{
        criterion_id: 'q1.א.c0',
        description: 'הגדרת המחלקה',
        points_possible: '4',
        points_awarded: '4',
        checks: [
            {
                check_id: 'q1.א.c0.k1', text: 'שלוש תכונות', kind: 'required',
                points: '2', partial_fraction: '0.5', verdict: 'met',
                quote: 'private string name;', quote_status: 'exact', tariff: null,
            },
            {
                check_id: 'q1.א.c0.k2', text: 'התכונות private', kind: 'required',
                points: '2', partial_fraction: '0.5', verdict: 'met',
                quote: 'private bool isSportive;', quote_status: 'exact', tariff: null,
            },
        ],
    }],
    ...over,
});

const draftOf = (scopes: WireScope[], feedback?: WireDraft['feedback']): WireDraft =>
    ({ scope_outcomes: scopes, feedback, plan_version: 'hobby_tvshow/v5' });

const build = (draft: WireDraft, overlay: OverlayTerminals = {}, extra = {}) =>
    buildReviewModel({
        draft, overlay, policy: POLICY, answers: [], questions: [], ...extra,
    });

describe('scope identity', () => {
    it('builds a full-path id and a Hebrew title', () => {
        expect(scopeIdOf(scope())).toBe('q1.א');
        expect(scopeTitle(scope())).toBe('שאלה 1.א');
        expect(scopeIdOf(scope({ sub_question_id: null }))).toBe('q1');
        expect(scopeTitle(scope({ sub_question_id: null }))).toBe('שאלה 1');
    });
});

describe('joining the answer to the scope', () => {
    const answers = [
        { question_number: 1, sub_question_id: 'א', answer_text: 'exact answer' },
        { question_number: 1, sub_question_id: null, answer_text: 'whole-question answer' },
        { question_number: 2, sub_question_id: null, answer_text: 'q2 answer' },
    ];

    it('prefers the exact sub-question answer', () => {
        expect(answerForScope(scope(), answers)).toBe('exact answer');
    });

    /**
     * The transcription pipeline segments to depth 1, so a nested leaf usually
     * has no answer of its own. Without this fallback every nested rubric shows
     * an empty answer box next to a real grade — it looks like the student
     * wrote nothing and was marked anyway.
     */
    it('falls back to the whole-question answer for a nested scope', () => {
        expect(answerForScope(scope({ sub_question_id: 'ב' }), answers))
            .toBe('whole-question answer');
    });

    it('returns null when the question has no answer at all', () => {
        expect(answerForScope(scope({ question_id: 'q9' }), answers)).toBeNull();
    });

    it('does not confuse a non-numeric question id for question 1', () => {
        expect(answerForScope(scope({ question_id: 'qX' }), answers)).toBeNull();
    });

    it('joins question text with the same exact-then-ancestor rule', () => {
        const questions = [{ question_id: 'q1', sub_question_id: null, text: 'הגדירו מחלקה' }];
        expect(questionTextForScope(scope(), questions)).toBe('הגדירו מחלקה');
        expect(questionTextForScope(scope({ question_id: 'q7' }), questions)).toBeNull();
    });
});

describe('the review model', () => {
    it('prices from the EFFECTIVE verdicts, so the number follows her hand', () => {
        const draft = draftOf([scope()]);
        expect(build(draft).total).toBe('4.00');

        // ✓ → ✗ on a 2-point check.
        const overlay = cycleVerdict(
            cycleVerdict({}, 'q1.א.c0', 'q1.א.c0.k1', 'met'),
            'q1.א.c0', 'q1.א.c0.k1', 'met',
        );
        // met → not_met → partially_met after two cycles: 2 + 1 = 3.
        const model = build(draft, overlay);
        expect(model.total).toBe('3.00');
        expect(model.anyOverride).toBe(true);
        expect(model.scopes[0].overridden).toBe(true);
        expect(model.scopes[0].criteria[0].checks[0].overridden).toBe(true);
    });

    it('keeps Vivi\'s proposal beside the teacher\'s verdict', () => {
        const overlay = cycleVerdict({}, 'q1.א.c0', 'q1.א.c0.k1', 'met');
        const check = build(draftOf([scope()]), overlay).scopes[0].criteria[0].checks[0];
        expect(check.aiVerdict).toBe('met');        // provenance, never overwritten
        expect(check.verdict).toBe('not_met');      // her decision
    });

    it('counts markers per scope: unvalidated evidence and dead scopes', () => {
        const marked = scope({
            criterion_outcomes: [{
                criterion_id: 'c0', description: 'x',
                points_possible: '4', points_awarded: '0',
                checks: [{
                    check_id: 'k1', text: 't', kind: 'required', points: '4',
                    partial_fraction: '0.5', verdict: 'met',
                    quote: 'q', quote_status: 'not_found', tariff: null,
                }],
            }],
        });
        expect(build(draftOf([marked])).scopes[0].markerCount).toBe(1);
        expect(build(draftOf([scope({ graded_by: 'failed', criterion_outcomes: [] })]))
            .scopes[0].markerCount).toBe(1);
    });

    it('shows an excluded scope but never sums it into the total', () => {
        const excluded = scope({ question_id: 'q2', graded_by: 'excluded_by_selection' });
        const model = build(draftOf([scope(), excluded]));
        expect(model.scopes).toHaveLength(2);
        expect(model.total).toBe('4.00');           // q2's 4 points are not owed
        expect(model.possible).toBe('4');
    });

    it('REFUSES a pre-v5 draft rather than rendering empty checklists', () => {
        const v3 = draftOf([scope({
            criterion_outcomes: [{
                criterion_id: 'c0', description: 'x',
                points_possible: '4', points_awarded: '4', checks: null,
            }],
        })]);
        expect(build(v3).renderable).toBe(false);
        expect(build(draftOf([scope()])).renderable).toBe(true);
    });

    describe('feedback', () => {
        const checksVector = [
            { check_id: 'q1.א.c0.k1', verdict: 'met' as const },
            { check_id: 'q1.א.c0.k2', verdict: 'met' as const },
        ];

        it('is fresh while the verdicts match its basis', () => {
            const draft = draftOf([scope()], {
                scopes: { 'q1.א': { text: 'כל הכבוד', basis_hash: basisHash(checksVector) } },
                summary: { text: 'סיכום', basis_hash: basisHash(checksVector) },
            });
            const model = build(draft);
            expect(model.scopes[0].feedback.state).toBe('fresh');
            expect(model.summary.state).toBe('fresh');
        });

        it('goes stale for the scope AND the summary when a verdict moves', () => {
            const draft = draftOf([scope()], {
                scopes: { 'q1.א': { text: 'כל הכבוד', basis_hash: basisHash(checksVector) } },
                summary: { text: 'סיכום', basis_hash: basisHash(checksVector) },
            });
            const overlay = cycleVerdict({}, 'q1.א.c0', 'q1.א.c0.k1', 'met');
            const model = build(draft, overlay);
            expect(model.scopes[0].feedback.state).toBe('stale');
            expect(model.summary.state).toBe('stale');
        });

        it('reports absent feedback as absent — never as an error', () => {
            const model = build(draftOf([scope()]));
            expect(model.scopes[0].feedback.state).toBe('absent');
            expect(model.summary.state).toBe('absent');
        });

        it('never calls her own edit stale', () => {
            const draft = draftOf([scope()], {
                scopes: { 'q1.א': { text: 'כל הכבוד', basis_hash: basisHash(checksVector) } },
                summary: { text: 's', basis_hash: basisHash(checksVector) },
            });
            const overlay = cycleVerdict({}, 'q1.א.c0', 'q1.א.c0.k1', 'met');
            const model = buildReviewModel({
                draft, overlay, policy: POLICY, answers: [], questions: [],
                editedFeedback: new Set(['q1.א']),
                feedbackOverrides: { 'q1.א': 'הטקסט שלי' },
            });
            expect(model.scopes[0].feedback.state).toBe('fresh');
            expect(model.scopes[0].feedback.text).toBe('הטקסט שלי');
        });

        it('hashes the EFFECTIVE vector, in document order', () => {
            const overlay = cycleVerdict({}, 'q1.א.c0', 'q1.א.c0.k1', 'met');
            expect(scopeBasisChecks(scope(), overlay)).toEqual([
                { check_id: 'q1.א.c0.k1', verdict: 'not_met' },
                { check_id: 'q1.א.c0.k2', verdict: 'met' },
            ]);
        });
    });

    it('builds a real published draft end to end', () => {
        const model = build(readFixture('draft_dan_basiuk.json') as WireDraft);
        expect(model.renderable).toBe(true);
        expect(model.scopes.length).toBeGreaterThan(0);
        expect(model.anyOverride).toBe(false);
        // Every scope's own total is the sum of its terminals, and the test
        // total is the sum of the scopes — one arithmetic, checked end to end.
        for (const s of model.scopes) {
            const summed = s.criteria.reduce((n, c) => n + Number(c.awarded), 0);
            expect(Number(s.awarded)).toBeCloseTo(summed, 6);
        }
        expect(Number(model.total)).toBeCloseTo(
            model.scopes.reduce((n, s) => n + Number(s.awarded), 0), 6);
    });

    it('renders the synthetic edge-case draft, marks and all', () => {
        const model = build(readFixture('draft_SYNTHETIC_edge_cases.json') as WireDraft);
        expect(model.renderable).toBe(true);
        const marked = model.scopes.filter((s) => s.markerCount > 0);
        expect(marked.length).toBeGreaterThan(0);
        const skipped = model.scopes.find((s) => s.gradedBy === 'skipped_no_answer');
        expect(skipped).toBeDefined();
        expect(skipped?.awarded).toBe('0');
    });
});
