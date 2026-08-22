/**
 * PR-6 §3/§4 — THE FIX INTERACTION, as pure functions.
 *
 * This is the demo moment and the trust moment: Vivi proposes, the teacher clicks
 * once, the sums settle, and the system remembers what she decided. Everything
 * here is pure and immutable for the same reason the mirror's edit ops are — the
 * page-level undo stack pushes snapshots BY REFERENCE and relies on structural
 * sharing, so one in-place mutation would retroactively corrupt earlier snapshots.
 *
 * Applying a fix does NOT mark the finding resolved. It changes the points through
 * the ordinary ops, and the LIVE validator then recomputes and finds nothing —
 * that is what closes the card. Resolution is never static bookkeeping.
 */

import type { RubricQuestion } from '@/types/rubric';
import { applyEditSteps, type AppliedSteps } from '@/utils/edit-steps';
import type { Finding, PedagogicalMistakeLike } from '@/utils/findings';

// Scope resolution moved to edit-steps.ts (the interpreter needs it and the
// module graph must stay a DAG); the public API is unchanged.
export { resolveScopePath, type ScopePath } from '@/utils/edit-steps';

// ─────────────────────────────────────────────────────────────────────────────
// §3 — apply the proposal
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Apply a finding's fix through the ONE edit-steps interpreter (which itself
 * routes every mutation through the existing pure ops — imported, never forked,
 * the mirror's correctness invariant).
 *
 * Returns null when the plan does not apply to the CURRENT tree (she edited
 * structurally since composition) — the caller must then change nothing.
 * `declaredTotal`, when present, is the rubric-level value the caller applies
 * through its own handler (it lives outside `questions`).
 */
export function applyFindingFix(questions: RubricQuestion[], finding: Finding): AppliedSteps | null {
    if (!finding.fix) return null;
    return applyEditSteps(questions, finding.fix.steps);
}

// ─────────────────────────────────────────────────────────────────────────────
// §4 — record the decision
// ─────────────────────────────────────────────────────────────────────────────

/** ISO-8601, injectable so tests are not clock-dependent. */
export type Clock = () => string;
const nowIso: Clock = () => new Date().toISOString();

function patch(
    mistakes: PedagogicalMistakeLike[],
    mistakeId: string | null,
    updates: Partial<PedagogicalMistakeLike>,
): PedagogicalMistakeLike[] {
    if (!mistakeId) return mistakes;
    return mistakes.map((m) => (m.mistake_id === mistakeId ? { ...m, ...updates } : m));
}

/** She accepted the proposal. */
export function recordFixApplied(
    mistakes: PedagogicalMistakeLike[], mistakeId: string | null, clock: Clock = nowIso,
): PedagogicalMistakeLike[] {
    return patch(mistakes, mistakeId, { fix_applied: true, fix_applied_at: clock() });
}

/**
 * She undid it. AN UNDONE FIX IS NOT AN APPLIED FIX — the record is cleared, not
 * left standing with a stale timestamp. An audit trail that remembers a decision
 * she reversed is worse than no audit trail.
 */
export function clearFixApplied(
    mistakes: PedagogicalMistakeLike[], mistakeId: string | null,
): PedagogicalMistakeLike[] {
    return patch(mistakes, mistakeId, { fix_applied: null, fix_applied_at: null });
}

/** She overruled Vivi: «השאירי כך». The finding stands, and is never re-asked. */
export function recordDismissed(
    mistakes: PedagogicalMistakeLike[], mistakeId: string | null, clock: Clock = nowIso,
): PedagogicalMistakeLike[] {
    return patch(mistakes, mistakeId, { dismissed: true, dismissed_at: clock() });
}

/** She reopened her own dismissal — equally a decision, equally recorded by absence. */
export function clearDismissed(
    mistakes: PedagogicalMistakeLike[], mistakeId: string | null,
): PedagogicalMistakeLike[] {
    return patch(mistakes, mistakeId, { dismissed: null, dismissed_at: null });
}
