'use client';

/**
 * Flagged Items Review Component
 *
 * Focused review mode for items flagged by AI.
 * Supports keyboard navigation (j/k/Enter) for efficient review.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    ChevronLeft,
    ChevronRight,
    CheckCircle,
    Flag,
    AlertTriangle,
    X,
    Keyboard,
    Eye,
    Edit3,
} from 'lucide-react';
import type {
    GradedTestDraft,
    FlaggedOutcome,
    RuleOutcome,
    QuestionOutcome,
    CriterionOutcome,
} from '@/lib/ontology-types';
import { formatPoints, getFlagReasonLabel } from '@/lib/api';
import {
    ConfidenceIndicator,
    QuoteDisplay,
    NeedsReviewBadge,
    ScoreDisplay,
} from './grading/QualitySignals';
import { ScoreOverrideModal } from './ScoreOverrideModal';

// =============================================================================
// TYPES
// =============================================================================

interface FlaggedItemsReviewProps {
    /** The graded test draft to review */
    draft: GradedTestDraft;
    /** Callback when an item is approved without changes */
    onApprove: (flaggedItem: FlaggedOutcome) => void;
    /** Callback when a score is overridden */
    onOverride: (
        flaggedItem: FlaggedOutcome,
        newPoints: number,
        reason: string
    ) => void;
    /** Callback when review is complete */
    onComplete: () => void;
    /** Callback to close review mode */
    onClose: () => void;
    /** Additional CSS classes */
    className?: string;
}

