import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import {
    ancestorPaths,
    answerViewOf,
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
        draft, overlay, policy: POLICY, questions: [], ...extra,
    });

describe('scope identity', () => {
    it('builds a full-path id and a Hebrew title', () => {
        expect(scopeIdOf(scope())).toBe('q1.א');
        expect(scopeTitle(scope())).toBe('שאלה 1.א');
        expect(scopeIdOf(scope({ sub_question_id: null }))).toBe('q1');
        expect(scopeTitle(scope({ sub_question_id: null }))).toBe('שאלה 1');
    });
});

describe('the answer view — read, never re-derived [EVD-1]', () => {
    /**
     * This replaced a client-side JOIN that re-implemented the backend's
     * nearest-ancestor rule as "exact, else whole-question". Its own header
     * claimed parity with `gradable_compiler` and it silently failed at
     * DEPTH 2: a leaf `q1.א.1` whose answer was inherited from `q1.א` matched
     * neither probe, so the surface rendered «no answer in the approved
     * transcription» next to a 12/12 grade and a verbatim quote from that very
     * answer. The server now sends the fact; there is nothing left to derive.
     */
    it('reads an own answer', () => {
        const view = answerViewOf(scope({
            student_answer: { text: 'her words', source: 'own' },
        }));
        expect(view).toEqual({ kind: 'own', text: 'her words' });
    });

    it('reads an inherited answer AND keeps the ancestor it came from', () => {
        const view = answerViewOf(scope({
            sub_question_id: 'א.1',
            student_answer: { text: 'the whole סעיף', source: 'inherited', inherited_from: 'א' },
        }));
        expect(view).toEqual({ kind: 'inherited', text: 'the whole סעיף', from: 'א' });
    });

    it('tolerates an inherited answer whose ancestor was not named', () => {
        const view = answerViewOf(scope({
            student_answer: { text: 't', source: 'inherited' },
        }));
        expect(view).toEqual({ kind: 'inherited', text: 't', from: null });
    });

    it('says MISSING only when the grader itself skipped for want of an answer', () => {
        expect(answerViewOf(scope({ graded_by: 'skipped_no_answer' })))
            .toEqual({ kind: 'missing' });
    });

    /**
     * THE REGRESSION GUARD. A scope the grader actually graded, with no
     * evidence attached, is a contradiction in the data — and the one thing
     * the surface must never do is resolve it by accusing the student.
     */
    it('says UNAVAILABLE — never missing — for a graded scope with no evidence', () => {
        expect(answerViewOf(scope({ graded_by: 'llm' }))).toEqual({ kind: 'unavailable' });
        expect(answerViewOf(scope({ graded_by: 'failed' }))).toEqual({ kind: 'unavailable' });
        expect(answerViewOf(scope({ graded_by: 'excluded_by_selection' })))
            .toEqual({ kind: 'unavailable' });
    });

    it('joins question text with an exact-then-ancestor rule', () => {
        const questions = [{ question_id: 'q1', sub_question_id: null, text: 'הגדירו מחלקה' }];
        expect(questionTextForScope(scope(), questions)).toBe('הגדירו מחלקה');
    });
});

describe('ancestorPaths — the shared nearest-ancestor walk', () => {
    it('walks a nested path outward, ending at the whole question', () => {
        expect(ancestorPaths('א.1')).toEqual(['א.1', 'א', null]);
        expect(ancestorPaths('א.1.ii')).toEqual(['א.1.ii', 'א.1', 'א', null]);
    });

    it('handles a depth-1 path and a direct-criteria scope', () => {
        expect(ancestorPaths('א')).toEqual(['א', null]);
        expect(ancestorPaths(null)).toEqual([null]);
        expect(ancestorPaths(undefined)).toEqual([null]);
    });
});

describe('question text at depth 2', () => {
    /**
     * The defect this pins: the resolver probed EXACT then WHOLE-QUESTION and
     * skipped every intermediate ancestor. A leaf `א.1` therefore never saw
     * `א`'s prose, so the «השאלה» disclosure rendered the whole-question stem —
     * or, when the parent had none, nothing at all — at the exact moment the
     * teacher is judging whether the grade is right.
     */
    const questions = [
        { question_id: 'q1', sub_question_id: null, text: 'preamble' },
        { question_id: 'q1', sub_question_id: 'א', text: 'the א stem' },
        { question_id: 'q1', sub_question_id: 'א.1', text: 'part 1 of א' },
    ];

    it('prefers the leaf’s own prose', () => {
        expect(questionTextForScope(scope({ sub_question_id: 'א.1' }), questions))
            .toBe('part 1 of א');
    });

    it('falls back to the NEAREST ancestor, not to the whole question', () => {
        expect(questionTextForScope(scope({ sub_question_id: 'א.2' }), questions))
            .toBe('the א stem');
    });

    it('reaches the whole question only when no ancestor carries prose', () => {
        expect(questionTextForScope(scope({ sub_question_id: 'ב.1' }), questions))
            .toBe('preamble');
    });

    it('returns null when the rubric carries none at any level', () => {
        expect(questionTextForScope(scope({ sub_question_id: 'א.1' }), [])).toBeNull();
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
                draft, overlay, policy: POLICY, questions: [],
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

describe('canHighlight — the quote button cannot land nowhere', () => {
    /**
     * Re-homed from the retired `hasQuoteButton` test (the §4.4a precedent).
     *
     * That predicate answered from `quote_status` alone — the SERVER's verdict,
     * reached under whitespace-collapsing, case-folding, whole-answer
     * normalisation. The renderer could not place every span the server
     * certified, so the button appeared over answers it never marked: 24% of
     * buttons drew nothing. The decision now belongs to the view-model, which
     * is the only place holding BOTH the check and the answer it cites, and it
     * asks the real matcher.
     */
    const withChecks = (answerText: string | null, quotes: (string | null)[]) => {
        const s = scope({
            student_answer: answerText === null
                ? null
                : { text: answerText, source: 'own' },
            criterion_outcomes: [{
                criterion_id: 'q1.א.c0',
                description: 'c',
                points_possible: '4',
                points_awarded: '4',
                checks: quotes.map((quote, i) => ({
                    check_id: `k${i}`, text: 't', kind: 'required',
                    points: '1', partial_fraction: '0.5', verdict: 'met',
                    quote, quote_status: quote ? 'exact' : null, tariff: null,
                })),
            }],
        });
        return build(draftOf([s])).scopes[0].criteria[0].checks;
    };

    const ANSWER = 'public class Hobby\n{\nprivate string hobbyName ;\n}';

    it('is TRUE for a multi-line quote — the case the old predicate got right for the wrong reason', () => {
        const [check] = withChecks(ANSWER, ['public class Hobby\n{\nprivate string hobbyName ;']);
        expect(check.canHighlight).toBe(true);
    });

    it('is TRUE for a single-line quote', () => {
        const [check] = withChecks(ANSWER, ['private string hobbyName ;']);
        expect(check.canHighlight).toBe(true);
    });

    it('is FALSE when there is no quote at all', () => {
        const [check] = withChecks(ANSWER, [null]);
        expect(check.canHighlight).toBe(false);
    });

    it('is FALSE when the quote is not in the answer — no button over an empty promise', () => {
        const [check] = withChecks(ANSWER, ['int somethingElseEntirely = 42 ;']);
        expect(check.canHighlight).toBe(false);
    });

    it('is FALSE when the scope carries no answer to mark', () => {
        const [check] = withChecks(null, ['private string hobbyName ;']);
        expect(check.canHighlight).toBe(false);
    });
});
