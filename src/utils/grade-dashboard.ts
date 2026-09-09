/**
 * The grade-review dashboard's arithmetic (spec §4.1, D2/D3/D6/D8/D9).
 *
 * Pure, so every state the teacher can land in is testable without a browser —
 * and so the three surfaces that must agree (the steps line, the attention
 * line, the pile) are derived from ONE reading of the feed rather than three.
 *
 * The honesty rules this file exists to keep:
 *
 *   * `look_count: null` is NOT zero. It means "this draft would not parse, so
 *     the number is not computable". Rendering it as 0 says "nothing to check"
 *     about precisely the test that most needs her eye — the `needs_eyes`
 *     over-count lesson pointed the other way (CLAUDE.md §3.5a). No number.
 *   * `eta.kind = "unknown"` renders «עוד רגע», never a figure. Publishing a
 *     time nothing supports is a confident guess about the one thing she is
 *     waiting on.
 *   * A `failed` test stays VISIBLE at completion. A batch completes with its
 *     hole showing rather than as "4 of 4".
 */

import { hebrewCount } from './hebrew-plural';

export type GradedStatus = 'pending' | 'grading' | 'draft' | 'approved' | 'failed';

export interface GradedItem {
    graded_test_id: string;
    student_id?: string | null;
    student_name?: string | null;
    status: GradedStatus | string;
    version?: number;
    landed_at?: string | null;
    opened_at?: string | null;
    total_awarded?: string | null;
    /** null = not computable, NOT zero. */
    look_count?: number | null;
    audit_touched?: 'none' | 'updated' | 'reapprove' | string;
    returned_exam_state?: 'none' | 'rendering' | 'ready' | 'stale' | string;
    page1_image_url?: string | null;
}

export interface BatchEta {
    kind: 'first_landing' | 'remaining' | 'unknown' | string;
    seconds?: number | null;
}

// ── D6 · the card state grammar ────────────────────────────────────────────

export type PileCardState =
    | 'pending'
    | 'grading'
    | 'landed'
    | 'landed_marked'
    | 'draft'
    | 'approved'
    | 'failed';

/**
 * One card, one state. `landed_marked` is split from `landed` because the
 * caption differs in kind, not degree: "ready to review" versus "k things to
 * look at" is the whole triage signal.
 *
 * An UNPARSEABLE draft (`look_count === null`) is `landed`, not
 * `landed_marked` — it gets no count, because it has none.
 */
export function pileCardState(item: GradedItem): PileCardState {
    switch (item.status) {
        case 'pending': return 'pending';
        case 'grading': return 'grading';
        case 'failed': return 'failed';
        case 'approved': return 'approved';
        case 'draft':
            if (item.opened_at) return 'draft';
            return (item.look_count ?? 0) > 0 ? 'landed_marked' : 'landed';
        default: return 'pending';
    }
}

/** Where a click on this card goes (D6). */
export function pileCardTarget(item: GradedItem): 'review' | 'preview' | 'retry' | null {
    const state = pileCardState(item);
    if (state === 'approved') return 'preview';
    if (state === 'failed') return 'retry';
    if (state === 'pending' || state === 'grading') return null;
    return 'review';
}

// ── D2 · the steps line ────────────────────────────────────────────────────

export type StepState = 'todo' | 'active' | 'done';

export interface Step {
    key: 'grading' | 'audit' | 'approve';
    label: string;
    state: StepState;
}

export interface Rollup {
    total: number;
    landed: number;
    approved: number;
    failed: number;
}

/**
 * `batchTotal` is the BATCH's test count, not `items.length`.
 *
 * `graded_tests` carries a row only for a test whose transcription she has
 * already accepted. On a ten-document batch with two accepted, `items.length`
 * is 2 — so a dashboard counting itself would say «נחתו 2 מתוך 2», «הכול מוכן»
 * and offer to download everything, while eight tests had not been graded at
 * all. The denominator has to come from the batch or the number is a
 * self-fulfilling one.
 *
 * It falls back to `items.length` only when the caller has no batch total,
 * which is the fixture-driven case.
 */
export function rollupOf(
    items: readonly GradedItem[],
    batchTotal?: number | null,
): Rollup {
    let landed = 0;
    let approved = 0;
    let failed = 0;
    for (const item of items) {
        if (item.status === 'approved') { approved += 1; landed += 1; }
        else if (item.status === 'draft') landed += 1;
        else if (item.status === 'failed') failed += 1;
    }
    return {
        total: Math.max(batchTotal ?? items.length, items.length),
        landed,
        approved,
        failed,
    };
}

/**
 * Two steps while the audit is disabled (R-1), three when it ships.
 *
 * The middle step is not rendered dark — a step nobody can reach teaches her
 * the line is decorative, which is how the next real step gets skimmed past.
 * `audit_status: "disabled"` is a product-scope state, not a frontend
 * accommodation.
 */
export function stepsLine(
    rollup: Rollup,
    auditStatus: string,
    labels: {
        grading: (landed: number, total: number) => string;
        audit: string;
        auditDone: (n: number) => string;
        approve: (approved: number, total: number) => string;
    },
    auditTouched = 0,
): Step[] {
    const gradingDone = rollup.landed + rollup.failed >= rollup.total && rollup.total > 0;
    const allApproved = rollup.total > 0 && rollup.approved + rollup.failed >= rollup.total;

    const steps: Step[] = [{
        key: 'grading',
        label: labels.grading(rollup.landed, rollup.total),
        state: gradingDone ? 'done' : 'active',
    }];

    if (auditStatus !== 'disabled') {
        steps.push({
            key: 'audit',
            label: auditStatus === 'done' ? labels.auditDone(auditTouched) : labels.audit,
            state: auditStatus === 'done' ? 'done'
                : auditStatus === 'running' ? 'active' : 'todo',
        });
    }

    steps.push({
        key: 'approve',
        label: labels.approve(rollup.approved, rollup.total),
        state: allApproved ? 'done' : gradingDone ? 'active' : 'todo',
    });
    return steps;
}

