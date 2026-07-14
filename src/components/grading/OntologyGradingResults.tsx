'use client';

/**
 * Ontology Grading Results Component
 *
 * Displays grading results using the v2.0 ontology structure:
 * GradedTestDraft → QuestionOutcome → CriterionOutcome → RuleOutcome
 *
 * Features:
 * - Hierarchical expandable view
 * - Quality signal indicators (confidence, quote validation)
 * - Flagged items highlighting
 * - Evidence display for each rule
 */

import React, { useState, useMemo } from 'react';
import {
    ChevronDown,
    ChevronUp,
    User,
    FileText,
    Clock,
    Zap,
    AlertTriangle,
    CheckCircle,
    Flag,
} from 'lucide-react';
import type {
    GradedTestDraft,
    QuestionOutcome,
    CriterionOutcome,
    RuleOutcome,
    FlaggedOutcome,
} from '@/lib/ontology-types';
import { formatPoints, calculatePercentage } from '@/lib/api';
import {
    ConfidenceIndicator,
    QuoteDisplay,
    NeedsReviewBadge,
    FlaggedItemsCounter,
    ScoreDisplay,
    EvidenceClaimDisplay,
} from './QualitySignals';

// =============================================================================
// TYPES
// =============================================================================

interface OntologyGradingResultsProps {
    /** List of graded test drafts to display */
    drafts: GradedTestDraft[];
    /** Callback when user clicks to review a draft */
    onReviewDraft?: (draft: GradedTestDraft) => void;
    /** Callback when user wants to view flagged items only */
    onViewFlagged?: (draft: GradedTestDraft) => void;
    /** Whether to show metadata like timing and LLM calls */
    showMetadata?: boolean;
    /** Additional CSS classes */
    className?: string;
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function OntologyGradingResults({
    drafts,
    onReviewDraft,
    onViewFlagged,
    showMetadata = false,
    className = '',
}: OntologyGradingResultsProps) {
    const [expandedDrafts, setExpandedDrafts] = useState<Set<string>>(new Set());
    const [expandedQuestions, setExpandedQuestions] = useState<Set<string>>(new Set());
    const [expandedCriteria, setExpandedCriteria] = useState<Set<string>>(new Set());

    // Calculate summary stats
    const stats = useMemo(() => {
        const total = drafts.length;
        const needsReview = drafts.filter((d) => d.flagged_outcomes.length > 0).length;
        const totalFlagged = drafts.reduce((sum, d) => sum + d.flagged_outcomes.length, 0);

        // Calculate average score
        let totalEarned = 0;
        let totalPossible = 0;
        drafts.forEach((d) => {
            totalEarned += parseFloat(d.total_points_earned);
            totalPossible += parseFloat(d.total_points_possible);
        });
        const avgPercentage = totalPossible > 0 ? (totalEarned / totalPossible) * 100 : 0;

        return { total, needsReview, totalFlagged, avgPercentage };
    }, [drafts]);

    const toggleDraft = (draftId: string) => {
        setExpandedDrafts((prev) => {
            const next = new Set(prev);
            if (next.has(draftId)) {
                next.delete(draftId);
            } else {
                next.add(draftId);
            }
            return next;
        });
    };

    const toggleQuestion = (key: string) => {
        setExpandedQuestions((prev) => {
            const next = new Set(prev);
            if (next.has(key)) {
                next.delete(key);
            } else {
                next.add(key);
            }
            return next;
        });
    };

    const toggleCriterion = (key: string) => {
        setExpandedCriteria((prev) => {
            const next = new Set(prev);
            if (next.has(key)) {
                next.delete(key);
            } else {
                next.add(key);
            }
            return next;
        });
    };

    if (drafts.length === 0) {
        return (
            <div className={`text-center py-12 text-gray-500 bg-surface-50 rounded-xl ${className}`}>
                <FileText size={48} className="mx-auto mb-4 opacity-50" />
                <p>אין תוצאות להצגה</p>
            </div>
        );
    }

    return (
        <div className={`space-y-6 ${className}`}>
            {/* Summary Cards */}
            <div className="grid grid-cols-4 gap-4">
                <div className="bg-white rounded-xl p-4 border border-surface-200 shadow-sm">
                    <div className="text-2xl font-bold text-gray-800">{stats.total}</div>
                    <div className="text-sm text-gray-500">סה״כ מבחנים</div>
                </div>
                <div className="bg-emerald-50 rounded-xl p-4 border border-emerald-200">
                    <div className="text-2xl font-bold text-emerald-600">
                        {stats.total - stats.needsReview}
                    </div>
                    <div className="text-sm text-emerald-600">הושלמו</div>
                </div>
                <div className="bg-amber-50 rounded-xl p-4 border border-amber-200">
                    <div className="text-2xl font-bold text-amber-600">{stats.totalFlagged}</div>
                    <div className="text-sm text-amber-600">פריטים לבדיקה</div>
                </div>
                <div className="bg-blue-50 rounded-xl p-4 border border-blue-200">
                    <div className="text-2xl font-bold text-blue-600">{stats.avgPercentage.toFixed(1)}%</div>
                    <div className="text-sm text-blue-600">ממוצע</div>
                </div>
            </div>

            {/* Results List */}
            <div className="space-y-3">
                <h3 className="font-semibold text-lg">תוצאות מפורטות</h3>

                {drafts
                    .sort((a, b) => {
                        // Sort by percentage descending
                        const pctA = calculatePercentage(a.total_points_earned, a.total_points_possible);
                        const pctB = calculatePercentage(b.total_points_earned, b.total_points_possible);
                        return pctB - pctA;
                    })
                    .map((draft) => {
                        const isExpanded = expandedDrafts.has(draft.draft_id);
                        const percentage = calculatePercentage(
                            draft.total_points_earned,
                            draft.total_points_possible
                        );
                        const hasFlagged = draft.flagged_outcomes.length > 0;

                        return (
                            <div
                                key={draft.draft_id}
                                className={`bg-white rounded-xl border shadow-sm overflow-hidden ${hasFlagged ? 'border-amber-300' : 'border-surface-200'
                                    }`}
                            >
                                {/* Draft Header */}
                                <div
                                    className="flex items-center justify-between p-4 cursor-pointer hover:bg-surface-50 transition-colors"
                                    onClick={() => toggleDraft(draft.draft_id)}
                                >
                                    <div className="flex items-center gap-4">
                                        {isExpanded ? (
                                            <ChevronUp size={20} className="text-gray-400" />
                                        ) : (
                                            <ChevronDown size={20} className="text-gray-400" />
                                        )}

                                        <div className="flex items-center gap-2">
                                            <User size={18} className="text-gray-400" />
                                            <span className="font-medium">{draft.student_name}</span>
                                        </div>

                                        {draft.filename && (
                                            <div className="flex items-center gap-1 text-xs text-gray-400">
                                                <FileText size={14} />
                                                <span className="truncate max-w-[200px]">{draft.filename}</span>
                                            </div>
                                        )}

                                        {hasFlagged && (
                                            <FlaggedItemsCounter
                                                count={draft.flagged_outcomes.length}
                                                onClick={
                                                    onViewFlagged
                                                        ? () => {
                                                            onViewFlagged(draft);
                                                        }
                                                        : undefined
                                                }
                                            />
                                        )}
                                    </div>

                                    <div className="flex items-center gap-4">
                                        {showMetadata && (
                                            <div className="flex items-center gap-3 text-xs text-gray-400">
                                                <span className="flex items-center gap-1">
                                                    <Clock size={12} />
                                                    {(draft.grading_duration_ms / 1000).toFixed(1)}s
                                                </span>
                                                <span className="flex items-center gap-1">
                                                    <Zap size={12} />
                                                    {draft.llm_calls_count} calls
                                                </span>
                                            </div>
                                        )}
                                        <ScoreDisplay
                                            earned={draft.total_points_earned}
                                            possible={draft.total_points_possible}
                                            size="md"
                                        />
                                    </div>
                                </div>

                                {/* Expanded Content */}
                                {isExpanded && (
                                    <div className="border-t border-surface-200 p-4 bg-surface-50">
                                        {/* Warnings */}
                                        {draft.warnings.length > 0 && (
                                            <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                                                <h5 className="font-medium text-amber-700 text-sm mb-1 flex items-center gap-2">
                                                    <AlertTriangle size={14} />
                                                    אזהרות
                                                </h5>
                                                <ul className="text-xs text-amber-600 space-y-1">
                                                    {draft.warnings.map((warning, i) => (
                                                        <li key={i}>• {warning}</li>
                                                    ))}
                                                </ul>
                                            </div>
                                        )}

                                        {/* Question Outcomes */}
                                        <div className="space-y-3">
                                            {draft.question_outcomes.map((qo) => (
                                                <QuestionOutcomeCard
                                                    key={qo.question_id}
                                                    outcome={qo}
                                                    draftId={draft.draft_id}
                                                    flaggedOutcomes={draft.flagged_outcomes}
                                                    expandedQuestions={expandedQuestions}
                                                    expandedCriteria={expandedCriteria}
                                                    onToggleQuestion={toggleQuestion}
                                                    onToggleCriterion={toggleCriterion}
                                                />
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })}
            </div>
        </div>
    );
}

// =============================================================================
// QUESTION OUTCOME CARD
// =============================================================================

interface QuestionOutcomeCardProps {
    outcome: QuestionOutcome;
    draftId: string;
    flaggedOutcomes: FlaggedOutcome[];
    expandedQuestions: Set<string>;
    expandedCriteria: Set<string>;
    onToggleQuestion: (key: string) => void;
    onToggleCriterion: (key: string) => void;
}

function QuestionOutcomeCard({
    outcome,
    draftId,
    flaggedOutcomes,
    expandedQuestions,
    expandedCriteria,
    onToggleQuestion,
    onToggleCriterion,
}: QuestionOutcomeCardProps) {
    const qKey = `${draftId}-${outcome.question_id}`;
    const isExpanded = expandedQuestions.has(qKey);
    const percentage = calculatePercentage(outcome.points_earned, outcome.points_possible);

    // Check if any criteria in this question are flagged
    const questionFlaggedCount = outcome.criterion_outcomes.reduce((count, co) => {
        return count + co.rule_outcomes.filter((ro) => ro.needs_review).length;
    }, 0);

    const getBorderColor = (pct: number) => {
        if (pct >= 80) return 'border-emerald-200';
        if (pct >= 60) return 'border-amber-200';
        return 'border-red-200';
    };

    return (
        <div className={`bg-white rounded-lg border ${getBorderColor(percentage)} overflow-hidden`}>
            {/* Question Header */}
            <div
                className="flex items-center justify-between p-3 cursor-pointer hover:bg-surface-50"
                onClick={(e) => {
                    e.stopPropagation();
                    onToggleQuestion(qKey);
                }}
            >
                <div className="flex items-center gap-3">
                    {isExpanded ? (
                        <ChevronUp size={16} className="text-gray-400" />
                    ) : (
                        <ChevronDown size={16} className="text-gray-400" />
                    )}
                    <span className="font-medium text-gray-700">שאלה {outcome.question_id}</span>
                    <span className="text-xs text-gray-400">
                        ({outcome.criterion_outcomes.length} קריטריונים)
                    </span>
                    {questionFlaggedCount > 0 && (
                        <span className="flex items-center gap-1 text-xs text-amber-600">
                            <Flag size={12} />
                            {questionFlaggedCount}
                        </span>
                    )}
                </div>
                <ScoreDisplay
                    earned={outcome.points_earned}
                    possible={outcome.points_possible}
                    size="sm"
                />
            </div>

            {/* Expanded Criteria */}
            {isExpanded && (
                <div className="border-t border-surface-100 divide-y divide-surface-100">
                    {outcome.criterion_outcomes.map((co) => (
                        <CriterionOutcomeRow
                            key={co.criterion_id}
                            outcome={co}
                            questionKey={qKey}
                            flaggedOutcomes={flaggedOutcomes}
                            expandedCriteria={expandedCriteria}
                            onToggleCriterion={onToggleCriterion}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}

// =============================================================================
// CRITERION OUTCOME ROW
// =============================================================================

interface CriterionOutcomeRowProps {
    outcome: CriterionOutcome;
    questionKey: string;
    flaggedOutcomes: FlaggedOutcome[];
    expandedCriteria: Set<string>;
    onToggleCriterion: (key: string) => void;
}

function CriterionOutcomeRow({
    outcome,
    questionKey,
    expandedCriteria,
    onToggleCriterion,
}: CriterionOutcomeRowProps) {
    const cKey = `${questionKey}-${outcome.criterion_id}`;
    const isExpanded = expandedCriteria.has(cKey);

    const flaggedRulesCount = outcome.rule_outcomes.filter((ro) => ro.needs_review).length;

    return (
        <div className={outcome.needs_review ? 'bg-amber-50/50' : ''}>
            {/* Criterion Header */}
            <div
                className="flex items-center justify-between p-3 cursor-pointer hover:bg-surface-50"
                onClick={(e) => {
                    e.stopPropagation();
                    onToggleCriterion(cKey);
                }}
            >
                <div className="flex items-center gap-3">
                    {isExpanded ? (
                        <ChevronUp size={14} className="text-gray-400" />
                    ) : (
                        <ChevronDown size={14} className="text-gray-400" />
                    )}
                    <span className="text-sm text-gray-700">קריטריון {outcome.criterion_id}</span>
                    {outcome.needs_review && <NeedsReviewBadge reason="low_confidence" size="sm" />}
                    {flaggedRulesCount > 0 && !outcome.needs_review && (
                        <span className="text-xs text-amber-500">({flaggedRulesCount} כללים לבדיקה)</span>
                    )}
                </div>
                <div className="flex items-center gap-3">
                    <ScoreDisplay
                        earned={outcome.points_earned}
                        possible={outcome.points_possible}
                        size="sm"
                        showPercentage={false}
                    />
                </div>
            </div>

            {/* Reasoning Summary */}
            {isExpanded && outcome.reasoning_summary && (
                <div className="px-3 pb-2">
                    <p className="text-xs text-gray-600 bg-gray-50 rounded p-2 border-r-2 border-gray-300">
                        {outcome.reasoning_summary}
                    </p>
                </div>
            )}

            {/* Rules */}
            {isExpanded && (
                <div className="px-3 pb-3 space-y-2">
                    {outcome.rule_outcomes.map((ro) => (
                        <RuleOutcomeItem key={ro.rule_id} outcome={ro} />
                    ))}
                </div>
            )}
        </div>
    );
}

// =============================================================================
// RULE OUTCOME ITEM
// =============================================================================

interface RuleOutcomeItemProps {
    outcome: RuleOutcome;
}

function RuleOutcomeItem({ outcome }: RuleOutcomeItemProps) {
    const [showEvidence, setShowEvidence] = useState(false);

    const points = parseFloat(outcome.points_awarded);
    const isFullPoints = points > 0; // Simplified check

    return (
        <div
            className={`rounded-lg border p-3 ${outcome.needs_review
                ? 'border-amber-300 bg-amber-50'
                : isFullPoints
                    ? 'border-emerald-200 bg-emerald-50/30'
                    : 'border-red-200 bg-red-50/30'
                }`}
        >
            {/* Rule Header */}
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    {outcome.needs_review ? (
                        <AlertTriangle size={14} className="text-amber-500" />
                    ) : isFullPoints ? (
                        <CheckCircle size={14} className="text-emerald-500" />
                    ) : (
                        <Flag size={14} className="text-red-500" />
                    )}
                    <span className="text-sm font-medium text-gray-700">כלל {outcome.rule_id}</span>
                    {outcome.needs_review && outcome.review_reason && (
                        <span className="text-xs text-amber-600">({outcome.review_reason})</span>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    <ConfidenceIndicator
                        level={outcome.evidence_claim.confidence_level}
                        size="sm"
                    />
                    <span
                        className={`text-sm font-medium ${isFullPoints ? 'text-emerald-600' : 'text-red-600'
                            }`}
                    >
                        {formatPoints(outcome.points_awarded)} נק׳
                    </span>
                </div>
            </div>

            {/* Evidence Claim Statement */}
            <div className="text-xs text-gray-600 mb-2">{outcome.evidence_claim.claim_statement}</div>

            {/* Toggle Evidence Button */}
            {outcome.evidence_claim.answer_quotations.length > 0 && (
                <button
                    onClick={() => setShowEvidence(!showEvidence)}
                    className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1"
                >
                    {showEvidence ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    {showEvidence ? 'הסתר ראיות' : 'הצג ראיות'}
                    <span className="text-gray-400">
                        ({outcome.evidence_claim.answer_quotations.length})
                    </span>
                </button>
            )}

            {/* Evidence Quotations */}
            {showEvidence && (
                <div className="mt-2 space-y-2">
                    {outcome.evidence_claim.answer_quotations.map((q, i) => (
                        <QuoteDisplay key={i} quotation={q} />
                    ))}
                </div>
            )}

        </div>
    );
}

export default OntologyGradingResults;
