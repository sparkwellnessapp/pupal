'use client';

/**
 * useBatchProgress Hook
 *
 * React hook for polling batch grading progress.
 * Automatically starts polling when mounted and stops on completion or unmount.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { BatchProgressResponse, SessionSummary } from '@/lib/ontology-types';
import { ApiAuthError, getBatchProgress } from '@/lib/api';

// =============================================================================
// TYPES
// =============================================================================

export interface UseBatchProgressOptions {
    /** Polling interval in milliseconds (default: 2000) */
    intervalMs?: number;
    /** Whether to start polling immediately (default: true) */
    autoStart?: boolean;
    /** Callback when progress updates */
    onProgress?: (progress: BatchProgressResponse) => void;
    /** Callback when batch completes */
    onComplete?: (progress: BatchProgressResponse) => void;
    /** Callback on error */
    onError?: (error: Error) => void;
}

export interface UseBatchProgressResult {
    /** Current progress data */
    progress: BatchProgressResponse | null;
    /** Whether currently polling */
    isPolling: boolean;
    /** Last error if any */
    error: Error | null;
    /** Start polling */
    start: () => void;
    /** Stop polling */
    stop: () => void;
    /** Manually refresh progress */
    refresh: () => Promise<void>;
}

// =============================================================================
// HOOK
// =============================================================================

export function useBatchProgress(
    batchId: string | null,
    options: UseBatchProgressOptions = {}
): UseBatchProgressResult {
    const {
        intervalMs = 2000,
        autoStart = true,
        onProgress,
        onComplete,
        onError,
    } = options;

    const [progress, setProgress] = useState<BatchProgressResponse | null>(null);
    const [isPolling, setIsPolling] = useState(false);
    const [error, setError] = useState<Error | null>(null);

    // Use refs to avoid stale closures in callbacks
    const callbacksRef = useRef({ onProgress, onComplete, onError });
    callbacksRef.current = { onProgress, onComplete, onError };

    const pollingRef = useRef(false);
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Fetch progress once
    const fetchProgress = useCallback(async () => {
        if (!batchId) return;

        try {
            const data = await getBatchProgress(batchId);
            setProgress(data);
            setError(null);
            callbacksRef.current.onProgress?.(data);

            // Check if batch is finished
            const isFinished =
                data.status === 'completed' ||
                data.status === 'failed' ||
                data.status === 'partially_completed';

            if (isFinished) {
                pollingRef.current = false;
                setIsPolling(false);
                callbacksRef.current.onComplete?.(data);
            }

            return data;
        } catch (err) {
            const error = err instanceof Error ? err : new Error(String(err));
            setError(error);
            callbacksRef.current.onError?.(error);
            throw error;
        }
    }, [batchId]);

    // Poll loop
    const poll = useCallback(async () => {
        if (!pollingRef.current || !batchId) return;

        try {
            const data = await fetchProgress();

            // Schedule next poll if still polling and not finished
            if (
                pollingRef.current &&
                data &&
                data.status !== 'completed' &&
                data.status !== 'failed' &&
                data.status !== 'partially_completed'
            ) {
                timeoutRef.current = setTimeout(poll, intervalMs);
            }
        } catch (err) {
            // PR-2 (D12): 401/403 is TERMINAL. This loop used to treat EVERY error as
            // transient and reschedule with backoff — so an expired token turned the
            // grading flow into an infinite, silent poll against a 401 that could never
            // succeed. Stop, and let the caller surface/redirect.
            if (err instanceof ApiAuthError) {
                pollingRef.current = false;
                setIsPolling(false);
                return;
            }
            // Genuine transient error: continue polling with backoff.
            if (pollingRef.current) {
                timeoutRef.current = setTimeout(poll, intervalMs * 2);
            }
        }
    }, [batchId, fetchProgress, intervalMs]);

    // Start polling
    const start = useCallback(() => {
        if (pollingRef.current || !batchId) return;

        pollingRef.current = true;
        setIsPolling(true);
        poll();
    }, [batchId, poll]);

    // Stop polling
    const stop = useCallback(() => {
        pollingRef.current = false;
        setIsPolling(false);

        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
            timeoutRef.current = null;
        }
    }, []);

    // Manual refresh
    const refresh = useCallback(async () => {
        await fetchProgress();
    }, [fetchProgress]);

    // Auto-start on mount if enabled
    useEffect(() => {
        if (autoStart && batchId) {
            start();
        }

        return () => {
            stop();
        };
    }, [autoStart, batchId, start, stop]);

    return {
        progress,
        isPolling,
        error,
        start,
        stop,
        refresh,
    };
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Group sessions by status for display.
 */
export function groupSessionsByStatus(sessions: SessionSummary[]): {
    pending: SessionSummary[];
    grading: SessionSummary[];
    completed: SessionSummary[];
    failed: SessionSummary[];
} {
    return {
        pending: sessions.filter((s) => s.status === 'initialized'),
        grading: sessions.filter((s) => s.status === 'grading'),
        completed: sessions.filter((s) => s.status === 'completed'),
        failed: sessions.filter((s) => s.status === 'failed'),
    };
}

/**
 * Format remaining time for display.
 */
export function formatRemainingTime(seconds: number | undefined): string {
    if (!seconds || seconds <= 0) return '';

    if (seconds < 60) {
        return `${Math.round(seconds)} שניות`;
    }

    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.round(seconds % 60);

    if (minutes < 60) {
        return remainingSeconds > 0
            ? `${minutes} דקות ו-${remainingSeconds} שניות`
            : `${minutes} דקות`;
    }

    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;

    return remainingMinutes > 0
        ? `${hours} שעות ו-${remainingMinutes} דקות`
        : `${hours} שעות`;
}

/**
 * Get status color class.
 */
export function getStatusColorClass(status: string): string {
    switch (status) {
        case 'completed':
            return 'text-emerald-600 bg-emerald-50 border-emerald-200';
        case 'processing':
        case 'in_progress':
        case 'grading':
            return 'text-blue-600 bg-blue-50 border-blue-200';
        case 'failed':
            return 'text-red-600 bg-red-50 border-red-200';
        case 'partially_completed':
            return 'text-amber-600 bg-amber-50 border-amber-200';
        default:
            return 'text-gray-600 bg-gray-50 border-gray-200';
    }
}

/**
 * Get status label in Hebrew.
 */
export function getStatusLabel(status: string): string {
    const labels: Record<string, string> = {
        processing: 'מעבד',
        in_progress: 'בתהליך',
        completed: 'הושלם',
        partially_completed: 'הושלם חלקית',
        failed: 'נכשל',
        initialized: 'ממתין',
        grading: 'בבדיקה',
    };
    return labels[status] || status;
}

export default useBatchProgress;
