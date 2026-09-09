import { expect, test } from '@playwright/test';

import { BATCH_ID, TEST_A, installGradeReviewMocks } from './gradeReviewFixtures';

/**
 * F3 — המבחן המוחזר, driven in a real browser.
 *
 * The two journeys the spec names by hand are here:
 * `preview-drag-stamp-apply-to-batch` and `appendix-toggle-with-info`, plus the
 * reachability guard that every phase now carries — F2 was built unreachable
 * once and nobody noticed for a week.
 */

const ART = 'e2e/review-artifacts/F3';
const PREVIEW = `/graded-tests/${TEST_A}/returned?batch=${BATCH_ID}`;

test.use({ viewport: { width: 1440, height: 900 } });

/** Wait for the page image AND the stamp's measurement — a screenshot taken
 *  before the ResizeObserver fires photographs a page with no stamp on it. */
async function settled(page: import('@playwright/test').Page) {
    await expect(page.locator('[data-returned-exam]')).toBeVisible();
    await expect(page.locator('[data-page-view="scan"] img')).toBeVisible();
    await expect(page.locator('[data-stamp-drag][data-measured="true"]')).toBeVisible();
    await page.waitForTimeout(250);
}

test('P1–P4 — the preview renders from the approved contract', async ({ page }) => {
    await installGradeReviewMocks(page, { feedState: 'complete', approved: true });
    await page.goto(PREVIEW);
    await settled(page);

    await expect(page.locator('h1')).toContainText('המבחן המוחזר');
    // P2: six scan pages + the appendix pages the content actually needs.
    const strip = page.locator('[data-strip-page]');
    expect(await strip.count()).toBeGreaterThan(6);
    await expect(page.locator('[data-strip-kind="appendix"]').first()).toBeVisible();
    await page.screenshot({ path: `${ART}/preview-page1.png` });
});

/**
 * `preview-drag-stamp-apply-to-batch` + `stamp-drag-persists-and-shows-apply-link`
 * (spec §7).
 *
 * The link must NOT be there before the drag: offering to propagate a position
 * she has not chosen is offering to spread the picker's guess across thirty
 * exams. The write goes to the stamp's OWN endpoint (OD-1) — never `/draft`,
 * which refuses approved rows and made this journey a refusal for a while.
 */
test('preview-drag-stamp-apply-to-batch: stamp-drag-persists-and-shows-apply-link',
    async ({ page }) => {
        const patches: string[] = [];
        await installGradeReviewMocks(page, { feedState: 'complete', approved: true });
        page.on('request', (request) => {
            if (request.method() === 'PATCH') patches.push(request.url());
        });

        await page.goto(PREVIEW);
        await settled(page);

        await expect(page.locator('[data-apply-all]')).toHaveCount(0);

        const stamp = page.locator('[data-stamp-drag]');
        const before = await stamp.boundingBox();
        const pageBox = await page.locator('[data-page-view="scan"]').boundingBox();
        expect(before && pageBox).toBeTruthy();

        await page.mouse.move(before!.x + before!.width / 2, before!.y + before!.height / 2);
        await page.mouse.down();
        await page.mouse.move(pageBox!.x + pageBox!.width * 0.6,
            pageBox!.y + pageBox!.height * 0.55, { steps: 12 });
        await page.mouse.up();

        // The drag went to the stamp endpoint — and ONLY there. A write to
        // `/draft` here would be the old dead path coming back.
        await expect.poll(() => patches.filter((u) => u.includes('/stamp_position')).length)
            .toBe(1);
        expect(patches.filter((u) => u.includes('/draft'))).toHaveLength(0);
        await expect(page.getByText('מיקום החותמת נשמר')).toBeVisible();

        // The stamp STAYS where she dropped it, and the offer appears.
        const after = await stamp.boundingBox();
        expect(after!.x).not.toBeCloseTo(before!.x, 0);
        await expect(page.locator('[data-apply-all]')).toBeVisible();
        await page.screenshot({ path: `${ART}/preview-stamp-dragged.png` });

        // «Apply to all» → the batch default, carrying the DROPPED position.
        await page.locator('[data-apply-all]').click();
        await expect(page.getByText('המיקום הוחל על כל המבחנים במקבץ')).toBeVisible();
        expect(patches.some((u) => /\/batches\/[^/]+$/.test(u))).toBe(true);
    });

/**
 * A LOOK IS NOT A DECISION.
 *
 * A bare click used to commit a manual point: it froze the picker's guess as
 * «her choice» (which «apply to all» then refuses to move), shifted the printed
 * stamp by ~24pt because a corner and a point are measured differently, and
 * offered to push that accident across the whole batch.
 */
test('P3 — clicking the stamp without moving it commits nothing',
    async ({ page }) => {
        const patches: string[] = [];
        await installGradeReviewMocks(page, { feedState: 'complete', approved: true });
        page.on('request', (r) => {
            if (r.method() === 'PATCH') patches.push(r.url());
        });

        await page.goto(PREVIEW);
        await settled(page);

        const stamp = page.locator('[data-stamp-drag]');
        const before = await stamp.boundingBox();
        await page.mouse.move(before!.x + before!.width / 2, before!.y + before!.height / 2);
        await page.mouse.down();
        await page.mouse.up();

        const after = await stamp.boundingBox();
        expect(after!.x).toBeCloseTo(before!.x, 1);
        expect(after!.y).toBeCloseTo(before!.y, 1);
        expect(patches.filter((u) => u.includes('/stamp_position'))).toHaveLength(0);
        await expect(page.locator('[data-apply-all]')).toHaveCount(0);
    });

