'use client';

/**
 * TranscriptionReviewSurface — THE transcription-review surface (plan §7):
 * the v0.5 page's layout and interaction patterns rebuilt on the current
 * plumbing. Answer-indexed cards (OD-3: the artifact is answer-shaped; per-page
 * text does not exist) beside a source-page column, with client-derived
 * per-line flags (Δ6/Δ7) and the student picker (RD-4).
 *
 * Controlled component: all editable state (answers, student) is owned by the
 * caller (the batch shell today; the single-flow wrapper in Phase 5).
 * Subject-agnostic (§3.3): plain monospace editing, no CS-specific rendering.
 */

import { AlignLeft, ChevronDown, ChevronUp, Eye, FileText, Loader2, Table, ZoomIn, ZoomOut } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { StudentPicker } from '@/components/StudentPicker';
import {
    ANSWER_VIEW_SHOW_RAW,
    ANSWER_VIEW_SHOW_TABLE,
    EMPTY_ANSWER_MARKER,
    EMPTY_ANSWER_PLACEHOLDER,
} from '@/copy/batch';
import type {
    AnswerSpaceSelectionGroup,
    TranscriptionAnnotation,
    TranscriptionDraft,
} from '@/types/transcription';
import { hasRenderableTable } from '@/utils/detect-pipe-tables';
import { answersCount, pagesCount } from '@/utils/hebrew-plural';
import { orderAnswersPageFirst } from '@/utils/review-anchors';
import { answerTargetId, deriveReviewFlags } from '@/utils/review-flags';
import { expectedEmptyKeys } from '@/utils/selection-expectation';
import { detectMismatch, keyLabel, type AnswerKey } from '@/utils/segmentation-check';

import { TranscribedAnswerView } from './TranscribedAnswerView';
import { TranscribedTextEditor } from './TranscribedTextEditor';

/** R10: discrete zoom stops for the scan pane (§3.2 — resets per item, which
 *  the App Router gives for free: the page segment remounts per item). */
const ZOOM_LEVELS = [1, 1.35, 1.8];

// NOTE (2026-08-07): the per-answer ConfidenceBadge was removed. Under the
// two_phase engine `answer.confidence` is page-attribution similarity, not
// transcription confidence — rendering it as a % ("100%" beside red flags)
// was a misleading mixed signal. Genuinely low attribution now surfaces via
// the triage verdict (low_confidence / missing_answers reasons), not here.

function GlobalAnnotations({ annotations }: { annotations: TranscriptionAnnotation[] }) {
    const global = annotations.filter((a) => a.target_id === 'transcription');
    if (global.length === 0) return null;
    return (
        <div className="mb-4 space-y-2">
            {global.map((a) => (
                <div
                    key={a.id}
                    className={`px-4 py-2 rounded-lg border text-sm ${
                        a.severity === 'warning'
                            ? 'bg-amber-50 border-amber-200 text-amber-800'
                            : 'bg-surface-50 border-surface-200 text-gray-600'
                    }`}
                >
                    {a.message}
                </div>
            ))}
        </div>
    );
}

export interface TranscriptionReviewSurfaceProps {
    /** The transcription draft — the surface consumes the ARTIFACT, not batch
     *  furniture (Phase 5: the same surface serves the single-test flow). */
    draft: TranscriptionDraft;
    /** VLM student-name guess — display-only hint beside the picker. */
    studentNameSuggestion?: string | null;
    editedAnswers: Record<string, string>;
    onAnswerChange: (key: string, text: string) => void;
    studentId: string | null;
    onStudentPick: (id: string) => void;
    readOnly: boolean;
    /** Δ9 cached page loader (from the entry holder). */
    getPage: (pageNumber: number) => Promise<string>;
    /** Δ7 session memory (from the entry holder). */
    isDissolved: (answerKey: string) => boolean;
    markDissolved: (answerKey: string) => void;
    /**
     * Reassignment (2026-08-07): SWAP the contents of two containers (keys
     * stay frozen — the grading route; only content moves). When absent the
     * whole reassignment UI (dropdown + one-click proposal) is hidden —
     * the single-test flow doesn't pass it, keeping its frozen seam inert.
     */
    onSwapAnswers?: (keyA: string, keyB: string) => void;
    /** Display provenance per key (page chips travel with swapped content);
     *  falls back to the draft's per-answer page_numbers. */
    pageNumbersByKey?: Record<string, number[]>;
    /**
     * Rubric selection groups in answer space ("choose k of N", 2026-08-12).
     * When a group is satisfied, its unattempted members' empty containers
     * collapse into one quiet disclosure row instead of rendering as gaps.
     * Absent/[] (selection-free rubric) → identical to old behavior.
     */
    selectionGroups?: AnswerSpaceSelectionGroup[] | null;
}

