'use client';

/**
 * The batch-review entry holder — owns the batch payload, the OD2
 * APPEND-ONLY cursor, the Δ9 shared page-image cache, and the Δ7 dissolution
 * memory.
 *
 * Why a layout-level holder and not page state (rider-a finding, 2026-08-05):
 * the App Router keys page segments by their dynamic-param VALUE, so
 * /review/a → /review/b REMOUNTS the page component — a page-held ref resets
 * silently and the order recomputes from post-accept state, the exact
 * mid-review reshuffle the freeze rule forbids (verified empirically in
 * e2e/batch-review-freeze.spec.ts before this holder existed). LAYOUTS
 * preserve state across sibling page navigations within their segment and
 * remount on fresh entry.
 *
 * OD2 (P3/R6 — the sanctioned Δ10 amendment): the cursor is PREFIX-STABLE,
 * APPEND-ONLY. Existing entries never move (even when their verdicts change);
 * late arrivals append — flagged at the partition boundary, clean at the
 * tail. ONE mergePayload() is the sole writer, fed by the entry fetch, the
 * post-accept refetch, and a 5s poll that runs ONLY while documents are
 * still in flight (rollup.uploading > 0 || rollup.transcribing > 0 ||
 * active_jobs non-empty — the first arm is Stage A's upload stage) and
 * tears down the tick that condition clears. Totals grow; the counter bump
 * is the only signal. Δ11's same-id-refresh-never-clobbers-edits still holds
 * at the controller layer.
 *
 * Also owned here (R11): the soft refetch note — set by the page when a
 * post-accept refetch fails, survives the intra-segment route.replace of the
 * auto-advance, cleared by the next successful fetch.
 *
 *  - Δ9 PAGE CACHE: base64 page images cached per (transcription, page) for
 *    the life of the entry, shared across item navigation. Deduped in-flight.
 *  - Δ7 DISSOLUTION MEMORY: per-(item, answer), session-scoped — survives
 *    arrow navigation, dies with the entry (Δ17: refresh loss is accepted).
 */

import {
    createContext, useCallback, useContext, useEffect, useRef, useState,
    type ReactNode,
} from 'react';

import { getBatch, getRubric, getTranscriptionPage, saveTranscriptionReview } from '@/lib/api';
import type { TranscriptionReview } from '@/lib/api';
import type { BatchDetailResponse } from '@/types/batch';
import {
    appendNewItems,
    initialCursor,
    type FrozenCursor,
} from '@/utils/batch-review-cursor';
import { BATCH_LOAD_ERROR } from '@/copy/batch';
import { isIdentityPending } from '@/utils/zone-assignment';

const POLL_MS = 5000;

export interface BatchReviewState {
    batch: BatchDetailResponse | null;
    /** OD2: the append-only cursor (order + flagged boundary). */
    cursor: FrozenCursor | null;
    /** Back-compat view of cursor.order (existing consumers). */
    frozenOrder: string[] | null;
    error: string | null;
    /** The rubric's subject key (migration 027) — null until the rubric loads
     *  (or when its fetch fails: the review still works, in today's direction). */
    rubricSubject: string | null;
    /** R11: post-accept refetch failed — accepted state stands, data catches
     *  up later. Cleared by the next successful fetch. */
    softNote: string | null;
    showSoftNote: (note: string) => void;
    /** Refetch as a direct consequence of an explicit user action (accept).
     *  Merges state + APPENDS new ids (OD2) — never reorders. Throws on
     *  failure so the caller can decouple accept-success from refetch (R11).
     *  Returns the merged payload so R4's advance decision can run against
     *  the freshest snapshot without waiting for a React re-render. */
    refetchAfterAction: () => Promise<BatchDetailResponse>;
    /** The cursor as of NOW (the ref, updated synchronously by mergePayload) —
     *  for decisions inside async handlers (R4/R6 edge: an append landing
     *  during an accept advance must be visible to advanceTarget). */
    getCursor: () => FrozenCursor | null;
    /** Merge a just-saved overlay into the in-memory payload (no refetch). */
    applyReviewLocally: (transcriptionId: string, review: TranscriptionReview) => void;
    /** Δ9: cached, deduped page image (base64 PNG). */
    getPage: (transcriptionId: string, pageNumber: number) => Promise<string>;
    /** Non-throwing prefetch warm-up (background/idle use). */
    warmPage: (transcriptionId: string, pageNumber: number) => void;
    /** Δ7 session memory. */
    isDissolved: (transcriptionId: string, answerKey: string) => boolean;
    markDissolved: (transcriptionId: string, answerKey: string) => void;
    save: typeof saveTranscriptionReview;
}

const BatchReviewCtx = createContext<BatchReviewState | null>(null);

export function useBatchReview(): BatchReviewState {
    const ctx = useContext(BatchReviewCtx);
    if (!ctx) {
        throw new Error('useBatchReview must be used inside BatchReviewProvider');
    }
    return ctx;
}

