import { readFileSync } from 'node:fs';
import path from 'node:path';
import type { Page } from '@playwright/test';

import { USER, seedAuth } from './fixtures';

/**
 * Route mocks for בדיקת ציונים.
 *
 * The payloads are the PUBLISHED §1.7 fixtures, read IN PLACE from the backend
 * tree — never copied (CLAUDE.md §0.4). What this file adds is only the join
 * the wire does not do for us yet: the answers and question text a review route
 * needs, assembled from the same eval bundle the drafts came from.
 */

const FIXTURES = path.resolve(
    __dirname, '../../backend/tests/fixtures/grade_review');

export const readApproved = (student: string): Record<string, unknown> =>
    JSON.parse(readFileSync(
        path.join(FIXTURES, `approved_${student}.json`), 'utf-8'));

export const readDraft = (student: string): Record<string, unknown> =>
    JSON.parse(readFileSync(path.join(FIXTURES, `draft_${student}.json`), 'utf-8'));

export const NUMERIC_POLICY = {
    precision: '0.25', rounding_mode: 'half_up', sum_tolerance: '0.01',
};

export const TEST_A = '44444444-4444-4444-8444-000000000000';
export const TEST_B = '44444444-4444-4444-8444-000000000001';
export const BATCH_ID = '11111111-1111-4111-8111-111111111111';

/**
 * ONE mapping from graded-test id to the student it belongs to.
 *
 * Everything about a test — its draft, its answers, its displayed name — must
 * come from THIS, keyed by the id being requested. An earlier version keyed the
 * name off the requested id but the draft off `opts.student`, so TEST_B served
 * dan's grade under דין עזרא's name beside din's answers: every evidence
 * quotation pointed at text that was not there, and the prev/next journeys were
 * quietly reviewing a test that does not exist.
 */
const HEBREW_NAME: Record<string, string> = {
    dan_basiuk: 'דן בסיוק',
    din_ezra: 'דין עזרא',
    moran_aharon: 'מורן אהרון',
    omer_gelber: 'עומר גלבר',
    yonatan_basiuk: 'יונתן בסיוק',
};

/** TEST_A is the test under scrutiny (`opts.student`); TEST_B is its neighbour. */
function studentForTest(testId: string, primary: string): string {
    return testId === TEST_B ? 'din_ezra' : primary;
}

/**
 * The REAL transcriptions the drafts were graded against, read in place from
 * the eval-suite benchmarks.
 *
 * An invented answer is worse than no answer here: the checks cite verbatim
 * spans, so hand-written text silently produces a surface where NO evidence
 * highlight can ever resolve — and the e2e would then be testing a review
 * module whose central affordance is dead. (That is exactly what the first
 * version of this file did, and the pin test caught it.)
 */
const TRANSCRIPTIONS = path.resolve(
    __dirname, '../../backend/tests/grading_eval_suite/benchmarks/transcriptions');

function answersFor(student: string): {
    question_number: number; sub_question_id: string | null; answer_text: string;
}[] {
    const contract = JSON.parse(readFileSync(
        path.join(TRANSCRIPTIONS, `${student}.contract.json`), 'utf-8'));
    return contract.answers.map((a: {
        question_number: number; sub_question_id?: string | null; answer_text: string;
    }) => ({
        question_number: a.question_number,
        sub_question_id: a.sub_question_id ?? null,
        answer_text: a.answer_text,
    }));
}


/**
 * [EVD-1] Stand in for the SERVER'S legacy backfill.
 *
 * The published drafts are real eval-run output and predate
 * `ScopeOutcome.student_answer`; the generator replays them rather than
 * re-grading, so they will never carry it. In production `get_single_graded_test`
 * resolves that case with `services/grading_inputs.backfill_scope_answers`,
 * using the same compiler the grader used. These mocks bypass the server, so
 * they must apply the same fill or they would serve a payload no real client can
 * receive — every scope reading «cannot show the answer».
 *
 * NOT a fallback rule: the nearest-ancestor walk lives on the server and is
 * tested there. This is a fixture standing in for a response.
 */
