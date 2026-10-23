import { expect, test, type Page } from '@playwright/test';
import { seedAuth } from './fixtures';
import { AUTH_ME, fulfillJson, SEED_BATCH_ID, seedBatch, seedItem } from './seedBatch';

/**
 * Native table editing on the per-item review route (2026-09-24).
 *
 * The report: a table-bearing answer could be edited only through
 * «הצגת הטקסט המקורי». These journeys pin the fix on the LIVE route
 * (/batches/[id]/review/[transcriptionId]), not the quarantined panel:
 *
 *   table-edit-in-place       — one header cell, one body cell, one prose line;
 *                               away and back; the overlay and the accept body
 *                               carry EXACTLY those three spans (TBL-2, TBL-5).
 *   table-viewing-is-not-commitment — focus, Tab, Shift+Tab, Enter, Esc, blur,
 *                               toggle: zero bytes, no dirt, no PATCH (TBL-3/Δ14).
 *   table-structure-guard     — `|` and `;` never change the grid (TBL-4, OD-4).
 *   table-cell-keys           — Enter walks the column, Esc leaves, arrows stay
 *                               in the cell and never navigate items (OD-2, R6).
 *   rtl-bidi-table-cell       — a Hebrew-initial cell is a pure dir=ltr island.
 *   table-swap-intact         — SWAP carries a table-bearing answer byte-for-byte.
 *
 * The fixture is the SHAPE P1 now emits (prompt t1.4-tables): fully bounded,
 * space-padded rows with explicit empty cells.
 */

const TABLE_ANSWER = [
    'א) 1)',
    '| x | i | arr[i] | ret |',
    '| 6 | 0 | 8 |  |',
    '|  | 1 | 5 |  |',
    '|  | 2 | 3 | T |',
    '',
    '(א, 2) הפעולה בודקת אם יש ערך במערך',
].join('\n');

const EXPECTED_AFTER_EDITS = TABLE_ANSWER
    .replace('| arr[i] |', '| arr[j] |')
    .replace('|  | 1 | 5 |', '|  | 1 | 7 |')
    .replace('ערך במערך', 'ערך אחר במערך');

const HEBREW_TABLE = [
    '| מוחזר x | i |',
    '| 6 | 0 |',
    '| 7 | 1 |',
].join('\n');

interface MockState {
    overlays: Map<string, Record<string, unknown>>;
    patchBodies: Array<{ txId: string; body: Record<string, unknown> }>;
    acceptBodies: Array<{ txId: string; body: Record<string, unknown> }>;
}

type Answer = { question_number: number; sub_question_id: string | null; answer_text: string; confidence: number; page_numbers: number[] };

