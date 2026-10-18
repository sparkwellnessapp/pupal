/**
 * Demo-mode event log — the core. `lib/demo/` is THE ONLY place in the app
 * that knows demo mode exists (single-entry-point rule): every other module
 * calls a demo function, and every demo function returns before doing any
 * work when `isDemo()` is false.
 *
 * WHAT IT IS FOR: a screen recording of a batch-grading session, edited later
 * by a tool that cannot watch video. The log is that tool's eyes — timestamped
 * app events with on-screen rectangles, aligned to the frames by the white
 * sync flash (Ctrl+Shift+S, `DemoLogProvider`).
 *
 * THE RULES IT KEEPS:
 *   · Off by default. Off means: no listeners, no storage writes, no output.
 *   · Never throws, never awaits, never blocks — every body is a try/catch.
 *   · Frontend only. Nothing is sent anywhere; the log leaves the browser
 *     only when someone presses Ctrl+Shift+E.
 *   · Privacy: ids, counters, statuses and positions. Never a student name,
 *     answer text, rubric text or file name — a call site that passes one in
 *     `meta` is a bug.
 *
 * SESSIONS (D3, owner-approved): a session is the browser TAB. Its `startedAt`
 * rides sessionStorage, so a reload inside the tab RESUMES the same log from
 * the localStorage mirror instead of splitting the recording in two. A stored
 * log from any other session is moved to `vivi_demo_log_prev_<startedAt>`
 * before a new one starts — never overwritten silently; if that move fails the
 * new session stays in memory (still exportable) rather than clobber it.
 * `performance.now()` restarts on a reload, so `epoch` is the canonical clock
 * for syncing against the video; `t` is only monotonic within one page load.
 */

export type DemoMeta = Record<string, string | number | boolean | null>;

export interface DemoRect {
    x: number;
    y: number;
    w: number;
    h: number;
    scrollX: number;
    scrollY: number;
}

export interface DemoEvent {
    t: number;
    epoch: number;
    type: string;
    id: string | null;
    rect: DemoRect | null;
    meta: DemoMeta | null;
}

export interface DemoHeader {
    v: 1;
    startedAt: number;
    viewport: { w: number; h: number };
    dpr: number;
    userAgent: string;
}

export type DemoLogFile = DemoHeader & { events: DemoEvent[] };

const FLAG_KEY = 'vivi_demo';
const SESSION_KEY = 'vivi_demo_session';
export const LOG_KEY = 'vivi_demo_log';
export const PREV_PREFIX = 'vivi_demo_log_prev_';

/** Latched: once demo mode is seen in this page load it stays on. */
let active = false;
let log: DemoLogFile | null = null;
/** False when a previous session's log could not be archived (see header). */
let mirror = true;

type StoreName = 'localStorage' | 'sessionStorage';

function storeGet(store: StoreName, key: string): string | null {
    try { return window[store].getItem(key); } catch { return null; }
}

function storeSet(store: StoreName, key: string, value: string): boolean {
    try { window[store].setItem(key, value); return true; } catch { return false; }
}

function storeRemove(store: StoreName, key: string): void {
    try { window[store].removeItem(key); } catch { /* ignore */ }
}

/**
 * True when the URL carries `demo=1` or this tab already saw it. Seeing it in
 * the URL stores the flag in sessionStorage, so demo mode survives client
 * navigation and URL changes. SSR-safe: false without a `window`.
 */
export function isDemo(): boolean {
    if (active) return true;
    if (typeof window === 'undefined') return false;
    try {
        let fromUrl = false;
        try {
            fromUrl = new URLSearchParams(window.location.search).get('demo') === '1';
        } catch { fromUrl = false; }
        if (fromUrl) {
            storeSet('sessionStorage', FLAG_KEY, '1');
            active = true;
            return true;
        }
        active = storeGet('sessionStorage', FLAG_KEY) === '1';
        return active;
    } catch {
        return false;
    }
}

