import { expect, test } from '@playwright/test';

import { BATCH_ID, installGradeReviewMocks } from './gradeReviewFixtures';

/**
 * F1 — לוח המקבץ, driven in a real browser across all four published states.
 *
 * The visual half captures each state at the mockup's own viewport so the
 * comparison is like for like.
 */

const ART = 'e2e/review-artifacts/F1';
const DASH = `/batches/${BATCH_ID}`;

test.use({ viewport: { width: 1440, height: 900 } });

/**
 * Wait for the pile to SETTLE before capturing.
 *
 * The thumbnails arrive through an IntersectionObserver and a fetch, so a
 * fixed timeout races them — and it lost: four capture runs produced blank
 * cards while the images were in flight, and the visual review was done
 * against a page that had not finished rendering. A visual gate that
 * photographs an unsettled screen is worse than none, because it looks like
 * evidence.
 */
async function settled(page: import('@playwright/test').Page) {
    await page.locator('[data-grade-dashboard]').waitFor();
    const cards = page.locator('[data-pile-card]');
    await expect(cards.first()).toBeVisible();
    // NOT one image per card: `page1_image_url` is null when the transcription
    // has no page 1, and that card is meant to render with no image at all
    // rather than a broken-image glyph. Wait for whatever images exist.
    const images = page.locator('[data-pile-card] img');
    await expect(images.first()).toBeVisible();
    const count = await images.count();
    for (let i = 0; i < count; i += 1) {
        await expect(images.nth(i)).toHaveJSProperty('complete', true);
    }
    await page.waitForTimeout(250);
}

for (const state of ['landing', 'running', 'done', 'complete'] as const) {
    test(`the ${state} state renders and captures`, async ({ page }) => {
        await installGradeReviewMocks(page, { feedState: state });
        await page.goto(DASH);
        await settled(page);
        await page.screenshot({ path: `${ART}/dash-${state}.png` });
    });
}

test('D2 — two steps while the audit is disabled, never a dark third', async ({ page }) => {
    await installGradeReviewMocks(page, { feedState: 'running' });
    await page.goto(DASH);
    await expect(page.locator('[data-step]')).toHaveCount(2);
    await expect(page.locator('[data-step="audit"]')).toHaveCount(0);
    await expect(page.locator('[data-step="grading"]')).toHaveAttribute(
        'data-step-state', 'active');
});

/**
 * The ETA answers "when will there be something to review". Once everything has
 * landed there is nothing to wait for — and the server keeps returning an
 * estimate regardless, so a stale «עוד כ-2 דקות» would sit on the screen for
 * the rest of the evening. It goes away instead.
 */
test('D2 — the ETA disappears once every test has landed', async ({ page }) => {
    await installGradeReviewMocks(page, { feedState: 'done' });
    await page.goto(DASH);
    await expect(page.locator('[data-grade-dashboard]')).toBeVisible();
    await expect(page.locator('[data-eta]')).toHaveCount(0);
});

test('D2 — the ETA is present while tests are still landing', async ({ page }) => {
    await installGradeReviewMocks(page, { feedState: 'landing' });
    await page.goto(DASH);
    await expect(page.locator('[data-eta]')).toContainText('דקות');
});

test('D3 — one attention slot, naming the worst landed test', async ({ page }) => {
    await installGradeReviewMocks(page, { feedState: 'running' });
    await page.goto(DASH);
    const attention = page.locator('[data-attention]');
    await expect(attention).toHaveCount(1);
    await expect(attention).toHaveAttribute('data-attention', 'worst');
    await expect(attention).toContainText('דין עזרא');
    await expect(attention).toContainText('3 סימונים לבדוק');
});

test('D3 — the done banner replaces it at completion', async ({ page }) => {
    await installGradeReviewMocks(page, { feedState: 'complete' });
    await page.goto(DASH);
    await expect(page.locator('[data-attention="done"]')).toHaveCount(1);
    await expect(page.locator('[data-attention="worst"]')).toHaveCount(0);
});

/**
 * `look_count: null` is the unparseable draft. It must show NO number — 0
 * would read as "nothing to check" on precisely the test that most needs her.
 */
