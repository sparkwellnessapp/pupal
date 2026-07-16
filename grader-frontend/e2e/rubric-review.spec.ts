import { test, expect, type Page } from '@playwright/test';
import { seedAuth, installMocks, type MockOptions } from './fixtures';

/**
 * PR-4 Phase 6 — the two journeys where "curl passed, browser died" actually
 * happened (census G12). Both drive the REAL wizard (upload → extract → review)
 * with the whole API route-mocked, so they exercise the render half deterministically.
 */

async function driveToReview(page: Page, opts: MockOptions): Promise<void> {
    await seedAuth(page);
    await installMocks(page, opts);
    await page.goto('/');

    await page.getByRole('button', { name: 'העלאת מחוון חדש' }).click();
    await page.locator('input[type="file"]').setInputFiles({
        name: 'rubric.docx',
        mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        buffer: Buffer.from('PK dummy docx — content is irrelevant, extraction is mocked'),
    });
    // Purpose step → skip → extracting → (mocked poll) → review.
    await page.getByRole('button', { name: /דלג/ }).click();
    await expect(page.getByText('סיכום מחוון')).toBeVisible({ timeout: 30_000 });
}

test.describe('rubric wizard — the render half (PR-4 Phase 6)', () => {
    test('bagrut: depth-2 renders, no white-screen, the q1.א.2 mismatch is caught client-side', async ({ page }) => {
        const crashes: string[] = [];
        page.on('pageerror', (e) => crashes.push(String(e)));

        await driveToReview(page, { fixture: 'bagrut_899371' });

        // Depth-2 nodes render at their FULL dotted paths — a depth-1 renderer could
        // never emit these. This is the exact screen that used to white-screen with
        // "e.toFixed is not a function" the moment a real discrepancy existed.
        await expect(page.locator('[data-scope-id="q1.א.2"]')).toBeVisible();
        await expect(page.locator('[data-scope-id="q1.ב.1"]')).toBeVisible();

        // The recursive client validator caught the leaf mismatch (criteria 2 vs
        // declared 3), so Save is blocked — the teacher can see and fix the exact node.
        await expect(page.getByRole('button', { name: 'שמור מחוון' })).toHaveAttribute('aria-disabled', 'true');

        expect(crashes, `uncaught page errors: ${crashes.join('\n')}`).toHaveLength(0);
    });

    test('employee: header shows achievable 50 (not offered 100); structured 400 then clean save', async ({ page }) => {
        await driveToReview(page, {
            fixture: 'employee_course_select1',
            save: 'reject-then-ok',
            rejectLocation: 'q2.א',
        });

        // Selection parity: the summary shows the ACHIEVABLE total (50), never the
        // offered sum (100) — the census's "two-disagreeing-totals" bug is gone.
        await expect(page.getByText(/\d+ שאלות\s*·\s*50 נקודות\s*·\s*\d+ קריטריונים/)).toBeVisible();
        await expect(page.getByText('100 נקודות')).toHaveCount(0);

        // No client errors → Save is enabled.
        const save = page.getByRole('button', { name: 'שמור מחוון' });
        await expect(save).toHaveAttribute('aria-disabled', 'false');

        // First save → mocked structured 400. PR-3's payload finally reaches the
        // teacher's eyes: the named invariant chip + a working jump-to-node.
        await save.click();
        await expect(page.getByText('INV-2')).toBeVisible();
        await expect(page.getByRole('button', { name: /מעבר לרכיב/ })).toBeVisible();

        // Second save → 201. The rubric is saved.
        await save.click();
        await expect(page.getByText('המחוון נשמר בהצלחה!')).toBeVisible({ timeout: 15_000 });
    });
});
