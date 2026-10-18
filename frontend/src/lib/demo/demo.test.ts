/**
 * The demo log (`lib/demo/`): off is a no-op, on appends the documented shape,
 * export is valid JSON, and storage failures never throw.
 *
 * The suite runs in `node` (no jsdom in this repo), so each test installs a
 * minimal fake `window` — exactly the surface `core.ts` touches — and loads
 * the module fresh, because its state (the latch, the log) is module-level.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';

type Core = typeof import('./core');
type Events = typeof import('./events');

interface FakeStore {
    getItem(key: string): string | null;
    setItem(key: string, value: string): void;
    removeItem(key: string): void;
    keys(): string[];
}

function memoryStore(failOn: (key: string) => boolean = () => false): FakeStore {
    const map = new Map<string, string>();
    return {
        getItem: (key) => (map.has(key) ? map.get(key)! : null),
        setItem: (key, value) => {
            if (failOn(key)) throw new Error('QuotaExceededError');
            map.set(key, String(value));
        },
        removeItem: (key) => { map.delete(key); },
        keys: () => Array.from(map.keys()),
    };
}

function brokenStore(): FakeStore {
    const fail = () => { throw new Error('SecurityError'); };
    return { getItem: fail, setItem: fail, removeItem: fail, keys: () => [] };
}

/** A fake element: `demoId` on itself (or on an ancestor via `parent`). */
function fakeElement(opts: { demoId?: string; parent?: ReturnType<typeof fakeElement>; id?: string } = {}) {
    const el = {
        id: opts.id,
        getAttribute: (name: string) => (name === 'data-demo' ? opts.demoId ?? null : null),
        closest: (selector: string): unknown => {
            if (selector !== '[data-demo]') return null;
            if (opts.demoId) return el;
            return opts.parent ? opts.parent.closest(selector) : null;
        },
        getBoundingClientRect: () => ({ x: 10, y: 20, width: 100, height: 40 }),
    };
    return el;
}

interface Env {
    local: FakeStore;
    session: FakeStore;
    downloads: { href: string; download: string }[];
    elements: ReturnType<typeof fakeElement>[];
}

function installWindow(opts: {
    search?: string; local?: FakeStore; session?: FakeStore;
    elements?: ReturnType<typeof fakeElement>[];
} = {}): Env {
    const env: Env = {
        local: opts.local ?? memoryStore(),
        session: opts.session ?? memoryStore(),
        downloads: [],
        elements: opts.elements ?? [],
    };
    const document = {
        querySelector: (selector: string) => {
            const m = /^\[data-demo="(.+)"\]$/.exec(selector);
            return m ? env.elements.find((e) => e.getAttribute('data-demo') === m[1]) ?? null : null;
        },
        getElementById: (id: string) => env.elements.find((e) => e.id === id) ?? null,
        createElement: () => {
            const anchor = {
                href: '', download: '',
                click: () => { env.downloads.push({ href: anchor.href, download: anchor.download }); },
                remove: () => undefined,
            };
            return anchor;
        },
        body: { appendChild: () => undefined },
    };
    vi.stubGlobal('window', {
        location: { search: opts.search ?? '' },
        localStorage: env.local,
        sessionStorage: env.session,
        innerWidth: 1440,
        innerHeight: 900,
        devicePixelRatio: 2,
        scrollX: 0,
        scrollY: 120,
        navigator: { userAgent: 'test-agent' },
        document,
    });
    return env;
}

async function load(): Promise<{ core: Core; events: Events }> {
    vi.resetModules();
    const core = await import('./core');
    const events = await import('./events');
    return { core, events };
}

function storedLog(env: Env) {
    const raw = env.local.getItem('vivi_demo_log');
    return raw ? JSON.parse(raw) : null;
}

afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
});

