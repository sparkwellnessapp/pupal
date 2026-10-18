'use client';

/**
 * The demo log's always-mounted half (root layout). With demo mode off it
 * renders nothing and attaches nothing: the route tracker below only reads the
 * router and asks `isDemo()`, which writes nothing.
 *
 * With demo mode on:
 *   · a capture-phase `click` listener logs every click with its target's rect;
 *   · route changes log `route {path}` (the pathname only — never the query);
 *   · `resize` logs `viewport {w, h, dpr}` (trailing 200 ms, so a drag is one event);
 *   · Ctrl+Shift+S logs `sync` and shows a full-viewport white flash for 250 ms
 *     — the frame the video editor aligns the log to;
 *   · Ctrl+Shift+E downloads the log.
 *   Both hotkeys are taken at the WINDOW in the capture phase and stopped there
 *   (D2): the review keymaps read Ctrl+S with Shift ignored, so without the stop
 *   the sync key would also fire «save now».
 *   · A 6 px gray dot sits bottom-left while active (hidden during the flash),
 *     so whoever is recording can see demo mode is on.
 *   · `window.__viviDemo = { exportLog, resetLog }` for manual use from DevTools.
 */

import { Suspense, useEffect, useRef, useState } from 'react';
import { usePathname, useSearchParams } from 'next/navigation';

import { demoLog, exportLog, isDemo, resetLog } from './core';

const FLASH_MS = 250;
const RESIZE_SETTLE_MS = 200;

export function DemoLogProvider() {
    const [active, setActive] = useState(false);
    return (
        <>
            {/* useSearchParams needs a Suspense boundary under the App Router. */}
            <Suspense fallback={null}>
                <DemoRouteTracker onActive={setActive} />
            </Suspense>
            {active ? <DemoActive /> : null}
        </>
    );
}

function DemoRouteTracker({ onActive }: { onActive: (active: boolean) => void }) {
    const pathname = usePathname();
    const query = useSearchParams()?.toString() ?? '';
    useEffect(() => {
        if (!isDemo()) return;
        onActive(true);
        demoLog('route', { path: pathname });
    }, [pathname, query, onActive]);
    return null;
}

function keyOf(event: KeyboardEvent, code: string, letter: string): boolean {
    return event.code === code || (!event.code && event.key?.toLowerCase() === letter);
}

function DemoActive() {
    const flashRef = useRef<HTMLDivElement>(null);
    const dotRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        let flashTimer: ReturnType<typeof setTimeout> | null = null;
        let resizeTimer: ReturnType<typeof setTimeout> | null = null;

        const showFlash = (on: boolean) => {
            if (flashRef.current) flashRef.current.style.display = on ? 'block' : 'none';
            if (dotRef.current) dotRef.current.style.display = on ? 'none' : 'block';
        };

        const onClick = (event: MouseEvent) => {
            try {
                const target = event.target;
                if (target instanceof Element) {
                    demoLog('click', { tag: target.tagName.toLowerCase() }, target);
                }
            } catch { /* never throws */ }
        };

        const onResize = () => {
            if (resizeTimer) clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => demoLog('viewport', {
                w: window.innerWidth, h: window.innerHeight, dpr: window.devicePixelRatio,
            }), RESIZE_SETTLE_MS);
        };

        const onKeyDown = (event: KeyboardEvent) => {
            try {
                if (!event.ctrlKey || !event.shiftKey || event.altKey || event.metaKey) return;
                const sync = keyOf(event, 'KeyS', 's');
                const exportKey = keyOf(event, 'KeyE', 'e');
                if (!sync && !exportKey) return;
                event.preventDefault();
                event.stopImmediatePropagation();
                if (event.repeat) return;            // a held key is one press
                if (sync) {
                    demoLog('sync');
                    showFlash(true);
                    if (flashTimer) clearTimeout(flashTimer);
                    flashTimer = setTimeout(() => showFlash(false), FLASH_MS);
                } else {
                    exportLog();
                }
            } catch { /* never throws */ }
        };

        window.addEventListener('click', onClick, true);
        window.addEventListener('resize', onResize);
        window.addEventListener('keydown', onKeyDown, true);
        const handle = window as unknown as { __viviDemo?: unknown };
        handle.__viviDemo = { exportLog, resetLog };
        return () => {
            window.removeEventListener('click', onClick, true);
            window.removeEventListener('resize', onResize);
            window.removeEventListener('keydown', onKeyDown, true);
            if (flashTimer) clearTimeout(flashTimer);
            if (resizeTimer) clearTimeout(resizeTimer);
            delete handle.__viviDemo;
        };
    }, []);

    return (
        <>
            <div
                ref={flashRef}
                aria-hidden="true"
                style={{
                    display: 'none', position: 'fixed', inset: 0, background: '#FFFFFF',
                    zIndex: 2147483647, pointerEvents: 'none',
                }}
            />
            <div
                ref={dotRef}
                aria-hidden="true"
                style={{
                    position: 'fixed', left: 8, bottom: 8, width: 6, height: 6,
                    borderRadius: '50%', background: '#9CA3AF',
                    zIndex: 2147483647, pointerEvents: 'none',
                }}
            />
        </>
    );
}
