import { test, expect, type Page } from '@playwright/test';
import { seedAuth, installMocks, type MockOptions } from './fixtures';

/**
 * PR-4 Phase 6 / PR-5 S2 — the two journeys where "curl passed, browser died"
 * happened (census G12), MIGRATED to the DOCUMENT MIRROR (RubricDocument). Both
 * drive the real wizard (upload → extract → arrival → review) with the API
 * route-mocked, exercising the render half deterministically. These remain the
 * render-half guard.
 */

async function driveToReview(page: Page, opts: MockOptions): Promise<void> {
    await seedAuth(page);
    await installMocks(page, opts);
    await page.goto('/');

    await page.getByRole('button', { name: 'העלאת מחוון חדש' }).click();
    await page.locator('input[type="file"]').setInputFiles({
        name: 'rubric.docx',
        mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        buffer: Buffer.from('PK dummy docx — content is irrelevant, extraction is mocked'),
    });
    // extracting → arrival summary card → the mirror. The mirror renders the
    // document itself (question headings), superseding the old "סיכום מחוון" card.
    await expect(page.getByText('סיימתי לקרוא את המחוון')).toBeVisible({ timeout: 30_000 });
    await page.getByRole('button', { name: 'עברי על המחוון' }).click();
    await expect(page.getByRole('heading', { name: /שאלה 1/ })).toBeVisible({ timeout: 30_000 });
}

test.describe('rubric mirror — the render half (PR-5 S2)', () => {
    test('bagrut: the mirror renders the document shape (depth-2), finding anchored at q1.א.2, save blocked', async ({ page }) => {
        const crashes: string[] = [];
        page.on('pageerror', (e) => crashes.push(String(e)));

        await driveToReview(page, { fixture: 'bagrut_899371' });

        // Document shape: nested identity headings render, and depth-2 nodes carry
        // their FULL dotted data-scope-id — the exact screen that used to white-screen
        // with "e.toFixed is not a function" the moment a real discrepancy existed.
        await expect(page.locator('[data-scope-id="q1.א.2"]')).toBeVisible();
        await expect(page.locator('[data-scope-id="q1.ב.1"]')).toBeVisible();

        // The recursive client validator caught the leaf mismatch → the finding is
        // surfaced in the relocated top summary (with a naming-law jump label, not a
        // raw id) and Save is blocked at the exact node.
        await expect(page.getByText('יש לתקן לפני שמירה')).toBeVisible();
        await expect(page.getByRole('button', { name: /שאלה 1 · סעיף/ })).toBeVisible();
        await expect(page.getByRole('button', { name: 'שמור מחוון' })).toHaveAttribute('aria-disabled', 'true');

        expect(crashes, `uncaught page errors: ${crashes.join('\n')}`).toHaveLength(0);
    });

    test('employee: selection header (achievable 50, not offered 100); structured 400 then clean save', async ({ page }) => {
        await driveToReview(page, {
            fixture: 'employee_course_select1',
            save: 'reject-then-ok',
            rejectLocation: 'q2.א',
        });

        // §5: the header states the selection structure in words and shows the
        // ACHIEVABLE total (50), never the offered sum (100).
        await expect(page.getByText(/מבחן בחירה/)).toBeVisible();
        await expect(page.getByTestId('rubric-achievable-total')).toContainText('50');
        await expect(page.getByText('100 נקודות')).toHaveCount(0);

        // No client errors → Save is enabled.
        const save = page.getByRole('button', { name: 'שמור מחוון' });
        await expect(save).toHaveAttribute('aria-disabled', 'false');

        // First save → mocked structured 400 (RubricSaveFlow): the named invariant chip
        // + a working jump whose label speaks the naming law, never the raw id.
        await save.click();
        await expect(page.getByText('INV-2')).toBeVisible();
        await expect(page.getByRole('button', { name: /מעבר ל/ })).toBeVisible();

        // Second save → 201. The completion card shows her rubric's NAME; the UUID is dead.
        await save.click();
        await expect(page.getByText('מכאן ויוי בודקת לפיו')).toBeVisible({ timeout: 15_000 });
        await expect(page.getByText('employee_course_select1')).toBeVisible();
        await expect(page.getByText('rub-e2e')).toHaveCount(0);

        // Carry-through: the CTA lands her on upload-tests with THIS rubric selected.
        await page.getByRole('button', { name: 'המשיכי לבדיקת מבחנים' }).click();
        await expect(page.getByText('העלאת מבחנים')).toBeVisible();
        await expect(page.getByRole('heading', { name: 'employee_course_select1' })).toBeVisible();
    });

    test('mirror is editable: a criterion points cell opens an input and commits (E-3 cascade)', async ({ page }) => {
        // Editing in the criteria table routes through the same ops as the old editor
        // (ops-parity is unit-proven byte-identical). Here we only prove the surface is
        // live: clicking a points chip opens the number input in place.
        await driveToReview(page, { fixture: 'bagrut_899371' });
        const chip = page.getByRole('button', { name: /ניקוד קריטריון/ }).first();
        await expect(chip).toBeVisible();
        await chip.click();
        await expect(page.locator('input[type="number"]').first()).toBeVisible();
    });
});
