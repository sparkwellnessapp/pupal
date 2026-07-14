'use client';

/**
 * Quality Signal Components for Ontology Grading v2.0
 *
 * These components display AI confidence levels, quote validation status,
 * and review flags to help teachers quickly identify items needing attention.
 */

import React from 'react';
import {
    CheckCircle,
    AlertCircle,
    AlertTriangle,
    HelpCircle,
    Quote,
    Flag,
} from 'lucide-react';
import type {
    QuoteValidationStatus,
    ConfidenceLevel,
    FlagReason,
    AnswerQuotation,
} from '@/lib/ontology-types';
import {
    getFlagReasonLabel,
    getQuoteValidationDisplay,
} from '@/lib/api';

// =============================================================================
// CONFIDENCE INDICATOR
// =============================================================================

interface ConfidenceIndicatorProps {
    /** AI confidence level */
    level: ConfidenceLevel | undefined;
    /** Show label text next to icon */
    showLabel?: boolean;
    /** Size variant */
    size?: 'sm' | 'md' | 'lg';
    /** Additional CSS classes */
    className?: string;
}

const confidenceConfig = {
    high: {
        icon: CheckCircle,
        color: 'text-emerald-500',
        bgColor: 'bg-emerald-50',
        borderColor: 'border-emerald-200',
        label: 'ביטחון גבוה',
        dotColor: 'bg-emerald-500',
    },
    medium: {
        icon: AlertCircle,
        color: 'text-amber-500',
        bgColor: 'bg-amber-50',
        borderColor: 'border-amber-200',
        label: 'ביטחון בינוני',
        dotColor: 'bg-amber-500',
    },
    low: {
        icon: AlertTriangle,
        color: 'text-red-500',
        bgColor: 'bg-red-50',
        borderColor: 'border-red-200',
        label: 'ביטחון נמוך',
        dotColor: 'bg-red-500',
    },
};

const sizeConfig = {
    sm: { icon: 12, text: 'text-xs', padding: 'px-1.5 py-0.5', dot: 'w-1.5 h-1.5' },
    md: { icon: 14, text: 'text-sm', padding: 'px-2 py-1', dot: 'w-2 h-2' },
    lg: { icon: 16, text: 'text-base', padding: 'px-2.5 py-1.5', dot: 'w-2.5 h-2.5' },
};

/**
 * Displays AI confidence level with color-coded indicator.
 * Use to show teachers how reliable a grading decision is.
 */
export function ConfidenceIndicator({
    level,
    showLabel = false,
    size = 'md',
    className = '',
}: ConfidenceIndicatorProps) {
    if (!level) {
        return (
            <span className={`inline-flex items-center gap-1 text-gray-400 ${sizeConfig[size].text} ${className}`}>
                <HelpCircle size={sizeConfig[size].icon} />
                {showLabel && <span>לא ידוע</span>}
            </span>
        );
    }

    const config = confidenceConfig[level];
    const sizes = sizeConfig[size];

    if (showLabel) {
        return (
            <span
                className={`inline-flex items-center gap-1.5 ${sizes.padding} rounded-full ${config.bgColor} ${config.borderColor} border ${sizes.text} font-medium ${config.color} ${className}`}
                title={config.label}
            >
                <span className={`${sizes.dot} rounded-full ${config.dotColor}`} />
                <span>{config.label}</span>
            </span>
        );
    }

    // Icon-only variant with tooltip
    const Icon = config.icon;
    return (
        <span
            className={`inline-flex items-center ${config.color} ${className}`}
            title={config.label}
        >
            <Icon size={sizes.icon} />
        </span>
    );
}

// =============================================================================
// QUOTE DISPLAY
// =============================================================================

interface QuoteDisplayProps {
    /** The quoted text from student work */
    quotation: AnswerQuotation;
    /** Show validation status indicator */
    showStatus?: boolean;
    /** Compact mode for inline display */
    compact?: boolean;
    /** Additional CSS classes */
    className?: string;
}

/**
 * Displays a quote from student work with validation status.
 * Shows whether the quote was found exactly, approximately, or not at all.
 */
