import { test, expect, type Page } from '@playwright/test';
import { seedAuth, installMocks } from './fixtures';

/**
 * Example solutions on the rubric mirror are display-rich / edit-raw (the D8 rule
 * question prose follows): click the rendered solution to edit the stored string;
 * a scope with none offers «+ הוסיפי פתרון לדוגמה» on hover/focus. Driven on
 * foundations_cs, where q3.ב has a solution and q3.א has none.
 */

async function driveToReview(page: Page): Promise<void> {
    await seedAuth(page);
    await installMocks(page, { fixture: 'foundations_cs' });
    await page.goto('/');
    await page.getByRole('button', { name: 'העלאת מחוון חדש' }).click();
    await page.locator('input[type="file"]').setInputFiles({
        name: 'rubric.docx',
        mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        buffer: Buffer.from('PK dummy docx — content is irrelevant, extraction is mocked'),
    });
    await expect(page.getByText('סיימתי לקרוא את המחוון')).toBeVisible({ timeout: 30_000 });
    await page.getByRole('button', { name: 'עברי על המחוון' }).click();
    await expect(page.locator('[data-scope-id="q3.ב"]')).toBeVisible({ timeout: 30_000 });
}

test('she edits an extracted example solution in place', async ({ page }) => {
    await driveToReview(page);
    const scope = page.locator('section[data-scope-id="q3.ב"]');

    await scope.getByRole('button', { name: 'פתרון לדוגמה', exact: true }).click();
    await scope.locator('[aria-label^="פתרון לדוגמה — "][aria-label$="לחצי לעריכה"]').click();
    const box = scope.locator('textarea');
    await expect(box).toBeVisible();
    await box.fill('SOLUTION_EDITED_42');
    await page.keyboard.press('Tab');

    await expect(scope.locator('textarea')).toHaveCount(0);
    await expect(scope.getByText('SOLUTION_EDITED_42')).toBeVisible();
});

test('she adds an example solution where none was extracted', async ({ page }) => {
    await driveToReview(page);
    const scope = page.locator('section[data-scope-id="q3.א"]');
    await expect(scope.getByRole('button', { name: 'פתרון לדוגמה', exact: true })).toHaveCount(0);

    await scope.hover();
    const add = scope.getByRole('button', { name: /^\+ הוסיפי פתרון לדוגמה — / });
    await expect(add).toBeVisible();
    await add.click();
    const box = scope.locator('textarea');
    await expect(box).toBeFocused();
    await box.fill('NEW_SOLUTION_7');
    await page.keyboard.press('Tab');

    // It opens expanded, so what she just wrote does not vanish behind a closed disclosure.
    await expect(scope.getByRole('button', { name: 'פתרון לדוגמה', exact: true })).toBeVisible();
    await expect(scope.getByText('NEW_SOLUTION_7')).toBeVisible();
});
