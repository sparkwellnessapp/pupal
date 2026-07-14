'use client';

import { useState, useRef, useEffect } from 'react';
import { Loader2, ChevronRight, SkipForward, FileText, HelpCircle } from 'lucide-react';
import type { DocxPreflightQuestion } from '@/lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface RubricPurposeValues {
    testTopic: string;
    /** Keyed by question_number (as string) */
    questionPurposes: Record<string, string>;
}

interface RubricPurposeProps {
    /** Questions returned by the preflight scan */
    questions: DocxPreflightQuestion[];
    /** Auto-detected title from the document (shown as placeholder) */
    detectedTitle: string | null;
    /** Called when user clicks "Save and Continue" */
    onConfirm: (values: RubricPurposeValues) => void;
    /** Called when user clicks "Skip" — pipeline runs with no purposes */
    onSkip: () => void;
    /** Disable form while parent is loading */
    isLoading?: boolean;
}

// ---------------------------------------------------------------------------
// QuestionTooltip — a "?" icon that shows a floating text popup on hover
// ---------------------------------------------------------------------------

function QuestionTooltip({ text }: { text: string }) {
    const [visible, setVisible] = useState(false);
    const [pos, setPos] = useState<{ top: number; left: number }>({ top: 0, left: 0 });
    const iconRef = useRef<HTMLButtonElement>(null);
    const tooltipRef = useRef<HTMLDivElement>(null);

    const show = () => {
        if (!iconRef.current) return;
        const rect = iconRef.current.getBoundingClientRect();
        setPos({ top: rect.top, left: rect.left });
        setVisible(true);
    };

    const hide = () => setVisible(false);

    // Adjust tooltip so it never clips the right edge of the viewport
    useEffect(() => {
        if (!visible || !tooltipRef.current) return;
        const tip = tooltipRef.current.getBoundingClientRect();
        if (tip.right > window.innerWidth - 16) {
            tooltipRef.current.style.left = `${window.innerWidth - tip.width - 16}px`;
        }
    }, [visible, pos]);

    return (
        <>
            <button
                ref={iconRef}
                type="button"
                onMouseEnter={show}
                onMouseLeave={hide}
                onFocus={show}
                onBlur={hide}
                className="inline-flex items-center justify-center w-5 h-5 rounded-full text-gray-400 hover:text-primary-500 hover:bg-primary-50 transition-colors shrink-0 focus:outline-none"
                aria-label="Show question text"
                tabIndex={0}
            >
                <HelpCircle size={14} strokeWidth={2} />
            </button>

            {visible && (
                <div
                    ref={tooltipRef}
                    role="tooltip"
                    style={{
                        position: 'fixed',
                        top: pos.top - 8,
                        left: pos.left + 24,
                        transform: 'translateY(-100%)',
                        zIndex: 9999,
                        maxWidth: '340px',
                        width: 'max-content',
                    }}
                    className="pointer-events-none bg-gray-900 text-gray-100 text-xs leading-relaxed rounded-lg px-3.5 py-2.5 shadow-xl"
                    dir="auto"
                >
                    {/* Arrow */}
                    <span
                        style={{
                            position: 'absolute',
                            bottom: '-5px',
                            left: '10px',
                            width: '10px',
                            height: '10px',
                            background: '#111827',
                            transform: 'rotate(45deg)',
                            borderRadius: '2px',
                        }}
                    />
                    {text}
                </div>
            )}
        </>
    );
}

// ---------------------------------------------------------------------------
// Inline short label — first ~25 chars of the question text
// ---------------------------------------------------------------------------

