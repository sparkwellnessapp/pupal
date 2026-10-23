import { expect, test, type Page } from '@playwright/test';

import {
    BATCH_ID, TEST_A, installGradeReviewMocks, readDraft,
} from './gradeReviewFixtures';

/**
 * F2 — the review module, driven in a real browser.
 *
 * The vitest suites close the data half (pricer, model, keymap, staleness) and
 * SSR-render the surface; none of them can catch a white screen, a bidi
 * inversion, or a keyboard that does nothing. This does.
 *
 * It also produces the phase's VISUAL EVIDENCE: full-page captures compared
 * against `vivi-grade-review-mockup-v2.html`.
 */

const REVIEW = `/batches/${BATCH_ID}/grade-review/${TEST_A}`;

/**
 * [S4] Open every collapsed criterion.
 *
 * The breakdown now sits behind a disclosure, so the per-CHECK affordances —
 * verdict buttons, the per-check quote button — are not in the DOM until she
 * opens the box. Tests that drive those are testing the row, not the fold, so
 * they open everything first and say so. Journeys that are ABOUT the fold live
 * in their own block and must not use this.
 */
async function openAllBreakdowns(page: Page) {
    // WAIT FOR THE SURFACE FIRST. `page.goto` resolves on load, but this screen
    // paints only after its (mocked) fetches settle — so querying straight away
    // matches nothing, opens nothing, and hands the test a silent no-op that
    // looks exactly like the product having no quote buttons.
    await page.locator('[data-breakdown-for]').first().waitFor();
    const ids: string[] = await page.locator('[data-breakdown-for]').evaluateAll(
        (els) => els
            .filter((el) => el.getAttribute('aria-expanded') === 'false')
            .map((el) => el.getAttribute('data-breakdown-for') as string));
    for (const id of ids) {
        await page.locator(`[data-breakdown-for="${id}"]`).click();
    }
}

const ART = 'e2e/review-artifacts/F2';

