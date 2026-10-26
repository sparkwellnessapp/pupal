import { readFileSync } from 'node:fs';
import path from 'node:path';
import { expect, test, type Page } from '@playwright/test';

import { BATCH_ID, TEST_A, installGradeReviewMocks } from './gradeReviewFixtures';

/**
 * grader-v6 review (owner rulings 2026-10-17 §7), driven in a real browser.
 *
 * Route-mocked like every grade-review spec: the batch, rubric and auth come
 * from `installGradeReviewMocks`; the v6 endpoints are served from the CAPTURED
 * server responses in `src/mocks/grade_review/v6_review_hobby.json` (the v6
 * grader on the scripted fake model, priced and reviewed by the server's own
 * code — see `src/mocks/grade_review/v6Fixture.ts`). Routes registered here
 * run before the shared ones (Playwright: last registered, first matched).
 */

const RAW = JSON.parse(readFileSync(
    path.resolve(__dirname, '../src/mocks/grade_review/v6_review_hobby.json'), 'utf-8'));
const BASE = RAW.base;
const DRAFT = { ...RAW.graded_test.draft, v6: BASE.content };
const FLIP = { ...BASE, ...RAW.flip.response };
const FLIP_CHECK: string = RAW.flip.check_id;            // q2.א.c1.c2
const FLIP_OPTION: string = RAW.flip.option_id;          // its middle choice
const FLIP_TERMINAL: string = BASE.content.checks
    .find((c: { plan: { check_id: string } }) => c.plan.check_id === FLIP_CHECK).plan.priced_terminal_id;
const FLIP_LINE: string = FLIP.lines
    .find((l: { terminal_id: string }) => l.terminal_id === FLIP_TERMINAL).text_he;
const BASE_LINE: string = BASE.lines
    .find((l: { terminal_id: string }) => l.terminal_id === FLIP_TERMINAL).text_he;

const REVIEW = `/batches/${BATCH_ID}/grade-review/${TEST_A}`;
const json = (body: unknown) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });

/** The display form `formatPoints` gives a decimal string. */
const shown = (value: string) => value.replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '');

async function installV6(page: Page, opts: { approved?: boolean } = {}) {
    await installGradeReviewMocks(page, { draftOverride: DRAFT });
    if (opts.approved) {
        await page.route(`**/api/v0/grading/graded_test/${TEST_A}`, (route) => route.fulfill(json({
            id: TEST_A, status: 'approved', student_name: 'נועה לוי', transcription_id: 't-a',
            numeric_policy: RAW.graded_test.numeric_policy, total_possible: '100',
            draft: DRAFT, contract: {}, approved_at: '2026-10-17T18:00:00Z',
        })));
    }
    await page.route('**/api/v0/grading/graded_test/*/v6', (route) => route.fulfill(
        json(opts.approved ? { ...BASE, status: 'approved' } : BASE)));
}

