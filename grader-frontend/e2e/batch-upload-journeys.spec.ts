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
    behaviors: Map<string, 'ok' | '422' | 'net-once' | 'hang'>;
    /** [Stage A/R9] every expected_test_count the client re-declared, in order. */
    redeclared: number[];
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
        redeclared: [],
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
            const body = route.request().postDataJSON() as Record<string, unknown>;
            state.createBodies.push(body);
            return fulfillJson(route, {
                batch_id: BATCH_ID, test_count: 0,
                expected_test_count: body.expected_test_count ?? null,
            });
        }
        // [Stage A/R9] the re-declare
        if (method === 'PATCH' && url.includes(`/api/v0/batches/${BATCH_ID}`)) {
            const body = route.request().postDataJSON() as Record<string, unknown>;
            if (typeof body.expected_test_count === 'number') {
                state.redeclared.push(body.expected_test_count);
            }
            return fulfillJson(route, {
                batch_id: BATCH_ID, name: null,
                expected_test_count: body.expected_test_count ?? null,
            });
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
            if (behavior === 'hang') {
                // Never resolves: the transfer stays in flight for the whole
                // test, which is what R10 needs to observe.
                return new Promise(() => {});
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

test('inline-states (U3/U4) — the SAME invariants, now on the dashboard lane', async ({ page }) => {
    // [Stage B / R3] Re-homed, not weakened (the §4.4a precedent). This journey
    // used to run entirely on the upload page, because the redirect waited for
    // the last byte. It no longer does: she is sent to the dashboard on create
    // and watches the transfers there. The invariants are unchanged and every
    // one of them is still asserted:
    //   * a 422 renders the server's Hebrew verdict VERBATIM and offers NO retry;
    //   * a network failure retries with the SAME client_file_id (B9) — the
    //     contract that makes a retry incapable of minting a second test;
    //   * failures stay visible instead of vanishing into a tidy short batch.
    // What is GONE is the four-minute wait and the explicit continue that
    // existed only to end it.
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

    // THE Stage B claim: she leaves at once, and the transfers survive the
    // route change instead of being aborted by the unmounting page.
    await expect(page).toHaveURL(new RegExp(`/batches/${BATCH_ID}$`));

    const lane = page.getByTestId('zone-upload');
    await expect(lane).toBeVisible();

    // good.pdf landed AFTER the navigation — the whole point.
    await expect(lane.locator('[data-state="done"]')).toHaveCount(1);

    // The 422's verdict, verbatim, with NO retry; the network failure keeps one.
    await expect(lane.getByTestId('upload-lane-reason').filter({ hasText: 'לא קובץ PDF' }))
        .toBeVisible();
    await expect(lane.locator('[data-state="failed"]')).toHaveCount(2);
    await expect(lane.getByTestId('upload-lane-retry')).toHaveCount(1);

    // Retry the network failure: the SAME idempotency key rides the wire.
    await lane.getByTestId('upload-lane-retry').click();
    await expect(lane.locator('[data-state="done"]')).toHaveCount(2);
    const flakyIds = state.appendIds.get('flaky.pdf') ?? [];
    expect(flakyIds).toHaveLength(2);
    expect(flakyIds[0]).toBe(flakyIds[1]);                             // B9: retry ≠ new identity

    // The 422 stays failed and stays VISIBLE: a batch that is quietly short is
    // the silent drop U4 kills at intake, relocated one screen later.
    await expect(lane.locator('[data-state="failed"]')).toHaveCount(1);
    await expect(lane).toContainText('bad.pdf');

    // R9's explicit half: removing it re-declares the batch's expected count
    // rather than leaving it to the 90-minute backstop.
    await lane.getByTestId('upload-lane-remove').click();
    expect(state.redeclared.at(-1)).toBe(2);

    // Nothing moving and nothing left behind ⇒ the lane has said all it has to
    // say and gets out of the way.
    await expect(page.getByTestId('zone-upload')).toHaveCount(0);
});

test('dismissing a lane with files left behind SETTLES the batch (review fix)', async ({ page }) => {
    // The bug this pins: `declaredCount` keeps a RETRYABLE failure in the
    // declaration on the reasoning that she may still click «נסי שוב» — true
    // only while the queue exists. Dismissing without settling left the server
    // holding expected > COUNT(jobs), so the batch reported "1 file still
    // uploading", pinned itself to in_progress and drew an uploading segment,
    // about a file that was not on the wire and that nothing could put there —
    // for ninety minutes, with the retry gone along with the lane. The X says
    // "close this list"; it must not also mean "abandon this file and misreport
    // it".
    await seedAuth(page);
    const state = await installMocks(page);
    state.behaviors.set('flaky.pdf', 'net-once');

    await page.goto('/?rubric=r1');
    await page.setInputFiles('input[type=file]', [
        pdfPayload('good.pdf'), pdfPayload('flaky.pdf'),
    ]);
    await page.getByTestId('upload-cta').click();
    await expect(page).toHaveURL(new RegExp(`/batches/${BATCH_ID}$`));

    const lane = page.getByTestId('zone-upload');
    await expect(lane.locator('[data-state="failed"]')).toHaveCount(1);
    // Still declared as 2: a retryable failure keeps its slot while she can act.
    expect(state.redeclared).not.toContain(1);

    await lane.getByTestId('upload-lane-dismiss').click();
    await expect(page.getByTestId('zone-upload')).toHaveCount(0);

    // Letting go IS a terminal event: the honest declaration is what landed.
    await expect.poll(() => state.redeclared.at(-1)).toBe(1);
});

test('one uploading batch at a time (R10) — the second start links to the first', async ({ page }) => {
    await seedAuth(page);
    const state = await installMocks(page);
    state.behaviors.set('slow.pdf', 'hang');

    await page.goto('/?rubric=r1');
    await page.setInputFiles('input[type=file]', [pdfPayload('slow.pdf')]);
    await page.getByTestId('upload-cta').click();
    await expect(page).toHaveURL(new RegExp(`/batches/${BATCH_ID}$`));

    // Back to the upload page with that transfer still in flight — via the
    // browser's own back, i.e. a SOFT navigation. A `page.goto` here would be a
    // full reload, which tears down the provider along with the page and is the
    // one case Stage B explicitly does not defend (the beforeunload guard is
    // what covers it). Soft navigation is the case that must keep the queue.
    await page.goBack();
    await expect(page.getByText('העלאת מבחנים')).toBeVisible();
    await page.setInputFiles('input[type=file]', [pdfPayload('second.pdf')]);
    await page.getByTestId('upload-cta').click();

    // No second batch is created, and she is pointed at the one running.
    await expect(page.getByTestId('upload-busy-notice')).toBeVisible();
    expect(state.createBodies).toHaveLength(1);
    await page.getByTestId('upload-busy-link').click();
    await expect(page).toHaveURL(new RegExp(`/batches/${BATCH_ID}$`));
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
