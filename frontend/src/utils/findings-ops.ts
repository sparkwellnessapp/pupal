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

import type { RubricQuestion, RubricSubQuestion } from '@/types/rubric';
import {
    changeQuestionPoints, changeSubQuestionPointsAtPath,
} from '@/utils/rubric-editor-ops';
import type { Finding, PedagogicalMistakeLike } from '@/utils/findings';

// ─────────────────────────────────────────────────────────────────────────────
// Scope resolution — a finding speaks in scope ids, the ops speak in indices
// ─────────────────────────────────────────────────────────────────────────────

export interface ScopePath { qIndex: number; sqPath: number[] }

/**
 * Resolve a dotted scope id (`q1`, `q1.א`, `q1.א.2`) to the (qIndex, sqPath) the
 * pure ops address. Returns null when the id names no node in the CURRENT tree —
 * which happens legitimately after a structural edit, and must degrade to "no
 * fix offered" rather than to a wrong write.
 */
export function resolveScopePath(questions: RubricQuestion[], scopeId: string | null): ScopePath | null {
    if (!scopeId) return null;
    const parts = scopeId.split('.');
    const qIndex = questions.findIndex((q) => q.question_id === parts[0]);
    if (qIndex < 0) return null;

    const sqPath: number[] = [];
    let level: RubricSubQuestion[] = questions[qIndex].sub_questions ?? [];
    for (let d = 1; d < parts.length; d++) {
        const idx = level.findIndex((sq) => sq.sub_question_id === parts[d]);
        if (idx < 0) return null;              // the path does not resolve — offer nothing
        sqPath.push(idx);
        level = level[idx].sub_questions ?? [];
    }
    return { qIndex, sqPath };
}

// ─────────────────────────────────────────────────────────────────────────────
// §3 — apply the proposal
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Apply a finding's fix to the question tree, through the EXISTING pure ops
 * (imported, never forked — the mirror's correctness invariant).
 *
 * Sets the node's DECLARED value to the sum its own children already state. No
 * redistribution, no rescaling of children: the number comes from her rubric, and
 * the E-3 cascade then makes the arithmetic visible.
 *
 * Returns the input unchanged when there is nothing to apply — a rubric-level fix
 * targets the declared total, which lives outside `questions` and is applied by the
 * caller through onTotalPointsChange.
 */
export function applyFindingFix(questions: RubricQuestion[], finding: Finding): RubricQuestion[] {
    const fix = finding.fix;
    if (!fix || fix.target === 'rubric') return questions;

    const path = resolveScopePath(questions, finding.scopeId);
    if (!path) return questions;

    return fix.target === 'question'
        ? changeQuestionPoints(questions, path.qIndex, fix.newValue)
        : changeSubQuestionPointsAtPath(questions, path.qIndex, path.sqPath, fix.newValue);
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
