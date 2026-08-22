'use client';

/**
 * Completion signals for a teacher who left the tab (Dream doc §3: "leaving is
 * quietly supported"). Both are strictly BEST-EFFORT — a blocked chime or a
 * title we can't set must be silent, never an error (autoplay policy,
 * background-tab throttling). She interacted at upload, so activation is
 * satisfied in the common case; the try/catch covers the rest.
 */

const READY_TITLE = '✓ המחוון מוכן — Vivi';

let chime: HTMLAudioElement | null = null;
let originalTitle: string | null = null;

/** Play a single gentle chime once. Never throws, never awaits. */
export function playCompletionChime(): void {
    try {
        if (typeof window === 'undefined') return;
        if (!chime) {
            chime = new Audio('/chime.wav');
            chime.volume = 0.4;
        }
        chime.currentTime = 0;
        const p = chime.play();
        if (p && typeof p.catch === 'function') p.catch(() => { /* blocked — silent */ });
    } catch {
        /* never surface */
    }
}

/** Flip the tab title to the ready state, remembering the original exactly once. */
export function flipTabTitleToReady(): void {
    try {
        if (typeof document === 'undefined') return;
        if (document.title === READY_TITLE) return;
        if (originalTitle === null) originalTitle = document.title;
        document.title = READY_TITLE;
    } catch {
        /* never surface */
    }
}

/** Restore the pre-flip title (no-op if we never flipped). */
export function restoreTabTitle(): void {
    try {
        if (typeof document === 'undefined' || originalTitle === null) return;
        document.title = originalTitle;
        originalTitle = null;
    } catch {
        /* never surface */
    }
}
