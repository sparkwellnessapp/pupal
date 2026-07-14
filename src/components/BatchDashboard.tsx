'use client';

/**
 * Batch Dashboard Component
 *
 * Displays batch grading progress with real-time updates.
 * Shows session list grouped by status with quick actions.
 */

import React, { useState, useMemo } from 'react';
import {
    Loader2,
    CheckCircle,
    XCircle,
    Clock,
    Users,
    AlertTriangle,
    Play,
    Pause,
    RefreshCw,
    Flag,
    ChevronDown,
    ChevronUp,
    FileText,
    Zap,
    X,
} from 'lucide-react';
import type {
    BatchProgressResponse,
    SessionSummary,
    GradedTestDraft,
} from '@/lib/ontology-types';
import {
    useBatchProgress,
    groupSessionsByStatus,
    formatRemainingTime,
    getStatusColorClass,
    getStatusLabel,
} from '@/hooks/useBatchProgress';
import { cancelBatch, getSessionDetails } from '@/lib/api';
import { ScoreDisplay, FlaggedItemsCounter } from './grading/QualitySignals';

// =============================================================================
// TYPES
// =============================================================================

interface BatchDashboardProps {
    /** Batch ID to monitor */
    batchId: string;
    /** Batch name for display */
    batchName?: string;
    /** Callback when user clicks a session to view details */
    onViewSession?: (sessionId: string) => void;
    /** Callback when user wants to review flagged items */
    onReviewFlagged?: (sessionId: string) => void;
    /** Callback when batch completes */
    onBatchComplete?: (progress: BatchProgressResponse) => void;
    /** Callback to close/dismiss dashboard */
    onClose?: () => void;
    /** Additional CSS classes */
    className?: string;
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function BatchDashboard({
    batchId,
    batchName,
    onViewSession,
    onReviewFlagged,
    onBatchComplete,
    onClose,
    className = '',
}: BatchDashboardProps) {
    const [expandedSections, setExpandedSections] = useState<Set<string>>(
        new Set(['in_progress', 'completed'])
    );
    const [isCancelling, setIsCancelling] = useState(false);

    const { progress, isPolling, error, stop, start, refresh } = useBatchProgress(batchId, {
        onComplete: onBatchComplete,
    });

    // Group sessions by status
    const groupedSessions = useMemo(() => {
        if (!progress?.sessions) return null;
        return groupSessionsByStatus(progress.sessions);
    }, [progress?.sessions]);

    const toggleSection = (section: string) => {
        setExpandedSections((prev) => {
            const next = new Set(prev);
            if (next.has(section)) {
                next.delete(section);
            } else {
                next.add(section);
            }
            return next;
        });
    };

    const handleCancel = async () => {
        if (!confirm('האם לבטל את הבדיקה? מבחנים שהושלמו יישמרו.')) return;

        setIsCancelling(true);
        try {
            await cancelBatch(batchId);
            stop();
            refresh();
        } catch (err) {
            console.error('Failed to cancel batch:', err);
        } finally {
            setIsCancelling(false);
        }
    };

    // Loading state
    if (!progress && !error) {
        return (
            <div className={`bg-white rounded-2xl border border-surface-200 shadow-lg p-8 ${className}`}>
                <div className="flex items-center justify-center gap-3 text-gray-500">
                    <Loader2 size={24} className="animate-spin" />
                    <span>טוען נתוני בדיקה...</span>
                </div>
            </div>
        );
    }

    // Error state
    if (error && !progress) {
        return (
            <div className={`bg-white rounded-2xl border border-red-200 shadow-lg p-8 ${className}`}>
                <div className="flex flex-col items-center gap-4 text-red-600">
                    <XCircle size={48} />
                    <p className="font-medium">שגיאה בטעינת נתונים</p>
                    <p className="text-sm text-red-500">{error.message}</p>
                    <button
                        onClick={refresh}
                        className="flex items-center gap-2 px-4 py-2 bg-red-50 hover:bg-red-100 rounded-lg transition-colors"
                    >
                        <RefreshCw size={16} />
                        נסה שוב
                    </button>
                </div>
            </div>
        );
    }

    if (!progress) return null;

    const isFinished =
        progress.status === 'completed' ||
        progress.status === 'failed' ||
        progress.status === 'partially_completed';

    const totalFlagged = progress.sessions.reduce((sum, s) => sum + s.flagged_count, 0);

    return (
        <div
            className={`bg-white rounded-2xl border border-surface-200 shadow-lg overflow-hidden ${className}`}
        >
            {/* Header */}
            <div className="bg-gradient-to-r from-indigo-500 to-purple-600 text-white p-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-xl font-bold mb-1">
                            {batchName || progress.batch_name || 'בדיקת מבחנים'}
                        </h2>
                        <p className="text-indigo-100 text-sm">
                            {progress.total_students} תלמידים • גרסת מחוון {progress.contract_version}
                        </p>
                    </div>

                    <div className="flex items-center gap-2">
                        {/* Polling indicator */}
                        {isPolling && (
                            <div className="flex items-center gap-1 text-indigo-200 text-xs">
                                <Loader2 size={12} className="animate-spin" />
                                <span>מתעדכן</span>
                            </div>
                        )}

                        {/* Refresh button */}
                        <button
                            onClick={refresh}
                            className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                            title="רענן"
                        >
                            <RefreshCw size={18} />
                        </button>

                        {/* Cancel button (only while in progress) */}
                        {!isFinished && (
                            <button
                                onClick={handleCancel}
                                disabled={isCancelling}
                                className="flex items-center gap-1 px-3 py-1.5 bg-white/10 hover:bg-white/20 rounded-lg transition-colors text-sm"
                            >
                                {isCancelling ? (
                                    <Loader2 size={14} className="animate-spin" />
                                ) : (
                                    <X size={14} />
                                )}
                                ביטול
                            </button>
                        )}

                        {/* Close button */}
                        {onClose && (
                            <button
                                onClick={onClose}
                                className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                            >
                                <X size={18} />
                            </button>
                        )}
                    </div>
                </div>

                {/* Progress bar */}
                <div className="mt-4">
                    <div className="flex justify-between text-sm mb-1">
                        <span>{progress.progress_percentage}% הושלם</span>
                        {progress.estimated_remaining_seconds && !isFinished && (
                            <span className="text-indigo-200">
                                נותרו: {formatRemainingTime(progress.estimated_remaining_seconds)}
                            </span>
                        )}
                    </div>
                    <div className="h-3 bg-white/20 rounded-full overflow-hidden">
                        <div
                            className={`h-full transition-all duration-500 ${progress.status === 'failed'
                                    ? 'bg-red-400'
                                    : progress.status === 'partially_completed'
                                        ? 'bg-amber-400'
                                        : 'bg-white'
                                }`}
                            style={{ width: `${progress.progress_percentage}%` }}
                        />
                    </div>
                </div>
            </div>

            {/* Stats Row */}
            <div className="grid grid-cols-5 divide-x divide-surface-200 border-b border-surface-200">
                <StatCard
                    icon={<Users size={20} />}
                    label="סה״כ"
                    value={progress.total_students}
                    colorClass="text-gray-600"
                />
                <StatCard
                    icon={<Clock size={20} />}
                    label="ממתינים"
                    value={progress.pending}
                    colorClass="text-gray-500"
                />
                <StatCard
                    icon={<Loader2 size={20} className={isPolling ? 'animate-spin' : ''} />}
                    label="בבדיקה"
                    value={progress.in_progress}
                    colorClass="text-blue-600"
                />
                <StatCard
                    icon={<CheckCircle size={20} />}
                    label="הושלמו"
                    value={progress.completed}
                    colorClass="text-emerald-600"
                />
                <StatCard
                    icon={<XCircle size={20} />}
                    label="נכשלו"
                    value={progress.failed}
                    colorClass="text-red-600"
                />
            </div>

            {/* Flagged Alert */}
            {totalFlagged > 0 && (
                <div className="mx-4 mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg flex items-center justify-between">
                    <div className="flex items-center gap-2 text-amber-700">
                        <AlertTriangle size={18} />
                        <span className="font-medium">{totalFlagged} פריטים דורשים בדיקה ידנית</span>
                    </div>
                    <button
                        onClick={() =>
                            onReviewFlagged?.(
                                progress.sessions.find((s) => s.flagged_count > 0)?.session_id || ''
                            )
                        }
                        className="px-3 py-1.5 bg-amber-100 hover:bg-amber-200 text-amber-800 rounded-lg text-sm font-medium transition-colors"
                    >
                        עבור לביקורת
                    </button>
                </div>
            )}

            {/* Session Lists */}
            <div className="p-4 space-y-3">
                {groupedSessions && (
                    <>
                        {/* In Progress */}
                        {groupedSessions.grading.length > 0 && (
                            <SessionSection
                                title="בבדיקה כעת"
                                sessions={groupedSessions.grading}
                                isExpanded={expandedSections.has('in_progress')}
                                onToggle={() => toggleSection('in_progress')}
                                colorClass="text-blue-600"
                                icon={<Loader2 size={16} className="animate-spin" />}
                                onViewSession={onViewSession}
                                onReviewFlagged={onReviewFlagged}
                            />
                        )}

                        {/* Completed */}
                        {groupedSessions.completed.length > 0 && (
                            <SessionSection
                                title="הושלמו"
                                sessions={groupedSessions.completed}
                                isExpanded={expandedSections.has('completed')}
                                onToggle={() => toggleSection('completed')}
                                colorClass="text-emerald-600"
                                icon={<CheckCircle size={16} />}
                                onViewSession={onViewSession}
                                onReviewFlagged={onReviewFlagged}
                            />
                        )}

                        {/* Pending */}
                        {groupedSessions.pending.length > 0 && (
                            <SessionSection
                                title="ממתינים"
                                sessions={groupedSessions.pending}
                                isExpanded={expandedSections.has('pending')}
                                onToggle={() => toggleSection('pending')}
                                colorClass="text-gray-500"
                                icon={<Clock size={16} />}
                                onViewSession={onViewSession}
                                onReviewFlagged={onReviewFlagged}
                            />
                        )}

                        {/* Failed */}
                        {groupedSessions.failed.length > 0 && (
                            <SessionSection
                                title="נכשלו"
                                sessions={groupedSessions.failed}
                                isExpanded={expandedSections.has('failed')}
                                onToggle={() => toggleSection('failed')}
                                colorClass="text-red-600"
                                icon={<XCircle size={16} />}
                                onViewSession={onViewSession}
                                onReviewFlagged={onReviewFlagged}
                            />
                        )}
                    </>
                )}
            </div>

            {/* Footer with completion status */}
            {isFinished && (
                <div
                    className={`p-4 border-t ${progress.status === 'completed'
                            ? 'bg-emerald-50 border-emerald-200'
                            : progress.status === 'failed'
                                ? 'bg-red-50 border-red-200'
                                : 'bg-amber-50 border-amber-200'
                        }`}
                >
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            {progress.status === 'completed' ? (
                                <CheckCircle size={20} className="text-emerald-600" />
                            ) : progress.status === 'failed' ? (
                                <XCircle size={20} className="text-red-600" />
                            ) : (
                                <AlertTriangle size={20} className="text-amber-600" />
                            )}
                            <span
                                className={`font-medium ${progress.status === 'completed'
                                        ? 'text-emerald-700'
                                        : progress.status === 'failed'
                                            ? 'text-red-700'
                                            : 'text-amber-700'
                                    }`}
                            >
                                {progress.status === 'completed'
                                    ? 'הבדיקה הושלמה בהצלחה!'
                                    : progress.status === 'failed'
                                        ? 'הבדיקה נכשלה'
                                        : `${progress.completed} מתוך ${progress.total_students} הושלמו`}
                            </span>
                        </div>
                        {progress.completed_at && (
                            <span className="text-sm text-gray-500">
                                {new Date(progress.completed_at).toLocaleTimeString('he-IL')}
                            </span>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

// =============================================================================
// STAT CARD
// =============================================================================

interface StatCardProps {
    icon: React.ReactNode;
    label: string;
    value: number;
    colorClass: string;
}

function StatCard({ icon, label, value, colorClass }: StatCardProps) {
    return (
        <div className="p-4 text-center">
            <div className={`flex items-center justify-center gap-2 ${colorClass}`}>
                {icon}
                <span className="text-2xl font-bold">{value}</span>
            </div>
            <div className="text-xs text-gray-500 mt-1">{label}</div>
        </div>
    );
}

// =============================================================================
// SESSION SECTION
// =============================================================================

interface SessionSectionProps {
    title: string;
    sessions: SessionSummary[];
    isExpanded: boolean;
    onToggle: () => void;
    colorClass: string;
    icon: React.ReactNode;
    onViewSession?: (sessionId: string) => void;
    onReviewFlagged?: (sessionId: string) => void;
}

function SessionSection({
    title,
    sessions,
    isExpanded,
    onToggle,
    colorClass,
    icon,
    onViewSession,
    onReviewFlagged,
}: SessionSectionProps) {
    return (
        <div className="border border-surface-200 rounded-lg overflow-hidden">
            <button
                onClick={onToggle}
                className="w-full flex items-center justify-between p-3 bg-surface-50 hover:bg-surface-100 transition-colors"
            >
                <div className={`flex items-center gap-2 ${colorClass}`}>
                    {icon}
                    <span className="font-medium">{title}</span>
                    <span className="text-gray-400 text-sm">({sessions.length})</span>
                </div>
                {isExpanded ? (
                    <ChevronUp size={18} className="text-gray-400" />
                ) : (
                    <ChevronDown size={18} className="text-gray-400" />
                )}
            </button>

            {isExpanded && (
                <div className="divide-y divide-surface-100">
                    {sessions.map((session) => (
                        <SessionRow
                            key={session.session_id}
                            session={session}
                            onView={() => onViewSession?.(session.session_id)}
                            onReviewFlagged={() => onReviewFlagged?.(session.session_id)}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}

// =============================================================================
// SESSION ROW
// =============================================================================

interface SessionRowProps {
    session: SessionSummary;
    onView?: () => void;
    onReviewFlagged?: () => void;
}

function SessionRow({ session, onView, onReviewFlagged }: SessionRowProps) {
    return (
        <div className="flex items-center justify-between p-3 hover:bg-surface-50 transition-colors">
            <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-surface-100 rounded-full flex items-center justify-center text-sm font-medium text-gray-600">
                    {session.student_name.charAt(0)}
                </div>
                <div>
                    <div className="font-medium text-gray-800">{session.student_name}</div>
                    <div className="text-xs text-gray-500">{session.progress}</div>
                </div>
            </div>

            <div className="flex items-center gap-3">
                {/* Score (if completed) */}
                {session.score && session.percentage !== undefined && (
                    <ScoreDisplay
                        earned={session.score.split('/')[0]}
                        possible={session.score.split('/')[1]}
                        size="sm"
                    />
                )}

                {/* Flagged badge */}
                {session.flagged_count > 0 && (
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            onReviewFlagged?.();
                        }}
                        className="flex items-center gap-1 px-2 py-1 bg-amber-50 text-amber-600 rounded text-xs hover:bg-amber-100 transition-colors"
                    >
                        <Flag size={12} />
                        {session.flagged_count}
                    </button>
                )}

                {/* View button */}
                {onView && session.status === 'completed' && (
                    <button
                        onClick={onView}
                        className="px-3 py-1.5 text-sm text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                    >
                        צפייה
                    </button>
                )}
            </div>
        </div>
    );
}

export default BatchDashboard;
