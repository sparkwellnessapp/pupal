import { expect, test } from '@playwright/test';

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
     * The quote button's SCROLL, and the two ways it went wrong.
     *
     * The button sits in the checklist, below the answer it cites, so the
     * answer is usually off-screen above and the toast was the teacher's only
     * evidence anything had happened. The first fix derived the scroll from
     * HIGHLIGHT STATE — which also changes on hover and on keyboard focus — so
     * the page jumped whenever the mouse crossed a criterion. It is now
     * commanded by the click, and only by the click.
     */
    test('quote-button-scrolls-to-its-own-answer: the click brings the answer into view', async ({ page }) => {
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);

        const quoteButton = page.getByRole('button', { name: /ציטוט רלוונטי מהתשובה/ }).first();
        await quoteButton.scrollIntoViewIfNeeded();

        // Park the viewport well below the first answer, the way a teacher
        // reading the checklist has it.
        await page.mouse.wheel(0, 1200);
        await page.waitForTimeout(300);

        const answer = page.locator('[data-answer-for]').first();
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
        await expect(page.getByText(/מנוקד עכשיו, עוד כ-2 דקות/)).toBeVisible();
    });
