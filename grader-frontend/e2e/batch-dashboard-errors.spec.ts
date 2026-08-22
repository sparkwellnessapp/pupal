import { expect, test } from '@playwright/test';
import { seedAuth } from './fixtures';
import { AUTH_ME, fulfillJson, SEED_BATCH_ID, seedFailure, steadyBatch } from './seedBatch';

/**
 * P0 — F1 (dashboard error lifecycle) + F2 (retry 409 Hebrew detail) + F3
 * (no raw Latin status enum).
 *
 * F1: one transient poll failure must NEVER replace the dashboard — it is a
 * dismissible banner over live content, auto-cleared by the next good poll
 * (census Q4's sticky-error page-death, closed).
 * F2: the retry 409's server Hebrew detail reaches the teacher verbatim.
 * F3: the header renders the C1 status label, never `in_progress`.
 */

const RETRY_409_DETAIL = 'המשימה עדיין פעילה או שכבר הושלמה';

test('transient poll failure shows a banner over live content, then clears', async ({ page }) => {
    await seedAuth(page);

    let batchCalls = 0;
    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        if (url.includes('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);

        if (url.includes(`/api/v0/batches/${SEED_BATCH_ID}`)) {
            batchCalls += 1;
            // Entry pair (StrictMode) → good. Call 3 (first poll tick) → 500.
            // Call 4+ → good again.
            if (batchCalls === 3) {
                return fulfillJson(route, { detail: 'תקלה זמנית בשרת' }, 500);
            }
            return fulfillJson(route, steadyBatch());
        }
        return fulfillJson(route, {});
    });

    await page.goto(`/batches/${SEED_BATCH_ID}`);

    // Loaded state + F3: the C1 label renders (as the D1 status chip); the
    // raw enum never does. (P2 moved the label from the meta line into the
    // chip — assertion follows the redesigned header.)
    await expect(page.getByText('מקבץ בדיקה')).toBeVisible();
    await expect(page.getByTestId('batch-status-chip')).toHaveText('בתמלול');
    await expect(page.getByText(/in_progress/)).toHaveCount(0);

    // The failed poll (≈3s in) surfaces as a banner — content stays alive.
    const banner = page.getByTestId('batch-poll-error-banner');
    await expect(banner).toBeVisible();
    await expect(banner).toContainText('תקלה זמנית בשרת');
    await expect(page.getByText('מקבץ בדיקה')).toBeVisible();      // no page-death
    await page.screenshot({
        path: 'e2e/review-artifacts/F1/transient-poll-banner.png',
        fullPage: true,
    });

    // The next good poll clears it (F1: success resets the error).
    await expect(banner).toBeHidden();
    await expect(page.getByText('מקבץ בדיקה')).toBeVisible();
});

test('retry 409 surfaces the server Hebrew detail, not an English fallback', async ({ page }) => {
    await seedAuth(page);

    const failure = seedFailure();
    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        const method = route.request().method();
        if (url.includes('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);

        if (method === 'POST' && url.includes('/jobs/') && url.includes('/retry')) {
            return fulfillJson(route, { detail: RETRY_409_DETAIL }, 409);
        }
        if (url.includes(`/api/v0/batches/${SEED_BATCH_ID}`)) {
            return fulfillJson(route, steadyBatch());
        }
        return fulfillJson(route, {});
    });

    await page.goto(`/batches/${SEED_BATCH_ID}`);
    await expect(page.getByText(`התמלול של ${failure.filename} נכשל`)).toBeVisible();

    await page.getByTestId('retry-job-button').click();

    const banner = page.getByTestId('batch-poll-error-banner');
    await expect(banner).toBeVisible();
    await expect(banner).toContainText(RETRY_409_DETAIL);           // the server's words
    await expect(banner).not.toContainText('Failed to retry job');  // never the old English
    await expect(page.getByText('מקבץ בדיקה')).toBeVisible();      // still no page-death
    await page.screenshot({
        path: 'e2e/review-artifacts/F2/retry-409-hebrew-detail.png',
        fullPage: true,
    });
});
