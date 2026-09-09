'use client';

import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from 'react';

/**
 * A layout effect on the client, a plain effect on the server. React warns
 * that `useLayoutEffect` does nothing during server rendering — true, and
 * harmless here (a window listener has no server half) — but the warning is
 * noise in every SSR render test, so the standard isomorphic alias is used.
 */
const useIsomorphicLayoutEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect;

import type { NumericPolicy } from '@/lib/pricing';
import {
    buildReviewModel,
    type QuestionText,
    type WireDraft,
} from '@/utils/grade-review-model';
import {
    cycleVerdict, revert, setNote, toggleEvidenceDisputed, type OverlayTerminals,
} from '@/utils/verdict-cycle';
import { resolveHighlight, type HighlightableCheck } from '@/utils/evidence-highlight';
import {
    markerCountByScope, nextMarker as nextMarkerAfter, reviewMarkers,
} from '@/utils/review-markers';
import { resolveKeyAction } from '@/utils/grade-review-keymap';
import type { QueueState } from '@/utils/grade-review-cursor';
import { ScopeSection } from './ScopeSection';
import { FeedbackCard } from './FeedbackCard';
import {
    QueueLine, ReviewBottomBar, ReviewTopBar, ScopeNav, VersionBanner, WaitCard,
    type SaveState,
} from './ReviewChrome';
import {
    RV_FB_SUMMARY_TITLE, RV_KEYS_REST, RV_NO_CHECKS, RV_QUOTE_PINNED,
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
    overlay: OverlayTerminals;
    onOverlayChange: (next: OverlayTerminals) => void;
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

    const [focus, setFocus] = useState<string | null>(null);
    const [pin, setPin] = useState<string | null>(null);
    const [hover, setHover] = useState<string | null>(null);
    const [openNote, setOpenNote] = useState<string | null>(null);
    const [editedFeedback, setEdited] = useState<ReadonlySet<string>>(new Set());

    const model = useMemo(() => buildReviewModel({
        draft, overlay, policy, questions, editedFeedback, feedbackOverrides,
    }), [draft, overlay, policy, questions, editedFeedback, feedbackOverrides]);

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

    /** R9: every marker kind, not just the evidence ones. */
    const markers = useMemo(() => reviewMarkers(draft as never), [draft]);
    /** Where F last stopped. Kept as the marker KEY, because two markers can
     *  share an id (see ReviewMarker.key) and walking by id ping-pongs. */
    const [lastMarkerKey, setLastMarkerKey] = useState<string | null>(null);
    /** R3's amber dot — the same count F walks and look_count reports. */
    const markersByScope = useMemo(() => markerCountByScope(markers), [markers]);

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

    const focusCheck = useCallback((checkId: string) => {
        setFocus(checkId);
        // Focus follows the eye: the row scrolls into view only when it is not
        // already there, so arrow-walking a visible list does not jitter.
        const el = typeof document === 'undefined'
            ? null
            : document.querySelector<HTMLElement>(`[data-check-id="${CSS.escape(checkId)}"]`);
        if (el) {
            const rect = el.getBoundingClientRect();
            if (rect.top < 170 || rect.bottom > window.innerHeight - 70) {
                el.scrollIntoView({ block: 'center' });
            }
        }
    }, []);

    const stepCheck = useCallback((delta: 1 | -1) => {
        if (!flatChecks.length) return;
        const at = focus ? flatChecks.findIndex((c) => c.check_id === focus) : -1;
        const next = at === -1
            ? (delta === 1 ? 0 : flatChecks.length - 1)
            : Math.min(flatChecks.length - 1, Math.max(0, at + delta));
        focusCheck(flatChecks[next].check_id);
    }, [flatChecks, focus, focusCheck]);

    const goToNextMarker = useCallback(() => {
        const target = nextMarkerAfter(markers, lastMarkerKey);
        if (!target) return;
        setLastMarkerKey(target.key);
        if (target.kind === 'check') {
            focusCheck(target.id);
            return;
        }
        // A scope-level marker (a failed or unanswered question, a clamped
        // terminal) has no row to focus — take her to the section itself.
        setFocus(target.id);
        document.getElementById(`scope-${target.scopeId}`)
            ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, [markers, lastMarkerKey, focusCheck]);

    const withFocused = useCallback((fn: (terminalId: string, checkId: string,
        aiVerdict: Parameters<typeof cycleVerdict>[3]) => OverlayTerminals) => {
        if (readOnly || !focus) return;
        const check = flatChecks.find((c) => c.check_id === focus);
        if (!check) return;
        onOverlayChange(fn(check.terminalId, check.check_id, check.aiVerdict));
    }, [readOnly, focus, flatChecks, onOverlayChange]);

    const togglePin = useCallback((checkId: string) => {
        // The side effects sit OUTSIDE the state updater on purpose: React may
        // invoke an updater twice (StrictMode does, in dev), and a toast fired
        // twice or a scroll commanded twice is a bug the updater form invites.
        // `pin` is a dependency, so this closure is never stale.
        const willPin = pin !== checkId;
        setPin(willPin ? checkId : null);
        setFocus(checkId);
        if (!willPin) return;

        onNotice(RV_QUOTE_PINNED);

        // BRING THE ANSWER INTO VIEW — on the CLICK, and only then.
        //
        // The quote button sits in the checklist, BELOW the answer it cites, so
        // the answer is usually off-screen above and the toast was the only
        // evidence anything had happened. This lives in the click handler
        // because a click is the one unambiguous signal of intent: deriving it
        // from highlight state made the page jump on HOVER and on keyboard
        // focus, which paint a highlight too. It scrolls to THIS check's own
        // scope, never to the last-highlighted one.
        //
        // `scroll-mt-scope` on the answer keeps it clear of the sticky bar;
        // without it `block: 'start'` lands the answer behind the header.
        const scopeId = scopeOf.get(checkId);
        if (!scopeId || typeof document === 'undefined') return;
        document.querySelector(`[data-answer-for="${CSS.escape(scopeId)}"]`)
            ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, [pin, onNotice, scopeOf]);

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
            // approving a test the surface declined to show her.
            if (resolution.action === 'approve' && (approved || !model.renderable)) return;

            if (resolution.preventDefault) event.preventDefault();

            switch (resolution.action) {
                case 'nextCheck': stepCheck(1); break;
                case 'prevCheck': stepCheck(-1); break;
                case 'nextTest': if (canNext) onNext(); break;
                case 'prevTest': if (canPrev) onPrev(); break;
                case 'cycleVerdict':
                    withFocused((t, c, ai) => cycleVerdict(overlay, t, c, ai));
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
                case 'release':
                    setPin(null);
                    setOpenNote(null);
                    if (inEditable) target?.blur();
                    break;
                default: break;
            }
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [overlay, focus, canNext, canPrev, onNext, onPrev, onApprove, onSaveNow,
        stepCheck, goToNextMarker, withFocused, approved, readOnly, model.renderable,
        modalOpen]);

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
        <div className="pb-24">
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
                                highlight={resolveHighlight(
                                    { hover, pin, focus }, checksById, scopeCheckIds)}
                                highlightTransient={hover !== null}
                                focusedCheckId={focus}
                                pinnedCheckId={pin}
                                openNoteCheckId={openNote}
                                feedbackBusy={feedbackBusy}
                                feedbackEdited={editedFeedback.has(scope.scopeId)}
                                subject={subject}
                                onFocusCheck={focusCheck}
                                onHoverCheck={(id, hovering) =>
                                    setHover(hovering ? id : null)}
                                onCycle={(t, c) => {
                                    if (readOnly) return;
                                    const found = flatChecks.find((k) => k.check_id === c);
                                    if (found) {
                                        onOverlayChange(
                                            cycleVerdict(overlay, t, c, found.aiVerdict));
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
                onApprove={onApprove}
                onShowKeys={() => onNotice(RV_KEYS_REST)}
            />
        </div>
    );
}
