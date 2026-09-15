import { describe, expect, it } from 'vitest';

import {
    cycleVerdict,
    effectiveVerdict,
    emptyOverlay,
    isOverridden,
    overriddenCheckIds,
    revert,
    revertTerminalPoints,
    setCheckPoints,
    setNote,
    setTerminalPoints,
    setVerdict,
    terminalPointsFor,
    toggleEvidenceDisputed,
    typedCheckPoints,
    typedPointsFor,
    type Overlay,
} from './verdict-cycle';

/**
 * The overlay reducers — the two kinds of decision (verdict, typed amount) and
 * the two rules that keep them from contradicting each other (OD-3 b, OD-2 b).
 */

const T = 'q1.c0';
const K1 = 'q1.c0.k1';
const K2 = 'q1.c0.k2';
const now = () => '2026-09-13T00:00:00.000Z';

describe('verdict-cycle — verdicts', () => {
    it('cycles ✗ → ½ → ✓ → ✗ and drops the record when it says nothing', () => {
        let o = cycleVerdict(emptyOverlay(), T, K1, 'not_met', 'required', now);
        expect(effectiveVerdict(o, T, K1, 'not_met')).toBe('partially_met');
        o = cycleVerdict(o, T, K1, 'not_met', 'required', now);
        expect(effectiveVerdict(o, T, K1, 'not_met')).toBe('met');
        o = cycleVerdict(o, T, K1, 'not_met', 'required', now);
        // back to Vivi's verdict with nothing else on the record: gone, so the
        // pricer does not skip evidence gating on a check she did not decide
        expect(o.terminals[T]).toBeUndefined();
        expect(isOverridden(o, T, K1, 'not_met')).toBe(false);
    });

    it('revert drops the whole record, note included', () => {
        let o = setVerdict(emptyOverlay(), T, K1, 'met', 'not_met', now);
        o = setNote(o, T, K1, 'because', 'not_met', now);
        o = revert(o, T, K1);
        expect(o.terminals[T]).toBeUndefined();
    });

    it('a note alone is a record at Vivi\'s verdict; clearing it removes the record', () => {
        let o = setNote(emptyOverlay(), T, K1, 'looked, leaving it', 'met', now);
        expect(o.terminals[T]?.[0]).toMatchObject({ check_id: K1, verdict: 'met' });
        expect(isOverridden(o, T, K1, 'met')).toBe(false);
        o = setNote(o, T, K1, '   ', 'met', now);
        expect(o.terminals[T]).toBeUndefined();
    });

    it('evidence-disputed toggles on and off through the same empty-record rule', () => {
        let o = toggleEvidenceDisputed(emptyOverlay(), T, K1, 'met', now);
        expect(o.terminals[T]?.[0].evidence_disputed).toBe(true);
        o = toggleEvidenceDisputed(o, T, K1, 'met', now);
        expect(o.terminals[T]).toBeUndefined();
    });
});

