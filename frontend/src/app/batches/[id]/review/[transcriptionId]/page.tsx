'use client';

/**
 * Per-item batch transcription review — the wired shell (Phase 3, rebuilt in
 * P3 as the spec §8 review module).
 *
 * /batches/[id]/review/[transcriptionId]
 *
 * DATA + CURSOR + CACHES LIVE IN THE SEGMENT LAYOUT (BatchReviewProvider):
 * this page component REMOUNTS on every prev/next (the App Router keys page
 * segments by param value — rider-a finding), so everything that must survive
 * navigation (the one batch fetch, the OD2 append-only cursor, the Δ9 page
 * cache, the Δ7 dissolution memory, the R11 soft note) is held by the layout.
 * Per-item editor state lives in ReviewItemController (hydrated per item
 * mount; Δ11-guarded against same-item payload refreshes).
 *
 * P3 behaviors owned here:
 *  - R5 counters: primary `{i} מתוך {F} לעיון` (flagged position — omitted on
 *    clean items) + secondary `מבחן {k} מתוך {T} במקבץ`.
 *  - R3 keyboard: ONE window keydown listener → the pure keymap reducer
 *    (ArrowLeft=הבא in RTL; composition and open modals never act; editables
 *    keep only Ctrl+S / Ctrl+Enter). Main region focused per item mount.
 *  - R1 reason rail: entry-frozen chips (past-tense framing); clicks resolve
 *    anchors against CURRENT text via reasonAnchors — scroll+pulse a card,
 *    focus the student picker, or shake when the target no longer exists.
 *  - R4/R12 advance: accept → advanceTarget over the LATEST cursor snapshot;
 *    flagged walk wraps before declaring the interstitial; clean walk is
 *    forward-only (בדיקה ידנית). Interstitial bulk rides accept_clean; a
 *    skipped>0 result is handed to the dashboard via the one-shot
 *    sessionStorage key (no router state in the App Router).
 *  - R8 guards: EVERY exit flushes (prev/next, the last-item dashboard exit).
 *    Browser Back interception is a LOGGED RESIDUAL — Next 14 App Router
 *    exposes no reliable hook; beforeunload + guarded links stand.
 *  - R11: accept success is never re-reported as failure — a failed refetch
 *    becomes the provider-held soft note.
 *  - D11: below `desk` (941px) the module yields to the honest interstitial.
 */

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Check, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';

import { acceptCleanTranscriptions, acceptOneTranscription } from '@/lib/api';
import { useBatchReview } from '@/components/batch-review/BatchReviewContext';
import { needsUnloadGuard } from '@/components/batch-review/reviewItemController';
import { ConfirmAcceptModal } from '@/components/batch-review/ConfirmAcceptModal';
import { ReviewInterstitialModal } from '@/components/batch-review/ReviewInterstitialModal';
import { TranscriptionReviewSurface } from '@/components/batch-review/TranscriptionReviewSurface';
import { useReviewItemState } from '@/components/batch-review/useReviewItemState';
import {
    flagReasonLabel,
    INTERSTITIAL_BACK,
    MOBILE_REVIEW_INTERSTITIAL,
    POSITION_PRIMARY,
    POSITION_SECONDARY,
    RAIL_LABEL,
    SKIP_NOTICE,
    SKIP_REASON_FRAGMENTS,
    SOFT_REFETCH_NOTE,
} from '@/copy/batch';
import type { BatchDetailResponse, BatchTranscriptionItem } from '@/types/batch';
import {
    advanceTarget,
    counterInfo,
    cursorPosition,
    type CounterInfo,
    type CursorPosition,
    type FrozenCursor,
} from '@/utils/batch-review-cursor';
import { reasonAnchors } from '@/utils/review-anchors';
import { resolveKeyAction } from '@/utils/review-keymap';
import { handOffSkipNotice } from '@/utils/skip-notice';

/** Item statuses from a payload snapshot, with the just-accepted item forced
 *  approved — the refetch may have failed (R11) or not landed. */
