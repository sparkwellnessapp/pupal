import { expect, test } from '@playwright/test';

import { BATCH_ID, TEST_A, installGradeReviewMocks } from './gradeReviewFixtures';

/**
 * STEP 1 — the entry point.
 *
 * The S12 review module existed for a whole phase with NOTHING linking to it:
 * the dashboard's `פתח` swapped in the OLD panel in place, so the owner drove
 * the surface being replaced while believing it was the new one. Every test in
 * `grade-review.spec.ts` was green throughout, because they all navigate
 * straight to the route.
 *
 * This is the test that could have caught that: it starts where a teacher
 * starts and clicks what a teacher clicks. It is a REACHABILITY guard, and it
 * is deliberately separate from the module's own suite so it cannot be
 * satisfied by the module's own navigation.
 *
 * The DOOR has changed once already — F1 replaced the `פתח` row list with the
 * Pile — and this guard followed it, because what it protects is the PATH, not
 * the widget. If the next redesign moves the door again, update the click here;
 * do not delete the test.
 */

test('a pile card opens the review module, not the old panel', async ({ page }) => {
    await installGradeReviewMocks(page);
    await page.goto(`/batches/${BATCH_ID}`);

    const card = page
        .locator('[data-pile-card][data-card-state="landed_marked"] button')
        .first();
    await expect(card).toBeVisible();
    await card.click();

    // 1. It NAVIGATED — the module's cursor and prev/next live in the segment
    //    layout, which only exists on a real route change.
    await expect(page).toHaveURL(new RegExp(`/batches/${BATCH_ID}/grade-review/`));

    // 2. It is the NEW surface: verdict controls and the live total.
    await expect(page.locator('[data-total]')).toBeVisible();
    await expect(page.locator('[data-check-id] [data-verdict]').first()).toBeVisible();

    // 3. And demonstrably NOT the old panel, whose signature is a numeric
    //    points input per terminal — the thing the new module refuses to have.
    await expect(page.locator('input[type="number"]')).toHaveCount(0);
    // getByPlaceholder, not getByText: that string is the old panel's INPUT
    // PLACEHOLDER, so a text query could never have matched it and half this
    // guard was passing vacuously.
    await expect(page.getByPlaceholder('הוסף הערה (אופציונלי)')).toHaveCount(0);
});

test('the review module lands on the very test whose card was clicked', async ({ page }) => {
    await installGradeReviewMocks(page);
    await page.goto(`/batches/${BATCH_ID}`);

    // דין עזרא is the marked card in the running fixture; clicking it must open
    // HER test, not simply "a" test.
    const card = page.locator('[data-pile-card]', { hasText: 'דין עזרא' });
    const id = await card.getAttribute('data-pile-card');
    await card.locator('button').first().click();

    await expect(page).toHaveURL(new RegExp(String(id)));
    await expect(page.getByText('דין עזרא').first()).toBeVisible();
});
