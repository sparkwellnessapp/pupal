import { describe, expect, it } from 'vitest';

import {
    HOVER_INTENT_MS,
    REVEAL_MARGIN_PX,
    initialHighlightState,
    displayedTarget,
    reduce,
    revealScrollTop,
    type HighlightEvent,
    type HighlightState,
} from './grade-review-highlight-machine';
import type { PinTarget } from './evidence-highlight';

/**
 * The side-by-side PR's pure half (spec §8.1, §8.2) — zero mocks.
 *
 * Two things are proven here and nowhere else:
 *
 *  1. A no-op transition returns THE SAME STATE OBJECT. React bails out on an
 *     identical reference; a fresh copy would re-render the whole checklist on
 *     every pixel the pointer crosses, which is the render cost §6.5 forbids.
 *  2. `seq` is strictly increasing and only intent events bump it (HL-6). The
 *     requests are the reducer's ONLY way to cause a side effect, so a
 *     reversion that bumped `seq` would scroll a pane behind her back.
 */

const a: PinTarget = { kind: 'check', id: 'a' };
const b: PinTarget = { kind: 'check', id: 'b' };
/** No quote — hover is inert on it and it can never issue a reveal (OD-12). */
const c: PinTarget = { kind: 'check', id: 'c' };
/** A criterion header: its quote is the union of its checks' (OD-A5). */
const crit: PinTarget = { kind: 'criterion', id: 'crit' };

const DEPS = { hasQuotes: (t: PinTarget) => t.id !== 'c' };

/** Run a script from the initial state and hand back the final state. */
function run(...events: HighlightEvent[]): HighlightState {
    return events.reduce((s, e) => reduce(s, e, DEPS), initialHighlightState);
}

const moved: HighlightEvent = { type: 'POINTER_MOVED', pointerType: 'mouse' };
const entered = (target: PinTarget): HighlightEvent => ({ type: 'ROW_ENTERED', target });
const left = (target: PinTarget): HighlightEvent => ({ type: 'ROW_LEFT', target });
const intent = (target: PinTarget): HighlightEvent => ({ type: 'HOVER_INTENT_FIRED', target });
const clicked = (target: PinTarget): HighlightEvent => ({ type: 'EVIDENCE_CLICKED', target });
const keyNav = (target: PinTarget): HighlightEvent => ({ type: 'KEY_NAV', target });

