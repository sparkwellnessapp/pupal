import { activeTarget, type PinTarget } from './evidence-highlight';

/**
 * WHICH EVIDENCE IS SHOWING, AND WHAT MADE IT SHOW — one pure reducer.
 *
 * The side-by-side review layout puts a scope's answer beside its own criteria,
 * so the teacher can read a criterion and its quotation without the page
 * moving. That promise is a STATE problem before it is a CSS one: a highlight
 * that follows the mouse, a pane that scrolls to the span, and a page that does
 * neither. Everything here exists to keep those three apart.
 *
 * ── THE LOOP THIS CLOSES ──────────────────────────────────────────────────
 * Hover reveals a quote → something scrolls → a different row slides under the
 * pointer → hover fires again. Three rules, together, make it unreachable:
 *
 *   HL-3  a reveal writes ONE pane body's `scrollTop`. Never the page.
 *   HL-5  `ROW_ENTERED` highlights nothing by itself. Only `HOVER_INTENT_FIRED`
 *         does, 150 ms after the pointer came to rest on that same row.
 *   HL-4  hover is ARMED only by a real pointer move and DISARMED by any page
 *         scroll (AM-1) — so rows sliding under a stationary pointer are inert.
 *
 * ── TWO STATES, NOT THREE (OD-7, OD-A4) ───────────────────────────────────
 *     displayed = hovered ?? selected
 *
 * `hovered` is transient — what her mouse is doing right now. `selected` is
 * persistent — the evidence button she pressed, or the row the keyboard walked
 * to. Leaving a row reverts to `selected`, never to nothing (M-1), and no hover
 * event ever writes `selected` (HL-2).
 *
 * The surface's `focus` — the CARET that Space, ⌫ and Enter act on — is
 * deliberately NOT a third source here. Every path that moves the caret
 * dispatches `KEY_NAV` as well, so the caret and the selection move together
 * for check rows and there is exactly one writer of each (HL-7).
 *
 * ── REQUESTS ARE THE ONLY SIDE EFFECT ─────────────────────────────────────
 * A reducer cannot scroll anything: the spans of `displayed` exist in the DOM
 * only after React has committed the state that made them displayed. So the
 * reducer EMITS a request carrying a monotonic `seq` (a repeat of the same
 * target still runs), and the component consumes it post-commit. Only the three
 * INTENT events emit one (HL-6) — a reversion changes the highlight and scrolls
 * nothing, which is what keeps a sweeping pointer calm.
 *
 * ── A NO-OP RETURNS THE SAME OBJECT ───────────────────────────────────────
 * React bails out on an identical reference. A fresh copy on every `pointermove`
 * would re-render the whole checklist for no change at all, which is the render
 * cost §6.5 forbids. Every guard below returns `state` itself, on purpose.
 */

/** OD-9 — the rest the pointer must make before anything happens. */
export const HOVER_INTENT_MS = 150;

/**
 * How close to the pane's edge a span may sit and still count as "in view"
 * (§6.4). One rendered line: enough that consecutive quotes which are all
 * already on screen do not make the pane fidget (M-2).
 */
export const REVEAL_MARGIN_PX = 24;

/** OD-9 — the span lands this far down the pane, so its surroundings show. */
const REVEAL_FRACTION = 3;

/**
 * A request to the DOM, consumed post-commit.
 *
 * `seq` is monotonic rather than a boolean so that asking for the SAME target
 * twice still runs: she may click the evidence button, scroll the pane by hand,
 * and click it again.
 */
export interface HighlightRequest {
    readonly target: PinTarget;
    readonly seq: number;
}

export interface HighlightState {
    /** Persistent: an evidence button, or wherever the keyboard walked to. */
    readonly selected: PinTarget | null;
    /** Transient: the row the pointer has rested on. */
    readonly hovered: PinTarget | null;
    /** The row the pointer is resting on; the 150 ms timer is keyed to it. */
    readonly pendingHover: PinTarget | null;
    /** True after a real pointer move; false after any page scroll (AM-1). */
    readonly hoverArmed: boolean;
    /** "Scroll the owning pane to this target's first quote." */
    readonly revealReq: HighlightRequest | null;
    /** "Scroll the page so this target's row is in view." */
    readonly scrollRowReq: HighlightRequest | null;
    readonly seq: number;
}