function statusMapWith(
    b: BatchDetailResponse | null,
    acceptedId: string,
): Record<string, 'transcribed' | 'approved'> {
    const m: Record<string, 'transcribed' | 'approved'> = {};
    for (const t of b?.transcriptions ?? []) m[t.transcription_id] = t.transcription_status;
    m[acceptedId] = 'approved';
    return m;
}

/** The interstitial's bulk-acceptable subset: unapproved cleans (cursor
 *  partition) with a matched student — the same client rule as the
 *  dashboard's D5 button; server-side skips (touched, re-flagged) surface
 *  via the skip notice. */
function cleanBulkItems(
    b: BatchDetailResponse,
    cursor: FrozenCursor,
    statusById: Record<string, 'transcribed' | 'approved'>,
): Array<{ transcription_id: string; student_id: string }> {
    const byId = new Map(b.transcriptions.map((t) => [t.transcription_id, t]));
    return cursor.order
        .slice(cursor.boundary)
        .filter((id) => statusById[id] !== 'approved')
        .map((id) => byId.get(id))
        .filter((t): t is BatchTranscriptionItem => !!t && !!t.matched_student_id)
        .map((t) => ({ transcription_id: t.transcription_id, student_id: t.matched_student_id! }));
}

export default function BatchItemReviewPage() {
    const params = useParams<{ id: string; transcriptionId: string }>();
    const batchId = params.id;
    const transcriptionId = params.transcriptionId;

    const { batch, cursor, error } = useBatchReview();

    const item: BatchTranscriptionItem | undefined = useMemo(
        () => batch?.transcriptions.find((t) => t.transcription_id === transcriptionId),
        [batch, transcriptionId],
    );

    const position = useMemo(
        () => (cursor ? cursorPosition(cursor.order, transcriptionId) : null),
        [cursor, transcriptionId],
    );
    const counters = useMemo(
        () => (cursor ? counterInfo(cursor, transcriptionId) : null),
        [cursor, transcriptionId],
    );

    if (error) {
        return (
            <div className="min-h-screen flex flex-col items-center justify-center gap-4 p-6">
                <p className="text-red-600">{error}</p>
                <Link href={`/batches/${batchId}`} className="text-primary-600 underline">
                    חזרה לסיכום המקבץ
                </Link>
            </div>
        );
    }

    if (!batch) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <Loader2 className="animate-spin text-primary-500" size={32} />
            </div>
        );
    }

    if (!item || !position || !counters) {
        // Bad deep link. (OD2: late arrivals APPEND to the cursor, so a valid
        // item is always locatable; only a genuinely foreign id lands here.)
        return (
            <div className="min-h-screen flex flex-col items-center justify-center gap-4 p-6">
                <p className="text-gray-700">המבחן המבוקש לא נמצא במקבץ הזה</p>
                <Link href={`/batches/${batchId}`} className="text-primary-600 underline">
                    חזרה לסיכום המקבץ
                </Link>
            </div>
        );
    }

    // Hooks that depend on the item live in the child (item is guaranteed here;
    // the child remounts per item, which is the hydration boundary).
    return (
        <ReviewItemView
            key={item.transcription_id}
            batchId={batchId}
            item={item}
            position={position}
            counters={counters}
        />
    );
}

