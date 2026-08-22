import { expect, test, type Page } from '@playwright/test';
import { seedAuth } from './fixtures';
import {
    AUTH_ME,
    fulfillJson,
    SEED_BATCH_ID,
    seedBatch,
    seedItem,
} from './seedBatch';

/**
 * Phase-4 journeys (plan §9 + the Phase-3 go riders):
 *  - batch-review-walkthrough — dashboard → drill-in → edit → save → arrows →
 *    persisted edit → ACCEPT MID-WALK → order stays the ENTRY order even though
 *    the post-accept refetch returns flipped verdicts (rider b).
 *  - unsaved-changes-guard — a failed overlay save BLOCKS navigation, loses
 *    nothing, and clears once the save succeeds.
 *  - rtl-bidi-code-comment-rendering — LTR code with inline Hebrew comments and
 *    a Hebrew-INITIAL comment line inside the RTL page: `//` must visually
 *    precede the Hebrew text and code punctuation must not reorder.
 */

const BATCH_ID = 'b0000000-0000-0000-0000-000000000002';

const BIDI_TEXT = [
    'public class Employee { // מחלקה',
    '// תכונות',
    'private int id; // מזהה [?]',
].join('\n');

interface MockState {
    accepted: Set<string>;
    overlays: Map<string, unknown>;
    patchShouldFail: boolean;
    batchCalls: number;
    patchBodies: Array<{ txId: string; body: Record<string, unknown> }>;
    acceptCalls: string[];
}

function draft(answerText: string) {
    return {
        schema_version: '1.0',
        student_name_suggestion: 'רז כהן',
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

function makeItem(state: MockState, id: string, filename: string, flagged: boolean, answerText: string) {
    const isAccepted = state.accepted.has(id);
    return {
        transcription_id: id,
        filename,
        transcription_status: isAccepted ? 'approved' : 'transcribed',
        created_at: '2026-08-04T10:00:00Z',
        draft: draft(answerText),
        review: state.overlays.get(id) ?? null,
        student_name_suggestion: 'רז כהן',
        matched_student_id: 's1',
        matched_student_name: 'רז כהן',
        flag_verdict: { review_needed: flagged && !isAccepted, reasons: flagged && !isAccepted ? ['low_confidence'] : [] },
        graded_test_id: isAccepted ? `gt-${id}` : null,
        graded_test_status: isAccepted ? 'pending' : null,
        total_score: null,
        total_possible: null,
    };
}

function batchPayload(state: MockState) {
    // Before any accept: only 'b' flagged → frozen order [b, a, c]. From the
    // first accept onward (the post-accept refetch — rider b), verdicts FLIP:
    // a recomputed order would be [a, c, b]; the frozen cursor must not care.
    const flipped = state.accepted.size > 0;
    const items = [
        makeItem(state, 'a', 'a.pdf', flipped, 'int alpha = 1;'),
        makeItem(state, 'b', 'b.pdf', !flipped, BIDI_TEXT),
        makeItem(state, 'c', 'c.pdf', flipped, 'int gamma = 3;'),
    ];
    const approved = items.filter((i) => i.transcription_status === 'approved').length;
    return {
        id: BATCH_ID,
        name: 'journeys',
        rubric_id: 'r0000000-0000-0000-0000-000000000001',
        class_id: null,
        status: 'in_progress',
        started_at: null,
        completed_at: null,
        created_at: '2026-08-04T10:00:00Z',
        rollup: {
            transcribing: 0, transcribed: 3 - approved, approved_transcription: approved,
            grading: 0, draft: 0, approved: 0, failed: 0, total: 3,
        },
        transcriptions: items,
    };
}

async function installMocks(page: Page): Promise<MockState> {
    const state: MockState = {
        accepted: new Set(),
        overlays: new Map(),
        patchShouldFail: false,
        batchCalls: 0,
        patchBodies: [],
        acceptCalls: [],
    };

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
        if (url.includes('/api/v0/classroom/students')) {
            return json({ students: [{ id: 's1', full_name: 'רז כהן', notes: null, created_at: '2026-01-01T00:00:00Z' }] });
        }
        const patchMatch = url.match(/\/api\/v0\/transcriptions\/([^/]+)\/review/);
        if (patchMatch && method === 'PATCH') {
            if (state.patchShouldFail) {
                return json({ detail: 'שמירה נכשלה בצד השרת' }, 500);
            }
            const body = route.request().postDataJSON() as Record<string, unknown>;
            const review = {
                schema_version: '1.0',
                answers: body.answers,
                student_id: body.student_id ?? null,
                updated_at: '2026-08-07T10:00:00Z',
            };
            state.patchBodies.push({ txId: patchMatch[1], body });
            state.overlays.set(patchMatch[1], review);
            return json(review);
        }
        const acceptMatch = url.match(/\/api\/v0\/batches\/[^/]+\/accept\/([^/?]+)/);
        if (acceptMatch && method === 'POST') {
            state.accepted.add(acceptMatch[1]);
            state.acceptCalls.push(acceptMatch[1]);
            return json({ accepted: 1 });
        }
        if (url.includes(`/api/v0/batches/${BATCH_ID}`)) {
            state.batchCalls += 1;
            return json(batchPayload(state));
        }
        if (/\/api\/v0\/transcriptions\/[^/]+\/pages\/\d+/.test(url)) {
            return json({
                page_number: Number(url.split('/pages/')[1]),
                thumbnail_base64:
                    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABh6FO1AAAAABJRU5ErkJggg==',
            });
        }
        return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' });
    });

    return state;
}

