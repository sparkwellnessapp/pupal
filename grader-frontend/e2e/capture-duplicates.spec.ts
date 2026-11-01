import { expect, test, type Page, type Route } from '@playwright/test';
import { seedAuth } from './fixtures';
import { AUTH_ME, fulfillJson, seedBatch, seedItem } from './seedBatch';

/**
 * [SCN-13/14] The photos a student sent, and the choice between two sets.
 *
 *  * «תמונות» on a submissions row opens the photos of the SAVED set: every
 *    page, one click to a large page, one more to the whole uncropped photo.
 *  * «בחירת הגשה» shows BOTH sets in full and keeps the one she picks — from
 *    the panel, or straight from the triage card (no navigation). A refusal
 *    is shown INSIDE the dialog, which stays open: the 2026-10-30 dialog
 *    closed first and reported its 422 behind itself, so nothing happened.
 *
 * Needs a server built with the capture flag (see capture-home-link.spec.ts):
 *   NEXT_PUBLIC_CAPTURE_ENABLED=true NEXT_DIST_DIR=.next-e2e npm run dev -- --port 3100
 *   E2E_CAPTURE=1 npx playwright test e2e/capture-duplicates.spec.ts
 */
test.skip(process.env.E2E_CAPTURE !== '1', 'needs a server built with NEXT_PUBLIC_CAPTURE_ENABLED=true');

const BATCH_ID = 'b0000000-0000-0000-0000-0000000dup13';
// A 3×4 grey PNG: any picture will do, the page box comes from image_w/h.
const PIXEL = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAMAAAAECAAAAABgKOSWAAAAEUlEQVR4nGNgYGBgYGBgYGAAAAAOAAFWDtAVAAAAAElFTkSuQmCC';

function page_(id: string, position: number) {
    return {
        page_id: id, position, status: 'analyzed', content_type: 'image/jpeg', image_w: 3000, image_h: 4000,
        corners: [[0.05, 0.05], [0.95, 0.05], [0.95, 0.95], [0.05, 0.95]], corners_source: 'auto_contour',
        rotation: 0, quality: null, preview_url: PIXEL,
    };
}

const DANI = { student_id: 'st-dani', display_name: 'דני כהן' };
const ROWS = [
    { submission_id: 'sub-a', source: 'student_link', student: DANI, student_state: 'conflict',
      duplicate_group: 'sub-a', page_count: 3, saved_at: '2026-10-29T15:42:00Z', version_no: 1,
      version_status: 'completed', transcription_id: 't-a', transcription_status: 'transcribed' },
    { submission_id: 'sub-b', source: 'student_link', student: DANI, student_state: 'conflict',
      duplicate_group: 'sub-a', page_count: 4, saved_at: '2026-10-29T16:52:00Z', version_no: 1,
      version_status: 'completed', transcription_id: 't-b', transcription_status: 'transcribed' },
    { submission_id: 'sub-c', source: 'teacher', student: { student_id: 'st-noa', display_name: 'נועה בר' },
      student_state: 'confirmed', duplicate_group: null, page_count: 2, saved_at: '2026-10-29T15:00:00Z',
      version_no: 1, version_status: 'completed', transcription_id: 't-c', transcription_status: 'transcribed' },
];
const PANEL = { rows: ROWS, counter: { submitted_students: 2, roster_size: 25 } };
const AFTER_KEEP = { rows: [ { ...ROWS[0], student_state: 'confirmed', duplicate_group: null }, ROWS[2] ],
                     counter: { submitted_students: 2, roster_size: 25 } };

function version(id: string, pages: number) {
    return {
        submission_id: id, source: 'student_link', student: DANI, version_no: 1,
        saved_at: '2026-10-29T15:42:00Z', transcription_status: 'transcribed',
        pages: Array.from({ length: pages }, (_, i) => page_(`${id}-p${i + 1}`, i + 1)),
    };
}

