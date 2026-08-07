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

import { Eye, FileText, Loader2 } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { StudentPicker } from '@/components/StudentPicker';
import type { TranscriptionAnnotation, TranscriptionDraft } from '@/types/transcription';
import { answersCount, pagesCount } from '@/utils/hebrew-plural';
import { answerTargetId, deriveReviewFlags } from '@/utils/review-flags';

import { TranscribedTextEditor } from './TranscribedTextEditor';

function ConfidenceBadge({ confidence }: { confidence: number }) {
    const percent = Math.round(confidence * 100);
    const colorClass = percent < 70
        ? 'bg-red-100 text-red-700 border-red-200'
        : percent < 85
            ? 'bg-amber-100 text-amber-700 border-amber-200'
            : 'bg-green-100 text-green-700 border-green-200';
    return (
        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${colorClass}`}>
            {percent}%
        </span>
    );
}

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
}: TranscriptionReviewSurfaceProps) {
    const [pages, setPages] = useState<Record<number, string>>({});
    const pageRefs = useRef(new Map<number, HTMLDivElement>());
    // Re-render trigger for dissolution (the memory itself lives in the holder).
    const [, bumpDissolved] = useState(0);

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

    // Answer order: first page, then question number (the panel's proven shape).
    const orderedAnswers = [...draft.answers].sort((a, b) => {
        const pa = a.page_numbers[0] ?? Number.MAX_SAFE_INTEGER;
        const pb = b.page_numbers[0] ?? Number.MAX_SAFE_INTEGER;
        if (pa !== pb) return pa - pb;
        if (a.question_number !== b.question_number) return a.question_number - b.question_number;
        return (a.sub_question_id ?? '').localeCompare(b.sub_question_id ?? '');
    });

    return (
        <div>
            <GlobalAnnotations annotations={draft.annotations} />

            {/* Student assignment (RD-4): on the review screen, pre-seeded. */}
            <div className="bg-white rounded-xl border border-surface-200 p-4 mb-4">
                <div className="flex items-center gap-3 flex-wrap">
                    <span className="text-sm font-medium text-gray-700">שיוך לתלמיד/ה:</span>
                    <div className="min-w-[240px]">
                        <StudentPicker
                            value={studentId}
                            onChange={onStudentPick}
                            disabled={readOnly}
                        />
                    </div>
                    {studentNameSuggestion && (
                        <span className="text-xs text-gray-500">
                            זיהוי מהסריקה: {studentNameSuggestion}
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
                </h2>
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                    <Eye className="text-primary-600" size={20} />
                    תמלול AI
                    <span className="text-sm font-normal text-gray-500">({answersCount(draft.answers.length)})</span>
                    {!readOnly && (
                        <span className="text-xs text-gray-400 font-normal mr-2">• ניתן לערוך ישירות</span>
                    )}
                </h2>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
                {/* Source pages (RTL grid: first column renders on the right) */}
                <div className="space-y-4 lg:sticky lg:top-24 lg:max-h-[calc(100vh-8rem)] lg:overflow-y-auto">
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

                {/* Answer cards */}
                <div className="space-y-4">
                    {orderedAnswers.length === 0 && (
                        <div className="bg-white rounded-xl border border-surface-200 p-8 text-center text-gray-500">
                            אין תשובות בתמלול
                        </div>
                    )}
                    {orderedAnswers.map((answer) => {
                        const key = answerTargetId(answer);
                        const currentText = editedAnswers[key] ?? answer.answer_text;
                        const anns = draft.annotations.filter((a) => a.target_id === key);
                        const { lineFlags, badges } = deriveReviewFlags({
                            currentText,
                            draftText: answer.answer_text,
                            annotations: anns,
                            dissolved: isDissolved(key),
                        });
                        const questionLabel = answer.sub_question_id
                            ? `שאלה ${answer.question_number} סעיף ${answer.sub_question_id}`
                            : `שאלה ${answer.question_number}`;

                        return (
                            <div key={key} className="bg-white rounded-xl border border-surface-200 overflow-hidden shadow-sm">
                                <div className="flex items-center justify-between px-4 py-2 border-b bg-surface-50 border-surface-200">
                                    <div className="flex items-center gap-2 flex-wrap">
                                        <span className="font-medium text-gray-900">{questionLabel}</span>
                                        {answer.page_numbers.map((p) => (
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
                                    <ConfidenceBadge confidence={answer.confidence} />
                                </div>
                                <div className="p-4">
                                    {badges.length > 0 && (
                                        <div className="mb-3 space-y-1">
                                            {badges.map((msg, i) => (
                                                <div key={i} className="px-3 py-1.5 rounded bg-amber-50 border border-amber-200 text-amber-800 text-xs">
                                                    {msg}
                                                </div>
                                            ))}
                                        </div>
                                    )}
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
                                    />
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