const editor = (page: Page) => page.getByTestId('transcription-editor');

test('batch-review-walkthrough — edit, save, arrows, persisted edit, accept-mid-walk order stability', async ({ page }) => {
    await seedAuth(page);
    const state = await installMocks(page);

    // Dashboard (P2 redesign): the needs-eyes zone carries the summary rows
    // + per-row links; still NO inline editing on the dashboard. (Assertions
    // updated 2026-08-17 with the D6 rebuild — same intent, new zone.)
    await page.goto(`/batches/${BATCH_ID}`);
    await expect(page.getByTestId('zone-eyes')).toBeVisible();
    expect(await page.locator('textarea').count()).toBe(0);           // the blind inline editor is gone
    await expect(page.getByRole('link', { name: 'פתחי לעיון' }).first()).toBeVisible();

    // Drill into the flagged item (b — first of the frozen order).
    await page.getByRole('link', { name: 'פתחי לעיון' }).first().click();
    await expect(page).toHaveURL(new RegExp(`/batches/${BATCH_ID}/review/b$`));
    await expect(page.getByText('1 מתוך 3')).toBeVisible();

    // Edit + explicit save → full snapshot lands, indicator honest.
    await editor(page).fill('edited by teacher');
    await expect(page.getByText('שינויים לא שמורים')).toBeVisible();
    await page.getByRole('button', { name: 'שמירה' }).click();
    await expect(page.getByText('נשמר')).toBeVisible();
    expect(state.patchBodies).toHaveLength(1);
    expect(state.patchBodies[0].txId).toBe('b');
    expect(state.patchBodies[0].body.student_id).toBe('s1');          // pre-seeded match carried

    // Arrow away and back: the edit survives (overlay-over-draft hydration).
    await page.getByRole('button', { name: 'הבא' }).click();
    await expect(page).toHaveURL(new RegExp(`/review/a$`));
    await page.getByRole('button', { name: 'הקודם' }).click();
    await expect(page).toHaveURL(new RegExp(`/review/b$`));
    await expect(editor(page)).toHaveValue('edited by teacher');

    // ACCEPT MID-WALK (rider b): confirm modal → accept → refetch returns
    // FLIPPED verdicts — the frozen order must not move. R4: b was the ONLY
    // flagged item, so the interstitial appears; Esc declines it (the walk
    // continues — nothing is bulk-accepted by a dismissal).
    await page.getByRole('button', { name: 'אישור תמלול' }).click();
    await page.getByRole('button', { name: 'אישור תמלול' }).last().click();   // modal confirm
    await expect(page.getByTestId('review-interstitial')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('review-interstitial')).toBeHidden();
    await expect(page.getByText('אושר')).toBeVisible();
    expect(state.acceptCalls).toEqual(['b']);

    await expect(page.getByText('1 מתוך 3')).toBeVisible();           // still position 1 of ENTRY order
    await page.getByRole('button', { name: 'הבא' }).click();
    await expect(page).toHaveURL(new RegExp(`/review/a$`));           // entry order: b → a (flipped would go b → c)
    await expect(page.getByText('2 מתוך 3')).toBeVisible();
});

test('unsaved-changes-guard — a failed save blocks navigation and loses nothing', async ({ page }) => {
    await seedAuth(page);
    const state = await installMocks(page);

    await page.goto(`/batches/${BATCH_ID}/review/a`);
    await expect(page.getByText('2 מתוך 3')).toBeVisible();

    state.patchShouldFail = true;
    await editor(page).fill('precious edit');
    await page.getByRole('button', { name: 'הבא' }).click();

    // Navigation BLOCKED, error surfaced, edit intact.
    await expect(page.getByText('השמירה נכשלה')).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`/review/a$`));
    await expect(editor(page)).toHaveValue('precious edit');

    // Save path restored → the same arrow now flushes and navigates.
    state.patchShouldFail = false;
    await page.getByRole('button', { name: 'הבא' }).click();
    await expect(page).toHaveURL(new RegExp(`/review/c$`));
    expect(state.overlays.has('a')).toBe(true);                        // nothing was lost
});

