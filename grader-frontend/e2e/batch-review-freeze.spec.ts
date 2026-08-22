import { expect, test, type Page } from '@playwright/test';
import { seedAuth } from './fixtures';
import {
    AUTH_ME,
    fulfillJson,
    SEED_BATCH_ID,
    seedActiveJob,
    seedBatch,
    seedItem,
} from './seedBatch';

/**
 * OD2 (spec §8/R6 — the sanctioned Δ10 amendment): the cursor is
 * PREFIX-STABLE, APPEND-ONLY.
 *
 *  1. Existing entries NEVER move — even when later payloads flip their flag
 *     verdicts (the original Δ10 freeze guarantee, kept verbatim).
 *  2. Late arrivals APPEND: flagged at the partition boundary, clean at the
 *     tail — judged by THEIR verdict at append time, regardless of payload
 *     position. Totals grow; the R5 counter bump is the only signal.
 *  3. The provider polls ONLY while documents are in flight
 *     (rollup.transcribing > 0 || active_jobs non-empty) and tears the
 *     interval down the tick the condition clears — no residual interval.
 *
 * HISTORY (kept because the failure mode is subtle): the freeze originally
 * lived in a ref inside the PAGE component and was ILLUSORY — the App Router
 * keys page segments by dynamic-param value, so every prev/next REMOUNTED the
 * page and silently recomputed the order from post-accept state (this spec's
 * ancestor caught it live). The holder is the segment LAYOUT
 * (BatchReviewProvider): layouts persist across sibling page navigations and
 * remount on fresh route entry.
 */

/**
 * F1 (closeout) — DEV-SEMANTICS DEPENDENCY, STATED EXPLICITLY.
 *
 * Two tests below assert an EXACT `getBatch` call count, and that count
 * includes React StrictMode's double mount, which `next dev` performs and
 * `next start` does not. Verified against a real production build: the entry
 * pair collapses to a single call (2 → 1).
 *
 * That is not a bug in either mode — the double mount is precisely what makes
 * these assertions valuable in dev (a per-navigation remount would push the
 * count to 10, which is how the illusory page-held freeze was caught). But it
 * means the assertions cannot hold under production semantics, so they declare
 * it rather than quietly passing or being skipped without a trace.
 *
 * The Δ11-under-poll test below does NOT depend on the mount count and runs in
 * both modes.
 */
const DEV_ONLY_MOUNT_COUNT =
    'dev-only: asserts the StrictMode mount PAIR, which next start does not perform';

const PNG_1PX =
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABh6FO1AAAAABJRU5ErkJggg==';

interface FreezeMockState { batchCalls: number }

async function installMocks(
    page: Page,
    payloadFor: (call: number) => unknown,
): Promise<FreezeMockState> {
    const state: FreezeMockState = { batchCalls: 0 };
    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        if (url.includes('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);
        if (url.includes('/api/v0/classroom/students')) {
            return fulfillJson(route, { students: [] });
        }
        if (/\/api\/v0\/transcriptions\/[^/]+\/pages\/\d+/.test(url)) {
            return fulfillJson(route, {
                page_number: Number(url.split('/pages/')[1]),
                thumbnail_base64: PNG_1PX,
            });
        }
        if (url.includes(`/api/v0/batches/${SEED_BATCH_ID}`)) {
            state.batchCalls += 1;
            return fulfillJson(route, payloadFor(state.batchCalls));
        }
        return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' });
    });
    return state;
}

