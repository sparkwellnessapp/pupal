/**
 * PR-5 Sprint 2 — the ONE shared severity-predicate + dedup module for findings.
 *
 * Both `countFindings` (the scalar) and `findingSectionsByQuestion` (the per-section
 * map, E-2's rail dots) consume this — three call sites, one truth. Keeping the
 * predicate here means the "what counts as an open finding" rule (lowercase
 * error/warning severities, as wired) lives in exactly one place.
 *
 * Why lowercase: `Annotation.severity` is `'error' | 'warning' | 'info'` on the
 * wire and from the client validator (see lib/api.ts::Annotation). The backend's
 * uppercase `ERROR|WARNING|INFO` is normalized before it reaches the client, so a
 * consumer that keys on uppercase silently matches nothing. Do not add an uppercase
 * branch here — fix the normalization at the boundary if a raw uppercase ever leaks.
 *
 * @see session-spine.ts — countFindings / findingSectionsByQuestion (the consumers)
 */

import type { Annotation } from '@/lib/api';

/**
 * An "open finding" = an unresolved error or warning the teacher must see and act
 * on. INFO is not a finding (it proceeds silently — CLAUDE.md §6).
 */
export function isOpenFinding(a: Annotation): boolean {
    return a.severity === 'error' || a.severity === 'warning';
}

/**
 * Collapse the open findings into their deduped decomposition:
 *   - `nodeTargets` — the DISTINCT anchored nodes (by `target_id`). Two annotations
 *     on the same node (e.g. an extraction `rubric_mismatch` and a live sum
 *     invariant on `q1.א.2`) are ONE finding — the flaw-1 ruling.
 *   - `globalCount`  — null-target (rubric-scope) findings, which cannot dedup by
 *     node and each count individually.
 *
 * `countFindings === nodeTargets.size + globalCount`. Section attribution
 * (findingSectionsByQuestion) walks `nodeTargets` only — a rubric-scope finding
 * has no section to dot.
 */
export function dedupeOpenFindings(
    annotations: Annotation[],
): { nodeTargets: Set<string>; globalCount: number } {
    const nodeTargets = new Set<string>();
    let globalCount = 0;
    for (const a of annotations) {
        if (!isOpenFinding(a)) continue;
        if (a.target_id) nodeTargets.add(a.target_id);
        else globalCount++;
    }
    return { nodeTargets, globalCount };
}
