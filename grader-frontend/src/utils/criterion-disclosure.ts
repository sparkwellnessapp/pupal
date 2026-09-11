import type { ReviewScope } from './grade-review-model';
import type { ReviewMarker } from './review-markers';

/**
 * Which criteria open themselves when a test is first shown (S4, decision D1).
 *
 * THE DEFAULT IS COLLAPSED, AND THE EXCEPTION IS THE POINT. Hiding every
 * breakdown declutters the screen, which is what was asked for — but it also
 * makes «approve without reading» the path of least resistance, and the grading
 * gate IS the product (§2). So a criterion that has something to say opens
 * itself, and the teacher closes it if she disagrees.
 *
 * "Something to say" is NOT a new rule invented here. It is:
 *
 *   1. A MARKER, from `review-markers.ts` — the same set `F` walks and the
 *      amber dot counts. Forking a second "needs eyes" predicate is exactly the
 *      duplication §0.4 forbids, and the two would drift within a sprint.
 *   2. HER OWN WORK — a check she overrode, or evidence she disputed. Not a
 *      marker (markers are derived from the DRAFT; these come from the
 *      overlay), but hiding what she already decided is its own kind of wrong.
 *
 * ⚠ THIS IS AN OPENING STATE, COMPUTED ONCE PER TEST — NEVER A LIVE DERIVATION.
 * Clause 2 reads the overlay, which changes as she works. Recomputed on every
 * overlay change, a criterion she had just collapsed would spring back open the
 * instant she overrode a check inside it — the UI arguing with the teacher.
 * The caller freezes this at mount and owns every change after; on re-entry to
 * a part-reviewed test it correctly re-opens what she had already touched.
 */
export function initialExpandedTerminals(
    scopes: readonly ReviewScope[],
    markers: readonly ReviewMarker[],
): ReadonlySet<string> {
    // Markers anchor on a check id OR on a terminal id (a scope-kind marker for
    // a clamped or closed-world terminal), so both are looked up by plain id.
    const marked = new Set(markers.map((m) => m.id));
    const expanded = new Set<string>();

    for (const scope of scopes) {
        for (const criterion of scope.criteria) {
            const wanted = marked.has(criterion.terminalId)
                || criterion.checks.some((check) => marked.has(check.check_id)
                    || check.overridden
                    || check.evidenceDisputed);
            if (wanted) expanded.add(criterion.terminalId);
        }
    }
    return expanded;
}