test('prefix-stable: entry order survives arrow navigation and flipped verdicts (no remount, no refetch)', async ({ page }) => {
    test.skip(!!process.env.PW_PROD_BUILD, DEV_ONLY_MOUNT_COUNT);
    await seedAuth(page);

    // Entry: only 'b' flagged → cursor [b | a, c]. No in-flight docs → the
    // OD2 poll must NOT arm. From call 3 on (a remount/recompute symptom),
    // verdicts are FLIPPED — recomputing from that payload would give [a, c | b].
    const entry = () => seedBatch({
        items: [
            seedItem('a', { filename: 'a.pdf' }),
            seedItem('b', { filename: 'b.pdf', reasons: ['low_confidence'] }),
            seedItem('c', { filename: 'c.pdf' }),
        ],
    });
    const flipped = () => seedBatch({
        items: [
            seedItem('a', { filename: 'a.pdf', reasons: ['low_confidence'] }),
            seedItem('b', { filename: 'b.pdf' }),
            seedItem('c', { filename: 'c.pdf', reasons: ['low_confidence'] }),
        ],
    });
    // Dev server runs React StrictMode: the entry effect mounts twice, so the
    // ENTRY payload must cover the first TWO calls.
    const state = await installMocks(page, (call) => (call <= 2 ? entry() : flipped()));

    // Enter at the first item of the entry order (flagged-first → 'b').
    await page.goto(`/batches/${SEED_BATCH_ID}/review/b`);
    await expect(page.getByText('b.pdf')).toBeVisible();
    await expect(page.getByTestId('position-primary')).toHaveText('1 מתוך 1 לעיון');
    await expect(page.getByTestId('position-secondary')).toHaveText('מבחן 1 מתוך 3 במקבץ');

    // b → a (entry order position 2; a reshuffled order would go b → c).
    await page.getByRole('button', { name: 'הבא' }).click();
    await expect(page).toHaveURL(new RegExp(`/batches/${SEED_BATCH_ID}/review/a$`));
    await expect(page.getByText('a.pdf')).toBeVisible();
    // Clean item: the flagged-position primary is OMITTED (R5).
    await expect(page.getByTestId('position-primary')).toHaveCount(0);
    await expect(page.getByTestId('position-secondary')).toHaveText('מבחן 2 מתוך 3 במקבץ');

    // a → c (last item): next becomes the guarded dashboard exit (R8: a
    // button through flushIfDirty, no longer a bare link).
    await page.getByRole('button', { name: 'הבא' }).click();
    await expect(page).toHaveURL(new RegExp(`/batches/${SEED_BATCH_ID}/review/c$`));
    await expect(page.getByTestId('position-secondary')).toHaveText('מבחן 3 מתוך 3 במקבץ');
    await expect(page.getByTestId('exit-to-dashboard')).toBeVisible();

    // c → a → b backwards, still entry order.
    await page.getByRole('button', { name: 'הקודם' }).click();
    await expect(page).toHaveURL(new RegExp(`/batches/${SEED_BATCH_ID}/review/a$`));
    await page.getByRole('button', { name: 'הקודם' }).click();
    await expect(page).toHaveURL(new RegExp(`/batches/${SEED_BATCH_ID}/review/b$`));
    await expect(page.getByTestId('position-primary')).toHaveText('1 מתוך 1 לעיון');

    // The remount detector: one StrictMode mount pair, nothing more — and no
    // poll (nothing in flight). A remount per arrow would push this to 10.
    expect(state.batchCalls).toBe(2);
});

test('append-only: late arrivals join at the boundary (flagged) and tail (clean); poll dies with the condition', async ({ page }) => {
    test.skip(!!process.env.PW_PROD_BUILD, DEV_ONLY_MOUNT_COUNT);
    await seedAuth(page);

    // Entry: [b | a] with two docs still in flight → the poll ARMS.
    const entry = () => seedBatch({
        items: [
            seedItem('a', { filename: 'a.pdf' }),
            seedItem('b', { filename: 'b.pdf', reasons: ['low_confidence'] }),
        ],
        rollup: { transcribing: 2, total: 4 },
        activeJobs: [seedActiveJob({ filename: 'in-flight.pdf', state: 'running' })],
    });
    // First poll payload: d (flagged) + e (clean) have landed; nothing left in
    // flight → the poll must tear down after this tick. Payload order is
    // SHUFFLED (e, d first) to prove placement comes from the verdict rule,
    // not payload position — and that a, b keep their slots.
    const appended = () => seedBatch({
        items: [
            seedItem('e', { filename: 'e.pdf' }),
            seedItem('d', { filename: 'd.pdf', reasons: ['missing_answers'] }),
            seedItem('a', { filename: 'a.pdf' }),
            seedItem('b', { filename: 'b.pdf', reasons: ['low_confidence'] }),
        ],
        rollup: { transcribing: 0, total: 4 },
        activeJobs: [],
    });
    const state = await installMocks(page, (call) => (call <= 2 ? entry() : appended()));

    await page.goto(`/batches/${SEED_BATCH_ID}/review/b`);
    await expect(page.getByTestId('position-primary')).toHaveText('1 מתוך 1 לעיון');
    await expect(page.getByTestId('position-secondary')).toHaveText('מבחן 1 מתוך 2 במקבץ');

    // The poll (5s) merges the arrivals: existing prefix untouched, counters
    // bump — the ONLY signal (OD2). b keeps slot 1 of a now-2-wide flagged
    // partition; the batch total grows 2 → 4.
    await expect(page.getByTestId('position-primary')).toHaveText('1 מתוך 2 לעיון', { timeout: 10_000 });
    await expect(page.getByTestId('position-secondary')).toHaveText('מבחן 1 מתוך 4 במקבץ');

    // Placement proof: b's NEXT is the appended flagged 'd' (boundary insert),
    // not the entry-order clean 'a'.
    await page.getByRole('button', { name: 'הבא' }).click();
    await expect(page).toHaveURL(new RegExp(`/review/d$`));
    await expect(page.getByTestId('position-primary')).toHaveText('2 מתוך 2 לעיון');

    // d → a (the entry clean, undisturbed) → e (the appended clean, at the tail).
    await page.getByRole('button', { name: 'הבא' }).click();
    await expect(page).toHaveURL(new RegExp(`/review/a$`));
    await page.getByRole('button', { name: 'הבא' }).click();
    await expect(page).toHaveURL(new RegExp(`/review/e$`));
    await expect(page.getByTestId('position-secondary')).toHaveText('מבחן 4 מתוך 4 במקבץ');
    await expect(page.getByTestId('exit-to-dashboard')).toBeVisible();

    // Poll teardown: the tick that delivered transcribing=0 must be the LAST
    // fetch — entry StrictMode pair (2) + one poll tick = 3, and 6.5 more
    // seconds must add nothing (no residual interval; navigation refetches
    // nothing).
    expect(state.batchCalls).toBe(3);
    await page.waitForTimeout(6_500);
    expect(state.batchCalls).toBe(3);
});

