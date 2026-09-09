import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { hydrateAnyQuestions } from '@/utils/rubric-transform';
import type { RubricQuestion } from '@/types/rubric';
import { applyEditSteps, canApplySteps, type FixStep } from './edit-steps';

/**
 * PR-6b — THE EDIT-STEPS INTERPRETER, proved on the real hobby fixture: the
 * canonical D5 fix (create סעיף ג, carve its text out of ב, move the mislabeled
 * criterion, set its points) settles ALL THREE of q2's findings in one click.
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BENCH = path.resolve(HERE, '../../../backend/tests/rubric_eval_suite/benchmarks');
const hobby = (): RubricQuestion[] =>
    hydrateAnyQuestions(JSON.parse(readFileSync(path.join(BENCH, 'hobby_tvshow.json'), 'utf-8')).questions);

const carve = () => {
    const sqb = hobby().find((q) => q.question_id === 'q2')!.sub_questions
        .find((s) => s.sub_question_id === 'ב')!;
    return sqb.text!.slice(sqb.text!.indexOf('ג. כתבו'));
};

const hobbyPlan = (): FixStep[] => [
    { op: 'move_text', scope: 'q2.ב', to_scope: 'q2.ג', text: carve() },
    { op: 'move_criterion', scope: 'q2.ב', criterion_index: 6, to_scope: 'q2.ג' },
    { op: 'set_points', scope: 'q2.ג', value: '16' },
];

describe('the hobby D5 full fix — one plan settles every shadow', () => {
    it('creates ג with the carved text, the moved criterion, and its points', () => {
        const out = applyEditSteps(hobby(), hobbyPlan())!;
        expect(out).not.toBeNull();
        const q2 = out.questions.find((q) => q.question_id === 'q2')!;
        const gimel = q2.sub_questions.find((s) => s.sub_question_id === 'ג')!;

        expect(gimel).toBeTruthy();                          // auto-vivified
        expect(gimel.text).toContain('PrintLowRatingChannel');
        expect(gimel.points).toBe(16);
        expect(gimel.criteria).toHaveLength(1);
        expect(gimel.criteria[0].description).toContain('PrintLowRatingChannel');
    });

    it('the machine did the subtraction — ב keeps everything except what moved', () => {
        const out = applyEditSteps(hobby(), hobbyPlan())!;
        const q2 = out.questions.find((q) => q.question_id === 'q2')!;
        const bet = q2.sub_questions.find((s) => s.sub_question_id === 'ב')!;

        expect(bet.text).toContain('LowestRateChannel');     // her prose, untouched
        expect(bet.text).not.toContain('PrintLowRatingChannel');
        expect(bet.criteria).toHaveLength(6);
        expect(bet.criteria.map((c) => c.index)).toEqual([0, 1, 2, 3, 4, 5]);   // reindexed
    });

    it('ALL the arithmetic settles at once — the point of root-cause fixing', () => {
        const out = applyEditSteps(hobby(), hobbyPlan())!;
        const q2 = out.questions.find((q) => q.question_id === 'q2')!;
        const sum = (cs: { points: number }[]) => cs.reduce((a, c) => a + c.points, 0);

        const bet = q2.sub_questions.find((s) => s.sub_question_id === 'ב')!;
        expect(sum(bet.criteria)).toBe(29);                  // == ב's declared 29
        expect(sum(q2.sub_questions.map((s) => ({ points: s.points })))).toBe(60);   // == q2's declared 60
    });

    it('never mutates its input — E-1 structural sharing stays safe', () => {
        const qs = hobby();
        const snapshot = JSON.stringify(qs);
        applyEditSteps(qs, hobbyPlan());
        expect(JSON.stringify(qs)).toBe(snapshot);
    });
});

describe('deterministic bookkeeping — the model may forget set_points, the math may not', () => {
    it('a moves-only plan (the shape observed live) still settles every sum', () => {
        // The real gpt-5.5 emitted exactly this: the two moves, no set_points,
        // and move_criterion BEFORE move_text (vivification must serve both).
        const plan: FixStep[] = [
            { op: 'move_criterion', scope: 'q2.ב', criterion_index: 6, to_scope: 'q2.ג' },
            { op: 'move_text', scope: 'q2.ב', to_scope: 'q2.ג', text: carve() },
        ];
        const out = applyEditSteps(hobby(), plan)!;
        const q2 = out.questions.find((q) => q.question_id === 'q2')!;
        const gimel = q2.sub_questions.find((s) => s.sub_question_id === 'ג')!;
        expect(gimel.points).toBe(16);                       // Σ of what arrived — HER number
        expect(q2.sub_questions.reduce((a, s) => a + s.points, 0)).toBe(60);
    });

    it('an explicit set_points on the vivified node still wins', () => {
        const plan: FixStep[] = [
            { op: 'move_criterion', scope: 'q2.ב', criterion_index: 6, to_scope: 'q2.ג' },
            { op: 'set_points', scope: 'q2.ג', value: '15' },
        ];
        const out = applyEditSteps(hobby(), plan)!;
        const gimel = out.questions.find((q) => q.question_id === 'q2')!
            .sub_questions.find((s) => s.sub_question_id === 'ג')!;
        expect(gimel.points).toBe(15);
    });
});

describe('atomicity — a plan that cannot complete changes NOTHING', () => {
    it('a later invalid step voids the whole plan', () => {
        const plan = [...hobbyPlan(), { op: 'move_criterion', scope: 'q2.ב', criterion_index: 99, to_scope: 'q2.ג' } as FixStep];
        expect(applyEditSteps(hobby(), plan)).toBeNull();
        expect(canApplySteps(hobby(), plan)).toBe(false);
    });

    it('a move_text quote that is not verbatim voids the plan', () => {
        const plan: FixStep[] = [{ op: 'move_text', scope: 'q2.ב', to_scope: 'q2.ג', text: 'ג. כתבו פעולה שאינה שם' }];
        expect(applyEditSteps(hobby(), plan)).toBeNull();
    });

    it('an unresolvable source scope voids the plan', () => {
        expect(applyEditSteps(hobby(), [{ op: 'set_points', scope: 'q9.א', value: '5' }])).toBeNull();
    });

    it('vivification creates ONLY the last segment — a missing parent is a void plan', () => {
        const plan: FixStep[] = [{ op: 'move_criterion', scope: 'q2.ב', criterion_index: 0, to_scope: 'q9.ג' }];
        expect(applyEditSteps(hobby(), plan)).toBeNull();
    });
});

describe('the rubric-level declared total', () => {
    it('a single rubric set_points reports declaredTotal and leaves the tree alone', () => {
        const qs = hobby();
        const out = applyEditSteps(qs, [{ op: 'set_points', scope: 'rubric', value: '97', current_value: '100' }])!;
        expect(out.declaredTotal).toBe(97);
        expect(out.questions).toBe(qs);                      // untouched, same reference
    });

    it('a rubric step may not ride in a multi-step plan (one click = one undo)', () => {
        const plan: FixStep[] = [
            { op: 'set_points', scope: 'rubric', value: '97' },
            { op: 'set_points', scope: 'q2', value: '60' },
        ];
        expect(applyEditSteps(hobby(), plan)).toBeNull();
    });
});

describe('criterion-level set_points cascades like her own edit (living sums)', () => {
    it('editing a criterion recascades its parent sub-question', () => {
        const out = applyEditSteps(hobby(), [
            { op: 'set_points', scope: 'q2.ב', criterion_index: 6, value: '0', current_value: '16' },
        ])!;
        const bet = out.questions.find((q) => q.question_id === 'q2')!
            .sub_questions.find((s) => s.sub_question_id === 'ב')!;
        expect(bet.criteria[6].points).toBe(0);
        expect(bet.points).toBe(29);                         // Σ criteria after the edit — E-3 cascade
    });
});

/**
 * CROSS-PINNED POINTS SEMANTICS — the eval scorer's twin.
 *
 * backend/tests/fixtures/edit_step_points_cases.json is read IN PLACE by BOTH this
 * file and backend/tests/rubric_eval_suite/test_fix_effect.py. The Python side
 * SIMULATES these steps to decide whether a model's proposed fix actually leaves
 * the rubric adding up (the gate criterion added 2026-08-24, after a fix that
 * created ג correctly but left ב declaring 45 against 29 of criteria reached
 * production). This file proves the REAL applier lands on the same numbers.
 *
 * If these two ever disagree, the eval gate silently starts passing broken fixes
 * or failing good ones — with nothing to say which. So: change edit-steps.ts's
 * point semantics on purpose, and update the vectors in the SAME commit.
 * (selection_expectation_cases.json is the precedent for this arrangement.)
 */
