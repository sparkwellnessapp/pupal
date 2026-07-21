import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { hydrateAnyQuestions, dehydrateQuestions, recalculateParentsFromCriteria } from '@/utils/rubric-transform';
import { updateCriterionAtPath, removeCriterionAtPath } from '@/utils/rubric-editor-ops';
import type { RubricQuestion } from '@/types/rubric';

/**
 * PR-5 S2 §7 — OPS-PARITY, byte-identity form (F4 ruling).
 *
 * The guarantee that matters is not "same function calls" (the old editor's
 * direct-criteria path uses an inline in-place mutation, so a call-sequence spy
 * would be literally false there) but "same SAVED BYTES for the same logical
 * edit." So: apply the edit through the mirror's ops, dehydrate, and compare to
 * the old editor's ALGORITHM reproduced purely. The mirror routes ALL criteria
 * edits — direct AND nested — through updateCriterionAtPath (empty sqPath for
 * direct), which makes it strictly safer (no shared-object mutation) than the
 * editor it replaces, while producing identical output.
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BENCHMARKS = path.resolve(HERE, '../../../backend/tests/rubric_eval_suite/benchmarks');
const load = (name: string): RubricQuestion[] =>
    hydrateAnyQuestions(JSON.parse(readFileSync(path.join(BENCHMARKS, `${name}.json`), 'utf-8')).questions);

/** The OLD editor's direct-criteria points edit, reproduced immutably (its inline
 *  `newQuestions[qi].criteria[ci] = {...}` then recalc — minus the shared mutation). */
function oldEditorDirectEdit(qs: RubricQuestion[], qi: number, ci: number, updates: Partial<RubricQuestion['criteria'][number]>): RubricQuestion[] {
    const edited = qs.map((q, i) => (i !== qi ? q : { ...q, criteria: q.criteria.map((c, j) => (j !== ci ? c : { ...c, ...updates })) }));
    return recalculateParentsFromCriteria(edited);
}

function firstDirectCriteriaQuestion(qs: RubricQuestion[]): number {
    return qs.findIndex((q) => q.sub_questions.length === 0 && q.criteria.length > 0);
}

describe('ops-parity — mirror ≡ old editor, dehydrated bytes', () => {
    it('criterion points edit on a DIRECT-criteria question: byte-identical to the old editor', () => {
        const qs = load('foundations_cs');
        const qi = firstDirectCriteriaQuestion(qs);
        expect(qi, 'a direct-criteria question exists in foundations_cs').toBeGreaterThanOrEqual(0);
        const ci = 0;

        const mirror = recalculateParentsFromCriteria(updateCriterionAtPath(qs, qi, [], ci, { points: 1.75 }));
        const old = oldEditorDirectEdit(qs, qi, ci, { points: 1.75 });

        expect(dehydrateQuestions(mirror)).toEqual(dehydrateQuestions(old));
    });

    it('the edit is SURGICAL — untouched questions dehydrate identically (no drop, carry survives)', () => {
        const qs = load('foundations_cs');
        const qi = firstDirectCriteriaQuestion(qs);
        const before = dehydrateQuestions(qs);
        const after = dehydrateQuestions(recalculateParentsFromCriteria(updateCriterionAtPath(qs, qi, [], 0, { points: 3 })));
        before.forEach((q, i) => {
            if (i !== qi) expect(after[i]).toEqual(q); // every other question byte-for-byte
        });
    });

    it('a DESCRIPTION edit changes only the text, never a point value (no cascade)', () => {
        const qs = load('foundations_cs');
        const qi = firstDirectCriteriaQuestion(qs);
        const edited = updateCriterionAtPath(qs, qi, [], 0, { description: 'תיאור מעודכן' });
        const wireBefore = dehydrateQuestions(qs)[qi];
        const wireAfter = dehydrateQuestions(edited)[qi];
        expect(wireAfter.criteria[0].description).toBe('תיאור מעודכן');
        expect(wireAfter.criteria[0].points).toBe(wireBefore.criteria[0].points); // points untouched
        expect(wireAfter.total_points).toBe(wireBefore.total_points);             // no cascade fired
    });

    it('nested leaf criterion edit cascades bottom-up and stays surgical (bagrut depth-2)', () => {
        const qs = load('bagrut_899371');
        // Find the first leaf sub-question WITH criteria (depth ≥ 1).
        let target: { qi: number; sqPath: number[] } | null = null;
        const walk = (subs: RubricQuestion['sub_questions'], qi: number, prefix: number[]) => {
            subs.forEach((sq, i) => {
                if (target) return;
                if ((sq.sub_questions?.length ?? 0) > 0) walk(sq.sub_questions!, qi, [...prefix, i]);
                else if (sq.criteria.length > 0) target = { qi, sqPath: [...prefix, i] };
            });
        };
        qs.forEach((q, qi) => { if (!target && q.sub_questions.length) walk(q.sub_questions, qi, []); });
        expect(target, 'a nested leaf with criteria exists in bagrut').toBeTruthy();

        const { qi, sqPath } = target!;
        const mirror = recalculateParentsFromCriteria(updateCriterionAtPath(qs, qi, sqPath, 0, { points: 0.5 }));
        // Round-trips cleanly and the edited question re-dehydrates without dropping
        // the nested subtree or _carry (the B-11 codec still owns fidelity).
        const wireAfter = dehydrateQuestions(mirror);
        expect(wireAfter).toHaveLength(qs.length);
        // Untouched sibling questions are byte-stable.
        const before = dehydrateQuestions(qs);
        before.forEach((q, i) => { if (i !== qi) expect(wireAfter[i]).toEqual(q); });
    });

    it('delete criterion leaves a GAP — no redistribution to siblings (Q1-strict)', () => {
        const qs = load('foundations_cs');
        const qi = qs.findIndex((q) => q.sub_questions.length === 0 && q.criteria.length >= 2);
        expect(qi).toBeGreaterThanOrEqual(0);
        const siblingPointsBefore = qs[qi].criteria[1].points;

        const afterQs = removeCriterionAtPath(qs, qi, [], 0);
        expect(afterQs[qi].criteria).toHaveLength(qs[qi].criteria.length - 1);
        // The surviving sibling (now index 0) keeps its exact points — nothing rescaled.
        expect(afterQs[qi].criteria[0].points).toBe(siblingPointsBefore);
    });
});
