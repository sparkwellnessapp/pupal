/**
 * Is this feedback still describing the grade it was written for?
 *
 * A faithful port of `backend/app/agents/feedback/staleness.py`. Staleness is
 * DERIVED, never a flag someone must remember to set: the text carries the hash
 * of the verdict vector it was generated from, and anything that moves that
 * vector makes the text stale by construction.
 *
 * OD-G4.1 — the basis is the ORDERED EFFECTIVE VERDICT VECTOR and nothing else.
 * Not points (they are derived from verdicts, so hashing them would make the
 * text stale when nothing it depends on moved) and not quotes (the feedback
 * says what was credited and what was missing, not which span was cited).
 *
 * ORDER IS PART OF THE BASIS: the same verdicts in a different sequence
 * describe a different answer, and the prose follows the sequence.
 *
 * @see backend/app/agents/feedback/staleness.py — the source of truth
 */

import { sha256Hex } from '@/lib/sha256';
import type { Verdict } from '@/lib/pricing';

/** The shape the hash is taken over — check id and effective verdict, nothing else. */
export interface BasisCheck {
    check_id: string;
    verdict: Verdict;
}

/** One piece of student-facing feedback with the basis it was written for. */
export interface FeedbackText {
    text: string;
    basis_hash?: string;
}

/** sha256 over `check_id=verdict` pairs, joined by `|`, in document order. */
export function basisHash(checks: readonly BasisCheck[]): string {
    return sha256Hex(checks.map((c) => `${c.check_id}=${c.verdict}`).join('|'));
}

/**
 * True when the verdicts have moved since this text was written.
 *
 * A text with no `basis_hash` is NOT stale: nothing was claimed, so nothing can
 * have gone out of date. Saying otherwise would put an amber "rewrite me"
 * header on feedback that has no idea what it was written for — a warning she
 * cannot act on, which is how the click-through reflex gets trained (the INV-6
 * lesson, CLAUDE.md §5).
 */
export function isStale(
    text: FeedbackText | null | undefined,
    checks: readonly BasisCheck[],
): boolean {
    if (!text || !text.basis_hash) return false;
    return text.basis_hash !== basisHash(checks);
}

/**
 * The three states a feedback card can be in.
 *
 * `absent` is a FIRST-CLASS WIRE STATE, not an error: the feedback call can
 * fail while the grade itself lands (review-first, never guess — the draft is
 * still valid and she must be able to review it). It renders as
 * «לא נכתב משוב» with a «כתיבה» action, never as an error page (R11).
 */
export type FeedbackState = 'absent' | 'stale' | 'fresh';

export function feedbackState(
    text: FeedbackText | null | undefined,
    checks: readonly BasisCheck[],
    teacherEdited = false,
): FeedbackState {
    if (!text || !text.text) return 'absent';
    // Her own words are never stale. She wrote them against what she could see;
    // telling her they are out of date would be Vivi second-guessing the
    // teacher, which is the one thing this product does not do.
    if (teacherEdited) return 'fresh';
    return isStale(text, checks) ? 'stale' : 'fresh';
}
