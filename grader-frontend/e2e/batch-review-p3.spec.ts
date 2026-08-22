import { expect, test, type Page } from '@playwright/test';
import { seedAuth } from './fixtures';
import {
    AUTH_ME,
    fulfillJson,
    SEED_BATCH_ID,
    seedBatch,
    seedItem,
    type SeedItemOpts,
} from './seedBatch';

/**
 * P3 — the review-module journeys (spec §8):
 *  - keyboard-only-walk (§4.3 + R3/R4/R9): a 3-flagged batch completed with
 *    ArrowLeft/ArrowRight/Enter/Esc only — focus asserted after every item
 *    switch, modal autofocus, auto-advance targets, the interstitial, the
 *    bulk-with-skip handoff, and the dashboard notice.
 *  - clean-walk (R12/AM1): בדיקה ידנית enters at the first clean; accepting a
 *    clean advances to the next clean (never into the flagged partition);
 *    the last clean exits to the dashboard.
 *  - reason-anchors (R1): chips scroll+pulse the first relevant card, resolve
 *    against CURRENT text (a fixed [?] chip shakes instead of scrolling
 *    nowhere), and student chips focus the picker.
 *  - modal-a11y (R9): role=dialog, aria-modal, focus trap wrap in both
 *    directions, Esc.
 *  - scan-zoom (R10): computed transform steps 1 → 1.35 → 1.8 → 1.35;
 *    bounds disable the buttons.
 *  - accept-refetch-decoupling (R11): accept-200 + refetch-500 → the item
 *    stays accepted, the advance still runs, and the provider-held soft note
 *    survives the route.replace (never re-reported as an accept error).
 *  - exit-flush (R8): a dirty edit + the dashboard exit button → the overlay
 *    PATCH lands BEFORE navigation.
 */

const PNG_1PX =
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABh6FO1AAAAABJRU5ErkJggg==';

interface P3ItemSpec {
    id: string;
    opts?: SeedItemOpts;
}

interface P3MockState {
    accepted: Set<string>;
    overlays: Map<string, unknown>;
    patchBodies: Array<{ txId: string; body: Record<string, unknown> }>;
    acceptCalls: string[];
    acceptCleanBodies: Array<{ items: Array<{ transcription_id: string; student_id: string }> }>;
    /** R11: when true, GET batch returns 500 (accept POSTs still succeed). */
    refetchFail: boolean;
    /** Response the accept_clean endpoint returns (per-test). */
    acceptCleanResponse: { accepted: number; skipped: Array<{ transcription_id: string; skipped_reason: string }> };
}

function buildPayload(state: P3MockState, specs: P3ItemSpec[]) {
    return seedBatch({
        items: specs.map(({ id, opts }) => {
            const accepted = state.accepted.has(id);
            const reasons = accepted ? [] : (opts?.reasons ?? []);
            return seedItem(id, {
                ...opts,
                status: accepted ? 'approved' : (opts?.status ?? 'transcribed'),
                reasons,
                review: (state.overlays.get(id) as Record<string, unknown> | undefined) ?? opts?.review ?? null,
            });
        }),
    });
}

