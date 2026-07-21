import { describe, it, expect } from 'vitest';
import { scopeLabel, isGeneratedId } from './scope-label';
import type { RubricQuestion, RubricSubQuestion, RubricCriterion } from '@/types/rubric';

function crit(id: string): RubricCriterion {
    return { criterion_id: id, index: 0, description: '', points: 0 };
}
function leaf(id: string, criteria: RubricCriterion[] = []): RubricSubQuestion {
    return { sub_question_id: id, index: 0, points: 0, criteria };
}
function parent(id: string, children: RubricSubQuestion[]): RubricSubQuestion {
    return { sub_question_id: id, index: 0, points: 0, criteria: [], sub_questions: children };
}
function q(id: string, opts: Partial<RubricQuestion> = {}): RubricQuestion {
    return { question_id: id, total_points: 0, criteria: [], sub_questions: [], ...opts };
}

// A depth-2 selection-bagrut shape: q1 → א(→1,2) / ב, … plus a direct-criteria q6.
const QUESTIONS: RubricQuestion[] = [
    q('q1', { sub_questions: [
        parent('א', [leaf('1', [crit('c_a1_0')]), leaf('2', [crit('c_a2_0'), crit('c_a2_1')])]),
        leaf('ב', [crit('c_b_0')]),
    ] }),
    q('q6', { criteria: [crit('c1'), crit('c2')] }),
];

describe('scopeLabel — the naming law resolver', () => {
    it('null / rubric → "המחוון"', () => {
        expect(scopeLabel(null, QUESTIONS)).toBe('המחוון');
        expect(scopeLabel(undefined, QUESTIONS)).toBe('המחוון');
        expect(scopeLabel('rubric', QUESTIONS)).toBe('המחוון');
    });

    it('question paths use paper identity', () => {
        expect(scopeLabel('q1', QUESTIONS)).toBe('שאלה 1');
        expect(scopeLabel('q6', QUESTIONS)).toBe('שאלה 6'); // 6, not its ordinal position (2)
    });

    it('the full dotted path q1.א.2 → "שאלה 1 · סעיף א · תת-סעיף 2"', () => {
        expect(scopeLabel('q1.א.2', QUESTIONS)).toBe('שאלה 1 · סעיף א · תת-סעיף 2');
        expect(scopeLabel('q1.א', QUESTIONS)).toBe('שאלה 1 · סעיף א');
        expect(scopeLabel('q1.ב', QUESTIONS)).toBe('שאלה 1 · סעיף ב');
    });

    it('a bare criterion id resolves through the tree to its parent', () => {
        expect(scopeLabel('c_a2_1', QUESTIONS)).toBe('שאלה 1 · סעיף א · תת-סעיף 2 · קריטריון 2');
        expect(scopeLabel('c1', QUESTIONS)).toBe('שאלה 6 · קריטריון 1'); // direct criterion under q6
    });

    it('NEVER leaks a technical id for teacher-added nodes — falls back to ordinal position', () => {
        const withAdded: RubricQuestion[] = [
            q('q1', { sub_questions: [leaf('א', [crit('c1')]), leaf('sq_mxyz12ab', [crit('c1721400000000')])] }),
            q('q_abc123'),
        ];
        // generated sub-question id → ordinal "סעיף 2", never "סעיף sq_mxyz12ab"
        expect(scopeLabel('q1.sq_mxyz12ab', withAdded)).toBe('שאלה 1 · סעיף 2');
        // generated question id → ordinal "שאלה 2", never "שאלה 0"/"שאלה q_abc123"
        expect(scopeLabel('q_abc123', withAdded)).toBe('שאלה 2');
        // generated criterion id resolves via its human parent
        expect(scopeLabel('c1721400000000', withAdded)).toBe('שאלה 1 · סעיף 2 · קריטריון 1');
    });

    it('an unresolvable id degrades to "המחוון", never the raw string', () => {
        expect(scopeLabel('q9.zz.99', QUESTIONS)).toBe('המחוון');
        expect(scopeLabel('c_does_not_exist', QUESTIONS)).toBe('המחוון');
    });

    it('isGeneratedId classifies minted vs extraction ids', () => {
        expect(isGeneratedId('q_ab12')).toBe(true);
        expect(isGeneratedId('sq_ab12')).toBe(true);
        expect(isGeneratedId('c_ab12')).toBe(true);
        expect(isGeneratedId('c1721400000000')).toBe(true); // c<timestamp>
        expect(isGeneratedId('q1')).toBe(false);
        expect(isGeneratedId('א')).toBe(false);
        expect(isGeneratedId('c1')).toBe(false);
    });
});
