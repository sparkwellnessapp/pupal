import { describe, it, expect } from 'vitest';

import { extractQuestions } from './GradeReviewContext';
import { questionTextForScope } from '@/utils/grade-review-model';

/**
 * Flattening the rubric contract into the entries the review surface looks up.
 *
 * THE DEFECT THIS PINS. `extractQuestions` walked exactly ONE level and emitted
 * BARE sub-question ids ("א"), while scope outcomes are keyed by the FULL PATH
 * within the question ("א.1" — `gradable_compiler`'s scope id). So on a rubric
 * nested two deep it produced no entry for the graded scope at all: the lookup
 * could not find what was never emitted, and the «השאלה» disclosure rendered
 * the whole-question stem — or, when the parent carried no prose of its own,
 * nothing whatsoever.
 *
 * It failed hardest where it mattered most: nested bagrut-style rubrics are
 * exactly the ones whose parts diverge, and the teacher hit it at the moment
 * she was judging whether a grade was right.
 */

/**
 * The real shape from the reported document (מתכונת 1 — שאלון 899371), reduced
 * to what this function reads. Note the two silences that made the failure
 * total rather than merely coarse: `question_text` is EMPTY on q1, and `text`
 * is NULL on the «א» stem — the prose lives only on the leaves.
 */
const REPORTED_RUBRIC = {
    contract_json: {
        questions: [{
            question_id: 'q1',
            question_text: '',
            sub_questions: [
                {
                    sub_question_id: 'א',
                    text: null,
                    sub_questions: [
                        { sub_question_id: '1', text: 'לפניכם הפעולה Check…', sub_questions: [] },
                        { sub_question_id: '2', text: 'רשמו בקצרה מה מטרת הפעולה Check.', sub_questions: [] },
                    ],
                },
                {
                    sub_question_id: 'ב',
                    text: 'ב. לפניכם הפעולה What…',
                    sub_questions: [
                        { sub_question_id: '1', text: 'כתבו מהו הערך המוחזר.', sub_questions: [] },
                    ],
                },
            ],
        }],
    },
};

const scope = (subQuestionId: string | null) => ({
    question_id: 'q1',
    sub_question_id: subQuestionId,
    points_possible: '12',
    points_awarded: '12',
    graded_by: 'llm',
});

describe('extractQuestions', () => {
    it('emits FULL-PATH ids for nested sub-questions', () => {
        const out = extractQuestions(REPORTED_RUBRIC);
        const paths = out.map((q) => q.sub_question_id);
        expect(paths).toContain('א.1');
        expect(paths).toContain('א.2');
        expect(paths).toContain('ב.1');
        // …and the depth-1 stem that DOES carry prose keeps its own entry.
        expect(paths).toContain('ב');
    });

    it('recurses THROUGH a parent that carries no prose of its own', () => {
        // «א» has text: null — the whole reason its children went missing. A
        // silent parent must not take its subtree down with it.
        const out = extractQuestions(REPORTED_RUBRIC);
        expect(out.map((q) => q.sub_question_id)).not.toContain('א');
        expect(out.find((q) => q.sub_question_id === 'א.1')?.text)
            .toBe('לפניכם הפעולה Check…');
    });

    it('omits an empty question_text rather than emitting a blank entry', () => {
        // q1.question_text is '' — an entry for it would make every descendant
        // "find" an empty string and stop walking, which is worse than nothing.
        const out = extractQuestions(REPORTED_RUBRIC);
        expect(out.map((q) => q.sub_question_id)).not.toContain(null);
    });

    /**
     * END TO END on the reported document: the scope the teacher was looking at.
     * Before this fix the lookup returned null and she reviewed a 12/12 grade
     * with no question on screen.
     */
    it('gives שאלה 1.א.1 its own prose', () => {
        const questions = extractQuestions(REPORTED_RUBRIC);
        expect(questionTextForScope(scope('א.1'), questions))
            .toBe('לפניכם הפעולה Check…');
    });

    it('gives a nested leaf its NEAREST ancestor when it has no prose', () => {
        const questions = extractQuestions(REPORTED_RUBRIC);
        // «ב.2» does not exist in the rubric; the nearest prose is «ב»'s stem,
        // NOT the (empty, therefore absent) whole-question preamble.
        expect(questionTextForScope(scope('ב.2'), questions))
            .toBe('ב. לפניכם הפעולה What…');
    });

    it('tolerates a rubric with no sub-questions at all', () => {
        const flat = { contract_json: { questions: [
            { question_id: 'q1', question_text: 'שאלה שלמה', sub_questions: [] },
        ] } };
        expect(extractQuestions(flat)).toEqual([
            { question_id: 'q1', sub_question_id: null, text: 'שאלה שלמה' },
        ]);
    });

    it('returns nothing for a shape it does not recognise, rather than throwing', () => {
        expect(extractQuestions(null)).toEqual([]);
        expect(extractQuestions({})).toEqual([]);
        expect(extractQuestions({ contract_json: { questions: [{ }] } })).toEqual([]);
    });
});