async function install(page: Page, answersById: Record<string, Answer[]>): Promise<MockState> {
    const state: MockState = { overlays: new Map(), patchBodies: [], acceptBodies: [] };
    const payload = () => seedBatch({
        items: Object.entries(answersById).map(([id, answers]) => ({
            ...seedItem(id, {
                matchedStudentId: 's1',
                matchedStudentName: 'רז כהן',
                draft: { answers },
            }),
            review: state.overlays.get(id) ?? null,
        })),
    });

    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        const method = route.request().method();
        if (url.includes('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);
        if (url.includes('/api/v0/classroom/students')) {
            return fulfillJson(route, {
                students: [{ id: 's1', full_name: 'רז כהן', notes: null, created_at: '2026-01-01T00:00:00Z' }],
            });
        }
        const patch = url.match(/\/transcriptions\/([^/]+)\/review/);
        if (method === 'PATCH' && patch) {
            const body = route.request().postDataJSON() as Record<string, unknown>;
            const review = {
                schema_version: '1.0', answers: body.answers,
                student_id: body.student_id ?? null, updated_at: '2026-09-24T10:00:00Z',
            };
            state.patchBodies.push({ txId: patch[1], body });
            state.overlays.set(patch[1], review);
            return fulfillJson(route, review);
        }
        const accept = url.match(/\/api\/v0\/batches\/[^/]+\/accept\/([^/?]+)/);
        if (method === 'POST' && accept) {
            state.acceptBodies.push({ txId: accept[1], body: route.request().postDataJSON() as Record<string, unknown> });
            return fulfillJson(route, { accepted: 1 });
        }
        if (url.includes(`/api/v0/batches/${SEED_BATCH_ID}`)) return fulfillJson(route, payload());
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

const answer = (question_number: number, answer_text: string, sub_question_id: string | null = null): Answer => ({
    question_number, sub_question_id, answer_text, confidence: 0.95, page_numbers: [1],
});

const cell = (page: Page, row: number, col: number) =>
    page.locator(`[data-testid="answer-cell"][data-row="${row}"][data-col="${col}"]`);
const textRun = (page: Page, i: number) => page.getByTestId('answer-text-run').nth(i);
const answerTextOf = (body: Record<string, unknown>) =>
    (body.answers as Array<{ answer_text: string }>)[0].answer_text;

test('table-edit-in-place — header cell, body cell and prose, carried exactly by overlay and accept', async ({ page }) => {
    await seedAuth(page);
    const state = await install(page, { tt1: [answer(1, TABLE_ANSWER)], tt2: [answer(1, 'int y = 2;')] });
    await page.goto(`/batches/${SEED_BATCH_ID}/review/tt1`);

    // No raw toggle needed: the grid IS the editor.
    await expect(cell(page, 0, 2)).toHaveValue('arr[i]');
    await expect(page.getByTestId('transcription-editor')).toHaveCount(0);

    await cell(page, 0, 2).fill('arr[j]');                 // header row
    await cell(page, 2, 2).fill('7');                      // body: '|  | 1 | 5 |  |' → 7
    await textRun(page, 1).fill('(א, 2) הפעולה בודקת אם יש ערך אחר במערך');
    await expect(page.getByText('שינויים לא שמורים')).toBeVisible();

    // Away and back: the autosave-on-navigate flush carries the three edits.
    await page.getByRole('button', { name: 'הבא' }).click();
    await expect(page).toHaveURL(/\/review\/tt2$/);
    expect(state.patchBodies).toHaveLength(1);
    expect(answerTextOf(state.patchBodies[0].body)).toBe(EXPECTED_AFTER_EDITS);
    await page.getByRole('button', { name: 'הקודם' }).click();
    await expect(page).toHaveURL(/\/review\/tt1$/);
    await expect(cell(page, 0, 2)).toHaveValue('arr[j]');
    await expect(cell(page, 2, 2)).toHaveValue('7');

    // Accept: the contract text differs from the draft in exactly those spans.
    await page.getByRole('button', { name: 'אישור תמלול' }).click();
    await page.getByRole('button', { name: 'אישור תמלול' }).last().click();
    await expect.poll(() => state.acceptBodies.length).toBe(1);
    expect(answerTextOf(state.acceptBodies[0].body)).toBe(EXPECTED_AFTER_EDITS);
});

test('table-viewing-is-not-commitment — focus, Tab, Enter, Esc, blur and toggle write nothing', async ({ page }) => {
    await seedAuth(page);
    const state = await install(page, { tt1: [answer(1, TABLE_ANSWER)], tt2: [answer(1, 'int y = 2;')] });
    await page.goto(`/batches/${SEED_BATCH_ID}/review/tt1`);

    await cell(page, 0, 0).click();
    for (let i = 0; i < 14; i += 1) await page.keyboard.press('Tab');
    for (let i = 0; i < 5; i += 1) await page.keyboard.press('Shift+Tab');
    await cell(page, 1, 1).click();
    await page.keyboard.press('Enter');
    await page.keyboard.press('Escape');
    await textRun(page, 1).click();
    await page.getByTestId('answer-view-toggle').click();          // → raw
    await expect(page.getByTestId('transcription-editor')).toHaveValue(TABLE_ANSWER);
    await page.getByTestId('answer-view-toggle').click();          // → grid

    await expect(page.getByText('שינויים לא שמורים')).toHaveCount(0);
    // Navigating flushes only when dirty — a glance must not create an overlay.
    await page.getByRole('button', { name: 'הבא' }).click();
    await expect(page).toHaveURL(/\/review\/tt2$/);
    expect(state.patchBodies).toHaveLength(0);
});

test('table-structure-guard — a typed `|` or `;` never changes the grid or the string', async ({ page }) => {
    await seedAuth(page);
    const state = await install(page, { tt1: [answer(1, TABLE_ANSWER)], tt2: [answer(1, 'int y = 2;')] });
    await page.goto(`/batches/${SEED_BATCH_ID}/review/tt1`);

    await cell(page, 1, 1).click();
    await page.keyboard.press('End');
    await page.keyboard.type('|');
    await expect(cell(page, 1, 1)).toHaveValue('0');
    await expect(page.getByTestId('answer-cell-hint')).toBeVisible();

    await page.keyboard.type(';');
    await expect(page.getByTestId('answer-cell-hint')).toBeVisible();
    await page.keyboard.press('Tab');                                // leave: the refused state is not kept
    await expect(cell(page, 1, 1)).toHaveValue('0');
    await expect(page.locator('[data-testid="answer-cell"]')).toHaveCount(16);

    await page.getByTestId('answer-view-toggle').click();
    await expect(page.getByTestId('transcription-editor')).toHaveValue(TABLE_ANSWER);
    await expect(page.getByText('שינויים לא שמורים')).toHaveCount(0);
    expect(state.patchBodies).toHaveLength(0);
});

test('table-cell-keys — Enter walks the column, Esc leaves, arrows never navigate items', async ({ page }) => {
    await seedAuth(page);
    await install(page, { tt1: [answer(1, TABLE_ANSWER)], tt2: [answer(1, 'int y = 2;')] });
    await page.goto(`/batches/${SEED_BATCH_ID}/review/tt1`);

    await cell(page, 0, 1).click();
    await page.keyboard.press('Enter');
    await expect(cell(page, 1, 1)).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(cell(page, 1, 2)).toBeFocused();
    await page.keyboard.press('ArrowLeft');                          // RTL page: ArrowLeft = הבא outside editables
    await page.keyboard.press('ArrowRight');
    await expect(page).toHaveURL(/\/review\/tt1$/);
    await expect(cell(page, 1, 2)).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(page.locator('[data-testid="answer-cell"]:focus')).toHaveCount(0);
    await expect(page).toHaveURL(/\/review\/tt1$/);
});

test('rtl-bidi-table-cell — a Hebrew-initial cell is a pure dir=ltr island, never plaintext', async ({ page }) => {
    await seedAuth(page);
    await install(page, { tt1: [answer(1, HEBREW_TABLE)] });
    await page.goto(`/batches/${SEED_BATCH_ID}/review/tt1`);

    const heb = cell(page, 0, 0);
    await expect(heb).toHaveValue('מוחזר x');
    await expect(heb).toHaveAttribute('dir', 'ltr');
    expect(await heb.evaluate((el) => getComputedStyle(el).unicodeBidi)).not.toBe('plaintext');
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');

    // Geometry, measured on the cell's sizer (same text, same dir, same font as
    // the input — an <input>'s own glyphs are not reachable by a Range). Under an
    // LTR base the RTL run renders first and the Latin `x` stays to its RIGHT;
    // plaintext would make the paragraph RTL and move `x` to the LEFT.
    const pos = await heb.evaluate((input) => {
        const sizer = input.parentElement?.querySelector('[data-cell-sizer]');
        const node = sizer?.firstChild as Text | null;
        if (!node) return null;
        const mid = (s: number, e: number) => {
            const r = document.createRange(); r.setStart(node, s); r.setEnd(node, e);
            const b = r.getBoundingClientRect(); return b.left + b.width / 2;
        };
        const t = node.textContent ?? '';
        return { hebrew: mid(0, 5), x: mid(t.indexOf('x'), t.indexOf('x') + 1) };
    });
    expect(pos).not.toBeNull();
    expect(pos!.x).toBeGreaterThan(pos!.hebrew);
});

test('table-swap-intact — SWAP carries a table-bearing answer byte-for-byte', async ({ page }) => {
    await seedAuth(page);
    const state = await install(page, {
        tt1: [answer(1, TABLE_ANSWER, 'א'), answer(1, '', 'ב')],
    });
    await page.goto(`/batches/${SEED_BATCH_ID}/review/tt1`);

    await page.locator('[data-answer-key="q1.א"] [data-testid="reassign-select"]').selectOption('q1.ב');
    // The grid moved with its content and is still editable where it landed.
    await expect(page.locator('[data-answer-key="q1.ב"] [data-testid="answer-cell"]')).toHaveCount(16);
    await expect(page.locator('[data-answer-key="q1.א"] [data-testid="answer-cell"]')).toHaveCount(0);

    await page.getByRole('button', { name: 'אישור תמלול' }).click();
    await page.getByRole('button', { name: 'אישור תמלול' }).last().click();
    await expect.poll(() => state.acceptBodies.length).toBe(1);
    const answers = state.acceptBodies[0].body.answers as Array<{ sub_question_id: string | null; answer_text: string }>;
    expect(answers.find((a) => a.sub_question_id === 'ב')!.answer_text).toBe(TABLE_ANSWER);
    expect(answers.find((a) => a.sub_question_id === 'א')!.answer_text).toBe('');
});
