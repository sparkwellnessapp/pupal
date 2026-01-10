'use client';

import { useState, useMemo, useCallback, useEffect, useReducer, useRef } from 'react';
import {
    FileText,
    AlertTriangle,
    ChevronLeft,
    ChevronRight,
    Loader2,
    Eye,
    X,
    CheckCircle2,
    Sparkles,
} from 'lucide-react';
import type {
    TranscriptionReviewResponse,
    TranscribedAnswerWithPages,
    StudentAnswerInput,
    TranscriptionPhase,
    PagePreview,
    TranscriptionStreamState,
    StreamAction,
} from '@/lib/api';
import {
    streamStateToReviewResponse,
    streamReducer,
    createInitialStreamState,
    streamTranscriptionV2,
} from '@/lib/api';

// =============================================================================
// Props Interfaces
// =============================================================================

interface TranscriptionReviewPageProps {
    // For non-streaming mode (backwards compatibility)
    transcriptionData?: TranscriptionReviewResponse;

    // For streaming mode
    rubricId?: string;
    testFile?: File;
    answeredQuestions?: number[];
    studentName?: string;  // Teacher-provided student name

    // Common props
    onContinueToGrading: (editedAnswers: StudentAnswerInput[]) => void;
    onBack: () => void;
    isGrading?: boolean;
    externalStreamState?: TranscriptionStreamState;
    externalTranscriptionData?: TranscriptionReviewResponse | null;
}

// =============================================================================
// Streaming Banner Component
// =============================================================================

