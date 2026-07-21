'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'sonner';
import {
    Upload,
    FileText,
    Loader2,
    Check,
    ChevronRight,
    ChevronLeft,
    Download,
    Mail,
    Save,
    Plus,
    Trash2,
    AlertCircle,
    Sparkles,
    Edit3,
} from 'lucide-react';
import {
    saveOntologyRubric,
    isWarningsResponse,
    RubricSaveError,
    shareRubricViaEmail,
    DetectedQuestion,
    ExtractRubricResponse,
    SaveOntologyRubricWarnings,
} from '@/lib/api';
import { RubricEditor } from '@/components/RubricEditor';
import type { RubricQuestion } from '@/types/rubric';
import { hydrateAnyQuestions, dehydrateQuestions } from '@/utils/rubric-transform';
import { SidebarLayout } from '@/components/SidebarLayout';
import { LanguageSelector } from '@/components/LanguageSelector';
import { RubricWarningsModal, RubricErrorDisplay } from '@/components/RubricSaveFlow';
import { hasErrors } from '@/utils/rubric-validation';

// =============================================================================
// Constants & Types
// =============================================================================

// TODO(Sprint 2+): Full ontology migration for rubric-generator page.
// Currently uses ExtractRubricResponse (legacy envelope) + hydrated RubricQuestion[]
// for the editor. The generateCriteria/regenerateQuestion APIs still return legacy
// types. Full migration requires updating those backend endpoints to return
// ontology format, then removing the hydration adapter here.

type WizardStep = 'upload' | 'questions' | 'rubric' | 'share';

const STEPS: { id: WizardStep; label: string; icon: typeof Upload }[] = [
    { id: 'upload', label: 'העלאת קובץ', icon: Upload },
    { id: 'questions', label: 'זיהוי שאלות', icon: FileText },
    { id: 'rubric', label: 'עריכת מחוון', icon: Sparkles },
    { id: 'share', label: 'שמירה ושיתוף', icon: Mail },
];

const DRAFT_STORAGE_KEY = 'rubric_generator_draft';

