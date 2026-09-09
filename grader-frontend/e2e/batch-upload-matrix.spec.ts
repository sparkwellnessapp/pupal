import { expect, test, type Page, type Route } from '@playwright/test';
import { seedAuth } from './fixtures';
import { AUTH_ME, fulfillJson, seedBatch } from './seedBatch';

/**
 * §4.2 — the UPLOAD screenshot matrix (P4): four states × two viewports,
 * one PNG per cell under e2e/review-artifacts/P4/. Cells:
 *   empty · files-listed (dup chip + one excluded row) · lane-mid-upload ·
 *   lane-complete.
 *
 * [Stage B / R3] The last two cells MOVED. They used to photograph the upload
 * page mid-transfer, because the redirect waited for the last byte; she is now
 * sent to the dashboard on create and the transfers render in its lane. So the
 * cells still photograph the same two moments — one file landed and one still
 * climbing, then drained with a terminal 422 — at their new address. The upload
 * page itself has no in-flight state left to photograph.
 *
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
        // [Stage B] The two in-flight cells now photograph the DASHBOARD, so
        // this route has to answer with a real payload rather than `{}` —
        // the lane renders beside the board, not instead of it.
        if (method === 'GET' && url.includes(`/api/v0/batches/${BATCH_ID}`)) {
            return fulfillJson(route, seedBatch({
                id: BATCH_ID, items: [], rollup: { uploading: 1, total: 2 },
            }));
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

    test(`matrix: upload lane-mid-upload @ ${vp.w}x${vp.h}`, async ({ page }) => {
        await page.setViewportSize({ width: vp.w, height: vp.h });
        await seedAuth(page);
        await install(page, { holdFilenames: ['בדרך.pdf'] });
        await page.goto('/?rubric=r1');
        await expect(page.getByText('העלאת מבחנים')).toBeVisible();
        await page.setInputFiles('input[type=file]', [
            pdfPayload('נחת.pdf'), pdfPayload('בדרך.pdf'),
        ]);
        await page.getByTestId('upload-cta').click();

        // She is on the dashboard within a beat, and BOTH transfers are still
        // running there — the one that landed and the one that has not.
        await expect(page).toHaveURL(new RegExp(`/batches/${BATCH_ID}$`));
        const lane = page.getByTestId('zone-upload');
        await expect(lane).toBeVisible();
        await expect(lane.locator('[data-state="done"]')).toHaveCount(1);       // נחת ✓
        await expect(lane.locator('[data-state="uploading"]')).toHaveCount(1);  // בדרך %
        await page.screenshot({
            path: `e2e/review-artifacts/P4/upload-lane-mid-upload-${vp.w}x${vp.h}.png`, fullPage: true,
        });
    });

    test(`matrix: upload lane-complete @ ${vp.w}x${vp.h}`, async ({ page }) => {
        await page.setViewportSize({ width: vp.w, height: vp.h });
        await seedAuth(page);
        await install(page, { reject422: ['ריק.pdf'] });
        await page.goto('/?rubric=r1');
        await expect(page.getByText('העלאת מבחנים')).toBeVisible();
        await page.setInputFiles('input[type=file]', [
            pdfPayload('מבחן_דנה.pdf'), pdfPayload('ריק.pdf'),
        ]);
        await page.getByTestId('upload-cta').click();

        await expect(page).toHaveURL(new RegExp(`/batches/${BATCH_ID}$`));
        const lane = page.getByTestId('zone-upload');
        // Drained with a file left behind: the lane STAYS, because a batch that
        // is quietly short is the silent drop U4 exists to kill.
        await expect(lane.locator('[data-state="failed"]')).toHaveCount(1);
        await expect(lane.getByTestId('upload-lane-reason')).toBeVisible();  // the 422's verdict, verbatim
        await expect(lane.getByTestId('upload-lane-dismiss')).toBeVisible();
        await page.screenshot({
            path: `e2e/review-artifacts/P4/upload-lane-complete-${vp.w}x${vp.h}.png`, fullPage: true,
        });
    });
}
