import { expect, test, type Page } from '@playwright/test';
import { seedAuth } from './fixtures';
import {
    AUTH_ME,
    fulfillJson,
    minutesAgo,
    SEED_BATCH_ID,
    seedActiveJob,
    seedBatch,
    seedItem,
    steadyBatch,
} from './seedBatch';

/**
 * P2 wave 3 — dashboard behavior journeys:
 *   1. Identity wave: edit a pill → bulk create (201s + one 409-as-resolved)
 *      → the NEXT POLL converges items into the clean panel; a mixed
 *      identity+content item stays in needs-eyes (D4's named edge).
 *   2. Rename round-trip: optimistic apply, server confirm; failure reverts
 *      with the server's Hebrew detail inline (D1/B5).
 *   3. Reduced motion kills shimmer/spin (computed-style, D2).
 *   4. D12 cadence: 3s while decisions pend → stop when nothing moves; a 401
 *      is TERMINAL (stop + leave).
 */

// ---------------------------------------------------------------------------
// 1 · Identity wave → convergence
// ---------------------------------------------------------------------------

function waveBatchV1() {
    return seedBatch({
        items: [
            seedItem('t1', { suggestion: 'נועה שריד', reasons: ['student_unassigned'] }),
            seedItem('t2', { suggestion: 'איתי כהן', reasons: ['student_unassigned'] }),
            seedItem('t3', {
                suggestion: 'רוני אלקיים',
                reasons: ['student_unassigned', 'unparseable'],
                draft: {
                    answers: [{
                        question_number: 1, sub_question_id: null,
                        answer_text: 'x = [?]', confidence: 0.9, page_numbers: [1],
                    }],
                },
            }),
        ],
        rollup: { total: 3 },
    });
}

function waveBatchV2() {
    return seedBatch({
        items: [
            seedItem('t1', {
                suggestion: 'נועה שריד-מתוקן', matchedStudentId: 's1',
                matchedStudentName: 'נועה שריד-מתוקן',
            }),
            seedItem('t2', {
                suggestion: 'איתי כהן', matchedStudentId: 's2', matchedStudentName: 'איתי כהן',
            }),
            seedItem('t3', {
                suggestion: 'רוני אלקיים', matchedStudentId: 's3',
                matchedStudentName: 'רוני אלקיים',
                reasons: ['unparseable'],
                draft: {
                    answers: [{
                        question_number: 1, sub_question_id: null,
                        answer_text: 'x = [?]', confidence: 0.9, page_numbers: [1],
                    }],
                },
            }),
        ],
        rollup: { total: 3 },
    });
}

test('identity wave: pill edit → bulk create → poll convergence; mixed item stays', async ({ page }) => {
    await seedAuth(page);

    const studentPosts: string[] = [];
    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        const method = route.request().method();
        if (url.includes('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);

        if (method === 'POST' && url.includes('/api/v0/classroom/students')) {
            const body = route.request().postDataJSON() as { full_name: string };
            studentPosts.push(body.full_name);
            if (body.full_name === 'איתי כהן') {
                return fulfillJson(route, { detail: 'כבר קיים תלמיד בשם זה' }, 409);
            }
            return fulfillJson(route, { id: `s-${studentPosts.length}`, full_name: body.full_name }, 201);
        }

        if (url.includes(`/api/v0/batches/${SEED_BATCH_ID}`)) {
            // Converge once the bulk has landed (server recomputes vs live roster).
            return fulfillJson(route, studentPosts.length >= 2 ? waveBatchV2() : waveBatchV1());
        }
        return fulfillJson(route, {});
    });

    await page.goto(`/batches/${SEED_BATCH_ID}`);

    // The wave leads (cold start): headline + 3 pills.
    await expect(page.getByTestId('zone-identity-wave')).toBeVisible();
    await expect(page.getByTestId('headline')).toContainText('ויוי זיהתה 3 תלמידים חדשים');

    // Fix a spelling IN PLACE — the bulk must post the CURRENT value.
    const pill = page.getByTestId('pill-נועה שריד').locator('input');
    await pill.fill('נועה שריד-מתוקן');

    await page.getByTestId('wave-bulk-create').click();

    // Per-pill outcomes: two created, the conflict resolves as "already exists".
    await expect(page.getByTestId('pill-נועה שריד')).toHaveAttribute('data-status', 'done');
    await expect(page.getByTestId('pill-איתי כהן')).toHaveAttribute('data-status', 'conflict');
    await expect(page.getByText('כבר קיים תלמיד בשם זה')).toBeVisible();
    expect(studentPosts).toContain('נועה שריד-מתוקן');   // the edited value, not the suggestion

    // Convergence is the POLL's job: clean rows appear; the wave dissolves.
    await expect(page.getByTestId('zone-clean')).toBeVisible();
    await expect(page.getByTestId('clean-row')).toHaveCount(2);
    await expect(page.getByTestId('zone-identity-wave')).toBeHidden();

    // D4 named edge: the mixed identity+content item DROPPED only its identity
    // chip — it remains in needs-eyes with its content reason.
    const eyes = page.getByTestId('zone-eyes');
    await expect(eyes).toBeVisible();
    await expect(eyes).toContainText('רוני אלקיים');
    await expect(eyes).toContainText('תוכן לא קריא [?] · 1');
});

