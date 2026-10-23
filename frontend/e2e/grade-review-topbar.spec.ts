import { expect, test } from '@playwright/test';

import { BATCH_ID, TEST_A, installGradeReviewMocks } from './gradeReviewFixtures';

/**
 * The top bar's way OUT — «חזרה לכל המבחנים», a small turquoise link stacked
 * above «הבא». The SSR test proves it is in the markup; only a browser can
 * prove it is ABOVE the button rather than beside or under it, that the two
 * do not touch, and that «הבא» still shares a baseline with «הקודם».
 */

const REVIEW = `/batches/${BATCH_ID}/grade-review/${TEST_A}`;
const ART = 'e2e/review-artifacts/side-by-side';

for (const width of [1440, 1280]) {
    test(`the dashboard link sits above «הבא», apart from it, at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await page.locator('[data-check-id]').first().waitFor();

        const link = page.locator('[data-nav-batch]');
        const next = page.getByRole('button', { name: /^הבא/ });
        const prev = page.getByRole('button', { name: /הקודם$/ });
        await expect(link).toBeVisible();
        await expect(link).toHaveText('חזרה לכל המבחנים');

        const l = (await link.boundingBox())!;
        const n = (await next.boundingBox())!;
        const p = (await prev.boundingBox())!;

        // ABOVE, with clear air between: the link's bottom edge is at least
        // 4px over the button's top edge — never overlapping, never fused.
        expect(n.y - (l.y + l.height)).toBeGreaterThanOrEqual(4);
        // The same column: the two share their horizontal extent.
        expect(Math.abs(l.x - n.x)).toBeLessThanOrEqual(1);
        expect(Math.abs(l.width - n.width)).toBeLessThanOrEqual(1);
        // Small: shorter than the nav button it sits over.
        expect(l.height).toBeLessThan(n.height);
        // «הבא» and «הקודם» still share one baseline.
        expect(Math.abs((n.y + n.height) - (p.y + p.height))).toBeLessThanOrEqual(1);
        // Turquoise: the primary fill, not the card's.
        await expect(link).toHaveCSS('background-color', 'rgb(13, 148, 136)');

        const bar = page.locator('[data-review-topbar]');
        await bar.screenshot({ path: `${ART}/topbar-back-link-${width}.png` });
        // The bar in context, at the top of the page and once scrolled — the
        // sticky strip beneath it is measured from the bar's height (OD-A12).
        await page.screenshot({ path: `${ART}/topbar-in-context-${width}.png` });
        await page.evaluate(() => window.scrollTo(0, 700));
        await page.waitForTimeout(150);
        await page.screenshot({ path: `${ART}/topbar-in-context-scrolled-${width}.png` });
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.waitForTimeout(150);

        await link.click();
        await expect(page).toHaveURL(new RegExp(`/batches/${BATCH_ID}$`));
    });
}
