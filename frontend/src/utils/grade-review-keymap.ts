/**
 * The grade-review keymap as a PURE reducer (PR spec §5), shaped after
 * `review-keymap.ts` so the two modules read alike. The route owns exactly one
 * window keydown listener and asks this function what a key means.
 *
 * ── THE FINDING THAT SHAPES THIS FILE ──────────────────────────────────────
 * Letter shortcuts resolve from `event.code` (physical position), not
 * `event.key` (produced character). Every teacher using Vivi types Hebrew: on
 * her layout the F key reports `key: 'כ'`, H reports `'י'`, E reports `'ק'`.
 * A `key`-based binding of F/H/E is dead on the only keyboard that matters.
 * `review-keymap.ts` never met this because it binds arrows and Enter only.
 * `key` stays as the fallback for events that carry no `code`.
 *
 * ── CENSUS C, the reconciliation §5 asks for ───────────────────────────────
 * ONE deliberate divergence from the transcription map, asserted in the test
 * file so it cannot drift into an accident: bare `Enter` approves there; here
 * it does NOTHING. Space cycles verdicts on this surface, so a hand resting
 * one key over would sign a grade. §5 lists Ctrl/⌘+↵ and only that.
 *
 * Ctrl/⌘+S was the second divergence and is no longer one. OD-F7, ruled
 * 2026-08-31: bind it. This surface autosaves, so the key has nothing of its
 * own to do — but the habit arrives from the transcription module, and an
 * unbound Ctrl+S hands her the BROWSER's "save this page" dialog, which looks
 * like the app broke. It flushes the pending save and says «נשמר», in a field
 * or out of one.
 *
 * Everything else agrees: ArrowLeft is forward in RTL, composition and open
 * modals silence the map, and Ctrl/⌘+Enter approves from inside a field.
 *
 * ── Two policies that live here rather than at the call site ───────────────
 *   * `preventDefault` is part of the verdict. Space scrolls the page and
 *     Backspace can navigate the browser back; the reducer that claims the key
 *     is the thing that knows it must be swallowed.
 *   * Auto-repeat navigates but never DECIDES. Holding Space would spin
 *     ✗ → ½ → ✓ → ✗ and leave a verdict nobody chose; holding ↓ to travel a
 *     long scope is what key repeat is for.
 */

export type GradeKeyAction =
    | 'nextCheck'
    | 'prevCheck'
    | 'nextTest'
    | 'prevTest'
    | 'cycleVerdict'
    | 'revert'
    | 'nextMarker'
    | 'note'
    | 'disputeEvidence'
    | 'approve'
    | 'save'
    | 'release';

export interface GradeKeyInput {
    /** `event.key` — the produced character (layout-dependent). */
    key: string;
    /** `event.code` — the physical key. Authoritative for letters. */
    code: string;
    ctrlOrMeta: boolean;
    isComposing: boolean;
    repeat: boolean;
    inEditable: boolean;
    modalOpen: boolean;
}

export interface GradeKeyResolution {
    action: GradeKeyAction;
    /** The caller must call `event.preventDefault()` when true. */
    preventDefault: boolean;
}

/** Actions that commit something. Never fired by auto-repeat. */
const DECIDING: ReadonlySet<GradeKeyAction> = new Set<GradeKeyAction>(['cycleVerdict', 'revert', 'approve']);
// `save` is deliberately NOT deciding: a held Ctrl+S flushing twice is a
// no-op, and suppressing it would let the browser dialog through on the repeat.

/** Keys the browser would otherwise act on. */
const SWALLOW: ReadonlySet<GradeKeyAction> = new Set<GradeKeyAction>([
    'cycleVerdict', 'revert', 'nextCheck', 'prevCheck', 'approve', 'save',
]);

const LETTERS: Readonly<Record<string, GradeKeyAction>> = {
    KeyF: 'nextMarker',
    KeyH: 'note',
    KeyE: 'disputeEvidence',
};

/** Latin fallback for events that carry no `code`. */
const LETTER_FALLBACK: Readonly<Record<string, GradeKeyAction>> = {
    f: 'nextMarker',
    h: 'note',
    e: 'disputeEvidence',
};

function bare(input: GradeKeyInput): GradeKeyAction | null {
    switch (input.code || input.key) {
        case 'ArrowDown':
            return 'nextCheck';
        case 'ArrowUp':
            return 'prevCheck';
        case 'ArrowLeft':
            return 'nextTest';       // RTL: left is forward
        case 'ArrowRight':
            return 'prevTest';
        case 'Space':
            return 'cycleVerdict';
        case 'Backspace':
            return 'revert';
        default:
            break;
    }
    // Space arrives as key ' ' when `code` is absent.
    if (!input.code && input.key === ' ') return 'cycleVerdict';
    return LETTERS[input.code] ?? LETTER_FALLBACK[input.key?.toLowerCase()] ?? null;
}

export function resolveKeyAction(input: GradeKeyInput): GradeKeyResolution | null {
    if (input.isComposing || input.modalOpen) return null;

    const approving = input.ctrlOrMeta && (input.code === 'Enter' || input.key === 'Enter');
    // By POSITION, like the letter bindings: on a Hebrew layout the S key
    // reports 'ס'. `key` is the fallback for events that carry no `code`.
    const saving = input.ctrlOrMeta
        && (input.code === 'KeyS' || (!input.code && input.key?.toLowerCase() === 's'));
    const escaping = input.code === 'Escape' || input.key === 'Escape';

    let action: GradeKeyAction | null;
    if (approving) {
        action = 'approve';
    } else if (saving) {
        action = 'save';
    } else if (escaping) {
        action = 'release';
    } else if (input.inEditable || input.ctrlOrMeta) {
        // Inside a field only approve and escape survive; and a modified key is
        // a browser or OS shortcut this surface has no claim on.
        action = null;
    } else {
        action = bare(input);
    }

    if (action === null) return null;
    if (input.repeat && DECIDING.has(action)) return null;
    return { action, preventDefault: SWALLOW.has(action) };
}