async function installMocks(page: Page, specs: P3ItemSpec[]): Promise<P3MockState> {
    const state: P3MockState = {
        accepted: new Set(),
        overlays: new Map(),
        patchBodies: [],
        acceptCalls: [],
        acceptCleanBodies: [],
        refetchFail: false,
        acceptCleanResponse: { accepted: 0, skipped: [] },
    };

    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        const method = route.request().method();

        if (url.includes('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);
        if (url.includes('/api/v0/classroom/students')) {
            return fulfillJson(route, {
                students: [{ id: 's1', full_name: 'רז כהן', notes: null, created_at: '2026-01-01T00:00:00Z' }],
            });
        }
        const patchMatch = url.match(/\/api\/v0\/transcriptions\/([^/]+)\/review/);
        if (patchMatch && method === 'PATCH') {
            const body = route.request().postDataJSON() as Record<string, unknown>;
            const review = {
                schema_version: '1.0',
                answers: body.answers,
                student_id: body.student_id ?? null,
                updated_at: '2026-08-18T10:00:00Z',
            };
            state.patchBodies.push({ txId: patchMatch[1], body });
            state.overlays.set(patchMatch[1], review);
            return fulfillJson(route, review);
        }
        if (method === 'POST' && url.includes('/accept_clean')) {
            const body = route.request().postDataJSON() as P3MockState['acceptCleanBodies'][number];
            state.acceptCleanBodies.push(body);
            return fulfillJson(route, state.acceptCleanResponse);
        }
        const acceptMatch = url.match(/\/api\/v0\/batches\/[^/]+\/accept\/([^/?]+)/);
        if (acceptMatch && method === 'POST') {
            state.accepted.add(acceptMatch[1]);
            state.acceptCalls.push(acceptMatch[1]);
            return fulfillJson(route, { accepted: 1 });
        }
        if (url.includes(`/api/v0/batches/${SEED_BATCH_ID}`)) {
            if (state.refetchFail) {
                return fulfillJson(route, { detail: 'boom' }, 500);
            }
            return fulfillJson(route, buildPayload(state, specs));
        }
        if (/\/api\/v0\/transcriptions\/[^/]+\/pages\/\d+/.test(url)) {
            return fulfillJson(route, {
                page_number: Number(url.split('/pages/')[1]),
                thumbnail_base64: PNG_1PX,
            });
        }
        return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' });
    });

    return state;
}

const matched = { matchedStudentId: 's1', matchedStudentName: 'רז כהן' };

test('keyboard-only-walk — arrows, modal trap, approve ×3, interstitial, bulk-with-skip, dashboard notice', async ({ page }) => {
    await seedAuth(page);
    const state = await installMocks(page, [
        { id: 'f1', opts: { reasons: ['low_confidence'], ...matched } },
        { id: 'f2', opts: { reasons: ['missing_answers'], ...matched } },
        { id: 'f3', opts: { reasons: ['unparseable'], ...matched } },
        { id: 'c1', opts: { ...matched } },
    ]);
    state.acceptCleanResponse = {
        accepted: 0,
        skipped: [{ transcription_id: 'c1', skipped_reason: 'has_review_edits' }],
    };

    // Enter from the dashboard's סבב עיון — keyboard, not mouse.
    await page.goto(`/batches/${SEED_BATCH_ID}`);
    const entry = page.getByRole('link', { name: /התחילי סבב עיון/ });
    await entry.focus();
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/\/review\/f1$/);
    await expect(page.getByTestId('review-main')).toBeFocused();

    // Arrow navigation: ArrowLeft = הבא (RTL), ArrowRight = הקודם; the main
    // region takes focus after every switch.
    await page.keyboard.press('ArrowLeft');
    await expect(page).toHaveURL(/\/review\/f2$/);
    await expect(page.getByTestId('review-main')).toBeFocused();
    await page.keyboard.press('ArrowRight');
    await expect(page).toHaveURL(/\/review\/f1$/);
    await expect(page.getByTestId('review-main')).toBeFocused();

    // Enter → modal (autofocus on the primary); Esc declines; Enter+Enter approves.
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('confirm-accept-modal')).toBeVisible();
    await expect(page.getByTestId('confirm-accept-primary')).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('confirm-accept-modal')).toBeHidden();
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('confirm-accept-primary')).toBeFocused();
    await page.keyboard.press('Enter');

    // R4 auto-advance: f1 → f2 (next unapproved flagged), focus re-landed.
    await expect(page).toHaveURL(/\/review\/f2$/);
    await expect(page.getByTestId('review-main')).toBeFocused();
    await expect(page.getByTestId('position-primary')).toHaveText('2 מתוך 3 לעיון');

    await page.keyboard.press('Enter');
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/\/review\/f3$/);
    await expect(page.getByTestId('review-main')).toBeFocused();

    // Last flagged approved → the interstitial, with the honest counts and
    // autofocus on the bulk primary (AM3 singular: one clean remains).
    await page.keyboard.press('Enter');
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('review-interstitial')).toBeVisible();
    await expect(page.getByText('כל המבחנים שסומנו נבדקו')).toBeVisible();
    await expect(page.getByText('נשאר מבחן נקי אחד — לאשר אותו?')).toBeVisible();
    await expect(page.getByTestId('interstitial-bulk')).toBeFocused();
    await expect(page.getByTestId('interstitial-bulk')).toHaveText('אשרי את המבחן (1)');
    expect(state.acceptCalls).toEqual(['f1', 'f2', 'f3']);

    // Enter → bulk accept_clean; the server skips c1 → the notice lands ON
    // THE DASHBOARD (decision 2: one-shot sessionStorage handoff), never a
    // stranding in a closed modal.
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(new RegExp(`/batches/${SEED_BATCH_ID}$`));
    await expect(page.getByText('מבחן אחד דולג — נערכו ידנית. הוא ממתין לעיון.')).toBeVisible();
    expect(state.acceptCleanBodies).toHaveLength(1);
    expect(state.acceptCleanBodies[0].items).toEqual([{ transcription_id: 'c1', student_id: 's1' }]);
});

