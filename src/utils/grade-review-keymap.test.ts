import { describe, it, expect } from 'vitest';

import { resolveKeyAction, type GradeKeyInput } from './grade-review-keymap';
import { resolveKeyAction as resolveTranscriptionKey } from './review-keymap';

const press = (over: Partial<GradeKeyInput> = {}): GradeKeyInput => ({
    key: 'ArrowDown',
    code: 'ArrowDown',
    ctrlOrMeta: false,
    isComposing: false,
    repeat: false,
    inEditable: false,
    modalOpen: false,
    ...over,
});

/**
 * The review keymap as a PURE reducer, mirroring `review-keymap.ts`'s shape so
 * the two modules stay legible side by side. PR spec §5 is the map; §5 also
 * orders the reconciliation with the transcription module (census C), which is
 * the last describe block.
 */
describe('grade-review keymap — PR spec §5', () => {
    it('moves between checks with ↓ / ↑', () => {
        expect(resolveKeyAction(press({ key: 'ArrowDown', code: 'ArrowDown' })))
            .toMatchObject({ action: 'nextCheck' });
        expect(resolveKeyAction(press({ key: 'ArrowUp', code: 'ArrowUp' })))
            .toMatchObject({ action: 'prevCheck' });
    });

    it('moves between TESTS with ← / →, matching the on-screen arrows in RTL', () => {
        expect(resolveKeyAction(press({ key: 'ArrowLeft', code: 'ArrowLeft' })))
            .toMatchObject({ action: 'nextTest' });
        expect(resolveKeyAction(press({ key: 'ArrowRight', code: 'ArrowRight' })))
            .toMatchObject({ action: 'prevTest' });
    });

    it('cycles the verdict on Space and swallows the page scroll', () => {
        expect(resolveKeyAction(press({ key: ' ', code: 'Space' })))
            .toEqual({ action: 'cycleVerdict', preventDefault: true });
    });

    it('reverts on ⌫ and never lets the browser navigate back', () => {
        expect(resolveKeyAction(press({ key: 'Backspace', code: 'Backspace' })))
            .toEqual({ action: 'revert', preventDefault: true });
    });

    it('binds F / H / E to marker, note and evidence-disputed', () => {
        expect(resolveKeyAction(press({ key: 'f', code: 'KeyF' })))
            .toMatchObject({ action: 'nextMarker' });
        expect(resolveKeyAction(press({ key: 'h', code: 'KeyH' })))
            .toMatchObject({ action: 'note' });
        expect(resolveKeyAction(press({ key: 'e', code: 'KeyE' })))
            .toMatchObject({ action: 'disputeEvidence' });
    });

    /**
     * THE finding this reducer exists for. Every teacher using this product
     * types Hebrew, so her layout reports `key: 'כ'` for the physical F key.
     * A `key`-based letter binding is dead on the only keyboard that matters.
     */
    it('resolves letter keys by physical POSITION, so a Hebrew layout works', () => {
        expect(resolveKeyAction(press({ key: 'כ', code: 'KeyF' })))
            .toMatchObject({ action: 'nextMarker' });
        expect(resolveKeyAction(press({ key: 'י', code: 'KeyH' })))
            .toMatchObject({ action: 'note' });
        expect(resolveKeyAction(press({ key: 'ק', code: 'KeyE' })))
            .toMatchObject({ action: 'disputeEvidence' });
    });

    it('still honours a Latin key when the event carries no code', () => {
        // Synthetic events and some remote-desktop stacks omit `code`.
        expect(resolveKeyAction(press({ key: 'F', code: '' })))
            .toMatchObject({ action: 'nextMarker' });
    });

    it('approves ONLY on Ctrl/⌘ + Enter — never on a bare Enter', () => {
        expect(resolveKeyAction(press({ key: 'Enter', code: 'Enter', ctrlOrMeta: true })))
            .toMatchObject({ action: 'approve' });
        expect(resolveKeyAction(press({ key: 'Enter', code: 'Enter' }))).toBeNull();
    });

    it('releases on Esc', () => {
        expect(resolveKeyAction(press({ key: 'Escape', code: 'Escape' })))
            .toMatchObject({ action: 'release' });
    });

    it('leaves the digits alone (OD-F6: accepted extension, not v1)', () => {
        for (const d of ['1', '2', '3']) {
            expect(resolveKeyAction(press({ key: d, code: `Digit${d}` }))).toBeNull();
        }
    });

    /**
     * OD-F7, RULED 2026-08-31: bind it. This surface autosaves, so Ctrl+S has
     * nothing of its own to do — but a teacher carries the habit over from the
     * transcription module, and leaving it unbound hands her the BROWSER's
     * "save this page" dialog, which looks like the app broke. It flushes the
     * pending autosave and says «נשמר». preventDefault is the whole point.
     */
    it('answers Ctrl/⌘+S with an explicit save-now (OD-F7)', () => {
        expect(resolveKeyAction(press({ key: 's', code: 'KeyS', ctrlOrMeta: true })))
            .toEqual({ action: 'save', preventDefault: true });
    });

    it('answers Ctrl+S on a Hebrew layout too (ס sits on the S key)', () => {
        expect(resolveKeyAction(press({ key: 'ס', code: 'KeyS', ctrlOrMeta: true })))
            .toMatchObject({ action: 'save' });
    });
});