const POINTS_VECTORS = path.resolve(
    HERE, '../../../backend/tests/fixtures/edit_step_points_cases.json');

type PointsCase = {
    name: string;
    questions: Array<{
        question_id: string; total_points: string;
        sub_questions: Array<{ sub_question_id: string; points: string; criteria: string[] }>;
    }>;
    steps: FixStep[];
    expected_points: Record<string, string>;
};

const expand = (c: PointsCase): RubricQuestion[] => c.questions.map((q, qi) => ({
    question_id: q.question_id,
    total_points: Number(q.total_points),
    criteria: [],
    sub_questions: q.sub_questions.map((s, si) => ({
        sub_question_id: s.sub_question_id,
        index: si,
        text: '',
        points: Number(s.points),
        criteria: s.criteria.map((p, ci) => ({
            criterion_id: `${q.question_id}.${s.sub_question_id}.c${ci}`,
            index: ci,
            description: `c${ci}`,
            points: Number(p),
        })),
        sub_questions: [],
    })),
    index: qi,
} as unknown as RubricQuestion));

const declaredAt = (questions: RubricQuestion[], scope: string): number | undefined => {
    const [qid, ...subs] = scope.split('.');
    const q = questions.find((x) => x.question_id.replace(/^q/i, '') === qid.replace(/^q/i, ''));
    if (!q) return undefined;
    let node: RubricSubQuestionLike = {
        sub_question_id: q.question_id,
        points: q.total_points,
        sub_questions: q.sub_questions as unknown as RubricSubQuestionLike[],
    };
    for (const seg of subs) {
        const next: RubricSubQuestionLike | undefined =
            node.sub_questions?.find((s) => s.sub_question_id === seg);
        if (!next) return undefined;
        node = next;
    }
    return node.points;
};