function parseLog(raw: string | null): DemoLogFile | null {
    if (raw === null) return null;
    try {
        const parsed = JSON.parse(raw) as DemoLogFile;
        return parsed && typeof parsed.startedAt === 'number' && Array.isArray(parsed.events)
            ? parsed : null;
    } catch {
        return null;
    }
}

function persist(): void {
    if (!mirror || !log) return;
    // Quota errors are ignored: the in-memory log (and the export) stay whole.
    storeSet('localStorage', LOG_KEY, JSON.stringify(log));
}

function ensureLog(): DemoLogFile {
    if (log) return log;
    const raw = storeGet('localStorage', LOG_KEY);
    const stored = parseLog(raw);
    const tabSession = Number(storeGet('sessionStorage', SESSION_KEY)) || null;

    if (stored && tabSession !== null && stored.startedAt === tabSession) {
        log = stored;                      // a reload inside the same tab: resume
        return log;
    }

    if (raw !== null) {
        // Never overwrite silently: park the previous session's log first.
        let key = PREV_PREFIX + (stored ? stored.startedAt : Date.now());
        if (storeGet('localStorage', key) !== null) key += `_${Date.now()}`;
        if (storeSet('localStorage', key, raw)) {
            storeRemove('localStorage', LOG_KEY);
        } else {
            mirror = false;
            console.warn('[demo] could not archive the previous log; this session stays in memory only');
        }
    }

    log = {
        v: 1,
        startedAt: Date.now(),
        viewport: { w: window.innerWidth, h: window.innerHeight },
        dpr: window.devicePixelRatio,
        userAgent: window.navigator.userAgent,
        events: [],
    };
    storeSet('sessionStorage', SESSION_KEY, String(log.startedAt));
    persist();
    return log;
}

function resolveElement(el: Element | string | null | undefined): Element | null {
    if (!el) return null;
    if (typeof el !== 'string') return el;
    return window.document.querySelector(`[data-demo="${el}"]`);
}

function rectOf(el: Element | null): DemoRect | null {
    if (!el || typeof el.getBoundingClientRect !== 'function') return null;
    const r = el.getBoundingClientRect();
    return {
        x: r.x, y: r.y, w: r.width, h: r.height,
        scrollX: window.scrollX, scrollY: window.scrollY,
    };
}

function demoIdOf(el: Element | null): string | null {
    if (!el || typeof el.closest !== 'function') return null;
    return el.closest('[data-demo]')?.getAttribute('data-demo') ?? null;
}

/**
 * Append one event. No-op when demo mode is off.
 *
 * `el` is the element the event is about — or a `data-demo` id, resolved
 * here so a call site does no DOM work while the flag is off. Its rect is
 * viewport-relative CSS px, plus the page scroll at that moment.
 */
export function demoLog(type: string, meta?: DemoMeta, el?: Element | string | null): void {
    try {
        if (!isDemo()) return;
        const file = ensureLog();
        const target = resolveElement(el);
        file.events.push({
            t: performance.now(),
            epoch: Date.now(),
            type,
            id: demoIdOf(target),
            rect: rectOf(target),
            meta: meta ?? null,
        });
        persist();
    } catch {
        /* the logger never throws */
    }
}

/** Download the session as `events-<startedAt>.json`: `{ ...header, events }`. */
export function exportLog(): void {
    try {
        if (!isDemo()) return;
        const file = ensureLog();
        const blob = new Blob([JSON.stringify(file, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const anchor = window.document.createElement('a');
        anchor.href = url;
        anchor.download = `events-${file.startedAt}.json`;
        window.document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        // Firefox starts a blob: download asynchronously; same margin as the app's.
        setTimeout(() => URL.revokeObjectURL(url), 10_000);
    } catch {
        /* the logger never throws */
    }
}

/** Clear the in-memory and stored log; the next event starts a new session. Manual use only. */
export function resetLog(): void {
    try {
        log = null;
        mirror = true;
        storeRemove('localStorage', LOG_KEY);
        storeRemove('sessionStorage', SESSION_KEY);
    } catch {
        /* the logger never throws */
    }
}