function withGradedAnswers(
    draft: Record<string, unknown>,
    answers: { question_number: number; sub_question_id: string | null; answer_text: string }[],
): Record<string, unknown> {
    const byKey = new Map(answers.map(
        (a) => [`${a.question_number}|${a.sub_question_id ?? ''}`, a.answer_text]));
    const qNum = (id: string) => Number((/\d+/.exec(id) ?? ['0'])[0]);

    const scopes = (draft.scope_outcomes as Record<string, unknown>[] | undefined) ?? [];
    return {
        ...draft,
        scope_outcomes: scopes.map((scope) => {
            if (scope.student_answer) return scope;
            const path = (scope.sub_question_id as string | null) ?? null;
            const n = qNum(scope.question_id as string);
            // exact id, then each ancestor up the path, then the whole question
            const candidates: (string | null)[] = [];
            let cursor = path;
            while (cursor) {
                candidates.push(cursor);
                const cut = cursor.lastIndexOf('.');
                cursor = cut === -1 ? null : cursor.slice(0, cut);
            }
            candidates.push(null);
            for (const candidate of candidates) {
                const text = byKey.get(`${n}|${candidate ?? ''}`);
                if (text === undefined) continue;
                return {
                    ...scope,
                    student_answer: candidate === path
                        ? { text, source: 'own', inherited_from: null }
                        : { text, source: 'inherited', inherited_from: candidate },
                };
            }
            return scope;
        }),
    };
}

const RUBRIC = {
    id: '22222222-2222-4222-8222-222222222222',
    name: 'מתכונת 1 — שאלון 899371',
    contract_json: {
        questions: [
            {
                question_id: 'q1',
                question_text:
                    'הגדירו את המחלקה Hobby. לכל תחביב יש שם (name), מספר דקות שבועיות (minutes) '
                    + 'והאם הוא ספורטיבי (isSportive). כתבו את התכונות, בנאי המאתחל את כולן '
                    + 'ופעולות get לכל תכונה.',
                sub_questions: [],
            },
            {
                question_id: 'q2',
                question_text:
                    'כתבו תוכנית הקולטת נתוני תחביבים ומדפיסה את התחביב שהוקדשו לו הכי הרבה דקות.',
                sub_questions: [],
            },
        ],
    },
};

/**
 * One transcription row, carrying every field the wire marks REQUIRED.
 *
 * `flag_verdict` and `draft` are both required on `BatchTranscriptionItem`, and
 * the dashboard reads `t.flag_verdict.review_needed` unguarded — correctly, since
 * the server always sends it. An earlier version of this mock omitted them and
 * crashed the dashboard, which is a mock that tests against a payload the server
 * would never produce.
 */
function transcriptionRow(
    id: string,
    gradedTestId: string,
    filename: string,
    studentName: string,
    answers: ReturnType<typeof answersFor>,
    score: string,
): Record<string, unknown> {
    return {
        transcription_id: id,
        graded_test_id: gradedTestId,
        graded_test_status: 'draft',
        transcription_status: 'approved',
        filename,
        matched_student_name: studentName,
        matched_student_id: `student-${id}`,
        student_name_suggestion: studentName,
        created_at: '2026-08-31T18:00:00+00:00',
        total_score: score,
        total_possible: '100',
        flag_verdict: { review_needed: false, reasons: [] },
        approved_answers: answers,
        draft: {
            schema_version: '1.0',
            page_count: 6,
            answers: answers.map((a, i) => ({
                question_number: a.question_number,
                sub_question_id: a.sub_question_id,
                answer_text: a.answer_text,
                confidence: 1,
                page_numbers: [Math.min(6, i + 1)],
            })),
            annotations: [],
        },
    };
}

function batchPayload(
    student: string,
    override?: GradeReviewMockOptions['answersOverride'],
    feedState: NonNullable<GradeReviewMockOptions['feedState']> = 'running',
    staleReturnedExam = false,
    revision = false,
    revisionFrom: 'approved' | 'failed' = 'approved',
): Record<string, unknown> {
    const feed = JSON.parse(
        readFileSync(path.join(FIXTURES, `batch_feed_${feedState}.json`), 'utf-8'));
    // The published feed carries `transcriptions: []` — the generator does not
    // emit them. The ANSWERS join is what a real payload would carry here.
    feed.transcriptions = [
        transcriptionRow('t-a', TEST_A, `${student}.pdf`, HEBREW_NAME[student] ?? student,
            override ?? answersFor(student), '79.5'),
        transcriptionRow('t-b', TEST_B, 'din_ezra.pdf', HEBREW_NAME.din_ezra,
            answersFor('din_ezra'), '64.25'),
    ];
    if (staleReturnedExam) {
        for (const item of feed.graded_tests ?? []) {
            if (item.graded_test_id === TEST_A) item.returned_exam_state = 'stale';
        }
    }
    if (revision) {
        for (const item of feed.graded_tests ?? []) {
            if (item.graded_test_id === TEST_A) item.version = 2;
            if (item.graded_test_id === TEST_B) item.status = revisionFrom;
        }
    }
    return feed;
}