describe('grade-review keymap — when the map goes quiet', () => {
    it('never acts mid-IME-composition', () => {
        expect(resolveKeyAction(press({ key: ' ', code: 'Space', isComposing: true }))).toBeNull();
    });

    it('never acts behind an open modal', () => {
        expect(resolveKeyAction(press({ key: ' ', code: 'Space', modalOpen: true }))).toBeNull();
    });

    it('is inert inside a text field, except approve and escape', () => {
        const inEditable = { inEditable: true };
        expect(resolveKeyAction(press({ key: ' ', code: 'Space', ...inEditable }))).toBeNull();
        expect(resolveKeyAction(press({ key: 'f', code: 'KeyF', ...inEditable }))).toBeNull();
        expect(resolveKeyAction(press({ key: 'Backspace', code: 'Backspace', ...inEditable }))).toBeNull();
        expect(resolveKeyAction(press({ key: 'ArrowDown', code: 'ArrowDown', ...inEditable }))).toBeNull();

        expect(resolveKeyAction(press({ key: 'Enter', code: 'Enter', ctrlOrMeta: true, ...inEditable })))
            .toMatchObject({ action: 'approve' });
        expect(resolveKeyAction(press({ key: 'Escape', code: 'Escape', ...inEditable })))
            .toMatchObject({ action: 'release' });
        // Ctrl+S survives a text field, exactly as it does in transcription —
        // mid-sentence in a feedback box is where the habit fires hardest.
        expect(resolveKeyAction(press({ key: 's', code: 'KeyS', ctrlOrMeta: true, ...inEditable })))
            .toMatchObject({ action: 'save' });
    });

    /**
     * Auto-repeat navigates but never DECIDES. Holding Space would spin
     * ✗ → ½ → ✓ → ✗ like a slot machine and leave a verdict nobody chose;
     * holding ↓ to travel a long scope is exactly what a key repeat is for.
     */
    it('ignores auto-repeat for the deciding keys, honours it for navigation', () => {
        expect(resolveKeyAction(press({ key: ' ', code: 'Space', repeat: true }))).toBeNull();
        expect(resolveKeyAction(press({ key: 'Backspace', code: 'Backspace', repeat: true }))).toBeNull();
        expect(resolveKeyAction(press({ key: 'Enter', code: 'Enter', ctrlOrMeta: true, repeat: true }))).toBeNull();
        expect(resolveKeyAction(press({ key: 'ArrowDown', code: 'ArrowDown', repeat: true })))
            .toMatchObject({ action: 'nextCheck' });
        expect(resolveKeyAction(press({ key: 'f', code: 'KeyF', repeat: true })))
            .toMatchObject({ action: 'nextMarker' });
    });
});

/**
 * CENSUS C — reconciliation with `review-keymap.ts` (the transcription module).
 *
 * The two reducers never share a listener (different routes), so "conflict"
 * means a key that would mean two different things to the same teacher. Each
 * one below is asserted rather than described, so a later edit to either map
 * has to face the divergence instead of drifting past it.
 */
describe('census C — reconciliation with the transcription review keymap', () => {
    const t = (over: Parameters<typeof resolveTranscriptionKey>[0]) => resolveTranscriptionKey(over);
    const base = { ctrlOrMeta: false, isComposing: false, inEditable: false, modalOpen: false };

    it('AGREES on the RTL arrow convention (ArrowLeft is forward)', () => {
        expect(t({ ...base, key: 'ArrowLeft' })).toBe('next');
        expect(resolveKeyAction(press({ key: 'ArrowLeft', code: 'ArrowLeft' })))
            .toMatchObject({ action: 'nextTest' });
    });

    it('DIVERGES on bare Enter — and the divergence is the safe direction', () => {
        // Transcription approves on a bare Enter. Grade review must not: Space
        // cycles verdicts here, so a hand resting one key over would sign a
        // grade. §5 lists Ctrl/⌘+↵ and only that.
        expect(t({ ...base, key: 'Enter' })).toBe('approve');
        expect(resolveKeyAction(press({ key: 'Enter', code: 'Enter' }))).toBeNull();
    });

    it('AGREES on Ctrl+S after OD-F7 (both save; here it flushes the autosave)', () => {
        expect(t({ ...base, key: 's', ctrlOrMeta: true })).toBe('save');
        expect(resolveKeyAction(press({ key: 's', code: 'KeyS', ctrlOrMeta: true })))
            .toMatchObject({ action: 'save' });
    });

    it('AGREES that composition and modals silence the map', () => {
        expect(t({ ...base, key: 'ArrowLeft', isComposing: true })).toBeNull();
        expect(t({ ...base, key: 'ArrowLeft', modalOpen: true })).toBeNull();
        expect(resolveKeyAction(press({ key: 'ArrowLeft', code: 'ArrowLeft', isComposing: true }))).toBeNull();
        expect(resolveKeyAction(press({ key: 'ArrowLeft', code: 'ArrowLeft', modalOpen: true }))).toBeNull();
    });

    it('AGREES that Ctrl/⌘+Enter approves from inside a text field', () => {
        expect(t({ ...base, key: 'Enter', ctrlOrMeta: true, inEditable: true })).toBe('approve');
        expect(resolveKeyAction(press({ key: 'Enter', code: 'Enter', ctrlOrMeta: true, inEditable: true })))
            .toMatchObject({ action: 'approve' });
    });
});
