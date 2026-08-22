import { expect, test, type Page, type Route } from '@playwright/test';
import { seedAuth } from './fixtures';
import { AUTH_ME, fulfillJson, seedBatch, seedItem } from './seedBatch';

/**
 * P4 — the upload-surface journeys (spec §6):
 *  - upload-journey (U1): ONE path — a single file becomes a batch of one and
 *    lands on the dashboard; the mode toggle and the dual CTA are gone; the
 *    composed name (B5) rides the metadata create.
 *  - inline-states (U3/U4): a 422 renders its server reason inline and offers
 *    NO retry; a network failure retries with the SAME client_file_id (the
 *    B9 idempotency contract, asserted on the wire); failures block
 *    auto-navigation; the explicit continue appears once ≥1 landed.
 *  - form-truths (U2): dup chip on identical (name,size) pairs, the §3.2
 *    truncation notice at >50, LTR size spans, disabled-CTA reason.
 */

const BATCH_ID = 'b0000000-0000-0000-0000-0000000000f4';

const RUBRIC = {
    id: 'r1', name: 'מחוון בדיקה', total_points: 100, total_questions: 2,
    is_compiled: true, needs_recompilation: false,
    created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
    stats: null, draft: null,
};

const pdfPayload = (name: string, content = '%PDF-1.4 stub content') => ({
    name, mimeType: 'application/pdf', buffer: Buffer.from(content),
});

interface UploadMockState {
    createBodies: Array<Record<string, unknown>>;
    /** filename → every client_file_id seen for it, in order. */
    appendIds: Map<string, string[]>;
    /** filename → behavior for the NEXT append of that file. */
    behaviors: Map<string, 'ok' | '422' | 'net-once'>;
}

function parseMultipart(post: string | null): { filename: string; clientFileId: string } {
    const filename = /filename="([^"]+)"/.exec(post ?? '')?.[1] ?? '';
    const clientFileId =
        /name="client_file_id"\r\n\r\n([0-9a-f-]+)/.exec(post ?? '')?.[1] ?? '';
    return { filename, clientFileId };
}

