import { expect, test, type Page } from '@playwright/test';
import { seedAuth } from './fixtures';
import { AUTH_ME, fulfillJson, minutesAgo, seedRollup } from './seedBatch';

/**
 * §4.2 — the LIST screenshot matrix (P5): two states × two viewports under
 * e2e/review-artifacts/P5/. The populated cell deliberately mixes every
 * lifecycle the mini bar can draw (arriving · decisions owed · in grading ·
 * complete · failed) so one PNG proves the whole vocabulary.
 */

const row = (over: Record<string, unknown>) => ({
    id: 'b0000000-0000-0000-0000-00000000000a',
    name: 'מקבץ בדיקה',
    rubric_id: 'r1',
    class_id: 'c1',
    rubric_name: 'מתכונת 1 — שאלון 899371',
    class_name: 'יא׳3',
    status: 'in_progress',
    created_at: minutesAgo(120),
    rollup: seedRollup({ total: 0 }),
    ...over,
});

const POPULATED = [
    row({
        id: 'b-1', name: 'מתכונת קיץ · יא׳3 · 18.8.2026',
        rollup: seedRollup({ transcribing: 3, transcribed: 2, approved: 1, total: 6 }),
        created_at: minutesAgo(12),
    }),
    row({
        id: 'b-2', name: 'מבחן מחצית · יב׳1',
        rollup: seedRollup({ transcribed: 5, approved: 2, total: 7 }),
        created_at: minutesAgo(95),
    }),
    row({
        id: 'b-3', name: null, class_name: null,        // → fallback name, no class
        rollup: seedRollup({ draft: 3, grading: 1, approved: 4, total: 8 }),
        created_at: minutesAgo(400),
    }),
    row({
        id: 'b-4', name: 'הכול אושר', status: 'completed',
        rollup: seedRollup({ approved: 5, total: 5 }),
        created_at: minutesAgo(1500),
    }),
    row({
        id: 'b-5', name: 'עם כשלים', status: 'partially_completed',
        rollup: seedRollup({ approved: 3, transcription_failed: 2, total: 5 }),
        created_at: minutesAgo(2000),
    }),
];

async function install(page: Page, batches: unknown[]) {
    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        if (url.includes('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);
        if (/\/api\/v0\/batches(\?[^/]*)?$/.test(url)) return fulfillJson(route, batches);
        return fulfillJson(route, {});
    });
}

const VIEWPORTS = [
    { w: 1440, h: 900 },
    { w: 390, h: 844 },
];

for (const vp of VIEWPORTS) {
    test(`matrix: list populated @ ${vp.w}x${vp.h}`, async ({ page }) => {
        await page.setViewportSize({ width: vp.w, height: vp.h });
        await seedAuth(page);
        await install(page, POPULATED);
        await page.goto('/batches');
        await expect(page.getByTestId('batch-row')).toHaveCount(5);
        await expect(page.getByTestId('segment-bar')).toHaveCount(5);
        await page.screenshot({
            path: `e2e/review-artifacts/P5/list-populated-${vp.w}x${vp.h}.png`, fullPage: true,
        });
    });

    test(`matrix: list empty @ ${vp.w}x${vp.h}`, async ({ page }) => {
        await page.setViewportSize({ width: vp.w, height: vp.h });
        await seedAuth(page);
        await install(page, []);
        await page.goto('/batches');
        await expect(page.getByTestId('list-empty')).toBeVisible();
        await page.screenshot({
            path: `e2e/review-artifacts/P5/list-empty-${vp.w}x${vp.h}.png`, fullPage: true,
        });
    });
}
