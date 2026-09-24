import { expect, test, type Page } from '@playwright/test';

import { BATCH_ID, TEST_A, installGradeReviewMocks } from './gradeReviewFixtures';

/**
 * THE SIDE-BY-SIDE LAYOUT — LAY-1..5, driven in a real browser.
 *
 * The vitest suites close the pure half (the highlight machine's table, the
 * reveal arithmetic) and SSR-render the card's anatomy. None of them can see a
 * pane that fails to pin, a criterion left without its answer, or a box that
 * moves when the pointer rests on a row — which is the whole claim this PR
 * makes. That is what this file is for.
 *
 * §8.3 asks for evidence at five widths. 2560 and 1440 exercise the M-9 cap and
 * the ordinary desktop; 1280 is the suite's default and the one every other
 * grade-review spec runs at; 1180 and 1179 are the breakpoint's two sides.
 */

const REVIEW = `/batches/${BATCH_ID}/grade-review/${TEST_A}`;
const ART = 'e2e/review-artifacts/side-by-side';

async function openAllBreakdowns(page: Page) {
    await page.locator('[data-breakdown-for]').first().waitFor();
    const ids: string[] = await page.locator('[data-breakdown-for]').evaluateAll(
        (els) => els
            .filter((el) => el.getAttribute('aria-expanded') === 'false')
            .map((el) => el.getAttribute('data-breakdown-for') as string));
    for (const id of ids) await page.locator(`[data-breakdown-for="${id}"]`).click();
}

/** The band a teacher can actually read: between the top bar and the action bar. */
async function readableBand(page: Page): Promise<{ top: number; bottom: number }> {
    return page.evaluate(() => {
        const bar = document.querySelector('[data-review-topbar]');
        const action = document.querySelector('[data-review-actionbar]');
        return {
            top: bar ? bar.getBoundingClientRect().bottom : 0,
            bottom: action ? action.getBoundingClientRect().top : window.innerHeight,
        };
    });
}

for (const width of [2560, 1440, 1280, 1180]) {
    test(`LAY-1 at ${width}px: every criterion row is read beside its own answer`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await openAllBreakdowns(page);

        const band = await readableBand(page);

        // Walk the page in viewport-sized steps and check the invariant at each
        // rest: for EVERY criterion row inside the band, that scope's pane is
        // inside the band too. One counter-example anywhere is a failure.
        const height = await page.evaluate(() => document.body.scrollHeight);
        for (let y = 0; y < height; y += 500) {
            await page.evaluate((to) => window.scrollTo(0, to), y);
            await page.waitForTimeout(120);

            const violations = await page.evaluate((b) => {
                const bad: string[] = [];
                for (const section of Array.from(
                    document.querySelectorAll<HTMLElement>('[data-scope-id]'))) {
                    const scopeId = section.dataset.scopeId!;
                    const pane = section.querySelector<HTMLElement>('[data-answer-pane]');
                    if (!pane) continue;
                    const rows = Array.from(
                        section.querySelectorAll<HTMLElement>('[data-check-id]'));
                    const rowInBand = rows.some((row) => {
                        const r = row.getBoundingClientRect();
                        return r.bottom > b.top && r.top < b.bottom;
                    });
                    if (!rowInBand) continue;
                    const p = pane.getBoundingClientRect();
                    // The pane must be present in the band. It may be partly
                    // clipped at the moment a card hands over to the next one
                    // (LAY-2 allows that overlap); it may not be absent.
                    const visible = Math.min(p.bottom, b.bottom) - Math.max(p.top, b.top);
                    if (visible < 40) bad.push(`${scopeId} pane visible ${Math.round(visible)}px`);
                }
                return bad;
            }, band);

            expect(violations, `at scrollY≈${y}`).toEqual([]);
        }

        await page.screenshot({ path: `${ART}/lay1-${width}.png` });
    });
}

