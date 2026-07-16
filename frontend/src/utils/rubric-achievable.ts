/**
 * Client mirror of the backend's achievable-points computation.
 *
 * This is a FAITHFUL port of `compute_achievable_points` in the backend
 * `app/schemas/ontology_types.py` (the function INV-4 checks against). Keep the
 * two in lockstep — if the backend rule changes, this changes with it.
 *
 *     achievable = Σ(mandatory question points)
 *                + Σ over selection groups of [top choose_k member totals]
 *
 * A question in no group is mandatory and contributes its full declared total.
 * With no selection groups, achievable = Σ all question totals — i.e. the rule
 * reduces EXACTLY to the legacy offered-sum, which is why the achievable-aware
 * INV-R3 is a strict superset of the old check (finding R-C / PR-4).
 *
 * Why this is safe to port client-side (unlike grading's best-k, which is
 * genuinely server-only): it is pure arithmetic over DECLARED totals — no
 * per-answer scores, no derived exclusion that a teacher override could flip.
 * Teacher point values are exact quarter-multiples, so `number` arithmetic is
 * exact here (no Decimal drift within the tolerance the validators use).
 *
 * @see app/schemas/ontology_types.py::compute_achievable_points — the source of truth
 * @see rubric-validation.ts::validateRubricTotalPoints — the INV-R3 (≡ backend INV-4) consumer
 */

import type { RubricQuestion } from '@/types/rubric';
import type { SelectionGroup } from '@/lib/api';

export function computeAchievablePoints(
    questions: RubricQuestion[],
    selectionGroups: SelectionGroup[] | undefined | null,
): number {
    const byId = new Map<string, number>();
    for (const q of questions) byId.set(q.question_id, q.total_points);

    const groupedIds = new Set<string>();
    let achievable = 0;

    for (const g of selectionGroups ?? []) {
        // Student-favorable default (mirrors the backend): the best `choose_k`
        // declared totals in the group count; the rest are never owed.
        const memberPoints = g.of_question_ids
            .map((qid) => byId.get(qid) ?? 0)   // dangling ref → 0 (structural validation surfaces it)
            .sort((a, b) => b - a);
        achievable += memberPoints
            .slice(0, g.choose_k)
            .reduce((sum, p) => sum + p, 0);
        for (const qid of g.of_question_ids) groupedIds.add(qid);
    }

    for (const q of questions) {
        if (!groupedIds.has(q.question_id)) achievable += q.total_points;
    }

    return achievable;
}