export function TranscriptionReviewSurface({
    draft,
    studentNameSuggestion,
    editedAnswers,
    onAnswerChange,
    studentId,
    onStudentPick,
    readOnly,
    getPage,
    isDissolved,
    markDissolved,
    onSwapAnswers,
    pageNumbersByKey,
    selectionGroups,
}: TranscriptionReviewSurfaceProps) {
    const [pages, setPages] = useState<Record<number, string>>({});
    const pageRefs = useRef(new Map<number, HTMLDivElement>());
    // Re-render trigger for dissolution (the memory itself lives in the holder).
    const [, bumpDissolved] = useState(0);
    // Selection-collapsed containers: closed by default, one click reveals.
    const [showUnanswered, setShowUnanswered] = useState(false);
    // R10: scan-pane zoom index into ZOOM_LEVELS.
    const [zoomIdx, setZoomIdx] = useState(0);
    const zoom = ZOOM_LEVELS[zoomIdx];
    /**
     * Per-answer view mode — EXPLICIT teacher choices only. The default is
     * derived per render (below), so an answer whose text starts or stops
     * containing a grid follows its own content until she overrules it.
     *
     * Δ14 (viewing is not commitment): switching modes writes ONLY here. It
     * never calls onAnswerChange, so it cannot mark the item dirty, cannot
     * create a review overlay, and cannot pull the item out of bulk-accept.
     */
    const [viewOverride, setViewOverride] = useState<Record<string, 'raw' | 'table'>>({});
    // The answer whose editor should take the caret: she clicked through to edit.
    const [focusKey, setFocusKey] = useState<string | null>(null);

    // Δ9: eager first page, then background-warm the rest sequentially.
    useEffect(() => {
        let cancelled = false;
        (async () => {
            for (let p = 1; p <= draft.page_count; p += 1) {
                try {
                    const b64 = await getPage(p);
                    if (cancelled) return;
                    setPages((prev) => (prev[p] ? prev : { ...prev, [p]: b64 }));
                } catch {
                    // A failed page shows its skeleton + retry happens on next entry;
                    // never blocks the answers column.
                }
            }
        })();
        return () => { cancelled = true; };
    }, [draft.page_count, getPage]);

    const scrollToPage = useCallback((pageNumber: number) => {
        pageRefs.current.get(pageNumber)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, []);

    // Answer order: first page, then question number (the panel's proven
    // shape) — THE shared sort (review-anchors), so the R1 rail chips and the
    // rendered cards can never disagree about "first".
    const orderedAnswers = orderAnswersPageFirst(draft.answers);

    // Reassignment support (frozen key set + current text per key, for the
    // live marker↔key mismatch detection and the dropdown).
    const allKeys: AnswerKey[] = draft.answers.map((a) => ({
        question_number: a.question_number,
        sub_question_id: a.sub_question_id,
    }));
    const currentTextByKey: Record<string, string> = {};
    for (const a of draft.answers) {
        const k = answerTargetId(a);
        currentTextByKey[k] = editedAnswers[k] ?? a.answer_text;
    }
    const reassignEnabled = !!onSwapAnswers && !readOnly && draft.answers.length > 1;

    // "Choose k of N" expectation — LIVE against current text (like the
    // mismatch detector): typing into a collapsed container or swapping
    // content into it makes its question "attempted" and the card
    // materializes; keys and submit payloads are untouched.
    const selectionExpectedEmpty = expectedEmptyKeys(
        draft.answers.map((a) => ({
            question_number: a.question_number,
            sub_question_id: a.sub_question_id,
            text: currentTextByKey[answerTargetId(a)] ?? '',
        })),
        selectionGroups,
    );
    const displayedAnswers = orderedAnswers.filter(
        (a) => showUnanswered || !selectionExpectedEmpty.has(answerTargetId(a)),
    );
    const suppressedQuestionNumbers = Array.from(new Set(
        orderedAnswers
            .filter((a) => selectionExpectedEmpty.has(answerTargetId(a)))
            .map((a) => a.question_number),
    )).sort((a, b) => a - b);

    return (
        <div>
            <GlobalAnnotations annotations={draft.annotations} />

            {/* Student assignment (RD-4): on the review screen, pre-seeded. */}
            <div className="bg-white rounded-xl border border-surface-200 p-4 mb-4">
                <div className="flex items-center gap-3 flex-wrap">
                    <span className="text-sm font-medium text-gray-700">שיוך לתלמיד/ה:</span>
                    {/* R1: the student_* rail chips anchor here. */}
                    <div className="min-w-[240px]" data-student-picker>
                        <StudentPicker
                            value={studentId}
                            onChange={onStudentPick}
                            disabled={readOnly}
                            suggestedName={studentNameSuggestion}
                        />
                    </div>
                    {studentNameSuggestion && (
                        <span className="text-xs text-gray-500">
                            שם התלמיד חולץ אוטומטית
                        </span>
                    )}
                </div>
            </div>

            {/* Column headers */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-3">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                    <FileText className="text-primary-600" size={20} />
                    מבחן מקורי
                    <span className="text-sm font-normal text-gray-500">({pagesCount(draft.page_count)})</span>
                    {/* R10: zoom controls — ms-auto pushes them to the pane's far (left) edge. */}
                    <span className="ms-auto flex items-center gap-1">
                        <button
                            type="button"
                            onClick={() => setZoomIdx((i) => Math.max(0, i - 1))}
                            disabled={zoomIdx === 0}
                            aria-label="הקטנת תצוגת הסריקה"
                            data-testid="zoom-out"
                            className="w-7 h-7 flex items-center justify-center rounded-lg border border-surface-300 bg-white text-gray-600 hover:bg-surface-50 transition-colors disabled:opacity-40 disabled:hover:bg-white"
                        >
                            <ZoomOut size={15} />
                        </button>
                        <button
                            type="button"
                            onClick={() => setZoomIdx((i) => Math.min(ZOOM_LEVELS.length - 1, i + 1))}
                            disabled={zoomIdx === ZOOM_LEVELS.length - 1}
                            aria-label="הגדלת תצוגת הסריקה"
                            data-testid="zoom-in"
                            className="w-7 h-7 flex items-center justify-center rounded-lg border border-surface-300 bg-white text-gray-600 hover:bg-surface-50 transition-colors disabled:opacity-40 disabled:hover:bg-white"
                        >
                            <ZoomIn size={15} />
                        </button>
                    </span>
                </h2>
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                    <Eye className="text-primary-600" size={20} />
                    תמלול AI
                    <span className="text-sm font-normal text-gray-500">({answersCount(displayedAnswers.length)})</span>
                    {!readOnly && (
                        <span className="text-xs text-gray-400 font-normal mr-2">• ניתן לערוך ישירות</span>
                    )}
                </h2>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
                {/* Source pages (RTL grid: first column renders on the right) */}
                <div className="lg:sticky lg:top-24 lg:max-h-[calc(100vh-8rem)] lg:overflow-auto">
                    {/* R10 zoom target. transform-origin is top RIGHT: in this
                        RTL container the scaled overflow extends inline-end
                        (left) + block-end (down) — exactly the directions the
                        CSS scrollable-overflow region grows in RTL, so the
                        parent pane scroll-pans with no measured sizer. */}
                    <div
                        data-testid="scan-zoom-content"
                        className="space-y-4"
                        style={zoom === 1 ? undefined : { transform: `scale(${zoom})`, transformOrigin: 'top right' }}
                    >
                        {Array.from({ length: draft.page_count }, (_, i) => i + 1).map((p) => (
                            <div
                                key={p}
                                ref={(el) => { if (el) pageRefs.current.set(p, el); }}
                                className="bg-white rounded-xl border border-surface-200 p-4"
                            >
                                <div className="text-sm text-gray-500 mb-2 font-medium">עמוד {p}</div>
                                {pages[p] ? (
                                    // eslint-disable-next-line @next/next/no-img-element
                                    <img
                                        src={`data:image/png;base64,${pages[p]}`}
                                        alt={`עמוד ${p}`}
                                        className="w-full h-auto rounded border border-surface-100"
                                    />
                                ) : (
                                    <div className="h-64 flex items-center justify-center text-gray-400">
                                        <Loader2 className="animate-spin" size={22} />
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>

                {/* Answer cards */}
                <div className="space-y-4">
                    {orderedAnswers.length === 0 && (
                        <div className="bg-white rounded-xl border border-surface-200 p-8 text-center text-gray-500">
                            אין תשובות בתמלול
                        </div>
                    )}
                    {displayedAnswers.map((answer) => {
                        const key = answerTargetId(answer);
                        const suppressedBySelection = selectionExpectedEmpty.has(key);
                        const assignedKey: AnswerKey = {
                            question_number: answer.question_number,
                            sub_question_id: answer.sub_question_id,
                        };
                        const currentText = editedAnswers[key] ?? answer.answer_text;
                        // ALPHA-GAP A-4 (D-2): the reviewer sees whole pages; alpha shows the crop behind a `[איור: …]` line.
                        const displayPages = pageNumbersByKey?.[key] ?? answer.page_numbers;
                        const anns = draft.annotations.filter((a) => a.target_id === key);
                        const { lineFlags, badges } = deriveReviewFlags({
                            currentText,
                            draftText: answer.answer_text,
                            annotations: anns,
                            dissolved: isDissolved(key),
                        });
                        // Table rendering (2026-08-23): a DISPLAY derivation over the
                        // same verbatim text — the raw string stays the payload.
                        // Default to the grid only when nothing is flagged: line
                        // flags are the review signal and they live in the raw view
                        // alone, so never trade one away for a prettier surface.
                        const tableAvailable = hasRenderableTable(currentText);
                        const viewMode = viewOverride[key]
                            ?? (tableAvailable && lineFlags.length === 0 ? 'table' : 'raw');
                        const showTable = tableAvailable && viewMode === 'table';
                        const questionLabel = keyLabel(assignedKey);
                        // LIVE marker↔key mismatch — recomputed against the
                        // current text, so banners stay truthful through a
                        // reassignment chain (swap → both banners update).
                        const mismatch = detectMismatch(currentText, assignedKey, allKeys);
                        const proposalKey = mismatch?.proposedTarget
                            ? answerTargetId(mismatch.proposedTarget) : null;
                        const proposalIsEmpty = proposalKey !== null
                            && (currentTextByKey[proposalKey] ?? '').trim() === '';
                        // R2: empty ∧ not selection-explained → marked. LIVE
                        // against current text: typing (or swapping content
                        // in) dissolves the marker immediately.
                        const emptyUnexplained = currentText.trim() === '' && !suppressedBySelection;

                        return (
                            <div
                                key={key}
                                data-answer-key={key}
                                className={`bg-white rounded-xl border overflow-hidden shadow-sm ${
                                    emptyUnexplained ? 'border-amber-300' : 'border-surface-200'
                                }`}
                            >
                                <div className="flex items-center justify-between px-4 py-2 border-b bg-surface-50 border-surface-200 gap-2">
                                    <div className="flex items-center gap-2 flex-wrap">
                                        <span className="font-medium text-gray-900">{questionLabel}</span>
                                        {emptyUnexplained && (
                                            <span
                                                className="bg-amber-100 text-amber-800 text-xs px-2 py-0.5 rounded"
                                                data-testid="empty-answer-marker"
                                            >
                                                {EMPTY_ANSWER_MARKER}
                                            </span>
                                        )}
                                        {suppressedBySelection && (
                                            <span
                                                className="bg-surface-100 text-gray-500 text-xs px-2 py-0.5 rounded"
                                                data-testid="selection-unanswered-badge"
                                            >
                                                לא נענתה (שאלת בחירה)
                                            </span>
                                        )}
                                        {displayPages.map((p) => (
                                            <button
                                                key={p}
                                                onClick={() => scrollToPage(p)}
                                                className="bg-primary-100 text-primary-700 text-xs px-2 py-0.5 rounded hover:bg-primary-200 transition-colors"
                                                title="מעבר לעמוד בסריקה"
                                            >
                                                עמוד {p}
                                            </button>
                                        ))}
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0">
                                        {tableAvailable && (
                                            <button
                                                type="button"
                                                onClick={() => {
                                                    const next = showTable ? 'raw' : 'table';
                                                    setViewOverride((prev) => ({ ...prev, [key]: next }));
                                                    // Switching TO the editor hands over the caret;
                                                    // switching away must not leave a stale request.
                                                    setFocusKey(next === 'raw' ? key : null);
                                                }}
                                                className="flex items-center gap-1 text-xs border border-surface-300 rounded-lg px-2 py-1 bg-white text-gray-600 hover:border-surface-400 hover:bg-surface-50 transition-colors"
                                                data-testid="answer-view-toggle"
                                            >
                                                {showTable
                                                    ? <><AlignLeft size={13} />{ANSWER_VIEW_SHOW_RAW}</>
                                                    : <><Table size={13} />{ANSWER_VIEW_SHOW_TABLE}</>}
                                            </button>
                                        )}
                                        {reassignEnabled && (
                                            <select
                                                value=""
                                                onChange={(e) => {
                                                    if (e.target.value) onSwapAnswers!(key, e.target.value);
                                                }}
                                                className="text-xs border border-surface-300 rounded-lg px-2 py-1 bg-white text-gray-600 hover:border-surface-400 cursor-pointer"
                                                title="החלפת תוכן עם שאלה אחרת (הכיתוב נשאר; התוכן עובר)"
                                                data-testid="reassign-select"
                                            >
                                                <option value="" disabled>העברה אל…</option>
                                                {draft.answers
                                                    .filter((o) => answerTargetId(o) !== key)
                                                    .map((o) => {
                                                        const ok = answerTargetId(o);
                                                        const empty = (currentTextByKey[ok] ?? '').trim() === '';
                                                        return (
                                                            <option key={ok} value={ok}>
                                                                {keyLabel({ question_number: o.question_number, sub_question_id: o.sub_question_id })}
                                                                {empty ? ' (ריק)' : ' (החלפה)'}
                                                            </option>
                                                        );
                                                    })}
                                            </select>
                                        )}
                                    </div>
                                </div>
                                <div className="p-4">
                                    {mismatch && (
                                        <div
                                            className="mb-3 px-3 py-2 rounded-lg bg-orange-50 border border-orange-300 text-orange-800 text-xs flex items-center justify-between gap-2 flex-wrap"
                                            data-testid="segmentation-mismatch-banner"
                                        >
                                            <span>
                                                בכתב היד הקטע מסומן כשאלה {mismatch.declaredQuestion}, אך שויך ל{questionLabel} — כדאי לוודא את השיוך.
                                            </span>
                                            {proposalKey && onSwapAnswers && !readOnly && (
                                                <button
                                                    onClick={() => onSwapAnswers(key, proposalKey)}
                                                    className="shrink-0 bg-orange-600 text-white px-2.5 py-1 rounded-lg hover:bg-orange-700 transition-colors font-medium"
                                                    data-testid="segmentation-mismatch-fix"
                                                >
                                                    {proposalIsEmpty
                                                        ? `העברה ל${keyLabel(mismatch.proposedTarget!)}`
                                                        : `החלפה עם ${keyLabel(mismatch.proposedTarget!)}`}
                                                </button>
                                            )}
                                        </div>
                                    )}
                                    {badges.length > 0 && (
                                        <div className="mb-3 space-y-1">
                                            {badges.map((msg, i) => (
                                                <div key={i} className="px-3 py-1.5 rounded bg-amber-50 border border-amber-200 text-amber-800 text-xs">
                                                    {msg}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                    {showTable ? (
                                        <TranscribedAnswerView
                                            text={currentText}
                                            flagCount={lineFlags.length}
                                        />
                                    ) : (
                                        <TranscribedTextEditor
                                            value={currentText}
                                            onChange={(text) => {
                                                // Δ7: first divergence dissolves this answer's
                                                // span flags for the session.
                                                if (text !== answer.answer_text && !isDissolved(key)) {
                                                    markDissolved(key);
                                                    bumpDissolved((n) => n + 1);
                                                }
                                                onAnswerChange(key, text);
                                            }}
                                            readOnly={readOnly}
                                            lineFlags={lineFlags}
                                            placeholder={emptyUnexplained ? EMPTY_ANSWER_PLACEHOLDER : undefined}
                                            autoFocus={focusKey === key}
                                        />
                                    )}
                                </div>
                            </div>
                        );
                    })}

                    {/* Selection exams: unchosen questions collapse into one
                        quiet row (owner-ruled 2026-08-12) — the containers
                        stay reachable so a pipeline miss can still be typed
                        into place, but they never render as gaps. */}
                    {suppressedQuestionNumbers.length > 0 && (
                        <button
                            onClick={() => setShowUnanswered((v) => !v)}
                            className="w-full flex items-center justify-between gap-2 px-4 py-3 rounded-xl border border-dashed border-surface-300 bg-surface-50 text-sm text-gray-500 hover:bg-surface-100 hover:text-gray-700 transition-colors"
                            data-testid="selection-unanswered-toggle"
                        >
                            <span className="text-right">
                                שאלות שלא נענו (שאלות בחירה):{' '}
                                {suppressedQuestionNumbers.map((n) => `שאלה ${n}`).join(', ')}
                            </span>
                            <span className="flex items-center gap-1 shrink-0">
                                {showUnanswered ? 'הסתרה' : 'הצגה'}
                                {showUnanswered ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                            </span>
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}