test('LAY-2 + LAY-4: a pane never leaves its own card, and never hides under the bar',
    async ({ page }) => {
        await page.setViewportSize({ width: 1440, height: 900 });
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await openAllBreakdowns(page);

        const height = await page.evaluate(() => document.body.scrollHeight);
        for (let y = 0; y < height; y += 400) {
            await page.evaluate((to) => window.scrollTo(0, to), y);
            await page.waitForTimeout(100);

            const problems = await page.evaluate(() => {
                const bad: string[] = [];
                const bar = document.querySelector('[data-review-topbar]');
                const action = document.querySelector('[data-review-actionbar]');
                const ceiling = bar ? bar.getBoundingClientRect().bottom : 0;
                const floor = action
                    ? action.getBoundingClientRect().top : window.innerHeight;
                for (const section of Array.from(
                    document.querySelectorAll<HTMLElement>('[data-scope-id]'))) {
                    const pane = section.querySelector<HTMLElement>('[data-answer-pane]');
                    if (!pane) continue;
                    const p = pane.getBoundingClientRect();
                    const s = section.getBoundingClientRect();
                    // LAY-2 — containment is structural: the pane is a DOM child
                    // of its card, and sticky cannot carry it past the card's
                    // own edges. Asserted with a pixel of slack for rounding.
                    if (p.top < s.top - 1 || p.bottom > s.bottom + 1) {
                        bad.push(`${section.dataset.scopeId} pane escaped its card`);
                    }
                    // LAY-4, stated where it is actually decided: the CAP. A
                    // pane that is merely below the fold extends past the action
                    // bar because the whole page does, and measuring that would
                    // be measuring the scroll position rather than the layout.
                    // What must hold everywhere is that the pane can never be
                    // TALLER than the band it pins into — from which "a fully
                    // scrolled pane's last line is never under the bar" follows
                    // for every pinned pane, at every scroll offset.
                    if (p.height > (floor - ceiling) + 1) {
                        bad.push(`${section.dataset.scopeId} pane is taller than the band`);
                    }
                    // …and a pane that IS pinned (its top is sitting at the
                    // sticky offset) must end above the bar.
                    const pinned = p.top > ceiling - 1 && p.top < ceiling + 80 && s.top < p.top;
                    if (pinned && p.bottom > floor + 1) {
                        bad.push(`${section.dataset.scopeId} pinned pane runs under the bar`);
                    }
                }
                return bad;
            });

            expect(problems, `at scrollY≈${y}`).toEqual([]);
        }
    });

test('LAY-3 + RTL at 1180: criteria at the inline-start, answer at the left', async ({ page }) => {
    await page.setViewportSize({ width: 1180, height: 900 });
    await installGradeReviewMocks(page);
    await page.goto(REVIEW);
    await page.locator('[data-answer-pane]').first().waitFor();

    const geometry = await page.evaluate(() => {
        const section = document.querySelector<HTMLElement>('[data-scope-id]')!;
        const pane = section.querySelector<HTMLElement>('[data-answer-pane]')!;
        const criteria = section.querySelector<HTMLElement>('.gr-card__criteria')!;
        return {
            pane: pane.getBoundingClientRect().x,
            criteria: criteria.getBoundingClientRect().x,
            sameRow: Math.abs(pane.getBoundingClientRect().y
                - criteria.getBoundingClientRect().y) < 60,
        };
    });

    // RTL: the criteria column is column 1 (inline-start = the RIGHT edge),
    // the answer is at the left — Noam's ruling, stated as coordinates.
    expect(geometry.sameRow).toBe(true);
    expect(geometry.pane).toBeLessThan(geometry.criteria);

    await page.screenshot({ path: `${ART}/two-col-1180.png`, fullPage: false });
});

test('LAY-3 at 1179: the SAME grid reflows to one column, answer above criteria',
    async ({ page }) => {
        await page.setViewportSize({ width: 1179, height: 900 });
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await page.locator('[data-answer-pane]').first().waitFor();

        const geometry = await page.evaluate(() => {
            const section = document.querySelector<HTMLElement>('[data-scope-id]')!;
            const pane = section.querySelector<HTMLElement>('[data-answer-pane]')!;
            const criteria = section.querySelector<HTMLElement>('.gr-card__criteria')!;
            return {
                paneY: pane.getBoundingClientRect().y,
                criteriaY: criteria.getBoundingClientRect().y,
                paneSticky: getComputedStyle(pane).position,
                bodyOverflow: getComputedStyle(
                    section.querySelector<HTMLElement>('[data-answer-for]')!).overflowY,
            };
        });

        expect(geometry.paneY).toBeLessThan(geometry.criteriaY);
        // M-5 — sticky at full viewport height in one column would hide the
        // criteria entirely, so the pane goes static and keeps today's cap.
        expect(geometry.paneSticky).toBe('static');
        expect(geometry.bodyOverflow).toBe('auto');

        await page.screenshot({ path: `${ART}/one-col-1179.png`, fullPage: false });
    });

