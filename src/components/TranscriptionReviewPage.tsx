'use client';

import { useState, useMemo } from 'react';
import {
    FileText,
    Edit3,
    Check,
    X,
    AlertTriangle,
    ChevronLeft,
    ChevronRight,
    Loader2,
    Eye,
} from 'lucide-react';
import type {
    TranscriptionReviewResponse,
    TranscribedAnswerWithPages,
    StudentAnswerInput,
    PagePreview,
} from '@/lib/api';

interface TranscriptionReviewPageProps {
    transcriptionData: TranscriptionReviewResponse;
    onContinueToGrading: (editedAnswers: StudentAnswerInput[]) => void;
    onBack: () => void;
    isGrading?: boolean;
}

// Confidence badge component
function ConfidenceBadge({ confidence }: { confidence: number }) {
    const percent = Math.round(confidence * 100);
    let colorClass = 'bg-green-100 text-green-700 border-green-200';
    let icon = <Check size={12} />;

    if (percent < 70) {
        colorClass = 'bg-red-100 text-red-700 border-red-200';
        icon = <AlertTriangle size={12} />;
    } else if (percent < 85) {
        colorClass = 'bg-amber-100 text-amber-700 border-amber-200';
        icon = <AlertTriangle size={12} />;
    }

    return (
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${colorClass}`}>
            {icon}
            {percent}%
        </span>
    );
}

// Single answer editor - displays full text
function AnswerEditor({
    answer,
    isEditing,
    editedText,
    onStartEdit,
    onCancelEdit,
    onSaveEdit,
    onTextChange,
}: {
    answer: TranscribedAnswerWithPages;
    isEditing: boolean;
    editedText: string;
    onStartEdit: () => void;
    onCancelEdit: () => void;
    onSaveEdit: () => void;
    onTextChange: (text: string) => void;
}) {
    const questionLabel = answer.sub_question_id
        ? `שאלה ${answer.question_number} - סעיף ${answer.sub_question_id}`
        : `שאלה ${answer.question_number}`;

    // Calculate dynamic height based on content
    const lineCount = (answer.answer_text || '').split('\n').length;
    const minHeight = Math.max(120, lineCount * 20 + 40);

    return (
        <div className="bg-white rounded-lg border border-surface-200 overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-2 bg-surface-50 border-b border-surface-200">
                <span className="font-medium text-gray-900">{questionLabel}</span>
                <div className="flex items-center gap-2">
                    <ConfidenceBadge confidence={answer.confidence} />
                    {!isEditing ? (
                        <button
                            onClick={onStartEdit}
                            className="p-1.5 text-primary-600 hover:bg-primary-50 rounded transition-colors"
                            title="עריכה"
                        >
                            <Edit3 size={16} />
                        </button>
                    ) : (
                        <div className="flex items-center gap-1">
                            <button
                                onClick={onSaveEdit}
                                className="p-1.5 text-green-600 hover:bg-green-50 rounded transition-colors"
                                title="שמור"
                            >
                                <Check size={16} />
                            </button>
                            <button
                                onClick={onCancelEdit}
                                className="p-1.5 text-red-600 hover:bg-red-50 rounded transition-colors"
                                title="בטל"
                            >
                                <X size={16} />
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* Content - Full text display */}
            <div className="p-4">
                {isEditing ? (
                    <textarea
                        value={editedText}
                        onChange={(e) => onTextChange(e.target.value)}
                        className="w-full p-3 font-mono text-sm bg-surface-50 border border-surface-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 resize-y"
                        dir="ltr"
                        style={{ minHeight: `${minHeight}px`, whiteSpace: 'pre-wrap' }}
                    />
                ) : (
                    <pre
                        className="whitespace-pre-wrap font-mono text-sm text-gray-800 bg-surface-50 p-3 rounded-lg"
                        dir="ltr"
                    >
                        {answer.answer_text || <span className="text-gray-400 italic">אין תוכן</span>}
                    </pre>
                )}

                {/* Transcription notes */}
                {answer.transcription_notes && (
                    <p className="mt-2 text-xs text-amber-600 flex items-center gap-1">
                        <AlertTriangle size={12} />
                        {answer.transcription_notes}
                    </p>
                )}
            </div>
        </div>
    );
}

// Main component
export function TranscriptionReviewPage({
    transcriptionData,
    onContinueToGrading,
    onBack,
    isGrading = false,
}: TranscriptionReviewPageProps) {
    const [editingAnswerKey, setEditingAnswerKey] = useState<string | null>(null);
    const [editedTexts, setEditedTexts] = useState<Record<string, string>>({});

    // Build initial answers from transcription data
    const [answers, setAnswers] = useState<TranscribedAnswerWithPages[]>(
        transcriptionData.answers
    );

    // Get answer key for tracking
    const getAnswerKey = (ans: TranscribedAnswerWithPages) =>
        `${ans.question_number}-${ans.sub_question_id || 'main'}`;

    // Handle edit operations
    const startEdit = (answer: TranscribedAnswerWithPages) => {
        const key = getAnswerKey(answer);
        setEditingAnswerKey(key);
        setEditedTexts(prev => ({ ...prev, [key]: answer.answer_text }));
    };

    const cancelEdit = () => {
        setEditingAnswerKey(null);
    };

    const saveEdit = (answer: TranscribedAnswerWithPages) => {
        const key = getAnswerKey(answer);
        const newText = editedTexts[key];

        setAnswers(prev => prev.map(a =>
            getAnswerKey(a) === key
                ? { ...a, answer_text: newText, confidence: 1.0 } // User-edited = 100% confidence
                : a
        ));

        setEditingAnswerKey(null);
    };

    // Handle continue to grading
    const handleContinue = () => {
        const editedAnswers: StudentAnswerInput[] = answers.map(a => ({
            question_number: a.question_number,
            sub_question_id: a.sub_question_id,
            answer_text: a.answer_text,
        }));
        onContinueToGrading(editedAnswers);
    };

    // Count low confidence answers
    const lowConfidenceCount = useMemo(
        () => answers.filter(a => a.confidence < 0.85).length,
        [answers]
    );

    return (
        <div className="min-h-screen bg-gradient-to-br from-surface-50 via-primary-50/20 to-surface-100">
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
                                    {transcriptionData.student_name} • {transcriptionData.filename}
                                </p>
                            </div>
                        </div>

                        <div className="flex items-center gap-3">
                            {lowConfidenceCount > 0 && (
                                <div className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-50 text-amber-700 rounded-lg text-sm">
                                    <AlertTriangle size={14} />
                                    {lowConfidenceCount} תמלולים בביטחון נמוך
                                </div>
                            )}

                            <button
                                onClick={handleContinue}
                                disabled={isGrading}
                                className="flex items-center gap-2 px-5 py-2.5 bg-primary-500 text-white rounded-lg font-medium hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                            >
                                {isGrading ? (
                                    <>
                                        <Loader2 className="animate-spin" size={18} />
                                        מדרג...
                                    </>
                                ) : (
                                    <>
                                        המשך לדירוג
                                        <ChevronLeft size={18} />
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Column Headers - Fixed below main header */}
            <div className="bg-white/95 backdrop-blur-sm border-b border-surface-200 sticky top-[73px] z-10">
                <div className="max-w-7xl mx-auto px-6 py-3">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                            <FileText className="text-primary-600" size={20} />
                            מבחן מקורי
                            <span className="text-sm font-normal text-gray-500">
                                ({transcriptionData.pages.length} עמודים)
                            </span>
                        </h2>
                        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                            <Eye className="text-primary-600" size={20} />
                            תמלול AI
                            <span className="text-sm font-normal text-gray-500">
                                ({answers.length} תשובות)
                            </span>
                        </h2>
                    </div>
                </div>
            </div>

            {/* Main content - Two panels that scroll together */}
            <div className="max-w-7xl mx-auto p-6">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Left Panel - PDF Pages stacked vertically */}
                    <div className="space-y-4">
                        {transcriptionData.pages.map((page) => (
                            <div
                                key={page.page_index}
                                className="bg-white rounded-xl border border-surface-200 p-4"
                            >
                                <div className="text-sm text-gray-500 mb-2 font-medium">
                                    עמוד {page.page_number}
                                </div>
                                <img
                                    src={`data:image/png;base64,${page.thumbnail_base64}`}
                                    alt={`עמוד ${page.page_number}`}
                                    className="w-full h-auto rounded border border-surface-100"
                                />
                            </div>
                        ))}
                    </div>

                    {/* Right Panel - Transcriptions (full text) */}
                    <div className="space-y-4">
                        {answers.map((answer) => {
                            const key = getAnswerKey(answer);
                            const isEditing = editingAnswerKey === key;

                            return (
                                <AnswerEditor
                                    key={key}
                                    answer={answer}
                                    isEditing={isEditing}
                                    editedText={editedTexts[key] || answer.answer_text}
                                    onStartEdit={() => startEdit(answer)}
                                    onCancelEdit={cancelEdit}
                                    onSaveEdit={() => saveEdit(answer)}
                                    onTextChange={(text) => setEditedTexts(prev => ({ ...prev, [key]: text }))}
                                />
                            );
                        })}
                    </div>
                </div>
            </div>
        </div>
    );
}

