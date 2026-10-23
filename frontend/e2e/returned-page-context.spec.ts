import { expect, test } from '@playwright/test';

import { BATCH_ID, STUDENT_DAN, TEST_A, installGradeReviewMocks } from './gradeReviewFixtures';

/**
 * The returned page's RETURN CONTEXT and its OD-14 wording
 * (PR_student_profile.md §6.5, §6.6, §8.3 items 4 and 6).
 *
 * `?student=` decides only where «back» goes; `batch` keeps its two jobs, so
 * «עריכת הבדיקה» and «הורדת PDF» are unchanged beside it. The dashboard's
 * card name is the fourth entry point (OD-2).
 */

const ART = 'e2e/review-artifacts/student-profile';
const PROFILE = `/my-classroom/students/${STUDENT_DAN}`;

test.use({ viewport: { width: 1440, height: 900 } });

test('from the profile: back goes to the student, the name links to the profile, the line reads «בדיקה אושרה ב»', async ({ page }) => {
    await installGradeReviewMocks(page, { approved: true });
    await page.goto(`/graded-tests/${TEST_A}/returned?batch=${BATCH_ID}&student=${STUDENT_DAN}`);
    await expect(page.locator('[data-page-view="scan"] img')).toBeVisible();

    const back = page.locator('[data-back-link]');
    await expect(back).toHaveAttribute('href', PROFILE);
    await expect(back).toHaveText(/חזרה אל דן בסיוק/);
    await expect(page.locator('h1 [data-student-link]')).toHaveAttribute('href', PROFILE);
    await expect(page.locator('h1')).toContainText('המבחן החתום · דן בסיוק');

    // OD-14 / §6.6 — the approval moment, not «נחתם».
    const meta = page.locator('h1 + div');
    await expect(meta).toContainText('בדיקה אושרה ב');
    await expect(meta).not.toContainText('נחתם');

    // The batch's two jobs survive the student context (FA-9).
    await expect(page.locator('[data-edit-review]')).toBeVisible();
    await expect(page.locator('[data-download-pdf]')).toBeVisible();

    await page.screenshot({ path: `${ART}/returned-from-profile-1440.png` });

    await back.click();
    await expect(page).toHaveURL(new RegExp(`${PROFILE}$`));
});

test('from the dashboard: back goes to the batch; with no context, to המבחנים שלי', async ({ page }) => {
    await installGradeReviewMocks(page, { approved: true });
    await page.goto(`/graded-tests/${TEST_A}/returned?batch=${BATCH_ID}`);
    await expect(page.locator('[data-page-view="scan"] img')).toBeVisible();
    await expect(page.locator('[data-back-link]')).toHaveAttribute('href', `/batches/${BATCH_ID}`);
    await expect(page.locator('[data-back-link]')).toHaveText(/חזרה ללוח המקבץ/);

    await page.goto(`/graded-tests/${TEST_A}/returned`);
    await expect(page.locator('[data-back-link]')).toHaveAttribute('href', '/batches');
    await expect(page.locator('[data-back-link]')).toHaveText(/המבחנים שלי/);
});

test('a malformed student parameter is ignored, never followed', async ({ page }) => {
    await installGradeReviewMocks(page, { approved: true });
    await page.goto(`/graded-tests/${TEST_A}/returned?batch=${BATCH_ID}&student=..%2Fadmin`);
    await expect(page.locator('[data-page-view="scan"] img')).toBeVisible();
    await expect(page.locator('[data-back-link]')).toHaveAttribute('href', `/batches/${BATCH_ID}`);
});

test('the dashboard card name is a real link to the profile, outside the card button (UI-5)', async ({ page }) => {
    await installGradeReviewMocks(page);
    await page.goto(`/batches/${BATCH_ID}`);
    await page.locator('[data-pile-card]').first().waitFor();

    // Structure first: a real <a>, never inside the card's button, and no
    // button anywhere contains an interactive descendant.
    const names = page.locator('[data-pile-card] a[data-card-student]');
    expect(await names.count()).toBeGreaterThan(0);
    expect(await page.locator('[data-pile-card] button a, [data-pile-card] button [role="link"], '
        + '[data-pile-card] button button').count()).toBe(0);
    await expect(names.first()).toHaveAttribute('href', `/my-classroom/students/${STUDENT_DAN}`);

    await names.first().click();
    await expect(page).toHaveURL(new RegExp(`/my-classroom/students/${STUDENT_DAN}$`));
});

test('the name link stays live on a card whose own action is disabled', async ({ page }) => {
    await installGradeReviewMocks(page);
    await page.goto(`/batches/${BATCH_ID}`);
    await page.locator('[data-pile-card]').first().waitFor();

    const inert = page.locator('[data-pile-card]:has(button[data-card-action][disabled])').first();
    await expect(inert).toBeVisible();
    await inert.locator('a[data-card-student]').click();
    await expect(page).toHaveURL(new RegExp(`/my-classroom/students/${STUDENT_DAN}$`));
});

test('the card\'s primary action is unchanged for keyboard and screen readers', async ({ page }) => {
    await installGradeReviewMocks(page);
    await page.goto(`/batches/${BATCH_ID}`);
    const card = page.locator('[data-pile-card][data-card-state="landed_marked"]').first();
    await card.waitFor();

    // Screen reader: still ONE button per card, named by the student and the
    // card's state — the name link is announced separately, as a link.
    const action = card.locator('button[data-card-action]');
    await expect(action).toHaveCount(1);
    await expect(action).toHaveAccessibleName(/דין עזרא — /);
    await expect(card.getByRole('link', { name: 'דין עזרא' })).toHaveCount(1);

    // Keyboard: the button comes BEFORE the name in the tab order, and Enter
    // on it opens the review exactly as it did.
    await action.focus();
    await page.keyboard.press('Tab');
    await expect(card.locator('a[data-card-student]')).toBeFocused();
    await action.focus();
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/\/grade-review\//);
});

test('a click anywhere on the card outside the name still opens the card', async ({ page }) => {
    await installGradeReviewMocks(page);
    await page.goto(`/batches/${BATCH_ID}`);
    const card = page.locator('[data-pile-card][data-card-state="landed_marked"]').first();
    await card.waitFor();
    // The caption line sits under the stretched layer, not inside the button:
    // a click there is the card's, exactly as before the restructure.
    // The pile sits low on a 900px page; a raw mouse click does not scroll.
    await card.scrollIntoViewIfNeeded();
    const caption = card.locator('button[data-card-action] + div + div');
    const box = (await caption.boundingBox())!;
    // What is actually under the pointer is the card's own button (its ::after),
    // not the caption text — asserted, so the click below cannot pass by luck.
    const hit = await page.evaluate(([x, y]) =>
        document.elementFromPoint(x, y)?.hasAttribute('data-card-action') ?? false,
        [box.x + 4, box.y + box.height / 2]);
    expect(hit).toBe(true);
    await page.mouse.click(box.x + 4, box.y + box.height / 2);
    await expect(page).toHaveURL(/\/grade-review\//);
});

test('the review module offers no link to the profile (OD-2)', async ({ page }) => {
    await installGradeReviewMocks(page);
    await page.goto(`/batches/${BATCH_ID}/grade-review/${TEST_A}`);
    await page.locator('[data-check-id]').first().waitFor();
    await expect(page.locator('[data-review-topbar] a[href*="/my-classroom/students/"]')).toHaveCount(0);
    await expect(page.locator('main a[href*="/my-classroom/students/"]')).toHaveCount(0);
});