type RubricSubQuestionLike = {
    sub_question_id: string; points: number; sub_questions?: RubricSubQuestionLike[];
};

describe('edit-step POINTS semantics — cross-pinned with the eval scorer', () => {
    const cases: PointsCase[] = JSON.parse(readFileSync(POINTS_VECTORS, 'utf-8')).cases;

    it('the vector file is present and non-empty (a silent drop would disable the cross-pin)', () => {
        expect(cases.length).toBeGreaterThan(0);
    });

    cases.forEach((c) => {
        it(`applier matches the vector: ${c.name}`, () => {
            const out = applyEditSteps(expand(c), c.steps);
            expect(out).not.toBeNull();
            for (const [scope, expected] of Object.entries(c.expected_points)) {
                expect(
                    declaredAt(out!.questions, scope),
                    `${scope}: the REAL applier disagrees with backend/tests/fixtures/` +
                    `edit_step_points_cases.json. If edit-steps.ts changed on purpose, ` +
                    `update the vectors in the same commit — the eval gate reads them.`,
                ).toBe(Number(expected));
            }
        });
    });
});

/**
 * ID RE-DERIVATION ON MOVE (2026-08-24, owner-ruled "B — ids reflect current location").
 *
 * Extraction names criteria by where they live (`q2.ב.c6`, sub-criteria `<cid>.scN`),
 * so a criterion that moves to ג while keeping `q2.ב.c6` is an id that lies about its
 * location — in JSON the teacher and every future reader will see. The applier already
 * renumbered `index` on both sides of a move; these pin that the id agrees.
 */
