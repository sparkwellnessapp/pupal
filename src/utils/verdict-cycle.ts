/**
 * The overlay: what the teacher decided, laid over what Vivi proposed (R7/R8).
 *
 * Pure reducers over `GradedTestOverrides.terminals`. The draft is never
 * mutated — it is the AI's immutable provenance, and the whole review surface
 * is a lens over (draft, overlay).
 *
 * ── THE CYCLE ORDER IS ✗ → ½ → ✓ → ✗ ──────────────────────────────────────
 * Deliberately upward from the harshest. The common correction is "Vivi was too
 * strict here", so one press of Space moves in the direction she most often
 * wants; the wrap keeps it reversible without a second key.
 *
 * ── REVERT CLEARS THE NOTE TOO ────────────────────────────────────────────
 * ⌫ removes the whole override, including `teacher_comment` and
 * `evidence_disputed`. The note explains a decision ("why I changed this"); a
 * note left hanging after the decision is withdrawn is a comment about nothing,
 * and it would ride into the contract as provenance for a change that no longer
 * exists. Withdrawing the decision withdraws its reasons.
 */

import type { Verdict } from '@/lib/pricing';

/** The teacher's decision on one check (`TeacherOverride`, PR-G5). */
export interface TeacherOverride {
    check_id: string;
    verdict: Verdict;
    teacher_comment?: string | null;
    evidence_disputed?: boolean;
    decided_at?: string;
}

/** Sparse: only terminals she touched appear. */
export type OverlayTerminals = Record<string, TeacherOverride[]>;

const NEXT_VERDICT: Readonly<Record<Verdict, Verdict>> = {
    not_met: 'partially_met',
    partially_met: 'met',
    met: 'not_met',
};

export function nextVerdict(current: Verdict): Verdict {
    return NEXT_VERDICT[current];
}

export function findOverride(
    terminals: OverlayTerminals,
    terminalId: string,
    checkId: string,
): TeacherOverride | undefined {
    return terminals[terminalId]?.find((o) => o.check_id === checkId);
}

/** Her verdict if she decided one, else Vivi's. */
export function effectiveVerdict(
    terminals: OverlayTerminals,
    terminalId: string,
    checkId: string,
    aiVerdict: Verdict,
): Verdict {
    return findOverride(terminals, terminalId, checkId)?.verdict ?? aiVerdict;
}

/** True when she decided something DIFFERENT from Vivi (R7's red ring). */
export function isOverridden(
    terminals: OverlayTerminals,
    terminalId: string,
    checkId: string,
    aiVerdict: Verdict,
): boolean {
    const override = findOverride(terminals, terminalId, checkId);
    return override !== undefined && override.verdict !== aiVerdict;
}

function withTerminal(
    terminals: OverlayTerminals,
    terminalId: string,
    next: TeacherOverride[],
): OverlayTerminals {
    const out = { ...terminals };
    if (next.length === 0) delete out[terminalId];
    else out[terminalId] = next;
    return out;
}

/**
 * Upsert one override, preserving any note/dispute already on it.
 *
 * A record that ends up saying NOTHING — her verdict equal to Vivi's, no note,
 * no dispute — is dropped, exactly as `setNote` and `toggleEvidenceDisputed`
 * do. This is not tidiness. `overriddenCheckIds` is what tells the pricer to
 * skip EVIDENCE GATING, so a leftover no-op record on a check whose citation
 * was `not_found` would silently CREDIT points the grader refused — with no
 * red ring to show for it, because the verdict matches. Three presses of Space
 * back to where she started is a completely ordinary thing to do.
 *
 * `aiVerdict` is therefore required. Without it this function cannot know
 * whether a record still means anything.
 */
export function setVerdict(
    terminals: OverlayTerminals,
    terminalId: string,
    checkId: string,
    verdict: Verdict,
    aiVerdict: Verdict,
    now: () => string = () => new Date().toISOString(),
): OverlayTerminals {
    const existing = terminals[terminalId] ?? [];
    const found = existing.find((o) => o.check_id === checkId);
    const updated: TeacherOverride = found
        ? { ...found, verdict, decided_at: now() }
        : { check_id: checkId, verdict, decided_at: now() };

    if (verdict === aiVerdict && !updated.teacher_comment && !updated.evidence_disputed) {
        return withTerminal(
            terminals, terminalId, existing.filter((o) => o.check_id !== checkId));
    }
    return withTerminal(
        terminals,
        terminalId,
        found
            ? existing.map((o) => (o.check_id === checkId ? updated : o))
            : [...existing, updated],
    );
}

