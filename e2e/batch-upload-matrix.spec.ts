import { expect, test, type Page, type Route } from '@playwright/test';
import { seedAuth } from './fixtures';
import { AUTH_ME, fulfillJson } from './seedBatch';

/**
 * §4.2 — the UPLOAD screenshot matrix (P4): four states × two viewports,
 * one PNG per cell under e2e/review-artifacts/P4/. Cells:
 *   empty · files-listed (dup chip + one excluded row) · mid-upload
 *   (per-file % + aggregate bar) · complete (drained: done ✓, a terminal
 *   422 row, the explicit continue — the honest "complete with failures").
 * The protocol's second half — opening each PNG and writing the structural
 * note — happens in the phase report.
 */

const BATCH_ID = 'b0000000-0000-0000-0000-0000000000f5';

const RUBRIC = {
    id: 'r1', name: 'מחוון בדיקה', total_points: 100, total_questions: 2,
    is_compiled: true, needs_recompilation: false,
    created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
    stats: null, draft: null,
};

const pdfPayload = (name: string, content = '%PDF-1.4 stub content') => ({
    name, mimeType: 'application/pdf', buffer: Buffer.from(content),
});

async function install(page: Page, opts: {
    holdFilenames?: string[];
    reject422?: string[];
}) {
    await page.route('**/api/v0/**', async (route: Route) => {
        const url = route.request().url();
        const method = route.request().method();
        if (url.includes('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);
        if (url.includes('/extraction-jobs')) return fulfillJson(route, []);
        if (url.includes('/api/v0/rubrics/r1')) return fulfillJson(route, RUBRIC);
        if (url.includes('/api/v0/classroom/classes')) {
            return fulfillJson(route, { classes: [{ id: 'c1', name: 'יא׳3' }] });
        }
        if (method === 'POST' && /\/api\/v0\/batches$/.test(url.split('?')[0])) {
            return fulfillJson(route, { batch_id: BATCH_ID, test_count: 0 });
        }
        if (method === 'POST' && url.includes(`/files`)) {
            const filename = /filename="([^"]+)"/.exec(route.request().postData() ?? '')?.[1] ?? '';
            if (opts.holdFilenames?.includes(filename)) {
                return; // held open — the mid-upload freeze frame
            }
            if (opts.reject422?.includes(filename)) {
                return fulfillJson(route, { detail: 'קובץ ריק' }, 422);
            }
            return fulfillJson(route, { job_id: `job-${filename}`, filename, test_count: 1 });
        }
        return fulfillJson(route, {});
    });
}

const VIEWPORTS = [
    { w: 1440, h: 900 },
    { w: 390, h: 844 },
];

for (const vp of VIEWPORTS) {
    test(`matrix: upload empty @ ${vp.w}x${vp.h}`, async ({ page }) => {
        await page.setViewportSize({ width: vp.w, height: vp.h });
        await seedAuth(page);
        await install(page, {});
        await page.goto('/?rubric=r1');
        await expect(page.getByText('העלאת מבחנים')).toBeVisible();
        await expect(page.getByTestId('upload-cta')).toBeDisabled();
        await page.screenshot({
            path: `e2e/review-artifacts/P4/upload-empty-${vp.w}x${vp.h}.png`, fullPage: true,
        });
    });

    test(`matrix: upload files-listed @ ${vp.w}x${vp.h}`, async ({ page }) => {
        await page.setViewportSize({ width: vp.w, height: vp.h });
        await seedAuth(page);
        await install(page, {});
        await page.goto('/?rubric=r1');
        await expect(page.getByText('העלאת מבחנים')).toBeVisible();
        await page.setInputFiles('input[type=file]', [
            pdfPayload('מבחן_דנה.pdf'), pdfPayload('מבחן_יובל.pdf'), pdfPayload('מבחן_דנה.pdf'),
            { name: 'הערות.txt', mimeType: 'text/plain', buffer: Buffer.from('לא PDF') },
        ]);
        await expect(page.getByTestId('dup-chip')).toBeVisible();
        await expect(page.getByTestId('excluded-summary')).toBeVisible();   // the client-excluded row, with its reason
        await page.screenshot({
            path: `e2e/review-artifacts/P4/upload-files-listed-${vp.w}x${vp.h}.png`, fullPage: true,
        });
    });

    test(`matrix: upload mid-upload @ ${vp.w}x${vp.h}`, async ({ page }) => {
        await page.setViewportSize({ width: vp.w, height: vp.h });
        await seedAuth(page);
        await install(page, { holdFilenames: ['בדרך.pdf'] });
        await page.goto('/?rubric=r1');
        await expect(page.getByText('העלאת מבחנים')).toBeVisible();
        await page.setInputFiles('input[type=file]', [
            pdfPayload('נחת.pdf'), pdfPayload('בדרך.pdf'),
        ]);
        await page.getByTestId('upload-cta').click();
        await expect(page.getByTestId('row-done')).toBeVisible();          // נחת ✓
        await expect(page.getByTestId('row-uploading')).toBeVisible();     // בדרך %
        await expect(page.getByTestId('upload-aggregate')).toBeVisible();
        await page.screenshot({
            path: `e2e/review-artifacts/P4/upload-mid-upload-${vp.w}x${vp.h}.png`, fullPage: true,
        });
    });

    test(`matrix: upload complete @ ${vp.w}x${vp.h}`, async ({ page }) => {
        await page.setViewportSize({ width: vp.w, height: vp.h });
        await seedAuth(page);
        await install(page, { reject422: ['ריק.pdf'] });
        await page.goto('/?rubric=r1');
        await expect(page.getByText('העלאת מבחנים')).toBeVisible();
        await page.setInputFiles('input[type=file]', [
            pdfPayload('מבחן_דנה.pdf'), pdfPayload('ריק.pdf'),
        ]);
        await page.getByTestId('upload-cta').click();
        await expect(page.getByTestId('row-done')).toBeVisible();
        await expect(page.getByTestId('row-failed')).toBeVisible();        // the 422's verdict, verbatim
        await expect(page.getByTestId('upload-continue')).toBeVisible();   // decision 4
        await page.screenshot({
            path: `e2e/review-artifacts/P4/upload-complete-${vp.w}x${vp.h}.png`, fullPage: true,
        });
    });
}
