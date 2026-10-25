/**
 * WHOLE-SCOPE (owner-ruled 2026-10-25): a leaf with NO criteria is graded as one unit
 * at its declared points. "No criteria" never means "the criteria sum to 0" — in the
 * validator, in the living-sums cascade, or in an extraction-time fix proposal.
 */
import { describe, expect, it } from 'vitest';
import type { RubricQuestion } from '@/types/rubric';
import { validateQuestion } from '@/utils/rubric-validation';
import { recalculateParentsFromCriteria } from '@/utils/rubric-transform';
import {
    addCriterionAtPath, addSubCriterionAtPath, removeSubCriterionAtPath, updateCriterionAtPath,
} from '@/utils/rubric-editor-ops';
import { composeFindings } from '@/utils/findings';

function rubric(): RubricQuestion[] {
    return [
        {
            question_id: 'q1', question_type: 'short_answer', question_text: '', total_points: 10,
            criteria: [], allow_multiple_valid_forms: false, example_solution: null,
            sub_questions: [
                { sub_question_id: 'א', index: 0, text: 'a', points: 5,
                  criteria: [{ criterion_id: 'q1.א.c0', index: 0, description: 'x', points: 5, sub_criteria: null }] },
                { sub_question_id: 'ב', index: 1, text: 'b', points: 5, criteria: [] },
            ],
        },
        {
            question_id: 'q2', question_type: 'short_answer', question_text: '', total_points: 20,
            criteria: [], sub_questions: [], allow_multiple_valid_forms: false, example_solution: null,
        },
    ];
}

describe('whole-scope leaves', () => {
    it('the validator is silent on a criteria-less leaf and a criteria-less question', () => {
        const qs = rubric();
        expect(validateQuestion(qs[0], 0, qs)).toEqual([]);
        expect(validateQuestion(qs[1], 1, qs)).toEqual([]);
    });

    it('a criterion edit elsewhere never zeroes a criteria-less leaf or question', () => {
        const qs = recalculateParentsFromCriteria(updateCriterionAtPath(rubric(), 0, [0], 0, { points: 4 }));
        expect(qs[0].sub_questions[0].points).toBe(4);   // the living sum still cascades
        expect(qs[0].sub_questions[1].points).toBe(5);   // …but a whole-scope leaf keeps hers
        expect(qs[1].total_points).toBe(20);
    });

    it('adding a table makes the leaf an ordinary criteria leaf again', () => {
        const qs = addCriterionAtPath(rubric(), 0, [1]);
        const issues = validateQuestion(qs[0], 0, qs);
        expect(issues.map((i) => i.invariant)).toEqual(['INV-R1b']);   // 0 of 5 until she fills it
    });

    it('an extraction-time «set declared to 0» fix is withdrawn for a whole-scope leaf', () => {
        const qs = rubric();
        const [f] = composeFindings([], [], [{
            mistake_id: 'pts:q1.ב', kind: 'point_sum_mismatch', target_id: 'q1.ב',
            explanation: 'e', evidence: { children_sum: '0', declared: '5' },
        } as never], qs);
        expect(f.status).toBe('resolved');
        expect(f.fix).toBeNull();
    });
});

describe('sub-criterion ops', () => {
    it('add appends a 0-point sub-criterion; removing the last returns the criterion to atomic', () => {
        let qs = addSubCriterionAtPath(rubric(), 0, [0], 0);
        qs = addSubCriterionAtPath(qs, 0, [0], 0);
        const subs = qs[0].sub_questions[0].criteria[0].sub_criteria!;
        expect(subs.map((s) => [s.index, s.points])).toEqual([[0, 0], [1, 0]]);
        expect(new Set(subs.map((s) => s.sub_criterion_id)).size).toBe(2);
        expect(rubric()[0].sub_questions[0].criteria[0].sub_criteria).toBeNull();   // pure

        qs = removeSubCriterionAtPath(qs, 0, [0], 0, 0);
        expect(qs[0].sub_questions[0].criteria[0].sub_criteria!.map((s) => s.index)).toEqual([0]);
        qs = removeSubCriterionAtPath(qs, 0, [0], 0, 0);
        expect(qs[0].sub_questions[0].criteria[0].sub_criteria).toBeNull();
    });
});
