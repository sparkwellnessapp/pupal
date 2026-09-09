'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { fetchPageImageObjectUrl } from '@/lib/api';

/**
 * Page-1 thumbnails for the Pile — one shared cache, fetched lazily.
 *
 * ── WHY THE CACHE LIVES HERE AND NOT IN THE CARD ─────────────────────────
 * The dashboard POLLS. Each poll replaces the payload and re-renders every
 * card, so a per-card `useEffect` would re-fetch and re-allocate a blob per
 * card per tick — the HTTP cache spares the network, but the churn is real and
 * every object URL leaks unless something revokes it. The cache is keyed by
 * PATH and outlives any individual card, exactly like
 * `BatchReviewContext.getPage` (Δ9): one entry per key, in-flight requests
 * deduped, failures dropped so they retry.
 *
 * ── WHY LAZILY ───────────────────────────────────────────────────────────
 * B1 costs `<img loading="lazy">`: a blob URL cannot be lazily loaded, because
 * by the time it exists the bytes are already downloaded. On a thirty-card grid
 * most cards are below the fold and a school connection should not fetch them
 * all on mount, so an IntersectionObserver puts the laziness back.
 *
 * ── THE LIFECYCLE, WHICH IS THE WHOLE DIFFICULTY ─────────────────────────
 * Ref callbacks run in the COMMIT phase, before effects. Two earlier shapes
 * both failed, in opposite directions:
 *
 *   observer built in an effect → always null when the first cards register,
 *     so every one took the eager fallback and the laziness never happened;
 *   observer built lazily in `register` → the mount effect's cleanup
 *     disconnected it under React's double-invoke and nothing ever re-observed,
 *     so no thumbnail loaded at all.
 *
 * The shape that works: `register` only RECORDS (and observes if an observer
 * happens to exist); the EFFECT owns the observer's lifetime and adopts
 * everything already recorded. Correct whichever runs first, and idempotent
 * under a double mount.
 */
export function usePageThumbnails() {
    const cacheRef = useRef(new Map<string, string>());
    const inflightRef = useRef(new Map<string, Promise<void>>());
    const observerRef = useRef<IntersectionObserver | null>(null);
    /** Every card element seen so far → its image path. Strong on purpose: the
     *  effect iterates it to adopt elements registered before it ran. */
    const registeredRef = useRef(new Map<Element, string>());
    const disposedRef = useRef(false);
    const [, bump] = useState(0);

    const load = useCallback((path: string) => {
        if (cacheRef.current.has(path) || inflightRef.current.has(path)) return;
        const request = fetchPageImageObjectUrl(path)
            .then((url) => {
                // Unmounted while this was in flight: the cleanup already ran
                // and cleared the map, so nothing would ever revoke this URL
                // and its bytes would be pinned for the life of the document.
                if (disposedRef.current) { URL.revokeObjectURL(url); return; }
                cacheRef.current.set(path, url);
                bump((n) => n + 1);
            })
            .catch(() => {
                // A failed thumbnail is never fatal to a card: the pile still
                // shows the score, the name and the state. It retries the next
                // time the card scrolls into view.
            })
            .finally(() => { inflightRef.current.delete(path); });
        inflightRef.current.set(path, request);
    }, []);

    useEffect(() => {
        disposedRef.current = false;
        const registered = registeredRef.current;

        if (typeof IntersectionObserver === 'undefined') {
            // No observer at all (jsdom, an old browser): fetch everything
            // rather than nothing — a missing optimisation must not become a
            // missing feature.
            for (const path of registered.values()) load(path);
            return () => { disposedRef.current = true; };
        }

        // 300px of runway: the image is in flight before the card arrives, so
        // scrolling reveals a picture rather than a placeholder.
        const observer = new IntersectionObserver((entries) => {
            for (const entry of entries) {
                if (!entry.isIntersecting) continue;
                const path = registered.get(entry.target);
                if (path) { load(path); observer.unobserve(entry.target); }
            }
        }, { rootMargin: '300px' });
        observerRef.current = observer;

        // Adopt every card that registered during the commit phase.
        for (const element of registered.keys()) observer.observe(element);

        const cache = cacheRef.current;
        return () => {
            disposedRef.current = true;
            observer.disconnect();
            observerRef.current = null;
            for (const url of cache.values()) URL.revokeObjectURL(url);
            cache.clear();
            registered.clear();
        };
    }, [load]);

    /** Ref callback for a card. Records; the effect does the watching. */
    const register = useCallback((element: Element | null, path: string | null) => {
        if (!element || !path || cacheRef.current.has(path)) return;
        registeredRef.current.set(element, path);
        observerRef.current?.observe(element);
    }, []);

    const urlFor = useCallback(
        (path: string | null | undefined) => (path ? cacheRef.current.get(path) ?? null : null),
        [],
    );

    return { register, urlFor };
}