export function QuoteDisplay({
    quotation,
    showStatus = true,
    compact = false,
    className = '',
}: QuoteDisplayProps) {
    const status = quotation.validation_status || 'exact';
    const { icon, colorClass, label } = getQuoteValidationDisplay(status);

    if (compact) {
        return (
            <span
                className={`inline-flex items-center gap-1 ${className}`}
                title={`${label}: ${quotation.quote_text}`}
            >
                {showStatus && (
                    <span className={`font-mono text-xs ${colorClass}`}>{icon}</span>
                )}
                <span className="text-gray-600 text-xs truncate max-w-[200px]">
                    &quot;{quotation.quote_text}&quot;
                </span>
            </span>
        );
    }

    return (
        <div
            className={`rounded-lg border overflow-hidden ${status === 'exact'
                    ? 'border-emerald-200 bg-emerald-50/50'
                    : status === 'fuzzy'
                        ? 'border-amber-200 bg-amber-50/50'
                        : 'border-red-200 bg-red-50/50'
                } ${className}`}
        >
            {/* Status header */}
            {showStatus && (
                <div
                    className={`flex items-center gap-2 px-3 py-1.5 text-xs font-medium ${status === 'exact'
                            ? 'bg-emerald-100 text-emerald-700'
                            : status === 'fuzzy'
                                ? 'bg-amber-100 text-amber-700'
                                : 'bg-red-100 text-red-700'
                        }`}
                >
                    <Quote size={12} />
                    <span>{label}</span>
                    {quotation.position_hint && (
                        <span className="text-gray-500 font-normal">• {quotation.position_hint}</span>
                    )}
                </div>
            )}

            {/* Quote text */}
            <div className="p-3">
                <blockquote
                    className="font-mono text-sm text-gray-800 whitespace-pre-wrap break-words"
                    dir="ltr"
                >
                    {quotation.quote_text}
                </blockquote>
            </div>
        </div>
    );
}

// =============================================================================
// NEEDS REVIEW BADGE
// =============================================================================

interface NeedsReviewBadgeProps {
    /** Why this item needs review */
    reason: FlagReason;
    /** Optional custom message */
    message?: string;
    /** Size variant */
    size?: 'sm' | 'md';
    /** Show as full banner vs inline badge */
    variant?: 'badge' | 'banner';
    /** Additional CSS classes */
    className?: string;
}

/**
 * Badge indicating an item needs teacher review.
 * Used to highlight flagged outcomes in grading results.
 */
export function NeedsReviewBadge({
    reason,
    message,
    size = 'md',
    variant = 'badge',
    className = '',
}: NeedsReviewBadgeProps) {
    const label = getFlagReasonLabel(reason);
    const sizes = sizeConfig[size];

    if (variant === 'banner') {
        return (
            <div
                className={`flex items-center gap-2 p-3 rounded-lg bg-amber-50 border border-amber-300 ${className}`}
            >
                <Flag size={16} className="text-amber-600 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                    <div className="font-medium text-amber-800 text-sm">{label}</div>
                    {message && (
                        <div className="text-xs text-amber-600 mt-0.5">{message}</div>
                    )}
                </div>
            </div>
        );
    }

    return (
        <span
            className={`inline-flex items-center gap-1 ${sizes.padding} rounded-full bg-amber-100 border border-amber-300 ${sizes.text} font-medium text-amber-700 ${className}`}
            title={message || label}
        >
            <Flag size={sizes.icon} />
            <span>{label}</span>
        </span>
    );
}

// =============================================================================
// FLAGGED ITEMS COUNTER
// =============================================================================

interface FlaggedItemsCounterProps {
    /** Number of flagged items */
    count: number;
    /** Total items for context */
    total?: number;
    /** Click handler */
    onClick?: () => void;
    /** Additional CSS classes */
    className?: string;
}

/**
 * Counter showing number of items needing review.
 * Clickable to jump to flagged items view.
 */
export function FlaggedItemsCounter({
    count,
    total,
    onClick,
    className = '',
}: FlaggedItemsCounterProps) {
    if (count === 0) {
        return (
            <span
                className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-sm font-medium text-emerald-600 ${className}`}
            >
                <CheckCircle size={14} />
                <span>הכל נבדק</span>
            </span>
        );
    }

    const Component = onClick ? 'button' : 'span';

    return (
        <Component
            onClick={onClick}
            className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full bg-amber-100 border border-amber-300 text-sm font-medium text-amber-700 ${onClick
                    ? 'cursor-pointer hover:bg-amber-200 transition-colors'
                    : ''
                } ${className}`}
        >
            <AlertTriangle size={14} />
            <span>
                {count} {total ? `מתוך ${total}` : ''} לבדיקה
            </span>
        </Component>
    );
}

