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
