'use client';

/**
 * Stage B (UPLOAD_LATENCY_PLAN.md, ruling R3) — the upload queue, hoisted out
 * of the upload page and into the app.
 *
 * WHY IT MOVED. The teacher watched a progress bar for four minutes because
 * `settleUploadQueue` navigated only on `allDone(...)`, and the queue lived
 * inside a page component whose XHRs `abort()` on unmount — so it could not
 * navigate earlier even though nothing downstream needed the last byte. Jobs
 * enqueue as each file lands, and the first transcription is reviewable about
 * half a second after its own file arrives. The whole wait was a client-side
 * lifetime problem.
 *
 * Mounted in the ROOT LAYOUT, above every route, so a `router.push` no longer
 * unmounts the thing holding the transfers. Nothing about the transfers
 * themselves changed: the U3 reducer, the `client_file_id` lifetime (minted
 * once per selected file, reused by retries — the B9 idempotency contract) and
 * "422 is terminal" all live where they always did, in `utils/batch-upload.ts`.
 * This module moves WHERE they live, not what they do.
 *
 * WHAT STILL KILLS AN UPLOAD, stated rather than hidden: a HARD navigation —
 * a full reload, or the session-expiry logout — tears down the page and its
 * XHRs with it. `beforeunload` covers the reload prompt; `hasActiveUploads` is
 * exported so the logout path can warn before it navigates. A soft route change
 * is now safe, which is the entire point.
 *
 * R10 — ONE uploading batch at a time. `begin()` refuses while a queue is
 * active, so there is no interleaving to reason about and no second queue to
 * test. The upload page reads `batchId` and offers a link to it instead.
 */

import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useRef,
    useState,
} from 'react';

import {
    appendBatchFileXHR,
    redeclareBatchExpectedCount,
    UploadAbortError,
    UploadHttpError,
} from '@/lib/api';
import { UPLOAD_FILE_FAILED } from '@/copy/batch';
import { handOffUploadFailures } from '@/utils/skip-notice';
import {
    declaredCount,
    initQueue,
    isDrained,
    landedCount,
    nextToStart,
    uploadQueueReducer,
    type UploadFileMeta,
    type UploadQueueAction,
    type UploadQueueState,
} from '@/utils/batch-upload';

export interface BeginResult {
    started: boolean;
    /** The batch whose upload is still running, when `started` is false. */
    blockedBy: string | null;
}

export interface UploadQueueApi {
    /** The batch these transfers belong to; null when nothing is queued. */
    batchId: string | null;
    queue: UploadQueueState | null;
    /** Anything still queued or uploading. Drives the tab-close guard. */
    isActive: boolean;
    /**
     * Adopt a fresh set of files for a batch. Refuses while a queue is still
     * live (R10) and names the batch that is blocking, so the caller can link
     * her to it instead of starting a second one behind it.
     */
    begin: (batchId: string, files: File[]) => BeginResult;
    /** Re-run one failed transfer with the SAME client_file_id (B9). */
    retry: (clientFileId: string) => void;
    /**
     * Drop a file from the batch's expectation (R9's explicit half). Aborts it
     * if it is mid-flight, and re-declares — this is how a teacher says "that
     * one is not coming" without waiting out the server's 90-minute backstop.
     */
    remove: (clientFileId: string) => void;
    /** Forget a finished queue (aborting anything left). Idempotent. */
    clear: () => void;
}

const noop = () => {};

const UploadQueueContext = createContext<UploadQueueApi>({
    batchId: null,
    queue: null,
    isActive: false,
    begin: () => ({ started: false, blockedBy: null }),
    retry: noop,
    remove: noop,
    clear: noop,
});

export function useUploadQueue(): UploadQueueApi {
    return useContext(UploadQueueContext);
}

