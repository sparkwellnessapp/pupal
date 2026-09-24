'use client';

import {
    useCallback, useEffect, useLayoutEffect, useMemo, useReducer, useRef, useState,
} from 'react';

/**
 * A layout effect on the client, a plain effect on the server. React warns
 * that `useLayoutEffect` does nothing during server rendering — true, and
 * harmless here (a window listener has no server half) — but the warning is
 * noise in every SSR render test, so the standard isomorphic alias is used.
 */
const useIsomorphicLayoutEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect;

/**
 * OD-9 — every scroll this surface commands is instant under
 * `prefers-reduced-motion: reduce`. Read at call time, not once: the setting
 * can change under a live session, and a cached answer would outlive it.
 */
function prefersReducedMotion(): boolean {
    return typeof window !== 'undefined'
        && typeof window.matchMedia === 'function'
        && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

import type { NumericPolicy } from '@/lib/pricing';
import {
    buildReviewModel,
    type QuestionText,
    type WireDraft,
} from '@/utils/grade-review-model';
import {
    cycleVerdict, revert, revertTerminalPoints, setCheckPoints, setNote,
    setTerminalPoints, toggleEvidenceDisputed, type Overlay,
} from '@/utils/verdict-cycle';
import {
    resolveHighlight, type HighlightableCheck, type PinTarget,
} from '@/utils/evidence-highlight';
import {
    HOVER_INTENT_MS, initialHighlightState, reduce as reduceHighlight,
    revealScrollTop, rowScrollDelta, type HighlightEvent, type HighlightState,
} from '@/utils/grade-review-highlight-machine';
import { REVIEW_LAYOUT_STACKED } from '@/lib/flags';
import {
    markerCountByScope, nextMarker as nextMarkerAfter, reviewMarkers,
} from '@/utils/review-markers';
import { initialExpandedTerminals } from '@/utils/criterion-disclosure';
import { resolveKeyAction } from '@/utils/grade-review-keymap';
import type { QueueState } from '@/utils/grade-review-cursor';
import { ScopeSection } from './ScopeSection';
import { FeedbackCard } from './FeedbackCard';
import {
    QueueLine, ReviewBottomBar, ReviewTopBar, ScopeNav, VersionBanner, WaitCard,
    type SaveState,
} from './ReviewChrome';
import {
    RV_APPROVE_BLOCKED, RV_FB_SUMMARY_TITLE, RV_KEYS_REST, RV_NO_CHECKS,
    RV_QUOTE_PINNED, RV_QUOTES_PINNED,
} from '@/copy/grade-review';

/**
 * בדיקת ציונים — the review module (R1–R13).
 *
 * The surface owns EPHEMERAL state only: which check has focus, which quote is
 * pinned, what the mouse is over, whether a note box is open. The overlay (her
 * decisions) and everything that has to survive navigation live above it, so
 * this component can be driven straight from a fixture in a test and from the
 * route in production without knowing the difference.
 *
 * ── ONE KEYDOWN LISTENER ─────────────────────────────────────────────────
 * Exactly one window listener, which asks the pure reducer what a key means
 * (`grade-review-keymap.ts`). Letter shortcuts resolve by PHYSICAL key, because
 * every teacher here types Hebrew and `event.key` for F is 'כ'.
 *
 * ── THE REFUSAL ──────────────────────────────────────────────────────────
 * A draft with no checks (a pre-v5 grade) is REFUSED, not rendered. Empty
 * checklists would read as "nothing to check" on a test nobody has checked —
 * a degradation that keeps computing is worse than one that stops (§3.5a).
 */

export interface GradeReviewSurfaceProps {
    draft: WireDraft;
    questions: readonly QuestionText[];
    /** The rubric's subject key (Phase 3a) — answer islands render prose/code by it. */
    subject?: string | null;
    policy: NumericPolicy;
    overlay: Overlay;
    onOverlayChange: (next: Overlay) => void;
    feedbackOverrides: Record<string, string>;
    onFeedbackChange: (target: string, text: string) => void;
    onFeedbackRegenerate: (target: string) => void;
    feedbackBusy?: boolean;
    /** R11 — per target ("summary" or a scope id), Vivi's offered wording. */
    feedbackOffers?: Record<string, string>;
    onAcceptFeedbackOffer?: (target: string) => void;
    onDismissFeedbackOffer?: (target: string) => void;

    studentName: string;
    identityMeta: string;
    approved?: boolean;
    /**
     * An approved test is immutable (LCY-2). Every write affordance goes
     * inert — not merely the approve button — because a single keystroke would
     * otherwise queue a save the server refuses, and a failed save blocks
     * navigation.
     */
    readOnly?: boolean;
    /** One beat of the stamp coming down, right after /approve returns (R12). */
    stampPressed?: boolean;
    /** §2 — regrade / manual_edit / retry, unchanged. */
    revision?: React.ComponentProps<typeof ReviewTopBar>['revision'];
    /** R1 — page 1 of the scan, for the mini thumb. */
    thumbUrl?: string | null;
    /**
     * R13: non-null puts the manual-edit banner up. `version` inside it is the
     * chain position when the feed knows it, else null — the banner then states
     * the fact without a number rather than inventing one.
     */
    versionBanner?: { version: number | null } | null;

    queue: QueueState;
    eta: string | null;
    batchHref: string;
    canPrev: boolean;
    canNext: boolean;
    onPrev: () => void;
    onNext: () => void;
    onOpenPreview: () => void;
    onShowScan: (scopeId: string) => void;
    onRetryScope?: () => void;

    saveState: SaveState;
    approving?: boolean;
    onApprove: () => void;
    /** Ctrl/⌘+S — flush the pending autosave now (OD-F7). */
    onSaveNow: () => void;
    onNotice: (message: string) => void;
    /**
     * A modal is open above the surface (the scan viewer). The keymap goes
     * INERT: with it live, Space behind the viewer cycled the focused verdict
     * and Ctrl+↵ signed and advanced the test she could not see. The keymap
     * already has the input; the surface simply never set it.
     */
    modalOpen?: boolean;
}

export function GradeReviewSurface(props: GradeReviewSurfaceProps) {
    const {
        draft, questions, subject, policy, overlay, onOverlayChange,
        feedbackOverrides, onFeedbackChange, onFeedbackRegenerate, feedbackBusy = false,
        feedbackOffers = {}, onAcceptFeedbackOffer, onDismissFeedbackOffer,
        studentName, identityMeta, approved = false, readOnly = false, versionBanner = null,
        stampPressed = false, revision, thumbUrl = null,
        queue, eta, batchHref, canPrev, canNext, onPrev, onNext, onOpenPreview,
        onShowScan, onRetryScope, saveState, approving = false, onApprove, onSaveNow,
        onNotice, modalOpen = false,
    } = props;

    /**
     * The CARET — the row Space, ⌫, N and Enter act on.
     *
     * Not a highlight source. Every path that moves it dispatches `KEY_NAV` as
     * well, so the selection follows it through one writer (HL-7) and "what is
     * lit" stays `hovered ?? selected` and nothing else (HL-1).
     */
    const [focus, setFocus] = useState<string | null>(null);
    /**
     * WHAT IS LIT, AND WHY — the whole highlight machine, in one reducer.
     *
     * `hasQuotes` rides a ref rather than a dependency so `dispatch` keeps a
     * stable identity across renders: the window listeners below are attached
     * once, and a reducer rebuilt on every model change would re-attach them on
     * every keystroke. The reducer ITSELF stays pure — the injected dep is the
     * seam, which is what makes the table in `grade-review-highlight-machine
     * .test.ts` a test of the real thing.
     */
    const hasQuotesRef = useRef<(target: PinTarget) => boolean>(() => false);
    const [hl, dispatch] = useReducer(
        (state: HighlightState, event: HighlightEvent) =>
            reduceHighlight(state, event, { hasQuotes: hasQuotesRef.current }),
        initialHighlightState,
    );
    const hlRef = useRef(hl);
    hlRef.current = hl;
    const [openNote, setOpenNote] = useState<string | null>(null);
    // [OD-R2] The one open points field, if any — a check row or a criterion.
    // Owned here so Enter on the focused row and a click on a number cannot
    // open two fields at once.
    const [editingPoints, setEditingPoints] = useState<
        { kind: 'check' | 'criterion'; id: string } | null>(null);
    const [editedFeedback, setEdited] = useState<ReadonlySet<string>>(new Set());

    const model = useMemo(() => buildReviewModel({
        draft, overlay, policy, questions, editedFeedback, feedbackOverrides,
    }), [draft, overlay, policy, questions, editedFeedback, feedbackOverrides]);

    /**
     * [OD-R1] Name the blockers and take her to the first one.
     *
     * §11's rule, applied to the grading gate: the affordance stays CLICKABLE
     * and explains itself. A native `disabled` would leave her pressing a dead
     * button with no account of why — which is materially what happened when
     * the only account was «שגיאת שרת (422)».
     */
    const showBlockers = useCallback(() => {
        const { blockers } = model;
        if (blockers.length === 0) return;
        onNotice(RV_APPROVE_BLOCKED(blockers.map((b) => b.message)));
        const anchor = blockers.find((b) => b.scopeId)?.scopeId;
        if (anchor) {
            document.getElementById(`scope-${anchor}`)
                ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }, [model, onNotice]);

    /** Every check, flat, in document order — what ↓/↑ and F walk. */
    const flatChecks = useMemo(
        () => model.scopes.flatMap((s) => s.criteria.flatMap((c) => c.checks)),
        [model],
    );
    const checksById = useMemo(
        () => new Map<string, HighlightableCheck>(
            flatChecks.map((c) => [c.check_id, c])),
        [flatChecks],
    );
    const scopeOf = useMemo(() => {
        const map = new Map<string, string>();
        for (const scope of model.scopes) {
            for (const criterion of scope.criteria) {
                for (const check of criterion.checks) map.set(check.check_id, scope.scopeId);
            }
        }
        return map;
    }, [model]);
    /** Which answer a criterion's union belongs to — what `reveal` scrolls. */
    const scopeOfTerminal = useMemo(() => {
        const map = new Map<string, string>();
        for (const scope of model.scopes) {
            for (const criterion of scope.criteria) map.set(criterion.terminalId, scope.scopeId);
        }
        return map;
    }, [model]);

    /**
     * Which rows can actually light the answer.
     *
     * From `canHighlight` — the client's own verdict against the real answer —
     * and NOT from `quote_status`, which is the server's under its own
     * normalisation and says "yes" for spans this render cannot place. That is
     * the same rule the quote button renders on, so a row that offers no button
     * is inert to the pointer too (OD-12), by construction rather than by two
     * places agreeing.
     */
    const quotable = useMemo(() => {
        const checks = new Set<string>();
        const terminals = new Set<string>();
        for (const check of flatChecks) {
            if (!check.canHighlight) continue;
            checks.add(check.check_id);
            terminals.add(check.terminalId);
        }
        return { checks, terminals };
    }, [flatChecks]);
    hasQuotesRef.current = useCallback((target: PinTarget) => (
        target.kind === 'check'
            ? quotable.checks.has(target.id)
            : quotable.terminals.has(target.id)
    ), [quotable]);

    /** R9: every marker kind, not just the evidence ones. */
    const markers = useMemo(() => reviewMarkers(draft as never), [draft]);
    /** Where F last stopped. Kept as the marker KEY, because two markers can
     *  share an id (see ReviewMarker.key) and walking by id ping-pongs. */
    const [lastMarkerKey, setLastMarkerKey] = useState<string | null>(null);
    /** R3's amber dot — the same count F walks and look_count reports. */
    const markersByScope = useMemo(() => markerCountByScope(markers), [markers]);

    /**
     * [S4] Which criterion breakdowns are open.
     *
     * TWO SOURCES, MERGED — and the split is the whole design:
     *
     *   `openingRef`  the once-per-test state (D1): collapsed, except where a
     *                 marker or her own earlier work says her eyes are needed.
     *   `toggled`     every change she has made since. Hers always wins.
     *
     * The opening state is computed into a REF during the first render that has
     * a renderable model, never recomputed. Its second clause reads the overlay,
     * which changes as she works — recomputed live, a criterion she had just
     * collapsed would spring open again the moment she overrode a check inside
     * it, the UI arguing with the teacher. A ref also means no state write
     * during render and no effect that paints twice.
     *
     * The route remounts per `gradedTestId`, so "once per mount" IS once per
     * test; the ref is re-seeded from scratch for the next student.
     */
    const openingRef = useRef<ReadonlySet<string> | null>(null);
    if (openingRef.current === null && model.renderable) {
        openingRef.current = initialExpandedTerminals(model.scopes, markers);
    }
    const [toggled, setToggled] = useState<ReadonlyMap<string, boolean>>(() => new Map());

    const isCriterionOpen = useCallback((terminalId: string) => {
        const hers = toggled.get(terminalId);
        return hers ?? (openingRef.current?.has(terminalId) ?? false);
    }, [toggled]);

    const toggleCriterion = useCallback((terminalId: string) => {
        setToggled((prev) => {
            const next = new Map(prev);
            next.set(terminalId, !(prev.get(terminalId)
                ?? (openingRef.current?.has(terminalId) ?? false)));
            return next;
        });
    }, []);

    /** Open one, idempotently — what a pin and (S5) the keyboard walk need. */
    const expandCriterion = useCallback((terminalId: string) => {
        setToggled((prev) => (prev.get(terminalId) === true
            ? prev
            : new Map(prev).set(terminalId, true)));
    }, []);

    /**
     * R3 scroll-spy. The nav follows the SCROLL, so she always knows where she
     * is on a page this long — but an explicit focus outranks it, because
     * arrow-walking a checklist must not have the nav argue with the caret.
     */
    const [visibleScopeId, setVisibleScopeId] = useState<string | null>(null);
    useEffect(() => {
        if (typeof IntersectionObserver === 'undefined') return;
        const sections = Array.from(
            document.querySelectorAll<HTMLElement>('[data-scope-id]'));
        if (!sections.length) return;
        const seen = new Map<string, number>();
        const observer = new IntersectionObserver((entries) => {
            for (const entry of entries) {
                const id = (entry.target as HTMLElement).dataset.scopeId;
                if (id) seen.set(id, entry.intersectionRatio);
            }
            // The section occupying most of the viewport wins; ties keep
            // document order, so a slow scroll does not flicker between two.
            let best: string | null = null;
            let bestRatio = 0;
            for (const section of sections) {
                const id = section.dataset.scopeId;
                if (!id) continue;
                const ratio = seen.get(id) ?? 0;
                if (ratio > bestRatio) { bestRatio = ratio; best = id; }
            }
            if (best) setVisibleScopeId(best);
        }, { threshold: [0, 0.25, 0.5, 0.75, 1] });
        sections.forEach((section) => observer.observe(section));
        return () => observer.disconnect();
    }, [model.scopes.length]);

    /** check_id → the criterion that owns it, for S5's auto-expand. */
    const terminalOf = useMemo(() => {
        const map = new Map<string, string>();
        for (const check of flatChecks) map.set(check.check_id, check.terminalId);
        return map;
    }, [flatChecks]);
    /** Every criterion that actually renders a disclosure — what may be expanded. */
    const knownTerminals = useMemo(() => new Set(terminalOf.values()), [terminalOf]);

    /**
     * A check id ONLY IF ITS ROW IS ON SCREEN — else null.
     *
     * `hover` and `focus` are ids, and an id outlives the row it names: she can
     * collapse the very box the caret sits in, and a keyboard collapse unmounts
     * a hovered row without ever firing its mouseleave. Both states then point
     * at something she cannot see. Everything that ACTS on a row — painting its
     * span, cycling its verdict — goes through this, so a hidden row is inert
     * by construction rather than by each caller remembering to check.
     *
     * A pure derivation, deliberately: clearing the state in an effect would
     * paint one frame of the wrong thing first and add a second owner of it.
     */
    const visibleCheck = useCallback((id: string | null): string | null => {
        if (id === null) return null;
        const terminalId = terminalOf.get(id);
        return terminalId !== undefined && isCriterionOpen(terminalId) ? id : null;
    }, [terminalOf, isCriterionOpen]);

    /**
     * The same guard, for a highlight target — and it now covers the SELECTION
     * as well as the hover.
     *
     * A folded row is one she cannot see, and its quote button is not on screen
     * to say what is lit; a mark left burning for it is a highlight with no
     * visible owner, which P4 rates worse than no highlight at all. A CRITERION
     * target needs no guard: its header always renders, open or closed.
     *
     * Returned BY REFERENCE when it passes, because `resolveHighlight` tells
     * "the selection lit this" from "a hover on the selected row" by identity.
     */
    const visibleTarget = useCallback((target: PinTarget | null): PinTarget | null => {
        if (target === null) return null;
        if (target.kind === 'criterion') return target;
        return visibleCheck(target.id) === null ? null : target;
    }, [visibleCheck]);

    /**
     * [S5] A row the walk is about to focus may be behind a fold.
     *
     * Since S4 the checklist is collapsed by default, so ↓/↑ and F can target a
     * check that is not in the DOM yet: the old code queried for it in the same
     * tick as `setFocus`, found nothing, and left the caret nowhere — the next
     * Space would have cycled a verdict on a row she could not see. Opening the
     * box and asking for the scroll are now the SAME commit, and the request is
     * consumed after it (§6.3), by which time the row has painted. That is why
     * the one-shot deferral ref this used to need is gone (OD-A7): the request
     * IS the deferral, and there is one row-scroller instead of two.
     */
    const selectCheck = useCallback((checkId: string) => {
        setFocus(checkId);
        const terminalId = terminalOf.get(checkId);
        if (terminalId) expandCriterion(terminalId);
        dispatch({ type: 'KEY_NAV', target: { kind: 'check', id: checkId } });
    }, [terminalOf, expandCriterion]);

    const stepCheck = useCallback((delta: 1 | -1) => {
        if (!flatChecks.length) return;
        const at = focus ? flatChecks.findIndex((c) => c.check_id === focus) : -1;
        const next = at === -1
            ? (delta === 1 ? 0 : flatChecks.length - 1)
            : Math.min(flatChecks.length - 1, Math.max(0, at + delta));
        const nextId = flatChecks[next].check_id;
        // CLAMPED AT AN END — she is already there. Before the requests existed
        // this was silently free (`setFocus` to the same id commits nothing);
        // now it would bump `seq`, re-scroll the row and re-reveal a pane she
        // may have scrolled by hand. A walk that cannot move must move nothing.
        if (nextId === focus) return;
        selectCheck(nextId);
    }, [flatChecks, focus, selectCheck]);

    const goToNextMarker = useCallback(() => {
        const target = nextMarkerAfter(markers, lastMarkerKey);
        if (!target) return;
        setLastMarkerKey(target.key);
        if (target.kind === 'check') {
            selectCheck(target.id);
            return;
        }
        // A scope-level marker (a failed or unanswered question, a clamped
        // terminal) has no row to focus — take her to the section itself.
        //
        // [S5] Its `id` may still name a TERMINAL (bounds_clamped and
        // closed_world anchor there), so open that criterion on the way: F
        // promises to stop at the thing needing her eyes, and stopping beside
        // a closed box that hides it keeps the letter of that and not the point.
        // Only a REAL terminal, though — a failed/unanswered question anchors
        // on the scope id, and recording that as "expanded" would be junk state.
        setFocus(target.id);
        if (knownTerminals.has(target.id)) {
            expandCriterion(target.id);
            // [F7] A terminal marker names a row that CAN be lit, so it selects
            // like any other — the reducer refuses it on its own if the
            // criterion has no placeable span.
            //
            // AND KEY_NAV'S OWN SCROLL IS THE ONLY ONE HERE. This branch used to
            // ALSO scroll the section to the top, so a smooth page scroll began
            // in the handler and an instant `nearest` scroll landed on top of it
            // one commit later — the second cancels the first and she sees a
            // lurch to a position neither of them meant. One scroller per
            // branch; this one aims at the criterion itself, which is a strictly
            // better answer to «take me to the thing needing my eyes» than the
            // top of its question.
            dispatch({ type: 'KEY_NAV', target: { kind: 'criterion', id: target.id } });
            return;
        }
        // A scope-anchored marker (a failed or unanswered question) names no row
        // at all: it selects nothing — pointing the pane at some other
        // criterion's evidence would be worse than pointing it nowhere (M-8) —
        // and the section itself is the only thing there is to scroll to.
        document.getElementById(`scope-${target.scopeId}`)
            ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, [markers, lastMarkerKey, selectCheck, expandCriterion, knownTerminals]);

    const withFocused = useCallback((fn: (terminalId: string, checkId: string,
        aiVerdict: Parameters<typeof cycleVerdict>[3],
        kind: Parameters<typeof cycleVerdict>[4],
        unverified: boolean) => Overlay) => {
        // A DECIDING action needs a row she can see. Navigation may keep the
        // caret on a folded row (so ↓ resumes from where she was); a verdict
        // may not be changed there.
        const target = visibleCheck(readOnly ? null : focus);
        if (target === null) return;
        const check = flatChecks.find((c) => c.check_id === target);
        if (!check) return;
        onOverlayChange(fn(
            check.terminalId, check.check_id, check.aiVerdict, check.kind, check.unverified));
    }, [readOnly, focus, flatChecks, onOverlayChange, visibleCheck]);

    /**
     * Select a target, or release it when it is already selected.
     *
     * ONE implementation for both kinds. The toast and the bring-into-view are
     * the same promise whichever button was pressed, and a second copy of this
     * for criteria is how the two would drift.
     *
     * @param scopeId the scope whose answer to bring into view. Passed in
     *   rather than looked up, because a criterion has no check id to look it
     *   up BY — and a criterion whose checks are all unhighlightable has no
     *   entry in `scopeOf` at all.
     */
    const toggleTarget = useCallback((
        target: PinTarget, scopeId: string | undefined,
    ) => {
        // The side effects sit OUTSIDE the reducer on purpose: a reducer may be
        // invoked twice (StrictMode does, in dev), and a toast fired twice is a
        // bug that form invites. `hlRef` is read, not closed over, so this is
        // never stale however the callback is memoised.
        const current = hlRef.current.selected;
        const willSelect = !(current && current.kind === target.kind
            && current.id === target.id);
        dispatch({ type: 'EVIDENCE_CLICKED', target });
        // Only a CHECK is a focusable row. A criterion selection leaves the
        // caret where she left it rather than inventing a focus for a header.
        if (target.kind === 'check') setFocus(target.id);
        if (!willSelect) return;

        // The criterion lights several spans; the singular notice would describe
        // one of them and leave her hunting for the rest.
        onNotice(target.kind === 'criterion' ? RV_QUOTES_PINNED : RV_QUOTE_PINNED);

        // BRING THE PANE INTO VIEW — on the CLICK, and only then (OD-A11).
        //
        // At two columns this is a NO-OP by construction: LAY-1 guarantees the
        // pane is on screen whenever a criterion row of its scope is, and
        // `block: 'nearest'` scrolls nothing that is already fully visible. It
        // earns its keep in the one-column band (941–1179 px), where the answer
        // sits above a long checklist and the toast used to be the only evidence
        // that anything had happened.
        //
        // A click is the one unambiguous signal of intent, which is why this
        // lives here and not in `reveal`: deriving it from highlight state made
        // the page jump on HOVER and on keyboard focus, and HL-3 exists to keep
        // that impossible. It targets THIS scope's own pane, never the
        // last-highlighted one.
        if (!scopeId || typeof document === 'undefined') return;
        document.querySelector(`[data-answer-pane="${CSS.escape(scopeId)}"]`)
            ?.scrollIntoView({
                behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'nearest',
            });
    }, [onNotice]);

    const togglePin = useCallback((checkId: string) => {
        toggleTarget({ kind: 'check', id: checkId }, scopeOf.get(checkId));
    }, [toggleTarget, scopeOf]);

    /**
     * REVEAL — scroll ONE pane body to the first span of a target (HL-3).
     *
     * `scrollIntoView` is refused here on principle: it scrolls every scrollable
     * ancestor, the page included, and a hover that moves the page is the exact
     * feedback loop this design exists to close. One element's `scrollTop`, and
     * nothing else.
     *
     * The spans are read from the DOM rather than recomputed, which is why this
     * runs POST-COMMIT: the marks of `displayed` exist only after React has
     * painted the state that made them displayed.
     */
    const reveal = useCallback((target: PinTarget) => {
        if (typeof document === 'undefined') return;
        const scopeId = target.kind === 'check'
            ? scopeOf.get(target.id) : scopeOfTerminal.get(target.id);
        if (!scopeId) return;
        const body = document.querySelector<HTMLElement>(
            `[data-answer-for="${CSS.escape(scopeId)}"]`);
        if (!body) return;
        // OD-13 — every span of the target is lit; the FIRST in DOM order is
        // the one revealed. OD-12 — no spans means nothing to show, and the
        // honest response is to leave the pane exactly where it is.
        const first = body.querySelector<HTMLElement>('mark');
        if (!first) return;
        // `clientTop` is the border width: `clientHeight`, `scrollHeight` and
        // `scrollTop` are all measured from the PADDING box, so the span's
        // offset has to be measured from there too.
        const bodyTop = body.getBoundingClientRect().top + body.clientTop;
        const markBox = first.getBoundingClientRect();
        const top = revealScrollTop({
            spanTop: markBox.top - bodyTop + body.scrollTop,
            spanBottom: markBox.bottom - bodyTop + body.scrollTop,
            scrollTop: body.scrollTop,
            clientHeight: body.clientHeight,
            scrollHeight: body.scrollHeight,
        });
        if (top === null) return;                 // already comfortably in view
        body.scrollTo({ top, behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
    }, [scopeOf, scopeOfTerminal]);

    /**
     * The ONLY code here that may move the page, and it is unreachable from
     * hover (HL-6: reversions never scroll, and no hover event issues this).
     *
     * `nearest` semantics plus the `gr-row-scroll` margins — which subtract the
     * top bar, the card's strip and the action bar — is "scroll it only when it
     * is not already there". Computed by hand: see `rowScrollDelta` for why the
     * browser's own `block: 'nearest'` cannot be trusted with the margins.
     * Instant, not smooth: arrow-walking a checklist through a 300 ms animation
     * per row is how a keyboard surface starts to feel broken.
     */
    const bringRowIntoView = useCallback((target: PinTarget) => {
        if (typeof document === 'undefined') return;
        // The criterion's HEADER, not its box: a box with a dozen checks plus
        // the two bar margins is taller than the viewport, and `nearest` does
        // nothing at all when both of an element's edges fall outside it.
        const selector = target.kind === 'check'
            ? `[data-check-id="${CSS.escape(target.id)}"]`
            : `[data-terminal-row="${CSS.escape(target.id)}"]`;
        const row = document.querySelector<HTMLElement>(selector);
        if (!row) return;
        // `nearest` BY HAND (`rowScrollDelta`): the native one ignores the
        // scroll margins whenever the row's own box is inside the window, so a
        // row under the fixed action bar stayed there. The margins are still
        // the `gr-row-scroll` ones — read, not restated.
        const rect = row.getBoundingClientRect();
        const style = getComputedStyle(row);
        const delta = rowScrollDelta({
            top: rect.top,
            bottom: rect.bottom,
            marginTop: parseFloat(style.scrollMarginTop) || 0,
            marginBottom: parseFloat(style.scrollMarginBottom) || 0,
            viewportHeight: window.innerHeight,
        });
        if (delta !== 0) window.scrollBy({ top: delta, behavior: 'auto' });
    }, []);

    // ── the requests, consumed post-commit (§6.3) ──────────────────────────
    // The ROW effect is declared FIRST and therefore runs first, which is what
    // `scrollRowReq.seq < revealReq.seq` records: bring the row into view, then
    // show its evidence.
    useIsomorphicLayoutEffect(() => {
        if (hl.scrollRowReq) bringRowIntoView(hl.scrollRowReq.target);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [hl.scrollRowReq?.seq]);

    useIsomorphicLayoutEffect(() => {
        if (hl.revealReq) reveal(hl.revealReq.target);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [hl.revealReq?.seq]);

    /**
     * HL-5 — the intent delay. `ROW_ENTERED` arms this and nothing else; a
     * pointer sweeping down the list never rests long enough to fire it, so a
     * sweep changes nothing at all.
     *
     * Keyed on the target's IDENTITY, which the reducer keeps stable while she
     * rests (`ROW_ENTERED` returns the same state object for a row already
     * pending), so the timer is started once per row rather than per pixel.
     */
    useEffect(() => {
        const pending = hl.pendingHover;
        if (pending === null) return;
        const timer = setTimeout(
            () => dispatch({ type: 'HOVER_INTENT_FIRED', target: pending }), HOVER_INTENT_MS);
        return () => clearTimeout(timer);
    }, [hl.pendingHover]);

    /**
     * HL-4 — arming, and AM-1's disarm.
     *
     * Both listeners are EDGE-TRIGGERED: `pointermove` fires per pixel and
     * `scroll` per frame, and dispatching on each would run the reducer
     * thousands of times a second for no change.
     *
     * The synthetic-move guard is not paranoia. Browsers dispatch a `pointermove`
     * at the SAME coordinates once a scroll settles, to refresh `:hover` — arming
     * on that would defeat AM-1 silently, and the wheel-with-a-stationary-pointer
     * case would highlight whatever slid beneath her.
     *
     * `pointermove` is attached IN THE CAPTURE PHASE and `scroll` is not, and
     * the asymmetry is load-bearing in both directions:
     *
     *   · React 18 attaches its synthetic handlers to the ROOT CONTAINER, so a
     *     bubbling window listener runs AFTER the row's own handler for the very
     *     same event. Arming there would leave the first move after a page
     *     scroll inert — the row would ask to be hovered while hover was still
     *     disarmed, and nothing would trigger it until the pointer moved again.
     *     Capture puts the arming first, where it belongs.
     *   · `scroll` does NOT bubble, so a non-capture window listener hears only
     *     the page. In capture it would also hear a PANE's own internal scroll —
     *     that is, the reveal a hover just asked for would disarm the hover that
     *     asked for it, once per frame of a smooth scroll.
     */
    useEffect(() => {
        if (typeof window === 'undefined') return;
        let lastX = Number.NaN;
        let lastY = Number.NaN;
        const onPointerMove = (event: PointerEvent) => {
            if (event.clientX === lastX && event.clientY === lastY) return;
            lastX = event.clientX;
            lastY = event.clientY;
            if (hlRef.current.hoverArmed) return;
            dispatch({ type: 'POINTER_MOVED', pointerType: event.pointerType });
        };
        const onScroll = () => {
            const state = hlRef.current;
            if (!state.hoverArmed && state.hovered === null
                && state.pendingHover === null) return;
            dispatch({ type: 'PAGE_SCROLLED' });
        };
        window.addEventListener('pointermove', onPointerMove, { passive: true, capture: true });
        window.addEventListener('scroll', onScroll, { passive: true });
        return () => {
            window.removeEventListener('pointermove', onPointerMove, { capture: true });
            window.removeEventListener('scroll', onScroll);
        };
    }, []);

    /**
     * A different test — a different highlight, and a pane that starts at the
     * top. The route remounts per `gradedTestId`, so this is belt-and-braces
     * rather than the mechanism; it is also what makes `TEST_CHANGED` reachable
     * if the surface is ever driven without a remount.
     */
    useEffect(() => { dispatch({ type: 'TEST_CHANGED' }); }, [draft]);

    /**
     * §5.4 — the two bar heights the sticky chain is built from. The strip's is
     * a constant (see `spacing.strip`); these two are not, so they are measured
     * rather than assumed: a revision menu or a two-line identity moves the top
     * bar, and a wrong number puts the strip under it or leaves a gap.
     */
    const surfaceRef = useRef<HTMLDivElement | null>(null);
    useIsomorphicLayoutEffect(() => {
        // A LAYOUT effect, for the same reason the keydown listener below is
        // one: a passive effect runs after PAINT, so the first frame would be
        // laid out against the stylesheet's defaults and then jump — with the
        // strip sitting UNDER the top bar for that frame whenever the real bar
        // is taller. Reading layout is exactly what this effect is for.
        if (typeof window === 'undefined') return;
        const root = surfaceRef.current;
        if (!root) return;
        // Scoped to THIS surface: both bars are its own children, and a global
        // query would happily measure someone else's.
        const bars = [
            ['[data-review-topbar]', '--gr-topbar-h'],
            ['[data-review-actionbar]', '--gr-actionbar-h'],
        ] as const;
        const measure = () => {
            for (const [selector, prop] of bars) {
                const height = root.querySelector<HTMLElement>(selector)?.offsetHeight ?? 0;
                // ZERO IS NOT A MEASUREMENT. Below `desk` the whole module is
                // `display: none` (N6's honest mobile interstitial), so every
                // bar measures 0 — and writing that would collapse the sticky
                // chain to nothing, to be repaired only if a resize happened to
                // follow. An unmeasurable bar keeps the stylesheet's default.
                if (height > 0) root.style.setProperty(prop, `${Math.round(height)}px`);
            }
        };
        measure();
        if (typeof ResizeObserver === 'undefined') return;
        // `border-box`, because `offsetHeight` IS a border-box measurement: a
        // content-box observer would sleep through a border or padding change.
        const observer = new ResizeObserver(measure);
        for (const [selector] of bars) {
            const el = root.querySelector<HTMLElement>(selector);
            if (el) observer.observe(el, { box: 'border-box' });
        }
        return () => observer.disconnect();
    }, [model.renderable]);

    // ── the single keydown listener ────────────────────────────────────────
    // `useLayoutEffect`, NOT `useEffect`: a passive effect attaches after PAINT,
    // so a key pressed in the gap between the checklist appearing and the effect
    // flushing hit no listener and was silently dropped. Measured under
    // repetition (≈1 in 6 runs the first ↓ after load did nothing). A layout
    // effect attaches before paint; nothing here reads layout, so it costs
    // nothing. On the server it degrades to a plain effect (see the alias).
    useIsomorphicLayoutEffect(() => {
        const onKeyDown = (event: KeyboardEvent) => {
            const target = event.target as HTMLElement | null;
            const inEditable = Boolean(target && (
                target.tagName === 'INPUT' || target.tagName === 'TEXTAREA'
                || target.isContentEditable));
            /**
             * Space and Enter belong to whatever control has focus.
             *
             * The surface swallows Space to cycle a verdict, but a focused
             * BUTTON already uses Space to activate — so tabbing to the quote
             * button and pressing Space silently changed a grade instead of
             * pinning a quote. The browser's own activation is the correct
             * behaviour here; the global map stands down.
             */
            const onControl = Boolean(target && (
                target.tagName === 'BUTTON' || target.tagName === 'SELECT'
                || target.tagName === 'A' || target.getAttribute('role') === 'button'));
            if (onControl && !event.ctrlKey && !event.metaKey
                && (event.code === 'Space' || event.key === ' ' || event.key === 'Enter')) {
                return;
            }
            const resolution = resolveKeyAction({
                key: event.key,
                code: event.code,
                ctrlOrMeta: event.ctrlKey || event.metaKey,
                isComposing: event.isComposing,
                repeat: event.repeat,
                inEditable,
                modalOpen,
            });
            if (!resolution) return;

            // Ctrl+Enter must obey exactly what the button obeys. The listener
            // is registered before the `renderable` early return, so without
            // this a REFUSED draft could still be signed from the keyboard —
            // approving a test the surface declined to show her. [OD-R1] the
            // blockers ride the same guard, or the shortcut walks straight into
            // the 422 the button now prevents.
            if (resolution.action === 'approve'
                && (approved || !model.renderable || model.blockers.length > 0)) {
                if (model.blockers.length > 0) showBlockers();
                return;
            }

            if (resolution.preventDefault) event.preventDefault();

            switch (resolution.action) {
                case 'nextCheck': stepCheck(1); break;
                case 'prevCheck': stepCheck(-1); break;
                case 'nextTest': if (canNext) onNext(); break;
                case 'prevTest': if (canPrev) onPrev(); break;
                case 'cycleVerdict':
                    withFocused((t, c, ai, kind, unverified) =>
                        cycleVerdict(overlay, t, c, ai, kind, undefined, unverified));
                    break;
                case 'revert':
                    withFocused((t, c) => revert(overlay, t, c));
                    break;
                case 'nextMarker': goToNextMarker(); break;
                case 'note': if (!readOnly && focus) setOpenNote(focus); break;
                case 'disputeEvidence':
                    withFocused((t, c, ai) => toggleEvidenceDisputed(overlay, t, c, ai));
                    break;
                case 'approve': onApprove(); break;
                case 'save': onSaveNow(); break;
                case 'editPoints': {
                    // [OD-R2] Enter types the points on the row she can SEE —
                    // the same visibility rule a verdict obeys.
                    const row = visibleCheck(readOnly ? null : focus);
                    if (row !== null) setEditingPoints({ kind: 'check', id: row });
                    break;
                }
                case 'release': {
                    // Esc lets go of the selection the same way a second press
                    // of its own button does — one release path, so the two
                    // cannot disagree about what "released" means.
                    const selected = hlRef.current.selected;
                    if (selected) dispatch({ type: 'EVIDENCE_CLICKED', target: selected });
                    setOpenNote(null);
                    setEditingPoints(null);
                    if (inEditable) target?.blur();
                    break;
                }
                default: break;
            }
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [overlay, focus, canNext, canPrev, onNext, onPrev, onApprove, onSaveNow,
        stepCheck, goToNextMarker, withFocused, visibleCheck, approved, readOnly,
        model.renderable, model.blockers.length, showBlockers, modalOpen]);

    if (!model.renderable) {
        return (
            <p
                data-no-checks
                className="rounded-grade border border-grade-amber-200 bg-grade-amber-50
                    px-6 py-5 text-gr-body text-grade-amber-ink"
            >
                {RV_NO_CHECKS}
            </p>
        );
    }

    // Focus outranks the scroll position; the spy answers when she is reading
    // rather than keyboarding.
    const activeScopeId = (focus ? scopeOf.get(focus) : null) ?? visibleScopeId;

    return (
        <div
            ref={surfaceRef}
            // `gr-review` carries the sticky chain's custom properties; the
            // attribute is M-10's kill switch, and the ONLY thing that can hold
            // the scope cards at one column above the breakpoint.
            className="gr-review pb-24"
            data-review-layout={REVIEW_LAYOUT_STACKED ? 'stacked' : undefined}
        >
            <ReviewTopBar
                studentName={studentName}
                meta={identityMeta}
                total={model.total}
                possible={model.possible}
                anyOverride={model.anyOverride}
                approved={approved}
                canPrev={canPrev}
                canNext={canNext}
                onPrev={onPrev}
                onNext={onNext}
                onOpenPreview={onOpenPreview}
                batchHref={batchHref}
                stampPressed={stampPressed}
                revision={revision}
                thumbUrl={thumbUrl}
            />
            <QueueLine queue={queue} eta={eta} />

            {versionBanner ? <VersionBanner version={versionBanner.version} /> : null}

            <div className="mt-4 grid items-start gap-6 rail:grid-cols-[190px_1fr]">
                <ScopeNav
                    scopes={model.scopes}
                    markersByScope={markersByScope}
                    activeScopeId={activeScopeId}
                    onJump={(scopeId) => {
                        document.getElementById(`scope-${scopeId}`)
                            ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }}
                />

                <div>
                    {model.scopes.map((scope) => {
                        const scopeCheckIds = new Set(
                            scope.criteria.flatMap((c) => c.checks.map((k) => k.check_id)));
                        return (
                            <ScopeSection
                                key={scope.scopeId}
                                scope={scope}
                                // HL-1 — ONE derived value decides what is lit,
                                // here and on every other card. A folded row
                                // paints nothing whichever slot named it (P4):
                                // its quote button is not on screen to say what
                                // the mark belongs to.
                                highlight={resolveHighlight(
                                    {
                                        hover: visibleTarget(hl.hovered),
                                        selected: visibleTarget(hl.selected),
                                    },
                                    checksById, scopeCheckIds)}
                                focusedCheckId={focus}
                                pinnedCheckId={hl.selected?.kind === 'check'
                                    ? hl.selected.id : null}
                                pinnedTerminalId={hl.selected?.kind === 'criterion'
                                    ? hl.selected.id : null}
                                // The scope is in closure, so no terminal→scope
                                // index is needed to tell toggleTarget where to
                                // scroll — the section knows which answer is its own.
                                onPinCriterion={(terminalId) => {
                                    // She asked to see this criterion's evidence;
                                    // opening it is part of answering that.
                                    expandCriterion(terminalId);
                                    toggleTarget({ kind: 'criterion', id: terminalId },
                                        scope.scopeId);
                                }}
                                isCriterionOpen={isCriterionOpen}
                                onToggleCriterion={toggleCriterion}
                                policy={policy}
                                readOnly={readOnly}
                                editingPoints={editingPoints}
                                onEditPoints={setEditingPoints}
                                onCheckPointsCommit={(t, c, amount) => {
                                    if (readOnly) return;
                                    const found = flatChecks.find((k) => k.check_id === c);
                                    if (!found) return;
                                    // `outOf` IS the row's ceiling (`points`); a
                                    // tariff row never reaches here — it has no field.
                                    if (found.kind === 'tariff') return;
                                    onOverlayChange(setCheckPoints(
                                        overlay, t, c, amount, found.outOf, found.aiVerdict));
                                    setFocus(c);
                                }}
                                onCriterionPointsCommit={(t, amount) => {
                                    if (readOnly) return;
                                    onOverlayChange(setTerminalPoints(overlay, t, amount,
                                        (id) => flatChecks.find((k) => k.check_id === id)
                                            ?.aiVerdict ?? 'met'));
                                }}
                                onCriterionPointsRevert={(t) => {
                                    if (!readOnly) onOverlayChange(revertTerminalPoints(overlay, t));
                                }}
                                openNoteCheckId={openNote}
                                feedbackBusy={feedbackBusy}
                                feedbackEdited={editedFeedback.has(scope.scopeId)}
                                subject={subject}
                                onFocusCheck={selectCheck}
                                /*
                                 * EDGE-TRIGGERED at the source. The row fires
                                 * this on every `pointermove` (OD-A6), and the
                                 * reducer would no-op anyway — but dispatching
                                 * per pixel makes React run the reducer
                                 * thousands of times a second for nothing, so
                                 * the current state is consulted first.
                                 */
                                onHoverTarget={(target, hovering) => {
                                    const state = hlRef.current;
                                    if (hovering) {
                                        if ((state.pendingHover?.kind === target.kind
                                            && state.pendingHover.id === target.id)
                                            || (state.hovered?.kind === target.kind
                                                && state.hovered.id === target.id)) return;
                                        dispatch({ type: 'ROW_ENTERED', target });
                                        return;
                                    }
                                    dispatch({ type: 'ROW_LEFT', target });
                                }}
                                onCycle={(t, c) => {
                                    if (readOnly) return;
                                    const found = flatChecks.find((k) => k.check_id === c);
                                    if (found) {
                                        onOverlayChange(cycleVerdict(
                                            overlay, t, c, found.aiVerdict, found.kind,
                                            undefined, found.unverified));
                                    }
                                    setFocus(c);
                                }}
                                onRevert={(t, c) => {
                                    if (!readOnly) onOverlayChange(revert(overlay, t, c));
                                }}
                                onPin={togglePin}
                                onNoteChange={(t, c, note) => {
                                    if (readOnly) return;
                                    const found = flatChecks.find((k) => k.check_id === c);
                                    if (found) {
                                        onOverlayChange(
                                            setNote(overlay, t, c, note, found.aiVerdict));
                                    }
                                    setOpenNote(null);
                                }}
                                onNoteClose={() => setOpenNote(null)}
                                onFeedbackChange={(scopeId, text) => {
                                    if (readOnly) return;
                                    setEdited((s) => new Set(s).add(scopeId));
                                    onFeedbackChange(scopeId, text);
                                }}
                                onFeedbackRegenerate={onFeedbackRegenerate}
                                feedbackOffer={feedbackOffers[scope.scopeId] ?? null}
                                onAcceptFeedbackOffer={onAcceptFeedbackOffer}
                                onDismissFeedbackOffer={onDismissFeedbackOffer}
                                onShowScan={onShowScan}
                                onRetry={scope.gradedBy === 'failed' ? onRetryScope : undefined}
                            />
                        );
                    })}

                    <div className="rounded-grade border border-grade-line bg-grade-card
                        px-6 py-4">
                        <FeedbackCard
                            title={RV_FB_SUMMARY_TITLE}
                            text={model.summary.text}
                            state={model.summary.state}
                            teacherEdited={editedFeedback.has('summary')}
                            busy={feedbackBusy}
                            onChange={(text) => {
                                if (readOnly) return;
                                setEdited((s) => new Set(s).add('summary'));
                                onFeedbackChange('summary', text);
                            }}
                            onRegenerate={() => onFeedbackRegenerate('summary')}
                            offered={feedbackOffers.summary ?? null}
                            onAcceptOffer={() => onAcceptFeedbackOffer?.('summary')}
                            onDismissOffer={() => onDismissFeedbackOffer?.('summary')}
                        />
                    </div>

                    {queue.exhausted ? (
                        <div className="mt-4">
                            <WaitCard
                                gradingCount={queue.grading.length}
                                eta={eta}
                                batchHref={batchHref}
                            />
                        </div>
                    ) : null}
                </div>
            </div>

            <ReviewBottomBar
                saveState={saveState}
                approving={approving}
                canApprove={!approved}
                blocked={model.blockers.length > 0}
                onBlocked={showBlockers}
                onApprove={onApprove}
                onShowKeys={() => onNotice(RV_KEYS_REST)}
            />
        </div>
    );
}