describe('flag off', () => {
    it('is a no-op: no events, no storage writes, no export', async () => {
        const env = installWindow();
        const setLocal = vi.spyOn(env.local, 'setItem');
        const setSession = vi.spyOn(env.session, 'setItem');
        const { core } = await load();

        expect(core.isDemo()).toBe(false);
        core.demoLog('click', { tag: 'button' }, fakeElement({ demoId: 'approve-button' }) as unknown as Element);
        core.exportLog();

        expect(setLocal).not.toHaveBeenCalled();
        expect(setSession).not.toHaveBeenCalled();
        expect(env.local.keys()).toEqual([]);
        expect(env.session.keys()).toEqual([]);
        expect(env.downloads).toEqual([]);
    });

    it('derived helpers do no work at all — the batch is never even read', async () => {
        const env = installWindow();
        const { events } = await load();
        let reads = 0;
        const batch = { get transcriptions() { reads += 1; return []; }, get rollup() { reads += 1; return null; } };
        const model = { get scopes() { reads += 1; return []; } };

        events.observeBatch(batch);
        events.demoObserveScores('v5', 'g1', model);
        events.demoTestApproved(batch, { byId: {} });
        events.demoFeedbackViewOpened('g1');
        events.demoPdfDownloaded();
        events.demoBatchZipDownloaded(batch);

        expect(reads).toBe(0);
        expect(env.local.keys()).toEqual([]);
        expect(env.session.keys()).toEqual([]);
    });

    it('is SSR-safe: false without a window, and never throws', async () => {
        const { core } = await load();
        expect(typeof window).toBe('undefined');
        expect(core.isDemo()).toBe(false);
        expect(() => core.demoLog('route', { path: '/' })).not.toThrow();
        expect(() => core.exportLog()).not.toThrow();
    });
});