// ---------------------------------------------------------------------------
// 2 · Rename round-trip + revert-on-failure
// ---------------------------------------------------------------------------

test('rename: optimistic apply + server confirm; failure reverts with Hebrew detail', async ({ page }) => {
    await seedAuth(page);

    let renameCalls = 0;
    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        const method = route.request().method();
        if (url.includes('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);

        if (method === 'PATCH' && url.includes(`/api/v0/batches/${SEED_BATCH_ID}`)) {
            renameCalls += 1;
            const body = route.request().postDataJSON() as { name: string };
            if (renameCalls === 1) {
                return fulfillJson(route, { batch_id: SEED_BATCH_ID, name: body.name });
            }
            return fulfillJson(route, { detail: 'שם המקבץ ארוך מדי (עד 255 תווים)' }, 422);
        }
        if (url.includes(`/api/v0/batches/${SEED_BATCH_ID}`)) {
            return fulfillJson(route, steadyBatch());
        }
        return fulfillJson(route, {});
    });

    await page.goto(`/batches/${SEED_BATCH_ID}`);
    await expect(page.getByRole('heading', { name: 'מקבץ בדיקה' })).toBeVisible();

    // Happy path: pencil → edit → Enter → applied.
    await page.getByTestId('rename-pencil').click();
    await page.getByTestId('rename-input').fill('מתכונת 1 · יא׳3');
    await page.getByTestId('rename-input').press('Enter');
    await expect(page.getByRole('heading', { name: 'מתכונת 1 · יא׳3' })).toBeVisible();

    // Failure path: optimistic value REVERTS + the server's detail shows.
    await page.getByTestId('rename-pencil').click();
    await page.getByTestId('rename-input').fill('שם שיפול בשרת');
    await page.getByTestId('rename-input').press('Enter');
    await expect(page.getByRole('heading', { name: 'מתכונת 1 · יא׳3' })).toBeVisible();
    await expect(page.getByText('שם המקבץ ארוך מדי (עד 255 תווים)')).toBeVisible();
});

// ---------------------------------------------------------------------------
// 3 · Reduced motion (D2/D7)
// ---------------------------------------------------------------------------

async function installStatic(page: Page, payload: unknown) {
    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        if (url.includes('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);
        if (url.includes(`/api/v0/batches/${SEED_BATCH_ID}`)) return fulfillJson(route, payload);
        return fulfillJson(route, {});
    });
}

test('reduced motion kills shimmer and spinner animations', async ({ page }) => {
    await seedAuth(page);
    await installStatic(page, steadyBatch());

    // Baseline sanity: WITH motion the shimmer animates.
    await page.goto(`/batches/${SEED_BATCH_ID}`);
    await expect(page.getByTestId('ghost-row').first()).toBeVisible();
    const animated = await page.getByTestId('segment-bar')
        .locator('[data-kind="moving"]')
        .evaluate((el) => getComputedStyle(el).animationName);
    expect(animated).not.toBe('none');

    // Under prefers-reduced-motion: every batch animation is off.
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.reload();
    await expect(page.getByTestId('ghost-row').first()).toBeVisible();
    const reduced = await page.getByTestId('segment-bar')
        .locator('[data-kind="moving"]')
        .evaluate((el) => getComputedStyle(el).animationName);
    expect(reduced).toBe('none');
    const spinner = await page.getByTestId('ghost-row').first()
        .locator('span').first()
        .evaluate((el) => getComputedStyle(el).animationName);
    expect(spinner).toBe('none');
});