describe('verdict-cycle — typed amounts [OD-R2]', () => {
    it('setCheckPoints records the amount with the verdict it IMPLIES (OD-3 b)', () => {
        const o = setCheckPoints(emptyOverlay(), T, K1, '1.5', '3', 'met', now);
        expect(o.terminals[T]?.[0]).toMatchObject(
            { check_id: K1, verdict: 'partially_met', points_awarded: '1.5' });
        expect(typedPointsFor(o, T, K1)).toBe('1.5');
        expect(typedCheckPoints(o, T)).toEqual({ [K1]: '1.5' });
        // a typed number is a decision even when it equals Vivi's own award
        const full = setCheckPoints(emptyOverlay(), T, K1, '3', '3', 'met', now);
        expect(full.terminals[T]?.[0]).toMatchObject({ verdict: 'met', points_awarded: '3' });
        expect(isOverridden(full, T, K1, 'met')).toBe(true);
    });

    it('a tariff row FLIPS ✓ ↔ ✗ and never shows ½ (ruling 2026-09-13)', () => {
        let o = cycleVerdict(emptyOverlay(), T, K2, 'met', 'tariff', now);
        expect(effectiveVerdict(o, T, K2, 'met')).toBe('not_met');
        o = cycleVerdict(o, T, K2, 'met', 'tariff', now);
        expect(o.terminals[T]).toBeUndefined();               // back to Vivi's ✓
        // a legacy ½ on a tariff prices as fired; one press takes it to ✓
        const legacy = setVerdict(emptyOverlay(), T, K2, 'partially_met', 'not_met', now);
        expect(effectiveVerdict(cycleVerdict(legacy, T, K2, 'not_met', 'tariff', now), T, K2, 'not_met'))
            .toBe('met');
    });

    it('cycling the glyph CLEARS the typed amount (OD-3 b)', () => {
        let o = setCheckPoints(emptyOverlay(), T, K1, '1.5', '3', 'met', now);
        o = cycleVerdict(o, T, K1, 'met', 'required', now);
        // ½ → ✓ … which is Vivi's verdict, no amount, no note: the record is gone
        expect(o.terminals[T]).toBeUndefined();
        o = setCheckPoints(emptyOverlay(), T, K1, '1.5', '3', 'not_met', now);
        o = cycleVerdict(o, T, K1, 'not_met', 'required', now);
        expect(o.terminals[T]?.[0]).toMatchObject({ verdict: 'met' });
        expect(o.terminals[T]?.[0].points_awarded ?? null).toBeNull();
    });

    it('typing keeps the note and the dispute — they are about the check, not the number', () => {
        let o = setNote(emptyOverlay(), T, K1, 'why', 'met', now);
        o = toggleEvidenceDisputed(o, T, K1, 'met', now);
        o = setCheckPoints(o, T, K1, '1', '3', 'met', now);
        expect(o.terminals[T]?.[0]).toMatchObject(
            { teacher_comment: 'why', evidence_disputed: true, points_awarded: '1' });
    });

    it('setTerminalPoints pins the criterion and WITHDRAWS the amounts typed beneath it (OD-2 b)', () => {
        let o = setCheckPoints(emptyOverlay(), T, K1, '1', '3', 'met', now);
        o = setNote(o, T, K2, 'kept', 'not_met', now);
        o = setCheckPoints(o, T, K2, '0.5', '2', 'not_met', now);
        o = setVerdict(o, T, 'q1.c0.k3', 'met', 'not_met', now);   // cycled by hand
        o = setTerminalPoints(o, T, '2.25', (id) => (id === K1 ? 'met' : 'not_met'), now);

        expect(terminalPointsFor(o, T)).toBe('2.25');
        expect(o.terminalPoints[T]).toEqual({ points_awarded: '2.25', decided_at: now() });
        // K1 said nothing beyond its amount → gone
        expect(o.terminals[T]?.find((r) => r.check_id === K1)).toBeUndefined();
        // K2 keeps its note, re-anchored to Vivi's verdict, amount withdrawn
        expect(o.terminals[T]?.find((r) => r.check_id === K2)).toMatchObject(
            { verdict: 'not_met', teacher_comment: 'kept' });
        expect(o.terminals[T]?.find((r) => r.check_id === K2)?.points_awarded ?? null).toBeNull();
        // a verdict she cycled by hand is a decision of its own and stays
        expect(o.terminals[T]?.find((r) => r.check_id === 'q1.c0.k3')).toMatchObject({ verdict: 'met' });
    });

    it('deciding a check beneath a pin RELEASES the pin (OD-2 b) — verdict or amount', () => {
        const pinned = setTerminalPoints(emptyOverlay(), T, '2', () => 'met', now);
        expect(terminalPointsFor(cycleVerdict(pinned, T, K1, 'met', 'required', now), T)).toBeNull();
        expect(terminalPointsFor(
            setCheckPoints(pinned, T, K1, '1', '3', 'met', now), T)).toBeNull();
        // a note or a dispute is not a points decision: the pin stands
        expect(terminalPointsFor(setNote(pinned, T, K1, 'n', 'met', now), T)).toBe('2');
        expect(terminalPointsFor(toggleEvidenceDisputed(pinned, T, K1, 'met', now), T)).toBe('2');
        // ⌫ withdraws a decision rather than making one: the pin stands too
        expect(terminalPointsFor(revert(pinned, T, K1), T)).toBe('2');
    });

    it('revertTerminalPoints withdraws the pin and nothing else', () => {
        let o = setVerdict(emptyOverlay(), T, K1, 'met', 'not_met', now);
        o = setTerminalPoints(o, T, '2', () => 'not_met', now);
        o = revertTerminalPoints(o, T);
        expect(o.terminalPoints).toEqual({});
        expect(o.terminals[T]?.[0]).toMatchObject({ verdict: 'met' });
    });

    it('never mutates its input', () => {
        const before: Overlay = setCheckPoints(emptyOverlay(), T, K1, '1', '3', 'met', now);
        const frozen = JSON.stringify(before);
        setTerminalPoints(before, T, '2', () => 'met', now);
        cycleVerdict(before, T, K1, 'met', 'required', now);
        revertTerminalPoints(setTerminalPoints(before, T, '2', () => 'met', now), T);
        expect(JSON.stringify(before)).toBe(frozen);
    });

    it('overriddenCheckIds lists typed checks too — they skip evidence gating', () => {
        const o = setCheckPoints(emptyOverlay(), T, K1, '1', '3', 'met', now);
        expect([...overriddenCheckIds(o)]).toEqual([K1]);
    });
});