test('D6 — an uncomputable marker count shows no number at all', async ({ page }) => {
    await installGradeReviewMocks(page, { feedState: 'running' });
    await page.goto(DASH);

    const cards = page.locator('[data-pile-card]');
    await expect(cards).toHaveCount(5);
    // מורן אהרון is the draft whose look_count is null in the fixture.
    const unparseable = page.locator('[data-pile-card]', { hasText: 'מורן אהרון' });
    await expect(unparseable).toHaveAttribute('data-card-state', 'landed');
    await expect(unparseable).not.toContainText('לבדוק');
});

test('D6 — the card state grammar, all five states on one screen', async ({ page }) => {
    await installGradeReviewMocks(page, { feedState: 'running' });
    await page.goto(DASH);
    // evaluateAll does NOT auto-wait — without this it reads an empty DOM.
    await expect(page.locator('[data-pile-card]')).toHaveCount(5);
    const states = await page.locator('[data-pile-card]')
        .evaluateAll((els) => els.map((e) => (e as HTMLElement).dataset.cardState));
    expect(states).toContain('landed');
    expect(states).toContain('landed_marked');
    expect(states).toContain('grading');
    expect(states).toContain('failed');
});

test('D6 — a card opens the review module', async ({ page }) => {
    await installGradeReviewMocks(page, { feedState: 'running' });
    await page.goto(DASH);
    await page.locator('[data-pile-card][data-card-state="landed_marked"] button')
        .first().click();
    await expect(page).toHaveURL(/\/grade-review\//);
});

test('D6 — a grading card is not clickable', async ({ page }) => {
    await installGradeReviewMocks(page, { feedState: 'landing' });
    await page.goto(DASH);
    await expect(
        page.locator('[data-pile-card][data-card-state="grading"] button').first(),
    ).toBeDisabled();
});

test('download-modal-explicit-exclusions: D9 — the download modal names its exclusions before it does anything',
    async ({ page }) => {
        await installGradeReviewMocks(page, { feedState: 'complete' });
        await page.goto(DASH);
        await page.locator('[data-download]').click();

        const modal = page.locator('[data-download-modal]');
        await expect(modal).toBeVisible();
        // complete = 4 approved + 1 failed. The failed test is named on its own
        // line with its own remedy — calling it "not yet approved" would send
        // her looking for a review that cannot exist.
        await expect(modal.locator('[data-failed-line]')).toContainText('נכשל בניקוד');
        await expect(modal).not.toContainText('עדיין לא אושר');
        // «DownloadModal from the manifest» (spec §2): the numbers she confirms
        // against are the SERVER's, once they arrive — the feed's count is only
        // the first paint.
        await expect(modal).toHaveAttribute('data-download-source', 'manifest');
        await page.screenshot({ path: `${ART}/download-modal.png` });

        await page.keyboard.press('Escape');
        await expect(modal).toHaveCount(0);
    });

/** D8/D9 — confirming actually fetches the ZIP, through the authorized seam. */
test('D9 — confirming the modal downloads the ZIP', async ({ page }) => {
    const requests: string[] = [];
    await installGradeReviewMocks(page, { feedState: 'complete' });
    page.on('request', (r) => { requests.push(r.url()); });
    await page.goto(DASH);
    await page.locator('[data-download]').click();
    await page.locator('[data-download-confirm]').click();
    await expect.poll(() => requests.some((u) => u.includes('/returned-exams.zip'))).toBe(true);
    await expect(page.getByText('ההורדה התחילה')).toBeVisible();
    await expect(page.locator('[data-download-modal]')).toHaveCount(0);
});

/**
 * D6 — failed → retry. The card's «ניסיון נוסף» sends the grade back to the
 * grader (a new pending row; the chain extends) instead of walking her to a
 * review screen with nothing on it.
 */
test('D6 — a failed card\'s «ניסיון נוסף» retries the grade from the pile',
    async ({ page }) => {
        const posts: string[] = [];
        await installGradeReviewMocks(page, { feedState: 'running' });
        page.on('request', (r) => { if (r.method() === 'POST') posts.push(r.url()); });
        await page.goto(DASH);

        const failed = page.locator('[data-pile-card][data-card-state="failed"]').first();
        await expect(failed).toBeVisible();
        await failed.getByText('ניסיון נוסף').click();

        await expect.poll(() => posts.some((u) => u.includes('/retry'))).toBe(true);
        await expect(page.getByText(/נשלח לניקוד חוזר/).first()).toBeVisible();
        // …and we did NOT navigate away to the review route.
        await expect(page).toHaveURL(new RegExp(`/batches/${BATCH_ID}$`));
        // The card now SAYS it was sent and stops offering the same click — the
        // successor is a new row the feed cannot show, so a second «ניסיון נוסף»
        // would 409 on the now non-leaf row.
        await expect(failed.locator('[data-card-retried]')).toBeVisible();
        await expect(failed.getByText('ניסיון נוסף')).toHaveCount(0);
    });

/** D6 — a revision of a signed test says its signature is gone. */
test('D6 — a revision draft reads «גרסה n · לא נחתם»', async ({ page }) => {
    await installGradeReviewMocks(page, { feedState: 'running', revision: true });
    await page.goto(DASH);
    const card = page.locator('[data-pile-card="44444444-4444-4444-8444-000000000000"]');
    await expect(card.locator('[data-card-revision]')).toContainText('גרסה 2 · לא נחתם');
    // APPENDED to the state caption, not replacing it (mockup `card()` appends).
    await expect(card).toContainText('נחת · מוכן לבדיקה');
});

/** D6 — the grading card's caption says what is happening to THIS test. */
test('D6 — a grading card is captioned «מנוקד עכשיו»', async ({ page }) => {
    await installGradeReviewMocks(page, { feedState: 'running' });
    await page.goto(DASH);
    const grading = page.locator('[data-pile-card][data-card-state="grading"]').first();
    await expect(grading).toContainText('מנוקד עכשיו');
});

test('mobile-dashboard-glanceable-review-interstitial: D10 — the dashboard stays glanceable on a phone', async ({ page }) => {
    await installGradeReviewMocks(page, { feedState: 'running' });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(DASH);
    await expect(page.locator('[data-grade-dashboard]')).toBeVisible();
    await settled(page);
    await page.screenshot({ path: `${ART}/dash-mobile.png`, fullPage: true });
});

test('the mockup dashboard, for visual comparison', async ({ page }) => {
    const mockup = `file://${process.cwd().replace(/\\/g, '/')}/../vivi-grade-review-mockup-v2.html`;
    await page.goto(mockup);
    await page.locator('.tabs button[data-v="v-land"]').click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${ART}/mockup-dashboard.png` });
});

/**
 * A REGRESSION GUARD, added after the thumbnails silently vanished.
 *
 * The observer's lifecycle has been wrong twice — once eager (no laziness),
 * once disconnected (no images at all) — and neither showed up in any test,
 * because every other assertion is about text. Only a screenshot caught it,
 * and screenshots are not run on every change. This is.
 */
test('D6 — every card actually shows its page thumbnail', async ({ page }) => {
    await installGradeReviewMocks(page, { feedState: 'running' });
    await page.goto(DASH);
    await expect(page.locator('[data-pile-card]')).toHaveCount(5);

    // The running fixture gives all five a URL, so all five must paint.
    const images = page.locator('[data-pile-card] img');
    await expect(images).toHaveCount(5);
    for (let i = 0; i < 5; i += 1) {
        await expect(images.nth(i)).toHaveJSProperty('complete', true);
        expect(await images.nth(i).evaluate(
            (el) => (el as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
    }
});

/**
 * `page1_image_url: null` is DEGRADE BY OMISSION, not a missing feature: a URL
 * known to 404 renders a broken-image glyph, which reads as "this test is
 * damaged" rather than "we have no preview of it". The landing fixture carries
 * exactly one such item.
 */
test('D6 — a card with no page image renders no image, not a broken one',
    async ({ page }) => {
        await installGradeReviewMocks(page, { feedState: 'landing' });
        await page.goto(DASH);
        await expect(page.locator('[data-pile-card]')).toHaveCount(5);

        const withoutImage = page.locator('[data-pile-card]', { hasText: 'יונתן בסיוק' });
        await expect(withoutImage.locator('img')).toHaveCount(0);
        // …and the card is still a card: name and state intact.
        await expect(withoutImage).toContainText('יונתן בסיוק');
        await expect(withoutImage).toHaveAttribute('data-card-state', 'grading');
    });
