'use client';

/**
 * The batch-review entry holder — owns the ONE batch fetch per route entry,
 * the Δ10 FROZEN cursor order, the Δ9 shared page-image cache, and the Δ7
 * dissolution memory.
 *
 * Why a layout-level holder and not page state (rider-a finding, 2026-08-05):
 * the App Router keys page segments by their dynamic-param VALUE, so
 * /review/a → /review/b REMOUNTS the page component — a page-held ref resets
 * silently and the order recomputes from post-accept state, the exact
 * mid-review reshuffle Δ10 forbids (verified empirically in
 * e2e/batch-review-freeze.spec.ts before this holder existed). LAYOUTS
 * preserve state across sibling page navigations within their segment and
 * remount on fresh entry — exactly Δ10's "order computed once per route
 * entry" semantics: refresh or re-entering from the batch page = fresh entry.
 *
 * Constraints owned here:
 *  - Δ11 NO POLLING: one fetch on entry; `refetchAfterAction` exists ONLY for
 *    explicit user actions (accept) and updates item STATE — never the order.
 *  - Δ10 FREEZE: `frozenOrder` is computed from the entry payload exactly once.
 *  - Δ9 PAGE CACHE: base64 page images cached per (transcription, page) for
 *    the life of the entry, shared across item navigation — which is what
 *    makes warming/prefetch worth anything. In-flight requests are deduped.
 *  - Δ7 DISSOLUTION MEMORY: per-(item, answer), session-scoped — survives
 *    arrow navigation (page remounts), dies with the entry (Δ17: refresh loss
 *    is accepted, stated behavior).
 */

import {
    createContext, useCallback, useContext, useEffect, useRef, useState,
    type ReactNode,
} from 'react';

import { getBatch, getTranscriptionPage, saveTranscriptionReview } from '@/lib/api';
import type { TranscriptionReview } from '@/lib/api';
import type { BatchDetailResponse } from '@/types/batch';
import { computeReviewOrder } from '@/utils/batch-review-cursor';

export interface BatchReviewState {
    batch: BatchDetailResponse | null;
    /** Δ10: flagged-first order from the ENTRY payload. Never recomputed. */
    frozenOrder: string[] | null;
    error: string | null;
    /**
     * Δ11: refetch as a direct consequence of an explicit user action only
     * (accept). Updates `batch` (item state) — the frozen order is untouched.
     */
    refetchAfterAction: () => Promise<void>;
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
    const frozenOrderRef = useRef<string[] | null>(null);
    const pageCacheRef = useRef(new Map<string, Promise<string>>());
    const dissolvedRef = useRef(new Map<string, Set<string>>());

    useEffect(() => {
        let cancelled = false;
        getBatch(batchId)
            .then((b) => {
                if (cancelled) return;
                if (frozenOrderRef.current === null) {
                    frozenOrderRef.current = computeReviewOrder(b.transcriptions);
                }
                setBatch(b);
            })
            .catch((e) => {
                if (!cancelled) setError(e instanceof Error ? e.message : 'שגיאה בטעינת המקבץ');
            });
        return () => { cancelled = true; };
        // Entry-only: batchId is stable for the life of the review segment.
    }, [batchId]);

    const refetchAfterAction = useCallback(async () => {
        const b = await getBatch(batchId);
        frozenOrderRef.current ??= computeReviewOrder(b.transcriptions);
        setBatch(b);
    }, [batchId]);

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
                frozenOrder: batch ? frozenOrderRef.current : null,
                error,
                refetchAfterAction,
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
