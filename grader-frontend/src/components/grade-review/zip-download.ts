'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';

import { ApiError } from '@/lib/api';
import { DASH_DOWNLOAD_FAILED, DASH_DOWNLOAD_STARTED } from '@/copy/grade-review';

/**
 * The download-all ZIP, in flight — DL-2 NoDoubleFire and DL-3 AlwaysTerminates.
 *
 * ── WHY A GUARD AND NOT JUST `disabled` ──────────────────────────────────
 * The ZIP takes a minute on a real batch (measured 2026-09-24: nine exams,
 * 52 MB, ~8 s of server render and ~50 s on the wire), and with nothing on
 * screen she clicked again fourteen seconds in. That second click was a second
 * full build on another instance and a second 52 MB transfer. A `disabled`
 * prop arrives with the NEXT render, so a fast second click can still land;
 * the flag here is set synchronously inside the first click.
 *
 * ── WHY THE SPINNER ENDS WHERE IT DOES ───────────────────────────────────
 * The bytes come back as a Blob through the seam (a plain link would 401 —
 * Bearer auth), so JS knows the moment they are all here. `save` hands them to
 * the browser, which starts its own download UI, and that is where ours stops.
 *
 * Framework-free on purpose (the `ReviewItemController` precedent): every exit
 * path is testable without a DOM, and `useZipDownload` below is a thin binding.
 */

export interface ZipDownloadDeps {
    fetchZip: () => Promise<Blob>;
    /** Hand the bytes to the browser (object URL + anchor click). */
    save: (blob: Blob) => void;
    onBusyChange: (busy: boolean) => void;
}

export interface ZipDownload {
    /** A no-op while one is in flight, or after `dispose`. */
    start(): void;
    /** Unmount: the request is left to finish (she asked for the file), but
     *  nothing is written back to a component that no longer exists. */
    dispose(): void;
    readonly busy: boolean;
}

export function createZipDownload({ fetchZip, save, onBusyChange }: ZipDownloadDeps): ZipDownload {
    let busy = false;
    let disposed = false;
    const setBusy = (next: boolean) => {
        busy = next;
        if (!disposed) onBusyChange(next);
    };

    return {
        get busy() { return busy; },
        start() {
            if (busy || disposed) return;
            setBusy(true);
            void (async () => {
                try {
                    save(await fetchZip());
                    toast.success(DASH_DOWNLOAD_STARTED);
                } catch (err) {
                    // Transport → toast (§10). A 401 arrives here as ApiAuthError
                    // from `throwIfAuthError` and stays terminal: one toast, no retry.
                    toast.error(err instanceof ApiError ? err.detail : DASH_DOWNLOAD_FAILED);
                } finally {
                    setBusy(false);
                }
            })();
        },
        dispose() { disposed = true; },
    };
}

/** React binding: `{ busy, start }`. The latest `fetchZip`/`save` are read at
 *  click time, so the batch name in the filename is never a stale closure. */
export function useZipDownload(
    fetchZip: () => Promise<Blob>,
    save: (blob: Blob) => void,
): { busy: boolean; start: () => void } {
    const [busy, setBusy] = useState(false);
    const fetchRef = useRef(fetchZip);
    fetchRef.current = fetchZip;
    const saveRef = useRef(save);
    saveRef.current = save;
    const ctlRef = useRef<ZipDownload | null>(null);

    // Built in the effect, not in render: StrictMode's mount → unmount → mount
    // would otherwise leave the one controller disposed for good.
    useEffect(() => {
        const ctl = createZipDownload({
            fetchZip: () => fetchRef.current(),
            save: (blob) => saveRef.current(blob),
            onBusyChange: setBusy,
        });
        ctlRef.current = ctl;
        return () => { ctl.dispose(); ctlRef.current = null; };
    }, []);

    const start = useCallback(() => { ctlRef.current?.start(); }, []);
    return { busy, start };
}