// ---------------------------------------------------------------------------
// 4 · D12 — cadence stops when nothing moves; 401 is terminal
// ---------------------------------------------------------------------------

test('polling stops when every state is terminal', async ({ page }) => {
    await seedAuth(page);

    let batchCalls = 0;
    const terminal = seedBatch({
        status: 'completed',
        items: [
            seedItem('t1', { status: 'approved' }),
            seedItem('t2', { status: 'approved' }),
        ],
        rollup: { approved: 2, total: 2 },
        activeJobs: [],
    });
    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        if (url.includes('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);
        if (url.includes(`/api/v0/batches/${SEED_BATCH_ID}`)) {
            batchCalls += 1;
            return fulfillJson(route, terminal);
        }
        return fulfillJson(route, {});
    });

    await page.goto(`/batches/${SEED_BATCH_ID}`);
    await expect(page.getByTestId('completion-hero')).toBeVisible();
    const settled = batchCalls;                      // entry fetch (+StrictMode pair)
    await page.waitForTimeout(7000);                 // two would-be 3s ticks
    expect(batchCalls).toBe(settled);                // cadence: STOP
});

test('a 401 mid-poll is terminal: polling stops and the page leaves', async ({ page }) => {
    await seedAuth(page);

    let batchCalls = 0;
    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        if (url.includes('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);
        if (url.includes(`/api/v0/batches/${SEED_BATCH_ID}`)) {
            batchCalls += 1;
            if (batchCalls <= 2) return fulfillJson(route, steadyBatch());
            return fulfillJson(route, { detail: 'Not authenticated' }, 401);
        }
        return fulfillJson(route, {});
    });

    await page.goto(`/batches/${SEED_BATCH_ID}`);
    await expect(page.getByRole('heading', { name: 'מקבץ בדיקה' })).toBeVisible();

    // The poll hits the 401 → the page navigates home and polling ends.
    await expect(page).toHaveURL(/\/$/, { timeout: 15_000 });
    const after = batchCalls;
    await page.waitForTimeout(4000);
    expect(batchCalls).toBe(after);
});

// ---------------------------------------------------------------------------
// 6 · D5 bulk accept — the F4 proof (P2-review item 2): server `skipped` is
//     surfaced VERBATIM; optimistic dimming; reconciliation by the poll.
// ---------------------------------------------------------------------------