test('LAY-5: hovering shifts no box on the page', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await installGradeReviewMocks(page);
    await page.goto(REVIEW);
    await openAllBreakdowns(page);

    const geometryOf = () => page.evaluate(() => Array.from(
        document.querySelectorAll<HTMLElement>('[data-check-id], [data-terminal-id]'))
        .map((el) => {
            const r = el.getBoundingClientRect();
            return `${Math.round(r.x)},${Math.round(r.y)},${Math.round(r.width)},${Math.round(r.height)}`;
        }));

    const row = page.locator(
        '[data-check-id]:has(button:has-text("ציטוט רלוונטי מהתשובה"))').first();
    await row.scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);
    const before = await geometryOf();

    const box = await row.boundingBox();
    expect(box).not.toBeNull();
    await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
    await expect(page.locator('mark').first()).toBeVisible();

    // Same boxes, to the pixel. A highlight that reflowed the list would move
    // the very row she is reading out from under her pointer.
    expect(await geometryOf()).toEqual(before);
});

test('HL-3: a hover reveal scrolls the PANE and nothing else', async ({ page }) => {
    // A SHORT viewport on purpose. At 900px tall the band is ~690px and every
    // answer in the cohort fits inside it, so the reveal has nothing to do and
    // the interesting half of HL-3 is never exercised. 560px forces the pane
    // body to scroll, which is the case the invariant is about.
    await page.setViewportSize({ width: 1440, height: 560 });
    await installGradeReviewMocks(page);
    await page.goto(REVIEW);
    await openAllBreakdowns(page);

    // A scope whose answer is long enough to have somewhere to scroll TO, and
    // whose last quoted row is far enough down it that M-2 will not skip.
    const scopeId = await page.evaluate(() => {
        for (const section of Array.from(
            document.querySelectorAll<HTMLElement>('[data-scope-id]'))) {
            const body = section.querySelector<HTMLElement>('[data-answer-for]');
            const row = section.querySelector('[data-check-id] button');
            if (body && row && body.scrollHeight > body.clientHeight + 60) {
                return section.dataset.scopeId!;
            }
        }
        return null;
    });
    expect(scopeId, 'no scope in this fixture has a scrollable answer').not.toBeNull();

    const pageBefore = await page.evaluate(() => window.scrollY);
    const row = page.locator(
        `[data-scope-id="${scopeId}"] [data-check-id]:has(button:has-text("ציטוט רלוונטי מהתשובה"))`,
    ).last();
    await row.scrollIntoViewIfNeeded();
    const box = await row.boundingBox();
    expect(box).not.toBeNull();

    const settled = await page.evaluate(() => window.scrollY);
    await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
    await expect(page.locator('mark').first()).toBeVisible();
    await page.waitForTimeout(700);                       // the pane's smooth scroll

    // The page has not moved a pixel because of the hover…
    expect(await page.evaluate(() => window.scrollY)).toBe(settled);
    expect(typeof pageBefore).toBe('number');
    // …and the mark is inside its pane's visible box, which is what "revealed"
    // means. Whether the pane had to scroll at all is M-2's business.
    const inView = await page.evaluate((id) => {
        const body = document.querySelector<HTMLElement>(`[data-answer-for="${id}"]`)!;
        const mark = body.querySelector('mark');
        if (!mark) return null;
        const b = body.getBoundingClientRect();
        const m = mark.getBoundingClientRect();
        return m.top >= b.top - 1 && m.bottom <= b.bottom + 1;
    }, scopeId);
    expect(inView).toBe(true);
});

test('§5.4: the bar heights are MEASURED, not assumed', async ({ page }) => {
    // The sticky chain is arithmetic on three numbers. Two of them are not
    // constants — a revision menu or a two-line identity moves the top bar —
    // so they are observed. The defaults in `globals.css` exist only so the
    // first paint and SSR are not laid out against zero; if the observer ever
    // stopped running, the layout would go subtly wrong in a way no invariant
    // above would name. This is the one assertion that names it.
    await page.setViewportSize({ width: 1440, height: 900 });
    await installGradeReviewMocks(page);
    await page.goto(REVIEW);
    await page.locator('[data-answer-pane]').first().waitFor();

    const measured = await page.evaluate(() => {
        const root = document.querySelector<HTMLElement>('.gr-review')!;
        const px = (name: string) => parseFloat(root.style.getPropertyValue(name));
        const real = (attr: string) =>
            document.querySelector<HTMLElement>(`[${attr}]`)!.offsetHeight;
        return {
            topbar: px('--gr-topbar-h'),
            actionbar: px('--gr-actionbar-h'),
            realTopbar: real('data-review-topbar'),
            realActionbar: real('data-review-actionbar'),
        };
    });

    // Written as INLINE style by the observer — i.e. it ran — and equal to what
    // the bars actually measure.
    expect(measured.topbar).toBe(Math.round(measured.realTopbar));
    expect(measured.actionbar).toBe(Math.round(measured.realActionbar));
});

