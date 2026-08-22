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