test('Δ11 under the OD2 poll — a poll tick landing mid-edit never clobbers the teacher\'s text (P3-review item 2)', async ({ page }) => {
    await seedAuth(page);

    // The item under edit, with the batch still transcribing → the poll runs
    // CONTINUOUSLY while the teacher types. Poll payloads are CLOBBER BAIT:
    // the same item id returns different draft text AND a server overlay —
    // if any layer of the rewrite (mergePayload → setBatch → re-render →
    // maybeRehydrate) re-hydrated on a same-id refresh, either would
    // overwrite the in-progress edit.
    const entry = () => seedBatch({
        items: [seedItem('b', {
            filename: 'b.pdf',
            reasons: ['low_confidence'],
            draft: { answers: [{ question_number: 1, sub_question_id: null, answer_text: 'טיוטת שרת v1', confidence: 0.9, page_numbers: [1] }] },
        })],
        rollup: { transcribing: 1, total: 2 },
        activeJobs: [seedActiveJob({ filename: 'in-flight.pdf', state: 'running' })],
    });
    const bait = () => seedBatch({
        items: [seedItem('b', {
            filename: 'b.pdf',
            reasons: ['low_confidence'],
            draft: { answers: [{ question_number: 1, sub_question_id: null, answer_text: 'טיוטת שרת v2 — פתיון דריסה', confidence: 0.9, page_numbers: [1] }] },
            review: {
                schema_version: '1.0',
                answers: [{ question_number: 1, sub_question_id: null, answer_text: 'אוברליי שרת — פתיון דריסה' }],
                student_id: null,
                updated_at: '2026-08-18T10:00:00Z',
            },
        })],
        rollup: { transcribing: 1, total: 2 },   // still in flight → poll keeps running
        activeJobs: [seedActiveJob({ filename: 'in-flight.pdf', state: 'running' })],
    });
    const state = await installMocks(page, (call) => (call <= 2 ? entry() : bait()));

    await page.goto(`/batches/${SEED_BATCH_ID}/review/b`);
    const editor = page.getByTestId('transcription-editor');
    await expect(editor).toHaveValue('טיוטת שרת v1');

    // Type the half-finished correction, then let TWO poll ticks land on it.
    await editor.fill('תיקון באמצע הקלדה');
    await expect(page.getByText('שינויים לא שמורים')).toBeVisible();

    // Wait for TWO poll ticks to land ON the edit — expressed relative to the
    // entry calls, not as an absolute number. The absolute `>= 4` this
    // replaced silently encoded the StrictMode mount PAIR (dev: 2 entry + 2
    // polls; prod: 1 entry + 2 polls = 3), so it failed under `next start`
    // for arithmetic reasons while testing nothing about production. F1 found
    // it: a spec can depend on dev semantics without ever mentioning them.
    const callsBeforeEdit = state.batchCalls;
    await expect
        .poll(() => state.batchCalls, { timeout: 20_000 })
        .toBeGreaterThanOrEqual(callsBeforeEdit + 2);

    // The edit survived every tick; the item is still honestly dirty; no
    // bait text leaked in from either the new draft or the server overlay.
    await expect(editor).toHaveValue('תיקון באמצע הקלדה');
    await expect(page.getByText('שינויים לא שמורים')).toBeVisible();
});
