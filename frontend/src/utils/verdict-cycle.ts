/**
 * The overlay: what the teacher decided, laid over what Vivi proposed (R7/R8).
 *
 * Pure reducers over `GradedTestOverrides`. The draft is never mutated — it is
 * the AI's immutable provenance, and the whole review surface is a lens over
 * (draft, overlay).
 *
 * ── TWO KINDS OF DECISION SINCE OD-R2 (owner ruling 2026-09-13) ───────────
 * A VERDICT on a check (Space), and an AMOUNT she typed — on a check
 * (`points_awarded` on the record) or on a whole criterion (`terminalPoints`).
 * A typed amount is an input to the one pricer, exactly like a verdict; it is
 * not a second arithmetic. Two rules keep the two kinds from contradicting
 * each other on screen:
 *
 *   * OD-3 (b) — the GLYPH IS DERIVED FROM THE NUMBER. Typing an amount sets
 *     the record's verdict to what the amount implies (`verdictForAmount`);
 *     cycling the glyph clears the amount. One glyph, one number, never at
 *     odds — and the server refuses any record where they are.
 *   * OD-2 (b) — LAST TOUCH WINS between a criterion and its checks. Typing on
 *     the criterion withdraws the amounts typed on its checks; deciding a
 *     check (verdict or amount) releases the criterion's pin. Under the
 *     alternative — a pin that silently outranks visible rows — the rows and
 *     the criterion total would disagree on one screen.
 *
 * ── THE CYCLE ORDER IS ✗ → ½ → ✓ → ✗ ──────────────────────────────────────
 * Deliberately upward from the harshest. The common correction is "Vivi was too
 * strict here", so one press of Space moves in the direction she most often
 * wants; the wrap keeps it reversible without a second key. A TARIFF (a
 * deduction, ruling 2026-09-13) is binary and simply flips: ✓ ↔ ✗, and a
 * legacy ½ on a tariff (which prices as fired) goes to ✓ like any ✗ would.
 *
 * ── REVERT CLEARS THE NOTE TOO ────────────────────────────────────────────
 * ⌫ removes the whole override, including `teacher_comment`,
 * `evidence_disputed` and any typed amount. The note explains a decision ("why
 * I changed this"); a note left hanging after the decision is withdrawn is a
 * comment about nothing, and it would ride into the contract as provenance for
 * a change that no longer exists. Withdrawing the decision withdraws its
 * reasons. ⌫ on a check leaves a criterion pin alone: it WITHDRAWS a decision
 * rather than making one, and the pin is a decision of its own with its own
 * revert.
 */

import { verdictForAmount, type CheckKind, type Verdict } from '@/lib/pricing';

/** The teacher's decision on one check (`TeacherOverride`, PR-G5 + OD-R2). */
export interface TeacherOverride {
    check_id: string;
    verdict: Verdict;
    /** [OD-R2] The amount she typed on this row; absent when priced from the verdict. */
    points_awarded?: string | null;
    teacher_comment?: string | null;
    evidence_disputed?: boolean;
    decided_at?: string;
}

/** [OD-R2] The amount she typed on the criterion row (`TerminalPointsOverride`). */
export interface TerminalPointsOverride {
    points_awarded: string;
    decided_at?: string;
}

/** Sparse: only terminals she touched appear. */
export type OverlayTerminals = Record<string, TeacherOverride[]>;
export type OverlayTerminalPoints = Record<string, TerminalPointsOverride>;

/**
 * Her whole working copy of the grade: check-level decisions and criterion
 * pins together, because the two reducers that keep them consistent (OD-2 b)
 * need to see both. The wire shape is `{ terminals, terminal_points }`.
 */
export interface Overlay {
    terminals: OverlayTerminals;
    terminalPoints: OverlayTerminalPoints;
}

export function emptyOverlay(): Overlay {
    return { terminals: {}, terminalPoints: {} };
}

/** True when she has decided nothing at all. */
export function isEmptyOverlay(overlay: Overlay): boolean {
    return Object.keys(overlay.terminals).length === 0
        && Object.keys(overlay.terminalPoints).length === 0;
}

const NEXT_VERDICT: Readonly<Record<Verdict, Verdict>> = {
    not_met: 'partially_met',
    partially_met: 'met',
    met: 'not_met',
};

export function nextVerdict(current: Verdict, kind: CheckKind = 'required'): Verdict {
    if (kind === 'tariff') return current === 'met' ? 'not_met' : 'met';
    return NEXT_VERDICT[current];
}

export function findOverride(
    overlay: Overlay,
    terminalId: string,
    checkId: string,
): TeacherOverride | undefined {
    return overlay.terminals[terminalId]?.find((o) => o.check_id === checkId);
}

/** Her verdict if she decided one, else Vivi's. */
export function effectiveVerdict(
    overlay: Overlay,
    terminalId: string,
    checkId: string,
    aiVerdict: Verdict,
): Verdict {
    return findOverride(overlay, terminalId, checkId)?.verdict ?? aiVerdict;
}

