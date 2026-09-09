'use client';

/**
 * useExtractionJob Hook (PR-1)
 *
 * Polls an async rubric-extraction job: 2s self-scheduling loop, ×2 backoff on
 * transient error, stop on terminal status (completed/failed) or staleness.
 *
 * Cloned from the retired useBatchProgress (deleted Phase 5) with one mandatory difference: a 401/403
 * (ApiAuthError) is TERMINAL — stop polling and surface an auth error. The
 * batch hook treats every error as transient, which loops forever against an
 * expired token; an extraction poll must never inherit that.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { ApiAuthError, ExtractionJobStatus, getExtractionJob } from '@/lib/api';

export interface UseExtractionJobOptions {
    /** Polling interval in milliseconds (default: 2000) */
    intervalMs?: number;
    /** Whether to start polling immediately (default: true) */
    autoStart?: boolean;
    /** Callback on every status update */
    onStatus?: (status: ExtractionJobStatus) => void;
    /** Callback when the job completes successfully */
    onComplete?: (status: ExtractionJobStatus) => void;
    /** Callback when the job fails or goes stale (instance died mid-job) */
    onFailed?: (status: ExtractionJobStatus) => void;
    /** Callback on auth expiry (401/403) — polling has already stopped */
    onAuthError?: (error: ApiAuthError) => void;
}

export interface UseExtractionJobResult {
    status: ExtractionJobStatus | null;
    isPolling: boolean;
    /** Last transient error (polling continues with backoff) */
    error: Error | null;
    /** Terminal auth error (polling stopped) */
    authError: ApiAuthError | null;
    start: () => void;
    stop: () => void;
    refresh: () => Promise<void>;
}

export function isTerminal(status: ExtractionJobStatus): boolean {
    return status.status === 'completed' || status.status === 'failed' || status.stale;
}

/**
 * TERMINAL IS AN EDGE, NOT A LEVEL — and getting this wrong destroys teacher work.
 *
 * A completed job stays completed forever, so every re-attach re-observes it. The
 * old code fired `onComplete` on EVERY terminal observation; the page's onComplete
 * re-applies the extraction result, which resets `extractedQuestions`, clears the
 * undo stack, drops the dirty flag and sends the teacher back to the arrival card.
 * So any restart of this hook against a finished job silently deleted her
 * in-progress review.
 *
 * Observed live (2026-09-01): a concurrent edit to `frontend/src` hot-reloaded the
 * page; React DEV treats a Fast-Refreshed component's hook deps as changed, so the
 * effect below re-ran `start()`, which re-fetched a completed job and bounced her
 * out of the review every ~2 minutes. Fast Refresh was only the trigger — resume,
 * crash-stash restore and retry all re-attach the same way in production.
 *
 * Keyed on the WIRE's `job_id`, not the hook argument: the answer must be about
 * the job we actually observed, not the id we happened to ask for.
 */
export function isNewTerminal(
    status: ExtractionJobStatus,
    deliveredFor: string | null,
): boolean {
    return isTerminal(status) && deliveredFor !== status.job_id;
}