describe('a moved criterion is renamed to its new home', () => {
    it('the moved criterion takes an id derived from its DESTINATION', () => {
        const out = applyEditSteps(hobby(), [
            { op: 'move_criterion', scope: 'q2.ב', criterion_index: 6, to_scope: 'q2.ג' },
        ])!;
        const q2 = out.questions.find((q) => q.question_id === 'q2')!;
        const gimel = q2.sub_questions.find((s) => s.sub_question_id === 'ג')!;

        expect(gimel.criteria).toHaveLength(1);
        expect(gimel.criteria[0].criterion_id).toBe('q2.ג.c0');
        expect(gimel.criteria[0].criterion_id).not.toContain('ב');   // the lie is gone
        expect(gimel.criteria[0].description).toContain('PrintLowRatingChannel');
    });

    it('its sub-criteria follow the new parent id', () => {
        const withSubs = (): RubricQuestion[] => {
            const qs = hobby();
            const bet = qs.find((q) => q.question_id === 'q2')!
                .sub_questions.find((s) => s.sub_question_id === 'ב')!;
            bet.criteria[6] = {
                ...bet.criteria[6],
                sub_criteria: [
                    { sub_criterion_id: 'q2.ב.c6.sc0', index: 0, description: 'a', points: 8 },
                    { sub_criterion_id: 'q2.ב.c6.sc1', index: 1, description: 'b', points: 8 },
                ],
            };
            return qs;
        };
        const out = applyEditSteps(withSubs(), [
            { op: 'move_criterion', scope: 'q2.ב', criterion_index: 6, to_scope: 'q2.ג' },
        ])!;
        const moved = out.questions.find((q) => q.question_id === 'q2')!
            .sub_questions.find((s) => s.sub_question_id === 'ג')!.criteria[0];

        expect(moved.criterion_id).toBe('q2.ג.c0');
        expect(moved.sub_criteria!.map((sc) => sc.sub_criterion_id))
            .toEqual(['q2.ג.c0.sc0', 'q2.ג.c0.sc1']);
    });

    it('siblings left behind keep their ids — digits are birth order, not position', () => {
        const out = applyEditSteps(hobby(), [
            { op: 'move_criterion', scope: 'q2.ב', criterion_index: 0, to_scope: 'q2.ג' },
        ])!;
        const bet = out.questions.find((q) => q.question_id === 'q2')!
            .sub_questions.find((s) => s.sub_question_id === 'ב')!;
        // index IS renumbered (pre-existing behaviour) …
        expect(bet.criteria.map((c) => c.index)).toEqual([0, 1, 2, 3, 4, 5]);
        // … while the ids of untouched siblings are deliberately NOT churned: they key
        // grading terminals, teacher overrides (CW-3) and data-scope-id anchors.
        expect(bet.criteria[0].criterion_id).toBe('q2.ב.c1');
        expect(bet.criteria.every((c) => c.criterion_id.startsWith('q2.ב.'))).toBe(true);
    });

    it('an id already taken in the destination falls back to an opaque one', () => {
        const clash = (): RubricQuestion[] => {
            const qs = hobby();
            const q2 = qs.find((q) => q.question_id === 'q2')!;
            q2.sub_questions.push({
                sub_question_id: 'ג', index: 2, text: '', points: 0,
                // the squatter holds the id the move WILL want (append lands at index 1),
                // which is how a collision actually arises: an id whose digits record
                // birth order, not position, after an earlier move + removal.
                criteria: [{ criterion_id: 'q2.ג.c1', index: 0, description: 'squatter', points: 1 }],
                sub_questions: [],
            } as unknown as RubricQuestion['sub_questions'][number]);
            return qs;
        };
        const out = applyEditSteps(clash(), [
            { op: 'move_criterion', scope: 'q2.ב', criterion_index: 6, to_scope: 'q2.ג' },
        ])!;
        const gimel = out.questions.find((q) => q.question_id === 'q2')!
            .sub_questions.find((s) => s.sub_question_id === 'ג')!;
        const movedIn = gimel.criteria[1];
        expect(movedIn.criterion_id).not.toBe('q2.ג.c1');       // no collision with the squatter
        expect(movedIn.criterion_id).toMatch(/^c_/);            // the editor's own opaque shape
        expect(new Set(gimel.criteria.map((c) => c.criterion_id)).size).toBe(2);
    });
});
