import { expect, test } from '@playwright/test';
import { seedAuth } from './fixtures';

/**
 * Rider (a) of the Phase-3 go + the Δ10 shell guarantee:
 * THE CURSOR FREEZE MUST SURVIVE ARROW NAVIGATION.
 *
 * HISTORY: the freeze originally lived in a ref inside the PAGE component and
 * was ILLUSORY — the App Router keys page segments by dynamic-param value, so
 * every prev/next REMOUNTED the page, re-ran the entry effect (a fetch pair
 * per arrow) and silently recomputed the order from post-accept state (this
 * spec caught it: 'a' rendered at position 1 of the flipped order). The fix,
 * per the rider's ruling, is the LAYOUT-level holder (BatchReviewProvider in
 * the segment layout): layouts persist across sibling page navigations and
 * remount on fresh route entry — exactly Δ10's "order per entry" semantics.
 *
 * Two detectors, both load-bearing:
 *  1. `getBatch` is called exactly once per mounted entry effect — one
 *     StrictMode dev pair for the WHOLE arrow walk. A page-held effect would
 *     produce a pair per navigation.
 *  2. Responses after the entry pair flip every flag verdict, so any recompute
 *     WOULD produce a different order — yet the walk must follow the ENTRY
 *     order (flagged-first over the entry payload): b → a → c, and back.
 */

const BATCH_ID = 'b0000000-0000-0000-0000-000000000001';

function draft(answerText: string) {
    return {
        schema_version: '1.0',
        student_name_suggestion: null,
        page_count: 1,
        answers: [{
            question_number: 1, sub_question_id: null,
            answer_text: answerText, confidence: 0.9, page_numbers: [1],
        }],
        annotations: [],
        model_version: null,
        transcription_duration_ms: null,
    };
}

function item(id: string, filename: string, flagged: boolean) {
    return {
        transcription_id: id,
        filename,
        transcription_status: 'transcribed',
        created_at: '2026-08-04T10:00:00Z',
        draft: draft(`int x = ${id.charCodeAt(0)};`),
        review: null,
        student_name_suggestion: null,
        matched_student_id: null,
        matched_student_name: null,
        flag_verdict: { review_needed: flagged, reasons: flagged ? ['low_confidence'] : [] },
        graded_test_id: null,
        graded_test_status: null,
        total_score: null,
        total_possible: null,
    };
}

function batchPayload(items: unknown[]) {
    return {
        id: BATCH_ID,
        name: 'freeze test',
        rubric_id: 'r0000000-0000-0000-0000-000000000001',
        class_id: null,
        status: 'in_progress',
        started_at: null,
        completed_at: null,
        created_at: '2026-08-04T10:00:00Z',
        rollup: {
            transcribing: 0, transcribed: 3, approved_transcription: 0,
            grading: 0, draft: 0, approved: 0, failed: 0, total: 3,
        },
        transcriptions: items,
    };
}

test('cursor order is frozen across arrow navigation (no remount, no refetch)', async ({ page }) => {
    await seedAuth(page);

    let batchCalls = 0;
    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        const json = (body: unknown) => route.fulfill({
            status: 200, contentType: 'application/json', body: JSON.stringify(body),
        });

        if (url.includes('/api/v0/auth/me')) {
            return json({
                id: 'u1', email: 'teacher@example.com', full_name: 'מורה בדיקה',
                subscription_status: 'active', is_subscription_active: true,
                subject_matters: [], created_at: '2026-01-01T00:00:00Z',
            });
        }

        if (url.includes(`/api/v0/batches/${BATCH_ID}`)) {
            batchCalls += 1;
            // Dev server runs React StrictMode: the entry effect mounts twice,
            // so the ENTRY payload must cover the first TWO calls (the shell's
            // cancellation guard discards the first response; the ref freezes
            // from the second). Flipped verdicts from call 3 onward.
            if (batchCalls <= 2) {
                // Entry payload: only 'b' flagged → frozen order [b, a, c].
                return json(batchPayload([
                    item('a', 'a.pdf', false),
                    item('b', 'b.pdf', true),
                    item('c', 'c.pdf', false),
                ]));
            }
            // Any LATER fetch (remount symptom) returns FLIPPED verdicts —
            // recomputing from this payload would give [a, c, b].
            return json(batchPayload([
                item('a', 'a.pdf', true),
                item('b', 'b.pdf', false),
                item('c', 'c.pdf', true),
            ]));
        }

        // Phase-3 surface dependencies: roster (empty) + page images (1px PNG).
        if (url.includes('/api/v0/classroom/students')) {
            return json({ students: [] });
        }
        if (/\/api\/v0\/transcriptions\/[^/]+\/pages\/\d+/.test(url)) {
            const page_number = Number(url.split('/pages/')[1]);
            return json({
                page_number,
                thumbnail_base64:
                    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABh6FO1AAAAABJRU5ErkJggg==',
            });
        }

        return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' });
    });

    // Enter at the first item of the ENTRY order (flagged-first → 'b').
    await page.goto(`/batches/${BATCH_ID}/review/b`);
    await expect(page.getByText('b.pdf')).toBeVisible();
    await expect(page.getByText('1 מתוך 3')).toBeVisible();

    // b → a (entry order position 2; a reshuffled order would go b → c).
    await page.getByRole('button', { name: 'הבא' }).click();
    await expect(page).toHaveURL(new RegExp(`/batches/${BATCH_ID}/review/a$`));
    await expect(page.getByText('a.pdf')).toBeVisible();
    await expect(page.getByText('2 מתוך 3')).toBeVisible();

    // a → c (last item): next becomes the back-to-batch link.
    await page.getByRole('button', { name: 'הבא' }).click();
    await expect(page).toHaveURL(new RegExp(`/batches/${BATCH_ID}/review/c$`));
    await expect(page.getByText('3 מתוך 3')).toBeVisible();
    await expect(page.getByRole('link', { name: /חזרה לסיכום המקבץ/ })).toBeVisible();

    // c → a → b backwards, still entry order.
    await page.getByRole('button', { name: 'הקודם' }).click();
    await expect(page).toHaveURL(new RegExp(`/batches/${BATCH_ID}/review/a$`));
    await page.getByRole('button', { name: 'הקודם' }).click();
    await expect(page).toHaveURL(new RegExp(`/batches/${BATCH_ID}/review/b$`));
    await expect(page.getByText('1 מתוך 3')).toBeVisible();

    // The remount detector: one StrictMode mount pair, nothing more. A remount
    // per arrow navigation would re-run the entry effect and push this to 10.
    expect(batchCalls).toBe(2);
});