/**
 * A VISIBLY SYNTHETIC page image.
 *
 * The published fixtures carry no scan bytes and never will — they are real
 * students' exam pages. The mockup solved this the same way, with generated
 * line art (`sqSvg`): obviously not a photograph, so a screenshot review can
 * never pass on a fake, while the Pile can still be built and looked at.
 *
 * This is content, not a wire SHAPE. The registry's refuse-don't-invent rule
 * governs shapes — a payload nobody agreed to. The shape here (bytes at a
 * path) is fully specified; only the pixels are stood in for.
 */
/**
 * A VISIBLY SYNTHETIC page image, drawn with the MOCKUP'S OWN algorithm.
 *
 * The published fixtures carry no scan bytes and never will — they are real
 * students' exam pages. The mockup solved this the same way (`sqSvg`):
 * generated wave strokes that read as handwriting at thumbnail size but are
 * obviously not a photograph, so a screenshot review can never pass on a fake.
 *
 * Reusing the mockup's exact shape matters for the VISUAL GATE: comparing my
 * pile against the mockup's is only meaningful if the thing inside the cards is
 * the same kind of thing. A first version drew sparse straight rules, and the
 * comparison it produced was worthless.
 *
 * This is content, not a wire SHAPE. The registry's refuse-don't-invent rule
 * governs shapes — a payload nobody agreed to. The shape here (bytes at a path)
 * is fully specified; only the pixels are stood in for.
 */
function syntheticPageSvg(seed: number): string {
    // The mockup's own LCG, so the strokes look the same.
    let state = (seed * 9301 + 49297) % 233280;
    const rnd = () => { state = (state * 9301 + 49297) % 233280; return state / 233280; };

    const paths: string[] = [
        '<path d="M136 15 q-5 4 -10 0 t-10 0 t-10 0 t-10 0 t-10 0" stroke-width="1.7"/>',
        '<path d="M136 25 q-5 3 -10 0 t-10 0 t-10 0" stroke-width="1.4"/>',
    ];
    let y = 34;
    for (let i = 0; i < 13; i += 1) {
        const len = 36 + rnd() * 76;
        const right = i < 3;
        const x0 = right ? 138 - len : 12 + (rnd() < 0.45 ? 0 : 12) + (rnd() < 0.3 ? 12 : 0);
        let d = `M${x0.toFixed(1)} ${y}`;
        for (let k = 0; k < len / 9; k += 1) {
            d += ` q4.5 ${((rnd() - 0.5) * 4.2).toFixed(1)} 9 0`;
        }
        paths.push(`<path d="${d}"/>`);
        y += 11.5;
        if (i === 2) y += 8;
    }

    return [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 150 198">',
        '<rect width="150" height="198" fill="#FFFDF8"/>',
        '<g fill="none" stroke="#B9BABF" stroke-width="1.15" stroke-linecap="round">',
        ...paths,
        '</g>',
        '<text x="6" y="194" font-size="6" fill="#C6C8CC">דוגמה סינתטית</text>',
        '</svg>',
    ].join('');
}