async function installMocks(page: Page): Promise<UploadMockState> {
    const state: UploadMockState = {
        createBodies: [],
        appendIds: new Map(),
        behaviors: new Map(),
    };

    await page.route('**/api/v0/**', async (route: Route) => {
        const url = route.request().url();
        const method = route.request().method();

        if (url.includes('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);
        if (url.includes('/extraction-jobs')) return fulfillJson(route, []);
        if (url.includes('/api/v0/rubrics/r1')) return fulfillJson(route, RUBRIC);
        if (url.includes('/api/v0/classroom/classes')) {
            return fulfillJson(route, { classes: [{ id: 'c1', name: 'יא׳3' }] });
        }
        if (url.includes('/api/v0/classroom/students')) {
            return fulfillJson(route, { students: [] });
        }
        if (method === 'POST' && /\/api\/v0\/batches$/.test(url.split('?')[0])) {
            state.createBodies.push(route.request().postDataJSON() as Record<string, unknown>);
            return fulfillJson(route, { batch_id: BATCH_ID, test_count: 0 });
        }
        if (method === 'POST' && url.includes(`/api/v0/batches/${BATCH_ID}/files`)) {
            const { filename, clientFileId } = parseMultipart(route.request().postData());
            const seen = state.appendIds.get(filename) ?? [];
            seen.push(clientFileId);
            state.appendIds.set(filename, seen);
            const behavior = state.behaviors.get(filename) ?? 'ok';
            if (behavior === '422') {
                return fulfillJson(route, { detail: 'לא קובץ PDF' }, 422);
            }
            if (behavior === 'net-once') {
                state.behaviors.set(filename, 'ok');   // heal on the retry
                return route.abort('failed');
            }
            return fulfillJson(route, {
                job_id: `job-${filename}`, filename, test_count: seen.length,
            });
        }
        if (url.includes(`/api/v0/batches/${BATCH_ID}`)) {
            return fulfillJson(route, seedBatch({
                id: BATCH_ID,
                items: [seedItem('t1', { filename: 'a.pdf' })],
                rollup: { transcribing: 0, total: 1 },
            }));
        }
        return fulfillJson(route, {});
    });

    return state;
}

test('upload-journey (U1) — one path: a single file becomes a batch of one and lands on the dashboard', async ({ page }) => {
    await seedAuth(page);
    const state = await installMocks(page);

    await page.goto('/?rubric=r1');
    await expect(page.getByText('העלאת מבחנים')).toBeVisible();
    await expect(page.getByText('מחוון בדיקה')).toBeVisible();

    // The census's dual-CTA world is GONE: no mode toggle, no single-file CTA,
    // no indigo batch panel.
    await expect(page.getByRole('button', { name: /תמלול כתב יד/ })).toHaveCount(0);
    await expect(page.getByRole('button', { name: /התחל בדיקה/ })).toHaveCount(0);
    await expect(page.getByRole('button', { name: /בדוק כאצווה/ })).toHaveCount(0);

    // B5: the name field arrives composed (rubric · he-IL date; no class picked).
    const nameInput = page.getByTestId('batch-name-input');
    await expect(nameInput).toHaveValue(/^מחוון בדיקה · \d{1,2}\.\d{1,2}\.\d{4}$/);

    // The CTA is disabled (with its reason) until a file lands — AM3 singular after one.
    await expect(page.getByTestId('upload-cta')).toBeDisabled();
    await expect(page.getByTestId('upload-cta')).toHaveAttribute('title', 'בחרי לפחות קובץ PDF אחד כדי להתחיל');
    await page.setInputFiles('input[type=file]', [pdfPayload('a.pdf')]);
    await expect(page.getByTestId('upload-cta')).toHaveText(/התחלת תמלול \(מבחן אחד\)/);

    await page.getByTestId('upload-cta').click();

    // All landed → auto-navigation to the dashboard (decision 4).
    await expect(page).toHaveURL(new RegExp(`/batches/${BATCH_ID}$`));

    // The wire: metadata-only create carried the composed name; the append
    // carried a client-generated UUID idempotency key.
    expect(state.createBodies).toHaveLength(1);
    expect(state.createBodies[0].rubric_id).toBe('r1');
    expect(String(state.createBodies[0].name)).toMatch(/^מחוון בדיקה · \d{1,2}\.\d{1,2}\.\d{4}$/);
    const ids = state.appendIds.get('a.pdf') ?? [];
    expect(ids).toHaveLength(1);
    expect(ids[0]).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/);
});

test('inline-states (U3/U4) — 422 terminal inline, network retry keeps the SAME client_file_id, continue after partial success', async ({ page }) => {
    await seedAuth(page);
    const state = await installMocks(page);
    state.behaviors.set('bad.pdf', '422');
    state.behaviors.set('flaky.pdf', 'net-once');

    await page.goto('/?rubric=r1');
    await expect(page.getByText('העלאת מבחנים')).toBeVisible();
    await page.setInputFiles('input[type=file]', [
        pdfPayload('good.pdf'), pdfPayload('bad.pdf'), pdfPayload('flaky.pdf'),
    ]);
    await expect(page.getByTestId('upload-cta')).toHaveText(/התחלת תמלול \(3 מבחנים\)/);
    await page.getByTestId('upload-cta').click();

    // Drained with failures → NO auto-navigation; each row tells its truth.
    await expect(page.getByTestId('row-done')).toBeVisible();          // good.pdf ✓
    const failedRows = page.getByTestId('row-failed');
    await expect(failedRows).toHaveCount(2);
    await expect(page.getByText('לא קובץ PDF')).toBeVisible();         // the server's 422 verdict, verbatim
    // Exactly ONE retry affordance: the network failure. The 422 is terminal.
    await expect(page.getByTestId('row-retry')).toHaveCount(1);
    await expect(page).toHaveURL(/\/\?rubric=r1$/);

    // Partial success → the explicit continue is offered (decision 4).
    await expect(page.getByTestId('upload-continue')).toBeVisible();

    // Live-E2E fix (2026-08-22): the page now SAYS transcription is already
    // running server-side — the mock batch serves one transcribed row, so
    // the signal reads the AM3 singular. She is no longer staring at a page
    // that pretends nothing is happening.
    await expect(page.getByTestId('upload-live-progress'))
        .toHaveText('תמלול אחד כבר מוכן לעיון', { timeout: 10_000 });

    // Retry the network failure: the SAME idempotency key rides the wire.
    await page.getByTestId('row-retry').click();
    await expect(page.getByTestId('row-done')).toHaveCount(2);
    const flakyIds = state.appendIds.get('flaky.pdf') ?? [];
    expect(flakyIds).toHaveLength(2);
    expect(flakyIds[0]).toBe(flakyIds[1]);                             // B9: retry ≠ new identity

    // The 422 stays failed; the teacher moves on explicitly.
    await expect(page.getByTestId('row-failed')).toHaveCount(1);
    await page.getByTestId('upload-continue').click();
    await expect(page).toHaveURL(new RegExp(`/batches/${BATCH_ID}$`));

    // D1 (closeout): the batch has no memory of `bad.pdf` — jobs ARE the
    // total (B9.5), so it renders as a coherent 2-item batch. Without the
    // handoff she would arrive at a tidy batch that is quietly short, which
    // is the silent drop U4 kills at intake relocated one screen later.
    await expect(page.getByTestId('upload-failures-notice')).toBeVisible();
    await expect(page.getByTestId('upload-failures-notice')).toContainText('bad.pdf');
    await expect(page.getByTestId('upload-failures-notice')).toContainText('לא הועלה');

    // It is a notice, not a blocker.
    await page.getByRole('button', { name: 'סגירת ההודעה' }).click();
    await expect(page.getByTestId('upload-failures-notice')).toBeHidden();

    // ONE-SHOT: a reload must not resurrect it (the handoff is consumed).
    await page.reload();
    await expect(page.getByTestId('upload-failures-notice')).toHaveCount(0);
});

test('form-truths (U2) — dup chip, >50 truncation notice, LTR sizes', async ({ page }) => {
    await seedAuth(page);
    await installMocks(page);

    await page.goto('/?rubric=r1');
    await expect(page.getByText('העלאת מבחנים')).toBeVisible();

    // Duplicate (name, size) pair → ONE advisory chip on the later row.
    await page.setInputFiles('input[type=file]', [pdfPayload('a.pdf'), pdfPayload('b.pdf')]);
    await page.setInputFiles('input[type=file]', [pdfPayload('a.pdf')]);
    await expect(page.getByTestId('dup-chip')).toHaveCount(1);
    await expect(page.getByText('כפילות אפשרית — שם וגודל זהים')).toBeVisible();

    // Sizes are LTR islands.
    const size = page.getByTestId('file-size').first();
    await expect(size).toHaveAttribute('dir', 'ltr');
    await expect(size).toHaveText(/MB$/);

    // >50 keeps the first 50 AND says so.
    await page.setInputFiles('input[type=file]',
        Array.from({ length: 49 }, (_, i) => pdfPayload(`bulk${i}.pdf`)));
    await expect(page.getByTestId('truncation-notice')).toHaveText('נבחרו יותר מ-50 קבצים — נכללו 50 הראשונים');
    await expect(page.getByTestId('upload-row')).toHaveCount(50);
    await expect(page.getByTestId('upload-cta')).toHaveText(/התחלת תמלול \(50 מבחנים\)/);
});