export const initialHighlightState: HighlightState = Object.freeze({
    selected: null,
    hovered: null,
    pendingHover: null,
    hoverArmed: false,
    revealReq: null,
    scrollRowReq: null,
    seq: 0,
});

export type HighlightEvent =
    /** `pointerType` is carried so the TOUCH refusal is testable as a transition. */
    | { readonly type: 'POINTER_MOVED'; readonly pointerType?: string }
    | { readonly type: 'PAGE_SCROLLED' }
    | { readonly type: 'ROW_ENTERED'; readonly target: PinTarget }
    | { readonly type: 'ROW_LEFT'; readonly target: PinTarget }
    | { readonly type: 'HOVER_INTENT_FIRED'; readonly target: PinTarget }
    | { readonly type: 'EVIDENCE_CLICKED'; readonly target: PinTarget }
    | { readonly type: 'KEY_NAV'; readonly target: PinTarget }
    | { readonly type: 'TEST_CHANGED' };

export interface HighlightDeps {
    /**
     * Does this row have at least one span that will actually be painted?
     *
     * Injected rather than derived, so the reducer stays pure and table-driven.
     * The surface answers it from `ReviewCheck.canHighlight` — the client's own
     * verdict against the real answer, not the server's `quote_status`, because
     * a row whose quote cannot be placed renders no button and must not react
     * to the pointer either (OD-12).
     */
    readonly hasQuotes: (target: PinTarget) => boolean;
}

/** Same row? Targets are compared by value; they arrive from render closures. */
function same(left: PinTarget | null, right: PinTarget | null): boolean {
    return left !== null && right !== null
        && left.kind === right.kind && left.id === right.id;
}

/**
 * `hovered ?? selected` — the ONE value that decides what is lit (HL-1).
 *
 * DELEGATED, not restated. `activeTarget` is where the precedence lives, and it
 * is what the renderer actually consults (through `resolveHighlight`, which adds
 * the per-answer scoping). A second `??` here would be a second place for the
 * rule to be edited, which is the whole thing HL-1 forbids — so this is the
 * machine's STATE in the resolver's vocabulary, and nothing more.
 */
export function displayedTarget(state: HighlightState): PinTarget | null {
    return activeTarget({ hover: state.hovered, selected: state.selected });
}