interface ReviewableItem {
    flaggedOutcome: FlaggedOutcome;
    questionOutcome: QuestionOutcome;
    criterionOutcome: CriterionOutcome;
    ruleOutcome: RuleOutcome;
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function FlaggedItemsReview({
    draft,
    onApprove,
    onOverride,
    onComplete,
    onClose,
    className = '',
}: FlaggedItemsReviewProps) {
    const [currentIndex, setCurrentIndex] = useState(0);
    const [reviewedItems, setReviewedItems] = useState<Set<string>>(new Set());
    const [showOverrideModal, setShowOverrideModal] = useState(false);
    const [showKeyboardHelp, setShowKeyboardHelp] = useState(false);

    const containerRef = useRef<HTMLDivElement>(null);

    // Build flat list of reviewable items
    const reviewableItems: ReviewableItem[] = [];
    draft.flagged_outcomes.forEach((flagged) => {
        // Find the corresponding data in the hierarchy
        for (const qo of draft.question_outcomes) {
            if (qo.question_id === flagged.question_id) {
                for (const co of qo.criterion_outcomes) {
                    if (co.criterion_id === flagged.criterion_id) {
                        for (const ro of co.rule_outcomes) {
                            if (ro.rule_id === flagged.rule_id) {
                                reviewableItems.push({
                                    flaggedOutcome: flagged,
                                    questionOutcome: qo,
                                    criterionOutcome: co,
                                    ruleOutcome: ro,
                                });
                            }
                        }
                    }
                }
            }
        }
    });

    const currentItem = reviewableItems[currentIndex];
    const totalItems = reviewableItems.length;
    const reviewedCount = reviewedItems.size;
    const isAllReviewed = reviewedCount === totalItems;

    // Get unique item key
    const getItemKey = (item: FlaggedOutcome) =>
        `${item.question_id}-${item.criterion_id}-${item.rule_id}`;

    // Navigation
    const goNext = useCallback(() => {
        if (currentIndex < totalItems - 1) {
            setCurrentIndex(currentIndex + 1);
        }
    }, [currentIndex, totalItems]);

    const goPrev = useCallback(() => {
        if (currentIndex > 0) {
            setCurrentIndex(currentIndex - 1);
        }
    }, [currentIndex]);

    // Actions
    const handleApprove = useCallback(() => {
        if (!currentItem) return;

        const key = getItemKey(currentItem.flaggedOutcome);
        setReviewedItems((prev) => new Set(prev).add(key));
        onApprove(currentItem.flaggedOutcome);

        // Auto-advance to next unreviewed item
        if (currentIndex < totalItems - 1) {
            goNext();
        }
    }, [currentItem, currentIndex, totalItems, onApprove, goNext]);

    const handleOverride = useCallback(
        (newPoints: number, reason: string) => {
            if (!currentItem) return;

            const key = getItemKey(currentItem.flaggedOutcome);
            setReviewedItems((prev) => new Set(prev).add(key));
            onOverride(currentItem.flaggedOutcome, newPoints, reason);
            setShowOverrideModal(false);

            // Auto-advance
            if (currentIndex < totalItems - 1) {
                goNext();
            }
        },
        [currentItem, currentIndex, totalItems, onOverride, goNext]
    );

    const handleComplete = useCallback(() => {
        onComplete();
    }, [onComplete]);

    // Keyboard navigation
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Don't capture if modal is open or typing in input
            if (
                showOverrideModal ||
                (e.target as HTMLElement).tagName === 'INPUT' ||
                (e.target as HTMLElement).tagName === 'TEXTAREA'
            ) {
                return;
            }

            switch (e.key) {
                case 'j':
                case 'ArrowDown':
                    e.preventDefault();
                    goNext();
                    break;
                case 'k':
                case 'ArrowUp':
                    e.preventDefault();
                    goPrev();
                    break;
                case 'Enter':
                    e.preventDefault();
                    handleApprove();
                    break;
                case 'e':
                    e.preventDefault();
                    setShowOverrideModal(true);
                    break;
                case '?':
                    e.preventDefault();
                    setShowKeyboardHelp(!showKeyboardHelp);
                    break;
                case 'Escape':
                    if (showKeyboardHelp) {
                        setShowKeyboardHelp(false);
                    } else {
                        onClose();
                    }
                    break;
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [
        goNext,
        goPrev,
        handleApprove,
        showOverrideModal,
        showKeyboardHelp,
        onClose,
    ]);

    // Focus container on mount
    useEffect(() => {
        containerRef.current?.focus();
    }, []);

    if (totalItems === 0) {
        return (
            <div className={`bg-white rounded-2xl shadow-lg p-8 text-center ${className}`}>
                <CheckCircle size={64} className="mx-auto mb-4 text-emerald-500" />
                <h2 className="text-xl font-bold text-gray-800 mb-2">אין פריטים לבדיקה!</h2>
                <p className="text-gray-500 mb-4">כל הפריטים נבדקו בביטחון גבוה</p>
                <button
                    onClick={onClose}
                    className="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors"
                >
                    חזרה
                </button>
            </div>
        );
    }

    return (
        <div
            ref={containerRef}
            tabIndex={0}
            className={`bg-white rounded-2xl shadow-lg overflow-hidden focus:outline-none ${className}`}
        >
            {/* Header */}
            <div className="bg-gradient-to-r from-amber-500 to-orange-500 text-white p-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Flag size={24} />
                        <div>
                            <h2 className="text-lg font-bold">ביקורת פריטים</h2>
                            <p className="text-amber-100 text-sm">{draft.student_name}</p>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        {/* Progress */}
                        <div className="text-sm">
                            <span className="font-bold">{reviewedCount}</span>
                            <span className="text-amber-200"> / {totalItems} נבדקו</span>
                        </div>

                        {/* Keyboard help toggle */}
                        <button
                            onClick={() => setShowKeyboardHelp(!showKeyboardHelp)}
                            className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                            title="מקשי קיצור (?)"
                        >
                            <Keyboard size={18} />
                        </button>

                        {/* Close */}
                        <button
                            onClick={onClose}
                            className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                        >
                            <X size={18} />
                        </button>
                    </div>
                </div>

                {/* Progress bar */}
                <div className="mt-3 h-2 bg-white/20 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-white transition-all duration-300"
                        style={{ width: `${(reviewedCount / totalItems) * 100}%` }}
                    />
                </div>
            </div>

            {/* Keyboard shortcuts help */}
            {showKeyboardHelp && (
                <div className="bg-gray-800 text-white p-4 text-sm">
                    <div className="grid grid-cols-2 gap-x-8 gap-y-2">
                        <div className="flex items-center gap-2">
                            <kbd className="px-2 py-0.5 bg-gray-700 rounded text-xs">j</kbd>
                            <span>/ </span>
                            <kbd className="px-2 py-0.5 bg-gray-700 rounded text-xs">↓</kbd>
                            <span className="text-gray-300">הבא</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <kbd className="px-2 py-0.5 bg-gray-700 rounded text-xs">k</kbd>
                            <span>/ </span>
                            <kbd className="px-2 py-0.5 bg-gray-700 rounded text-xs">↑</kbd>
                            <span className="text-gray-300">הקודם</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <kbd className="px-2 py-0.5 bg-gray-700 rounded text-xs">Enter</kbd>
                            <span className="text-gray-300">אשר ניקוד</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <kbd className="px-2 py-0.5 bg-gray-700 rounded text-xs">e</kbd>
                            <span className="text-gray-300">ערוך ניקוד</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <kbd className="px-2 py-0.5 bg-gray-700 rounded text-xs">Esc</kbd>
                            <span className="text-gray-300">סגור</span>
                        </div>
                    </div>
                </div>
            )}

            {/* Navigation */}
            <div className="flex items-center justify-between px-4 py-2 bg-surface-50 border-b border-surface-200">
                <button
                    onClick={goPrev}
                    disabled={currentIndex === 0}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm text-gray-600 hover:bg-surface-100 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
                >
                    <ChevronRight size={16} />
                    הקודם
                </button>

                <span className="text-sm text-gray-500">
                    {currentIndex + 1} מתוך {totalItems}
                </span>

                <button
                    onClick={goNext}
                    disabled={currentIndex === totalItems - 1}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm text-gray-600 hover:bg-surface-100 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
                >
                    הבא
                    <ChevronLeft size={16} />
                </button>
            </div>

            {/* Current Item Display */}
            {currentItem && (
                <div className="p-6">
                    {/* Context header */}
                    <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
                        <span>שאלה {currentItem.questionOutcome.question_id}</span>
                        <span>•</span>
                        <span>קריטריון {currentItem.criterionOutcome.criterion_id}</span>
                        <span>•</span>
                        <span>כלל {currentItem.ruleOutcome.rule_id}</span>
                    </div>

                    {/* Flag reason badge */}
                    <div className="mb-4">
                        <NeedsReviewBadge
                            reason={currentItem.flaggedOutcome.reason}
                            message={currentItem.flaggedOutcome.message}
                            variant="banner"
                        />
                    </div>

                    {/* Rule details card */}
                    <div
                        className={`rounded-xl border-2 p-4 ${reviewedItems.has(getItemKey(currentItem.flaggedOutcome))
                                ? 'border-emerald-300 bg-emerald-50'
                                : 'border-amber-300 bg-amber-50'
                            }`}
                    >
                        {/* Score and confidence */}
                        <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-3">
                                <ScoreDisplay
                                    earned={currentItem.ruleOutcome.points_awarded}
                                    possible={currentItem.ruleOutcome.points_awarded} // Would need max from criterion
                                    size="md"
                                />
                                <ConfidenceIndicator
                                    level={currentItem.ruleOutcome.evidence_claim.confidence_level}
                                    showLabel
                                    size="md"
                                />
                            </div>

                            {reviewedItems.has(getItemKey(currentItem.flaggedOutcome)) && (
                                <span className="flex items-center gap-1 text-emerald-600 text-sm font-medium">
                                    <CheckCircle size={16} />
                                    נבדק
                                </span>
                            )}
                        </div>

                        {/* Claim statement */}
                        <div className="mb-4">
                            <h4 className="text-sm font-medium text-gray-700 mb-1">
                                טענת ה-AI:
                            </h4>
                            <p className="text-gray-800">
                                {currentItem.ruleOutcome.evidence_claim.claim_statement}
                            </p>
                        </div>

                        {/* Evidence quotations */}
                        {currentItem.ruleOutcome.evidence_claim.answer_quotations.length > 0 && (
                            <div>
                                <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-1">
                                    <Eye size={14} />
                                    ראיות מהתשובה:
                                </h4>
                                <div className="space-y-2">
                                    {currentItem.ruleOutcome.evidence_claim.answer_quotations.map(
                                        (q, i) => (
                                            <QuoteDisplay key={i} quotation={q} />
                                        )
                                    )}
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center justify-center gap-4 mt-6">
                        <button
                            onClick={() => setShowOverrideModal(true)}
                            className="flex items-center gap-2 px-6 py-3 border-2 border-purple-300 text-purple-700 hover:bg-purple-50 rounded-xl transition-colors font-medium"
                        >
                            <Edit3 size={18} />
                            ערוך ניקוד
                            <kbd className="px-1.5 py-0.5 bg-purple-100 rounded text-xs mr-1">e</kbd>
                        </button>

                        <button
                            onClick={handleApprove}
                            className="flex items-center gap-2 px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl transition-colors font-medium shadow-lg shadow-emerald-200"
                        >
                            <CheckCircle size={18} />
                            אשר ניקוד
                            <kbd className="px-1.5 py-0.5 bg-emerald-500 rounded text-xs mr-1">↵</kbd>
                        </button>
                    </div>
                </div>
            )}

            {/* Footer - Complete button */}
            {isAllReviewed && (
                <div className="p-4 bg-emerald-50 border-t border-emerald-200">
                    <button
                        onClick={handleComplete}
                        className="w-full flex items-center justify-center gap-2 py-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl transition-colors font-medium"
                    >
                        <CheckCircle size={20} />
                        סיום ביקורת - כל הפריטים נבדקו!
                    </button>
                </div>
            )}

            {/* Override Modal */}
            {currentItem && (
                <ScoreOverrideModal
                    isOpen={showOverrideModal}
                    ruleOutcome={currentItem.ruleOutcome}
                    questionNumber={currentItem.questionOutcome.question_id}
                    maxPoints={parseFloat(currentItem.ruleOutcome.points_awarded) || 5} // Default max
                    onConfirm={handleOverride}
                    onCancel={() => setShowOverrideModal(false)}
                />
            )}
        </div>
    );
}

export default FlaggedItemsReview;
