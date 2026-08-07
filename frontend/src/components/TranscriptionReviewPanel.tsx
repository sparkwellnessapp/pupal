'use client';

/**
 * TranscriptionReviewPanel — the SINGLE-TEST review step, now a thin wrapper
 * over the ONE shared review surface (Phase 5 unification, plan OD-7).
 *
 * PROP SEAM UNCHANGED — `{response, onSubmit, onBack, submitting}` — so the
 * wizard (src/app/page.tsx) has a zero diff; verified by the named journey
 * `single-flow-review-unchanged`.
 *
 * Batch-born behaviors are INERT here by construction (Phase-5 rider 2):
 *  - NO autosave / overlay PATCH — the single flow has no review endpoint;
 *    edits live in component state and ride out on submit, as always.
 *  - NO accept modal, NO accepted read-only state, NO save indicator.
 *  - Flag dissolution is a local per-mount set (the Δ7 edit-dissolves behavior
 *    without any cross-item session memory).
 * The submit payload is the panel's historical shape verbatim: the FULL answer
 * set in draft order, edited text merged over draft text, plus the studentId.
 */

import { useCallback, useRef, useState } from 'react';
import { ChevronRight, Loader2 } from 'lucide-react';

import { getTranscriptionPage } from '@/lib/api';
import type { GradeAnswerInput, TranscribeResponse } from '@/types/transcription';
import { answerTargetId } from '@/utils/review-flags';

import { TranscriptionReviewSurface } from './batch-review/TranscriptionReviewSurface';

interface Props {
    response: TranscribeResponse;
    onSubmit: (answers: GradeAnswerInput[], studentId: string) => Promise<void>;
    onBack: () => void;
    submitting: boolean;
}

export function TranscriptionReviewPanel({ response, onSubmit, onBack, submitting }: Props) {
    const draft = response.draft;
    const [editedAnswers, setEditedAnswers] = useState<Record<string, string>>({});
    const [studentId, setStudentId] = useState<string | null>(null);
    const [submitError, setSubmitError] = useState<string | null>(null);
    const dissolvedRef = useRef(new Set<string>());
    const pageCacheRef = useRef(new Map<number, Promise<string>>());
    const [, bump] = useState(0);

    const getPage = useCallback((p: number): Promise<string> => {
        const cached = pageCacheRef.current.get(p);
        if (cached) return cached;
        const inflight = getTranscriptionPage(response.transcription_id, p)
            .then((r) => r.thumbnail_base64);
        inflight.catch(() => pageCacheRef.current.delete(p));
        pageCacheRef.current.set(p, inflight);
        return inflight;
    }, [response.transcription_id]);

    const handleSubmit = async () => {
        if (!studentId) return;
        setSubmitError(null);
        // The historical payload shape, verbatim: full snapshot, draft order.
        const answers: GradeAnswerInput[] = draft.answers.map((a) => ({
            question_number: a.question_number,
            sub_question_id: a.sub_question_id,
            answer_text: editedAnswers[answerTargetId(a)] ?? a.answer_text,
        }));
        try {
            await onSubmit(answers, studentId);
        } catch (err: unknown) {
            setSubmitError(err instanceof Error ? err.message : 'שגיאה בשליחה');
        }
    };

    return (
        <div dir="rtl" className="min-h-screen bg-gradient-to-br from-surface-50 via-primary-50/20 to-surface-100">
            {/* Header */}
            <div className="sticky top-0 z-10 bg-white/80 backdrop-blur border-b border-surface-200 px-6 py-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <button
                        onClick={onBack}
                        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors"
                        disabled={submitting}
                    >
                        <ChevronRight size={18} />
                        חזרה
                    </button>
                    <h1 className="text-lg font-bold text-gray-900">בדיקת תמלול</h1>
                </div>
                <button
                    onClick={handleSubmit}
                    disabled={!studentId || submitting}
                    title={!studentId ? 'יש לבחור תלמיד/ה לפני שליחה' : undefined}
                    className="py-2 px-5 text-sm font-semibold bg-primary-500 text-white rounded-xl hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors"
                >
                    {submitting ? (
                        <>
                            <Loader2 size={16} className="animate-spin" />
                            שולח לבדיקה...
                        </>
                    ) : (
                        'שלח לבדיקה'
                    )}
                </button>
            </div>

            {submitError && (
                <div className="max-w-7xl mx-auto px-6 pt-3">
                    <div className="bg-red-50 border border-red-300 text-red-800 rounded-xl px-4 py-3 text-sm">
                        {submitError}
                    </div>
                </div>
            )}

            <div className="max-w-7xl mx-auto p-6">
                <TranscriptionReviewSurface
                    draft={draft}
                    studentNameSuggestion={draft.student_name_suggestion}
                    editedAnswers={editedAnswers}
                    onAnswerChange={(key, text) => {
                        setEditedAnswers((prev) => ({ ...prev, [key]: text }));
                    }}
                    studentId={studentId}
                    onStudentPick={setStudentId}
                    readOnly={submitting}
                    getPage={getPage}
                    isDissolved={(key) => dissolvedRef.current.has(key)}
                    markDissolved={(key) => { dissolvedRef.current.add(key); bump((n) => n + 1); }}
                />
            </div>
        </div>
    );
}
