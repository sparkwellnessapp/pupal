import { expect, test } from '@playwright/test';
import { seedAuth } from './fixtures';

/**
 * single-flow-review-unchanged (plan §9, ruled; lands with Phase 5):
 * the wizard's review step renders via the WRAPPED TranscriptionReviewPanel
 * (now a thin wrapper over the shared surface) with its prop seam intact —
 * and the submit payload is byte-identical in shape to the historical panel:
 * the FULL answer set in draft order (edited over draft), plus student_id.
 *
 * Phase-5 rider 2 — batch-born behaviors must be INERT in the single flow:
 * no autosave PATCH ever fires, and no save/accept affordances render.
 */

const DRAFT = {
    schema_version: '1.0',
    student_name_suggestion: 'רז כהן',
    page_count: 1,
    answers: [
        {
            question_number: 1, sub_question_id: null,
            answer_text: 'int original = 1;', confidence: 0.9, page_numbers: [1],
        },
        {
            question_number: 2, sub_question_id: 'א',
            answer_text: 'int second = 2;', confidence: 0.95, page_numbers: [1],
        },
    ],
    annotations: [],
    model_version: null,
    transcription_duration_ms: null,
};

test('single-flow-review-unchanged — wrapped panel, identical submit payload, batch behaviors inert', async ({ page }) => {
    await seedAuth(page);

    let gradeBody: Record<string, unknown> | null = null;
    let reviewPatchCalls = 0;

    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        const method = route.request().method();
        const json = (body: unknown, status = 200) => route.fulfill({
            status, contentType: 'application/json', body: JSON.stringify(body),
        });

        if (url.includes('/api/v0/auth/me')) {
            return json({
                id: 'u1', email: 'teacher@example.com', full_name: 'מורה בדיקה',
                subscription_status: 'active', is_subscription_active: true,
                subject_matters: [], created_at: '2026-01-01T00:00:00Z',
            });
        }
        if (url.includes('/extraction-jobs')) return json([]);
        if (url.includes('/api/v0/rubrics/r1')) {
            return json({
                id: 'r1', name: 'מחוון בדיקה', total_points: 100, total_questions: 2,
                is_compiled: true, needs_recompilation: false,
                created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
                stats: null, draft: null,
            });
        }
        if (url.includes('/api/v0/classroom/classes')) return json({ classes: [] });
        if (url.includes('/api/v0/classroom/students')) {
            return json({ students: [{ id: 's1', full_name: 'רז כהן', notes: null, created_at: '2026-01-01T00:00:00Z' }] });
        }
        if (url.includes('/api/v0/transcriptions/transcribe') && method === 'POST') {
            return json({ transcription_id: 'tx-1', draft: DRAFT });
        }
        if (/\/api\/v0\/transcriptions\/[^/]+\/review/.test(url) && method === 'PATCH') {
            reviewPatchCalls += 1;   // rider 2: must stay 0
            return json({}, 500);
        }
        if (url.includes('/api/v0/transcriptions/grade') && method === 'POST') {
            gradeBody = route.request().postDataJSON() as Record<string, unknown>;
            return json({ graded_test_id: 'gt-1', status: 'pending' });
        }
        if (/\/api\/v0\/transcriptions\/[^/]+\/pages\/\d+/.test(url)) {
            return json({
                page_number: 1,
                thumbnail_base64:
                    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABh6FO1AAAAABJRU5ErkJggg==',
            });
        }
        // Graded-test polling after submit — return a stub the poller tolerates.
        if (url.includes('/api/v0/grading/graded_test/')) {
            return json({ id: 'gt-1', status: 'pending' });
        }
        return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' });
    });

    // Deep-link lands on the upload step with the rubric preselected.
    await page.goto('/?rubric=r1');
    await expect(page.getByText('העלאת מבחנים')).toBeVisible();
    await expect(page.getByText('מחוון בדיקה')).toBeVisible();

    // One handwritten PDF → the single-test path. The mode toggle starts
    // unselected (transcriptionMode is null until the teacher picks).
    await page.getByRole('button', { name: /תמלול כתב יד/ }).click();
    await page.setInputFiles('input[type=file]', {
        name: 'test.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 stub'),
    });
    await page.getByRole('button', { name: /התחל בדיקה/ }).click();

    // The review step renders via the WRAPPED panel: single-flow chrome +
    // the shared surface underneath.
    await expect(page.getByRole('button', { name: /שלח לבדיקה/ })).toBeVisible();
    await expect(page.getByText('מבחן מקורי')).toBeVisible();
    await expect(page.getByText('תמלול AI')).toBeVisible();
    await expect(page.getByTestId('transcription-editor').first()).toBeVisible();

    // Rider 2 — batch affordances ABSENT: no accept, no save button/indicator,
    // no accepted chip. (The submit button is the only primary action.)
    await expect(page.getByRole('button', { name: 'אישור תמלול' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'שמירה' })).toHaveCount(0);
    await expect(page.getByText('שינויים לא שמורים')).toHaveCount(0);
    await expect(page.getByText('נשמר', { exact: true })).toHaveCount(0);
    await expect(page.getByText('אושר', { exact: true })).toHaveCount(0);

    // Edit the first answer, pick the student, submit.
    await page.getByTestId('transcription-editor').first().fill('int edited = 42;');
    await page.getByPlaceholder('חפש תלמיד...').click();
    await page.getByText('רז כהן', { exact: true }).first().click();
    await page.getByRole('button', { name: /שלח לבדיקה/ }).click();

    // The submit payload: byte-identical SHAPE to the historical panel —
    // full snapshot in draft order, edited over draft, student_id attached.
    await expect.poll(() => gradeBody).not.toBeNull();
    expect(gradeBody).toEqual({
        transcription_id: 'tx-1',
        answers: [
            { question_number: 1, sub_question_id: null, answer_text: 'int edited = 42;' },
            { question_number: 2, sub_question_id: 'א', answer_text: 'int second = 2;' },
        ],
        student_id: 's1',
    });

    // Rider 2 — the overlay autosave NEVER fired in the single flow.
    expect(reviewPatchCalls).toBe(0);
});