function ReviewItemView({ batchId, item, position, counters }: {
    batchId: string;
    item: BatchTranscriptionItem;
    position: CursorPosition;
    counters: CounterInfo;
}) {
    const router = useRouter();
    const {
        batch, save, applyReviewLocally, refetchAfterAction, getCursor,
        softNote, showSoftNote,
        getPage, warmPage, isDissolved, markDissolved,
    } = useBatchReview();

    const state = useReviewItemState(item, async (txId, body) => {
        const review = await save(txId, body);
        applyReviewLocally(txId, review);
        return review;
    });

    const [showAcceptModal, setShowAcceptModal] = useState(false);
    const [accepting, setAccepting] = useState(false);
    const [acceptError, setAcceptError] = useState<string | null>(null);
    // R4: the end-of-flagged-walk interstitial (count frozen at decision time).
    const [interstitial, setInterstitial] = useState<{ cleansRemaining: number } | null>(null);
    const [bulkBusy, setBulkBusy] = useState(false);
    const [bulkError, setBulkError] = useState<string | null>(null);
    // R1: chip-shake feedback for anchors that no longer resolve.
    const [shakenReason, setShakenReason] = useState<string | null>(null);

    const readOnly = state.accepted;
    const modalOpen = showAcceptModal || interstitial !== null;

    // Freshest payload for async decisions (advance, bulk) without waiting on
    // a React re-render.
    const latestBatchRef = useRef(batch);
    latestBatchRef.current = batch;

    // F9: stable identity — the inline arrow restarted the surface's
    // page-warm loop on EVERY keystroke (census Q21; the single flow always
    // memoized). Cache-absorbed but wasteful; fixed at the source.
    const getPageForItem = useCallback(
        (p: number) => getPage(item.transcription_id, p),
        [getPage, item.transcription_id],
    );

    // Δ9 prefetch: once idle, warm the NEXT item's first page (linear cost now).
    useEffect(() => {
        if (!position.nextId) return;
        const nextId = position.nextId;
        const w = window as Window & {
            requestIdleCallback?: (cb: () => void) => number;
            cancelIdleCallback?: (h: number) => void;
        };
        const handle = w.requestIdleCallback
            ? w.requestIdleCallback(() => warmPage(nextId, 1))
            : window.setTimeout(() => warmPage(nextId, 1), 1500);
        return () => {
            if (w.cancelIdleCallback) w.cancelIdleCallback(handle);
            else window.clearTimeout(handle);
        };
    }, [position.nextId, warmPage]);

    // Rider-1 amended OD-8 ruling: guard whenever there's something to lose —
    // dirty, or a save in-flight/failed (tab-close is the exit autosave-on-
    // navigate can't cover). Predicate lives in the controller module, tested.
    useEffect(() => {
        if (!needsUnloadGuard(state)) return;
        const handler = (e: BeforeUnloadEvent) => { e.preventDefault(); };
        window.addEventListener('beforeunload', handler);
        return () => window.removeEventListener('beforeunload', handler);
    }, [state.dirty, state.saving, state.saveError, state.accepted]);

    // R3: focus the main region on item mount (the keyboard walk's landing).
    const mainRef = useRef<HTMLDivElement | null>(null);
    useEffect(() => { mainRef.current?.focus(); }, []);

    const goTo = useCallback(async (targetId: string) => {
        const ok = await state.flushIfDirty();
        if (!ok) return; // failed save BLOCKS navigation (OD-8) — never silent loss
        router.replace(`/batches/${batchId}/review/${targetId}`);
    }, [batchId, router, state]);

    // R8: exits OUT of the review segment flush too (the last-item dashboard
    // exit was a bare <Link> before P3).
    const exitTo = useCallback(async (path: string) => {
        const ok = await state.flushIfDirty();
        if (!ok) return;
        router.push(path);
    }, [router, state]);

    const handleAcceptConfirm = useCallback(async () => {
        if (!state.studentId) return;
        setAccepting(true);
        setAcceptError(null);
        try {
            await acceptOneTranscription(
                batchId, item.transcription_id, state.studentId, state.buildAnswers(),
            );
        } catch (e) {
            setAcceptError(e instanceof Error ? e.message : 'שגיאה באישור התמלול');
            setAccepting(false);
            return;
        }
        state.markAccepted();          // Δ4: suppress all further PATCHes
        setShowAcceptModal(false);
        // R11: the accept SUCCEEDED — a refetch failure is a soft note, never
        // a re-reported error; accepted state stands.
        let fresh: BatchDetailResponse | null = null;
        try {
            fresh = await refetchAfterAction();
        } catch {
            showSoftNote(SOFT_REFETCH_NOTE);
        }
        setAccepting(false);
        // R4/R12: advance from the freshest snapshot available.
        const cur = getCursor();
        if (!cur) return;
        const statusById = statusMapWith(fresh ?? latestBatchRef.current, item.transcription_id);
        const target = advanceTarget(cur, item.transcription_id, statusById);
        if (target.kind === 'item') {
            router.replace(`/batches/${batchId}/review/${target.id}`);
        } else if (target.kind === 'interstitial') {
            const cleansRemaining = cur.order
                .slice(cur.boundary)
                .filter((id) => statusById[id] !== 'approved')
                .length;
            setInterstitial({ cleansRemaining });
        } else {
            router.push(`/batches/${batchId}`);
        }
    }, [batchId, getCursor, item.transcription_id, refetchAfterAction, router, showSoftNote, state]);

    // The interstitial's bulk-acceptable subset, live against the latest data.
    const bulkAcceptable = useMemo(() => {
        if (!interstitial || !batch) return 0;
        const cur = getCursor();
        if (!cur) return 0;
        return cleanBulkItems(batch, cur, statusMapWith(batch, item.transcription_id)).length;
    }, [interstitial, batch, getCursor, item.transcription_id]);

    const handleInterstitialBulk = useCallback(async () => {
        const cur = getCursor();
        const b = latestBatchRef.current;
        if (!cur || !b) return;
        const items = cleanBulkItems(b, cur, statusMapWith(b, item.transcription_id));
        if (items.length === 0) {
            router.push(`/batches/${batchId}`);
            return;
        }
        setBulkBusy(true);
        setBulkError(null);
        try {
            const res = await acceptCleanTranscriptions(batchId, items);
            if (res.skipped.length > 0) {
                const fragments = Array.from(new Set(
                    res.skipped.map((s) => SKIP_REASON_FRAGMENTS[s.skipped_reason] ?? s.skipped_reason),
                ));
                handOffSkipNotice(batchId, SKIP_NOTICE(res.skipped.length, fragments.join(', ')));
            }
            router.push(`/batches/${batchId}`);
        } catch (e) {
            setBulkError(e instanceof Error ? e.message : 'שגיאה באישור המרוכז');
            setBulkBusy(false);
        }
    }, [batchId, getCursor, item.transcription_id, router]);

    // R1: entry-frozen chips; anchors resolved at CLICK time against current
    // text (a fixed card honestly stops anchoring — the chip shakes instead).
    const reasons = item.flag_verdict.reasons;
    const onChipClick = useCallback((reason: string) => {
        const anchors = reasonAnchors(
            item,
            state.editedAnswers as Record<string, string>,
            latestBatchRef.current?.selection_groups,
        );
        const anchor = anchors.find((a) => a.reason === reason)?.anchor ?? { kind: 'missing' as const };
        if (anchor.kind === 'card') {
            const el = document.querySelector<HTMLElement>(`[data-answer-key="${anchor.key}"]`);
            if (el) {
                el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                el.classList.remove('motion-safe:animate-anchor-pulse');
                void el.offsetWidth; // restart the animation on repeat clicks
                el.classList.add('motion-safe:animate-anchor-pulse');
                window.setTimeout(() => el.classList.remove('motion-safe:animate-anchor-pulse'), 1300);
                return;
            }
        } else if (anchor.kind === 'student') {
            const picker = document.querySelector<HTMLElement>('[data-student-picker]');
            if (picker) {
                picker.scrollIntoView({ behavior: 'smooth', block: 'center' });
                picker.querySelector<HTMLElement>('input, button')?.focus();
                return;
            }
        }
        // Missing target → shake the chip, never scroll nowhere (R1 edge).
        setShakenReason(reason);
        window.setTimeout(() => setShakenReason(null), 450);
    }, [item, state.editedAnswers]);

    // R3: one window listener, one pure reducer. Modal-open and IME
    // composition are dead keys (the F8 Modal also suppresses at capture).
    useEffect(() => {
        const onKey = (e: KeyboardEvent) => {
            const t = e.target as HTMLElement | null;
            // Native activation stays native: Enter on a focused button/link/
            // select must click IT, never be hijacked into page-level approve
            // (preventDefault would suppress the click).
            if (e.key === 'Enter' && t?.closest('button, a, select, summary')) return;
            // Held-key auto-repeat must not machine-gun navigation through
            // the flush pipeline.
            if (e.repeat) return;
            const inEditable = !!t && (
                t instanceof HTMLTextAreaElement
                || t instanceof HTMLInputElement
                || t instanceof HTMLSelectElement
                || t.isContentEditable
            );
            const action = resolveKeyAction({
                key: e.key,
                ctrlOrMeta: e.ctrlKey || e.metaKey,
                isComposing: e.isComposing,
                inEditable,
                modalOpen,
            });
            if (!action) return;
            e.preventDefault();
            switch (action) {
                case 'save':
                    if (!readOnly) void state.flushIfDirty();
                    return;
                case 'approve':
                    if (!readOnly && state.studentId && !state.saving) setShowAcceptModal(true);
                    return;
                case 'next':
                    if (position.nextId) void goTo(position.nextId);
                    else void exitTo(`/batches/${batchId}`);
                    return;
                case 'prev':
                    if (position.prevId) void goTo(position.prevId);
                    return;
            }
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [modalOpen, readOnly, position.nextId, position.prevId, goTo, exitTo, batchId, state]);

    // Accept-modal signals (v0.5 thresholds; low confidence < 0.85).
    // Empty answers are excluded: under two_phase, confidence is page-attribution
    // similarity and a legitimately-skipped question is empty with 0.0 — an
    // empty transcription is already its own modal warning (isEmpty).
    const lowConfidence = item.draft.answers.filter(
        (a) => a.answer_text.trim() !== '' && a.confidence < 0.85,
    ).length;
    // editedAnswers covers every draft key after hydration, so it is the whole truth.
    const hasUncertain = Object.values(state.editedAnswers).some((t) => t.includes('[?]'));
    const isEmpty = item.draft.answers.length === 0
        || Object.values(state.editedAnswers).every((t) => t.trim() === '');

    const saveStatus = state.saving
        ? { text: 'שומר…', cls: 'text-gray-500' }
        : state.saveError
            ? { text: 'השמירה נכשלה', cls: 'text-red-600' }
            : state.dirty
                ? { text: 'שינויים לא שמורים', cls: 'text-amber-600' }
                : state.saved
                    ? { text: 'נשמר', cls: 'text-green-600' }
                    : null;

    const kbdCls = 'hidden desk:inline-block text-[10px] leading-none px-1 py-0.5 rounded border border-surface-300 bg-surface-50 text-gray-500 font-sans';

    return (
        <>
            {/* D11: below the desk breakpoint the review module yields to the
                honest interstitial (§3.2) — CSS-only, per the logged decision. */}
            <div
                className="desk:hidden min-h-screen bg-surface-50 flex flex-col items-center justify-center gap-4 p-6 text-center"
                data-testid="mobile-review-interstitial"
            >
                <p className="text-gray-700 max-w-sm">{MOBILE_REVIEW_INTERSTITIAL}</p>
                <Link href={`/batches/${batchId}`} className="text-primary-600 underline">
                    {INTERSTITIAL_BACK}
                </Link>
            </div>

            <div className="hidden desk:block min-h-screen bg-surface-50">
                {/* Sticky header: title + counters + status + actions + cursor nav */}
                <div className="bg-white border-b border-surface-200 sticky top-0 z-20">
                    <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between gap-4 flex-wrap">
                        <div>
                            <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                                בדיקת תמלול
                                {/* R5 primary: flagged-walk position; omitted on clean items */}
                                {counters.i !== null && (
                                    <span
                                        className="text-sm font-medium text-batch-amber-ink bg-batch-amber-soft border border-batch-amber-line rounded-full px-2.5 py-0.5"
                                        data-testid="position-primary"
                                    >
                                        {POSITION_PRIMARY(counters.i, counters.F)}
                                    </span>
                                )}
                                {readOnly && (
                                    <span className="inline-flex items-center gap-1 text-sm font-medium text-green-700 bg-green-50 border border-green-200 rounded-full px-2 py-0.5">
                                        <Check size={14} />
                                        אושר
                                    </span>
                                )}
                            </h1>
                            <p className="text-sm text-gray-500">
                                {item.filename ?? 'ללא שם קובץ'}
                                {item.matched_student_name ? ` • ${item.matched_student_name}` : ''}
                                {' '}• <span data-testid="position-secondary">{POSITION_SECONDARY(counters.k, counters.T)}</span>
                            </p>
                        </div>

                        <div className="flex items-center gap-3">
                            {saveStatus && !readOnly && (
                                <span className={`text-sm ${saveStatus.cls}`}>{saveStatus.text}</span>
                            )}
                            {!readOnly && (
                                <>
                                    <button
                                        onClick={() => void state.flushIfDirty()}
                                        disabled={state.saving || !state.dirty}
                                        className="px-4 py-2 rounded-lg border border-surface-300 text-gray-700 hover:bg-surface-100 disabled:opacity-50 transition-colors flex items-center gap-2"
                                    >
                                        שמירה
                                        <kbd className={kbdCls}>Ctrl+S</kbd>
                                    </button>
                                    <button
                                        onClick={() => setShowAcceptModal(true)}
                                        disabled={!state.studentId || state.saving}
                                        title={!state.studentId ? 'יש לבחור תלמיד/ה לפני אישור' : undefined}
                                        className="px-4 py-2 rounded-lg bg-primary-500 text-white hover:bg-primary-600 disabled:opacity-50 transition-colors flex items-center gap-2"
                                        data-testid="accept-button"
                                    >
                                        אישור תמלול
                                        <kbd className="hidden desk:inline-block text-[10px] leading-none px-1 py-0.5 rounded border border-primary-300 bg-primary-400/40 text-white font-sans">Enter</kbd>
                                    </button>
                                </>
                            )}

                            {/* RTL: "previous" points right, "next" points left */}
                            {position.prevId !== null && (
                                <button
                                    onClick={() => void goTo(position.prevId!)}
                                    className="flex items-center gap-1 px-3 py-2 rounded-lg text-gray-700 hover:bg-surface-100 transition-colors"
                                >
                                    <ChevronRight size={18} />
                                    הקודם
                                    <kbd className={kbdCls}>→</kbd>
                                </button>
                            )}
                            {position.nextId !== null ? (
                                <button
                                    onClick={() => void goTo(position.nextId!)}
                                    className="flex items-center gap-1 px-3 py-2 rounded-lg text-gray-700 hover:bg-surface-100 transition-colors"
                                >
                                    הבא
                                    <kbd className={kbdCls}>←</kbd>
                                    <ChevronLeft size={18} />
                                </button>
                            ) : (
                                <button
                                    onClick={() => void exitTo(`/batches/${batchId}`)}
                                    className="flex items-center gap-1 px-3 py-2 rounded-lg bg-primary-500 text-white hover:bg-primary-600 transition-colors"
                                    data-testid="exit-to-dashboard"
                                >
                                    חזרה לסיכום המקבץ
                                    <ChevronLeft size={18} />
                                </button>
                            )}
                        </div>
                    </div>

                    {/* R1: the reason rail — entry-frozen chips, click to anchor */}
                    {reasons.length > 0 && (
                        <div className="max-w-7xl mx-auto px-6 pb-3" data-testid="reason-rail">
                            <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-sm font-medium text-batch-amber-ink">{RAIL_LABEL}</span>
                                {reasons.map((r) => (
                                    <button
                                        key={r}
                                        onClick={() => onChipClick(r)}
                                        data-testid={`reason-chip-${r}`}
                                        className={`text-xs px-2.5 py-1 rounded-full bg-batch-amber-soft border border-batch-amber-line text-batch-amber-ink hover:bg-amber-100 transition-colors ${
                                            shakenReason === r ? 'motion-safe:animate-shake' : ''
                                        }`}
                                    >
                                        {flagReasonLabel(r)}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* R11: provider-held soft note (survives the auto-advance) */}
                    {softNote && (
                        <div className="max-w-7xl mx-auto px-6 pb-3">
                            <div
                                className="px-4 py-2 rounded-lg bg-batch-amber-soft border border-batch-amber-line text-batch-amber-ink text-sm"
                                data-testid="soft-refetch-note"
                            >
                                {softNote}
                            </div>
                        </div>
                    )}

                    {(state.saveError || acceptError) && (
                        <div className="max-w-7xl mx-auto px-6 pb-3">
                            <div className="px-4 py-2 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
                                {state.saveError ?? acceptError}
                            </div>
                        </div>
                    )}
                </div>

                {/* R3: the main region takes focus per item mount */}
                <div
                    ref={mainRef}
                    tabIndex={-1}
                    data-testid="review-main"
                    className="max-w-7xl mx-auto p-6 outline-none"
                >
                    <TranscriptionReviewSurface
                        draft={item.draft}
                        selectionGroups={batch?.selection_groups}
                        studentNameSuggestion={item.student_name_suggestion}
                        editedAnswers={state.editedAnswers}
                        onAnswerChange={state.onAnswerChange}
                        studentId={state.studentId}
                        onStudentPick={state.onStudentPick}
                        readOnly={readOnly}
                        getPage={getPageForItem}
                        isDissolved={(key) => isDissolved(item.transcription_id, key)}
                        markDissolved={(key) => markDissolved(item.transcription_id, key)}
                        onSwapAnswers={state.swapAnswers}
                        pageNumbersByKey={state.pageNumbers as Record<string, number[]>}
                    />
                </div>

                {/* R3: the fixed keyboard legend (desktop only) */}
                <div
                    className="hidden desk:flex fixed bottom-4 left-4 z-10 items-center gap-3 rounded-lg border border-surface-200 bg-white/95 px-3 py-2 text-xs text-gray-500 shadow-sm"
                    data-testid="kbd-legend"
                >
                    <span className="flex items-center gap-1"><kbd className={kbdCls}>←</kbd> הבא</span>
                    <span className="flex items-center gap-1"><kbd className={kbdCls}>→</kbd> הקודם</span>
                    <span className="flex items-center gap-1"><kbd className={kbdCls}>Enter</kbd> אישור</span>
                    <span className="flex items-center gap-1"><kbd className={kbdCls}>Ctrl+S</kbd> שמירה</span>
                    <span className="flex items-center gap-1"><kbd className={kbdCls}>Esc</kbd> סגירה</span>
                </div>

                <ConfirmAcceptModal
                    isOpen={showAcceptModal}
                    onConfirm={() => void handleAcceptConfirm()}
                    onCancel={() => setShowAcceptModal(false)}
                    lowConfidence={lowConfidence}
                    hasUncertain={hasUncertain}
                    isEmpty={isEmpty}
                    confirming={accepting}
                />

                <ReviewInterstitialModal
                    open={interstitial !== null}
                    cleansRemaining={interstitial?.cleansRemaining ?? 0}
                    bulkAcceptable={bulkAcceptable}
                    busy={bulkBusy}
                    error={bulkError}
                    onBulkAccept={() => void handleInterstitialBulk()}
                    onBackToDashboard={() => router.push(`/batches/${batchId}`)}
                    onClose={() => setInterstitial(null)}
                />
            </div>
        </>
    );
}