/**
 * True when she decided something DIFFERENT from Vivi (R7's red ring): another
 * verdict, or an amount of her own — a typed number is a decision even when
 * it happens to equal what the pricer would have derived.
 */
export function isOverridden(
    overlay: Overlay,
    terminalId: string,
    checkId: string,
    aiVerdict: Verdict,
): boolean {
    const override = findOverride(overlay, terminalId, checkId);
    if (override === undefined) return false;
    return override.verdict !== aiVerdict || override.points_awarded != null;
}

/** [OD-R2] The amount she typed on this check, if any. */
export function typedPointsFor(
    overlay: Overlay,
    terminalId: string,
    checkId: string,
): string | null {
    return findOverride(overlay, terminalId, checkId)?.points_awarded ?? null;
}

/** [OD-R2] The amount she typed on the criterion row, if any. */
export function terminalPointsFor(overlay: Overlay, terminalId: string): string | null {
    return overlay.terminalPoints[terminalId]?.points_awarded ?? null;
}

/** [OD-R2] check_id → typed amount, for one terminal — what the pricer takes. */
export function typedCheckPoints(overlay: Overlay, terminalId: string): Record<string, string> {
    const out: Record<string, string> = {};
    for (const o of overlay.terminals[terminalId] ?? []) {
        if (o.points_awarded != null) out[o.check_id] = o.points_awarded;
    }
    return out;
}

/**
 * A record that ends up saying NOTHING — her verdict equal to Vivi's, no
 * amount, no note, no dispute — is dropped. This is not tidiness.
 * `overriddenCheckIds` is what tells the pricer to skip EVIDENCE GATING, so a
 * leftover no-op record on a check whose citation was `not_found` would
 * silently CREDIT points the grader refused — with no red ring to show for it,
 * because the verdict matches. Three presses of Space back to where she
 * started is a completely ordinary thing to do.
 */
function saysNothing(override: TeacherOverride, aiVerdict: Verdict): boolean {
    return override.verdict === aiVerdict
        && override.points_awarded == null
        && !override.teacher_comment
        && !override.evidence_disputed;
}

function withTerminal(
    overlay: Overlay,
    terminalId: string,
    next: TeacherOverride[],
): Overlay {
    const terminals = { ...overlay.terminals };
    if (next.length === 0) delete terminals[terminalId];
    else terminals[terminalId] = next;
    return { ...overlay, terminals };
}

function withoutPin(overlay: Overlay, terminalId: string): Overlay {
    if (!(terminalId in overlay.terminalPoints)) return overlay;
    const terminalPoints = { ...overlay.terminalPoints };
    delete terminalPoints[terminalId];
    return { ...overlay, terminalPoints };
}

function upsert(
    overlay: Overlay,
    terminalId: string,
    updated: TeacherOverride,
    aiVerdict: Verdict,
): Overlay {
    const existing = overlay.terminals[terminalId] ?? [];
    const found = existing.some((o) => o.check_id === updated.check_id);
    if (saysNothing(updated, aiVerdict)) {
        return withTerminal(
            overlay, terminalId, existing.filter((o) => o.check_id !== updated.check_id));
    }
    return withTerminal(
        overlay,
        terminalId,
        found
            ? existing.map((o) => (o.check_id === updated.check_id ? updated : o))
            : [...existing, updated],
    );
}

/**
 * Upsert one verdict, preserving any note/dispute already on it.
 *
 * A verdict is a DECISION on the check, so (OD-3 b) it clears any amount she
 * typed there — the glyph now derives the number again — and (OD-2 b) it
 * releases a pin on the criterion above.
 *
 * `aiVerdict` is required. Without it this function cannot know whether a
 * record still means anything (see `saysNothing`).
 */
export function setVerdict(
    overlay: Overlay,
    terminalId: string,
    checkId: string,
    verdict: Verdict,
    aiVerdict: Verdict,
    now: () => string = () => new Date().toISOString(),
): Overlay {
    const found = findOverride(overlay, terminalId, checkId);
    const updated: TeacherOverride = found
        ? { ...found, verdict, points_awarded: null, decided_at: now() }
        : { check_id: checkId, verdict, decided_at: now() };
    return upsert(withoutPin(overlay, terminalId), terminalId, updated, aiVerdict);
}

/** Space: advance the EFFECTIVE verdict one step round the cycle (a tariff flips). */
export function cycleVerdict(
    overlay: Overlay,
    terminalId: string,
    checkId: string,
    aiVerdict: Verdict,
    kind: CheckKind = 'required',
    now?: () => string,
): Overlay {
    const current = effectiveVerdict(overlay, terminalId, checkId, aiVerdict);
    return setVerdict(overlay, terminalId, checkId, nextVerdict(current, kind), aiVerdict, now);
}