test.describe('בדיקת ציונים — a grader-v6 grade', () => {
    test('open → flip a choice → the grade moves → «ההסבר מתעדכן…» → the saved line → approve', async ({ page }) => {
        await installV6(page);

        let releasePatch!: () => void;
        const patchHeld = new Promise<void>((resolve) => { releasePatch = resolve; });
        const patches: unknown[] = [];
        await page.route('**/api/v0/grading/graded_test/*/v6/draft', async (route) => {
            patches.push(route.request().postDataJSON());
            await patchHeld;                          // hold the response: the line must read «מתעדכן»
            await route.fulfill(json(FLIP));
        });
        let approveBody: unknown = null;
        await page.route('**/api/v0/grading/graded_test/*/approve', async (route) => {
            approveBody = route.request().postDataJSON();
            await route.fulfill(json({
                id: TEST_A, status: 'approved', student_name: 'נועה לוי', transcription_id: 't-a',
                draft: DRAFT, contract: {}, approved_at: '2026-10-17T18:00:00Z',
            }));
        });

        await page.goto(REVIEW);
        await expect(page.locator('[data-review-surface="v6"]')).toBeVisible();
        const total = page.locator('[data-total]');
        await expect(total).toHaveText(shown(BASE.priced.total_score));
        await expect(total).toHaveAttribute('data-overridden', 'false');

        await page.screenshot({ path: test.info().outputPath('v6-landed.png'), fullPage: true });

        const row = page.locator(`[data-v6-criterion="${FLIP_TERMINAL}"]`);
        await expect(row.locator('[data-reasoning-line]')).toHaveText(BASE_LINE);
        await row.locator(`[data-v6-toggle="${FLIP_TERMINAL}"]`).click();

        const check = row.locator(`[data-v6-check="${FLIP_CHECK}"]`);
        await expect(check.locator('[data-vivi="true"]')).toHaveCount(1);
        await check.locator(`[data-option="${FLIP_OPTION}"]`).click();

        // The grade moves at once — the TS pricer, under her hand.
        await expect(total).toHaveText(shown(FLIP.priced.total_score));
        await expect(total).toHaveAttribute('data-overridden', 'true');
        await expect(check.locator(`[data-option="${FLIP_OPTION}"]`)).toHaveAttribute('data-hers', 'true');
        // …and the line says it is being rewritten, until the save lands.
        await expect(row.locator('[data-reasoning-line]')).toHaveAttribute('data-line-state', 'updating');
        await expect(row.locator('[data-reasoning-line]')).toHaveText('ההסבר מתעדכן…');

        // The debounced PATCH carries ONLY what she changed, with the client's total.
        await expect.poll(() => patches.length, { timeout: 10_000 }).toBe(1);
        expect(patches[0]).toEqual({
            v6: { checks: { [FLIP_CHECK]: { option_id: FLIP_OPTION, comment: null } } },
            feedback: {},
            client_total: FLIP.priced.total_score,
        });
        await expect(row.locator('[data-reasoning-line]')).toHaveAttribute('data-line-state', 'updating');

        releasePatch();
        await expect(row.locator('[data-reasoning-line]')).toHaveAttribute('data-line-state', 'ready');
        await expect(row.locator('[data-reasoning-line]')).toHaveText(FLIP_LINE);
        await expect(page.locator('[data-save-state]')).toHaveAttribute('data-save-state', 'saved');

        // Evidence for a human eye, kept in test-results (never committed: the
        // answer pane shows a benchmark student's real work).
        await page.screenshot({ path: test.info().outputPath('v6-after-flip.png'), fullPage: false });

        await page.getByRole('button', { name: /אישור וחתימה/ }).click();
        await expect.poll(() => approveBody, { timeout: 10_000 }).not.toBeNull();
        expect(approveBody).toEqual({ overrides: FLIP.overrides, client_total: FLIP.priced.total_score });
        await expect(page.getByText(/אושר ונחתם/).first()).toBeVisible();
    });

    test('a note for the student is written on a CLOSED criterion and saved on it', async ({ page }) => {
        await installV6(page);
        const NOTE = 'הבנת את הרעיון, אבל אין מספר כזה 01';
        const patches: unknown[] = [];
        await page.route('**/api/v0/grading/graded_test/*/v6/draft', async (route) => {
            patches.push(route.request().postDataJSON());
            await route.fulfill(json({
                ...BASE,
                overlay: { ...BASE.overlay, terminal_comments: { [FLIP_TERMINAL]: NOTE } },
            }));
        });
        await page.goto(REVIEW);
        const row = page.locator(`[data-v6-criterion="${FLIP_TERMINAL}"]`);
        await expect(row).toHaveAttribute('data-expanded', 'false');
        // every closed criterion offers it — no need to open one first
        await expect(page.locator('[data-comment-add]'))
            .toHaveCount(await page.locator('[data-v6-criterion]').count());

        await row.locator('[data-comment-add]').click();
        await row.locator('[data-comment-editor] textarea').fill(NOTE);
        await row.locator('[data-comment-save]').click();
        await expect(row.locator('[data-her-comment]')).toContainText(NOTE);
        await expect(row).toHaveAttribute('data-expanded', 'false');

        await expect.poll(() => patches.length, { timeout: 10_000 }).toBe(1);
        expect(patches[0]).toEqual({
            v6: { terminal_comments: { [FLIP_TERMINAL]: NOTE } },
            feedback: {},
            client_total: BASE.priced.total_score,
        });
        // a note moves no grade and rewrites no line
        await expect(page.locator('[data-total]')).toHaveAttribute('data-overridden', 'false');
        await expect(row.locator('[data-reasoning-line]')).toHaveText(BASE_LINE);
    });

    test('an approved v6 grade is read-only', async ({ page }) => {
        await installV6(page, { approved: true });
        let patched = false;
        await page.route('**/api/v0/grading/graded_test/*/v6/draft', (route) => {
            patched = true;
            return route.fulfill(json(BASE));
        });
        await page.goto(REVIEW);
        await expect(page.locator('[data-review-surface="v6"]')).toBeVisible();
        await page.locator(`[data-v6-toggle="${FLIP_TERMINAL}"]`).click();
        const radios = page.locator(`[data-v6-criterion="${FLIP_TERMINAL}"] [role="radio"]`);
        await expect(radios.first()).toBeDisabled();
        await expect(page.locator('[data-comment-add]')).toHaveCount(0);
        await expect(page.getByRole('button', { name: /אישור וחתימה/ })).toBeDisabled();
        await page.waitForTimeout(1_800);
        expect(patched).toBe(false);
    });
});