export interface GradeReviewMockOptions {
    student?: string;
    /** Make every PATCH /draft fail, to drive the save-failure journey. */
    failSave?: boolean;
    draftOverride?: Record<string, unknown>;
    /**
     * SYNTHETIC answers, for the render states the cohort cannot produce.
     *
     * Verified 2026-08-31 across all five transcriptions: there is exactly ONE
     * Hebrew-only comment line (moran_aharon q2.א — used real) and NOT ONE
     * all-prose answer, because every student wrote code. The prose renderer
     * therefore has no observed input and must be driven synthetically, the
     * same discipline the backend's `--with-synthetic` fixture follows.
     */
    answersOverride?: {
        question_number: number; sub_question_id: string | null; answer_text: string;
    }[];
    /** Which of the four published dashboard states to serve (F1). */
    feedState?: 'landing' | 'running' | 'done' | 'complete';
    /**
     * Serve TEST_A's APPROVED payload (F3) instead of its draft.
     *
     * The approved fixtures are compiled by the real approval gate from the
     * real drafts (`scripts/gen_returned_exam_fixtures.py`), so the returned
     * exam is previewed from a contract that actually passed the gate — not
     * from a draft dressed up as one.
     */
    approved?: boolean;
    /** P8 — mark TEST_A's returned exam stale, so the banner has a driver. */
    staleReturnedExam?: boolean;
    /** Make the batch PATCH fail, to drive the roll-back-and-say-so path. */
    failBatchSettings?: boolean;
    /** Serve TEST_A as a manual_edit SUCCESSOR: `regraded_from_id` set and the
     *  feed row at version 2 — the R13 banner's driver. */
    revision?: boolean;
    /** What the predecessor (TEST_B) was: `approved` (manual_edit / regrade —
     *  the banner is true) or `failed` (a retry — nothing was ever signed). */
    revisionFrom?: 'approved' | 'failed';
}

