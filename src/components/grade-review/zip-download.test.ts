/**
 * DL-2 / DL-3 — the download-all controller, driven through the REAL seam.
 *
 * `fetchReturnedExamsZip` runs for real over a stubbed `fetch`, so every
 * failure kind reaches the controller in the shape production throws it:
 * 401 → ApiAuthError (via `throwIfAuthError`), 500 → ApiError with the
 * server's Hebrew, a network drop → the TypeError `fetch` rejects with.
 * Only the browser's save (object URL + anchor click) and sonner are faked.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const toastMock = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }));
vi.mock('sonner', () => ({ toast: toastMock }));

import { fetchReturnedExamsZip } from '@/lib/api';
import { DASH_DOWNLOAD_FAILED, DASH_DOWNLOAD_STARTED } from '@/copy/grade-review';
import { createZipDownload } from './zip-download';

function deferred<T>() {
    let resolve!: (v: T) => void;
    let reject!: (e: unknown) => void;
    const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
    return { promise, resolve, reject };
}

const zipResponse = () => new Response(new Blob(['PK']), {
    status: 200, headers: { 'Content-Type': 'application/zip' },
});
const jsonResponse = (body: unknown, status: number) => new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
});

/** Flush the controller's async body after the fetch settles. */
const settle = () => new Promise((r) => setTimeout(r, 0));

function harness() {
    const busy: boolean[] = [];
    const save = vi.fn();
    const ctl = createZipDownload({
        fetchZip: () => fetchReturnedExamsZip('b-1'),
        save,
        onBusyChange: (b) => busy.push(b),
    });
    return { ctl, busy, save };
}

beforeEach(() => {
    vi.stubGlobal('localStorage', {
        getItem: () => 'stub-token', setItem: () => undefined, removeItem: () => undefined,
    });
    toastMock.success.mockReset();
    toastMock.error.mockReset();
});
afterEach(() => { vi.unstubAllGlobals(); });

describe('DL-2 NoDoubleFire', () => {
    it('a second start while in flight fires no second request', async () => {
        const gate = deferred<Response>();
        const fetchMock = vi.fn(() => gate.promise);
        vi.stubGlobal('fetch', fetchMock);
        const { ctl, busy } = harness();

        ctl.start();
        ctl.start();
        ctl.start();
        expect(fetchMock).toHaveBeenCalledTimes(1);
        expect(ctl.busy).toBe(true);
        expect(busy).toEqual([true]);

        gate.resolve(zipResponse());
        await settle();
        expect(fetchMock).toHaveBeenCalledTimes(1);
        expect(busy).toEqual([true, false]);
    });

    it('once settled, a new click is a new download', async () => {
        const fetchMock = vi.fn(async () => zipResponse());
        vi.stubGlobal('fetch', fetchMock);
        const { ctl, save } = harness();

        ctl.start();
        await settle();
        ctl.start();
        await settle();
        expect(fetchMock).toHaveBeenCalledTimes(2);
        expect(save).toHaveBeenCalledTimes(2);
    });
});

describe('DL-3 AlwaysTerminates', () => {
    it('success: saves once, one «started» toast, spinner ends', async () => {
        vi.stubGlobal('fetch', vi.fn(async () => zipResponse()));
        const { ctl, busy, save } = harness();

        ctl.start();
        await settle();
        expect(save).toHaveBeenCalledTimes(1);
        expect(save.mock.calls[0][0]).toBeInstanceOf(Blob);
        expect(toastMock.success).toHaveBeenCalledTimes(1);
        expect(toastMock.success).toHaveBeenCalledWith(DASH_DOWNLOAD_STARTED);
        expect(toastMock.error).not.toHaveBeenCalled();
        expect(busy).toEqual([true, false]);
        expect(ctl.busy).toBe(false);
    });

    const failures: [string, () => Promise<Response>, string][] = [
        ['401', async () => jsonResponse({ detail: 'Not authenticated' }, 401),
            'פג תוקף ההתחברות — יש להתחבר מחדש'],
        ['500', async () => jsonResponse({ detail: 'תקלה זמנית בשרת' }, 500),
            'תקלה זמנית בשרת'],
        ['network', async () => { throw new TypeError('Failed to fetch'); },
            DASH_DOWNLOAD_FAILED],
    ];

    it.each(failures)('%s: spinner ends, exactly one toast, nothing saved',
        async (_kind, respond, message) => {
            vi.stubGlobal('fetch', vi.fn(respond));
            const { ctl, busy, save } = harness();

            ctl.start();
            await settle();
            expect(busy).toEqual([true, false]);
            expect(ctl.busy).toBe(false);
            expect(save).not.toHaveBeenCalled();
            expect(toastMock.error).toHaveBeenCalledTimes(1);
            expect(toastMock.error).toHaveBeenCalledWith(message);
            expect(toastMock.success).not.toHaveBeenCalled();
        });

    it('a failure is not a dead end: the next click tries again', async () => {
        const fetchMock = vi.fn()
            .mockImplementationOnce(async () => jsonResponse({ detail: 'x' }, 500))
            .mockImplementationOnce(async () => zipResponse());
        vi.stubGlobal('fetch', fetchMock);
        const { ctl, save } = harness();

        ctl.start();
        await settle();
        ctl.start();
        await settle();
        expect(fetchMock).toHaveBeenCalledTimes(2);
        expect(save).toHaveBeenCalledTimes(1);
    });

    it('unmount mid-flight: no busy-state update after dispose', async () => {
        const gate = deferred<Response>();
        vi.stubGlobal('fetch', vi.fn(() => gate.promise));
        const { ctl, busy } = harness();

        ctl.start();
        ctl.dispose();
        gate.resolve(zipResponse());
        await settle();
        // Only the `true` from the click; the settle wrote nothing to a
        // component that no longer exists.
        expect(busy).toEqual([true]);
    });

    it('a disposed controller starts nothing', () => {
        const fetchMock = vi.fn(async () => zipResponse());
        vi.stubGlobal('fetch', fetchMock);
        const { ctl, busy } = harness();

        ctl.dispose();
        ctl.start();
        expect(fetchMock).not.toHaveBeenCalled();
        expect(busy).toEqual([]);
    });
});
