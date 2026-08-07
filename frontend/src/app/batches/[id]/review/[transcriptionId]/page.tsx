'use client';

/**
 * Per-item batch transcription review — the wired shell (Phase 3).
 *
 * /batches/[id]/review/[transcriptionId]
 *
 * DATA + FREEZE + CACHES LIVE IN THE SEGMENT LAYOUT (BatchReviewProvider):
 * this page component REMOUNTS on every prev/next (the App Router keys page
 * segments by param value — rider-a finding), so everything that must survive
 * navigation (the one batch fetch, the Δ10 frozen order, the Δ9 page cache,
 * the Δ7 dissolution memory) is held by the layout. Per-item editor state
 * lives in ReviewItemController (hydrated per item mount; Δ11-guarded against
 * same-item payload refreshes).
 *
 * Actions (OD-2A): שמירה = the overlay flush (repeatable, navigation-safe);
 * אישור תמלול = today's accept semantics (approve + queue grading, per item).
 * Autosave-on-navigate is dirty-gated (Δ14); a failed save blocks navigation
 * (OD-8); PATCHes are suppressed after accept (Δ4).
 */

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Check, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';

import { acceptOneTranscription } from '@/lib/api';
import { useBatchReview } from '@/components/batch-review/BatchReviewContext';
import { needsUnloadGuard } from '@/components/batch-review/reviewItemController';
import { ConfirmAcceptModal } from '@/components/batch-review/ConfirmAcceptModal';
import { TranscriptionReviewSurface } from '@/components/batch-review/TranscriptionReviewSurface';
import { useReviewItemState } from '@/components/batch-review/useReviewItemState';
import type { BatchTranscriptionItem } from '@/types/batch';
import { cursorPosition, type CursorPosition } from '@/utils/batch-review-cursor';

export default function BatchItemReviewPage() {
    const params = useParams<{ id: string; transcriptionId: string }>();
    const batchId = params.id;
    const transcriptionId = params.transcriptionId;

    const { batch, frozenOrder, error } = useBatchReview();

    const item: BatchTranscriptionItem | undefined = useMemo(
        () => batch?.transcriptions.find((t) => t.transcription_id === transcriptionId),
        [batch, transcriptionId],
    );

    const position = useMemo(
        () => (frozenOrder ? cursorPosition(frozenOrder, transcriptionId) : null),
        [frozenOrder, transcriptionId],
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

    if (!item || !position) {
        // Bad deep link, or an item that arrived after route entry (Δ10):
        // fall back to the batch page rather than guessing a cursor.
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
    return <ReviewItemView key={item.transcription_id} batchId={batchId} item={item} position={position} />;
}

function ReviewItemView({ batchId, item, position }: {
    batchId: string;
    item: BatchTranscriptionItem;
    position: CursorPosition;
}) {
    const router = useRouter();
    const {
        save, applyReviewLocally, refetchAfterAction,
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

    const readOnly = state.accepted;

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

    const goTo = useCallback(async (targetId: string) => {
        const ok = await state.flushIfDirty();
        if (!ok) return; // failed save BLOCKS navigation (OD-8) — never silent loss
        router.replace(`/batches/${batchId}/review/${targetId}`);
    }, [batchId, router, state]);

    const handleAcceptConfirm = useCallback(async () => {
        if (!state.studentId) return;
        setAccepting(true);
        setAcceptError(null);
        try {
            await acceptOneTranscription(
                batchId, item.transcription_id, state.studentId, state.buildAnswers(),
            );
            state.markAccepted();          // Δ4: suppress all further PATCHes
            setShowAcceptModal(false);
            await refetchAfterAction();    // Δ11: explicit-action refetch (state, not order)
        } catch (e) {
            setAcceptError(e instanceof Error ? e.message : 'שגיאה באישור התמלול');
        } finally {
            setAccepting(false);
        }
    }, [batchId, item.transcription_id, refetchAfterAction, state]);

    // Accept-modal signals (v0.5 thresholds; low confidence < 0.85).
    const lowConfidence = item.draft.answers.filter((a) => a.confidence < 0.85).length;
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

    return (
        <div className="min-h-screen bg-surface-50">
            {/* Sticky header: title + status + actions + cursor nav */}
            <div className="bg-white border-b border-surface-200 sticky top-0 z-20">
                <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between gap-4 flex-wrap">
                    <div>
                        <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                            בדיקת תמלול
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
                            {' '}• {position.index + 1} מתוך {position.total}
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
                                    className="px-4 py-2 rounded-lg border border-surface-300 text-gray-700 hover:bg-surface-100 disabled:opacity-50 transition-colors"
                                >
                                    שמירה
                                </button>
                                <button
                                    onClick={() => setShowAcceptModal(true)}
                                    disabled={!state.studentId || state.saving}
                                    title={!state.studentId ? 'יש לבחור תלמיד/ה לפני אישור' : undefined}
                                    className="px-4 py-2 rounded-lg bg-primary-500 text-white hover:bg-primary-600 disabled:opacity-50 transition-colors"
                                >
                                    אישור תמלול
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
                            </button>
                        )}
                        {position.nextId !== null ? (
                            <button
                                onClick={() => void goTo(position.nextId!)}
                                className="flex items-center gap-1 px-3 py-2 rounded-lg text-gray-700 hover:bg-surface-100 transition-colors"
                            >
                                הבא
                                <ChevronLeft size={18} />
                            </button>
                        ) : (
                            <Link
                                href={`/batches/${batchId}`}
                                className="flex items-center gap-1 px-3 py-2 rounded-lg bg-primary-500 text-white hover:bg-primary-600 transition-colors"
                            >
                                חזרה לסיכום המקבץ
                                <ChevronLeft size={18} />
                            </Link>
                        )}
                    </div>
                </div>
                {(state.saveError || acceptError) && (
                    <div className="max-w-7xl mx-auto px-6 pb-3">
                        <div className="px-4 py-2 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
                            {state.saveError ?? acceptError}
                        </div>
                    </div>
                )}
            </div>

            <div className="max-w-7xl mx-auto p-6">
                <TranscriptionReviewSurface
                    draft={item.draft}
                    studentNameSuggestion={item.student_name_suggestion}
                    editedAnswers={state.editedAnswers}
                    onAnswerChange={state.onAnswerChange}
                    studentId={state.studentId}
                    onStudentPick={state.onStudentPick}
                    readOnly={readOnly}
                    getPage={(p) => getPage(item.transcription_id, p)}
                    isDissolved={(key) => isDissolved(item.transcription_id, key)}
                    markDissolved={(key) => markDissolved(item.transcription_id, key)}
                />
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
        </div>
    );
}