async function mock(page: Page, opts: { keepStatus?: number; keepBody?: unknown } = {}) {
    const kept: string[] = [];
    let panel: unknown = PANEL;
    await seedAuth(page);
    await page.route('**/api/v0/**', async (route: Route) => {
        const url = route.request().url().split('?')[0];
        const method = route.request().method();
        if (url.endsWith('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);
        if (url.endsWith(`/batches/${BATCH_ID}/capture-link`)) return fulfillJson(route, { detail: 'Not Found' }, 404);
        if (url.endsWith(`/batches/${BATCH_ID}/capture-submissions`)) return fulfillJson(route, panel);
        const keep = url.match(/capture-submissions\/([^/]+)\/keep$/);
        if (keep && method === 'POST') {
            kept.push(keep[1]);
            if (opts.keepStatus) return fulfillJson(route, opts.keepBody, opts.keepStatus);
            panel = AFTER_KEEP;
            return fulfillJson(route, AFTER_KEEP);
        }
        const v = url.match(/capture\/teacher\/[^/]+\/submissions\/([^/]+)\/version$/);
        if (v) return fulfillJson(route, version(v[1], ROWS.find((r) => r.submission_id === v[1])!.page_count));
        if (url.endsWith(`/api/v0/batches/${BATCH_ID}`)) {
            return fulfillJson(route, seedBatch({
                id: BATCH_ID,
                items: [
                    seedItem('t-a', { reasons: ['capture_conflict'], suggestion: 'דני כהן' }),
                    seedItem('t-b', { reasons: ['capture_conflict'], suggestion: 'דני כהן' }),
                    seedItem('t-c', { matchedStudentId: 'st-noa', matchedStudentName: 'נועה בר' }),
                ],
            }));
        }
        return fulfillJson(route, {});
    });
    return { kept };
}

test('«תמונות» opens the saved set: every page, a large page, the whole photo', async ({ page }) => {
    await mock(page);
    await page.goto(`/batches/${BATCH_ID}`);
    const noa = page.getByTestId('capture-row').filter({ hasText: 'נועה בר' });
    await noa.getByTestId('capture-photos').click();

    const dialog = page.getByTestId('photos-dialog');
    await expect(dialog.getByText('התמונות של נועה בר')).toBeVisible();
    await expect(dialog.getByTestId('captured-page')).toHaveCount(2);
    await dialog.getByTestId('captured-page').nth(1).click();
    await expect(dialog.getByTestId('page-zoom')).toContainText('עמוד 2 / 2');
    await dialog.getByRole('button', { name: 'הצגת התמונה המלאה' }).click();
    await expect(dialog.getByRole('button', { name: 'הצגת הדף החתוך' })).toBeVisible();
    await dialog.getByRole('button', { name: 'חזרה לכל העמודים' }).click();
    await expect(dialog.getByTestId('captured-page')).toHaveCount(2);
});

test('«בחירת הגשה» shows both sets in full and keeps the EARLIER one', async ({ page }) => {
    const { kept } = await mock(page);
    await page.goto(`/batches/${BATCH_ID}`);
    // Both rows of the pair carry the action — the earlier one used to have none.
    await expect(page.getByTestId('choose-set')).toHaveCount(2);
    await page.getByTestId('choose-set').first().click();

    const dialog = page.getByTestId('duplicate-dialog');
    await expect(dialog.getByText('דני כהן — יותר מהגשה אחת')).toBeVisible();
    const sets = dialog.getByTestId('duplicate-set');
    await expect(sets).toHaveCount(2);
    await expect(sets.nth(0).getByTestId('captured-page')).toHaveCount(3);
    await expect(sets.nth(1).getByTestId('captured-page')).toHaveCount(4);

    await sets.nth(0).getByTestId('keep-this').click();
    await expect(sets.nth(0)).toContainText('ההגשה השנייה תבוטל ולא תיבדק.');
    expect(kept).toEqual([]);                                   // nothing until she confirms
    await sets.nth(0).getByTestId('keep-confirm').click();
    await expect(dialog).toBeHidden();
    expect(kept).toEqual(['sub-a']);
    await expect(page.getByTestId('capture-row')).toHaveCount(2);
    await expect(page.getByTestId('choose-set')).toHaveCount(0);
});

test('a refusal is said inside the dialog, which stays open', async ({ page }) => {
    await mock(page, { keepStatus: 409, keepBody: { detail: {
        code: 'other_approved', message_he: 'הגשה אחרת של התלמיד כבר אושרה — רק אותה אפשר לשמור' } } });
    await page.goto(`/batches/${BATCH_ID}`);
    await page.getByTestId('choose-set').first().click();
    const dialog = page.getByTestId('duplicate-dialog');
    const first = dialog.getByTestId('duplicate-set').nth(0);
    await first.getByTestId('keep-this').click();
    await first.getByTestId('keep-confirm').click();
    await expect(dialog.getByRole('alert')).toHaveText('הגשה אחרת של התלמיד כבר אושרה — רק אותה אפשר לשמור');
    await expect(dialog).toBeVisible();
});

test('the triage card of a duplicate opens the choice in place', async ({ page }) => {
    await mock(page);
    await page.goto(`/batches/${BATCH_ID}`);
    const card = page.getByTestId('eyes-row').first();
    await expect(card).toContainText('בחירת הגשה');
    await card.click();
    await expect(page.getByTestId('duplicate-dialog')).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`/batches/${BATCH_ID}$`));
});

test('the review page chip lands on the batch with the choice open', async ({ page }) => {
    await mock(page);
    await page.goto(`/batches/${BATCH_ID}?resolve=t-b`);
    await expect(page.getByTestId('duplicate-dialog')).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`/batches/${BATCH_ID}$`));     // the query is dropped
});
