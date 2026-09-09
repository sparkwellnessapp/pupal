import { expect, test } from '@playwright/test';

import { BATCH_ID, TEST_A, installGradeReviewMocks } from './gradeReviewFixtures';

/**
 * The F2 VISUAL GATE.
 *
 * Viewport-sized captures at the mockup's own width, plus a clipped capture of
 * one scope — the unit the teacher actually reads. A full-page shot of this
 * surface is ~10 000px tall and is unreviewable once it is scaled to fit, which
 * is the same as having no visual gate at all.
 *
 * The mockup is captured through the SAME browser at the SAME viewport, so the
 * comparison is like for like rather than a screenshot against a memory.
 */

const ART = 'e2e/review-artifacts/F2';
const REVIEW = `/batches/${BATCH_ID}/grade-review/${TEST_A}`;
const MOCKUP = `file://${process.cwd().replace(/\\/g, '/')}/../vivi-grade-review-mockup-v2.html`;

test.use({ viewport: { width: 1440, height: 900 } });

test('viewport captures for visual review', async ({ page }) => {
    await installGradeReviewMocks(page);
    await page.goto(REVIEW);
    await page.locator('[data-check-id]').first().waitFor();
    await page.waitForTimeout(400);

    await page.screenshot({ path: `${ART}/vp-top.png` });

    const scope = page.locator('[data-scope-id]').first();
    await scope.screenshot({ path: `${ART}/vp-scope.png` });

    // With an override in place: the red ink grammar, end to end.
    await page.locator('[data-check-id] [data-verdict]').first().click();
    await page.mouse.move(0, 0);
    await page.waitForTimeout(200);
    await page.screenshot({ path: `${ART}/vp-overridden.png` });
    await scope.screenshot({ path: `${ART}/vp-scope-overridden.png` });
});

/** The path a teacher actually takes: dashboard → a pile card → the module. */
test('entry path capture', async ({ page }) => {
    await installGradeReviewMocks(page);
    await page.goto(`/batches/${BATCH_ID}`);
    await page.locator('[data-pile-card]').first().waitFor();
    await page.waitForTimeout(400);
    await page.screenshot({ path: `${ART}/entry-dashboard.png` });

    await page.locator('[data-pile-card][data-card-state="landed_marked"] button')
        .first().click();
    await expect(page.locator('[data-total]')).toBeVisible();
    await page.waitForTimeout(400);
    await page.screenshot({ path: `${ART}/entry-opened.png` });
});

test('mockup viewport capture', async ({ page }) => {
    await page.goto(MOCKUP);
    await page.locator('.tabs button[data-v="v-review"]').click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${ART}/vp-mockup-top.png` });
    await page.locator('#s-q1a').screenshot({ path: `${ART}/vp-mockup-scope.png` });
});
