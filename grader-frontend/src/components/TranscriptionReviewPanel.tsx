'use client';

import { useState, useEffect, useCallback } from 'react';
import { AlertTriangle, Info, Loader2, ChevronRight, ChevronLeft } from 'lucide-react';
import { StudentPicker } from './StudentPicker';
import { getTranscriptionPage } from '@/lib/api';
import type {
    TranscribeResponse,
    TranscriptionAnnotation,
    ReaderDisagreementMetadata,
    GradeAnswerInput,
} from '@/types/transcription';

interface Props {
    response: TranscribeResponse;
    onSubmit: (answers: GradeAnswerInput[], studentId: string) => Promise<void>;
    onBack: () => void;
    submitting: boolean;
}

// ---------------------------------------------------------------------------
// Annotation banner (local helper)
// ---------------------------------------------------------------------------

function AnnotationBanner({
    annotation,
    onShowPage,
}: {
    annotation: TranscriptionAnnotation;
    onShowPage?: (page: number) => void;
}) {
    const styles: Record<string, string> = {
        error: 'bg-red-50 border-red-300 text-red-800',
        warning: 'bg-amber-50 border-amber-300 text-amber-800',
        info: 'bg-blue-50 border-blue-300 text-blue-700',
    };
    const icons: Record<string, React.ReactNode> = {
        error: <AlertTriangle size={14} className="shrink-0 mt-0.5" />,
        warning: <AlertTriangle size={14} className="shrink-0 mt-0.5" />,
        info: <Info size={14} className="shrink-0 mt-0.5" />,
    };

    // Trust-layer disagreement: show the disputed span + alternatives verbatim
    // and a jump-to-page affordance (the whole point is a fast look at the ink).
    if (annotation.annotation_type === 'reader_disagreement') {
        const md = annotation.metadata as unknown as ReaderDisagreementMetadata;
        return (
            <div
                className={`px-3 py-2 border rounded-lg text-sm space-y-1.5 ${styles[annotation.severity] ?? ''}`}
                dir="rtl"
            >
                <div className="flex items-start gap-2">
                    {icons[annotation.severity]}
                    <span>קריאה חוזרת של קטע זה זיהתה נוסח שונה — מומלץ להשוות מול הסריקה</span>
                    {typeof md?.page === 'number' && onShowPage && (
                        <button
                            onClick={() => onShowPage(md.page)}
                            className="mr-auto shrink-0 text-xs bg-white/70 hover:bg-white border border-current/20 px-2 py-0.5 rounded-full transition-colors"
                            title="הצג את העמוד בסריקה"
                        >
                            עמ׳ {md.page}
                        </button>
                    )}
                </div>
                {md?.line_quote && (
                    <div dir="ltr" className="font-mono text-xs bg-white/60 rounded px-2 py-1 overflow-x-auto whitespace-pre">
                        {md.line_quote}
                    </div>
                )}
                <div dir="ltr" className="font-mono text-xs flex flex-wrap items-center gap-1.5">
                    <span className="px-1.5 py-0.5 rounded bg-white/60 line-through decoration-dotted">
                        {md?.transcribed || '∅'}
                    </span>
                    <span className="text-gray-400">↔</span>
                    {(md?.alternatives ?? []).map((alt, i) => (
                        <span key={i} className="px-1.5 py-0.5 rounded bg-white/90 border border-current/20 font-semibold">
                            {alt || '∅'}
                        </span>
                    ))}
                </div>
            </div>
        );
    }

    return (
        <div
            className={`flex items-start gap-2 px-3 py-2 border rounded-lg text-sm ${styles[annotation.severity] ?? ''}`}
            dir="rtl"
        >
            {icons[annotation.severity]}
            <span>{annotation.message}</span>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export function TranscriptionReviewPanel({ response, onSubmit, onBack, submitting }: Props) {
    const { draft } = response;

    function answerKey(a: { question_number: number; sub_question_id: string | null }) {
        return a.sub_question_id
            ? `q${a.question_number}.${a.sub_question_id}`
            : `q${a.question_number}`;
    }

    // Answer editing state
    const [editedAnswers, setEditedAnswers] = useState<Record<string, string>>(
        Object.fromEntries(draft.answers.map(a => [answerKey(a), a.answer_text]))
    );
    const [studentId, setStudentId] = useState<string | null>(null);
    const [submitError, setSubmitError] = useState<string | null>(null);

    // Source pane state
    const [selectedPage, setSelectedPage] = useState<number>(
        () => draft.answers[0]?.page_numbers?.[0] ?? 1
    );
    const [pageCache, setPageCache] = useState<Record<number, string>>({}); // page# → base64
    const [loadingPage, setLoadingPage] = useState(false);
    const [pageLoadError, setPageLoadError] = useState<string | null>(null);

    // Mobile tab state
    const [activeMobilePane, setActiveMobilePane] = useState<'answers' | 'source'>('answers');

    // Order annotations by evidence strength: warnings first, then (for reader
    // disagreements) by how many independent readers disputed the span — the
    // measured P(real error) rises steeply with the vote count, so the
    // teacher's first glances land on the most suspicious spans.
    const evidenceOrder = (a: TranscriptionAnnotation, b: TranscriptionAnnotation) => {
        const sev = (x: TranscriptionAnnotation) =>
            x.severity === 'error' ? 0 : x.severity === 'warning' ? 1 : 2;
        if (sev(a) !== sev(b)) return sev(a) - sev(b);
        const votes = (x: TranscriptionAnnotation) =>
            typeof x.metadata?.n_readers === 'number' ? -(x.metadata.n_readers as number) : 0;
        return votes(a) - votes(b);
    };
    const globalAnnotations = draft.annotations
        .filter(ann => ann.target_id === 'transcription')
        .sort(evidenceOrder);
    const annotationsFor = (key: string) =>
        draft.annotations.filter(ann => ann.target_id === key).sort(evidenceOrder);
    const warningCount = draft.annotations.filter(a => a.severity === 'warning').length;

    // Fetch a page image (with component-state cache)
    const fetchPage = useCallback(async (pageNumber: number) => {
        if (pageNumber < 1 || pageNumber > draft.page_count) return;
        if (pageCache[pageNumber]) {
            setSelectedPage(pageNumber);
            return;
        }
        setLoadingPage(true);
        setPageLoadError(null);
        try {
            const result = await getTranscriptionPage(response.transcription_id, pageNumber);
            setPageCache(prev => ({ ...prev, [pageNumber]: result.thumbnail_base64 }));
            setSelectedPage(pageNumber);
        } catch (err: unknown) {
            setPageLoadError(err instanceof Error ? err.message : 'שגיאה בטעינת הדף');
        } finally {
            setLoadingPage(false);
        }
    }, [pageCache, response.transcription_id, draft.page_count]);

    // Load the first page on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
    useEffect(() => { void fetchPage(selectedPage); }, []);

    // Flag jump-to-page: fetch + reveal the source pane (mobile switches tab)
    const showPage = useCallback((page: number) => {
        void fetchPage(page);
        setActiveMobilePane('source');
    }, [fetchPage]);

    const handleSubmit = async () => {
        if (!studentId) return;
        setSubmitError(null);
        const answers: GradeAnswerInput[] = draft.answers.map(a => ({
            question_number: a.question_number,
            sub_question_id: a.sub_question_id,
            answer_text: editedAnswers[answerKey(a)] ?? a.answer_text,
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
                        <ChevronRight size={16} />
                        חזרה
                    </button>
                    <span className="text-gray-300">|</span>
                    <h1 className="text-lg font-semibold text-gray-900">בדיקת תמלול</h1>
                </div>

                {/* Mobile tab switcher */}
                <div className="flex lg:hidden gap-1 bg-surface-100 rounded-lg p-0.5">
                    <button
                        onClick={() => setActiveMobilePane('answers')}
                        className={`px-3 py-1 text-xs rounded-md transition-colors ${
                            activeMobilePane === 'answers'
                                ? 'bg-white shadow text-gray-900 font-medium'
                                : 'text-gray-500 hover:text-gray-700'
                        }`}
                    >
                        תשובות
                    </button>
                    <button
                        onClick={() => setActiveMobilePane('source')}
                        className={`px-3 py-1 text-xs rounded-md transition-colors ${
                            activeMobilePane === 'source'
                                ? 'bg-white shadow text-gray-900 font-medium'
                                : 'text-gray-500 hover:text-gray-700'
                        }`}
                    >
                        מקור
                    </button>
                </div>

                {/* Desktop: review summary + page count */}
                <div className="hidden lg:flex items-center gap-3">
                    {warningCount > 0 ? (
                        <span className="flex items-center gap-1.5 text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 px-2.5 py-1 rounded-full">
                            <AlertTriangle size={12} />
                            {warningCount} אזורים מומלצים לבדיקה
                        </span>
                    ) : (
                        <span className="text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-full">
                            לא זוהו אזורים חשודים
                        </span>
                    )}
                    <span className="text-sm text-gray-400">
                        {draft.page_count} {draft.page_count === 1 ? 'עמוד' : 'עמודים'}
                    </span>
                </div>
            </div>

            {/* Two-pane body */}
            <div
                className="flex flex-col lg:flex-row overflow-hidden"
                style={{ height: 'calc(100vh - 65px)' }}
            >
                {/* Answers pane (right in RTL = first in flex) */}
                <div
                    className={`w-full lg:w-1/2 overflow-y-auto px-6 py-8 space-y-6 ${
                        activeMobilePane !== 'answers' ? 'hidden lg:block' : ''
                    }`}
                >
                    {/* Global annotations */}
                    {globalAnnotations.length > 0 && (
                        <div className="space-y-2">
                            {globalAnnotations.map(ann => (
                                <AnnotationBanner key={ann.id} annotation={ann} onShowPage={showPage} />
                            ))}
                        </div>
                    )}

                    {/* Student picker */}
                    <div className="bg-white rounded-xl border border-surface-200 p-5 shadow-sm">
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            תלמיד
                            <span className="text-red-500 mr-1">*</span>
                        </label>
                        {draft.student_name_suggestion && (
                            <p className="text-xs text-gray-400 mb-2">
                                הצעה מהתמלול:{' '}
                                <span className="font-medium">{draft.student_name_suggestion}</span>
                            </p>
                        )}
                        <StudentPicker
                            value={studentId}
                            onChange={setStudentId}
                            disabled={submitting}
                        />
                    </div>

                    {/* Answer editors */}
                    {draft.answers.length === 0 ? (
                        <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 text-amber-800 text-sm text-center">
                            לא זוהו תשובות בתמלול — בדוק שהקובץ הועלה נכון
                        </div>
                    ) : (
                        draft.answers.map(a => {
                            const key = answerKey(a);
                            const anns = annotationsFor(key);
                            // Trust-layer INFO flags can be numerous (single-reader
                            // disagreements ≈ 5% real) — fold them behind a summary
                            // so warnings keep the teacher's attention budget.
                            const primary = anns.filter(
                                ann => ann.severity !== 'info' || ann.annotation_type !== 'reader_disagreement'
                            );
                            const secondary = anns.filter(
                                ann => ann.severity === 'info' && ann.annotation_type === 'reader_disagreement'
                            );
                            return (
                                <div
                                    key={key}
                                    className="bg-white rounded-xl border border-surface-200 p-5 shadow-sm space-y-3"
                                >
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm font-semibold text-gray-800">
                                                שאלה {a.question_number}
                                                {a.sub_question_id ? ` סעיף ${a.sub_question_id}` : ''}
                                            </span>
                                            {a.page_numbers.length > 0 && (
                                                <button
                                                    onClick={() => void fetchPage(a.page_numbers[0])}
                                                    className="text-xs text-gray-400 bg-surface-100 hover:bg-surface-200 px-2 py-0.5 rounded-full transition-colors"
                                                    title="הצג עמוד במקור"
                                                >
                                                    עמ׳ {a.page_numbers.join(', ')}
                                                </button>
                                            )}
                                        </div>
                                        <span className="text-xs text-gray-400">
                                            ביטחון {Math.round(a.confidence * 100)}%
                                        </span>
                                    </div>

                                    {primary.map(ann => (
                                        <AnnotationBanner key={ann.id} annotation={ann} onShowPage={showPage} />
                                    ))}
                                    {secondary.length > 0 && (
                                        <details className="group">
                                            <summary className="cursor-pointer text-xs text-gray-400 hover:text-gray-600 select-none transition-colors">
                                                עוד {secondary.length} הערות תמלול משניות
                                            </summary>
                                            <div className="space-y-2 mt-2">
                                                {secondary.map(ann => (
                                                    <AnnotationBanner key={ann.id} annotation={ann} onShowPage={showPage} />
                                                ))}
                                            </div>
                                        </details>
                                    )}

                                    <textarea
                                        value={editedAnswers[key] ?? ''}
                                        onChange={e =>
                                            setEditedAnswers(prev => ({ ...prev, [key]: e.target.value }))
                                        }
                                        dir="ltr"
                                        rows={8}
                                        disabled={submitting}
                                        className="w-full px-3 py-2.5 text-sm font-mono border border-surface-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 resize-y bg-surface-50 text-gray-900 disabled:opacity-60"
                                        placeholder="תשובת התלמיד..."
                                    />
                                </div>
                            );
                        })
                    )}

                    {/* Submit error */}
                    {submitError && (
                        <div className="bg-red-50 border border-red-300 text-red-800 rounded-xl px-4 py-3 text-sm">
                            {submitError}
                        </div>
                    )}

                    {/* Action buttons */}
                    <div className="flex gap-3 pt-2 pb-6">
                        <button
                            onClick={onBack}
                            disabled={submitting}
                            className="flex-1 py-3 text-sm font-medium text-gray-600 border border-surface-300 rounded-xl hover:bg-surface-50 disabled:opacity-50 transition-colors"
                        >
                            חזרה
                        </button>
                        <button
                            onClick={handleSubmit}
                            disabled={!studentId || submitting}
                            className="flex-2 flex-grow-[2] py-3 text-sm font-semibold bg-primary-500 text-white rounded-xl hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors"
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
                </div>

                {/* Vertical divider (desktop only) */}
                <div className="hidden lg:block w-px bg-surface-200 flex-shrink-0" />

                {/* Source pane (left in RTL = second in flex) */}
                <div
                    className={`w-full lg:w-1/2 flex flex-col bg-surface-50 border-t border-surface-200 lg:border-t-0 ${
                        activeMobilePane !== 'source' ? 'hidden lg:flex' : 'flex'
                    }`}
                >
                    {/* Page navigation bar */}
                    <div className="sticky top-0 bg-white/80 backdrop-blur border-b border-surface-200 px-4 py-2 flex items-center justify-between flex-shrink-0">
                        <div className="flex items-center gap-2">
                            {/* RTL: ChevronRight = previous page (goes right = back) */}
                            <button
                                onClick={() => void fetchPage(selectedPage - 1)}
                                disabled={selectedPage <= 1 || loadingPage}
                                className="p-1 rounded hover:bg-surface-100 disabled:opacity-40 transition-colors"
                                aria-label="עמוד קודם"
                            >
                                <ChevronRight size={16} className="text-gray-600" />
                            </button>
                            <span className="text-sm text-gray-600 min-w-[80px] text-center">
                                עמוד {selectedPage} / {draft.page_count}
                            </span>
                            {/* RTL: ChevronLeft = next page (goes left = forward) */}
                            <button
                                onClick={() => void fetchPage(selectedPage + 1)}
                                disabled={selectedPage >= draft.page_count || loadingPage}
                                className="p-1 rounded hover:bg-surface-100 disabled:opacity-40 transition-colors"
                                aria-label="עמוד הבא"
                            >
                                <ChevronLeft size={16} className="text-gray-600" />
                            </button>
                        </div>
                        {loadingPage && (
                            <Loader2 size={14} className="animate-spin text-gray-400" />
                        )}
                    </div>

                    {/* Image area */}
                    <div className="flex-1 overflow-y-auto p-4">
                        {loadingPage && !pageCache[selectedPage] ? (
                            <div className="flex items-center justify-center min-h-64 h-full">
                                <Loader2 size={28} className="animate-spin text-gray-400" />
                            </div>
                        ) : pageLoadError ? (
                            <div className="text-red-500 text-sm text-center py-8">
                                {pageLoadError}
                            </div>
                        ) : pageCache[selectedPage] ? (
                            <img
                                src={`data:image/png;base64,${pageCache[selectedPage]}`}
                                alt={`עמוד ${selectedPage}`}
                                className="w-full rounded-lg border border-surface-200 shadow-sm"
                            />
                        ) : null}
                    </div>
                </div>
            </div>
        </div>
    );
}
