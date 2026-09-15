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
    mixedThirtyBatch,
    signedOffBatch,
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
    // [§5.1E/F] RENAMED IN MEANING, not in file name. This payload is every
    // TRANSCRIPTION approved — four steps from the end — and it used to fire the
    // green-check hero. It now collapses to a one-line strip, and the cell
    // asserts the celebration is ABSENT (below): that assertion is the
    // "exactly one celebration" claim, checked where it used to be broken.
    { name: 'completed', payload: completedBatch, anchor: 'transcriptions-approved-strip' },
    // [§5.6] The real end state — every graded test signed. The ONE cell where
    // the celebration is expected to exist.
    { name: 'signed-off', payload: signedOffBatch, anchor: 'completion-hero' },
    // [§6] Thirty papers with four stages live at once — the only size at which
    // the conditional copy is interesting (see `mixedThirtyBatch`).
    { name: 'mixed-30', payload: mixedThirtyBatch, anchor: 'zone-eyes' },
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
            // [§5.1F] EXACTLY ONE CELEBRATION, and this is the cell where the
            // old one used to fire. Every TRANSCRIPTION is approved here —
            // four steps from the end — so the stage collapses to a strip and
            // the green check must NOT appear.
            if (state.name === 'completed') {
                await expect(page.getByTestId('completion-hero')).toHaveCount(0);
                await expect(page.getByTestId('batch-status-chip'))
                    .toHaveText('ממתין לחתימה שלך');
            }
            // …and this is the ONLY cell where it may.
            if (state.name === 'signed-off') {
                await expect(page.getByTestId('batch-status-chip')).toHaveText('הושלם');
                await expect(page.getByTestId('turn-line')).toContainText('סיימת');
            }
            // [§6] Thirty papers, four stages live: the chip picks ONE of them,
            // the turn line names it WITH its nuance, and the download appears
            // for the five signed without claiming the twenty-five that are not.
            if (state.name === 'mixed-30') {
                await expect(page.getByTestId('batch-status-chip'))
                    .toHaveText('ממתין לאישור שלך');
                await expect(page.getByTestId('turn-line'))
                    .toHaveText('תורך: 13 מבחנים לאישור, 3 מבחנים דורשים מבט');
                await expect(page.getByTestId('eyes-row')).toHaveCount(3);
                await expect(page.getByTestId('clean-row')).toHaveCount(10);
                await expect(page.getByTestId('completion-hero')).toHaveCount(0);
                await expect(page.locator('[data-download]')).toHaveCount(1);
            }
            // [§5.3C] The clean panel's expandable row peek is gone with the
            // rows: a clean CARD opens the review route rather than unfolding
            // in place, so there is nothing to expand for a screenshot. The
            // richer cell is now the grid itself, which the anchor already
            // waits for.
            if (state.name === 'steady' && vp.w > 940) {
                await expect(page.getByTestId('clean-row').first()).toBeVisible();
            }
            await page.screenshot({
                path: `e2e/review-artifacts/P2/dashboard-${state.name}-${vp.w}x${vp.h}.png`,
                fullPage: true,
            });
        });
    }
}