/** Minutes granularity — she does not act on seconds. */
export function etaText(
    eta: BatchEta | null | undefined,
    labels: {
        firstLanding: (minutes: number) => string;
        remaining: (minutes: number) => string;
        unknown: string;
    },
): string | null {
    if (!eta) return null;
    if (eta.kind === 'unknown' || eta.seconds == null) return labels.unknown;
    // Round UP: "about 1 minute" that turns out to be 90 seconds is a small
    // lie in the direction that makes her wait; rounding down is the one that
    // makes the product look late.
    const minutes = Math.max(1, Math.ceil(eta.seconds / 60));
    return eta.kind === 'first_landing'
        ? labels.firstLanding(minutes)
        : labels.remaining(minutes);
}

// ── D3 · the attention line ────────────────────────────────────────────────

export interface Attention {
    kind: 'worst' | 'done' | 'none';
    item?: GradedItem;
    /** How many markers that test carries — never rendered when not computable. */
    markers?: number;
}

/**
 * One slot, three variants, in priority order (D3). The audit banner would
 * outrank the worst test; it is deferred, so this is worst-then-done.
 *
 * "Worst" is the LANDED, unopened, unapproved test with the most markers. A
 * test she has already opened is not the one to send her to — she has seen it,
 * and re-nominating it would make the line feel stuck.
 *
 * A test whose count is NOT COMPUTABLE can never be "worst": there is no
 * number to rank it by, and inventing one to make it sortable is the exact
 * substitution §3.5a forbids.
 */
export function attentionLine(
    items: readonly GradedItem[],
    batchTotal?: number | null,
): Attention {
    const rollup = rollupOf(items, batchTotal);
    // Done means every test in the BATCH is accounted for — and at least one
    // was actually signed. An all-failed batch satisfies the arithmetic and is
    // the opposite of finished; «הכול מוכן. 0 המבחנים נחתמו» is a sentence no
    // teacher should ever read.
    if (rollup.total > 0
        && rollup.approved + rollup.failed >= rollup.total
        && rollup.approved > 0) {
        return { kind: 'done' };
    }

    let worst: GradedItem | undefined;
    let worstCount = 0;
    for (const item of items) {
        if (item.status !== 'draft' || item.opened_at) continue;
        const count = item.look_count;
        if (count == null || count <= worstCount) continue;
        worst = item;
        worstCount = count;
    }
    return worst ? { kind: 'worst', item: worst, markers: worstCount } : { kind: 'none' };
}

// ── D8 · the completion summary ────────────────────────────────────────────

export interface SessionSummary {
    approved: number;
    failed: number;
    minutes: number | null;
}

export function sessionSummary(
    items: readonly GradedItem[],
    startedAt: string | null | undefined,
    completedAt: string | null | undefined,
): SessionSummary {
    const rollup = rollupOf(items);
    const minutes = startedAt && completedAt
        ? Math.max(1, Math.round(
            (new Date(completedAt).getTime() - new Date(startedAt).getTime()) / 60000))
        : null;
    return { approved: rollup.approved, failed: rollup.failed, minutes };
}

// ── D9 · the download manifest ─────────────────────────────────────────────

export interface DownloadSummary {
    included: number;
    /** Reviewable but unsigned — she can still act on these. */
    excludedNotApproved: number;
    /** Signed, then edited — needs re-signing, a different action. */
    excludedStale: number;
    /** Never graded at all — she cannot approve these, only retry them. */
    excludedFailed: number;
}

/**
 * Approved-only, and it says so BEFORE it does anything (D9).
 *
 * Derived from the same items the pile renders, so the modal cannot promise a
 * different number from the one on screen. The real manifest endpoint is the
 * authority at download time; this is what the confirmation is allowed to
 * claim beforehand.
 */
export function downloadSummary(items: readonly GradedItem[]): DownloadSummary {
    let included = 0;
    let excludedNotApproved = 0;
    let excludedStale = 0;
    let excludedFailed = 0;
    for (const item of items) {
        // A failed test is counted APART from an unapproved one. Telling her
        // "N tests are not yet approved" about a test that can never be
        // approved sends her looking for a review that does not exist — the
        // same conflation this function already refuses to make for stale
        // exams, whose fix is re-signing rather than reviewing.
        if (item.status === 'failed') { excludedFailed += 1; continue; }
        if (item.status !== 'approved') { excludedNotApproved += 1; continue; }
        if (item.returned_exam_state === 'stale') { excludedStale += 1; continue; }
        included += 1;
    }
    return { included, excludedNotApproved, excludedStale, excludedFailed };
}

/** «מבחן אחד» / «N מבחנים» — the plural helper, so "1 מבחנים" cannot ship. */
export function testsCount(n: number): string {
    return hebrewCount(n, {
        zero: 'אין מבחנים',
        one: 'מבחן אחד',
        many: (x) => `${x} מבחנים`,
    });
}