export function reduce(
    state: HighlightState, event: HighlightEvent, deps: HighlightDeps,
): HighlightState {
    switch (event.type) {
        case 'POINTER_MOVED': {
            // A finger is not a pointer that can hover: a tap would otherwise
            // arm it and the first row touched would light on a 150 ms rest.
            if (event.pointerType === 'touch') return state;
            if (state.hoverArmed) return state;             // edge-triggered
            return { ...state, hoverArmed: true };
        }

        case 'PAGE_SCROLLED': {
            if (!state.hoverArmed && state.hovered === null
                && state.pendingHover === null) return state;
            return { ...state, hoverArmed: false, hovered: null, pendingHover: null };
        }

        case 'ROW_ENTERED': {
            if (!state.hoverArmed) return state;
            if (!deps.hasQuotes(event.target)) return state;
            // Already resting here, or already showing this row: re-arming the
            // timer would re-issue the reveal. Rows dispatch this from
            // `pointermove` as well as `pointerenter` (the boundary events fire
            // BEFORE the move that re-arms hover, so enter alone would leave a
            // re-armed pointer with nothing to trigger it), which is what makes
            // the identity load-bearing rather than merely tidy.
            if (same(state.pendingHover, event.target)) return state;
            if (same(state.hovered, event.target)) return state;
            return { ...state, pendingHover: event.target };
        }

        case 'ROW_LEFT': {
            const pendingHover = same(state.pendingHover, event.target)
                ? null : state.pendingHover;
            const hovered = same(state.hovered, event.target) ? null : state.hovered;
            if (pendingHover === state.pendingHover && hovered === state.hovered) return state;
            return { ...state, pendingHover, hovered };
        }

        case 'HOVER_INTENT_FIRED': {
            // A timer that outlived its row (she moved on, or a scroll disarmed
            // hover) must fire into nothing.
            if (!state.hoverArmed || !same(state.pendingHover, event.target)) return state;
            const seq = state.seq + 1;
            return {
                ...state,
                hovered: event.target,
                pendingHover: null,
                revealReq: { target: event.target, seq },
                seq,
            };
        }

        case 'EVIDENCE_CLICKED': {
            // A TOGGLE, as `aria-pressed` on the button announces and as Esc
            // describes. Releasing is a reversion: it changes what is lit and
            // scrolls nothing (HL-6).
            //
            // The release is tested FIRST, before `hasQuotes`: letting go of
            // what is already lit cannot depend on whether it still has a
            // placeable span, or Esc would silently stop working on a row whose
            // answer had changed under it.
            if (same(state.selected, event.target)) {
                return { ...state, selected: null, hovered: null, pendingHover: null };
            }
            if (!deps.hasQuotes(event.target)) return state;
            const seq = state.seq + 1;
            return {
                ...state,
                selected: event.target,
                hovered: null,
                pendingHover: null,
                revealReq: { target: event.target, seq },
                seq,
            };
        }

        case 'KEY_NAV': {
            // The row is brought into view FIRST and the pane revealed second,
            // so the two effects cannot race: `seq` says which is which.
            const rowSeq = state.seq + 1;
            const quoted = deps.hasQuotes(event.target);
            const revealSeq = rowSeq + 1;
            return {
                ...state,
                selected: event.target,
                hovered: null,
                pendingHover: null,
                // Keyboard navigation moves the page; AM-1 disarms hover on any
                // page scroll, and saying so here means the rule does not
                // depend on the scroll listener winning a race with the caret.
                hoverArmed: false,
                scrollRowReq: { target: event.target, seq: rowSeq },
                // M-8: a row with no quote clears the highlight (`displayed` is
                // it, and it has no spans) and reveals nothing. Pointing the
                // pane at some OTHER criterion's evidence would be worse than
                // pointing it nowhere.
                revealReq: quoted ? { target: event.target, seq: revealSeq } : state.revealReq,
                seq: quoted ? revealSeq : rowSeq,
            };
        }

        case 'TEST_CHANGED':
            return initialHighlightState;

        default:
            return state;
    }
}

export interface RevealGeometry {
    /** The span's offsets within the pane body's SCROLL CONTENT, not the viewport. */
    readonly spanTop: number;
    readonly spanBottom: number;
    readonly scrollTop: number;
    readonly clientHeight: number;
    readonly scrollHeight: number;
    readonly margin?: number;
}

/**
 * Where the pane body should scroll to put a span in view, or `null` for
 * "leave it alone" (M-2).
 *
 * Pure, and tested as such: this is the only arithmetic in the reveal, and
 * getting it wrong is how a pane ends up jittering a few pixels on every row.
 */
export function revealScrollTop(geometry: RevealGeometry): number | null {
    const {
        spanTop, spanBottom, scrollTop, clientHeight, scrollHeight,
        margin = REVEAL_MARGIN_PX,
    } = geometry;

    const visibleTop = scrollTop + margin;
    const visibleBottom = scrollTop + clientHeight - margin;
    if (spanTop >= visibleTop && spanBottom <= visibleBottom) return null;

    const maxScroll = Math.max(0, scrollHeight - clientHeight);
    const wanted = spanTop - clientHeight / REVEAL_FRACTION;
    return Math.min(Math.max(wanted, 0), maxScroll);
}
