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
 * The scope key an annotation pairs on. The rubric scope reaches us under TWO
 * spellings — the backend emits `target_id: null` for a RUBRIC-scoped mismatch
 * while the client's INV-R3 emits `'rubric'` — and the UI already treats them as
 * one bucket (the global banner). Normalizing here keeps the pairing rule honest
 * for that pair too.
 */
function scopeKey(a: Annotation): string {
    return a.target_id ?? 'rubric';
}

/**
 * Is this annotation LIVE — i.e. recomputed from the current editor state on every
 * edit — as opposed to a static extraction-time message?
 *
 * Keyed on the client validator's own id convention: every issue `key` minted by
 * `rubric-validation.ts` is `inv-r…` (`inv-r1-q1`, `inv-r1b-q1.א.2`, `inv-r2-<cid>`,
 * `inv-r3-rubric-total`, `inv-r-xor-<id>`). That convention is the contract between
 * the validator and this module; a test pins it so a renamed key cannot silently
 * turn every live finding back into a "stale" one.
 */
export function isLiveValidatorAnnotation(a: Annotation): boolean {
    return typeof a.id === 'string' && /^inv-r/.test(a.id);
}

/**
 * D7 — THE STALE-ASSERTION RULE. Extraction-origin annotations carry numbers baked
 * into the message string at extraction time (backend `pipeline.py` interpolates
 * `computed`/`declared` into Hebrew prose). They NEVER recompute: `page.tsx` sets
 * `extractionAnnotations` once and passes it through forever. So the moment the
 * teacher edits a point value, that message asserts a present-tense claim about the
 * editor state that is FALSE — the "lying warning" (a warning citing 40/21 beside a
 * header reading 25).
 *
 * The fix is structural, not a rewording: when a static annotation and a LIVE one
 * describe the SAME node, render only the live one — it is recomputable and current.
 * This is the same pairing rule `dedupeOpenFindings` already applies for counting
 * (the flaw-1 ruling: an extraction `rubric_mismatch` and a live sum invariant on
 * one node are ONE finding), now applied to what the teacher actually sees.
 *
 * RULE ADOPTED WITH IT: an extraction-origin message may never assert a present-tense
 * claim about editor state. Its content survives only as the "original document"
 * residual (Sprint 3 formalizes that card).
 *
 * RESIDUAL (known, deliberately not cured here): when the teacher RESOLVES the
 * mismatch, the live twin disappears and the static one renders alone — still
 * asserting the old numbers. Suppression cannot see that; only the Sprint-3 residual
 * card (which re-frames it as past-tense provenance) closes it.
 */
export function visibleAnnotations(annotations: Annotation[]): Annotation[] {
    const liveScopes = new Set<string>();
    for (const a of annotations) {
        if (isLiveValidatorAnnotation(a)) liveScopes.add(scopeKey(a));
    }
    if (liveScopes.size === 0) return annotations;
    return annotations.filter(
        (a) => isLiveValidatorAnnotation(a) || !liveScopes.has(scopeKey(a)),
    );
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