test('rtl-bidi-code-comment-rendering — dir=ltr island, // before Hebrew, punctuation unreordered', async ({ page }) => {
    await seedAuth(page);
    await installMocks(page);

    // Item b carries the bidi fixture incl. a [?] line, so the flagged-path
    // BACKDROP renders per-line divs we can measure.
    await page.goto(`/batches/${BATCH_ID}/review/b`);
    await expect(editor(page)).toBeVisible();

    // The code region is an LTR island inside the RTL page.
    await expect(editor(page)).toHaveAttribute('dir', 'ltr');
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');

    // Measure visual char positions inside the backdrop's line divs
    // (visibility:hidden keeps geometry). For each assertion pair we compare
    // the x-midpoint of a substring's rect via Range.getBoundingClientRect.
    const positions = await page.evaluate(() => {
        function mid(node: Text, start: number, end: number): number {
            const r = document.createRange();
            r.setStart(node, start); r.setEnd(node, end);
            const rect = r.getBoundingClientRect();
            return rect.left + rect.width / 2;
        }
        const backdrop = document.querySelector('[aria-hidden="true"].pointer-events-none');
        if (!backdrop) return null;
        const lines = Array.from(backdrop.children) as HTMLElement[];
        const out: Record<string, { slashes: number; hebrew: number; extra?: Record<string, number> }> = {};
        for (const line of lines) {
            const span = line.querySelector('span');
            const textNode = span?.firstChild as Text | null;
            const text = textNode?.textContent ?? '';
            if (!textNode) continue;
            const slashIdx = text.indexOf('//');
            if (slashIdx === -1) continue;
            const hebrewMatch = /[֐-׿]+/.exec(text);
            if (!hebrewMatch) continue;
            const key = text.includes('תכונות') ? 'hebrewInitial'
                : text.includes('מחלקה') ? 'classLine'
                : text.includes('מזהה') ? 'idLine' : text.slice(0, 10);
            out[key] = {
                slashes: mid(textNode, slashIdx, slashIdx + 2),
                hebrew: mid(textNode, hebrewMatch.index, hebrewMatch.index + hebrewMatch[0].length),
            };
            if (key === 'idLine') {
                const semiIdx = text.indexOf(';');
                const privIdx = text.indexOf('private');
                out[key].extra = {
                    semi: mid(textNode, semiIdx, semiIdx + 1),
                    privateKw: mid(textNode, privIdx, privIdx + 7),
                };
            }
        }
        return out;
    });

    expect(positions).not.toBeNull();
    const p = positions!;

    // `//` visually PRECEDES (is left of) the Hebrew comment text — including
    // on the Hebrew-INITIAL line, the known bidi trap.
    expect(p.hebrewInitial.slashes).toBeLessThan(p.hebrewInitial.hebrew);
    expect(p.classLine.slashes).toBeLessThan(p.classLine.hebrew);
    expect(p.idLine.slashes).toBeLessThan(p.idLine.hebrew);

    // Punctuation not reordered: the statement's `;` sits after (right of) the
    // `private` keyword and before the comment markers.
    expect(p.idLine.extra!.privateKw).toBeLessThan(p.idLine.extra!.semi);
    expect(p.idLine.extra!.semi).toBeLessThan(p.idLine.slashes);
});

// ---------------------------------------------------------------------------
// StudentPicker inline conflict (P3 wave 0, P2-review item 3): the OTHER
// dead-code victim of the _classroomFetch regression — the 409's server
// detail must render inline in the picker, not a generic error.
// ---------------------------------------------------------------------------

test('student-picker-conflict — a 409 create renders the server detail inline', async ({ page }) => {
    await seedAuth(page);

    const payload = seedBatch({
        items: [seedItem('t1', { reasons: ['missing_answers'] })],
        rollup: { total: 1 },
    });
    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        const method = route.request().method();
        if (url.includes('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);
        if (method === 'POST' && url.includes('/api/v0/classroom/students')) {
            return fulfillJson(route, { detail: 'כבר קיים תלמיד בשם זה' }, 409);
        }
        if (url.includes('/api/v0/classroom/students')) {
            return fulfillJson(route, { students: [] });
        }
        if (/\/api\/v0\/transcriptions\/[^/]+\/pages\/\d+/.test(url)) {
            return fulfillJson(route, {
                page_number: 1,
                thumbnail_base64:
                    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABh6FO1AAAAABJRU5ErkJggg==',
            });
        }
        if (url.includes(`/api/v0/batches/${SEED_BATCH_ID}`)) {
            return fulfillJson(route, payload);
        }
        return fulfillJson(route, {});
    });

    await page.goto(`/batches/${SEED_BATCH_ID}/review/t1`);
    await expect(page.getByText('בדיקת תמלול')).toBeVisible();

    const search = page.getByPlaceholder('חפש תלמיד...');
    await search.click();               // closed state is readonly; click opens
    await search.fill('דנה לוי');
    await page.getByText('צור תלמיד חדש').click();

    // The typed conflict's SERVER detail renders inline (was: generic
    // 'שגיאה ביצירת התלמיד' while the 409 branch was dead).
    await expect(page.getByText('כבר קיים תלמיד בשם זה')).toBeVisible();
});