export function useExtractionJob(
    jobId: string | null,
    options: UseExtractionJobOptions = {}
): UseExtractionJobResult {
    const { intervalMs = 2000, autoStart = true, onStatus, onComplete, onFailed, onAuthError } = options;

    const [status, setStatus] = useState<ExtractionJobStatus | null>(null);
    const [isPolling, setIsPolling] = useState(false);
    const [error, setError] = useState<Error | null>(null);
    const [authError, setAuthError] = useState<ApiAuthError | null>(null);

    // Refs to avoid stale closures in the self-scheduling loop
    const callbacksRef = useRef({ onStatus, onComplete, onFailed, onAuthError });
    callbacksRef.current = { onStatus, onComplete, onFailed, onAuthError };

    const pollingRef = useRef(false);
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    /** The job id whose TERMINAL transition has already been handed to the caller.
     *  Survives re-renders and effect re-runs; only a new job id clears it. */
    const deliveredTerminalRef = useRef<string | null>(null);

    const fetchStatus = useCallback(async (): Promise<ExtractionJobStatus | null> => {
        if (!jobId) return null;
        const data = await getExtractionJob(jobId);
        setStatus(data);
        setError(null);
        callbacksRef.current.onStatus?.(data);

        if (isTerminal(data)) {
            pollingRef.current = false;
            setIsPolling(false);
            // Status is always published (above); the terminal CALLBACKS fire once.
            if (isNewTerminal(data, deliveredTerminalRef.current)) {
                deliveredTerminalRef.current = data.job_id;
                if (data.status === 'completed') {
                    callbacksRef.current.onComplete?.(data);
                } else {
                    // failed, or stale-extracting (server died mid-job) — both retryable
                    callbacksRef.current.onFailed?.(data);
                }
            }
        } else if (deliveredTerminalRef.current === data.job_id) {
            // The job LEFT terminal — `/retry` re-queued this same id. That is a
            // genuinely new run, so its completion is a new edge. (A job that
            // stays completed never reaches this branch, so the guard above holds.)
            deliveredTerminalRef.current = null;
        }
        return data;
    }, [jobId]);

    const poll = useCallback(async () => {
        if (!pollingRef.current || !jobId) return;
        try {
            const data = await fetchStatus();
            if (pollingRef.current && data && !isTerminal(data)) {
                timeoutRef.current = setTimeout(poll, intervalMs);
            }
        } catch (err) {
            if (err instanceof ApiAuthError) {
                // TERMINAL: never loop a poll against an expired token.
                pollingRef.current = false;
                setIsPolling(false);
                setAuthError(err);
                callbacksRef.current.onAuthError?.(err);
                return;
            }
            const e = err instanceof Error ? err : new Error(String(err));
            setError(e);
            if (pollingRef.current) {
                timeoutRef.current = setTimeout(poll, intervalMs * 2); // transient → backoff
            }
        }
    }, [jobId, fetchStatus, intervalMs]);

    const start = useCallback(() => {
        if (pollingRef.current || !jobId) return;
        pollingRef.current = true;
        setIsPolling(true);
        setAuthError(null);
        poll();
    }, [jobId, poll]);

    const stop = useCallback(() => {
        pollingRef.current = false;
        setIsPolling(false);
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
            timeoutRef.current = null;
        }
    }, []);

    const refresh = useCallback(async () => {
        try {
            await fetchStatus();
        } catch (err) {
            if (err instanceof ApiAuthError) {
                setAuthError(err);
                callbacksRef.current.onAuthError?.(err);
                return;
            }
            setError(err instanceof Error ? err : new Error(String(err)));
        }
    }, [fetchStatus]);

    useEffect(() => {
        if (autoStart && jobId) start();
        return () => stop();
    }, [autoStart, jobId, start, stop]);

    return { status, isPolling, error, authError, start, stop, refresh };
}

/** Hebrew labels for pipeline progress stages (ProgressEvent.stage values). */
const STAGE_LABELS: Record<string, string> = {
    render: 'קוראת את המסמך',
    llm_call: 'מנתחת את המחוון',
    validate: 'בודקת עקביות',
    retry: 'מדייקת את החילוץ',
    build: 'בונה את מבנה המחוון',
    pedagogical: 'סורקת שגיאות במחוון',
    complete: 'החילוץ הושלם',
};

/**
 * Canonical stage order — for the PR-5 wait-screen checklist to sort the stages
 * the SERVER has actually reported (never to fabricate future ones). A stage the
 * server never reports simply never appears; ordering only affects how observed
 * stages stack. `retry` is intentionally excluded from the ladder — it is an
 * out-of-band "still working" beat, shown live but not as a ladder rung.
 */
const STAGE_ORDER = ['render', 'llm_call', 'validate', 'build', 'pedagogical', 'complete'] as const;

export function getExtractionStageLabel(stage: string | null): string {
    return (stage && STAGE_LABELS[stage]) || 'מעבדת את המסמך';
}

/** The canonical stage ladder (ordered), each with its Hebrew label. */
export function getExtractionStageOrder(): { stage: string; label: string }[] {
    return STAGE_ORDER.map(stage => ({ stage, label: STAGE_LABELS[stage] }));
}

export default useExtractionJob;