test('D5 bulk accept: skipped surfaced verbatim, dimming, poll reconciliation', async ({ page }) => {
    await seedAuth(page);

    const v1 = seedBatch({
        items: [
            seedItem('t1', { matchedStudentId: 's1', matchedStudentName: 'דנה לוי' }),
            seedItem('t2', { matchedStudentId: 's2', matchedStudentName: 'יובל כץ' }),
            seedItem('t3', { reasons: ['unparseable'] }),
        ],
        rollup: { total: 3 },
    });
    // Post-accept truth: t1 approved; t2 flipped flagged between render and
    // POST (the exact race B1 guards) — the server SKIPPED it; t3 unchanged.
    const v2 = seedBatch({
        items: [
            seedItem('t1', { status: 'approved', gradedTestStatus: 'grading' }),
            seedItem('t2', {
                matchedStudentId: 's2', matchedStudentName: 'יובל כץ',
                reasons: ['missing_answers'],
                draft: { answers: [{ question_number: 1, sub_question_id: null, answer_text: '', confidence: 0, page_numbers: [] }] },
            }),
            seedItem('t3', { reasons: ['unparseable'] }),
        ],
        rollup: { total: 3, grading: 1 },
    });

    let accepted = false;
    let acceptBody: { items?: Array<{ transcription_id: string; student_id: string }> } = {};
    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        const method = route.request().method();
        if (url.includes('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);
        if (method === 'POST' && url.includes('/accept_clean')) {
            acceptBody = route.request().postDataJSON();
            accepted = true;
            await new Promise((r) => setTimeout(r, 800));   // hold in-flight for the dimming assert
            return fulfillJson(route, {
                accepted: 1,
                skipped: [{ transcription_id: 't2', skipped_reason: 'flagged' }],
            });
        }
        if (url.includes(`/api/v0/batches/${SEED_BATCH_ID}`)) {
            return fulfillJson(route, accepted ? v2 : v1);
        }
        return fulfillJson(route, {});
    });

    await page.goto(`/batches/${SEED_BATCH_ID}`);
    await expect(page.getByTestId('clean-accept-all')).toHaveText('אשרי את כולם (2)');

    await page.getByTestId('clean-accept-all').click();

    // Optimistic dimming while the POST is held: both clean rows dim, keyed by id.
    await expect(page.locator('.opacity-45')).toHaveCount(2);

    // The wire carried exactly the matched clean pair.
    await expect.poll(() => acceptBody.items?.length).toBe(2);
    expect(acceptBody.items).toEqual([
        { transcription_id: 't1', student_id: 's1' },
        { transcription_id: 't2', student_id: 's2' },
    ]);

    // F4: the server's skip is surfaced VERBATIM (AM3 singular form).
    await expect(page.getByTestId('clean-skip-notice')).toHaveText(
        'מבחן אחד דולג — סומנו לעיון. הוא ממתין לעיון.',
    );

    // Reconciliation by the refetch: t1 approved (gone), t2 now a needs-eyes
    // row — the clean panel keeps ONLY the notice (zero rows, no dimming left).
    await expect(page.getByTestId('clean-row')).toHaveCount(0);
    await expect(page.locator('.opacity-45')).toHaveCount(0);
    const eyesRows = page.getByTestId('eyes-row');
    await expect(eyesRows).toHaveCount(2);
    await expect(eyesRows.filter({ hasText: 'יובל כץ' })).toHaveCount(1);
});

// ---------------------------------------------------------------------------
// 7 · D7 ghost→row — a finishing document lands as a highlighted real row on
//     the next poll (P2-review item 2).
// ---------------------------------------------------------------------------

test('D7: a finishing ghost becomes a highlighted clean row on the next poll', async ({ page }) => {
    await seedAuth(page);

    const v1 = seedBatch({
        items: [seedItem('t1', { matchedStudentId: 's1', matchedStudentName: 'דנה לוי' })],
        rollup: { total: 2, transcribing: 1 },
        activeJobs: [seedActiveJob({
            filename: 'חדש.pdf', state: 'running',
            started_at: minutesAgo(1), attempt_count: 1,
        })],
    });
    const v2 = seedBatch({
        items: [
            seedItem('t1', { matchedStudentId: 's1', matchedStudentName: 'דנה לוי' }),
            seedItem('tNew', {
                filename: 'חדש.pdf',
                matchedStudentId: 's9', matchedStudentName: 'עומר גלבר',
            }),
        ],
        rollup: { total: 2, transcribing: 0 },
        activeJobs: [],
    });

    let batchCalls = 0;
    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        if (url.includes('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);
        if (url.includes(`/api/v0/batches/${SEED_BATCH_ID}`)) {
            batchCalls += 1;
            return fulfillJson(route, batchCalls <= 2 ? v1 : v2);
        }
        return fulfillJson(route, {});
    });

    await page.goto(`/batches/${SEED_BATCH_ID}`);

    // The ghost renders honestly: named row, running copy, in the ghost zone.
    await expect(page.getByTestId('zone-ghosts')).toBeVisible();
    await expect(page.getByTestId('ghost-row')).toHaveCount(1);
    await expect(page.getByTestId('ghost-row')).toContainText('חדש.pdf');

    // Next poll (≈3s): the ghost zone dissolves; the SAME document is now a
    // real clean row carrying the arrival highlight (keyed as a NEW id).
    await expect(page.getByTestId('zone-ghosts')).toBeHidden({ timeout: 10_000 });
    await expect(page.getByTestId('clean-row')).toHaveCount(2);
    const landed = page.getByTestId('clean-row').filter({ hasText: 'חדש.pdf' });
    await expect(landed).toHaveCount(1);
    await expect(landed).toHaveClass(/bg-batch-teal-soft/);
});