// =============================================================================
// EVIDENCE CLAIM DISPLAY
// =============================================================================

interface EvidenceClaimDisplayProps {
    /** The claim type */
    claimType: string;
    /** Human-readable claim statement */
    claimStatement: string;
    /** Confidence level of the claim */
    confidenceLevel?: ConfidenceLevel;
    /** Quotations supporting the claim */
    quotations: AnswerQuotation[];
    /** Whether this claim needs review */
    needsReview?: boolean;
    /** Additional CSS classes */
    className?: string;
}

const claimTypeLabels: Record<string, string> = {
    presence: 'נוכחות',
    correctness: 'נכונות',
    coverage: 'כיסוי',
    constraint: 'אילוץ',
    quality: 'איכות',
};

/**
 * Displays an evidence claim with its supporting quotations.
 * Core component for showing grading evidence to teachers.
 */
export function EvidenceClaimDisplay({
    claimType,
    claimStatement,
    confidenceLevel,
    quotations,
    needsReview = false,
    className = '',
}: EvidenceClaimDisplayProps) {
    return (
        <div
            className={`rounded-lg border ${needsReview
                    ? 'border-amber-300 bg-amber-50/30'
                    : 'border-gray-200 bg-white'
                } ${className}`}
        >
            {/* Claim header */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100">
                <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                        {claimTypeLabels[claimType] || claimType}
                    </span>
                    {needsReview && <NeedsReviewBadge reason="low_confidence" size="sm" />}
                </div>
                {confidenceLevel && (
                    <ConfidenceIndicator level={confidenceLevel} showLabel size="sm" />
                )}
            </div>

            {/* Claim statement */}
            <div className="p-3">
                <p className="text-sm text-gray-800">{claimStatement}</p>
            </div>

            {/* Quotations */}
            {quotations.length > 0 && (
                <div className="px-3 pb-3 space-y-2">
                    <div className="text-xs font-medium text-gray-500 mb-1">ראיות:</div>
                    {quotations.map((q, i) => (
                        <QuoteDisplay key={i} quotation={q} compact={quotations.length > 2} />
                    ))}
                </div>
            )}
        </div>
    );
}

// =============================================================================
// SCORE DISPLAY
// =============================================================================

interface ScoreDisplayProps {
    /** Points earned */
    earned: string | number;
    /** Points possible */
    possible: string | number;
    /** Show percentage */
    showPercentage?: boolean;
    /** Size variant */
    size?: 'sm' | 'md' | 'lg';
    /** Additional CSS classes */
    className?: string;
}

/**
 * Displays score with color coding based on percentage.
 * Handles decimal string points from backend.
 */
export function ScoreDisplay({
    earned,
    possible,
    showPercentage = true,
    size = 'md',
    className = '',
}: ScoreDisplayProps) {
    const e = typeof earned === 'string' ? parseFloat(earned) : earned;
    const p = typeof possible === 'string' ? parseFloat(possible) : possible;
    const percentage = p > 0 ? (e / p) * 100 : 0;

    const formatNum = (n: number) => (n % 1 === 0 ? n.toString() : n.toFixed(1));

    const getColorClass = (pct: number) => {
        if (pct >= 80) return 'text-emerald-600 bg-emerald-50 border-emerald-200';
        if (pct >= 60) return 'text-amber-600 bg-amber-50 border-amber-200';
        return 'text-red-600 bg-red-50 border-red-200';
    };

    const sizeClasses = {
        sm: 'text-xs px-1.5 py-0.5',
        md: 'text-sm px-2 py-1',
        lg: 'text-base px-3 py-1.5',
    };

    const colorClass = getColorClass(percentage);

    return (
        <span
            className={`inline-flex items-center gap-2 rounded-full border font-medium ${colorClass} ${sizeClasses[size]} ${className}`}
        >
            <span>
                {formatNum(e)}/{formatNum(p)}
            </span>
            {showPercentage && (
                <span className="opacity-80">{Math.round(percentage)}%</span>
            )}
        </span>
    );
}
