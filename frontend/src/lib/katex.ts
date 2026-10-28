/**
 * KaTeX, loaded on demand (MATH_RENDERING_PLAN §4).
 *
 * CODE-SPLIT ON PURPOSE: KaTeX and its stylesheet are a chunk of their own, fetched the
 * first time a math answer is on screen. A computer-science or English page never
 * requests it. Until it arrives, `MathText` shows each span's source — the same thing
 * it shows when a span cannot render — so nothing is hidden while it loads.
 *
 * Rendering is CACHED by span body: a review screen re-renders on every hover, and a
 * formula's HTML is a pure function of its source.
 */
import { useEffect, useState } from 'react';

type Katex = typeof import('katex').default;

let loaded: Katex | null = null;
let pending: Promise<Katex> | null = null;

export function loadKatex(): Promise<Katex> {
    if (!pending) {
        pending = import('./katex-bundle').then((m) => {
            loaded = m.default;
            return loaded;
        });
    }
    return pending;
}

export function katexIfLoaded(): Katex | null {
    return loaded;
}

/** KaTeX once it is here; `null` before. Starts the load when `needed` — a line with no
 *  formula never fetches the chunk. */
export function useKatex(needed = true): Katex | null {
    const [k, setK] = useState<Katex | null>(loaded);
    useEffect(() => {
        if (k || !needed) return;
        let alive = true;
        loadKatex().then((m) => { if (alive) setK(() => m); }).catch(() => { /* raw stays */ });
        return () => { alive = false; };
    }, [k, needed]);
    return k;
}

export type MathRender = { ok: true; html: string } | { ok: false; error: string };

const cache = new Map<string, MathRender>();
const CACHE_MAX = 2000;

export function renderMathBody(katex: Katex, body: string): MathRender {
    const hit = cache.get(body);
    if (hit) return hit;
    let out: MathRender;
    try {
        out = {
            ok: true,
            // throwOnError: a span KaTeX cannot parse must SAY so (the raw source and a
            // marker), never render red error text inside the student's answer.
            // trust stays false: no \href, no \includegraphics, no HTML from an answer.
            html: katex.renderToString(body, { throwOnError: true, strict: 'ignore', trust: false }),
        };
    } catch (e) {
        out = { ok: false, error: e instanceof Error ? e.message : String(e) };
    }
    if (cache.size >= CACHE_MAX) cache.clear();
    cache.set(body, out);
    return out;
}