test('M-10: the kill switch holds the card at one column above the breakpoint',
    async ({ page }) => {
        // `NEXT_PUBLIC_REVIEW_LAYOUT=stacked` is a BUILD-time inline, so the
        // flag→attribute half is one typechecked line. What could actually be
        // wrong is the CSS, and that is what this drives: set the attribute the
        // flag sets, at a width where two columns would otherwise apply.
        await page.setViewportSize({ width: 1440, height: 900 });
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await page.locator('[data-answer-pane]').first().waitFor();

        const before = await page.evaluate(() => {
            const section = document.querySelector<HTMLElement>('[data-scope-id]')!;
            const pane = section.querySelector<HTMLElement>('[data-answer-pane]')!;
            return getComputedStyle(pane).position;
        });
        expect(before).toBe('sticky');

        const after = await page.evaluate(() => {
            document.querySelector('.gr-review')!
                .setAttribute('data-review-layout', 'stacked');
            const section = document.querySelector<HTMLElement>('[data-scope-id]')!;
            const pane = section.querySelector<HTMLElement>('[data-answer-pane]')!;
            const criteria = section.querySelector<HTMLElement>('.gr-card__criteria')!;
            return {
                position: getComputedStyle(pane).position,
                paneY: pane.getBoundingClientRect().y,
                criteriaY: criteria.getBoundingClientRect().y,
            };
        });
        expect(after.position).toBe('static');
        expect(after.paneY).toBeLessThan(after.criteriaY);
    });

test('OD-3: the strip pins under the top bar and is pushed out by its own card',
    async ({ page }) => {
        // The trap this guards: a sticky GRID ITEM is confined to its grid area,
        // so the first version of this strip — a `strip strip` row of its own
        // height — had zero travel and never pinned. It looked correct in the
        // stylesheet and was wrong on the screen, which is the only kind of
        // sticky bug worth a browser test.
        await page.setViewportSize({ width: 1440, height: 900 });
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await openAllBreakdowns(page);

        const first = page.locator('[data-scope-id]').first();
        const scopeId = await first.getAttribute('data-scope-id');

        // Scroll well into the first card — past where its header would be if it
        // did not stick.
        await page.evaluate((id) => {
            const section = document.querySelector<HTMLElement>(`[data-scope-id="${id}"]`)!;
            window.scrollTo(0, section.offsetTop + 400);
        }, scopeId);
        await page.waitForTimeout(150);

        const pinned = await page.evaluate((id) => {
            const section = document.querySelector<HTMLElement>(`[data-scope-id="${id}"]`)!;
            const strip = section.querySelector<HTMLElement>('.gr-card__strip')!;
            const bar = document.querySelector('[data-review-topbar]')!.getBoundingClientRect();
            const s = strip.getBoundingClientRect();
            const sec = section.getBoundingClientRect();
            return {
                atTheBar: Math.abs(s.top - bar.bottom) < 2,
                belowItsOwnNaturalPlace: s.top > sec.top + 2,
                // Opaque, or the criteria would show through it as they pass.
                opaque: getComputedStyle(strip).backgroundColor,
                // Full-bleed across the card's padding: nothing shows at its sides.
                bleeds: s.width >= sec.width - 2,
            };
        }, scopeId);

        expect(pinned.atTheBar).toBe(true);
        expect(pinned.belowItsOwnNaturalPlace).toBe(true);
        expect(pinned.opaque).not.toMatch(/rgba\([^)]*,\s*0\)/);
        expect(pinned.bleeds).toBe(true);

        // …and it leaves with its card, rather than riding down the page.
        await page.evaluate((id) => {
            const section = document.querySelector<HTMLElement>(`[data-scope-id="${id}"]`)!;
            window.scrollTo(0, section.offsetTop + section.offsetHeight + 200);
        }, scopeId);
        await page.waitForTimeout(150);

        const gone = await page.evaluate((id) => {
            const strip = document.querySelector<HTMLElement>(
                `[data-scope-id="${id}"] .gr-card__strip`)!;
            const bar = document.querySelector('[data-review-topbar]')!.getBoundingClientRect();
            return strip.getBoundingClientRect().top < bar.bottom - 2;
        }, scopeId);
        expect(gone).toBe(true);
    });