export function BatchReviewProvider({ batchId, children }: {
    batchId: string;
    children: ReactNode;
}) {
    const [batch, setBatch] = useState<BatchDetailResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [rubricSubject, setRubricSubject] = useState<string | null>(null);
    const [softNote, setSoftNote] = useState<string | null>(null);
    const cursorRef = useRef<FrozenCursor | null>(null);
    const pageCacheRef = useRef(new Map<string, Promise<string>>());
    const dissolvedRef = useRef(new Map<string, Set<string>>());
    const aliveRef = useRef(true);
    const fetchingRef = useRef(false);

    useEffect(() => {
        aliveRef.current = true;
        return () => { aliveRef.current = false; };
    }, []);

    /** OD2's sole writer: entry fetch, poll, and refetchAfterAction all land
     *  here. Prefix-stable append + state replacement + soft-note clear.
     *
     *  ZC-1 v2/Q3 (owner-ruled 2026-08-23): the cursor's flagged partition is
     *  the WALK's definition of flagged — identity-pending items (only flag =
     *  extracted new name, untouched) walk as CLEAN, so the eyes CTA count
     *  and the walk's stop count agree. One predicate, shared with the
     *  dashboard (zone-assignment.ts). */
    const mergePayload = useCallback((b: BatchDetailResponse) => {
        const walkItems = b.transcriptions.map((t) => ({
            transcription_id: String(t.transcription_id),
            flag_verdict: {
                review_needed: t.flag_verdict.review_needed && !isIdentityPending(t),
            },
        }));
        cursorRef.current = cursorRef.current === null
            ? initialCursor(walkItems)
            : appendNewItems(cursorRef.current, walkItems);
        setBatch(b);
        setSoftNote(null);          // R11: a successful fetch clears the note
    }, []);

    useEffect(() => {
        let cancelled = false;
        getBatch(batchId)
            .then((b) => {
                if (cancelled) return;
                mergePayload(b);
                // The subject rides the rubric row (migration 027). Its fetch is
                // CONTEXT for direction, never a gate: a failure leaves it null and
                // the surface renders in today's direction.
                getRubric(b.rubric_id)
                    .then((r) => {
                        if (!cancelled) setRubricSubject((r as { subject?: string | null }).subject ?? null);
                    })
                    .catch(() => { /* direction context only */ });
            })
            .catch((e) => {
                if (!cancelled) setError(e instanceof Error ? e.message : BATCH_LOAD_ERROR);
            });
        return () => { cancelled = true; };
        // Entry-only: batchId is stable for the life of the review segment.
    }, [batchId, mergePayload]);

    // OD2 poll: ONLY while documents are still in flight. The interval dies
    // the tick the condition clears; a failing poll is silent (transient —
    // the next tick or the next explicit action recovers).
    // [Stage A] `uploading` joins the in-flight test: while she reviews the
    // documents that landed first, later ones are still climbing the wire and
    // will append to the cursor (OD2). A gate that watched only `transcribing`
    // would stop polling in the gap between "the last landed file finished
    // transcribing" and "the next file arrives" — and the review surface would
    // sit there believing the batch was done.
    const stillInFlight = batch !== null
        && ((batch.rollup.uploading ?? 0) > 0
            || batch.rollup.transcribing > 0
            || (batch.active_jobs?.length ?? 0) > 0);
    useEffect(() => {
        if (!stillInFlight) return;
        const tick = async () => {
            if (fetchingRef.current) return;      // never overlap fetches
            fetchingRef.current = true;
            try {
                const b = await getBatch(batchId);
                if (aliveRef.current) mergePayload(b);
            } catch {
                /* transient poll failure — silent by design */
            } finally {
                fetchingRef.current = false;
            }
        };
        const interval = setInterval(() => { void tick(); }, POLL_MS);
        return () => clearInterval(interval);
    }, [stillInFlight, batchId, mergePayload]);

    const refetchAfterAction = useCallback(async (): Promise<BatchDetailResponse> => {
        const b = await getBatch(batchId);
        if (aliveRef.current) mergePayload(b);
        return b;
    }, [batchId, mergePayload]);

    const getCursor = useCallback(() => cursorRef.current, []);

    const showSoftNote = useCallback((note: string) => setSoftNote(note), []);

    const applyReviewLocally = useCallback((transcriptionId: string, review: TranscriptionReview) => {
        setBatch((prev) => prev && {
            ...prev,
            transcriptions: prev.transcriptions.map((t) =>
                t.transcription_id === transcriptionId ? { ...t, review } : t),
        });
    }, []);

    const getPage = useCallback((transcriptionId: string, pageNumber: number): Promise<string> => {
        const key = `${transcriptionId}:${pageNumber}`;
        const cached = pageCacheRef.current.get(key);
        if (cached) return cached;
        const inflight = getTranscriptionPage(transcriptionId, pageNumber)
            .then((r) => r.thumbnail_base64);
        inflight.catch(() => pageCacheRef.current.delete(key)); // failed fetches retry next time
        pageCacheRef.current.set(key, inflight);
        return inflight;
    }, []);

    const warmPage = useCallback((transcriptionId: string, pageNumber: number) => {
        void getPage(transcriptionId, pageNumber).catch(() => { /* warm-up only */ });
    }, [getPage]);

    const isDissolved = useCallback((transcriptionId: string, answerKey: string): boolean =>
        dissolvedRef.current.get(transcriptionId)?.has(answerKey) ?? false, []);

    const markDissolved = useCallback((transcriptionId: string, answerKey: string) => {
        const set = dissolvedRef.current.get(transcriptionId) ?? new Set<string>();
        set.add(answerKey);
        dissolvedRef.current.set(transcriptionId, set);
    }, []);

    return (
        <BatchReviewCtx.Provider
            value={{
                batch,
                cursor: batch ? cursorRef.current : null,
                frozenOrder: batch ? cursorRef.current?.order ?? null : null,
                error,
                rubricSubject,
                softNote,
                showSoftNote,
                refetchAfterAction,
                getCursor,
                applyReviewLocally,
                getPage,
                warmPage,
                isDissolved,
                markDissolved,
                save: saveTranscriptionReview,
            }}
        >
            {children}
        </BatchReviewCtx.Provider>
    );
}