test.describe('בדיקת ציונים v6 — «ציטוט מהתשובה» (owner 2026-10-21)', () => {
    test('every criterion has the button; a click lights its quotes in the answer, a second click clears', async ({ page }) => {
        await installV6(page);
        await page.goto(REVIEW);
        const buttons = page.locator('[data-quote-button]');
        await expect(buttons.first()).toBeVisible();
        expect(await buttons.count()).toBe(await page.locator('[data-v6-toggle]').count());

        const first = page.locator('[data-quote-button]:not([disabled])').first();
        const section = page.locator('section', { has: first });
        await expect(section.locator('mark')).toHaveCount(0);
        await first.click();
        await expect(first).toHaveAttribute('aria-pressed', 'true');
        await expect(section.locator('[data-answer-pane] mark').first()).toBeVisible();
        if (process.env.QUOTE_SHOT) await page.screenshot({ path: process.env.QUOTE_SHOT });
        await first.click();
        await expect(section.locator('[data-answer-pane] mark')).toHaveCount(0);
    });
});

test.describe('בדיקת ציונים v6 — the student\'s feedback follows her decisions', () => {
    const SCOPE_OF = (tid: string): string => {
        const t = BASE.content.view_terminals.find((x: { terminal_id: string }) => x.terminal_id === tid);
        return t.sub_question_id ? `${t.question_id}.${t.sub_question_id}` : t.question_id;
    };
    const FLIP_SCOPE = SCOPE_OF(FLIP_TERMINAL);
    const COUNTED: string[] = [...new Set<string>(BASE.content.view_terminals
        .map((t: { terminal_id: string }) => SCOPE_OF(t.terminal_id)))];
    const block = (text: (scope: string) => string) => ({
        scopes: Object.fromEntries(COUNTED.map((s) => [s, { text: text(s), basis_hash: 'h' }])),
        summary: { text: 'סיכום', basis_hash: '' }, model_version: 'm', prompt_version: 'p',
    });
    const ORIGINAL = block((s) => `משוב מקורי ${s}`);
    const REWRITTEN = block((s) => (s === FLIP_SCOPE ? 'משוב חדש לפי ההחלטה שלך' : `משוב מקורי ${s}`));

    async function installStale(page: Page) {
        await installV6(page);
        const state = { rewrites: 0, approves: 0, rewritten: false };
        await page.route('**/api/v0/grading/graded_test/*/v6', (route) => route.fulfill(json({
            ...BASE,
            feedback: state.rewritten ? REWRITTEN : ORIGINAL,
            stale_feedback_scope_ids: [],
        })));
        await page.route('**/api/v0/grading/graded_test/*/v6/draft', (route) => route.fulfill(json({
            ...FLIP, feedback: ORIGINAL, stale_feedback_scope_ids: [FLIP_SCOPE],
        })));
        await page.route('**/api/v0/grading/graded_test/*/feedback/regenerate*', (route) => {
            state.rewrites += 1;
            state.rewritten = true;
            return route.fulfill(json({
                target: FLIP_SCOPE, text: 'משוב חדש לפי ההחלטה שלך', offered_only: false, stale: false,
            }));
        });
        await page.route('**/api/v0/grading/graded_test/*/approve', (route) => {
            state.approves += 1;
            return route.fulfill(json({
                id: TEST_A, status: 'approved', student_name: 'נועה לוי', transcription_id: 't-a',
                draft: DRAFT, contract: {}, approved_at: '2026-10-17T18:00:00Z',
            }));
        });
        return state;
    }

    async function flip(page: Page) {
        const row = page.locator(`[data-v6-criterion="${FLIP_TERMINAL}"]`);
        await row.locator(`[data-v6-toggle="${FLIP_TERMINAL}"]`).click();
        await row.locator(`[data-v6-check="${FLIP_CHECK}"] [data-option="${FLIP_OPTION}"]`).click();
    }

    test('a decision makes its question\'s feedback stale, and Vivi rewrites it on her own', async ({ page }) => {
        const state = await installStale(page);
        await page.goto(REVIEW);
        const card = page.locator(`[data-scope-id="${FLIP_SCOPE}"] [data-feedback-state]`);
        await expect(card).toHaveAttribute('data-feedback-state', 'fresh');
        await flip(page);
        await expect(card).toHaveAttribute('data-feedback-state', 'stale');
        await card.screenshot({ path: test.info().outputPath('feedback-stale.png') });
        // after the quiet period, with nothing pressed
        await expect(card.locator('textarea')).toHaveValue('משוב חדש לפי ההחלטה שלך', { timeout: 20_000 });
        await expect(card).toHaveAttribute('data-feedback-state', 'fresh');
        expect(state.rewrites).toBe(1);
        // every other question kept the text she had read
        const other = COUNTED.find((s) => s !== FLIP_SCOPE);
        if (other) {
            await expect(page.locator(`[data-scope-id="${other}"] [data-feedback-state] textarea`))
                .toHaveValue(`משוב מקורי ${other}`);
        }
    });

    test('pressing approve over stale feedback updates it for her to read — the next press signs', async ({ page }) => {
        const state = await installStale(page);
        await page.goto(REVIEW);
        await flip(page);
        await page.getByRole('button', { name: /אישור וחתימה/ }).click();   // inside the quiet period
        await expect(page.getByText('ויוי עדכנה את המשוב לפי השינויים שלך — עברי עליו ואשרי שוב'))
            .toBeVisible();
        expect(state.rewrites).toBe(1);
        expect(state.approves).toBe(0);
        await expect(page.locator(`[data-scope-id="${FLIP_SCOPE}"] [data-feedback-state] textarea`))
            .toHaveValue('משוב חדש לפי ההחלטה שלך');
        await page.getByRole('button', { name: /אישור וחתימה/ }).click();
        await expect.poll(() => state.approves, { timeout: 10_000 }).toBe(1);
    });

    test('with no feedback written, every question still has a box — write it, or ask again', async ({ page }) => {
        await installV6(page);
        const patches: { feedback?: Record<string, string> }[] = [];
        await page.route('**/api/v0/grading/graded_test/*/v6/draft', async (route) => {
            patches.push(route.request().postDataJSON());
            await route.fulfill(json(BASE));
        });
        await page.goto(REVIEW);
        const absent = page.locator('[data-feedback-state="absent"]');
        // one per counted question, plus the summary
        await expect(absent).toHaveCount(COUNTED.length + 1);
        await expect(page.locator('[data-review-notice]')).toHaveText(`${COUNTED.length} שאלות בלי משוב`);

        const card = page.locator(`[data-scope-id="${FLIP_SCOPE}"] [data-feedback-state]`);
        await expect(card.locator('[data-feedback-retry]')).toBeVisible();
        await card.screenshot({ path: test.info().outputPath('feedback-absent.png') });
        await page.locator('[data-review-actionbar]').screenshot({ path: test.info().outputPath('feedback-bar.png') });
        await card.locator('[data-feedback-write]').click();
        await expect(card).toHaveAttribute('data-feedback-state', 'blank');
        await expect(card.locator('textarea')).toBeFocused();
        await page.keyboard.type('עבודה טובה');
        await expect(card).toHaveAttribute('data-feedback-state', 'fresh');
        await expect.poll(() => patches.at(-1)?.feedback?.[FLIP_SCOPE], { timeout: 10_000 })
            .toBe('עבודה טובה');
        // emptying it again keeps the box: «no feedback» is her choice, not a vanished card
        await card.locator('textarea').fill('');
        await expect(card).toHaveAttribute('data-feedback-state', 'blank');
        await expect(card.locator('[data-feedback-ask]')).toBeVisible();
        await card.screenshot({ path: test.info().outputPath('feedback-blank.png') });
    });
});