test('OD-11: ↓ across a scope boundary reveals in the NEW pane and leaves the old one',
    async ({ page }) => {
        await page.setViewportSize({ width: 1440, height: 900 });
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await openAllBreakdowns(page);

        // Walk to the last check of the first scope.
        const firstScope = (await page.locator('[data-scope-id]').first()
            .getAttribute('data-scope-id'))!;
        const lastOfFirst = await page.locator(
            `[data-scope-id="${firstScope}"] [data-check-id]`).last().getAttribute('data-check-id');

        await page.evaluate((id) => {
            document.querySelector<HTMLElement>(`[data-check-id="${id}"]`)!.click();
        }, lastOfFirst);
        await expect(page.locator(`[data-check-id="${lastOfFirst}"][data-focused="true"]`))
            .toHaveCount(1);

        // THE PRECONDITION, made certain: park the row ↓ will select HALF UNDER
        // the action bar. Left to chance the row often already fit, and the
        // test passed without the page ever having to move — which is how a
        // `rounded overflow-hidden` criterion box that swallowed
        // `scrollIntoView` shipped (found against production, 2026-09-23).
        await page.evaluate((scope) => {
            const next = Array.from(document.querySelectorAll<HTMLElement>('[data-check-id]'))
                .find((el) => el.closest('[data-scope-id]')!.getAttribute('data-scope-id') !== scope)!;
            const action = document.querySelector('[data-review-actionbar]')!.getBoundingClientRect();
            const r = next.getBoundingClientRect();
            window.scrollBy(0, r.top + r.height / 2 - action.top);
        }, firstScope);
        const parked = await page.evaluate((scope) => {
            const next = Array.from(document.querySelectorAll<HTMLElement>('[data-check-id]'))
                .find((el) => el.closest('[data-scope-id]')!.getAttribute('data-scope-id') !== scope)!;
            const action = document.querySelector('[data-review-actionbar]')!.getBoundingClientRect();
            return next.getBoundingClientRect().bottom > action.top + 1;
        }, firstScope);
        expect(parked).toBe(true);

        const before = await page.evaluate((id) => {
            const body = document.querySelector<HTMLElement>(`[data-answer-for="${id}"]`);
            return body ? body.scrollTop : 0;
        }, firstScope);

        await page.keyboard.press('ArrowDown');

        // The caret crossed into the next scope…
        const landedIn = await page.evaluate(() => document
            .querySelector<HTMLElement>('[data-check-id][data-focused="true"]')!
            .closest('[data-scope-id]')!.getAttribute('data-scope-id'));
        expect(landedIn).not.toBe(firstScope);

        // …its row is clear of the strip above and the action bar below (the
        // `gr-row-scroll` margins doing their job)…
        const clear = await page.evaluate(() => {
            const row = document.querySelector<HTMLElement>(
                '[data-check-id][data-focused="true"]')!.getBoundingClientRect();
            const bar = document.querySelector('[data-review-topbar]')!.getBoundingClientRect();
            const action = document.querySelector(
                '[data-review-actionbar]')!.getBoundingClientRect();
            return row.top >= bar.bottom - 1 && row.bottom <= action.top + 1;
        });
        expect(clear).toBe(true);

        // …and the PREVIOUS scope's pane was left exactly where she left it.
        await page.waitForTimeout(600);
        const after = await page.evaluate((id) => {
            const body = document.querySelector<HTMLElement>(`[data-answer-for="${id}"]`);
            return body ? body.scrollTop : 0;
        }, firstScope);
        expect(after).toBe(before);
    });

