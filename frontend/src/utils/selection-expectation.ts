/**
 * Client mirror of the backend's selection-expectation rule.
 *
 * FAITHFUL port of `expected_empty_keys` in
 * `backend/app/services/selection_expectation.py` — keep the two in lockstep.
 * Both sides are pinned by the SAME fixture file
 * (`backend/tests/fixtures/selection_expectation_cases.json`), read in place
 * by `selection-expectation.test.ts` (the rubric-transform precedent: one
 * owner of ground truth, no drift).
 *
 * The rule: on a "choose k of N" exam, a group member is ATTEMPTED iff at
 * least one of its answers has non-empty text. When a group has ≥ choose_k
 * attempted members, every answer key of its UNATTEMPTED members is
 * "expected empty" — the review surface collapses those containers instead
 * of rendering empty cards. An under-answered group suppresses nothing, and
 * empty answers inside an attempted member are never suppressed (a real gap).
 *
 * The id→number mapping (rubric 'q5' → answer question_number 5) lives
 * SERVER-side only (`answer_space_groups`); the wire already carries groups
 * in answer space, so this module needs no rubric knowledge.
 *
 * Computed LIVE against the teacher's current edited text (the
 * segmentation-check pattern): typing into a collapsed container or swapping
 * content into it makes its member "attempted" and the card materializes.
 */

import type { AnswerSpaceSelectionGroup } from '@/types/transcription';
import { answerTargetId } from '@/utils/review-flags';

export type { AnswerSpaceSelectionGroup };

export interface SelectionAnswerLike {
    question_number: number;
    sub_question_id: string | null;
    /** CURRENT text — draft text overlaid with the teacher's live edits. */
    text: string;
}

/** Keys (answerTargetId format: "q5" / "q5.א") whose emptiness the selection
 *  rules fully explain. Empty set when `groups` is empty/absent. */
export function expectedEmptyKeys(
    answers: SelectionAnswerLike[],
    groups: AnswerSpaceSelectionGroup[] | undefined | null,
): Set<string> {
    const expected = new Set<string>();
    if (!groups || groups.length === 0) return expected;

    const keysByQuestion = new Map<number, string[]>();
    const attempted = new Set<number>();
    for (const a of answers) {
        const keys = keysByQuestion.get(a.question_number) ?? [];
        keys.push(answerTargetId(a));
        keysByQuestion.set(a.question_number, keys);
        if (a.text.trim()) attempted.add(a.question_number);
    }

    for (const g of groups) {
        const attemptedCount = g.question_numbers.filter((n) => attempted.has(n)).length;
        if (attemptedCount < g.choose_k) continue; // under-answered: everything stays reviewable
        for (const n of g.question_numbers) {
            if (!attempted.has(n)) {
                for (const k of keysByQuestion.get(n) ?? []) expected.add(k);
            }
        }
    }
    return expected;
}
