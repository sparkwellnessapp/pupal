import { expect, test, type Page } from '@playwright/test';
import { seedAuth } from './fixtures';
import { AUTH_ME, fulfillJson, SEED_BATCH_ID, seedBatch, seedItem } from './seedBatch';

/**
 * Table rendering on the transcription-review surface (2026-08-23).
 *
 * The load-bearing claim is NOT "a grid appears" — it is that the grid is a
 * DISPLAY DERIVATION and the verbatim text underneath is untouched. So the
 * assertions here are, in order of importance:
 *   1. the pipe rows stop being text and become a <table>;
 *   2. one click returns the EXACT original string to an editable textarea;
 *   3. that click does NOT dirty the item (Δ14 — viewing is not commitment,
 *      and a phantom overlay would silently drop the item out of bulk-accept);
 *   4. an edit made after toggling still saves verbatim through the unchanged
 *      PATCH path.
 *
 * The fixture is a REAL transcribed trace table from a live draft, ragged rows
 * and all — a rectangular synthetic one would not exercise the detector.
 */

const TABLE_ANSWER = [
    'if:',
    'returned | x | i | arr[i] | (arr[i]≠1 && arr[i]≠x && x%arr[i]==0)',
    '6 | 0 | 1 | F',
    '6 | 1 | 5 | F',
    '6 | 2 | 4 | F',
    'true | 6 | 4 | 3 | T',
    '',
    '(א, 2) לבדוק אם יש ערך במערך ש-שונה מ-1',
].join('\n');

interface MockState {
    patchBodies: Array<Record<string, unknown>>;
}

async function install(page: Page): Promise<MockState> {
    const state: MockState = { patchBodies: [] };
    const payload = seedBatch({
        items: [
            seedItem('tt1', {
                matchedStudentId: 's1',
                matchedStudentName: 'רז כהן',
                draft: {
                    answers: [{
                        question_number: 1, sub_question_id: null,
                        answer_text: TABLE_ANSWER, confidence: 0.95, page_numbers: [1],
                    }],
                },
            }),
        ],
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
        if (method === 'PATCH' && /\/transcriptions\/[^/]+\/review/.test(url)) {
            const body = route.request().postDataJSON() as Record<string, unknown>;
            state.patchBodies.push(body);
            return fulfillJson(route, {
                schema_version: '1.0', answers: body.answers,
                student_id: body.student_id ?? null, updated_at: '2026-08-23T10:00:00Z',
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

test('transcription-table-rendering — grid by default, verbatim text one click away, no phantom dirt', async ({ page }) => {
    await seedAuth(page);
    const state = await install(page);

    await page.goto(`/batches/${SEED_BATCH_ID}/review/tt1`);

    // 1. The pipe rows became a real table; none of them survives as text.
    const view = page.getByTestId('transcribed-answer-view');
    await expect(view).toBeVisible();
    await expect(view.locator('table')).toBeVisible();
    await expect(view.locator('thead th').first()).toHaveText('returned');
    await expect(page.getByText('6 | 0 | 1 | F')).toHaveCount(0);
    await expect(page.getByTestId('transcription-editor')).toHaveCount(0);
    // The surrounding prose is untouched by the grid.
    await expect(view).toContainText('לבדוק אם יש ערך במערך');

    // The grid is an LTR island, like the editor it stands in for.
    await expect(view.locator('table').locator('xpath=ancestor::div[@dir][1]'))
        .toHaveAttribute('dir', 'ltr');

    // 2. One click returns the EXACT source string, editable.
    await page.getByTestId('answer-view-toggle').click();
    const editor = page.getByTestId('transcription-editor');
    await expect(editor).toHaveValue(TABLE_ANSWER);
    await expect(page.getByTestId('transcribed-answer-view')).toHaveCount(0);
    // The caret was handed over — she clicked to edit, so she can type at once.
    await expect(editor).toBeFocused();

    // 3. Δ14: looking at the text is not an edit. No dirt, no autosave.
    await expect(page.getByText('שינויים לא שמורים')).toHaveCount(0);
    expect(state.patchBodies).toHaveLength(0);

    // Back to the grid, still no dirt.
    await page.getByTestId('answer-view-toggle').click();
    await expect(page.getByTestId('transcribed-answer-view')).toBeVisible();
    await expect(page.getByText('שינויים לא שמורים')).toHaveCount(0);
    expect(state.patchBodies).toHaveLength(0);

    // 4. A real edit made through the toggle still saves verbatim.
    await page.getByTestId('answer-view-toggle').click();
    await editor.fill('6 | 0 | 1 | T');
    await expect(page.getByText('שינויים לא שמורים')).toBeVisible();
    await page.getByRole('button', { name: 'שמירה' }).click();
    await expect(page.getByText('נשמר')).toBeVisible();
    expect(state.patchBodies).toHaveLength(1);
    expect((state.patchBodies[0].answers as Array<{ answer_text: string }>)[0].answer_text)
        .toBe('6 | 0 | 1 | T');
});