test('a clamped ↑ at the first row moves neither the page nor the pane', async ({ page }) => {
    // The walk is clamped at both ends. Before the requests existed that was
    // free — `setFocus` to the same id commits nothing — but a KEY_NAV would
    // bump `seq` and re-run both scrollers on a row she is already sitting on,
    // re-scrolling a pane she may have moved by hand.
    // A SHORT viewport, so the pane's cap is well under every answer and the
    // pane is genuinely scrollable — otherwise a spurious reveal has nothing to
    // undo and this test would pass whether the guard exists or not.
    await page.setViewportSize({ width: 1440, height: 420 });
    await installGradeReviewMocks(page);
    await page.goto(REVIEW);
    await openAllBreakdowns(page);

    // The FIRST row, and ↑ — the same clamp as ↓ at the last row, but the first
    // row is one that actually CITES something, so a spurious reveal has a
    // quotation to drag back into view. (The cohort's last row has no quote, so
    // the ↓ end of the same clamp is unobservable and would not test the guard.)
    const lastId = await page.locator(
        '[data-check-id]:has(button:has-text("ציטוט רלוונטי מהתשובה"))')
        .first().getAttribute('data-check-id');
    expect(await page.locator('[data-check-id]').first().getAttribute('data-check-id'))
        .toBe(lastId);
    await page.evaluate((id) => {
        document.querySelector<HTMLElement>(`[data-check-id="${id}"]`)!.click();
    }, lastId);
    await expect(page.locator(`[data-check-id="${lastId}"][data-focused="true"]`))
        .toHaveCount(1);
    await page.waitForTimeout(700);

    // Scroll that pane to its FAR END by hand — the thing a spurious reveal
    // would undo by dragging the quotation back into view.
    const scopeId = await page.evaluate((id) => document
        .querySelector<HTMLElement>(`[data-check-id="${id}"]`)!
        .closest('[data-scope-id]')!.getAttribute('data-scope-id')!, lastId);
    const room = await page.evaluate((s) => {
        const body = document.querySelector<HTMLElement>(`[data-answer-for="${s}"]`);
        if (!body) return 0;
        body.scrollTop = body.scrollHeight - body.clientHeight;
        return body.scrollTop;
    }, scopeId);
    // If the pane cannot scroll there is nothing to protect, and a test that
    // cannot fail is worse than no test.
    expect(room, 'the pane must be scrollable for this to mean anything')
        .toBeGreaterThan(20);

    const before = await page.evaluate((s) => ({
        page: window.scrollY,
        pane: document.querySelector<HTMLElement>(`[data-answer-for="${s}"]`)?.scrollTop ?? 0,
    }), scopeId);

    await page.keyboard.press('ArrowUp');
    await page.waitForTimeout(700);

    expect(await page.evaluate((s) => ({
        page: window.scrollY,
        pane: document.querySelector<HTMLElement>(`[data-answer-for="${s}"]`)?.scrollTop ?? 0,
    }), scopeId)).toEqual(before);
});

test('an unmeasurable bar keeps the stylesheet default rather than writing 0',
    async ({ page }) => {
        // Below `desk` the whole module is `display: none`, so every bar reports
        // a height of 0. Writing that would collapse the sticky chain and leave
        // it collapsed until some later resize happened to repair it.
        await page.setViewportSize({ width: 390, height: 844 });
        await installGradeReviewMocks(page);
        await page.goto(REVIEW);
        await page.getByText(/דורשת מסך רחב/).waitFor();

        const vars = await page.evaluate(() => {
            const root = document.querySelector<HTMLElement>('.gr-review');
            if (!root) return null;
            return {
                inline: root.style.getPropertyValue('--gr-topbar-h'),
                resolved: getComputedStyle(root).getPropertyValue('--gr-topbar-h').trim(),
            };
        });
        if (vars) {
            expect(vars.inline).toBe('');          // nothing was written
            expect(vars.resolved).not.toBe('0px'); // …so the default still stands
        }
    });

test('the one-column band keeps hover and selection working', async ({ page }) => {
    // §1.5's honest degradation: below the breakpoint the guarantee she loses is
    // CO-VISIBILITY, and only that. The evidence machinery is layout-agnostic —
    // it is state, not CSS — and this is what says so.
    await page.setViewportSize({ width: 1100, height: 800 });
    await installGradeReviewMocks(page);
    await page.goto(REVIEW);
    await openAllBreakdowns(page);

    const row = page.locator(
        '[data-check-id]:has(button:has-text("ציטוט רלוונטי מהתשובה"))').first();
    await row.scrollIntoViewIfNeeded();
    const box = await row.boundingBox();
    expect(box).not.toBeNull();

    // Hover: transient, and it writes no selection (HL-2).
    await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
    await expect(page.locator('mark').first()).toBeVisible();
    await expect(page.locator('mark[data-pinned="true"]')).toHaveCount(0);

    // Leaving reverts to the selection — nothing, here (M-1).
    await page.mouse.move(0, 0);
    await expect(page.locator('mark')).toHaveCount(0);

    // And the button still selects.
    await row.locator('button:has-text("ציטוט רלוונטי מהתשובה")').click();
    await page.mouse.move(0, 0);
    await expect(page.locator('mark[data-pinned="true"]').first()).toBeVisible();
});
