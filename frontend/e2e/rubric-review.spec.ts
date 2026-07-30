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


/**
 * /design-lab is SERVER-rendered, so its markup exists long before React attaches.
 * Clicking in that window silently does nothing — the source of a real flake.
 * The rail auto-expands the ACTIVE question, which is impossible server-side
 * (activeId is null in SSR), so that row appearing is a precise "React is live"
 * signal. Every lab-driven test goes through here.
 */
async function gotoLab(page: Page, state = 'at-rest'): Promise<void> {
    await page.goto(`/design-lab?fixture=bagrut_899371&state=${state}`);
    await expect(page.locator('nav[aria-label="מפת המחוון"] [data-rail-link="q1.א"]'))
        .toBeVisible({ timeout: 20_000 });
}

/**
 * Design Recovery Round 2 — D9 (rail landing) and the D5/D8 edit surfaces, driven
 * against /design-lab so the assertions are LAYOUT assertions, not markup ones.
 * vitest runs node-env (no layout), so "did it land in the top region" can only be
 * answered by a real browser — this is that answer.
 */
test.describe('Round 2 — rail landing + edit surfaces (design-lab)', () => {
    for (const vp of [{ w: 1440, h: 900 }, { w: 1280, h: 800 }]) {
        test(`D9: a rail click lands the question TITLE in the top region @${vp.w}`, async ({ page }) => {
            await page.setViewportSize({ width: vp.w, height: vp.h });
            await gotoLab(page);

            const rail = page.getByRole('navigation', { name: 'מפת המחוון' });
            // target the JUMP control specifically — a parent row also has a chevron
            await rail.locator('[data-rail-link="q4"]').click();
            await page.waitForTimeout(1200); // smooth scroll settle

            // The TITLE itself must be visible near the top — not the sub-question
            // body, and not scrolled under the ~80px sticky app header.
            const heading = page.locator('[data-scope-id="q4"] h3').first();
            await expect(heading).toBeInViewport();
            const box = await heading.boundingBox();
            expect(box).not.toBeNull();
            expect(box!.y).toBeGreaterThanOrEqual(0);
            expect(box!.y).toBeLessThan(220);
        });
    }

    test('D5: a SUB-QUESTION points chip opens an input (points editable at every node)', async ({ page }) => {
        await gotoLab(page);
        const chip = page.getByRole('button', { name: /^ניקוד סעיף/ }).first();
        await expect(chip).toBeVisible();
        await chip.click();
        await expect(page.locator('input[type="number"]').first()).toBeVisible();
    });

    test('D8: clicking prose opens a RAW textarea (display-rich / edit-raw)', async ({ page }) => {
        await gotoLab(page);
        // At rest the markers are rendered away…
        await expect(page.getByText('[TABLE', { exact: false })).toHaveCount(0);
        const prose = page.getByRole('button', { name: /^טקסט שאלה/ }).first();
        await prose.click();
        // …and on edit intent she gets the SOURCE back, markers and all.
        const box = page.locator('textarea').first();
        await expect(box).toBeVisible();
        expect(await box.inputValue()).toContain('[TABLE');
    });
});

/**
 * The outline rail as a MAP: nested to full depth, points on every row, branches
 * collapsible, and every row a jump target. Expansion is an auto rule (the question
 * you are reading opens) that an explicit chevron click overrides for good.
 */
test.describe('Outline rail — nesting, points, collapse, navigation', () => {
    const NAV = 'nav[aria-label="מפת המחוון"]';

    test('the ACTIVE question auto-expands; the others start collapsed', async ({ page }) => {
        await gotoLab(page);
        const rail = page.locator(NAV);
        await expect(rail).toBeVisible();

        // q1 is what she is looking at, so its branch opens itself…
        await expect(rail.locator('button[aria-label="כווצי שאלה 1"]')).toBeVisible();
        const sub = rail.locator('[data-rail-link="q1.א"]');
        await expect(sub).toBeVisible();
        await expect(sub).toContainText('סעיף א');
        await expect(sub).toContainText('15');              // its OWN points

        // …and every other branch stays shut, so the map stays short.
        await expect(rail.locator('[data-rail-link="q3.א"]')).toHaveCount(0);
        await expect(rail.locator('button[aria-label="הרחיבי שאלה 3"]')).toBeVisible();
    });

    test('a chevron expands a collapsed branch, with each row carrying its points', async ({ page }) => {
        await gotoLab(page);
        const rail = page.locator(NAV);
        await rail.locator('button[aria-label="הרחיבי שאלה 3"]').click();

        const sub = rail.locator('[data-rail-link="q3.א"]');
        await expect(sub).toBeVisible();
        await expect(sub).toContainText('סעיף א');
        await expect(sub).toContainText('10');
        await expect(rail.locator('[data-rail-link="q3.ב"]')).toContainText('15');
    });

    test('nesting goes ALL the way down (תת-סעיף), and each level collapses', async ({ page }) => {
        await gotoLab(page);
        const rail = page.locator(NAV);
        await rail.locator('button[aria-label="הרחיבי סעיף א"]').click();   // q1 is already open

        const inner = rail.locator('[data-rail-link="q1.א.1"]');
        await expect(inner).toBeVisible();
        await expect(inner).toContainText('תת-סעיף 1');
        await expect(inner).toContainText('12');

        // collapsing removes the whole subtree, but keeps the parent row
        await rail.locator('button[aria-label="כווצי סעיף א"]').click();
        await expect(rail.locator('[data-rail-link="q1.א.1"]')).toHaveCount(0);
        await expect(rail.locator('[data-rail-link="q1.א"]')).toBeVisible();
    });

    test('clicking a SUB-QUESTION row navigates to it, exactly like a question', async ({ page }) => {
        await gotoLab(page);
        const rail = page.locator(NAV);
        await rail.locator('button[aria-label="הרחיבי שאלה 3"]').click();
        await rail.locator('[data-rail-link="q3.ב"]').click();
        await page.waitForTimeout(1200);

        const heading = page.locator('[data-scope-id="q3.ב"] h4').first();
        await expect(heading).toBeInViewport();
        const box = await heading.boundingBox();
        expect(box!.y).toBeGreaterThanOrEqual(0);
        expect(box!.y).toBeLessThan(260);
    });

    test('an explicit collapse WINS over the auto rule (her choice is not undone)', async ({ page }) => {
        await gotoLab(page);
        const rail = page.locator(NAV);
        // q1 auto-opened; close it by hand
        await expect(rail.locator('[data-rail-link="q1.א"]')).toBeVisible();
        await rail.locator('button[aria-label="כווצי שאלה 1"]').click();
        await expect(rail.locator('[data-rail-link="q1.א"]')).toHaveCount(0);

        // scroll q1 back into view — the auto rule would reopen it; it must not
        await page.locator('[data-scope-id="q2"]').scrollIntoViewIfNeeded();
        await page.waitForTimeout(500);
        await page.locator('[data-scope-id="q1"]').scrollIntoViewIfNeeded();
        await page.waitForTimeout(700);
        await expect(rail.locator('[data-rail-link="q1.א"]')).toHaveCount(0);
    });
});
