import { expect, test, type Page } from '@playwright/test';
import { seedAuth } from './fixtures';
import { AUTH_ME, fulfillJson, SEED_BATCH_ID, seedBatch, seedItem } from './seedBatch';

/**
 * Mathematics on the transcription-review surface (MATH_RENDERING_PLAN §4).
 *
 *   math-rtl-coordinate-order — THE STANDING GUARD for MathText's isolation. Measured in
 *     Chromium (docs/math-rendering/render-test): KaTeX inheriting the page's RTL drew
 *     `(1/e, 0)` as `(0, 1/e)`. Asserted by GEOMETRY — the fraction's box must sit LEFT of
 *     the zero's — because the DOM order is the same either way and only the layout lies.
 *   math-span-viewing-is-not-commitment — opening a formula and closing it writes nothing (Δ14).
 *   math-span-edit-splices-one-span — an edit in MathLive changes that span's body and no
 *     other byte of the answer.
 */

const RUBRIC_ID = 'r0000000-0000-0000-0000-0000000000m1';

async function install(page: Page, answer: string, figures?: unknown[]) {
    const state = { patchBodies: [] as Array<Record<string, unknown>> };
    const base = seedBatch({
        items: [
            seedItem('m1', {
                matchedStudentId: 's1',
                matchedStudentName: 'רז כהן',
                draft: {
                    answers: [{
                        question_number: 1, sub_question_id: null,
                        answer_text: answer, confidence: 0.95, page_numbers: [1],
                        ...(figures ? { figures } : {}),
                    }],
                },
            }),
        ],
    });
    const payload = { ...base, rubric_id: RUBRIC_ID };

    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        const method = route.request().method();
        if (url.includes('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);
        if (url.includes(`/api/v0/rubrics/${RUBRIC_ID}`)) {
            return fulfillJson(route, { id: RUBRIC_ID, name: 'מתמטיקה', subject: 'mathematics' });
        }
        if (url.includes('/api/v0/classroom/students')) {
            return fulfillJson(route, {
                students: [{ id: 's1', full_name: 'רז כהן', notes: null, created_at: '2026-01-01T00:00:00Z' }],
            });
        }
        if (method === 'PATCH' && /\/transcriptions\/[^/]+\/review/.test(url)) {
            const body = route.request().postDataJSON() as Record<string, unknown>;
            state.patchBodies.push(body);
            return fulfillJson(route, {
                schema_version: '1.0', answers: body.answers,
                student_id: body.student_id ?? null, updated_at: '2026-10-28T10:00:00Z',
            });
        }
        if (url.includes(`/api/v0/batches/${SEED_BATCH_ID}`)) return fulfillJson(route, payload);
        if (/\/api\/v0\/transcriptions\/[^/]+\/pages\/\d+/.test(url)) {
            return fulfillJson(route, {
                page_number: Number(url.split('/pages/')[1]),
                thumbnail_base64:
                    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABh6FO1AAAAABJRU5ErkJggg==',
            });
        }
        return fulfillJson(route, {});
    });
    return state;
}

test('math-rtl-coordinate-order — a point inside Hebrew reads left to right', async ({ page }) => {
    await seedAuth(page);
    await install(page, 'נקודת חיתוך \\((\\frac{1}{e}, 0)\\) עם ציר x');
    await page.goto(`/batches/${SEED_BATCH_ID}/review/m1`);

    const editor = page.getByTestId('math-answer-editor');
    await expect(editor).toBeVisible();
    const span = editor.locator('[data-math-span="0"]');
    await expect(span.locator('.katex-html')).toBeVisible();

    const frac = await span.locator('.katex-html .mfrac').first().boundingBox();
    const zero = await span.locator('.katex-html .mord', { hasText: /^0$/ }).last().boundingBox();
    expect(frac && zero).toBeTruthy();
    expect(frac!.x + frac!.width).toBeLessThanOrEqual(zero!.x + 0.5);

    // and the Hebrew stays on the right of the formula, as the sentence reads
    const hebrew = await editor.getByText('נקודת חיתוך').boundingBox();
    expect(hebrew!.x).toBeGreaterThan(zero!.x);
});