/**
 * ⌫: drop the override entirely — verdict, amount, note and dispute together.
 *
 * Removing the record rather than writing back Vivi's verdict is what makes the
 * overlay sparse: "she agreed" and "she never looked" stay the same state, and
 * only what she actually touched travels to the server.
 */
export function revert(
    overlay: Overlay,
    terminalId: string,
    checkId: string,
): Overlay {
    const existing = overlay.terminals[terminalId];
    if (!existing) return overlay;
    return withTerminal(overlay, terminalId, existing.filter((o) => o.check_id !== checkId));
}

/**
 * [OD-R2] She typed an amount on a credit check row (a tariff is toggle-only).
 *
 * The verdict is DERIVED from it (OD-3 b) — `maximum` is the row's `points` —
 * and the criterion's pin, if any, is released (OD-2 b). Note and dispute
 * survive; they are about the check, not about the number.
 */
export function setCheckPoints(
    overlay: Overlay,
    terminalId: string,
    checkId: string,
    amount: string,
    maximum: string,
    aiVerdict: Verdict,
    now: () => string = () => new Date().toISOString(),
): Overlay {
    const found = findOverride(overlay, terminalId, checkId);
    const verdict = verdictForAmount(amount, maximum);
    const updated: TeacherOverride = found
        ? { ...found, verdict, points_awarded: amount, decided_at: now() }
        : { check_id: checkId, verdict, points_awarded: amount, decided_at: now() };
    return upsert(withoutPin(overlay, terminalId), terminalId, updated, aiVerdict);
}

/**
 * [OD-R2] She typed an amount on the criterion row.
 *
 * The amounts typed on the rows beneath are WITHDRAWN (OD-2 b) — the whole
 * decision, verdict included, because that verdict was derived from a number
 * she has just replaced. Notes and disputes on those rows survive at Vivi's
 * verdict, which is why `aiVerdictOf` is needed: a note-only record must be
 * re-anchored to the proposal, and a record that then says nothing is dropped.
 * Verdicts she cycled BY HAND are left alone: they are decisions in their own
 * right, and the pin simply outranks them until she touches a row again.
 */
export function setTerminalPoints(
    overlay: Overlay,
    terminalId: string,
    amount: string,
    aiVerdictOf: (checkId: string) => Verdict,
    now: () => string = () => new Date().toISOString(),
): Overlay {
    let next: Overlay = {
        ...overlay,
        terminalPoints: {
            ...overlay.terminalPoints,
            [terminalId]: { points_awarded: amount, decided_at: now() },
        },
    };
    for (const record of overlay.terminals[terminalId] ?? []) {
        if (record.points_awarded == null) continue;
        const ai = aiVerdictOf(record.check_id);
        const { points_awarded: _dropped, ...rest } = record;
        next = upsert(next, terminalId, { ...rest, verdict: ai }, ai);
    }
    return next;
}

/** [OD-R2] Withdraw the amount typed on the criterion row. */
export function revertTerminalPoints(overlay: Overlay, terminalId: string): Overlay {
    return withoutPin(overlay, terminalId);
}

/**
 * H: attach a note. An empty note removes ONLY the note.
 *
 * A note can exist without a verdict change — "I looked at this and I am
 * leaving it, here is why" is a real thing a teacher writes — so this creates
 * an override at the CURRENT effective verdict rather than refusing.
 */
export function setNote(
    overlay: Overlay,
    terminalId: string,
    checkId: string,
    note: string,
    aiVerdict: Verdict,
    now: () => string = () => new Date().toISOString(),
): Overlay {
    const trimmed = note.trim();
    const found = findOverride(overlay, terminalId, checkId);

    if (!found) {
        if (!trimmed) return overlay;
        return upsert(overlay, terminalId, {
            check_id: checkId,
            verdict: aiVerdict,
            teacher_comment: trimmed,
            decided_at: now(),
        }, aiVerdict);
    }
    return upsert(overlay, terminalId, { ...found, teacher_comment: trimmed || null }, aiVerdict);
}

/** E: toggle «העדות שגויה». Same empty-record rule as setNote. */
export function toggleEvidenceDisputed(
    overlay: Overlay,
    terminalId: string,
    checkId: string,
    aiVerdict: Verdict,
    now: () => string = () => new Date().toISOString(),
): Overlay {
    const found = findOverride(overlay, terminalId, checkId);
    if (!found) {
        return upsert(overlay, terminalId, {
            check_id: checkId,
            verdict: aiVerdict,
            evidence_disputed: true,
            decided_at: now(),
        }, aiVerdict);
    }
    return upsert(
        overlay, terminalId, { ...found, evidence_disputed: !found.evidence_disputed }, aiVerdict);
}

/** Every check id she decided — what the pricer needs to skip evidence gating. */
export function overriddenCheckIds(overlay: Overlay): Set<string> {
    const ids = new Set<string>();
    for (const list of Object.values(overlay.terminals)) {
        for (const override of list) ids.add(override.check_id);
    }
    return ids;
}