test.describe('בדיקת ציונים — the review module', () => {
    test('land-review-override-approve-stamp: land → override → the total goes red → approve', async ({ page }) => {
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);

        const total = page.locator('[data-total]');
        await expect(total).toBeVisible();
        await expect(total).toHaveAttribute('data-overridden', 'false');
        const proposal = (await total.textContent())?.trim();

        await page.screenshot({ path: `${ART}/review-landed.png`, fullPage: true });

        await openAllBreakdowns(page);

        // Click the first verdict button — one click cycles the verdict.
        const firstVerdict = page.locator('[data-check-id] [data-verdict]').first();
        await firstVerdict.click();

        // Grey proposes; red decided. The whole ink grammar in one assertion.
        await expect(total).toHaveAttribute('data-overridden', 'true');
        await expect(page.locator('[data-check-id][data-overridden="true"]').first())
            .toBeVisible();
        await expect(page.getByText('אחרי השינויים שלך')).toBeVisible();
        expect((await total.textContent())?.trim()).not.toBe(proposal);

        // Vivi's proposal survives beside her decision.
        await expect(page.getByText('הצעת ויוי:').first()).toBeVisible();

        await page.screenshot({ path: `${ART}/review-overridden.png`, fullPage: true });

        await expect(page.getByRole('button', { name: /אישור וחתימה/ })).toBeEnabled();
    });

    test('the keyboard drives the checklist', async ({ page }) => {
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await expect(page.locator('[data-check-id]').first()).toBeVisible();

        // ↓ focuses the first check; Space cycles it; ⌫ puts it back.
        await page.keyboard.press('ArrowDown');
        const focused = page.locator('[data-check-id][data-focused="true"]');
        await expect(focused).toHaveCount(1);

        await page.keyboard.press('Space');
        await expect(page.locator('[data-total]')).toHaveAttribute('data-overridden', 'true');

        await page.keyboard.press('Backspace');
        await expect(page.locator('[data-total]')).toHaveAttribute('data-overridden', 'false');
    });

    test('Space never scrolls the page while it is judging a check', async ({ page }) => {
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await page.keyboard.press('ArrowDown');
        const before = await page.evaluate(() => window.scrollY);
        await page.keyboard.press('Space');
        expect(await page.evaluate(() => window.scrollY)).toBe(before);
    });

    test('quote-button-pin-hover-focus-precedence: a quote button pins the highlight, Esc releases it', async ({ page }) => {
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);

        await openAllBreakdowns(page);
        const quoteButton = page.getByRole('button', { name: /ציטוט רלוונטי מהתשובה/ }).first();
        await quoteButton.click();

        // The span lights immediately — the click leaves the mouse ON the row,
        // and hover outranks pin by design (precedence: hover ?? pin ?? focus).
        await expect(page.locator('mark')).toHaveCount(1);

        // The PERSISTENT underline is the pin's own mark, and it appears once
        // the mouse leaves: drawing it under the cursor would flicker it on and
        // off as she moves between rows.
        await page.mouse.move(0, 0);
        await expect(page.locator('mark[data-pinned="true"]')).toHaveCount(1);

        await page.keyboard.press('Escape');
        await expect(page.locator('mark[data-pinned="true"]')).toHaveCount(0);
    });

    /**
     * [S3] The criterion-level button lights the UNION, and one pin replaces
     * the other (owner ruling D4: one pin at a time, criterion replaces check).
     *
     * The identity «the union is exactly what its rows light» is pinned as an
     * equation in `evidence-highlight.test.ts`; this journey proves the WIRING —
     * that the button exists, lights something, is drawn as pinned, is replaced
     * by a per-check pin rather than layered beneath it, and releases on Esc.
     */
    test('criterion-quote-button: lights the union, and a check pin replaces it', async ({ page }) => {
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);

        const unionButton = page.locator('[data-terminal-quote]').first();
        await expect(unionButton).toBeVisible();
        await unionButton.click();
        await page.mouse.move(0, 0);                       // hover outranks pin

        // Something is lit, drawn as pinned, and the CRITERION button says so.
        await expect(page.locator('mark[data-pinned="true"]').first()).toBeVisible();
        await expect(page.locator('[data-terminal-quote][data-pinned="true"]')).toHaveCount(1);

        // A per-check pin REPLACES it: the criterion's pinned state clears and
        // exactly one span (that check's own) stays lit. Clicking the union
        // above OPENED that criterion (S4), so its rows are reachable.
        await page.getByRole('button', { name: /ציטוט רלוונטי מהתשובה/ }).first().click();
        await page.mouse.move(0, 0);
        await expect(page.locator('[data-terminal-quote][data-pinned="true"]')).toHaveCount(0);
        await expect(page.locator('mark[data-pinned="true"]')).toHaveCount(1);

        // …and clicking the criterion again takes it back, replacing the check pin.
        await unionButton.click();
        await page.mouse.move(0, 0);
        await expect(page.locator('[data-terminal-quote][data-pinned="true"]')).toHaveCount(1);

        await page.keyboard.press('Escape');
        await expect(page.locator('mark[data-pinned="true"]')).toHaveCount(0);
        await expect(page.locator('[data-terminal-quote][data-pinned="true"]')).toHaveCount(0);
    });

    /**
     * THE CLICK NO LONGER HAS TO MOVE THE PAGE — the layout removed the cause.
     *
     * This guard used to assert the opposite, and was right to: the button sat
     * in the checklist BELOW the answer it cited, the answer was usually
     * off-screen above, and the toast was the teacher's only evidence that
     * anything had happened. (An earlier fix derived the scroll from HIGHLIGHT
     * STATE — which also changes on hover and on keyboard focus — so the page
     * jumped whenever the mouse crossed a criterion; that is now structurally
     * impossible, HL-3.)
     *
     * At two columns the answer is pinned beside the criteria of its own scope
     * (LAY-1), so the evidence she asked for is already on screen and the only
     * thing that may move is the pane's own `scrollTop`. The one-column band
     * keeps the old behaviour and has the test below.
     */
    test('quote-button-reveals-without-moving-the-page: the pane scrolls, the page does not',
        async ({ page }) => {
            await installGradeReviewMocks(page);
            await page.goto(REVIEW);

            await openAllBreakdowns(page);
            const quoteButton = page.getByRole('button', { name: /ציטוט רלוונטי מהתשובה/ }).first();
            await quoteButton.scrollIntoViewIfNeeded();
            await page.waitForTimeout(300);

            // LAY-1: she is on a criterion row, so that scope's answer is beside
            // it — which is exactly why nothing has to scroll.
            const paneVisible = await quoteButton.evaluate((btn) => {
                const pane = btn.closest('[data-scope-id]')!
                    .querySelector('[data-answer-pane]')!.getBoundingClientRect();
                return pane.bottom > 0 && pane.top < window.innerHeight;
            });
            expect(paneVisible).toBe(true);

            const before = await page.evaluate(() => window.scrollY);
            await quoteButton.click();
            await page.waitForTimeout(700);              // the pane's scroll is smooth

            expect(await page.evaluate(() => window.scrollY)).toBe(before);
            await page.mouse.move(0, 0);
            await expect(page.locator('mark[data-pinned="true"]').first()).toBeVisible();
        });

    test('one-column band: the click still brings the answer into view', async ({ page }) => {
        // Between `desk` (941) and `split` (1180) the same grid reflows to one
        // column and the answer sits above a long checklist again. Honest
        // degradation (§1.5): no co-visibility guarantee, but the click must
        // still show her what it claims to be showing (OD-A11).
        await page.setViewportSize({ width: 1100, height: 800 });
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);

        await openAllBreakdowns(page);
        const quoteButton = page.getByRole('button', { name: /ציטוט רלוונטי מהתשובה/ }).first();
        await quoteButton.scrollIntoViewIfNeeded();

        // Park the viewport well below the first answer, the way a teacher
        // reading the checklist has it.
        await page.mouse.wheel(0, 1200);
        await page.waitForTimeout(300);

        const answer = page.locator('[data-answer-pane]').first();
        const before = await answer.boundingBox();

        await quoteButton.click();
        await page.waitForTimeout(700);          // the scroll is smooth
        const after = await answer.boundingBox();

        expect(before).not.toBeNull();
        expect(after).not.toBeNull();
        // The answer moved DOWN the viewport, i.e. the page scrolled up to it,
        // and it ended up somewhere a person can actually read.
        expect(after!.y).toBeGreaterThan(before!.y);
        expect(after!.y).toBeLessThan(await page.evaluate(() => window.innerHeight));
    });

    test('hovering a criterion never scrolls the page', async ({ page }) => {
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);

        // Bring a quote button into view FIRST, then read the position. The
        // mouse is moved by coordinate rather than with `.hover()`, because
        // Playwright's hover scrolls the target into view itself — that would
        // measure Playwright, not the app.
        await openAllBreakdowns(page);
        const quoteButton = page.getByRole('button', { name: /ציטוט רלוונטי מהתשובה/ }).first();
        await quoteButton.scrollIntoViewIfNeeded();
        await page.waitForTimeout(300);

        const box = await quoteButton.boundingBox();
        expect(box).not.toBeNull();
        const before = await page.evaluate(() => window.scrollY);

        await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
        await page.waitForTimeout(500);

        // The hover paints a transient highlight by design; it must move nothing.
        await expect(page.locator('mark')).toHaveCount(1);
        expect(await page.evaluate(() => window.scrollY)).toBe(before);
    });

    /**
     * The bidi guard, extended to the two-mode answer. `unicode-bidi: plaintext`
     * is FALSIFIED: it resolves paragraph direction from the first strong
     * character, so a Hebrew comment goes RTL-base and its `//` jumps to the
     * RIGHT of the Hebrew. Any new mechanism must pass this before it is
     * believed.
     */
    test('bidi-two-mode-answer: a Hebrew comment keeps its slashes on the left',
        async ({ page }) => {
            // moran_aharon q2.א is the ONE answer in the whole cohort with a
            // Hebrew-only comment line — verified, not assumed.
            await installGradeReviewMocks(page, { student: 'moran_aharon' });
            await page.goto(REVIEW);

            // The island that actually CONTAINS the Hebrew comment — not
            // simply the first one on the page, which is q1.א and has none.
            const island = page
                .locator('[data-answer-mode="code"]:has([data-line-dir="rtl"])')
                .first();
            await expect(island).toBeVisible();
            await expect(island).toHaveAttribute('dir', 'ltr');

            const hebrewLine = island.locator('[data-line-dir="rtl"]').first();
            await expect(hebrewLine).toBeVisible();

            // The comment line must start (visually) to the LEFT of where the
            // island's right edge is — i.e. it is still left-aligned code.
            const lineBox = await hebrewLine.boundingBox();
            const islandBox = await island.boundingBox();
            expect(lineBox).not.toBeNull();
            expect(islandBox).not.toBeNull();
            expect(lineBox!.x).toBeLessThan(islandBox!.x + islandBox!.width / 2);

            await page.screenshot({ path: `${ART}/answer-bidi.png` });
        });

    test('an all-Hebrew answer renders as prose, not as a code island',
        async ({ page }) => {
            // SYNTHETIC by necessity: every student in the cohort wrote code, so
            // the prose renderer has no observed input (see the mock's
            // `answersOverride` note).
            await installGradeReviewMocks(page, {
                answersOverride: [{
                    question_number: 1,
                    sub_question_id: 'א',
                    answer_text: [
                        'התוכנית קולטת את שמות התחביבים ואת מספר הדקות.',
                        'לאחר מכן היא מחזירה את התחביב שהוקדשו לו הכי הרבה דקות.',
                    ].join('\n'),
                }],
            });
            await page.goto(REVIEW);
            const prose = page.locator('[data-answer-mode="prose"]').first();
            await expect(prose).toBeVisible();
            await expect(prose).toHaveAttribute('dir', 'rtl');
        });

    test('save-failure-blocks-navigation', async ({ page }) => {
        await installGradeReviewMocks(page, { failSave: true });
        await page.goto(REVIEW);

        await page.locator('[data-check-id] [data-verdict]').first().click();

        // Ctrl+S flushes now (OD-F7) rather than waiting out the debounce.
        await page.keyboard.press('Control+s');
        await expect(page.locator('[data-save-state="failed"]')).toBeVisible();
        await expect(page.getByText('השמירה נכשלה — נסי שוב')).toBeVisible();

        // She must not be walked to the next test with her work only in this tab.
        await page.getByRole('button', { name: /^הבא/ }).click();
        await expect(page).toHaveURL(new RegExp(TEST_A));

        await page.screenshot({ path: `${ART}/save-failed.png`, fullPage: true });
    });

    test('refuses a pre-v5 draft instead of painting empty checklists',
        async ({ page }) => {
            const draft = readDraft('dan_basiuk') as {
                scope_outcomes: { criterion_outcomes: Record<string, unknown>[] }[];
            };
            for (const scope of draft.scope_outcomes) {
                for (const criterion of scope.criterion_outcomes) {
                    criterion.checks = null;
                    for (const sub of (criterion.sub_criterion_outcomes ?? []) as
                        Record<string, unknown>[]) sub.checks = null;
                }
            }
            await installGradeReviewMocks(page, { draftOverride: draft });
            await page.goto(REVIEW);

            await expect(page.locator('[data-no-checks]')).toBeVisible();
            await expect(page.locator('[data-check-id]')).toHaveCount(0);
        });

    test('mobile-dashboard-glanceable-review-interstitial: the review module yields on a phone', async ({ page }) => {
        await installGradeReviewMocks(page);
        await page.setViewportSize({ width: 390, height: 844 });
        await page.goto(REVIEW);

        await expect(page.getByText(/דורשת מסך רחב/)).toBeVisible();
        // CSS-only yield, matching the transcription module's D11 precedent:
        // the surface is in the DOM but never VISIBLE, so nothing about the
        // checklist can be read — or approved — from a phone.
        await expect(page.locator('[data-check-id]').first()).not.toBeVisible();
        await expect(page.getByRole('button', { name: /אישור וחתימה/ })).not.toBeVisible();
        await page.screenshot({ path: `${ART}/mobile-interstitial.png`, fullPage: true });
    });
});