interface WizardState {
    uploadId: string | null;
    detectedQuestions: DetectedQuestion[];
    generatedRubric: ExtractRubricResponse | null;
    rubricName: string;
    subjectMatter: string;
    programmingLanguage: string;
    savedRubricId: string | null;
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Normalize question points to sum to a target total (default 100).
 * If explicit points are detected from the document, prioritize them.
 * Otherwise, distribute points equally among questions.
 */
function normalizePointsToTotal(
    questions: DetectedQuestion[],
    targetTotal: number = 100
): (DetectedQuestion & { teacher_points: number })[] {
    if (questions.length === 0) return [];

    // Check if any question has explicit points from document
    const questionsWithExplicitPoints = questions.filter(q => q.suggested_points && q.suggested_points > 0);
    const hasExplicitPoints = questionsWithExplicitPoints.length > 0;

    if (hasExplicitPoints) {
        // Use explicit points for questions that have them
        const explicitTotal = questionsWithExplicitPoints.reduce((sum, q) => sum + (q.suggested_points || 0), 0);
        const questionsWithoutPoints = questions.filter(q => !q.suggested_points || q.suggested_points === 0);

        // If explicit points are reasonable (< 150% of target), use them directly
        if (explicitTotal <= targetTotal * 1.5 && explicitTotal >= targetTotal * 0.5) {
            // Distribute remaining points to questions without explicit points
            const remainingPoints = Math.max(0, targetTotal - explicitTotal);
            const pointsPerRemaining = questionsWithoutPoints.length > 0
                ? Math.round(remainingPoints / questionsWithoutPoints.length)
                : 0;

            return questions.map(q => ({
                ...q,
                teacher_points: q.suggested_points && q.suggested_points > 0
                    ? q.suggested_points
                    : pointsPerRemaining || Math.round(targetTotal / questions.length),
            }));
        }
    }

    // No explicit points or unreasonable total - distribute equally
    const pointsPerQuestion = Math.round(targetTotal / questions.length);
    const remainder = targetTotal - (pointsPerQuestion * questions.length);

    return questions.map((q, index) => ({
        ...q,
        teacher_points: pointsPerQuestion + (index < remainder ? 1 : 0),
    }));
}

// =============================================================================
// Celebration Functions
// =============================================================================

const celebrations = {
    uploadComplete: () => {
        toast.success('הקובץ הועלה בהצלחה! 📄', {
            description: 'מזהה שאלות...',
        });
    },
    questionsDetected: (count: number) => {
        toast.success(`נמצאו ${count} שאלות! 🎯`, {
            description: 'ניתן לערוך את הנקודות לפני המשך',
        });
    },
    rubricGenerated: () => {
        toast.success('המחוון נוצר בהצלחה! ✨', {
            description: 'סקרי את הקריטריונים וערכי לפי הצורך',
        });
    },
    rubricSaved: () => {
        toast.success('המחוון נשמר בהצלחה! 🎉', {
            description: 'ניתן למצוא אותו ב"המחוונים שלי"',
        });
    },
    emailSent: (email: string) => {
        toast.success('המייל נשלח בהצלחה! 📧', {
            description: `נשלח ל-${email}`,
        });
    },
};

// =============================================================================
// Main Component
// =============================================================================

export default function RubricGeneratorPage() {
    // Wizard state
    const [currentStep, setCurrentStep] = useState<WizardStep>('upload');
    const [completedSteps, setCompletedSteps] = useState<WizardStep[]>([]);

    // Data state
    const [state, setState] = useState<WizardState>({
        uploadId: null,
        detectedQuestions: [],
        generatedRubric: null,
        rubricName: '',
        subjectMatter: '',
        programmingLanguage: '',
        savedRubricId: null,
    });

    // UI state
    const [isUploading, setIsUploading] = useState(false);
    const [isDetecting, setIsDetecting] = useState(false);
    const [isGenerating, setIsGenerating] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [isSharing, setIsSharing] = useState(false);
    const [progressMessage, setProgressMessage] = useState('');
    const [error, setError] = useState<string | null>(null);

    // Hydrated rubric questions for the editor (RubricQuestion[] with number points).
    // Kept separate from generatedRubric (which holds the raw API response envelope
    // with stats). Synced when generatedRubric.questions changes.
    const [editedQuestions, setEditedQuestions] = useState<RubricQuestion[]>([]);

    // Rubric save warnings/errors state
    const [saveWarnings, setSaveWarnings] = useState<SaveOntologyRubricWarnings | null>(null);
    const [saveError, setSaveError] = useState<RubricSaveError | null>(null);

    // Share form
    const [shareEmail, setShareEmail] = useState('');
    const [senderName, setSenderName] = useState('');

    // File ref
    const fileInputRef = useRef<HTMLInputElement>(null);

    // =============================================================================
    // Draft Auto-Save
    // =============================================================================

    useEffect(() => {
        // Load draft on mount
        const savedDraft = localStorage.getItem(DRAFT_STORAGE_KEY);
        if (savedDraft) {
            try {
                const draft = JSON.parse(savedDraft);
                setState(draft.state);
                setCurrentStep(draft.currentStep);
                setCompletedSteps(draft.completedSteps);
                // Hydrate restored rubric questions for the editor
                if (draft.state?.generatedRubric?.questions) {
                    setEditedQuestions(hydrateAnyQuestions(draft.state.generatedRubric.questions));
                }
                toast.info('טיוטה נטענה', { description: 'ממשיך מהמקום שעצרת' });
            } catch (e) {
                console.warn('Failed to load draft:', e);
            }
        }
    }, []);

    useEffect(() => {
        // Auto-save draft every 10 seconds
        const interval = setInterval(() => {
            if (state.detectedQuestions.length > 0 || state.generatedRubric) {
                localStorage.setItem(
                    DRAFT_STORAGE_KEY,
                    JSON.stringify({
                        state,
                        currentStep,
                        completedSteps,
                        savedAt: new Date().toISOString(),
                    })
                );
            }
        }, 10000);

        return () => clearInterval(interval);
    }, [state, currentStep, completedSteps]);

    const clearDraft = () => {
        localStorage.removeItem(DRAFT_STORAGE_KEY);
    };

    // =============================================================================
    // Navigation
    // =============================================================================

    const stepIndex = STEPS.findIndex((s) => s.id === currentStep);

    const canGoBack = stepIndex > 0;
    const canGoForward =
        stepIndex < STEPS.length - 1 &&
        completedSteps.includes(STEPS[stepIndex].id);

    const goBack = () => {
        if (canGoBack) {
            setCurrentStep(STEPS[stepIndex - 1].id);
        }
    };

    const goForward = () => {
        if (canGoForward) {
            setCurrentStep(STEPS[stepIndex + 1].id);
        }
    };

    const goToStep = (step: WizardStep) => {
        const targetIndex = STEPS.findIndex((s) => s.id === step);
        // Can only go to completed steps or current step
        if (targetIndex <= stepIndex || completedSteps.includes(STEPS[targetIndex - 1]?.id)) {
            setCurrentStep(step);
        }
    };

    // =============================================================================
    // Step 1: Upload
    // =============================================================================

    const handleFileSelect = async (_file: File) => {
        toast.error('פיצ׳ר זה אינו זמין כרגע');
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        toast.error('פיצ׳ר זה אינו זמין כרגע');
    };

    // =============================================================================
    // Step 2: Question Detection
    // =============================================================================

    const startDetection = (_uploadId: string) => {
        // No-op: backend not implemented
    };

    const updateQuestionPoints = (questionNumber: number, points: number) => {
        setState((prev) => ({
            ...prev,
            detectedQuestions: prev.detectedQuestions.map((q) =>
                q.question_number === questionNumber
                    ? { ...q, teacher_points: points }
                    : q
            ),
        }));
    };

    const updateQuestionText = (questionNumber: number, text: string) => {
        setState((prev) => ({
            ...prev,
            detectedQuestions: prev.detectedQuestions.map((q) =>
                q.question_number === questionNumber
                    ? { ...q, question_text: text }
                    : q
            ),
        }));
    };

    const addManualQuestion = () => {
        const newNumber = state.detectedQuestions.length + 1;
        setState((prev) => ({
            ...prev,
            detectedQuestions: [
                ...prev.detectedQuestions,
                {
                    question_number: newNumber,
                    question_text: '',
                    page_indexes: [],
                    sub_questions: [],
                    suggested_points: null,
                    teacher_points: 10,
                },
            ],
        }));
    };

    const removeQuestion = (questionNumber: number) => {
        setState((prev) => ({
            ...prev,
            detectedQuestions: prev.detectedQuestions.filter(
                (q) => q.question_number !== questionNumber
            ),
        }));
    };

    // =============================================================================
    // Step 3: Rubric Generation
    // =============================================================================

    const handleGenerateRubric = async () => {
        toast.error('פיצ׳ר זה אינו זמין כרגע');
    };

    const handleRegenerateQuestion = async (_questionNumber: number) => {
        toast.error('פיצ׳ר זה אינו זמין כרגע');
    };

    const handleRubricChange = (updatedQuestions: RubricQuestion[]) => {
        setEditedQuestions(updatedQuestions);
    };

    // =============================================================================
    // Step 4: Save & Share
    // =============================================================================

    const handleSaveRubric = async (acknowledgedWarningIds: string[] = []) => {
        if (!state.generatedRubric) return;

        // Block save if validation errors exist (INV-R1: point sums don't match)
        if (hasErrors(editedQuestions)) {
            toast.error('יש שגיאות בבדיקת המחוון. אנא תקני את הנקודות לפני שמירה.');
            return;
        }

        setIsSaving(true);
        setSaveError(null);
        setSaveWarnings(null);

        try {
            // Dehydrate: convert number point fields back to strings for backend
            const dehydrated = dehydrateQuestions(editedQuestions);
            const response = await saveOntologyRubric({
                name: state.rubricName || 'מחוון חדש',
                description: state.subjectMatter || undefined,
                draft: {
                    questions: dehydrated,
                    total_points: editedQuestions.reduce((sum, q) => sum + q.total_points, 0),
                    num_questions: editedQuestions.length,
                    num_sub_questions: editedQuestions.reduce((sum, q) => sum + (q.sub_questions?.length || 0), 0),
                    num_criteria: editedQuestions.reduce((sum, q) =>
                        sum + q.criteria.length + (q.sub_questions || []).reduce((s, sq) => s + sq.criteria.length, 0), 0
                    ),
                },
                acknowledged_warning_ids: acknowledgedWarningIds,
            });

            // Check if response contains warnings that need acknowledgment
            if (isWarningsResponse(response)) {
                setSaveWarnings(response);
                setIsSaving(false);
                return;
            }

            // Success - rubric is now saved AND compiled
            setState((prev) => ({ ...prev, savedRubricId: response.rubric_id }));
            setCompletedSteps((prev) => [...prev, 'share']);
            clearDraft();
            celebrations.rubricSaved();
        } catch (e) {
            if (e instanceof RubricSaveError) {
                setSaveError(e);
                toast.error('שגיאה בשמירת המחוון', { description: e.messageHe });
            } else {
                toast.error('שגיאה בשמירה', { description: (e as Error).message });
            }
        } finally {
            setIsSaving(false);
        }
    };

    // Handle warning acknowledgment
    const handleAcknowledgeWarnings = (warningIds: string[]) => {
        setSaveWarnings(null);
        handleSaveRubric(warningIds);
    };

    const handleCancelWarnings = () => {
        setSaveWarnings(null);
    };

    const handleDownloadPdf = async () => {
        toast.error('פיצ׳ר זה אינו זמין כרגע');
    };

    const handleShareEmail = async () => {
        if (!state.savedRubricId || !shareEmail) {
            toast.error('יש לשמור את המחוון ולהזין אימייל');
            return;
        }

        setIsSharing(true);

        try {
            const result = await shareRubricViaEmail(
                state.savedRubricId,
                shareEmail,
                senderName || 'מורה'
            );

            if (result.success) {
                celebrations.emailSent(shareEmail);
                setShareEmail('');
            } else {
                toast.error(result.message);
            }
        } catch (e) {
            toast.error('שגיאה בשליחה', { description: (e as Error).message });
        } finally {
            setIsSharing(false);
        }
    };

    // =============================================================================
    // Render
    // =============================================================================

    return (
        <SidebarLayout>
            <div className="min-h-screen" dir="rtl">
                {/* Page Header */}
                <div className="bg-white border-b border-surface-200 px-6 py-4">
                    <div className="flex items-center justify-between">
                        <h1 className="text-2xl font-bold text-gray-900">
                            יצירת מחוון חדש
                        </h1>

                        {/* Step Progress */}
                        <div className="flex items-center gap-2">
                            {STEPS.map((step, i) => (
                                <button
                                    key={step.id}
                                    onClick={() => goToStep(step.id)}
                                    disabled={i > stepIndex && !completedSteps.includes(STEPS[i - 1]?.id)}
                                    className="flex items-center gap-2"
                                >
                                    <motion.div
                                        initial={{ scale: 0.8, opacity: 0 }}
                                        animate={{
                                            scale: completedSteps.includes(step.id) ? 1 : 0.9,
                                            opacity: 1,
                                        }}
                                        className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${completedSteps.includes(step.id)
                                            ? 'bg-primary-500 text-white'
                                            : currentStep === step.id
                                                ? 'bg-primary-400 text-white'
                                                : 'bg-gray-200 text-gray-500'
                                            }`}
                                    >
                                        {completedSteps.includes(step.id) ? (
                                            <Check className="w-4 h-4" />
                                        ) : (
                                            <span className="text-sm">{i + 1}</span>
                                        )}
                                    </motion.div>
                                    {i < STEPS.length - 1 && (
                                        <div
                                            className={`w-8 h-0.5 ${completedSteps.includes(step.id)
                                                ? 'bg-primary-500'
                                                : 'bg-gray-200'
                                                }`}
                                        />
                                    )}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Navigation Buttons */}
                    <div className="flex items-center justify-between mt-4">
                        <button
                            onClick={goBack}
                            disabled={!canGoBack}
                            className={`flex items-center gap-1 px-3 py-1.5 rounded-lg transition-all ${canGoBack
                                ? 'text-gray-700 hover:bg-gray-100'
                                : 'text-gray-300 cursor-not-allowed'
                                }`}
                        >
                            <ChevronRight className="w-4 h-4" />
                            חזור
                        </button>

                        <span className="text-sm text-gray-500">
                            {STEPS[stepIndex].label} ({stepIndex + 1}/{STEPS.length})
                        </span>

                        <button
                            onClick={goForward}
                            disabled={!canGoForward}
                            className={`flex items-center gap-1 px-3 py-1.5 rounded-lg transition-all ${canGoForward
                                ? 'text-primary-600 hover:bg-primary-50'
                                : 'text-gray-300 cursor-not-allowed'
                                }`}
                        >
                            הבא
                            <ChevronLeft className="w-4 h-4" />
                        </button>
                    </div>
                </div>

                {/* Content */}
                <main className="max-w-6xl mx-auto px-4 py-8">
                    <AnimatePresence mode="wait">
                        {/* Step 1: Upload */}
                        {currentStep === 'upload' && (
                            <motion.div
                                key="upload"
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -20 }}
                                className="max-w-xl mx-auto"
                            >
                                <div
                                    onDragOver={(e) => e.preventDefault()}
                                    onDrop={handleDrop}
                                    onClick={() => fileInputRef.current?.click()}
                                    className={`border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all ${isUploading
                                        ? 'border-primary-400 bg-primary-50'
                                        : 'border-gray-300 hover:border-primary-400 hover:bg-primary-50/50'
                                        }`}
                                >
                                    <input
                                        ref={fileInputRef}
                                        type="file"
                                        accept=".pdf"
                                        onChange={(e) => {
                                            const file = e.target.files?.[0];
                                            if (file) handleFileSelect(file);
                                        }}
                                        className="hidden"
                                    />

                                    {isUploading ? (
                                        <>
                                            <Loader2 className="w-12 h-12 mx-auto text-primary-500 animate-spin mb-4" />
                                            <p className="text-gray-600">מעלה קובץ...</p>
                                        </>
                                    ) : (
                                        <>
                                            <Upload className="w-12 h-12 mx-auto text-gray-400 mb-4" />
                                            <p className="text-lg font-medium text-gray-700 mb-2">
                                                גרור לכאן קובץ PDF או לחץ להעלאה
                                            </p>
                                            <p className="text-sm text-gray-500">
                                                מקסימום 25MB
                                            </p>
                                        </>
                                    )}
                                </div>

                                {error && (
                                    <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700">
                                        <AlertCircle className="w-5 h-5 flex-shrink-0" />
                                        <span>{error}</span>
                                    </div>
                                )}

                                <p className="text-center text-sm text-gray-500 mt-6">
                                    ✓ אחרי העלאה, ה-AI יזהה את השאלות אוטומטית
                                </p>
                            </motion.div>
                        )}

                        {/* Step 2: Questions */}
                        {currentStep === 'questions' && (
                            <motion.div
                                key="questions"
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -20 }}
                            >
                                {isDetecting && (
                                    <div className="text-center mb-6">
                                        <Loader2 className="w-8 h-8 mx-auto text-primary-500 animate-spin mb-2" />
                                        <p className="text-gray-600">{progressMessage}</p>
                                    </div>
                                )}

                                {/* Test Name and Subject Matter - above questions */}
                                {!isDetecting && state.detectedQuestions.length > 0 && (
                                    <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm mb-6">
                                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                            <div>
                                                <label className="block text-sm font-medium text-gray-700 mb-1 text-right">
                                                    שם המבחן / המחוון
                                                </label>
                                                <input
                                                    type="text"
                                                    placeholder="לדוגמה: בוחן לולאות"
                                                    value={state.rubricName}
                                                    onChange={(e) =>
                                                        setState((prev) => ({ ...prev, rubricName: e.target.value }))
                                                    }
                                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-right focus:border-primary-400 focus:ring-1 focus:ring-primary-200 outline-none"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-sm font-medium text-gray-700 mb-1 text-right">
                                                    תיאור נושא המבחן
                                                </label>
                                                <input
                                                    type="text"
                                                    placeholder="לדוגמה: לולאות בתכנות מונחה עצמים"
                                                    value={state.subjectMatter}
                                                    onChange={(e) =>
                                                        setState((prev) => ({ ...prev, subjectMatter: e.target.value }))
                                                    }
                                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-right focus:border-primary-400 focus:ring-1 focus:ring-primary-200 outline-none"
                                                />
                                            </div>
                                            <LanguageSelector
                                                value={state.programmingLanguage}
                                                onChange={(lang) =>
                                                    setState((prev) => ({ ...prev, programmingLanguage: lang }))
                                                }
                                            />
                                        </div>
                                        <p className="text-xs text-gray-500 mt-2 text-right">
                                            בחירת שפת תכנות תעזור למערכת להתאים את הבדיקה למוסכמות השפה
                                        </p>
                                    </div>
                                )}

                                <div className="space-y-4">
                                    {state.detectedQuestions.map((question) => (
                                        <motion.div
                                            key={question.question_number}
                                            initial={{ opacity: 0, y: 10 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm"
                                        >
                                            {/* Header row with question number and points */}
                                            <div className="flex items-center justify-between mb-3">
                                                <div className="flex items-center gap-2">
                                                    <span className="px-2 py-0.5 bg-primary-100 text-primary-700 rounded-md text-sm font-medium">
                                                        שאלה {question.question_number}
                                                    </span>
                                                    {question.sub_questions.length > 0 && (
                                                        <span className="text-xs text-gray-500">
                                                            סעיפים: {question.sub_questions.join(', ')}
                                                        </span>
                                                    )}
                                                    <span className="text-xs text-primary-600 flex items-center gap-1">
                                                        <Check className="w-3 h-3" />
                                                        נמצאה
                                                    </span>
                                                </div>

                                                <div className="flex items-center gap-3">
                                                    <div className="flex items-center gap-1">
                                                        <span className="text-sm text-gray-500">נקודות:</span>
                                                        <input
                                                            type="number"
                                                            min="1"
                                                            max="100"
                                                            value={question.teacher_points || question.suggested_points || 10}
                                                            onChange={(e) =>
                                                                updateQuestionPoints(
                                                                    question.question_number,
                                                                    parseInt(e.target.value) || 10
                                                                )
                                                            }
                                                            className="w-16 px-2 py-1 border border-gray-300 rounded-lg text-center text-sm focus:border-primary-400 focus:ring-1 focus:ring-primary-200 outline-none"
                                                        />
                                                        {question.suggested_points && question.suggested_points !== question.teacher_points && (
                                                            <span className="text-xs text-gray-400">
                                                                (מקור: {question.suggested_points})
                                                            </span>
                                                        )}
                                                    </div>

                                                    <button
                                                        onClick={() => removeQuestion(question.question_number)}
                                                        className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                                                        title="הסר שאלה"
                                                    >
                                                        <Trash2 className="w-4 h-4" />
                                                    </button>
                                                </div>
                                            </div>

                                            {/* Editable question text */}
                                            <textarea
                                                value={question.question_text || ''}
                                                onChange={(e) => updateQuestionText(question.question_number, e.target.value)}
                                                placeholder="טקסט השאלה..."
                                                rows={Math.max(3, Math.min(10, (question.question_text?.split('\n').length || 1) + 1))}
                                                className="w-full px-3 py-2 text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded-lg resize-y focus:border-primary-400 focus:ring-1 focus:ring-primary-200 focus:bg-white outline-none transition-colors whitespace-pre-wrap font-mono leading-relaxed"
                                                style={{
                                                    minHeight: '80px',
                                                    whiteSpace: 'pre-wrap',
                                                    tabSize: 4,
                                                }}
                                            />
                                        </motion.div>
                                    ))}

                                    {!isDetecting && (
                                        <button
                                            onClick={addManualQuestion}
                                            className="w-full py-3 border-2 border-dashed border-gray-300 rounded-xl text-gray-500 hover:border-primary-400 hover:text-primary-600 hover:bg-primary-50/50 transition-all flex items-center justify-center gap-2"
                                        >
                                            <Plus className="w-4 h-4" />
                                            הוסף שאלה ידנית
                                        </button>
                                    )}
                                </div>

                                {state.detectedQuestions.length > 0 && !isDetecting && (
                                    <div className="mt-8 text-center">
                                        {/* Total points indicator */}
                                        {(() => {
                                            const totalPoints = state.detectedQuestions.reduce(
                                                (sum, q) => sum + (q.teacher_points || q.suggested_points || 0),
                                                0
                                            );
                                            const isCorrect = totalPoints === 100;
                                            return (
                                                <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg mb-4 ${isCorrect
                                                    ? 'bg-primary-50 text-primary-700'
                                                    : 'bg-amber-50 text-amber-700'
                                                    }`}>
                                                    <span className="text-sm font-medium">
                                                        סה"כ נקודות: {totalPoints}
                                                    </span>
                                                    {!isCorrect && (
                                                        <span className="text-xs">
                                                            ({totalPoints > 100 ? `+${totalPoints - 100}` : totalPoints - 100})
                                                        </span>
                                                    )}
                                                    {isCorrect && <Check className="w-4 h-4" />}
                                                </div>
                                            );
                                        })()}

