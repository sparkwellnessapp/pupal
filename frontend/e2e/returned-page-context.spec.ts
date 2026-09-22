import { expect, test } from '@playwright/test';

import { BATCH_ID, FIXTURE_STUDENT_ID, TEST_A, installGradeReviewMocks } from './gradeReviewFixtures';

/**
 * The returned page's RETURN CONTEXT and its OD-14 wording
 * (PR_student_profile.md §6.5, §6.6, §8.3 items 4 and 6).
 *
 * `?student=` decides only where «back» goes; `batch` keeps its two jobs, so
 * «עריכת הבדיקה» and «הורדת PDF» are unchanged beside it. The dashboard's
 * card name is the fourth entry point (OD-2).
 */

const PROFILE = `/my-classroom/students/${FIXTURE_STUDENT_ID}`;

test.use({ viewport: { width: 1440, height: 900 } });

test('from the profile: back goes to the student, the name links to the profile, the line reads «בדיקה אושרה ב»', async ({ page }) => {
    await installGradeReviewMocks(page, { approved: true });
    await page.goto(`/graded-tests/${TEST_A}/returned?batch=${BATCH_ID}&student=${FIXTURE_STUDENT_ID}`);
    await expect(page.locator('[data-page-view="scan"] img')).toBeVisible();

    // The name is read off the page rather than written here: the shared
    // grade-review fixtures carry a real student's name, and a literal in
    // this file would publish it once more.
    const nameLink = page.locator('h1 [data-student-link]');
    await expect(nameLink).toHaveAttribute('href', PROFILE);
    const name = (await nameLink.innerText()).trim();
    expect(name.length).toBeGreaterThan(0);
    const back = page.locator('[data-back-link]');
    await expect(back).toHaveAttribute('href', PROFILE);
    await expect(back).toHaveText(new RegExp(`חזרה אל ${name}`));
    await expect(page.locator('h1')).toContainText(`המבחן החתום · ${name}`);

    // OD-14 / §6.6 — the approval moment, not «נחתם».
    const meta = page.locator('h1 + div');
    await expect(meta).toContainText('בדיקה אושרה ב');
    await expect(meta).not.toContainText('נחתם');

    // The batch's two jobs survive the student context (FA-9).
    await expect(page.locator('[data-edit-review]')).toBeVisible();
    await expect(page.locator('[data-download-pdf]')).toBeVisible();

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

test('the dashboard card name opens the profile; the review panel offers no link', async ({ page }) => {
    await installGradeReviewMocks(page);
    await page.goto(`/batches/${BATCH_ID}`);
    await page.locator('[data-pile-card]').first().waitFor();

    // Any card whose own button is live: the name inside it is the link. (A
    // pending/grading card's button is disabled and swallows the click — the
    // same as its retry/preview controls; OD-2 asks for the name, not a
    // guarantee on cards that are not hers to open yet.)
    const name = page.locator('[data-pile-card] button:not([disabled]) [data-card-student]').first();
    await expect(name).toBeVisible();
    await name.click();
    await expect(page).toHaveURL(new RegExp(`/my-classroom/students/${FIXTURE_STUDENT_ID}$`));
});

test('the review module offers no link to the profile (OD-2)', async ({ page }) => {
    await installGradeReviewMocks(page);
    await page.goto(`/batches/${BATCH_ID}/grade-review/${TEST_A}`);
    await page.locator('[data-check-id]').first().waitFor();
    await expect(page.locator('[data-review-topbar] a[href*="/my-classroom/students/"]')).toHaveCount(0);
    await expect(page.locator('main a[href*="/my-classroom/students/"]')).toHaveCount(0);
});