/** Space: advance the EFFECTIVE verdict one step round the cycle. */
export function cycleVerdict(
    terminals: OverlayTerminals,
    terminalId: string,
    checkId: string,
    aiVerdict: Verdict,
    now?: () => string,
): OverlayTerminals {
    const current = effectiveVerdict(terminals, terminalId, checkId, aiVerdict);
    return setVerdict(
        terminals, terminalId, checkId, nextVerdict(current), aiVerdict, now);
}

/**
 * ⌫: drop the override entirely — verdict, note and dispute together.
 *
 * Removing the record rather than writing back Vivi's verdict is what makes the
 * overlay sparse: "she agreed" and "she never looked" stay the same state, and
 * only what she actually touched travels to the server.
 */
export function revert(
    terminals: OverlayTerminals,
    terminalId: string,
    checkId: string,
): OverlayTerminals {
    const existing = terminals[terminalId];
    if (!existing) return terminals;
    return withTerminal(terminals, terminalId, existing.filter((o) => o.check_id !== checkId));
}

/**
 * H: attach a note. An empty note removes ONLY the note.
 *
 * A note can exist without a verdict change — "I looked at this and I am
 * leaving it, here is why" is a real thing a teacher writes — so this creates
 * an override at the CURRENT effective verdict rather than refusing.
 */
export function setNote(
    terminals: OverlayTerminals,
    terminalId: string,
    checkId: string,
    note: string,
    aiVerdict: Verdict,
    now: () => string = () => new Date().toISOString(),
): OverlayTerminals {
    const trimmed = note.trim();
    const existing = terminals[terminalId] ?? [];
    const found = existing.find((o) => o.check_id === checkId);

    if (!found) {
        if (!trimmed) return terminals;
        return withTerminal(terminals, terminalId, [...existing, {
            check_id: checkId,
            verdict: aiVerdict,
            teacher_comment: trimmed,
            decided_at: now(),
        }]);
    }

    const updated: TeacherOverride = { ...found, teacher_comment: trimmed || null };
    // An override that now says nothing — same verdict as Vivi, no note, no
    // dispute — is not a decision, so it stops travelling.
    const empty = updated.verdict === aiVerdict
        && !updated.teacher_comment && !updated.evidence_disputed;
    return withTerminal(
        terminals,
        terminalId,
        empty
            ? existing.filter((o) => o.check_id !== checkId)
            : existing.map((o) => (o.check_id === checkId ? updated : o)),
    );
}

/** E: toggle «העדות שגויה». Same empty-record rule as setNote. */
export function toggleEvidenceDisputed(
    terminals: OverlayTerminals,
    terminalId: string,
    checkId: string,
    aiVerdict: Verdict,
    now: () => string = () => new Date().toISOString(),
): OverlayTerminals {
    const existing = terminals[terminalId] ?? [];
    const found = existing.find((o) => o.check_id === checkId);

    if (!found) {
        return withTerminal(terminals, terminalId, [...existing, {
            check_id: checkId,
            verdict: aiVerdict,
            evidence_disputed: true,
            decided_at: now(),
        }]);
    }

    const updated: TeacherOverride = { ...found, evidence_disputed: !found.evidence_disputed };
    const empty = updated.verdict === aiVerdict
        && !updated.teacher_comment && !updated.evidence_disputed;
    return withTerminal(
        terminals,
        terminalId,
        empty
            ? existing.filter((o) => o.check_id !== checkId)
            : existing.map((o) => (o.check_id === checkId ? updated : o)),
    );
}

/** Every check id she decided — what the pricer needs to skip evidence gating. */
export function overriddenCheckIds(terminals: OverlayTerminals): Set<string> {
    const ids = new Set<string>();
    for (const list of Object.values(terminals)) {
        for (const override of list) ids.add(override.check_id);
    }
    return ids;
}
