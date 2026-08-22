/**
 * §4.1 Layer 1 — the canonical BatchDetailResponse fixture factory.
 *
 * Every deterministic dashboard/review spec builds its payloads HERE (one
 * shape, spec-controlled), and wires them via the house catch-all
 * `page.route('**' + '/api/v0/**')` pattern (see batch-review-freeze.spec.ts).
 * The §4.2 state presets (cold-start / steady / transcribing-only / completed)
 * are the screenshot-matrix inputs for P2+.
 *
 * NOTE: `active_jobs` lands with B3 (P1) — until the payload carries it,
 * ghosts are represented only by `rollup.transcribing`.
 */
import type { Route } from '@playwright/test';

export const SEED_BATCH_ID = 'b0000000-0000-0000-0000-0000000000b1';

export const AUTH_ME = {
    id: 'u1',
    email: 'teacher@example.com',
    full_name: 'מורה בדיקה',
    subscription_status: 'active',
    is_subscription_active: true,
    subject_matters: [],
    created_at: '2026-01-01T00:00:00Z',
};

export function fulfillJson(route: Route, body: unknown, status = 200) {
    return route.fulfill({
        status,
        contentType: 'application/json',
        body: JSON.stringify(body),
    });
}

// ---------------------------------------------------------------------------
// Building blocks
// ---------------------------------------------------------------------------

export interface SeedAnswer {
    question_number: number;
    sub_question_id: string | null;
    answer_text: string;
    confidence: number;
    page_numbers: number[];
}

export function seedAnswer(overrides: Partial<SeedAnswer> = {}): SeedAnswer {
    return {
        question_number: 1,
        sub_question_id: null,
        answer_text: 'public int foo() { return 1; }',
        confidence: 0.95,
        page_numbers: [1],
        ...overrides,
    };
}

export function seedDraft(overrides: Record<string, unknown> = {}) {
    return {
        schema_version: '1.0',
        student_name_suggestion: null,
        page_count: 1,
        answers: [seedAnswer()],
        annotations: [],
        model_version: 'two_phase/v4_p2-spans',
        transcription_duration_ms: 62000,
        ...overrides,
    };
}

export interface SeedItemOpts {
    filename?: string | null;
    status?: 'transcribed' | 'approved';
    reasons?: string[];               // non-empty ⇒ review_needed
    suggestion?: string | null;
    matchedStudentId?: string | null;
    matchedStudentName?: string | null;
    review?: Record<string, unknown> | null;
    draft?: Record<string, unknown>;
    /** B6: contract answers, present on approved items. */
    approvedAnswers?: Array<{
        question_number: number;
        sub_question_id: string | null;
        answer_text: string;
    }> | null;
    gradedTestStatus?: string | null;
}

export function seedItem(id: string, opts: SeedItemOpts = {}) {
    const reasons = opts.reasons ?? [];
    return {
        transcription_id: id,
        filename: opts.filename === undefined ? `${id}.pdf` : opts.filename,
        transcription_status: opts.status ?? 'transcribed',
        created_at: '2026-08-16T10:00:00Z',
        draft: seedDraft({
            student_name_suggestion: opts.suggestion ?? null,
            ...(opts.draft ?? {}),
        }),
        review: opts.review ?? null,
        student_name_suggestion: opts.suggestion ?? null,
        matched_student_id: opts.matchedStudentId ?? null,
        matched_student_name: opts.matchedStudentName ?? null,
        flag_verdict: { review_needed: reasons.length > 0, reasons },
        approved_answers: opts.approvedAnswers ?? null,
        graded_test_id: opts.gradedTestStatus ? `gt-${id}` : null,
        graded_test_status: opts.gradedTestStatus ?? null,
        total_score: null,
        total_possible: null,
    };
}

/** Runtime-relative timestamp — static fixture dates rendered honest-but-
 *  absurd elapsed/duration values in the screenshot matrix (e.g. "2076
 *  minutes"); the elapsed/duration UI derives from now(). */
export function minutesAgo(m: number): string {
    return new Date(Date.now() - m * 60_000).toISOString();
}

/** B3: one in-flight document (queued/running ghost). */
export function seedActiveJob(overrides: Record<string, unknown> = {}) {
    return {
        filename: 'scan_inflight.pdf',
        state: 'queued',
        created_at: minutesAgo(3),
        started_at: null,
        attempt_count: 0,
        ...overrides,
    };
}

export function seedFailure(overrides: Record<string, unknown> = {}) {
    return {
        filename: 'scan_07.pdf',
        error: 'VLMCallError: transport timeout after 2 attempts',
        at: '2026-08-16T10:05:00Z',
        net_verdict: null,
        job_id: 'j0000000-0000-0000-0000-0000000000j1',
        ...overrides,
    };
}

export function seedRollup(overrides: Record<string, number> = {}) {
    return {
        transcribing: 0,
        transcribed: 0,
        approved_transcription: 0,
        grading: 0,
        draft: 0,
        approved: 0,
        failed: 0,
        transcription_failed: 0,
        needs_eyes: 0,
        total: 0,
        ...overrides,
    };
}