describe('the highlight machine [§8.1]', () => {
    it('T1 — a sweep across two rows without resting changes nothing', () => {
        const state = run(moved, entered(a), left(a), entered(b), left(b));
        expect(state.hovered).toBeNull();
        expect(state.pendingHover).toBeNull();
        expect(state.revealReq).toBeNull();
        expect(state.scrollRowReq).toBeNull();
        expect(state.seq).toBe(0);
    });

    it('T2 — resting on a row for the intent delay highlights it and reveals its quote', () => {
        const state = run(moved, entered(a), intent(a));
        expect(state.hovered).toEqual(a);
        expect(state.pendingHover).toBeNull();
        expect(state.revealReq?.target).toEqual(a);
    });

    it('T3 — leaving reverts to the selected criterion and scrolls nothing', () => {
        const hovering = run(moved, entered(a), intent(a));
        const state = reduce(hovering, left(a), DEPS);
        expect(state.hovered).toBeNull();
        expect(state.seq).toBe(hovering.seq);                 // HL-6: no request
        expect(displayedTarget(state)).toBe(state.selected);
    });

    it('T4 — a stale timer is a no-op, and returns the same state object', () => {
        const before = run(moved, entered(a), left(a));
        expect(reduce(before, intent(a), DEPS)).toBe(before);
    });

    it('T5 — ROW_ENTERED while hover is disarmed does nothing at all', () => {
        const before = initialHighlightState;
        expect(reduce(before, entered(a), DEPS)).toBe(before);
        expect(reduce(before, entered(a), DEPS).pendingHover).toBeNull();
    });

    it('T6 — a page scroll disarms hover and drops what it was showing (AM-1)', () => {
        const state = run(moved, { type: 'PAGE_SCROLLED' }, entered(a));
        expect(state.hoverArmed).toBe(false);
        expect(state.pendingHover).toBeNull();
        expect(state.hovered).toBeNull();
    });

    it('T7 — a real pointer move re-arms it', () => {
        const state = run(
            moved, { type: 'PAGE_SCROLLED' }, entered(a),
            moved, entered(a), intent(a),
        );
        expect(state.hovered).toEqual(a);
    });

    it('T8 — a click on the evidence button takes over from the hover', () => {
        const hovering = run(moved, entered(a), intent(a));
        const state = reduce(hovering, clicked(a), DEPS);
        expect(state.selected).toEqual(a);
        expect(state.hovered).toBeNull();
        expect(state.revealReq?.target).toEqual(a);
        expect(state.seq).toBe(2);                            // one per intent event
        expect(state.revealReq!.seq).toBeGreaterThan(hovering.revealReq!.seq);
    });

    it('T9 — no hover event ever writes `selected` (HL-2)', () => {
        const state = run(moved, entered(a), intent(a));
        expect(state.selected).toBeNull();
    });

    it('T10 — KEY_NAV selects, brings the row into view, then reveals', () => {
        const state = reduce(initialHighlightState, keyNav(b), DEPS);
        expect(state.selected).toEqual(b);
        expect(state.hovered).toBeNull();
        expect(state.hoverArmed).toBe(false);
        expect(state.scrollRowReq?.target).toEqual(b);
        expect(state.revealReq?.target).toEqual(b);
        // The row effect is declared first and must run first (§6.3).
        expect(state.scrollRowReq!.seq).toBeLessThan(state.revealReq!.seq);
    });

    it('T11 — KEY_NAV onto a row with no quote scrolls to it and reveals nothing', () => {
        const before = run(moved, entered(a), intent(a));
        const state = reduce(before, keyNav(c), DEPS);
        expect(state.selected).toEqual(c);
        expect(state.scrollRowReq?.target).toEqual(c);
        expect(state.revealReq).toBe(before.revealReq);       // M-8: unchanged
        expect(displayedTarget(state)).toEqual(c);            // …and it has no spans
    });

    it('T12 — hovering a row with no quote never arms the timer (OD-12)', () => {
        const state = run(moved, entered(c));
        expect(state.pendingHover).toBeNull();
    });

    it('T13 — touch never arms hover', () => {
        const state = reduce(
            initialHighlightState, { type: 'POINTER_MOVED', pointerType: 'touch' }, DEPS);
        expect(state.hoverArmed).toBe(false);
        expect(state).toBe(initialHighlightState);
    });

    it('T14 — TEST_CHANGED returns the initial state', () => {
        const busy = run(moved, entered(a), intent(a), clicked(a), keyNav(b));
        expect(reduce(busy, { type: 'TEST_CHANGED' }, DEPS)).toBe(initialHighlightState);
    });

    it('T15 — displayed is `hovered ?? selected`, and reverts on leave', () => {
        const state = run(clicked(b), moved, entered(a), intent(a));
        expect(displayedTarget(state)).toEqual(a);
        expect(displayedTarget(reduce(state, left(a), DEPS))).toEqual(b);
    });

    it('T16 — a click on a row with no quote is a no-op', () => {
        const before = run(moved);
        expect(reduce(before, clicked(c), DEPS)).toBe(before);
    });
});