                                        <div className="flex justify-center">
                                            <button
                                                onClick={handleGenerateRubric}
                                                disabled={isGenerating}
                                                className="px-6 py-3 bg-gradient-to-r from-violet-500 to-primary-500 text-white font-medium rounded-xl shadow-lg hover:shadow-xl transition-all disabled:opacity-50 flex items-center gap-2"
                                            >
                                                {isGenerating ? (
                                                    <>
                                                        <Loader2 className="w-5 h-5 animate-spin" />
                                                        יוצר קריטריונים...
                                                    </>
                                                ) : (
                                                    <>
                                                        <Sparkles className="w-5 h-5" />
                                                        יצירת מחוון
                                                    </>
                                                )}
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </motion.div>
                        )}

                        {/* Step 3: Rubric Editor */}
                        {currentStep === 'rubric' && state.generatedRubric && (
                            <motion.div
                                key="rubric"
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -20 }}
                            >
                                <RubricEditor
                                    questions={editedQuestions}
                                    onQuestionsChange={handleRubricChange}
                                    pages={[]}
                                />

                                <div className="mt-8 text-center">
                                    <button
                                        onClick={() => setCurrentStep('share')}
                                        className="px-6 py-3 bg-gradient-to-r from-primary-500 to-accent-500 text-white font-medium rounded-xl shadow-lg hover:shadow-xl transition-all flex items-center gap-2 mx-auto"
                                    >
                                        <ChevronLeft className="w-5 h-5" />
                                        המשך לשמירה ושיתוף
                                    </button>
                                </div>
                            </motion.div>
                        )}

                        {/* Step 4: Save & Share */}
                        {currentStep === 'share' && state.generatedRubric && (
                            <motion.div
                                key="share"
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -20 }}
                                className="max-w-xl mx-auto"
                            >
                                {/* Summary Card */}
                                <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm mb-6">
                                    <h3 className="text-lg font-semibold text-gray-800 mb-4">
                                        📋 סיכום המחוון
                                    </h3>

                                    <input
                                        type="text"
                                        placeholder="שם המחוון"
                                        value={state.rubricName}
                                        onChange={(e) =>
                                            setState((prev) => ({ ...prev, rubricName: e.target.value }))
                                        }
                                        className="w-full px-4 py-2 border border-gray-300 rounded-lg mb-4"
                                    />

                                    <div className="flex items-center justify-around text-center">
                                        <div>
                                            <div className="text-2xl font-bold text-primary-600">
                                                {state.generatedRubric.num_questions}
                                            </div>
                                            <div className="text-sm text-gray-500">שאלות</div>
                                        </div>
                                        <div className="h-8 w-px bg-gray-200" />
                                        <div>
                                            <div className="text-2xl font-bold text-primary-600">
                                                {state.generatedRubric.num_criteria}
                                            </div>
                                            <div className="text-sm text-gray-500">קריטריונים</div>
                                        </div>
                                        <div className="h-8 w-px bg-gray-200" />
                                        <div>
                                            <div className="text-2xl font-bold text-primary-600">
                                                {state.generatedRubric.total_points}
                                            </div>
                                            <div className="text-sm text-gray-500">נקודות</div>
                                        </div>
                                    </div>
                                </div>

                                {/* Save Section */}
                                <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm mb-6">
                                    <h3 className="text-lg font-semibold text-gray-800 mb-4">
                                        💾 שמירה
                                    </h3>

                                    <div className="space-y-3">
                                        <button
                                            onClick={() => handleSaveRubric()}
                                            disabled={isSaving || !!state.savedRubricId}
                                            className={`w-full py-3 rounded-xl font-medium flex items-center justify-center gap-2 transition-all ${state.savedRubricId
                                                ? 'bg-green-100 text-green-700'
                                                : 'bg-primary-500 text-white hover:bg-primary-600'
                                                }`}
                                        >
                                            {isSaving ? (
                                                <Loader2 className="w-5 h-5 animate-spin" />
                                            ) : state.savedRubricId ? (
                                                <>
                                                    <Check className="w-5 h-5" />
                                                    נשמר בהצלחה!
                                                </>
                                            ) : (
                                                <>
                                                    <Save className="w-5 h-5" />
                                                    שמור במחוונים שלי
                                                </>
                                            )}
                                        </button>

                                        <button
                                            onClick={handleDownloadPdf}
                                            className="w-full py-3 border border-gray-300 rounded-xl text-gray-700 hover:bg-gray-50 font-medium flex items-center justify-center gap-2 transition-all"
                                        >
                                            <Download className="w-5 h-5" />
                                            הורד PDF עם טבלאות מחוון
                                        </button>
                                    </div>
                                </div>

                                {/* Share Section */}
                                <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
                                    <h3 className="text-lg font-semibold text-gray-800 mb-4">
                                        📧 שיתוף עם מורה אחר
                                    </h3>

                                    <div className="space-y-3">
                                        <input
                                            type="text"
                                            placeholder="השם שלך (יופיע במייל)"
                                            value={senderName}
                                            onChange={(e) => setSenderName(e.target.value)}
                                            className="w-full px-4 py-2 border border-gray-300 rounded-lg"
                                        />

                                        <input
                                            type="email"
                                            placeholder="אימייל של המורה"
                                            value={shareEmail}
                                            onChange={(e) => setShareEmail(e.target.value)}
                                            className="w-full px-4 py-2 border border-gray-300 rounded-lg"
                                        />

                                        <button
                                            onClick={handleShareEmail}
                                            disabled={isSharing || !state.savedRubricId || !shareEmail}
                                            className="w-full py-3 bg-green-500 text-white rounded-xl font-medium flex items-center justify-center gap-2 hover:bg-green-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                                        >
                                            {isSharing ? (
                                                <Loader2 className="w-5 h-5 animate-spin" />
                                            ) : (
                                                <>
                                                    <Mail className="w-5 h-5" />
                                                    שלח במייל
                                                </>
                                            )}
                                        </button>

                                        {!state.savedRubricId && (
                                            <p className="text-sm text-amber-600 text-center">
                                                יש לשמור את המחוון לפני שיתוף
                                            </p>
                                        )}

                                        <p className="text-sm text-gray-500 text-center mt-2">
                                            ℹ️ המורה יקבל קישור להורדה + הזמנה להצטרף ל-Vivi
                                        </p>
                                    </div>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </main>
            </div>

            {/* Warnings Modal */}
            {saveWarnings && (
                <RubricWarningsModal
                    warnings={saveWarnings.warnings}
                    messageHe={saveWarnings.message_he}
                    questions={editedQuestions}
                    onAcknowledge={handleAcknowledgeWarnings}
                    onCancel={handleCancelWarnings}
                    isSubmitting={isSaving}
                />
            )}

            {/* Error Display - shown in a fixed position */}
            {saveError && (
                <div className="fixed bottom-4 left-4 right-4 max-w-lg mx-auto z-40">
                    <RubricErrorDisplay
                        error={saveError}
                        questions={editedQuestions}
                        onDismiss={() => setSaveError(null)}
                    />
                </div>
            )}
        </SidebarLayout >
    );
}