function QuestionSnippet({ text }: { text: string }) {
    if (!text) return null;
    const snippet = text.length > 28 ? text.slice(0, 25).trimEnd() + '…' : text;
    return (
        <span className="text-xs text-gray-400 truncate" dir="auto">
            {snippet}
        </span>
    );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RubricPurpose({
    questions,
    detectedTitle,
    onConfirm,
    onSkip,
    isLoading = false,
}: RubricPurposeProps) {
    const [testTopic, setTestTopic] = useState('');
    const [questionPurposes, setQuestionPurposes] = useState<Record<string, string>>({});

    const handlePurposeChange = (questionNumber: number, value: string) => {
        setQuestionPurposes(prev => ({
            ...prev,
            [String(questionNumber)]: value,
        }));
    };

    const handleConfirm = () => {
        // Only include questions that actually have a non-empty purpose
        const filteredPurposes: Record<string, string> = {};
        for (const [key, val] of Object.entries(questionPurposes)) {
            if (val.trim()) filteredPurposes[key] = val.trim();
        }
        onConfirm({
            testTopic: testTopic.trim(),
            questionPurposes: filteredPurposes,
        });
    };

    return (
        <div className="bg-white rounded-xl border border-surface-200 p-6">
            {/* Header */}
            <div className="flex items-start gap-3 mb-6">
                <div className="w-10 h-10 rounded-lg bg-primary-100 flex items-center justify-center shrink-0">
                    <FileText size={20} className="text-primary-600" />
                </div>
                <div>
                    <h2 className="text-lg font-semibold text-gray-900">הגדרת מטרות שאלות (אופציונלי)</h2>
                    <p className="text-sm text-gray-500 mt-0.5">
                        ניתן להוסיף הסברים שיעזרו לבינה המלאכותית להבין את מטרת כל שאלה.
                        שדות ריקים יסיק הבינה המלאכותית בעצמה.
                    </p>
                </div>
            </div>

            {/* Test topic */}
            <div className="mb-5">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                    נושא המבחן / כותרת
                </label>
                <input
                    type="text"
                    value={testTopic}
                    onChange={e => setTestTopic(e.target.value)}
                    disabled={isLoading}
                    placeholder={detectedTitle || 'לדוגמה: מבחן מיון — מבני נתונים'}
                    className="w-full px-4 py-2.5 border border-surface-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-50"
                />
                <p className="text-xs text-gray-400 mt-1">
                    {detectedTitle
                        ? `זוהה אוטומטית: "${detectedTitle}" — ניתן לשנות`
                        : 'נושא זה יעקוף את הכותרת שזוהתה אוטומטית'}
                </p>
            </div>

            {/* Per-question purposes */}
            {questions.length > 0 && (
                <div className="space-y-3 mb-6">
                    <h3 className="text-sm font-semibold text-gray-700">מטרת כל שאלה</h3>
                    {questions.map(q => (
                        <div key={q.question_number} className="bg-surface-50 rounded-lg p-4 border border-surface-200">
                            {/* Question header row: badge · snippet · tooltip icon */}
                            <div className="flex items-center gap-2 mb-2 min-w-0">
                                <span className="text-xs font-semibold text-primary-600 bg-primary-100 px-2 py-0.5 rounded-full shrink-0 whitespace-nowrap">
                                    שאלה {q.question_number}
                                </span>
                                {q.full_text_preview && (
                                    <>
                                        <QuestionSnippet text={q.full_text_preview} />
                                        <QuestionTooltip text={q.full_text_preview} />
                                    </>
                                )}
                            </div>
                            <textarea
                                value={questionPurposes[String(q.question_number)] || ''}
                                onChange={e => handlePurposeChange(q.question_number, e.target.value)}
                                disabled={isLoading}
                                placeholder="מטרת השאלה (אם תשאיר ריק, הבינה המלאכותית תסיק זאת)"
                                rows={2}
                                className="w-full px-3 py-2 text-sm border border-surface-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-50"
                            />
                        </div>
                    ))}
                </div>
            )}

            {/* Actions */}
            <div className="flex items-center justify-between pt-4 border-t border-surface-100">
                <button
                    onClick={onSkip}
                    disabled={isLoading}
                    className="flex items-center gap-2 px-4 py-2 text-gray-500 hover:text-gray-700 hover:bg-surface-100 rounded-lg transition-colors disabled:opacity-40 text-sm"
                >
                    <SkipForward size={16} />
                    דלג — הבינה המלאכותית תסיק הכל
                </button>

                <button
                    onClick={handleConfirm}
                    disabled={isLoading}
                    className="flex items-center gap-2 px-5 py-2.5 bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 transition-colors text-sm font-medium"
                >
                    {isLoading ? (
                        <Loader2 className="animate-spin" size={16} />
                    ) : (
                        <ChevronRight size={16} />
                    )}
                    {isLoading ? 'מחלץ מחוון...' : 'המשך לחילוץ'}
                </button>
            </div>
        </div>
    );
}