describe('the machine — this surface\'s own cases [OD-A4..A6]', () => {
    it('a criterion header is a target like any row: it hovers and it selects', () => {
        const hovered = run(moved, entered(crit), intent(crit));
        expect(displayedTarget(hovered)).toEqual(crit);
        const selected = reduce(hovered, clicked(crit), DEPS);
        expect(selected.selected).toEqual(crit);
        expect(selected.hovered).toBeNull();
    });

    it('clicking the lit button again RELEASES it, and scrolls nothing', () => {
        // Today's toggle, which `aria-pressed` and Esc both describe. A release
        // is a reversion, so it issues no request (HL-6).
        const on = reduce(initialHighlightState, clicked(a), DEPS);
        const off = reduce(on, clicked(a), DEPS);
        expect(off.selected).toBeNull();
        expect(off.seq).toBe(on.seq);
        expect(off.revealReq).toBe(on.revealReq);
    });

    it('a criterion selection REPLACES a check selection — one at a time', () => {
        const state = reduce(reduce(initialHighlightState, clicked(a), DEPS), clicked(crit), DEPS);
        expect(state.selected).toEqual(crit);
    });

    it('re-entering the row it is already resting on does not restart the timer', () => {
        // OD-A6: rows dispatch ROW_ENTERED from `pointermove` too, because the
        // boundary events fire BEFORE the move that re-arms hover. Without this
        // identity the timer would restart on every pixel and never fire.
        const resting = run(moved, entered(a));
        expect(reduce(resting, entered(a), DEPS)).toBe(resting);
        const showing = reduce(resting, intent(a), DEPS);
        expect(reduce(showing, entered(a), DEPS)).toBe(showing);
    });

    it('leaving a row that is not the hovered one changes nothing', () => {
        const showing = run(moved, entered(a), intent(a));
        expect(reduce(showing, left(b), DEPS)).toBe(showing);
    });

    it('a page scroll with nothing to drop is a no-op', () => {
        expect(reduce(initialHighlightState, { type: 'PAGE_SCROLLED' }, DEPS))
            .toBe(initialHighlightState);
    });

    it('a pointer move while already armed is a no-op (edge-triggered, §6.5)', () => {
        const armed = run(moved);
        expect(reduce(armed, moved, DEPS)).toBe(armed);
    });

    it('the intent delay is the ruled 150 ms (OD-9)', () => {
        expect(HOVER_INTENT_MS).toBe(150);
    });
});

describe('revealScrollTop [§8.2]', () => {
    const PANE = { scrollTop: 0, clientHeight: 300, scrollHeight: 1200 };

    it('returns null when the span is comfortably visible (M-2)', () => {
        expect(revealScrollTop({ ...PANE, spanTop: 100, spanBottom: 120 })).toBeNull();
    });

    it('lands a span below the fold at the upper third (OD-9)', () => {
        expect(revealScrollTop({ ...PANE, spanTop: 600, spanBottom: 620 }))
            .toBe(600 - 300 / 3);
    });

    it('lands a span above the top at the upper third too', () => {
        expect(revealScrollTop({ ...PANE, scrollTop: 800, spanTop: 400, spanBottom: 420 }))
            .toBe(400 - 300 / 3);
    });

    it('clamps at the end of the content', () => {
        expect(revealScrollTop({ ...PANE, spanTop: 1190, spanBottom: 1200 }))
            .toBe(1200 - 300);
    });

    it('puts a span TALLER than the pane at the upper third, clamped', () => {
        expect(revealScrollTop({ ...PANE, spanTop: 500, spanBottom: 900 }))
            .toBe(500 - 300 / 3);
    });

    it('never returns a negative offset when the content does not scroll', () => {
        const top = revealScrollTop({
            spanTop: 0, spanBottom: 18, scrollTop: 0, clientHeight: 300, scrollHeight: 200,
        });
        expect(top === null || top === 0).toBe(true);
    });

    it('never returns a negative offset for a span near the very top', () => {
        expect(revealScrollTop({ ...PANE, spanTop: 4, spanBottom: 22 })).toBe(0);
    });

    it('treats "one rendered line" from the edge as still visible', () => {
        // The margin is what stops consecutive quotes making the pane fidget.
        expect(revealScrollTop({
            ...PANE, spanTop: REVEAL_MARGIN_PX, spanBottom: 300 - REVEAL_MARGIN_PX,
        })).toBeNull();
        expect(revealScrollTop({
            ...PANE, spanTop: REVEAL_MARGIN_PX - 1, spanBottom: 40,
        })).not.toBeNull();
    });
});
