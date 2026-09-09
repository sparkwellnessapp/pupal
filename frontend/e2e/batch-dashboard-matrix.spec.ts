import { expect, test, type Page } from '@playwright/test';
import { seedAuth } from './fixtures';
import {
    AUTH_ME,
    fulfillJson,
    SEED_BATCH_ID,
    coldStartBatch,
    completedBatch,
    steadyBatch,
    transcribingOnlyBatch,
    uploadingBatch,
} from './seedBatch';

/**
 * §4.2 — the dashboard screenshot matrix: four states × two viewports, one
 * saved PNG per cell under e2e/review-artifacts/P2/. The protocol's second
 * half — opening each PNG and writing the structural-diff note against the
 * corresponding mockup tab — happens OUTSIDE this spec (the phase report).
 */

const STATES: Array<{ name: string; payload: () => unknown; anchor: string }> = [
    { name: 'cold-start', payload: coldStartBatch, anchor: 'zone-identity-wave' },
    { name: 'steady', payload: steadyBatch, anchor: 'zone-clean' },
    { name: 'transcribing-only', payload: transcribingOnlyBatch, anchor: 'zone-ghosts' },
    // [Stage A] The Defect-D shape: nine files still on the wire. The anchor is
    // the honesty bar because that is where the upload segment lives — and
    // because anchoring on `completion-hero` NOT appearing is what this cell is
    // really about (asserted below, and in the dedicated journey spec).
    { name: 'uploading', payload: uploadingBatch, anchor: 'segment-bar' },
    { name: 'completed', payload: completedBatch, anchor: 'completion-hero' },
];

const VIEWPORTS = [
    { w: 1440, h: 900 },
    { w: 390, h: 844 },
];

async function install(page: Page, payload: unknown) {
    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        if (url.includes('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);
        if (url.includes(`/api/v0/batches/${SEED_BATCH_ID}`)) return fulfillJson(route, payload);
        return fulfillJson(route, {});
    });
}

for (const state of STATES) {
    for (const vp of VIEWPORTS) {
        test(`matrix: dashboard ${state.name} @ ${vp.w}x${vp.h}`, async ({ page }) => {
            await page.setViewportSize({ width: vp.w, height: vp.h });
            await seedAuth(page);
            await install(page, state.payload());

            await page.goto(`/batches/${SEED_BATCH_ID}`);
            await expect(page.getByTestId(state.anchor)).toBeVisible();
            // [Stage A] The cell exists to prove the batch does NOT claim to be
            // finished while files are still arriving.
            if (state.name === 'uploading') {
                await expect(page.getByTestId('completion-hero')).toHaveCount(0);
                await expect(page.getByTestId('batch-status-chip')).toHaveText('בהעלאה');
            }
            // Let the expanded steady peek render for the richer cell.
            if (state.name === 'steady' && vp.w > 940) {
                await page.getByTestId('clean-row').first().click();
                await expect(page.getByTestId('clean-peek')).toBeVisible();
            }
            await page.screenshot({
                path: `e2e/review-artifacts/P2/dashboard-${state.name}-${vp.w}x${vp.h}.png`,
                fullPage: true,
            });
        });
    }
}