export interface SeedBatchOpts {
    id?: string;
    name?: string | null;
    status?: string;
    items?: ReturnType<typeof seedItem>[];
    rollup?: Record<string, number>;
    failures?: ReturnType<typeof seedFailure>[];
    selection_groups?: unknown[];
    activeJobs?: ReturnType<typeof seedActiveJob>[];
    rubricName?: string | null;
    className?: string | null;
}

export function seedBatch(opts: SeedBatchOpts = {}) {
    const items = opts.items ?? [];
    return {
        id: opts.id ?? SEED_BATCH_ID,
        name: opts.name ?? 'מקבץ בדיקה',
        rubric_id: 'r0000000-0000-0000-0000-000000000001',
        class_id: null,
        rubric_name: opts.rubricName === undefined ? 'מתכונת 1 — שאלון 899371' : opts.rubricName,
        class_name: opts.className === undefined ? 'יא׳3' : opts.className,
        status: opts.status ?? 'in_progress',
        started_at: minutesAgo(26),
        completed_at: null,
        created_at: minutesAgo(26),
        rollup: seedRollup({
            transcribed: items.filter((i) => i.transcription_status === 'transcribed').length,
            approved_transcription: items.filter((i) => i.transcription_status === 'approved').length,
            total: items.length,
            ...(opts.rollup ?? {}),
        }),
        transcriptions: items,
        selection_groups: opts.selection_groups ?? [],
        transcription_failures: opts.failures ?? [],
        active_jobs: opts.activeJobs ?? [],
    };
}

// ---------------------------------------------------------------------------
// §4.2 state presets (the screenshot-matrix inputs)
// ---------------------------------------------------------------------------

/** Cold start: most items flagged via unknown students; some still in flight
 *  (two named ghosts + queued tail — B3 active_jobs). */
export function coldStartBatch() {
    return seedBatch({
        items: [
            seedItem('t1', { suggestion: 'נועה לוי', reasons: ['student_unassigned'] }),
            seedItem('t2', { suggestion: 'איתי כהן', reasons: ['student_unassigned'] }),
            seedItem('t3', { suggestion: null, filename: 'סריקה_007.pdf', reasons: ['student_unmatched'] }),
        ],
        rollup: { transcribing: 2, total: 5 },
        activeJobs: [
            seedActiveJob({
                filename: 'טל גורבן.pdf', state: 'running',
                started_at: minutesAgo(1.2), attempt_count: 1,
            }),
            seedActiveJob({ filename: 'אורי לביא.pdf', state: 'queued' }),
        ],
    });
}

/** Steady state: a clean group + a flagged tail + one failed document. */
export function steadyBatch() {
    return seedBatch({
        items: [
            seedItem('t1', {
                suggestion: 'דנה לוי', matchedStudentId: 's1', matchedStudentName: 'דנה לוי',
            }),
            seedItem('t2', {
                suggestion: 'יובל כץ', matchedStudentId: 's2', matchedStudentName: 'יובל כץ',
            }),
            seedItem('t3', {
                suggestion: 'רוני בר', matchedStudentId: 's3', matchedStudentName: 'רוני בר',
                reasons: ['missing_answers', 'unparseable'],
                // Honest payload: the flags derive FROM the draft (one empty
                // answer, one [?] marker) — chip counts must never read "· 0".
                draft: {
                    answers: [
                        { question_number: 1, sub_question_id: null, answer_text: '', confidence: 0, page_numbers: [] },
                        { question_number: 2, sub_question_id: null, answer_text: 'x = [?] + 1', confidence: 0.9, page_numbers: [2] },
                    ],
                    page_count: 3,
                },
            }),
        ],
        rollup: { transcribing: 1, transcription_failed: 1, total: 6 },
        failures: [seedFailure()],
        activeJobs: [
            seedActiveJob({
                filename: 'שירה כהן.pdf', state: 'running',
                started_at: minutesAgo(0.8), attempt_count: 1,
            }),
        ],
    });
}

/** Only the transcription tail remains. */
export function transcribingOnlyBatch() {
    return seedBatch({
        items: [seedItem('t1', { status: 'approved' }), seedItem('t2', { status: 'approved' })],
        rollup: { transcribing: 2, approved: 2, total: 4 },
        activeJobs: [
            seedActiveJob({ filename: 'אחרון א.pdf', state: 'running', started_at: minutesAgo(2), attempt_count: 1 }),
            seedActiveJob({ filename: 'אחרון ב.pdf', state: 'queued' }),
        ],
    });
}

/** Everything terminal-approved (B6 contract answers present). */
export function completedBatch() {
    return seedBatch({
        status: 'completed',
        items: [
            seedItem('t1', { status: 'approved', approvedAnswers: [
                { question_number: 1, sub_question_id: null, answer_text: 'public int foo() { return 1; }' },
            ], gradedTestStatus: 'draft' }),
            seedItem('t2', { status: 'approved', gradedTestStatus: 'draft' }),
            seedItem('t3', { status: 'approved', gradedTestStatus: 'grading' }),
        ],
        rollup: { approved: 3, total: 3, draft: 2, grading: 1 },
    });
}