test('clean-walk (R12) — בדיקה ידנית enters at the first clean; accepts advance clean→clean→dashboard, never into flagged', async ({ page }) => {
    await seedAuth(page);
    await installMocks(page, [
        { id: 'f1', opts: { reasons: ['low_confidence'], ...matched } },
        { id: 'c1', opts: { ...matched } },
        { id: 'c2', opts: { ...matched } },
    ]);

    await page.goto(`/batches/${SEED_BATCH_ID}`);
    await page.getByRole('link', { name: 'בדיקה ידנית' }).click();
    await expect(page).toHaveURL(/\/review\/c1$/);

    // Clean item: no flagged-position primary; whole-batch secondary only.
    await expect(page.getByTestId('position-primary')).toHaveCount(0);
    await expect(page.getByTestId('position-secondary')).toHaveText('מבחן 2 מתוך 3 במקבץ');

    // Accept c1 → the walk stays in the CLEAN partition: c2, not f1.
    await page.getByRole('button', { name: 'אישור תמלול' }).first().click();
    await page.getByTestId('confirm-accept-primary').click();
    await expect(page).toHaveURL(/\/review\/c2$/);

    // Accept the last clean → the dashboard (no terminal claim ⇒ no interstitial).
    await page.getByRole('button', { name: 'אישור תמלול' }).first().click();
    await page.getByTestId('confirm-accept-primary').click();
    await expect(page).toHaveURL(new RegExp(`/batches/${SEED_BATCH_ID}$`));
});

test('reason-anchors (R1) — chips pulse the first relevant card, shake when the target was fixed, focus the picker', async ({ page }) => {
    await seedAuth(page);
    await installMocks(page, [
        {
            id: 't1',
            opts: {
                reasons: ['missing_answers', 'unparseable', 'student_unmatched'],
                draft: {
                    answers: [
                        { question_number: 1, sub_question_id: null, answer_text: 'x = [?] + 1', confidence: 0.9, page_numbers: [1] },
                        { question_number: 2, sub_question_id: null, answer_text: 'תשובה מלאה', confidence: 0.95, page_numbers: [1] },
                        { question_number: 3, sub_question_id: null, answer_text: '', confidence: 0, page_numbers: [] },
                    ],
                },
            },
        },
    ]);

    await page.goto(`/batches/${SEED_BATCH_ID}/review/t1`);
    await expect(page.getByTestId('reason-rail')).toBeVisible();
    await expect(page.getByText('סומן בגלל:')).toBeVisible();

    // unparseable → the first card whose CURRENT text holds a [?].
    await page.getByTestId('reason-chip-unparseable').click();
    await expect(page.locator('[data-answer-key="q1"]')).toHaveClass(/animate-anchor-pulse/);

    // missing_answers → the first empty-unexplained card (q3 — which also
    // wears the R2 amber marker).
    await page.getByTestId('reason-chip-missing_answers').click();
    await expect(page.locator('[data-answer-key="q3"]')).toHaveClass(/animate-anchor-pulse/);
    await expect(page.locator('[data-answer-key="q3"]').getByTestId('empty-answer-marker')).toBeVisible();

    // Fix the [?] → the chip stays (entry-frozen, past tense) but the anchor
    // honestly dissolves: click no-ops with a shake, no scroll target.
    await page.locator('[data-answer-key="q1"] textarea').fill('x = 5 + 1');
    await page.getByTestId('reason-chip-unparseable').click();
    await expect(page.getByTestId('reason-chip-unparseable')).toHaveClass(/animate-shake/);

    // student_* → the picker takes focus.
    await page.getByTestId('reason-chip-student_unmatched').click();
    await expect(page.locator('[data-student-picker] input').first()).toBeFocused();
});