function StreamingBanner({
    phase,
    currentPage,
    totalPages,
    message,
    pageStates,
}: {
    phase: TranscriptionPhase;
    currentPage: number;
    totalPages: number;
    message: string;
    pageStates: Map<number, { rawText: string; verifiedText: string; phase: string; isStreaming: boolean }>;
}) {
    if (phase === 'done') return null;

    // Calculate progress
    const completedPages = Array.from(pageStates.values()).filter(p => p.phase === 'complete').length;
    const progressPercent = totalPages > 0 ? (completedPages / totalPages) * 100 : 0;

    const phaseIcons: Record<TranscriptionPhase, JSX.Element> = {
        loading: <Loader2 className="animate-spin text-primary-600" size={20} />,
        transcribing: <Eye className="text-blue-600" size={20} />,
        verifying: <Sparkles className="text-purple-600" size={20} />,
        done: <CheckCircle2 className="text-green-600" size={20} />,
    };

    const phaseColors: Record<TranscriptionPhase, string> = {
        loading: 'from-gray-50 to-gray-100 border-gray-200',
        transcribing: 'from-blue-50 to-indigo-50 border-blue-200',
        verifying: 'from-purple-50 to-pink-50 border-purple-200',
        done: 'from-green-50 to-emerald-50 border-green-200',
    };

    return (
        <div className={`bg-gradient-to-r ${phaseColors[phase]} border-b`}>
            <div className="max-w-7xl mx-auto px-6 py-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="relative">
                            {phaseIcons[phase]}
                            <div className="absolute inset-0 animate-ping opacity-30">
                                {phaseIcons[phase]}
                            </div>
                        </div>
                        <div>
                            <span className="font-medium text-gray-900">{message}</span>
                            {totalPages > 0 && phase !== 'loading' && (
                                <span className="text-gray-500 text-sm mr-2">
                                    • עמוד {currentPage} מתוך {totalPages}
                                </span>
                            )}
                        </div>
                    </div>

                    {/* Progress bar */}
                    {totalPages > 0 && (
                        <div className="flex items-center gap-2 w-48">
                            <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-primary-500 transition-all duration-500 ease-out"
                                    style={{ width: `${progressPercent}%` }}
                                />
                            </div>
                            <span className="text-xs text-gray-500 w-10">
                                {Math.round(progressPercent)}%
                            </span>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

// =============================================================================
// Streaming Text Display Component
// =============================================================================

function StreamingTextDisplay({
    rawText,
    verifiedText,
    phase,
    isStreaming,
}: {
    rawText: string;
    verifiedText: string;
    phase: 'raw' | 'verifying' | 'complete';
    isStreaming: boolean;
}) {
    const containerRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom while streaming
    useEffect(() => {
        if (isStreaming && containerRef.current) {
            containerRef.current.scrollTop = containerRef.current.scrollHeight;
        }
    }, [rawText, verifiedText, isStreaming]);

    // Determine which text to display
    const displayText = phase === 'raw' ? rawText : (verifiedText || rawText);

    // Extract just the code content if we can parse it
    const codeContent = useMemo(() => {
        try {
            // Try to extract answer_text from JSON response
            const jsonMatch = displayText.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                const parsed = JSON.parse(jsonMatch[0]);
                const answers = parsed?.transcription?.answers || [];
                if (answers.length > 0) {
                    return answers.map((a: any) => a.answer_text || '').join('\n\n');
                }
            }
        } catch {
            // Fall through to raw display
        }
        // If can't parse, show the raw streaming text
        return displayText;
    }, [displayText]);

    // Visual indicator for streaming phase
    const phaseIndicator = {
        raw: { bg: 'bg-blue-50', border: 'border-blue-200', label: 'תמלול גולמי', color: 'text-blue-600' },
        verifying: { bg: 'bg-purple-50', border: 'border-purple-200', label: 'מאמת...', color: 'text-purple-600' },
        complete: { bg: 'bg-green-50', border: 'border-green-200', label: 'הושלם', color: 'text-green-600' },
    }[phase];

    return (
        <div className={`relative rounded-lg border ${phaseIndicator.border} ${phaseIndicator.bg} overflow-hidden`}>
            {/* Phase indicator badge */}
            <div className={`absolute top-2 left-2 px-2 py-1 rounded text-xs font-medium ${phaseIndicator.color} bg-white/80 backdrop-blur-sm flex items-center gap-1 z-10`}>
                {isStreaming && <Loader2 className="animate-spin" size={12} />}
                {phase === 'complete' && <CheckCircle2 size={12} />}
                {phaseIndicator.label}
            </div>

            {/* Streaming text content */}
            <div
                ref={containerRef}
                className="p-4 pt-10 font-mono text-sm max-h-96 overflow-y-auto"
                dir="ltr"
            >
                <pre className="whitespace-pre-wrap break-words">
                    {codeContent || <span className="text-gray-400">ממתין לתמלול...</span>}
                    {isStreaming && <span className="animate-pulse text-primary-500">|</span>}
                </pre>
            </div>

            {/* Transition overlay when switching from raw to verified */}
            {phase === 'verifying' && verifiedText && (
                <div className="absolute inset-0 bg-gradient-to-b from-transparent via-purple-100/30 to-purple-100/50 pointer-events-none animate-pulse" />
            )}
        </div>
    );
}

// =============================================================================
// Confidence Badge Component
// =============================================================================

function ConfidenceBadge({ confidence }: { confidence: number }) {
    const percent = Math.round(confidence * 100);
    let colorClass = 'bg-green-100 text-green-700 border-green-200';

    if (percent < 70) {
        colorClass = 'bg-red-100 text-red-700 border-red-200';
    } else if (percent < 85) {
        colorClass = 'bg-amber-100 text-amber-700 border-amber-200';
    }

    return (
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${colorClass}`}>
            {percent}%
        </span>
    );
}

// =============================================================================
// Transcribed Text Display (Editable)
// =============================================================================

function TranscribedTextDisplay({
    text,
    onChange,
    readOnly = false,
}: {
    text: string;
    onChange: (newText: string) => void;
    readOnly?: boolean;
}) {
    const hasUncertainLines = text.includes('[?]');
    const lineCount = text.split('\n').length;
    const minHeight = Math.max(150, lineCount * 22 + 40);

    return (
        <div className="relative">
            <textarea
                value={text}
                onChange={(e) => onChange(e.target.value)}
                readOnly={readOnly}
                className={`w-full p-3 font-mono text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 resize-y ${hasUncertainLines
                    ? 'bg-red-50/30 border-red-200 focus:border-red-300'
                    : 'bg-surface-50 border-surface-300'
                    } ${readOnly ? 'cursor-not-allowed opacity-70' : ''}`}
                dir="ltr"
                style={{ minHeight: `${minHeight}px`, whiteSpace: 'pre-wrap' }}
                placeholder="תמלול ריק - ניתן להקליד כאן"
            />
            {hasUncertainLines && (
                <div className="absolute top-2 left-2 flex items-center gap-1 px-2 py-1 bg-red-100 text-red-700 rounded text-xs font-medium">
                    <AlertTriangle size={12} />
                    מכיל תווים לא ברורים [?]
                </div>
            )}
        </div>
    );
}

// =============================================================================
// Answer Editor Component
// =============================================================================

function AnswerEditor({
    answer,
    editedText,
    onTextChange,
    pageLabel,
    isStreaming,
    streamingContent,
}: {
    answer: TranscribedAnswerWithPages;
    editedText: string;
    onTextChange: (text: string) => void;
    pageLabel: string;
    isStreaming?: boolean;
    streamingContent?: { rawText: string; verifiedText: string; phase: 'raw' | 'verifying' | 'complete' };
}) {
    const questionLabel = answer.sub_question_id
        ? `שאלה ${answer.question_number} - סעיף ${answer.sub_question_id}`
        : `שאלה ${answer.question_number}`;

    const hasUncertainContent = editedText.includes('[?]');
    const isLowConfidence = answer.confidence < 0.85;

    return (
        <div className={`bg-white rounded-lg border overflow-hidden ${hasUncertainContent || isLowConfidence
            ? 'border-red-200 shadow-red-100/50'
            : 'border-surface-200'
            } shadow-sm`}>
            {/* Header */}
            <div className={`flex items-center justify-between px-4 py-2 border-b ${hasUncertainContent || isLowConfidence
                ? 'bg-red-50 border-red-200'
                : 'bg-surface-50 border-surface-200'
                }`}>
                <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900">{questionLabel}</span>
                    <span className="text-xs text-gray-500">({pageLabel})</span>
                </div>
                <div className="flex items-center gap-2">
                    <ConfidenceBadge confidence={answer.confidence} />
                    {isStreaming && (
                        <span className="text-xs text-primary-600 flex items-center gap-1">
                            <Loader2 className="animate-spin" size={12} />
                            מתמלל...
                        </span>
                    )}
                </div>
            </div>

            {/* Content */}
            <div className="p-4">
                {isStreaming && streamingContent ? (
                    <StreamingTextDisplay
                        rawText={streamingContent.rawText}
                        verifiedText={streamingContent.verifiedText}
                        phase={streamingContent.phase}
                        isStreaming={isStreaming}
                    />
                ) : (
                    <TranscribedTextDisplay
                        text={editedText}
                        onChange={onTextChange}
                        readOnly={isStreaming}
                    />
                )}
            </div>
        </div>
    );
}

// =============================================================================
// Confirmation Modal
// =============================================================================

function ConfirmationModal({
    isOpen,
    onConfirm,
    onCancel,
    hasUncertainAnswers,
    lowConfidenceCount,
}: {
    isOpen: boolean;
    onConfirm: () => void;
    onCancel: () => void;
    hasUncertainAnswers: boolean;
    lowConfidenceCount: number;
}) {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onCancel} />
            <div className="relative bg-white rounded-xl shadow-2xl max-w-md w-full p-6">
                <button
                    onClick={onCancel}
                    className="absolute top-4 left-4 p-1 text-gray-400 hover:text-gray-600"
                >
                    <X size={20} />
                </button>

                <div className="text-center">
                    <div className="mx-auto w-12 h-12 bg-primary-100 rounded-full flex items-center justify-center mb-4">
                        <CheckCircle2 className="text-primary-600" size={24} />
                    </div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">
                        להמשיך לדירוג?
                    </h3>

                    {(hasUncertainAnswers || lowConfidenceCount > 0) ? (
                        <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg text-right">
                            <div className="flex items-start gap-2 text-amber-700 text-sm">
                                <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" />
                                <div>
                                    {lowConfidenceCount > 0 && (
                                        <p>יש {lowConfidenceCount} תשובות עם ביטחון נמוך</p>
                                    )}
                                    {hasUncertainAnswers && (
                                        <p>יש תווים לא ברורים [?] שיש לבדוק</p>
                                    )}
                                </div>
                            </div>
                        </div>
                    ) : (
                        <p className="text-gray-600 mb-4">
                            וידאת שהתמלול נכון ומוכן לדירוג?
                        </p>
                    )}

                    <div className="flex gap-3 justify-center">
                        <button
                            onClick={onCancel}
                            className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                        >
                            ביטול
                        </button>
                        <button
                            onClick={onConfirm}
                            className="px-4 py-2 text-white bg-primary-500 rounded-lg hover:bg-primary-600 transition-colors"
                        >
                            המשך לדירוג
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export default function TranscriptionReviewPage({
    transcriptionData: initialData,
    rubricId,
    testFile,
    answeredQuestions,
    studentName: providedStudentName,
    onContinueToGrading,
    onBack,
    isGrading = false,
    externalStreamState,
    externalTranscriptionData,
}: TranscriptionReviewPageProps) {
    // Check if parent is providing streaming state (already started streaming)
    const useExternalStream = !!(externalStreamState && externalTranscriptionData);

    // Determine if we're in streaming mode
    const isStreamingMode = useExternalStream || !!(rubricId && testFile);

    // Internal streaming state (only used if no external state provided)
    const [internalStreamState, dispatch] = useReducer(streamReducer, createInitialStreamState());
    const streamAbortRef = useRef<{ abort: () => void } | null>(null);

    // Use external state if provided, otherwise use internal state
    const streamState = useExternalStream ? externalStreamState! : internalStreamState;

    // Use either external transcription data, streamed data, or initial data
    const transcriptionData = useExternalStream
        ? externalTranscriptionData!
        : isStreamingMode
            ? streamStateToReviewResponse(internalStreamState)
            : initialData!;

    // Edited texts state
    const [editedTexts, setEditedTexts] = useState<Record<string, string>>({});
    const [showConfirmModal, setShowConfirmModal] = useState(false);

    // Initialize streaming when in streaming mode
    // Initialize streaming when in streaming mode
    // Initialize streaming when in streaming mode (only if NOT using external stream)
    useEffect(() => {
        // Skip if using external stream (parent already started streaming)
        if (useExternalStream) return;
        if (!isStreamingMode || !rubricId || !testFile) return;

        // Start streaming
        const handle = streamTranscriptionV2(
            rubricId,
            testFile,
            {
                onMetadata: (data) => dispatch({ type: 'METADATA', payload: data }),
                onPage: (page) => dispatch({ type: 'PAGE', payload: page }),
                onPhase: (phase, currentPage, totalPages, message) =>
                    dispatch({ type: 'PHASE', payload: { phase, currentPage, totalPages, message } }),
                onRawChunk: (pageNumber, delta) =>
                    dispatch({ type: 'RAW_CHUNK', payload: { pageNumber, delta } }),
                onRawComplete: (pageNumber, fullText) =>
                    dispatch({ type: 'RAW_COMPLETE', payload: { pageNumber, fullText } }),
                onVerifiedChunk: (pageNumber, delta) =>
                    dispatch({ type: 'VERIFIED_CHUNK', payload: { pageNumber, delta } }),
                onPageComplete: (pageNumber, pageIndex, markedText, detectedQuestions, confidenceScores) =>
                    dispatch({ type: 'PAGE_COMPLETE', payload: { pageNumber, pageIndex, markedText, detectedQuestions, confidenceScores } }),
                onAnswer: (answer) => dispatch({ type: 'ANSWER', payload: answer }),
                onDone: (totalAnswers) => dispatch({ type: 'DONE', payload: { totalAnswers } }),
                onError: (message) => dispatch({ type: 'ERROR', payload: { message } }),
            },
            {
                firstPageIndex: 0,
                answeredQuestions,
            }
        );

        streamAbortRef.current = handle;

        return () => {
            streamAbortRef.current?.abort();
        };
    }, [useExternalStream, isStreamingMode, rubricId, testFile, answeredQuestions]);

    // Initialize edited texts from answers
    useEffect(() => {
        if (transcriptionData?.answers?.length > 0) {
            const initial: Record<string, string> = {};
            transcriptionData.answers.forEach((a) => {
                const key = getAnswerKey(a);
                if (!(key in editedTexts)) {
                    initial[key] = a.answer_text;
                }
            });
            if (Object.keys(initial).length > 0) {
                setEditedTexts(prev => ({ ...prev, ...initial }));
            }
        }
    }, [transcriptionData?.answers]);

    // Helper to get unique key for an answer
    const getAnswerKey = (a: TranscribedAnswerWithPages) =>
        `${a.question_number}-${a.sub_question_id || 'main'}`;

    // Sort answers by page order, then question number
    const sortedAnswers = useMemo(() => {
        if (!transcriptionData?.answers) return [];

        // Deduplicate: merge answers with same question_number + sub_question_id
        const answerMap = new Map<string, TranscribedAnswerWithPages>();

        transcriptionData.answers.forEach((answer) => {
            const key = `${answer.question_number}-${answer.sub_question_id || 'main'}`;
            const existing = answerMap.get(key);

            if (existing) {
                // Merge: combine page_indexes and keep the longer/more complete answer text
                const mergedPageIndexes = Array.from(new Set([...existing.page_indexes, ...answer.page_indexes])).sort((a, b) => a - b);

                // Use the more recent answer text (assuming later answers are more complete)
                // Or concatenate if they're different
                let mergedText = answer.answer_text;
                if (existing.answer_text !== answer.answer_text && !answer.answer_text.includes(existing.answer_text)) {
                    // If texts are different and one doesn't contain the other, keep the longer one
                    mergedText = answer.answer_text.length > existing.answer_text.length
                        ? answer.answer_text
                        : existing.answer_text;
                }

                answerMap.set(key, {
                    ...answer,
                    page_indexes: mergedPageIndexes,
                    answer_text: mergedText,
                    confidence: Math.max(existing.confidence, answer.confidence),
                });
            } else {
                answerMap.set(key, { ...answer });
            }
        });

        // Convert back to array and sort
        return Array.from(answerMap.values()).sort((a, b) => {
            const pageA = a.page_indexes[0] ?? 999;
            const pageB = b.page_indexes[0] ?? 999;
            if (pageA !== pageB) return pageA - pageB;
            if (a.question_number !== b.question_number) return a.question_number - b.question_number;
            return (a.sub_question_id || '').localeCompare(b.sub_question_id || '');
        });
    }, [transcriptionData?.answers]);

    // Get page label for an answer
    const getPageLabel = (answer: TranscribedAnswerWithPages) => {
        if (answer.page_indexes.length === 0) return 'עמוד לא ידוע';
        if (answer.page_indexes.length === 1) return `עמוד ${answer.page_indexes[0] + 1}`;
        return `עמודים ${answer.page_indexes.map(i => i + 1).join(', ')}`;
    };

    // Handle text change
    const handleTextChange = useCallback((key: string, text: string) => {
        setEditedTexts(prev => ({ ...prev, [key]: text }));
    }, []);

    // Handle continue button
    const handleContinueClick = () => {
        setShowConfirmModal(true);
    };

    // Handle confirmed continue - assemble answers from page data
    const handleConfirmedContinue = () => {
        setShowConfirmModal(false);

        // Build a map of question number -> answer text (from all pages)
        const questionAnswers = new Map<number, string[]>();

        // First try to assemble from page states (page-first approach)
        if (streamState.pageStates.size > 0) {
            Array.from(streamState.pageStates.entries())
                .sort(([a], [b]) => a - b)
                .forEach(([pageNum, pageState]) => {
                    const pageKey = `page-${pageNum}`;
                    // Use edited text if available, otherwise use the display text
                    const text = editedTexts[pageKey]
                        ?? (pageState.markedText || pageState.verifiedText || pageState.rawText).replace(/<Q\d+>/g, '');

                    // Get detected questions for this page
                    const questions = pageState.detectedQuestions || [];

                    if (questions.length > 0) {
                        // Assign text to first detected question (for single-question pages)
                        const qNum = questions[0];
                        const existing = questionAnswers.get(qNum) || [];
                        existing.push(text);
                        questionAnswers.set(qNum, existing);
                    } else {
                        // No question detected - use question 1 as fallback
                        const existing = questionAnswers.get(1) || [];
                        existing.push(text);
                        questionAnswers.set(1, existing);
                    }
                });
        }

        // Convert to StudentAnswerInput array
        let editedAnswers: StudentAnswerInput[];

        if (questionAnswers.size > 0) {
            // Build from page-assembled data
            editedAnswers = Array.from(questionAnswers.entries())
                .sort(([a], [b]) => a - b)
                .map(([question_number, texts]) => ({
                    question_number,
                    sub_question_id: null,
                    answer_text: texts.join('\n\n'),
                }));
        } else {
            // Fallback to sortedAnswers if no page data
            editedAnswers = sortedAnswers.map(a => {
                const key = getAnswerKey(a);
                return {
                    question_number: a.question_number,
                    sub_question_id: a.sub_question_id,
                    answer_text: editedTexts[key] ?? a.answer_text,
                };
            });
        }

        onContinueToGrading(editedAnswers);
    };

    // Calculate issues
    const { lowConfidenceCount, hasUncertainAnswers } = useMemo(() => {
        let lowConf = 0;
        let hasUncertain = false;

        sortedAnswers.forEach(a => {
            const key = getAnswerKey(a);
            const text = editedTexts[key] ?? a.answer_text;
            if (a.confidence < 0.85) lowConf++;
            if (text.includes('[?]')) hasUncertain = true;
        });

        return { lowConfidenceCount: lowConf, hasUncertainAnswers: hasUncertain };
    }, [sortedAnswers, editedTexts]);

    // Streaming status
    const isStreaming = isStreamingMode && !streamState.isComplete;
    const currentPhase = streamState.currentPhase;

    // Error state
    if (streamState.error) {
        return (
            <div className="min-h-screen bg-gradient-to-br from-surface-50 via-primary-50/20 to-surface-100 flex items-center justify-center">
                <div className="bg-white rounded-xl shadow-lg p-8 max-w-md">
                    <div className="text-center">
                        <div className="mx-auto w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mb-4">
                            <AlertTriangle className="text-red-600" size={24} />
                        </div>
                        <h3 className="text-lg font-semibold text-gray-900 mb-2">שגיאה בתמלול</h3>
                        <p className="text-gray-600 mb-4">{streamState.error}</p>
                        <button
                            onClick={onBack}
                            className="px-4 py-2 text-white bg-primary-500 rounded-lg hover:bg-primary-600"
                        >
                            חזור
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-surface-50 via-primary-50/20 to-surface-100">
            {/* Streaming Banner */}
            {isStreaming && (
                <StreamingBanner
                    phase={currentPhase}
                    currentPage={streamState.currentPage}
                    totalPages={streamState.totalPages}
                    message={streamState.phaseMessage}
                    pageStates={streamState.pageStates}
                />
            )}

            {/* Sticky Header */}
            <div className="bg-white border-b border-surface-200 sticky top-0 z-20">
                <div className="max-w-7xl mx-auto px-6 py-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <button
                                onClick={onBack}
                                className="p-2 text-gray-500 hover:text-gray-700 hover:bg-surface-100 rounded-lg transition-colors"
                            >
                                <ChevronRight size={20} />
                            </button>
                            <div>
                                <h1 className="text-xl font-bold text-gray-900">בדיקת תמלול</h1>
                                <p className="text-sm text-gray-500">
                                    {providedStudentName || transcriptionData?.student_name || 'תלמיד'} • {transcriptionData?.filename || testFile?.name || ''}
                                </p>
                            </div>
                        </div>

                        <div className="flex items-center gap-3">
                            {(lowConfidenceCount > 0 || hasUncertainAnswers) && !isStreaming && (
                                <div className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-50 text-amber-700 rounded-lg text-sm">
                                    <AlertTriangle size={14} />
                                    {lowConfidenceCount > 0 && `${lowConfidenceCount} תמלולים בביטחון נמוך`}
                                    {lowConfidenceCount > 0 && hasUncertainAnswers && ' • '}
                                    {hasUncertainAnswers && 'יש תווים לא ברורים'}
                                </div>
                            )}

                            <button
                                onClick={handleContinueClick}
                                disabled={isGrading || isStreaming}
                                className="flex items-center gap-2 px-5 py-2.5 bg-primary-500 text-white rounded-lg font-medium hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                            >
                                {isGrading ? (
                                    <>
                                        <Loader2 className="animate-spin" size={18} />
                                        מדרג...
                                    </>
                                ) : isStreaming ? (
                                    <>
                                        <Loader2 className="animate-spin" size={18} />
                                        מתמלל...
                                    </>
                                ) : (
                                    <>
                                        אישור והמשך לדירוג
                                        <ChevronLeft size={18} />
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Column Headers */}
            <div className="bg-white/95 backdrop-blur-sm border-b border-surface-200 sticky top-[73px] z-10">
                <div className="max-w-7xl mx-auto px-6 py-3">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                            <FileText className="text-primary-600" size={20} />
                            מבחן מקורי
                            <span className="text-sm font-normal text-gray-500">
                                ({transcriptionData?.pages?.length || 0} עמודים)
                            </span>
                        </h2>
                        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                            <Eye className="text-primary-600" size={20} />
                            תמלול AI
                            <span className="text-sm font-normal text-gray-500">
                                ({sortedAnswers.length} תשובות)
                            </span>
                            {!isStreaming && (
                                <span className="text-xs text-gray-400 font-normal mr-2">
                                    • ניתן לערוך ישירות
                                </span>
                            )}
                        </h2>
                    </div>
                </div>
            </div>

            {/* Main content */}
            <div className="max-w-7xl mx-auto p-6">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Left Panel - PDF Pages */}
                    <div className="space-y-4">
                        {(transcriptionData?.pages || []).map((page) => (
                            <div
                                key={page.page_index}
                                className="bg-white rounded-xl border border-surface-200 p-4"
                            >
                                <div className="text-sm text-gray-500 mb-2 font-medium flex items-center justify-between">
                                    <span>עמוד {page.page_number}</span>
                                    {isStreamingMode && streamState.pageStates.get(page.page_number)?.isStreaming && (
                                        <span className="flex items-center gap-1 text-primary-600">
                                            <Loader2 className="animate-spin" size={14} />
                                            מתמלל
                                        </span>
                                    )}
                                </div>
                                <img
                                    src={`data:image/png;base64,${page.thumbnail_base64}`}
                                    alt={`עמוד ${page.page_number}`}
                                    className="w-full h-auto rounded border border-surface-100"
                                />
                            </div>
                        ))}

                        {(transcriptionData?.pages?.length === 0 || !transcriptionData?.pages) && (
                            <div className="bg-white rounded-xl border border-surface-200 p-8 text-center">
                                <Loader2 className="animate-spin mx-auto mb-2 text-primary-500" size={24} />
                                <p className="text-gray-500">טוען עמודים...</p>
                            </div>
                        )}
                    </div>

                    {/* Right Panel - Transcriptions */}
                    <div className="space-y-4">
                        {/* 
                          Unified display logic:
                          - During streaming: Show page-by-page streaming content
                          - After streaming: Show the final structured answers (by question)
                          
                          Key insight: We need a smooth transition. When streaming ends,
                          answers should already be populated. If not, we fall back to 
                          showing raw page content to avoid losing any transcribed text.
                        */}

                        {/* During active streaming: Show page-based streaming content */}
                        {isStreaming && (
                            <>
                                {streamState.pageStates.size > 0 ? (
                                    Array.from(streamState.pageStates.entries())
                                        .sort(([a], [b]) => a - b)
                                        .filter(([_, state]) => state.rawText || state.verifiedText)
                                        .map(([pageNum, pageState]) => {
                                            const isActivelyStreaming = pageState.isStreaming || pageState.phase === 'verifying';
                                            const isCompleted = pageState.phase === 'complete';

                                            return (
                                                <div
                                                    key={`streaming-${pageNum}`}
                                                    className={`bg-white rounded-lg border shadow-sm overflow-hidden ${isActivelyStreaming ? 'border-primary-200' :
                                                        isCompleted ? 'border-green-200' : 'border-surface-200'
                                                        }`}
                                                >
                                                    <div className={`flex items-center justify-between px-4 py-2 border-b ${isActivelyStreaming ? 'bg-primary-50 border-primary-200' :
                                                        isCompleted ? 'bg-green-50 border-green-200' : 'bg-surface-50 border-surface-200'
                                                        }`}>
                                                        <span className="font-medium text-gray-900">עמוד {pageNum}</span>
                                                        {isActivelyStreaming ? (
                                                            <span className="text-xs text-primary-600 flex items-center gap-1">
                                                                <Loader2 className="animate-spin" size={12} />
                                                                {pageState.phase === 'raw' ? 'קורא תשובות...' : 'מאמת...'}
                                                            </span>
                                                        ) : isCompleted ? (
                                                            <span className="text-xs text-green-600 flex items-center gap-1">
                                                                <CheckCircle2 size={12} />
                                                                הושלם
                                                            </span>
                                                        ) : null}
                                                    </div>
                                                    <div className="p-4">
                                                        <StreamingTextDisplay
                                                            rawText={pageState.rawText}
                                                            verifiedText={pageState.verifiedText}
                                                            phase={pageState.phase as 'raw' | 'verifying' | 'complete'}
                                                            isStreaming={pageState.isStreaming}
                                                        />
                                                    </div>
                                                </div>
                                            );
                                        })
                                ) : (
                                    <div className="bg-white rounded-xl border border-surface-200 p-8 text-center">
                                        <Loader2 className="animate-spin mx-auto mb-2 text-primary-500" size={24} />
                                        <p className="text-gray-500">מתמלל...</p>
                                    </div>
                                )}
                            </>
                        )}

                        {/* After streaming completes: Show page-based content with question badges */}
                        {!isStreaming && (
                            <>
                                {streamState.pageStates.size > 0 ? (
                                    Array.from(streamState.pageStates.entries())
                                        .sort(([a], [b]) => a - b)
                                        .filter(([_, state]) => state.rawText || state.verifiedText || state.markedText)
                                        .map(([pageNum, pageState]) => {
                                            // Create a unique key for this page
                                            const pageKey = `page-${pageNum}`;
                                            // Get the text to display (prefer markedText, then verifiedText, then rawText)
                                            const displayText = pageState.markedText || pageState.verifiedText || pageState.rawText;
                                            // Get detected questions for this page
                                            const questions = pageState.detectedQuestions || [];
                                            // Build the header label
                                            const questionLabel = questions.length > 0
                                                ? `שאלה ${questions.join(', ')}`
                                                : '';

                                            return (
                                                <div
                                                    key={pageKey}
                                                    className="bg-white rounded-lg border border-green-200 shadow-sm overflow-hidden"
                                                >
                                                    <div className="flex items-center justify-between px-4 py-2 border-b bg-green-50 border-green-200">
                                                        <div className="flex items-center gap-2">
                                                            <span className="font-medium text-gray-900">עמוד {pageNum}</span>
                                                            {questions.length > 0 && (
                                                                <span className="bg-primary-100 text-primary-700 text-xs px-2 py-0.5 rounded">
                                                                    {questionLabel}
                                                                </span>
                                                            )}
                                                        </div>
                                                        <span className="text-xs text-green-600 flex items-center gap-1">
                                                            <CheckCircle2 size={12} />
                                                            הושלם
                                                        </span>
                                                    </div>
                                                    <div className="p-4">
                                                        <TranscribedTextDisplay
                                                            text={editedTexts[pageKey] ?? displayText.replace(/<Q\d+>/g, '')}
                                                            onChange={(newText) => handleTextChange(pageKey, newText)}
                                                            readOnly={false}
                                                        />
                                                    </div>
                                                </div>
                                            );
                                        })
                                ) : sortedAnswers.length > 0 ? (
                                    /* Fallback: If no pageStates but we have answers, show by question */
                                    sortedAnswers.map((answer) => {
                                        const key = getAnswerKey(answer);
                                        const pageLabel = getPageLabel(answer);

                                        return (
                                            <AnswerEditor
                                                key={key}
                                                answer={answer}
                                                editedText={editedTexts[key] ?? answer.answer_text}
                                                onTextChange={(text) => handleTextChange(key, text)}
                                                pageLabel={pageLabel}
                                                isStreaming={false}
                                            />
                                        );
                                    })
                                ) : (
                                    <div className="bg-white rounded-xl border border-surface-200 p-8 text-center">
                                        <p className="text-gray-500">לא נמצאו תשובות בתמלול</p>
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                </div>
            </div>

            {/* Confirmation Modal */}
            <ConfirmationModal
                isOpen={showConfirmModal}
                onConfirm={handleConfirmedContinue}
                onCancel={() => setShowConfirmModal(false)}
                hasUncertainAnswers={hasUncertainAnswers}
                lowConfidenceCount={lowConfidenceCount}
            />
        </div>
    );
}