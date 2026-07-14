'use client';

/**
 * Score Override Modal
 *
 * Modal for teachers to override AI-assigned scores with explanation.
 * Supports full or partial point adjustments with reason tracking.
 */

import React, { useState, useEffect, useRef } from 'react';
import {
    X,
    AlertTriangle,
    CheckCircle,
    Edit3,
    MessageSquare,
} from 'lucide-react';
import type { RuleOutcome, ConfidenceLevel } from '@/lib/ontology-types';
import { formatPoints } from '@/lib/api';
import { ConfidenceIndicator, QuoteDisplay } from './grading/QualitySignals';

// =============================================================================
// TYPES
// =============================================================================

interface ScoreOverrideModalProps {
    /** Rule outcome being overridden */
    ruleOutcome: RuleOutcome;
    /** Criterion description for context */
    criterionDescription?: string;
    /** Question number for context */
    questionNumber: string;
    /** Maximum points possible for this rule */
    maxPoints: number;
    /** Callback when override is confirmed */
    onConfirm: (newPoints: number, reason: string) => void;
    /** Callback when modal is cancelled */
    onCancel: () => void;
    /** Whether modal is open */
    isOpen: boolean;
}

// =============================================================================
// PRESET REASONS
// =============================================================================

const PRESET_REASONS = [
    { label: 'הבנה שגויה של התשובה', value: 'AI misunderstood the answer' },
    { label: 'ניקוד חלקי מוצדק', value: 'Partial credit warranted' },
    { label: 'קריטריון לא רלוונטי', value: 'Criterion not applicable' },
    { label: 'התלמיד צודק', value: 'Student answer is correct' },
    { label: 'הקוד עובד אבל שונה', value: 'Code works but uses different approach' },
    { label: 'אחר', value: 'custom' },
];

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function ScoreOverrideModal({
    ruleOutcome,
    criterionDescription,
    questionNumber,
    maxPoints,
    onConfirm,
    onCancel,
    isOpen,
}: ScoreOverrideModalProps) {
    const currentPoints = parseFloat(ruleOutcome.points_awarded);
    const [newPoints, setNewPoints] = useState<number>(currentPoints);
    const [selectedReason, setSelectedReason] = useState<string>('');
    const [customReason, setCustomReason] = useState<string>('');
    const [error, setError] = useState<string>('');

    const inputRef = useRef<HTMLInputElement>(null);
    const modalRef = useRef<HTMLDivElement>(null);

    // Focus input on open
    useEffect(() => {
        if (isOpen) {
            setNewPoints(currentPoints);
            setSelectedReason('');
            setCustomReason('');
            setError('');
            setTimeout(() => inputRef.current?.focus(), 100);
        }
    }, [isOpen, currentPoints]);

    // Handle escape key
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && isOpen) {
                onCancel();
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isOpen, onCancel]);

    // Click outside to close
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
                onCancel();
            }
        };
        if (isOpen) {
            document.addEventListener('mousedown', handleClickOutside);
        }
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [isOpen, onCancel]);

    const handleSubmit = () => {
        // Validate
        if (newPoints < 0) {
            setError('הניקוד לא יכול להיות שלילי');
            return;
        }
        if (newPoints > maxPoints) {
            setError(`הניקוד המקסימלי הוא ${maxPoints}`);
            return;
        }

        const reason =
            selectedReason === 'custom' ? customReason : selectedReason;
        if (!reason.trim()) {
            setError('נא לבחור או להזין סיבה לשינוי');
            return;
        }

        onConfirm(newPoints, reason);
    };

    const handlePointsChange = (value: string) => {
        const num = parseFloat(value);
        if (!isNaN(num)) {
            setNewPoints(num);
            setError('');
        }
    };

    // Quick point buttons
    const quickPoints = [0, maxPoints * 0.5, maxPoints];

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div
                ref={modalRef}
                className="bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden"
                role="dialog"
                aria-modal="true"
                aria-labelledby="override-modal-title"
            >
                {/* Header */}
                <div className="bg-gradient-to-r from-purple-500 to-indigo-600 text-white p-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Edit3 size={20} />
                            <h2 id="override-modal-title" className="text-lg font-bold">
                                עריכת ניקוד
                            </h2>
                        </div>
                        <button
                            onClick={onCancel}
                            className="p-1 hover:bg-white/20 rounded-lg transition-colors"
                            aria-label="סגור"
                        >
                            <X size={20} />
                        </button>
                    </div>
                    <p className="text-purple-100 text-sm mt-1">
                        שאלה {questionNumber} • כלל {ruleOutcome.rule_id}
                    </p>
                </div>

                {/* Content */}
                <div className="p-4 space-y-4">
                    {/* Current Score Info */}
                    <div className="bg-surface-50 rounded-lg p-3 border border-surface-200">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-sm font-medium text-gray-700">
                                ניקוד נוכחי (AI)
                            </span>
                            <div className="flex items-center gap-2">
                                <ConfidenceIndicator
                                    level={ruleOutcome.evidence_claim.confidence_level}
                                    showLabel
                                    size="sm"
                                />
                                <span className="text-lg font-bold text-gray-800">
                                    {formatPoints(ruleOutcome.points_awarded)} / {formatPoints(maxPoints.toString())}
                                </span>
                            </div>
                        </div>
                        <p className="text-xs text-gray-600">
                            {ruleOutcome.evidence_claim.claim_statement}
                        </p>
                    </div>

                    {/* Evidence Preview */}
                    {ruleOutcome.evidence_claim.answer_quotations.length > 0 && (
                        <div>
                            <div className="text-xs font-medium text-gray-500 mb-1">ראיות:</div>
                            <div className="max-h-24 overflow-y-auto space-y-1">
                                {ruleOutcome.evidence_claim.answer_quotations.slice(0, 2).map((q, i) => (
                                    <QuoteDisplay key={i} quotation={q} compact />
                                ))}
                            </div>
                        </div>
                    )}

                    {/* New Points Input */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            ניקוד חדש
                        </label>
                        <div className="flex items-center gap-2">
                            <input
                                ref={inputRef}
                                type="number"
                                min={0}
                                max={maxPoints}
                                step={0.5}
                                value={newPoints}
                                onChange={(e) => handlePointsChange(e.target.value)}
                                className="flex-1 px-4 py-2 border border-surface-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-lg font-medium text-center"
                            />
                            <span className="text-gray-500">/ {formatPoints(maxPoints.toString())}</span>
                        </div>

                        {/* Quick buttons */}
                        <div className="flex gap-2 mt-2">
                            {quickPoints.map((points) => (
                                <button
                                    key={points}
                                    onClick={() => setNewPoints(points)}
                                    className={`flex-1 py-1.5 text-sm rounded-lg border transition-colors ${newPoints === points
                                            ? 'bg-purple-100 border-purple-300 text-purple-700'
                                            : 'bg-white border-surface-200 text-gray-600 hover:bg-surface-50'
                                        }`}
                                >
                                    {formatPoints(points.toString())}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Reason Selection */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            סיבה לשינוי
                        </label>
                        <div className="grid grid-cols-2 gap-2">
                            {PRESET_REASONS.map((reason) => (
                                <button
                                    key={reason.value}
                                    onClick={() => setSelectedReason(reason.value)}
                                    className={`px-3 py-2 text-sm rounded-lg border text-right transition-colors ${selectedReason === reason.value
                                            ? 'bg-purple-100 border-purple-300 text-purple-700'
                                            : 'bg-white border-surface-200 text-gray-600 hover:bg-surface-50'
                                        }`}
                                >
                                    {reason.label}
                                </button>
                            ))}
                        </div>

                        {/* Custom reason input */}
                        {selectedReason === 'custom' && (
                            <textarea
                                value={customReason}
                                onChange={(e) => setCustomReason(e.target.value)}
                                placeholder="הזן סיבה משלך..."
                                className="w-full mt-2 px-3 py-2 border border-surface-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-sm resize-none"
                                rows={2}
                            />
                        )}
                    </div>

                    {/* Error message */}
                    {error && (
                        <div className="flex items-center gap-2 text-red-600 text-sm">
                            <AlertTriangle size={14} />
                            <span>{error}</span>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-end gap-3 p-4 bg-surface-50 border-t border-surface-200">
                    <button
                        onClick={onCancel}
                        className="px-4 py-2 text-gray-600 hover:bg-surface-100 rounded-lg transition-colors"
                    >
                        ביטול
                    </button>
                    <button
                        onClick={handleSubmit}
                        className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors font-medium"
                    >
                        <CheckCircle size={16} />
                        שמור שינוי
                    </button>
                </div>
            </div>
        </div>
    );
}

export default ScoreOverrideModal;
