/**
 * The semantic events that need state or a computation to derive — kept HERE,
 * not at their call sites, so that with demo mode off a call site's whole cost
 * is one `isDemo()` check (owner amendment to D1/D7). Every export returns
 * before doing any work when the flag is off.
 *
 * `testIndex` (D5): 1-based position in `batch.transcriptions`, which the
 * server orders by `created_at, id` — append-only, so an index never moves.
 * It is the order transcriptions ARRIVED, not the order files were uploaded
 * (upload order is not on the wire per transcription).
 */

import { demoLog, isDemo } from './core';

/** The slice of `BatchDetailResponse` these helpers read — structural, so every holder's type fits. */
export interface DemoBatchLike {
    rollup?: { total?: number | null } | null;
    transcriptions?: ReadonlyArray<{
        transcription_id: string;
        transcription_status?: string | null;
        graded_test_id?: string | null;
        graded_test_status?: string | null;
    }> | null;
    graded_tests?: ReadonlyArray<{
        graded_test_id: string;
        transcription_id?: string | null;
        status?: string | null;
    }> | null;
}

/** The slice of a review model (v5 `ReviewModel` or v6 `V6ReviewModel`) the score diff reads. */
export interface DemoScoredModel {
    scopes: ReadonlyArray<{
        scopeId: string;
        criteria: ReadonlyArray<{ terminalId: string; awarded: string }>;
    }>;
}

const PROGRESS = 'batch-progress';
/** sessionStorage: what each test last looked like, so a reload does not re-announce. */
const SEEN_KEY = 'vivi_demo_seen';

type Seen = Record<string, { t: string | null; g: string | null }>;

let seen: Seen | null = null;
const indexByTranscription = new Map<string, number>();
const indexByGradedTest = new Map<string, number>();
/** `${surface}:${gradedTestId}` → scopeId → that scope's awarded signature. */
const scoreBaselines = new Map<string, Map<string, string>>();

function loadSeen(): Seen {
    if (seen) return seen;
    try {
        seen = (JSON.parse(window.sessionStorage.getItem(SEEN_KEY) ?? '{}') as Seen) ?? {};
    } catch {
        seen = {};
    }
    return seen;
}

/**
 * Feed every batch payload the app receives (dashboard poll, transcription
 * review holder, grade-review holder, returned page). Emits:
 *   · `transcription_ready {testIndex}` — the first time a test is seen
 *     `transcribed` (a transcription row exists only once its document is read);
 *   · `grading_status {testIndex, from, to}` — only on an actual change of
 *     `graded_test_status` since the last payload, never on every poll. A
 *     test's first sighting is the baseline (there is no `from` to report).
 * The last-seen map is module-level, so a route change neither repeats nor
 * loses a transition: one observed late is logged when it is observed.
 */
export function observeBatch(batch: DemoBatchLike | null | undefined): void {
    try {
        if (!isDemo() || !batch) return;
        const s = loadSeen();
        let changed = false;
        (batch.transcriptions ?? []).forEach((row, i) => {
            const testIndex = i + 1;
            const tid = String(row.transcription_id);
            indexByTranscription.set(tid, testIndex);
            if (row.graded_test_id) indexByGradedTest.set(String(row.graded_test_id), testIndex);

            const t = row.transcription_status ?? null;
            const g = row.graded_test_status ?? null;
            const prev = s[tid];
            if (!prev) {
                if (t === 'transcribed') demoLog('transcription_ready', { testIndex }, PROGRESS);
                s[tid] = { t, g };
                changed = true;
                return;
            }
            if (prev.g !== g) demoLog('grading_status', { testIndex, from: prev.g, to: g }, PROGRESS);
            if (prev.t !== t || prev.g !== g) {
                s[tid] = { t, g };
                changed = true;
            }
        });
        for (const item of batch.graded_tests ?? []) {
            const idx = item.transcription_id
                ? indexByTranscription.get(String(item.transcription_id)) : undefined;
            if (idx !== undefined) indexByGradedTest.set(String(item.graded_test_id), idx);
        }
        if (changed) window.sessionStorage.setItem(SEEN_KEY, JSON.stringify(s));
    } catch {
        /* the logger never throws */
    }
}

/**
 * `override_edited {testIndex, scopeId}` — call with the review model after
 * every render. A scope whose awarded figures changed since the previous model
 * for the same test is an edit she committed (D6: a verdict click, a key, a
 * typed amount, a revert — notes and disputes change no figure and are not
 * logged). The first model per test is the baseline. `surface` keeps the v5
 * and v6 models of one test apart, since both can be built for it.
 */
export function demoObserveScores(
    surface: string, gradedTestId: string, model: DemoScoredModel | null | undefined,
): void {
    try {
        if (!isDemo() || !model) return;
        const key = `${surface}:${gradedTestId}`;
        const next = new Map(model.scopes.map((scope) => [
            scope.scopeId,
            scope.criteria.map((c) => `${c.terminalId}=${c.awarded}`).join('|'),
        ]));
        const prev = scoreBaselines.get(key);
        scoreBaselines.set(key, next);
        if (!prev) return;
        const testIndex = indexByGradedTest.get(gradedTestId) ?? null;
        next.forEach((signature, scopeId) => {
            if (prev.get(scopeId) === signature) return;
            demoLog('override_edited', { testIndex, scopeId },
                window.document.getElementById(`scope-${scopeId}`));
        });
    } catch {
        /* the logger never throws */
    }
}

/**
 * `test_approved {i, total}` — after /approve succeeded and the cursor has
 * been told. `i` = approved tests in the batch after this one; `total` = the
 * batch size.
 */
export function demoTestApproved(
    batch: DemoBatchLike | null | undefined,
    cursor: { byId: Record<string, { status?: string | null }> } | null | undefined,
): void {
    try {
        if (!isDemo()) return;
        const i = cursor
            ? Object.values(cursor.byId).filter((item) => item.status === 'approved').length
            : null;
        const total = batch?.rollup?.total ?? batch?.transcriptions?.length ?? null;
        demoLog('test_approved', { i, total }, 'approve-button');
    } catch {
        /* the logger never throws */
    }
}

/** `feedback_view_opened {testIndex}` — the returned (student-feedback) view has rendered. */
export function demoFeedbackViewOpened(gradedTestId: string): void {
    try {
        if (!isDemo()) return;
        demoLog('feedback_view_opened',
            { testIndex: indexByGradedTest.get(gradedTestId) ?? null }, 'feedback-view');
    } catch {
        /* the logger never throws */
    }
}

/** `pdf_downloaded {count}` for one returned exam. */
export function demoPdfDownloaded(): void {
    demoLog('pdf_downloaded', { count: 1 }, 'pdf-download');
}

/** `pdf_downloaded {count}` for the batch ZIP — count = the batch's approved tests. */
export function demoBatchZipDownloaded(batch: DemoBatchLike | null | undefined): void {
    try {
        if (!isDemo()) return;
        const count = batch?.graded_tests
            ? batch.graded_tests.filter((t) => t.status === 'approved').length
            : (batch?.transcriptions ?? []).filter((t) => t.graded_test_status === 'approved').length;
        demoLog('pdf_downloaded', { count }, 'pdf-download');
    } catch {
        /* the logger never throws */
    }
}