/**
 * [S4] The fold itself.
 *
 * Everything above drives what is INSIDE a criterion and opens the box first.
 * These journeys are about the box: that it starts closed, that it opens itself
 * where her eyes are needed, that her own collapse is respected afterwards, and
 * that the keyboard can still reach a row behind it.
 */
test.describe('בדיקת ציונים — the criterion fold (S4/S5)', () => {
    /**
     * ⚠ THIS GUARD WAS INVERTED BY RULING OD-8, deliberately.
     *
     * It used to assert that the criterion header lights nothing on hover, and
     * said so: «pinned here so a future "helpful" hover preview cannot arrive
     * unnoticed». The hover preview is now the point of the screen — the whole
     * reason the answer moved beside the criteria — so the guard is rewritten
     * rather than deleted, and what it protects is the DISTINCTION the ruling
     * actually cares about: hover is TRANSIENT (no persistent underline, no
     * selection), a click is not.
     */
    test('the criterion header lights its union on HOVER — transiently; the click keeps it',
        async ({ page }) => {
            await installGradeReviewMocks(page);
            await page.goto(REVIEW);
            const union = page.locator('[data-terminal-quote]').first();
            await expect(union).toBeVisible();

            await union.hover();
            // HL-5 — it takes a REST of ~150 ms, not a crossing.
            await expect(page.locator('mark').first()).toBeVisible();
            // HL-2 — and it wrote no selection: no persistent underline, and
            // the button is not pressed.
            await expect(page.locator('mark[data-pinned="true"]')).toHaveCount(0);
            await expect(page.locator('[data-terminal-quote][data-pinned="true"]')).toHaveCount(0);

            // Leaving reverts to the selection — which is nothing, here (M-1).
            await page.mouse.move(0, 0);
            await expect(page.locator('mark')).toHaveCount(0);

            await union.click();
            await page.mouse.move(0, 0);
            expect(await page.locator('mark').count()).toBeGreaterThan(0);
            await expect(page.locator('[data-terminal-quote][data-pinned="true"]')).toHaveCount(1);
        });

    test('a SWEEP down the checklist changes nothing at all [HL-5]', async ({ page }) => {
        // P3: nothing reacts faster than her intent. A pointer crossing four
        // rows on its way somewhere is not a request to see four quotations.
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await openAllBreakdowns(page);

        const rows = page.locator('[data-check-id]');
        const count = Math.min(5, await rows.count());
        for (let i = 0; i < count; i += 1) {
            const box = await rows.nth(i).boundingBox();
            if (!box) continue;
            await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
        }
        // No rest anywhere — so no timer fired, and nothing is lit.
        await expect(page.locator('mark')).toHaveCount(0);
    });

    test('a wheel under a stationary pointer changes no highlight [AM-1]', async ({ page }) => {
        // The loop this closes: hover reveals → something scrolls → a different
        // row slides under the pointer → hover fires again. Arming is what
        // makes it unreachable.
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await openAllBreakdowns(page);

        const row = page.locator(
            '[data-check-id]:has(button:has-text("ציטוט רלוונטי מהתשובה"))').first();
        await row.scrollIntoViewIfNeeded();
        const box = await row.boundingBox();
        expect(box).not.toBeNull();

        // Rest on it — it lights.
        await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
        await expect(page.locator('mark').first()).toBeVisible();

        // Now turn the wheel WITHOUT moving the mouse. Rows slide beneath it;
        // none of them may light.
        await page.mouse.wheel(0, 400);
        await page.waitForTimeout(500);
        await expect(page.locator('mark')).toHaveCount(0);
    });

    /**
     * [S4/S5 review] Two ways an id outlived the row it named.
     *
     * `focus` and `hover` are ids. She can fold the very box the caret sits
     * in, and a KEYBOARD collapse unmounts a hovered row without ever firing
     * its mouseleave. Both states then point at something she cannot see —
     * and Space on the first of those cycled an invisible verdict, the exact
     * failure mode S5 was built to remove. `visibleCheck` is the one guard.
     */
    test('folding the box the caret is in makes Space inert — no invisible verdict', async ({ page }) => {
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await page.locator('[data-breakdown-for]').first().waitFor();

        // ↓ focuses the first check and opens its box (S5).
        await page.keyboard.press('ArrowDown');
        const focused = page.locator('[data-check-id][data-focused="true"]');
        await expect(focused).toHaveCount(1);
        const terminalId = await focused.evaluate(
            (el) => el.closest('[data-terminal-id]')!.getAttribute('data-terminal-id'));
        const disclosure = page.locator(`[data-breakdown-for="${terminalId}"]`);

        // She folds that box with the caret still inside it. The disclosure is
        // then BLURRED on purpose: with DOM focus left on the button, Space is
        // the button's own activation (the keymap stands down for controls)
        // and this test would pass for a reason that is not the guard.
        await disclosure.click();
        await disclosure.evaluate((el) => (el as HTMLElement).blur());
        await expect(page.locator(`[data-terminal-id="${terminalId}"] [data-check-id]`))
            .toHaveCount(0);

        // Space must not change a grade she cannot see…
        await page.keyboard.press('Space');
        await expect(page.locator('[data-total]')).toHaveAttribute('data-overridden', 'false');
        // …and a folded focus paints nothing in the answer either.
        await expect(page.locator('mark')).toHaveCount(0);

        // Navigation, by contrast, keeps the caret: ↓ resumes from where she
        // was and opens whatever box the next row lives in.
        await page.keyboard.press('ArrowDown');
        await expect(page.locator('[data-check-id][data-focused="true"]')).toHaveCount(1);
    });

    test('a keyboard collapse leaves no phantom hover behind', async ({ page }) => {
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await page.locator('[data-breakdown-for]').first().waitFor();

        // Open one box through its union button, then release the pin so the
        // only thing that can light the answer is the hover under test.
        const union = page.locator('[data-terminal-quote]').first();
        const terminalId = await union.getAttribute('data-terminal-quote');
        await union.click();
        await page.keyboard.press('Escape');
        await expect(page.locator('mark[data-pinned="true"]')).toHaveCount(0);

        // Rest the mouse on a row that has a quote: a transient mark paints.
        const row = page.locator(
            `[data-terminal-id="${terminalId}"] [data-check-id]:has(button:has-text("ציטוט רלוונטי מהתשובה"))`,
        ).first();
        await row.hover();
        // The intent delay (HL-5) means this is not true on the same tick.
        await expect(page.locator('mark').first()).toBeVisible();

        // Collapse WITHOUT moving the mouse: focus the disclosure and press
        // Enter. The hovered row unmounts and its mouseleave never fires.
        const disclosure = page.locator(`[data-breakdown-for="${terminalId}"]`);
        await disclosure.focus();
        await page.keyboard.press('Enter');
        await expect(disclosure).toHaveAttribute('aria-expanded', 'false');

        // The hover id is now stale — and it must paint nothing.
        await expect(page.locator('mark')).toHaveCount(0);
    });

    test('starts collapsed, except the criteria that need her eyes', async ({ page }) => {
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await page.locator('[data-breakdown-for]').first().waitFor();

        const closed = page.locator('[data-breakdown-for][aria-expanded="false"]');
        const open = page.locator('[data-breakdown-for][aria-expanded="true"]');

        // Most of the page is folded…
        expect(await closed.count()).toBeGreaterThan(10);
        // …and the exception is real: dan_basiuk carries exactly one marker (a
        // clamp), so exactly one criterion opens itself. If this ever becomes
        // zero, D1's safety half is gone and «approve without reading» is one
        // click away.
        await expect(open).toHaveCount(1);
    });

    test('opens and closes on click, and her collapse STICKS', async ({ page }) => {
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await page.locator('[data-breakdown-for]').first().waitFor();

        // Pinned BY ID, not by state: a locator written as
        // `[aria-expanded="false"]` stops matching the instant the box opens,
        // and every later assertion would then be about a different criterion.
        const terminalId = await page
            .locator('[data-breakdown-for][aria-expanded="false"]').first()
            .getAttribute('data-breakdown-for');
        const header = page.locator(`[data-breakdown-for="${terminalId}"]`);
        const box = page.locator(`[data-terminal-id="${terminalId}"]`);

        await expect(box.locator('[data-check-id]')).toHaveCount(0);
        await header.click();
        await expect(header).toHaveAttribute('aria-expanded', 'true');
        expect(await box.locator('[data-check-id]').count()).toBeGreaterThan(0);

        // She decides something inside it, then folds it away.
        await box.locator('[data-verdict]').first().click();
        await expect(box.locator('[data-check-id][data-overridden="true"]').first())
            .toBeVisible();
        await header.click();
        await expect(header).toHaveAttribute('aria-expanded', 'false');

        // AND IT STAYS SHUT. The opening rule's second clause re-opens criteria
        // she has already decided — computed ONCE, at mount. Were it live, the
        // override she just made would spring this box open again under her
        // hand, which is the UI arguing with the teacher.
        await page.waitForTimeout(300);
        await expect(header).toHaveAttribute('aria-expanded', 'false');
        await expect(box.locator('[data-check-id]')).toHaveCount(0);
    });

    test('the keyboard opens a folded criterion rather than focusing nothing', async ({ page }) => {
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await page.locator('[data-breakdown-for]').first().waitFor();

        const first = page.locator('[data-breakdown-for]').first();
        await expect(first).toHaveAttribute('aria-expanded', 'false');

        // Before S5 this focused a row that was not in the DOM: the caret went
        // nowhere and the next Space would have cycled a verdict she could not
        // see — the worse of the two failure modes.
        await page.keyboard.press('ArrowDown');

        await expect(first).toHaveAttribute('aria-expanded', 'true');
        await expect(page.locator('[data-check-id][data-focused="true"]')).toHaveCount(1);
    });

    test('F opens the criterion it stops at', async ({ page }) => {
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await page.locator('[data-breakdown-for]').first().waitFor();

        await page.keyboard.press('KeyF');

        // F promises to stop at the thing needing her eyes; stopping beside a
        // closed box that hides it would keep the letter of that, not the point.
        await expect(page.locator('[data-breakdown-for][aria-expanded="true"]').first())
            .toBeVisible();
    });
});