describe('flag on', () => {
    it('turns on from ?demo=1 and remembers it for the tab', async () => {
        const env = installWindow({ search: '?demo=1' });
        let { core } = await load();
        expect(core.isDemo()).toBe(true);
        expect(env.session.getItem('vivi_demo')).toBe('1');

        // A later page load in the same tab, with no flag in the URL.
        installWindow({ search: '', session: env.session, local: env.local });
        ({ core } = await load());
        expect(core.isDemo()).toBe(true);
    });

    it('appends events with the documented shape and mirrors the log', async () => {
        const approve = fakeElement({ demoId: 'approve-button' });
        const child = fakeElement({ parent: approve });
        const env = installWindow({ search: '?demo=1', elements: [approve] });
        const { core } = await load();

        core.demoLog('click', { tag: 'span' }, child as unknown as Element);
        core.demoLog('sync');
        core.demoLog('test_approved', { i: 1, total: 15 }, 'approve-button');
        core.demoLog('pdf_downloaded', { count: 1 }, 'pdf-download');   // not on screen

        const log = storedLog(env);
        expect(log).toMatchObject({
            v: 1, viewport: { w: 1440, h: 900 }, dpr: 2, userAgent: 'test-agent',
        });
        expect(typeof log.startedAt).toBe('number');
        expect(log.events).toHaveLength(4);

        const [click, sync, approved, pdf] = log.events;
        expect(Object.keys(click).sort()).toEqual(['epoch', 'id', 'meta', 'rect', 't', 'type']);
        expect(typeof click.t).toBe('number');
        expect(typeof click.epoch).toBe('number');
        expect(click).toMatchObject({
            type: 'click', id: 'approve-button', meta: { tag: 'span' },
            rect: { x: 10, y: 20, w: 100, h: 40, scrollX: 0, scrollY: 120 },
        });
        expect(sync).toMatchObject({ type: 'sync', id: null, rect: null, meta: null });
        expect(approved).toMatchObject({ id: 'approve-button', meta: { i: 1, total: 15 } });
        expect(approved.rect).not.toBeNull();
        expect(pdf).toMatchObject({ id: null, rect: null, meta: { count: 1 } });
    });

    it("archives a previous session's log instead of overwriting it", async () => {
        const local = memoryStore();
        const previous = JSON.stringify({ v: 1, startedAt: 111, events: [{ type: 'old' }] });
        local.setItem('vivi_demo_log', previous);
        const env = installWindow({ search: '?demo=1', local });
        const { core } = await load();

        core.demoLog('route', { path: '/' });

        expect(env.local.getItem('vivi_demo_log_prev_111')).toBe(previous);
        const log = storedLog(env);
        expect(log.startedAt).not.toBe(111);
        expect(log.events.map((e: { type: string }) => e.type)).toEqual(['route']);
    });

    it('keeps the old log untouched when it cannot be archived', async () => {
        vi.spyOn(console, 'warn').mockImplementation(() => undefined);
        const local = memoryStore((key) => key.startsWith('vivi_demo_log_prev_'));
        const previous = JSON.stringify({ v: 1, startedAt: 222, events: [] });
        local.setItem('vivi_demo_log', previous);
        const env = installWindow({ search: '?demo=1', local });
        const { core } = await load();

        core.demoLog('route', { path: '/' });

        expect(env.local.getItem('vivi_demo_log')).toBe(previous);
    });

    it('resumes the same log after a reload in the same tab', async () => {
        const env = installWindow({ search: '?demo=1' });
        let { core } = await load();
        core.demoLog('route', { path: '/' });
        core.demoLog('click', { tag: 'button' });
        const startedAt = storedLog(env).startedAt;

        installWindow({ search: '', local: env.local, session: env.session });
        ({ core } = await load());
        core.demoLog('route', { path: '/batches/b1' });

        const log = storedLog(env);
        expect(log.startedAt).toBe(startedAt);
        expect(log.events).toHaveLength(3);
        expect(env.local.keys().some((k) => k.startsWith('vivi_demo_log_prev_'))).toBe(false);
    });

    it('exports valid JSON: the header plus every event', async () => {
        const env = installWindow({ search: '?demo=1' });
        let blob: Blob | null = null;
        vi.spyOn(URL, 'createObjectURL').mockImplementation((b) => { blob = b as Blob; return 'blob:demo'; });
        vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
        const { core } = await load();

        core.demoLog('route', { path: '/' });
        core.demoLog('sync');
        core.exportLog();

        const startedAt = storedLog(env).startedAt;
        expect(env.downloads).toEqual([{ href: 'blob:demo', download: `events-${startedAt}.json` }]);
        expect(blob).not.toBeNull();
        const parsed = JSON.parse(await (blob as unknown as Blob).text());
        expect(parsed).toMatchObject({ v: 1, startedAt, viewport: { w: 1440, h: 900 }, dpr: 2 });
        expect(parsed.events.map((e: { type: string }) => e.type)).toEqual(['route', 'sync']);
    });

    it('never throws when storage is unavailable, and still exports from memory', async () => {
        installWindow({ search: '?demo=1', local: brokenStore(), session: brokenStore() });
        let blob: Blob | null = null;
        vi.spyOn(URL, 'createObjectURL').mockImplementation((b) => { blob = b as Blob; return 'blob:demo'; });
        vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
        const { core, events } = await load();

        expect(core.isDemo()).toBe(true);
        expect(() => core.demoLog('click', { tag: 'div' })).not.toThrow();
        expect(() => events.observeBatch({ transcriptions: [
            { transcription_id: 't1', transcription_status: 'transcribed' },
        ] })).not.toThrow();
        expect(() => core.exportLog()).not.toThrow();
        expect(() => core.resetLog()).not.toThrow();

        const parsed = JSON.parse(await (blob as unknown as Blob).text());
        expect(parsed.events.map((e: { type: string }) => e.type)).toEqual(['click', 'transcription_ready']);
    });

    it('survives quota errors on the mirror', async () => {
        const local = memoryStore((key) => key === 'vivi_demo_log');
        installWindow({ search: '?demo=1', local });
        const { core } = await load();
        expect(() => core.demoLog('click', { tag: 'div' })).not.toThrow();
    });
});

