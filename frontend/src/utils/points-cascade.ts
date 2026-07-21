/**
 * PR-5 S2 E-3 (living sums) — the pure hook behind the visible cascade.
 *
 * `changedPointNodeIds(before, after)` returns the set of node ids whose point
 * value changed between two question trees: the edited leaf criterion AND every
 * ancestor `recalculateParentsFromCriteria` moved. The mirror uses it to glow
 * exactly those chips; the elevation test asserts on this set (keys, not pixels).
 *
 * Pure, id-keyed (not reference diffing) — robust across the immutable ops.
 */

import type { RubricQuestion, RubricSubQuestion, RubricCriterion } from '@/types/rubric';

function collectPoints(questions: RubricQuestion[], out: Map<string, number>): void {
    const walkCriterion = (c: RubricCriterion) => {
        out.set(c.criterion_id, c.points);
        for (const sc of c.sub_criteria ?? []) out.set(sc.sub_criterion_id, sc.points);
    };
    const walkSub = (sq: RubricSubQuestion) => {
        out.set(sq.sub_question_id, sq.points);
        for (const c of sq.criteria) walkCriterion(c);
        for (const child of sq.sub_questions ?? []) walkSub(child);
    };
    for (const q of questions) {
        out.set(q.question_id, q.total_points);
        for (const c of q.criteria) walkCriterion(c);
        for (const sq of q.sub_questions) walkSub(sq);
    }
}

export function changedPointNodeIds(
    before: RubricQuestion[],
    after: RubricQuestion[],
): Set<string> {
    const beforeMap = new Map<string, number>();
    collectPoints(before, beforeMap);
    const afterMap = new Map<string, number>();
    collectPoints(after, afterMap);

    const changed = new Set<string>();
    afterMap.forEach((pts, id) => {
        const prev = beforeMap.get(id);
        // A newly-added node (no prior value) is not a "cascade change" — only a
        // value that MOVED glows.
        if (prev !== undefined && prev !== pts) changed.add(id);
    });
    return changed;
}