export async function installGradeReviewMocks(
    page: Page,
    opts: GradeReviewMockOptions = {},
): Promise<void> {
    await seedAuth(page);
    const student = opts.student ?? 'dan_basiuk';
    const draft = opts.draftOverride ?? readDraft(student);
    // [EVD-1] what the SERVER would return for these legacy drafts.
    const gradedDraft = withGradedAnswers(
        draft, opts.answersOverride ?? answersFor(student));

    const json = (body: unknown, status = 200) => ({
        status,
        contentType: 'application/json',
        body: JSON.stringify(body),
    });

    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        const method = route.request().method();

        if (url.includes('/auth/me')) {
            return route.fulfill(json(USER));
        }
        if (method === 'GET' && /\/batches\/[^/]+$/.test(url)) {
            return route.fulfill(json(batchPayload(
                student, opts.answersOverride, opts.feedState,
                opts.staleReturnedExam, opts.revision, opts.revisionFrom ?? 'approved')));
        }
        if (method === 'GET' && /\/rubrics\/[^/]+$/.test(url)) {
            return route.fulfill(json(RUBRIC));
        }
        if (method === 'GET' && /\/graded_test\/[^/]+$/.test(url)) {
            const id = url.split('/graded_test/')[1].split('?')[0];
            if (opts.approved) {
                // Serve the fixture under whatever id was asked for, so a deep
                // link works the same way. `transcription_id` is REWRITTEN to
                // this mock's own row: the generator stamps a synthetic one,
                // and the preview joins on it to find the scan's page count —
                // a mismatch silently produces an exam with no pages.
                const who = studentForTest(id, student);
                const payload = readApproved(who);
                return route.fulfill(json({
                    ...payload, id, transcription_id: id === TEST_B ? 't-b' : 't-a',
                    // [EVD-1] as above — the approved payload's DRAFT is what the
                    // review surface renders.
                    draft: withGradedAnswers(
                        (payload as Record<string, unknown>).draft as Record<string, unknown>,
                        answersFor(who)),
                }));
            }
            // Keyed by the REQUESTED id, all of it — see studentForTest.
            const who = studentForTest(id, student);
            // [EVD-1] every served draft carries its resolved evidence, exactly
            // as the server's legacy backfill would supply it.
            const body = id === TEST_A
                ? gradedDraft
                : withGradedAnswers(readDraft(who), answersFor(who));
            return route.fulfill(json({
                id,
                status: 'draft',
                student_name: HEBREW_NAME[who] ?? who,
                filename: `${who}.pdf`,
                transcription_id: id === TEST_B ? 't-b' : 't-a',
                numeric_policy: NUMERIC_POLICY,
                // The contract's achievable total. Omitting it made every e2e
                // exercise the client re-sum FALLBACK rather than the wire
                // denominator — the one thing CLAUDE.md §5 forbids re-deriving.
                total_possible: '100',
                draft: body,
                rubric_contract_stale: false,
                regraded_from_id: opts.revision && id === TEST_A ? TEST_B : null,
            }));
        }
        if (method === 'GET' && url.includes('/pages/') && url.includes('/image')) {
            // Seeded per transcription so the cards differ from one another,
            // exactly as thirty real scans would.
            const seed = [...url].reduce((n, c) => (n + c.charCodeAt(0)) % 997, 7);
            return route.fulfill({
                status: 200,
                contentType: 'image/svg+xml',
                body: syntheticPageSvg(seed),
            });
        }
        if (method === 'PATCH' && /\/batches\/[^/]+$/.test(url)) {
            if (opts.failBatchSettings) {
                return route.fulfill(json({ detail: 'שמירה נכשלה' }, 500));
            }
            const body = route.request().postDataJSON() ?? {};
            return route.fulfill(json({
                batch_id: BATCH_ID,
                name: null,
                appendix_include_criteria: Boolean(body.appendix_include_criteria),
                stamp_position_default: body.stamp_position_default ?? null,
                invalidated_count: 0,
                stamp_applied_count: 0,
            }));
        }
        if (method === 'PATCH' && url.includes('/stamp_position')) {
            // OD-1: the stamp's own write, which accepts approved rows. The
            // server sets `source` itself and reports the render as stale only
            // when one existed to invalidate.
            const body = route.request().postDataJSON() ?? {};
            const position = body.stamp_position
                ? { ...body.stamp_position, source: 'manual' } : null;
            return route.fulfill(json({
                id: TEST_A, status: 'approved', stamp_position: position,
                returned_exam_state: 'none',
            }));
        }
        if (method === 'GET' && url.includes('/returned-exams/manifest')) {
            // D9: approved-only, named exclusions — the modal's authority.
            const feed = batchPayload(student, opts.answersOverride, opts.feedState);
            const tests = (feed.graded_tests ?? []) as {
                graded_test_id: string; student_name: string; status: string;
            }[];
            const named = (rows: typeof tests) => rows.map(
                (t) => ({ graded_test_id: t.graded_test_id, student_name: t.student_name }));
            // As the SERVER files them (`returned_exam.py`): every non-approved
            // leaf — failed included — is «not approved». The dashboard splits
            // failed out by id; a mock that pre-split them made that code
            // untested and the D9 assertion vacuous.
            return route.fulfill(json({
                included: named(tests.filter((t) => t.status === 'approved')),
                excluded_not_approved: named(tests.filter((t) => t.status !== 'approved')),
                excluded_stale: [],
            }));
        }
        if (method === 'GET' && url.includes('/returned-exams.zip')) {
            return route.fulfill({
                status: 200, contentType: 'application/zip', body: 'PK mock zip',
            });
        }
        if (method === 'GET' && url.includes('/returned-exam')) {
            // A real PDF is not what this journey tests — the download seam is.
            return route.fulfill({
                status: 200,
                contentType: 'application/pdf',
                body: '%PDF-1.4 mock',
            });
        }
        if (method === 'PATCH' && url.includes('/draft')) {
            if (opts.failSave) {
                return route.fulfill(json({ detail: 'שמירה נכשלה' }, 500));
            }
            // The real server refuses this on an approved row (`grading.py`,
            // «expected 'draft'»), and the mock says so too. The preview no
            // longer calls it — the stamp has its own endpoint above — so this
            // branch now guards against a REGRESSION to the old call, not a
            // known gap.
            if (opts.approved) {
                return route.fulfill(json(
                    { detail: "Cannot save overrides: graded test is 'approved', "
                        + "expected 'draft'." }, 409));
            }
            return route.fulfill(json({
                id: TEST_A, status: 'draft', student_name: 'דן בסיוק',
                transcription_id: 't-a', draft: gradedDraft,
                effective_totals: {}, pricing_mismatch: false,
            }));
        }
        if (method === 'POST' && url.includes('/retry')) {
            // The chain extends: a NEW pending row, which the next feed shows.
            return route.fulfill(json({ graded_test_id: 'retry-successor', status: 'pending' }));
        }
        if (method === 'POST' && url.includes('/approve')) {
            return route.fulfill(json({
                id: TEST_A, status: 'approved', student_name: 'דן בסיוק',
                transcription_id: 't-a', draft: gradedDraft, contract: {},
                approved_at: '2026-08-31T20:00:00Z',
            }));
        }
        return route.fulfill(json({}));
    });
}