describe('derived events', () => {
    const types = (env: Env) => storedLog(env).events.map((e: { type: string; meta: unknown }) => [e.type, e.meta]);

    it('transcription_ready once per test; grading_status only on a real transition', async () => {
        const env = installWindow({ search: '?demo=1', elements: [fakeElement({ demoId: 'batch-progress' })] });
        const { events } = await load();
        const row = (id: string, t: string, g: string | null, gid: string | null = null) => ({
            transcription_id: id, transcription_status: t, graded_test_status: g, graded_test_id: gid,
        });

        events.observeBatch({ transcriptions: [row('t1', 'transcribed', null)] });
        events.observeBatch({ transcriptions: [row('t1', 'transcribed', null)] });          // a poll: nothing
        events.observeBatch({ transcriptions: [row('t1', 'approved', 'pending', 'g1')] });
        events.observeBatch({ transcriptions: [
            row('t1', 'approved', 'grading', 'g1'), row('t2', 'transcribed', null),
        ] });
        // First sighting of an already-graded test is a baseline, not a transition.
        events.observeBatch({ transcriptions: [
            row('t1', 'approved', 'grading', 'g1'), row('t2', 'transcribed', null),
            row('t3', 'approved', 'draft', 'g3'),
        ] });

        expect(types(env)).toEqual([
            ['transcription_ready', { testIndex: 1 }],
            ['grading_status', { testIndex: 1, from: null, to: 'pending' }],
            ['grading_status', { testIndex: 1, from: 'pending', to: 'grading' }],
            ['transcription_ready', { testIndex: 2 }],
        ]);
        expect(storedLog(env).events[0].id).toBe('batch-progress');
    });

    it('does not re-announce after a reload in the same tab', async () => {
        const env = installWindow({ search: '?demo=1' });
        let { events } = await load();
        const batch = { transcriptions: [{ transcription_id: 't1', transcription_status: 'transcribed' }] };
        events.observeBatch(batch);

        installWindow({ search: '', local: env.local, session: env.session });
        ({ events } = await load());
        events.observeBatch(batch);

        expect(types(env)).toEqual([['transcription_ready', { testIndex: 1 }]]);
    });

    it('override_edited fires per changed scope, after the baseline, with testIndex', async () => {
        const scope = fakeElement({ id: 'scope-q2' });
        const env = installWindow({ search: '?demo=1', elements: [scope] });
        const { events } = await load();
        events.observeBatch({ transcriptions: [
            { transcription_id: 't1', graded_test_id: 'g1' },
            { transcription_id: 't2', graded_test_id: 'g2' },
        ] });
        const model = (q1: string, q2: string) => ({ scopes: [
            { scopeId: 'q1', criteria: [{ terminalId: 'q1/c1', awarded: q1 }] },
            { scopeId: 'q2', criteria: [{ terminalId: 'q2/c1', awarded: q2 }] },
        ] });

        events.demoObserveScores('v6', 'g2', model('5', '3'));      // baseline
        events.demoObserveScores('v6', 'g2', model('5', '3'));      // re-render, no change
        events.demoObserveScores('v6', 'g2', model('5', '1.5'));    // she changed q2
        events.demoObserveScores('v5', 'g2', model('0', '0'));      // another surface's baseline

        expect(types(env)).toEqual([['override_edited', { testIndex: 2, scopeId: 'q2' }]]);
        expect(storedLog(env).events[0].rect).not.toBeNull();
    });

    it('test_approved counts approved tests in the cursor against the batch size', async () => {
        const env = installWindow({ search: '?demo=1' });
        const { events } = await load();
        events.demoTestApproved(
            { rollup: { total: 15 } },
            { byId: { a: { status: 'approved' }, b: { status: 'approved' }, c: { status: 'draft' } } },
        );
        expect(types(env)).toEqual([['test_approved', { i: 2, total: 15 }]]);
    });

    it('feedback_view_opened and the ZIP download resolve their numbers from the batch', async () => {
        const env = installWindow({ search: '?demo=1' });
        const { events } = await load();
        const batch = {
            transcriptions: [
                { transcription_id: 't1', graded_test_id: 'g1' },
                { transcription_id: 't2', graded_test_id: 'g2' },
            ],
            graded_tests: [
                { graded_test_id: 'g1', transcription_id: 't1', status: 'approved' },
                { graded_test_id: 'g2', transcription_id: 't2', status: 'draft' },
            ],
        };
        events.observeBatch(batch);
        events.demoFeedbackViewOpened('g2');
        events.demoFeedbackViewOpened('unknown');
        events.demoPdfDownloaded();
        events.demoBatchZipDownloaded(batch);

        expect(types(env)).toEqual([
            ['feedback_view_opened', { testIndex: 2 }],
            ['feedback_view_opened', { testIndex: null }],
            ['pdf_downloaded', { count: 1 }],
            ['pdf_downloaded', { count: 1 }],
        ]);
    });
});