test('math-span-viewing-is-not-commitment — open and close a formula, nothing is written', async ({ page }) => {
    await seedAuth(page);
    const state = await install(page, 'לכן \\(x=3\\)');
    await page.goto(`/batches/${SEED_BATCH_ID}/review/m1`);

    await page.locator('[data-math-edit="0"]').click();
    await expect(page.locator('math-field')).toBeVisible();
    await page.getByTestId('math-span-editor').getByRole('button', { name: 'ביטול' }).click();
    await expect(page.locator('math-field')).toHaveCount(0);

    // Save without a keystroke is still not an edit.
    await page.locator('[data-math-edit="0"]').click();
    await expect(page.locator('math-field')).toBeVisible();
    await page.getByTestId('math-span-save').click();

    await expect(page.getByText('שינויים לא שמורים')).toHaveCount(0);
    expect(state.patchBodies).toHaveLength(0);
});

test('math-span-edit-splices-one-span — a MathLive edit changes that span only', async ({ page }) => {
    await seedAuth(page);
    const answer = 'ראשית \\(x=3\\)\nולכן \\(y=\\sqrt{e}\\) בדיוק';
    const state = await install(page, answer);
    await page.goto(`/batches/${SEED_BATCH_ID}/review/m1`);

    await page.locator('[data-math-line]').first().locator('[data-math-edit="0"]').click();
    const field = page.locator('math-field');
    await expect(field).toBeVisible();
    await field.focus();
    await page.keyboard.press('End');
    await page.keyboard.press('Backspace');
    await page.keyboard.type('4');
    await page.getByTestId('math-span-save').click();

    await expect(page.getByText('שינויים לא שמורים')).toBeVisible();
    await page.getByRole('button', { name: 'שמירה' }).click();
    await expect(page.getByText('נשמר')).toBeVisible();
    expect(state.patchBodies).toHaveLength(1);
    expect((state.patchBodies[0].answers as Array<{ answer_text: string }>)[0].answer_text)
        .toBe(answer.replace('x=3', 'x=4'));
});

// ── Phase 3: a drawing is the student's ink with Vivi's reading pinned on it ──────────

const SKETCH = "ב.\n\\(f'(x)=0\\)\n[איור 1: סקיצה של הפונקציה]";
const READING = [{
    figure_no: 1, page_number: 1, kind: 'function_sketch', box_2d: [100, 100, 900, 900],
    features: [
        { kind: 'vertical_asymptote', as_written: 'x=2', point: [500, 400], ink: 'primary', uncertain: false, source: 'vivi' },
        { kind: 'minimum', as_written: '(\\sqrt{e}, -2.25)', point: [800, 600], ink: 'other', uncertain: true, source: 'vivi' },
    ],
}];

test('math-figure-card — readings sit on the ink; viewing writes nothing; an edit is saved with the answer', async ({ page }) => {
    await seedAuth(page);
    const state = await install(page, SKETCH, READING);
    await page.goto(`/batches/${SEED_BATCH_ID}/review/m1`);

    const card = page.getByTestId('figure-card');
    await expect(card).toBeVisible();
    await expect(card.locator('[data-figure-chip]')).toHaveCount(2);
    await expect(card.getByTestId('figure-features').locator('[data-figure-feature]')).toHaveCount(2);
    await expect(card).toContainText('אסימפטוטה אנכית');
    await expect(card).toContainText('לא ודאי');
    await expect(card).toContainText('בצבע אחר');

    // Hovering a row lights its chip — the reading and its mark are one thing.
    await card.locator('[data-figure-feature="0"]').hover();
    await expect(card.locator('[data-figure-chip="0"]')).toHaveClass(/h-5/);

    // Δ14: looking is not an edit.
    await expect(page.getByText('שינויים לא שמורים')).toHaveCount(0);
    expect(state.patchBodies).toHaveLength(0);

    // Deleting a misread is her decision, and it travels with the answer.
    await card.locator('[data-figure-delete="1"]').click();
    await expect(card.locator('[data-figure-feature]')).toHaveCount(1);
    await expect(page.getByText('שינויים לא שמורים')).toBeVisible();
    await page.getByRole('button', { name: 'שמירה' }).click();
    await expect(page.getByText('נשמר')).toBeVisible();
    expect(state.patchBodies).toHaveLength(1);
    const saved = (state.patchBodies[0].answers as Array<{ answer_text: string; figures?: Array<{ features: unknown[] }> }>)[0];
    expect(saved.answer_text).toBe(SKETCH);
    expect(saved.figures?.[0].features).toHaveLength(1);
});