// ---------------------------------------------------------------------------
// ZC-1 v2 (owner-ruled 2026-08-22, refined 2026-08-23):
// transcribed = Σ(eyes rows) + Σ(clean rows), with identity-pending items
// (ONLY flag = extracted new name, untouched) homed in the CLEAN panel,
// their names riding the wave, EXCLUDED from the bulk count. Seeds the
// owner's exact live batch shape.
// ---------------------------------------------------------------------------

test('ZC-1 v2 — identity-pending items home in CLEAN: sum intact, bulk count honest, wave overlaid', async ({ page }) => {
    await seedAuth(page);
    const payload = seedBatch({
        items: [
            seedItem('t1', { filename: 'איתי קראפט.pdf', suggestion: 'איתי קראפט', reasons: ['unparseable', 'student_unassigned'] }),
            seedItem('t2', { filename: 'דין עזרא.pdf', suggestion: 'דין עזרא', reasons: ['unparseable', 'student_unassigned'] }),
            seedItem('t3', { filename: 'יהלי כהן.pdf', suggestion: 'יהלי כהן', reasons: ['unparseable', 'student_unassigned'] }),
            seedItem('t4', { filename: 'טל גורבן.pdf', suggestion: 'טל גורבן', reasons: ['unparseable', 'student_unassigned'] }),
            // THE bug shape: clean content, new name extracted, no student yet.
            seedItem('t5', { filename: 'דן בסיוק.pdf', suggestion: 'דן בסיוק', reasons: ['student_unassigned'] }),
            seedItem('t6', { filename: 'איתי כתב.pdf', suggestion: 'איתי כתב', matchedStudentId: 's1', matchedStudentName: 'איתי כתב' }),
        ],
    });
    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        if (url.includes('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);
        if (url.includes(`/api/v0/batches/${SEED_BATCH_ID}`)) return fulfillJson(route, payload);
        return fulfillJson(route, {});
    });

    await page.goto(`/batches/${SEED_BATCH_ID}`);

    // THE SUM: 6 transcribed = 4 eyes rows + 2 clean rows. No item homeless.
    await expect(page.getByTestId('eyes-row')).toHaveCount(4);
    await expect(page.getByTestId('clean-row')).toHaveCount(2);

    // דן בסיוק homes in the CLEAN panel: his extracted name shows, the amber
    // chip says WHY he is not yet bulk-acceptable, and the row carries the
    // panel's per-item entry (reachability, ZC-1's original complaint).
    const danRow = page.getByTestId('clean-row').filter({ hasText: 'דן בסיוק.pdf' });
    await expect(danRow).toHaveCount(1);
    await expect(danRow).toContainText('דן בסיוק');
    await expect(danRow).toContainText('תלמיד חדש - טרם נוצר');

    // The BULK COUNT is honest: only the matched item (איתי כתב) is counted —
    // the button never claims items the server would refuse.
    await expect(page.getByTestId('clean-accept-all')).toHaveText('אשרי את המבחן (1)');
    await expect(page.getByTestId('clean-pending-note'))
        .toHaveText('מבחן אחד ממתין ליצירת תלמיד — צרי אותו בזיהוי התלמידים למעלה');

    // The zone title, walk CTA and bar legend all count the SAME eyes set.
    await expect(page.getByTestId('zone-eyes').getByText('דורשים עיון — 4')).toBeVisible();
    await expect(page.getByTestId('eyes-start-walk')).toHaveText('התחילי סבב עיון (4)');
    const legendEyes = page.getByTestId('segment-bar').first()
        .locator('span', { hasText: 'דורשים עיון' }).locator('b');
    await expect(legendEyes).toHaveText('4');
    const legendClean = page.getByTestId('segment-bar').first()
        .locator('span', { hasText: 'נקיים' }).locator('b');
    await expect(legendClean).toHaveText('2');

    // The wave still shows the pills — an ACCELERATOR overlay, never a home.
    await expect(page.getByTestId('zone-identity-wave')).toBeVisible();
});
