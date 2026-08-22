import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { hydrateAnyQuestions, dehydrateQuestions } from '@/utils/rubric-transform';
import {
    changeQuestionPoints, changeSubQuestionPointsAtPath,
    setQuestionText, setSubQuestionTextAtPath,
} from '@/utils/rubric-editor-ops';
import { validateAllQuestions } from '@/utils/rubric-validation';
import type { RubricQuestion } from '@/types/rubric';

/**
 * Design Recovery Round 2 — D5 (points editable at EVERY point-bearing node) and
 * D8 (prose editable, display-rich / edit-raw). Both are tested at the OPS layer,
 * purely: the mirror's correctness invariant is "ops imported, never forked", so
 * proving the op is the thing that proves the surface.
 *
 * The undo stack pushes snapshots BY REFERENCE and relies on structural sharing,
 * so "does not mutate its input" is not a style check here — it is what keeps
 * earlier undo snapshots from being retroactively corrupted.
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BENCHMARKS = path.resolve(HERE, '../../../backend/tests/rubric_eval_suite/benchmarks');
const load = (name: string): RubricQuestion[] =>
    hydrateAnyQuestions(JSON.parse(readFileSync(path.join(BENCHMARKS, `${name}.json`), 'utf-8')).questions);

const issuesAt = (qs: RubricQuestion[], targetId: string) =>
    Array.from(validateAllQuestions(qs).values()).flat().filter((i) => i.target_id === targetId);

describe('D5 — a parent points edit sets DECLARED, and nothing else', () => {
    it('sub-question edit: the node moves, its CHILDREN are untouched (no redistribution)', () => {
        const qs = load('bagrut_899371');           // q1 → א(15) → 1(12), 2(3)
        const before = qs[0].sub_questions[0];
        const childrenBefore = JSON.stringify(before.sub_questions);

        const next = changeSubQuestionPointsAtPath(qs, 0, [0], 21);
        const after = next[0].sub_questions[0];

        expect(after.points).toBe(21);
        expect(JSON.stringify(after.sub_questions)).toBe(childrenBefore); // NOT rescaled
    });

    it('the resulting sum gap SURFACES as a live finding (never silently reconciled)', () => {
        const qs = load('bagrut_899371');
        expect(issuesAt(qs, 'q1')).toHaveLength(0);          // clean before

        const next = changeSubQuestionPointsAtPath(qs, 0, [0], 21); // 21 + 10 ≠ 25
        const found = issuesAt(next, 'q1');
        expect(found).toHaveLength(1);
        expect(found[0].invariant).toBe('INV-R1');
    });

    it('an INNER (depth-2) sub-question is editable at its own path', () => {
        const qs = load('bagrut_899371');
        const next = changeSubQuestionPointsAtPath(qs, 0, [0, 1], 7); // q1.א.2
        expect(next[0].sub_questions[0].sub_questions![1].points).toBe(7);
        expect(next[0].sub_questions[0].sub_questions![0].points)
            .toBe(qs[0].sub_questions[0].sub_questions![0].points); // sibling untouched
    });

    it('a question total edit does not rescale its sub-questions', () => {
        const qs = load('bagrut_899371');
        const subsBefore = JSON.stringify(qs[0].sub_questions);
        const next = changeQuestionPoints(qs, 0, 40);
        expect(next[0].total_points).toBe(40);
        expect(JSON.stringify(next[0].sub_questions)).toBe(subsBefore);
    });

    it('NEVER mutates its input (the undo stack shares structure by reference)', () => {
        const qs = load('bagrut_899371');
        const snapshot = JSON.stringify(qs);
        changeSubQuestionPointsAtPath(qs, 0, [0], 21);
        changeQuestionPoints(qs, 0, 40);
        expect(JSON.stringify(qs)).toBe(snapshot);
    });

    it('untouched questions dehydrate identically (the edit is surgical)', () => {
        const qs = load('bagrut_899371');
        const next = changeSubQuestionPointsAtPath(qs, 0, [0], 21);
        expect(JSON.stringify(dehydrateQuestions(next).slice(1)))
            .toBe(JSON.stringify(dehydrateQuestions(qs).slice(1)));
    });
});

describe('D8 — prose commits RAW and round-trips VERBATIM', () => {
    // She edits the SOURCE (markers and all), so what dehydrate emits must be
    // byte-identical to what she typed — no trim, no normalization, no re-render.
    const MARKER_TEXT = [
        'לפניכם הפעולה Check בשפת #C:',
        'public static bool Check(int[] arr)',
        '[TABLE 3: 6x5]',
        '| ערך מוחזר | cond | arr[i] | i | x |',
        '|---|---|---|---|---|',
        '|  |  |  |  |  |',
        '  trailing spaces and a blank line follow  ',
        '',
    ].join('\n');

    it('question text: what she typed is what dehydrate emits', () => {
        const qs = load('bagrut_899371');
        const next = setQuestionText(qs, 0, MARKER_TEXT);
        expect(next[0].question_text).toBe(MARKER_TEXT);
        expect(dehydrateQuestions(next)[0].question_text).toBe(MARKER_TEXT);
    });

    it('sub-question text at a nested path: verbatim, markers intact', () => {
        const qs = load('bagrut_899371');
        const next = setSubQuestionTextAtPath(qs, 0, [0, 0], MARKER_TEXT);
        const sq = dehydrateQuestions(next)[0].sub_questions![0].sub_questions![0];
        expect(sq.text).toBe(MARKER_TEXT);
        expect(sq.text).toContain('[TABLE 3: 6x5]');   // the marker SURVIVES the edit
    });

    it('a text edit moves no point value anywhere', () => {
        const qs = load('bagrut_899371');
        const pointsOf = (x: RubricQuestion[]) => JSON.stringify(x.map((q) => [q.total_points, q.sub_questions.map((s) => s.points)]));
        const next = setQuestionText(qs, 0, 'טקסט חדש לגמרי');
        expect(pointsOf(next)).toBe(pointsOf(qs));
    });

    it('NEVER mutates its input', () => {
        const qs = load('bagrut_899371');
        const snapshot = JSON.stringify(qs);
        setQuestionText(qs, 0, 'x');
        setSubQuestionTextAtPath(qs, 0, [0], 'y');
        expect(JSON.stringify(qs)).toBe(snapshot);
    });

    it('an empty commit is stored as empty — absence is not invented content', () => {
        const qs = load('bagrut_899371');
        expect(setQuestionText(qs, 0, '')[0].question_text).toBe('');
    });
});