export function UploadQueueProvider({ children }: { children: React.ReactNode }) {
    // State drives the UI; the refs are the driver's truth — the pump runs
    // from XHR promise callbacks, outside the render cycle (the U3 pattern,
    // carried over verbatim).
    const [queue, setQueue] = useState<UploadQueueState | null>(null);
    const [batchId, setBatchId] = useState<string | null>(null);
    const queueRef = useRef<UploadQueueState | null>(null);
    const batchIdRef = useRef<string | null>(null);
    const fileByIdRef = useRef(new Map<string, File>());
    const abortsRef = useRef(new Map<string, () => void>());
    const declaredRef = useRef<number | null>(null);

    const dispatch = useCallback((action: UploadQueueAction): UploadQueueState | null => {
        const current = queueRef.current;
        if (!current) return null;
        const next = uploadQueueReducer(current, action);
        queueRef.current = next;
        setQueue(next);
        return next;
    }, []);

    /**
     * A 422 is a VALIDATION verdict — terminal, never retried, because an
     * invalid file does not heal. 401/403 cannot be healed by repeating either.
     * Everything else is transport and keeps its retry.
     */
    const classifyError = (err: unknown, filename: string) => {
        if (err instanceof UploadHttpError) {
            const retryable = err.status !== 422 && err.status !== 401 && err.status !== 403;
            return { reason: err.message, retryable };
        }
        return { reason: UPLOAD_FILE_FAILED(filename), retryable: true };
    };

    /**
     * [R9] Tell the batch how many files it is still expecting, when that
     * number changes. `declaredCount` owns the rule (everything selected minus
     * the terminally failed). Change-gated so a settle per landed file does not
     * become a PATCH per landed file; fire-and-forget because the server's
     * backstop is the net and losing this call must never lose her upload.
     */
    const maybeRedeclare = useCallback((state: UploadQueueState, id: string) => {
        const n = declaredCount(state);
        if (declaredRef.current === n) return;
        declaredRef.current = n;
        void redeclareBatchExpectedCount(id, n).catch(() => {
            // REOPEN THE GATE. `declaredCount` only ever decreases over a
            // queue's life and the gate is pure equality, so advancing it past
            // a PATCH that never landed would retire that value forever: the
            // client would know a file was dead, have told nobody, and have no
            // way left to say it. On the 2 Mbps link this whole plan exists for
            // — six appends saturating the uplink — that request is exactly the
            // one likely to fail. Clearing the gate lets the next terminal
            // event re-send; if none comes, the 90-minute backstop still closes
            // the batch. Never surfaced to her: this is bookkeeping.
            if (declaredRef.current === n) declaredRef.current = null;
        });
    }, []);

    /**
     * Launch whatever the reducer says may start now, then — after each
     * transfer resolves — start the next one and re-declare if the number
     * changed.
     *
     * Written as ONE function that re-enters itself rather than a pump/settle
     * pair, because the pair is mutually recursive: `pump` needs `settle` for
     * its callbacks and `settle` needs `pump` to fill the freed slot. Through
     * `useCallback` that becomes a temporal-dead-zone hazard held open only by
     * the fact that nothing calls it synchronously — a property one refactor
     * could quietly remove.
     */
    const pump = useCallback(() => {
        const state = queueRef.current;
        const id = batchIdRef.current;
        if (!state || !id) return;

        const afterEach = () => {
            const s = queueRef.current;
            const b = batchIdRef.current;
            if (s && b) maybeRedeclare(s, b);
            pump();                        // fill the slot this transfer freed
        };

        for (const clientFileId of nextToStart(state)) {
            const file = fileByIdRef.current.get(clientFileId);
            if (!file) continue;
            dispatch({ type: 'start', clientFileId });
            const handle = appendBatchFileXHR(id, file, clientFileId, (pct) => {
                dispatch({ type: 'progress', clientFileId, pct });
            });
            abortsRef.current.set(clientFileId, handle.abort);
            handle.promise
                .then((res) => {
                    abortsRef.current.delete(clientFileId);
                    dispatch({ type: 'done', clientFileId, jobId: res.job_id });
                    afterEach();
                })
                .catch((err: unknown) => {
                    abortsRef.current.delete(clientFileId);
                    // An abort is a removal or a teardown, never a failure —
                    // the item is already gone from the queue.
                    if (err instanceof UploadAbortError) return;
                    const { reason, retryable } = classifyError(err, file.name);
                    dispatch({ type: 'fail', clientFileId, reason, retryable });
                    afterEach();
                });
        }
    }, [dispatch, maybeRedeclare]);

    /**
     * Let go of a queue — and SETTLE UP with the batch first.
     *
     * This is the bug that makes the difference between an honest surface and a
     * lie with a 90-minute half-life. `declaredCount` deliberately keeps a
     * RETRYABLE failure in the declaration, on the reasoning that she may still
     * click «נסי שוב» — which is only true while the queue exists. Dropping it
     * without settling leaves the server holding `expected > COUNT(jobs)`, so
     * the batch reports "1 file still uploading", pins itself to `in_progress`,
     * and renders an uploading segment — about a file that is not on the wire,
     * that nothing can put there, and whose retry button just went away with
     * the lane. The X is labelled "close the list"; it must not also mean
     * "abandon this file and misreport it until the backstop fires".
     *
     * So letting go IS one of R9's terminal events: the honest declaration at
     * that moment is exactly what landed. The filenames ride the existing
     * one-shot handoff so the dashboard can still name them after a reload —
     * the notice the upload page used to write before Stage B moved the queue.
     */
    const settleAndForget = useCallback((state: UploadQueueState | null,
                                         id: string | null) => {
        if (!state || !id) return;
        const lost = state.items
            .filter((i) => i.state.kind !== 'done')
            .map((i) => i.filename);
        if (lost.length > 0) handOffUploadFailures(id, lost);
        const landed = landedCount(state);
        if (declaredRef.current !== landed) {
            declaredRef.current = landed;
            void redeclareBatchExpectedCount(id, landed).catch(() => {
                /* the backstop is the net; nothing here is worth a toast */
            });
        }
    }, []);

    const begin = useCallback((id: string, files: File[]): BeginResult => {
        // R10: one uploading batch at a time. A live queue is never replaced —
        // doing so would strand transfers with no surface and no abort.
        //
        // The refusal REPORTS the blocking batch rather than a bare false: the
        // caller cannot read `batchId` off the context at that moment (its
        // closure was captured before the click), so a bare false left the
        // caller with nothing to link her to.
        const live = queueRef.current;
        if (live && !isDrained(live)) {
            return { started: false, blockedBy: batchIdRef.current };
        }
        // A DRAINED queue may be replaced — but not silently: a drained queue
        // with failures still holds files the outgoing batch is expecting, and
        // walking away from them without settling is B1's path B.
        settleAndForget(live, batchIdRef.current);

        const metas: UploadFileMeta[] = files.map((f) => ({
            // The B9 idempotency key — generated ONCE per selected file and
            // owned for its lifetime, so a retry can never mint a new identity.
            clientFileId: crypto.randomUUID(),
            filename: f.name,
            size: f.size,
        }));
        fileByIdRef.current = new Map(metas.map((m, i) => [m.clientFileId, files[i]]));
        abortsRef.current.forEach((abort) => abort());
        abortsRef.current.clear();
        // Seeded with what create() already declared, so the first PATCH fires
        // on the first real change rather than on the first landed file.
        declaredRef.current = files.length;
        const q = initQueue(metas);
        queueRef.current = q;
        batchIdRef.current = id;
        setQueue(q);
        setBatchId(id);
        pump();
        return { started: true, blockedBy: null };
    }, [pump, settleAndForget]);

    const retry = useCallback((clientFileId: string) => {
        dispatch({ type: 'retry', clientFileId });   // SAME id — idempotent server-side
        pump();
    }, [dispatch, pump]);

    const remove = useCallback((clientFileId: string) => {
        const state = queueRef.current;
        const id = batchIdRef.current;
        if (!state) return;
        // A LANDED file cannot be removed. It already has a job row, so
        // dropping it here would re-declare below COUNT(jobs) — which the
        // server refuses (correctly), leaving the client silently out of step
        // with the batch it is describing. Removal is for a file that has not
        // arrived and is not going to.
        const item = state.items.find((i) => i.clientFileId === clientFileId);
        if (!item || item.state.kind === 'done') return;
        abortsRef.current.get(clientFileId)?.();
        abortsRef.current.delete(clientFileId);
        fileByIdRef.current.delete(clientFileId);
        const next = { items: state.items.filter((i) => i.clientFileId !== clientFileId) };
        queueRef.current = next;
        setQueue(next);
        // Removal is one of R9's two terminal events, so it re-declares at
        // once rather than waiting for the batch to go quiet for 90 minutes.
        if (id) maybeRedeclare(next, id);
        pump();
    }, [maybeRedeclare, pump]);

    const clear = useCallback(() => {
        settleAndForget(queueRef.current, batchIdRef.current);
        abortsRef.current.forEach((abort) => abort());
        abortsRef.current.clear();
        fileByIdRef.current = new Map();
        queueRef.current = null;
        batchIdRef.current = null;
        declaredRef.current = null;
        setQueue(null);
        setBatchId(null);
    }, [settleAndForget]);

    const isActive = queue !== null && !isDrained(queue);

    // The tab-close guard. Deliberately NOT paired with an unmount abort: the
    // provider unmounts only when the whole app goes away, and an abort on
    // route change is exactly the defect Stage B exists to remove.
    useEffect(() => {
        if (!isActive) return;
        const handler = (e: BeforeUnloadEvent) => { e.preventDefault(); };
        window.addEventListener('beforeunload', handler);
        return () => window.removeEventListener('beforeunload', handler);
    }, [isActive]);

    const value = useMemo<UploadQueueApi>(() => ({
        batchId, queue, isActive, begin, retry, remove, clear,
    }), [batchId, queue, isActive, begin, retry, remove, clear]);

    return (
        <UploadQueueContext.Provider value={value}>
            {children}
        </UploadQueueContext.Provider>
    );
}
