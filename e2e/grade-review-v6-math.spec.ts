import { readFileSync } from 'node:fs';
import path from 'node:path';
import { expect, test } from '@playwright/test';

import { BATCH_ID, RUBRIC, TEST_A, installGradeReviewMocks } from './gradeReviewFixtures';

/**
 * «ציטוט מהתשובה» on a MATH answer (QM-1, 2026-10-29) — the case the audit found broken.
 *
 * The answer is LaTeX (production transcribes math with `TRANSCRIPTION_P1_VARIANT=latex1`),
 * and the verifier's quote is a BARE FRAGMENT of one formula — `f'(x)=4x` copied out of
 * `\(f'(x) = 4x\)`, without its delimiters and with other spacing. The server certifies it
 * in the math match form; the client used to place it with the plain rule, find nothing
 * exact, and paint an approximate window — a neighbouring formula. Asserted here: the mark
 * lands on THAT formula's line, typeset, and on no other.
 */

const RAW = JSON.parse(readFileSync(
    path.resolve(__dirname, '../src/mocks/grade_review/v6_review_hobby.json'), 'utf-8'));
const BASE = RAW.base;

const ANSWER = 'נגזור את הפונקציה:\n\\(f(x) = 2x^2 + 1\\)\n\\(f\'(x) = 4x\\)\nולכן השיפוע חיובי עבור \\(x > 0\\)';
const QUOTE = "f'(x)=4x";

const CHECK = BASE.content.checks.find(
    (c: { quote_status: string | null }) => c.quote_status === 'exact');
const TERMINAL: string = CHECK.plan.priced_terminal_id;
const SCOPE = BASE.content.view_terminals.find((t: { terminal_id: string }) => t.terminal_id === TERMINAL);

const content = {
    ...BASE.content,
    checks: BASE.content.checks.map((c: { plan: { priced_terminal_id: string }; quote_status: string | null }) =>
        (c === CHECK ? { ...c, evidence_quote: QUOTE, quote_status: 'exact' }
            : c.plan.priced_terminal_id === TERMINAL ? { ...c, evidence_quote: '', quote_status: null } : c)),
};
const DRAFT = {
    ...RAW.graded_test.draft,
    v6: content,
    scope_outcomes: RAW.graded_test.draft.scope_outcomes.map(
        (so: { question_id: string; sub_question_id: string | null }) =>
            (so.question_id === SCOPE.question_id && so.sub_question_id === SCOPE.sub_question_id
                ? { ...so, student_answer: { text: ANSWER } } : so)),
};
const json = (body: unknown) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });

test('a bare formula fragment lights its own formula, typeset, and nothing else', async ({ page }) => {
    await installGradeReviewMocks(page, { draftOverride: DRAFT });
    await page.route('**/api/v0/grading/graded_test/*/v6', (route) => route.fulfill(json({ ...BASE, content })));
    await page.route(/\/api\/v0\/rubrics\/[^/?]+(\?.*)?$/, (route) => route.fulfill(json({ ...RUBRIC, subject: 'mathematics' })));
    await page.goto(`/batches/${BATCH_ID}/grade-review/${TEST_A}`);

    const row = page.locator(`[data-v6-criterion="${TERMINAL}"]`);
    const section = page.locator('section', { has: row });
    const pane = section.locator('[data-answer-pane]');
    await expect(pane.locator('[data-answer-mode="math"]')).toBeVisible();
    await expect(pane.locator('.katex').first()).toBeVisible();

    await row.locator('[data-quote-button]').click();
    const marks = pane.locator('mark');
    await expect(marks).toHaveCount(1);
    await expect(marks.first()).toHaveAttribute('data-highlight', 'exact');
    await expect(marks.first().locator('.katex')).toHaveCount(1);            // the formula, typeset
    // …and it is the derivative's line, not f(x)'s or the inequality's
    const lines = pane.locator('[data-answer-mode="math"] > div');
    await expect(lines.nth(2).locator('mark')).toHaveCount(1);
    await expect(lines.nth(1).locator('mark')).toHaveCount(0);
    await expect(lines.nth(3).locator('mark')).toHaveCount(0);
    if (process.env.QUOTE_SHOT) await page.screenshot({ path: process.env.QUOTE_SHOT });
});