/**
 * The MOCKUP, captured through the same browser at the same viewport — so the
 * comparison is like for like rather than a screenshot against a memory.
 */
test('capture the mockup for visual comparison', async ({ page }) => {
    const file = `file://${process.cwd().replace(/\\/g, '/')}/../vivi-grade-review-mockup-v2.html`;
    await page.goto(file);
    await page.locator('.tabs button[data-v="v-review"]').click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${ART}/mockup-review.png`, fullPage: true });
});

/**
 * F2 completion — the spec items the first pass left open.
 */
test.describe('בדיקת ציונים — R3/R9/R12 completion', () => {
    test('F walks EVERY marker kind, not just the evidence ones', async ({ page }) => {
        // The synthetic draft carries a not_found quote, a fuzzy quote and a
        // skipped scope — three different kinds, which is the point.
        await installGradeReviewMocks(page, {
            draftOverride: readDraft('SYNTHETIC_edge_cases'),
        });
        await page.goto(REVIEW);
        await page.locator('[data-check-id]').first().waitFor();

        // Each F lands somewhere; pressing it more times than there are markers
        // must WRAP rather than stall.
        const seen = new Set<string>();
        for (let i = 0; i < 6; i += 1) {
            await page.keyboard.press('KeyF');
            await page.waitForTimeout(120);
            const focused = page.locator('[data-check-id][data-focused="true"]');
            if (await focused.count()) {
                seen.add((await focused.getAttribute('data-check-id')) ?? '');
            }
        }
        // At least the two evidence markers were visited.
        expect(seen.size).toBeGreaterThanOrEqual(2);
    });

    test('the scope nav follows the scroll (R3 scroll-spy)', async ({ page }) => {
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await page.locator('[data-nav-scope]').first().waitFor();

        const navIds = await page.locator('[data-nav-scope]').evaluateAll(
            (els) => els.map((e) => (e as HTMLElement).dataset.navScope));
        expect(navIds.length).toBeGreaterThan(2);

        // Scroll to the LAST question; the nav must follow without a click.
        const last = navIds[navIds.length - 1]!;
        await page.locator(`[data-scope-id="${last}"]`)
            .scrollIntoViewIfNeeded();
        await page.waitForTimeout(700);
        const active = page.locator(`[data-nav-scope="${last}"]`);
        await expect(active).toHaveClass(/text-primary-700/);
    });

    test('the revision overflow is absent on a draft and present on approved',
        async ({ page }) => {
            await installGradeReviewMocks(page);
            await page.goto(REVIEW);
            await page.locator('[data-total]').waitFor();
            // A draft is the thing being reviewed — no revision applies.
            await expect(page.locator('[data-revision-menu]')).toHaveCount(0);
        });
});

/**
 * R4 — «הצגת הסריקה». Was a placeholder toast for two phases: the button
 * existed, the scan did not. It opens the pages the transcription attributed to
 * THAT answer, fetched as authorized bytes, and Esc closes it without also
 * firing the surface's own Esc.
 */
test.describe('בדיקת ציונים — the scan viewer (R4)', () => {
    test('«הצגת הסריקה» opens the pages the transcription attributed to the answer',
        async ({ page }) => {
            await installGradeReviewMocks(page);
            await page.goto(REVIEW);
            await expect(page.locator('[data-check-id]').first()).toBeVisible();

            await expect(page.locator('[data-scan-viewer]')).toHaveCount(0);
            await page.getByRole('button', { name: 'הצגת הסריקה' }).first().click();

            const viewer = page.locator('[data-scan-viewer]');
            await expect(viewer).toBeVisible();
            await expect(viewer).toContainText('הסריקה ·');
            const pages = viewer.locator('[data-scan-page]');
            expect(await pages.count()).toBeGreaterThan(0);
            // The page is a real, loaded image — not a placeholder that
            // happens to be in the DOM.
            const img = pages.first().locator('img');
            await expect(img).toBeVisible();
            await expect(img).toHaveJSProperty('complete', true);
            await page.screenshot({ path: `${ART}/scan-viewer.png` });

            await page.keyboard.press('Escape');
            await expect(viewer).toHaveCount(0);
        });
});

/**
 * THE KEYMAP STANDS DOWN BEHIND THE VIEWER. With it live, Space behind the
 * modal cycled the focused verdict and Ctrl+↵ signed and advanced the test she
 * could not see.
 */
test('R4 — the keyboard is inert while the scan viewer is open', async ({ page }) => {
    const posts: string[] = [];
    await installGradeReviewMocks(page);
    page.on('request', (r) => { if (r.method() === 'POST') posts.push(r.url()); });
    await page.goto(REVIEW);
    await expect(page.locator('[data-check-id]').first()).toBeVisible();

    await page.keyboard.press('ArrowDown');
    const focused = page.locator('[data-check-id][data-focused="true"]');
    await expect(focused).toHaveCount(1);
    const before = await focused.locator('[data-verdict]').getAttribute('data-verdict');

    await page.getByRole('button', { name: 'הצגת הסריקה' }).first().click();
    const viewer = page.locator('[data-scan-viewer]');
    await expect(viewer).toBeVisible();
    // The close button takes focus on open, and Space on a focused BUTTON is
    // the browser's own activation — that closes the viewer legitimately and
    // would let the next key reach the surface. Move focus off it first, so the
    // keys land on the surface's window listener with the viewer still open;
    // THAT is the guard under test.
    await viewer.locator('[data-scan-page]').first().click();
    await page.keyboard.press('Space');
    await page.keyboard.press('Control+Enter');
    await expect(viewer).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(viewer).toHaveCount(0);

    await expect(focused.locator('[data-verdict]')).toHaveAttribute('data-verdict', before!);
    await expect(page.locator('[data-check-id][data-overridden="true"]')).toHaveCount(0);
    expect(posts.filter((u) => u.includes('/approve'))).toHaveLength(0);
    await expect(page).toHaveURL(new RegExp(`${TEST_A}$`));
});

/**
 * R13 — a manual_edit successor says so. Driven by `regraded_from_id` AND an
 * approved predecessor; the number comes from the feed's `version`.
 */
test('R13 — a revision draft carries the version banner', async ({ page }) => {
    await installGradeReviewMocks(page, { revision: true });
    await page.goto(REVIEW);
    const banner = page.locator('[data-version-banner]');
    await expect(banner).toBeVisible();
    await expect(banner).toContainText('גרסה 2');
    await expect(banner).toContainText('את עורכת בדיקה שכבר אושרה');
});

/**
 * A RETRY successor also carries `regraded_from_id`, but its predecessor FAILED
 * — «את עורכת בדיקה שכבר אושרה» would be false, so the banner stays down.
 */
test('R13 — a retry successor of a failed test carries no version banner',
    async ({ page }) => {
        await installGradeReviewMocks(page, { revision: true, revisionFrom: 'failed' });
        await page.goto(REVIEW);
        await expect(page.locator('[data-total]')).toBeVisible();
        await expect(page.locator('[data-version-banner]')).toHaveCount(0);
    });

/** An ordinary draft is NOT a revision — no banner, no number. */
test('R13 — a first-version draft carries no version banner', async ({ page }) => {
    await installGradeReviewMocks(page);
    await page.goto(REVIEW);
    await expect(page.locator('[data-total]')).toBeVisible();
    await expect(page.locator('[data-version-banner]')).toHaveCount(0);
});

/**
 * R2 — the queue line names who is grading now AND how long, from the batch's
 * own ETA. The fixture says 68 seconds; minutes-granular and rounded UP that is
 * «עוד כ-2 דקות» — a small lie in the direction that makes her wait, never the
 * one that makes the product look late (see `etaText`).
 */
test('R2 — the queue line carries the batch ETA for the test being graded',
    async ({ page }) => {
        await installGradeReviewMocks(page, { feedState: 'running' });
        await page.goto(REVIEW);
        await expect(page.locator('[data-total]')).toBeVisible();
        await expect(page.getByText(/נבדק עכשיו, עוד כ-2 דקות/)).toBeVisible();
    });

/**
 * [OD-R2, owner ruling 2026-09-13] Typed points — on a check row and on the
 * criterion row. The vitest suites pin the reducers and the pricer; these pin
 * the half only a browser can: the field opens, the refusal shows LIVE, the
 * figures up the tree follow, and the overlay that leaves for the server
 * carries her number with the verdict it implies.
 */
test.describe('typed points [OD-R2]', () => {
    const firstRow = (page: Page) => page.locator('[data-check-id]').first();
    const rowPoints = (page: Page) => firstRow(page).locator('button[data-points-target="check"]');
    const input = (page: Page) => page.locator('input[data-points-input]');
    const draftSave = (page: Page) => page.waitForRequest(
        (r) => r.method() === 'PATCH' && r.url().includes('/draft'));

    test('typing on a check row re-prices the row, the criterion and the total, and travels', async ({ page }) => {
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await openAllBreakdowns(page);
        const total = page.locator('[data-total]');
        const before = await total.textContent();

        await rowPoints(page).click();
        await expect(input(page)).toBeFocused();
        await input(page).fill('0');
        await input(page).press('Enter');

        await expect(input(page)).toHaveCount(0);
        await expect(firstRow(page)).toHaveAttribute('data-points-typed', 'true');
        await expect(firstRow(page)).toHaveAttribute('data-overridden', 'true');
        // a typed zero is ✗ — the glyph follows the number (OD-3 b)
        await expect(firstRow(page).locator('[data-verdict]')).toHaveAttribute('data-verdict', 'not_met');
        await expect(total).toHaveAttribute('data-overridden', 'true');
        expect(await total.textContent()).not.toBe(before);

        const saved = draftSave(page);
        await page.keyboard.press('Control+s');
        const body = (await saved).postDataJSON();
        const checkId = await firstRow(page).getAttribute('data-check-id');
        const decisions = Object.values(body.overrides.terminals as Record<string, {
            check_id: string; verdict: string; points_awarded?: string;
        }[]>).flat();
        expect(decisions).toContainEqual(expect.objectContaining(
            { check_id: checkId, verdict: 'not_met', points_awarded: '0' }));
        expect(body.overrides.terminal_points).toEqual({});
    });

    test('the refusal shows LIVE above the ceiling and off the grid, and nothing commits', async ({ page }) => {
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await openAllBreakdowns(page);

        const crit = page.locator('button[data-points-target="criterion"]').first();
        const before = await crit.textContent();
        await crit.click();
        const max = (await input(page).locator('..').locator('small').textContent())!.replace(/[^\d.]/g, '');
        const tooMany = String(Number(max) + 1);
        await input(page).fill(tooMany);
        // no Enter yet — the popover is already there
        const alert = page.locator('[data-points-error]');
        await expect(alert).toHaveAttribute('data-points-error', 'over_max');
        await expect(alert).toHaveText(
            `לא ניתן להעניק ${tooMany} נקודות לקריטריון עם מקסימום ${max} נקודות`);
        // Enter on a refused number does nothing: the field stays, the number does not land
        await input(page).press('Enter');
        await expect(input(page)).toHaveCount(1);

        await input(page).fill('0.3');
        await expect(alert).toHaveAttribute('data-points-error', 'off_grid');
        await expect(alert).toContainText('בקפיצות של 0.25');

        await input(page).press('Escape');
        await expect(input(page)).toHaveCount(0);
        await expect(crit).toHaveText(before!);
        await expect(page.locator('[data-criterion-typed]')).toHaveCount(0);
    });

    test('typing on the criterion pins it; deciding a row beneath releases the pin (OD-2 b)', async ({ page }) => {
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await openAllBreakdowns(page);

        const crit = page.locator('button[data-points-target="criterion"]').first();
        await crit.click();
        await input(page).fill('0');
        await input(page).press('Enter');

        const terminalId = await page.locator('[data-criterion-points]').first()
            .getAttribute('data-criterion-points');
        await expect(page.locator(`[data-criterion-typed="${terminalId}"]`)).toBeVisible();
        await expect(firstRow(page)).toHaveAttribute('data-under-pin', 'true');
        await expect(page.locator('[data-total]')).toHaveAttribute('data-overridden', 'true');

        const saved = draftSave(page);
        await page.keyboard.press('Control+s');
        const body = (await saved).postDataJSON();
        expect(body.overrides.terminal_points).toEqual(
            { [terminalId!]: expect.objectContaining({ points_awarded: '0' }) });

        // Space on the row beneath is a decision: the pin goes
        await firstRow(page).click();
        await page.keyboard.press('Space');
        await expect(page.locator(`[data-criterion-typed="${terminalId}"]`)).toHaveCount(0);
        await expect(firstRow(page)).toHaveAttribute('data-under-pin', 'false');
    });

    test('the pin has its own revert', async ({ page }) => {
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await openAllBreakdowns(page);
        const crit = page.locator('button[data-points-target="criterion"]').first();
        const before = await crit.textContent();
        await crit.click();
        await input(page).fill('0');
        await input(page).press('Enter');
        await expect(crit).not.toHaveText(before!);
        await page.locator('[data-criterion-points-revert]').first().click();
        await expect(page.locator('[data-criterion-typed]')).toHaveCount(0);
        await expect(crit).toHaveText(before!);
    });

    test('Enter on the focused row opens its field; Esc closes it without a change', async ({ page }) => {
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await openAllBreakdowns(page);
        await firstRow(page).click();
        await expect(firstRow(page)).toHaveAttribute('data-focused', 'true');
        await page.keyboard.press('Enter');
        await expect(input(page)).toBeFocused();
        // keys inside the field belong to the field: Space types, it does not cycle
        await page.keyboard.press('Escape');
        await expect(input(page)).toHaveCount(0);
        await expect(firstRow(page)).toHaveAttribute('data-overridden', 'false');
    });

    test('an approved test offers no field at all', async ({ page }) => {
        await installGradeReviewMocks(page, { approved: true });
        await page.goto(REVIEW);
        await expect(page.locator('[data-total]')).toBeVisible();
        await expect(page.locator('button[data-points-target]')).toHaveCount(0);
        await expect(page.locator('[data-points-target="criterion"]').first()).toBeVisible();
    });
});

/**
 * A deduction row (ruling 2026-09-13): its own grammar, a two-state toggle,
 * and no points field. The production case that drove it (graded_test
 * 3438b7a2) showed «0 / 0.5» beside a ✓ and «−0.5 / 0.5» beside a ✗.
 */
test.describe('deduction rows', () => {
    test('a tariff row says הורדה, toggles ✓ ↔ ✗ only, and has no field', async ({ page }) => {
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await openAllBreakdowns(page);
        const row = page.locator('[data-check-id][data-check-kind="tariff"]').first();
        await expect(row).toBeVisible();
        await expect(row.locator('[data-chip="tariff"]')).toHaveText('הורדה');
        await expect(row.locator('button[data-points-target]')).toHaveCount(0);
        await expect(row.locator('[data-tariff-figure]')).toContainText('עד ');

        const verdict = row.locator('[data-verdict]');
        const before = await verdict.getAttribute('data-verdict');
        await verdict.click();
        const after = await verdict.getAttribute('data-verdict');
        expect(after).not.toBe(before);
        expect(after).not.toBe('partially_met');
        await expect(row).toHaveAttribute('data-overridden', 'true');
        // the figure reads as a deduction, never as «points granted»
        const figure = row.locator('[data-tariff-figure]');
        if (after === 'not_met') {
            await expect(figure).toHaveAttribute('data-tariff-figure', /charged|once/);
            await expect(figure).not.toContainText('/');
        } else {
            await expect(figure).toHaveAttribute('data-tariff-figure', 'none');
            await expect(figure).toContainText('ללא הורדה');
        }
        // and a second press returns to Vivi's verdict — two states, no ½
        await verdict.click();
        await expect(verdict).toHaveAttribute('data-verdict', before!);
        await expect(row).toHaveAttribute('data-overridden', 'false');
        // Enter on a focused tariff row opens nothing
        await row.click();
        await page.keyboard.press('Enter');
        await expect(page.locator('input[data-points-input]')).toHaveCount(0);
    });
});

/**
 * An UNVERIFIED ✓ (2026-09-15): Vivi's credit verdict whose cited span the
 * validator could not find. It prices at 0, it says so, and one press of
 * Space confirms it as hers — it used to cycle to ✗, the opposite of what a
 * teacher who has just read the answer as correct wants (graded_test a0cd07ff).
 */
test.describe('unverified ✓ — confirm, do not cycle', () => {
    test('the row is marked, worth 0, and Space confirms it into her credited ✓', async ({ page }) => {
        await installGradeReviewMocks(page, { draftOverride: readDraft('SYNTHETIC_edge_cases') });
        await page.goto(REVIEW);
        await openAllBreakdowns(page);

        // Pin the row by ID: a locator keyed on the state this test changes
        // would re-resolve to the NEXT unverified row after the first press.
        const firstUnverified = page.locator('[data-check-id][data-unverified="true"]').first();
        await expect(firstUnverified).toBeVisible();
        const rowId = await firstUnverified.getAttribute('data-check-id');
        const row = page.locator(`[data-check-id="${rowId}"]`);
        const verdict = row.locator('[data-verdict]');
        await expect(verdict).toHaveAttribute('data-verdict', 'met');
        await expect(verdict).toHaveAttribute('data-verdict-shown', 'unverified');
        await expect(row).toHaveAttribute('data-overridden', 'false');
        const figure = row.locator('button[data-points-target="check"]');
        expect((await figure.textContent())!.trim().startsWith('0')).toBe(true);

        await row.click();
        await page.keyboard.press('Space');

        await expect(row).toHaveAttribute('data-unverified', 'false');
        await expect(row).toHaveAttribute('data-overridden', 'true');
        await expect(verdict).toHaveAttribute('data-verdict-shown', 'met');
        await expect(row.locator('[data-confirmed="true"]')).toBeVisible();
        expect((await figure.textContent())!.trim().startsWith('0')).toBe(false);

        const saved = page.waitForRequest(
            (r) => r.method() === 'PATCH' && r.url().includes('/draft'));
        await page.keyboard.press('Control+s');
        const body = (await saved).postDataJSON();
        const checkId = await row.getAttribute('data-check-id');
        const decisions = Object.values(body.overrides.terminals as Record<string, {
            check_id: string; verdict: string; evidence_confirmed?: boolean;
        }[]>).flat();
        expect(decisions).toContainEqual(expect.objectContaining(
            { check_id: checkId, verdict: 'met', evidence_confirmed: true }));

        // ⌫ withdraws the confirmation: back to the unverified, uncredited state
        await page.keyboard.press('Backspace');
        await expect(row).toHaveAttribute('data-unverified', 'true');
        await expect(verdict).toHaveAttribute('data-verdict-shown', 'unverified');
        expect((await figure.textContent())!.trim().startsWith('0')).toBe(true);
    });
});