/** `appendix-toggle-with-info` (spec §7). */
test('appendix-toggle-with-info: the (i) explains the batch-wide switch before she flips it',
    async ({ page }) => {
        await installGradeReviewMocks(page, { feedState: 'complete', approved: true });
        await page.goto(PREVIEW);
        await settled(page);

        await expect(page.locator('[data-breakdown-tip]')).toHaveCount(0);
        await page.locator('[data-breakdown-info]').hover();
        const tip = page.locator('[data-breakdown-tip]');
        await expect(tip).toBeVisible();
        // The first sentence is the whole point: this is not a per-test switch.
        await expect(tip).toContainText('חל על כל המבחנים במקבץ');
        await page.screenshot({ path: `${ART}/preview-toggle-info.png` });
    });

test('P4 — the switch adds the criteria breakdown to every appendix scope',
    async ({ page }) => {
        await installGradeReviewMocks(page, { feedState: 'complete', approved: true });
        await page.goto(PREVIEW);
        await settled(page);

        // Jump to the first appendix page.
        await page.locator('[data-strip-kind="appendix"]').first().click();
        await expect(page.locator('[data-appendix-page]')).toBeVisible();
        await expect(page.locator('[data-appendix-total]')).toContainText('79.5');
        await expect(page.locator('[data-appendix-breakdown]')).toHaveCount(0);
        await page.screenshot({ path: `${ART}/preview-appendix-plain.png` });

        await page.locator('[data-breakdown-toggle]').click();
        await expect(page.locator('[data-breakdown-toggle]'))
            .toHaveAttribute('data-checked', 'on');
        await expect(page.locator('[data-appendix-breakdown]').first()).toBeVisible();
        await page.screenshot({ path: `${ART}/preview-appendix-breakdown.png` });
    });

/**
 * A control that LOOKS like it took effect but did not is how a batch of thirty
 * gets the wrong appendix. The switch must go back and say so.
 */
test('P1 — a failed settings write rolls the switch back and says so',
    async ({ page }) => {
        await installGradeReviewMocks(page, {
            feedState: 'complete', approved: true, failBatchSettings: true,
        });
        await page.goto(PREVIEW);
        await settled(page);

        await page.locator('[data-breakdown-toggle]').click();
        // The SERVER's own Hebrew when it sends one (§6) — the mock answers
        // 500 {detail: 'שמירה נכשלה'}, and that is what she reads. Our fallback
        // («לא הצלחנו לשמור את ההגדרה — נסי שוב») appears only when the failure
        // carried no detail at all.
        await expect(page.getByText('שמירה נכשלה').first()).toBeVisible();
        await expect(page.locator('[data-breakdown-toggle]'))
            .toHaveAttribute('data-checked', 'off');
    });

/** P8. */
test('P8 — an exam edited after signing says the copy below is the old one',
    async ({ page }) => {
        await installGradeReviewMocks(page, {
            feedState: 'complete', approved: true, staleReturnedExam: true,
        });
        await page.goto(PREVIEW);
        await settled(page);

        const banner = page.locator('[data-stale-banner]');
        await expect(banner).toBeVisible();
        await expect(banner).toContainText('ערכת את הבדיקה אחרי החתימה');
        await expect(page.locator('[data-reapprove]')).toBeVisible();
        await page.screenshot({ path: `${ART}/preview-stale.png` });
    });

/**
 * Reached without a batch, the two batch-wide controls are ABSENT, not inert:
 * a switch that writes to a batch we had to guess is worse than no switch.
 */
test('the batch-wide controls vanish on a link that carries no batch',
    async ({ page }) => {
        await installGradeReviewMocks(page, { feedState: 'complete', approved: true });
        await page.goto(`/graded-tests/${TEST_A}/returned`);
        await expect(page.locator('[data-returned-exam]')).toBeVisible();
        await expect(page.locator('[data-breakdown-toggle]')).toHaveCount(0);
    });

/** A draft has no contract, so there is nothing honest to preview. */
test('a test that was never signed refuses instead of previewing a draft',
    async ({ page }) => {
        await installGradeReviewMocks(page, { feedState: 'running', approved: false });
        await page.goto(PREVIEW);
        await expect(page.locator('[data-not-approved]')).toBeVisible();
        await expect(page.locator('[data-returned-exam]')).toHaveCount(0);
    });

/**
 * THE REACHABILITY GUARD. F2 shipped orphaned once — 900 green tests and no way
 * in from the product. Every phase now proves its own front door.
 */
test('an approved pile card opens the returned exam from the dashboard',
    async ({ page }) => {
        await installGradeReviewMocks(page, { feedState: 'complete', approved: true });
        await page.goto(`/batches/${BATCH_ID}`);
        await page.locator('[data-pile-card][data-card-state="approved"] button')
            .first().click();
        await expect(page).toHaveURL(/\/graded-tests\/.+\/returned\?batch=/);
        await expect(page.locator('[data-returned-exam]')).toBeVisible();
    });

test('the mockup preview, for visual comparison', async ({ page }) => {
    const mockup = `file://${process.cwd().replace(/\\/g, '/')}/../vivi-grade-review-mockup-v2.html`;
    await page.goto(mockup);
    await page.locator('.tabs button[data-v="v-preview"]').click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${ART}/mockup-preview.png` });

    await page.evaluate(() => (window as unknown as { showPage: (i: number) => void })
        .showPage(6));
    await page.waitForTimeout(200);
    await page.screenshot({ path: `${ART}/mockup-appendix.png` });
});