test('modal-a11y (R9) — dialog semantics, focus trap wraps both directions, Esc closes', async ({ page }) => {
    await seedAuth(page);
    await installMocks(page, [
        { id: 'f1', opts: { reasons: ['low_confidence'], ...matched } },
    ]);

    await page.goto(`/batches/${SEED_BATCH_ID}/review/f1`);
    await page.getByRole('button', { name: 'אישור תמלול' }).first().click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveAttribute('aria-modal', 'true');

    // Initial focus on the primary (last focusable) → Tab wraps to the first
    // (the close X); Shift+Tab wraps back to the last.
    await expect(page.getByTestId('confirm-accept-primary')).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(dialog.getByRole('button', { name: 'סגירה' })).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await expect(page.getByTestId('confirm-accept-primary')).toBeFocused();

    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
});

test('scan-zoom (R10) — transform steps 1 → 1.35 → 1.8 with bounds; container pans', async ({ page }) => {
    await seedAuth(page);
    await installMocks(page, [
        { id: 'c1', opts: { ...matched } },
    ]);

    await page.goto(`/batches/${SEED_BATCH_ID}/review/c1`);
    const content = page.getByTestId('scan-zoom-content');
    await expect(content).toBeVisible();
    await expect(content).toHaveCSS('transform', 'none');
    await expect(page.getByTestId('zoom-out')).toBeDisabled();

    await page.getByTestId('zoom-in').click();
    await expect(content).toHaveCSS('transform', 'matrix(1.35, 0, 0, 1.35, 0, 0)');

    await page.getByTestId('zoom-in').click();
    await expect(content).toHaveCSS('transform', 'matrix(1.8, 0, 0, 1.8, 0, 0)');
    await expect(page.getByTestId('zoom-in')).toBeDisabled();

    await page.getByTestId('zoom-out').click();
    await expect(content).toHaveCSS('transform', 'matrix(1.35, 0, 0, 1.35, 0, 0)');
});

test('accept-refetch-decoupling (R11) — accept-200 + refetch-500: accepted stands, advance runs, soft note survives the advance', async ({ page }) => {
    await seedAuth(page);
    const state = await installMocks(page, [
        { id: 'f1', opts: { reasons: ['low_confidence'], ...matched } },
        { id: 'f2', opts: { reasons: ['missing_answers'], ...matched } },
    ]);

    await page.goto(`/batches/${SEED_BATCH_ID}/review/f1`);
    await expect(page.getByTestId('position-primary')).toHaveText('1 מתוך 2 לעיון');

    // The accept succeeds; the refetch right after it fails.
    state.refetchFail = true;
    await page.getByRole('button', { name: 'אישור תמלול' }).first().click();
    await page.getByTestId('confirm-accept-primary').click();

    // R4 still advanced (stale snapshot + the accepted override), and the
    // PROVIDER-held soft note survived the route.replace (decision 3).
    await expect(page).toHaveURL(/\/review\/f2$/);
    await expect(page.getByTestId('soft-refetch-note')).toHaveText('הרענון נכשל — הנתונים יתעדכנו בהמשך');
    await expect(page.getByText('שגיאה באישור התמלול')).toHaveCount(0);
    expect(state.acceptCalls).toEqual(['f1']);
});

test('exit-flush (R8) — a dirty edit + the dashboard exit flushes the overlay BEFORE navigating', async ({ page }) => {
    await seedAuth(page);
    const state = await installMocks(page, [
        { id: 'c1', opts: { ...matched } },
    ]);

    await page.goto(`/batches/${SEED_BATCH_ID}/review/c1`);
    await page.getByTestId('transcription-editor').fill('עריכה לפני יציאה');
    await expect(page.getByText('שינויים לא שמורים')).toBeVisible();

    await page.getByTestId('exit-to-dashboard').click();
    await expect(page).toHaveURL(new RegExp(`/batches/${SEED_BATCH_ID}$`));

    expect(state.patchBodies).toHaveLength(1);
    expect(state.patchBodies[0].txId).toBe('c1');
    const answers = state.patchBodies[0].body.answers as Array<{ answer_text: string }>;
    expect(answers[0].answer_text).toBe('עריכה לפני יציאה');
});
