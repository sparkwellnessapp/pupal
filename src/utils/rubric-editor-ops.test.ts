import { describe, it, expect } from 'vitest';
import { setExampleSolution, setSubQuestionExampleSolutionAtPath } from './rubric-editor-ops';
import type { RubricQuestion, RubricSubQuestion } from '@/types/rubric';

const sq = (id: string, children: RubricSubQuestion[] = []): RubricSubQuestion => ({
    sub_question_id: id, index: 0, text: '', points: 0, criteria: [], sub_questions: children, example_solution: null,
});

const fixture = (): RubricQuestion[] => [{
    question_id: 'q1', total_points: 0, criteria: [], allow_multiple_valid_forms: false, example_solution: 'old',
    sub_questions: [sq('א', [sq('1'), sq('2')]), sq('ב')],
}];

describe('example-solution ops', () => {
    it('sets a question-level solution verbatim, and null removes it', () => {
        const qs = fixture();
        expect(setExampleSolution(qs, 0, '  x = 1\n')[0].example_solution).toBe('  x = 1\n');
        expect(setExampleSolution(qs, 0, null)[0].example_solution).toBeNull();
    });

    it('sets a solution at depth 2 without touching its siblings or ancestors', () => {
        const qs = fixture();
        const next = setSubQuestionExampleSolutionAtPath(qs, 0, [0, 1], 'פתרון');
        const parent = next[0].sub_questions[0];
        expect(parent.sub_questions![1].example_solution).toBe('פתרון');
        expect(parent.sub_questions![0].example_solution).toBeNull();
        expect(parent.example_solution).toBeNull();
        expect(next[0].example_solution).toBe('old');
    });

    it('is immutable and structurally shares untouched branches (the undo stack relies on it)', () => {
        const qs = fixture();
        const before = JSON.stringify(qs);
        const next = setSubQuestionExampleSolutionAtPath(qs, 0, [0, 1], 'פתרון');
        expect(JSON.stringify(qs)).toBe(before);
        expect(next[0].sub_questions[1]).toBe(qs[0].sub_questions[1]);
        expect(next[0].sub_questions[0].sub_questions![0]).toBe(qs[0].sub_questions[0].sub_questions![0]);
    });
});
