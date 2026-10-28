/**
 * look_count — how many things on this test need her eye (R9).
 *
 * A faithful port of `backend/app/services/look_count.py`. The dashboard reads
 * the server's number off the batch feed; this mirror computes the SAME number
 * from a draft the review route already holds, so the card and the open test
 * cannot disagree while she works.
 *
 * DETERMINISTIC MARKERS ONLY. This is a routing number, not a quality score —
 * it says where to look first on an evening with thirty papers, so it must be
 * reproducible from the draft alone and must never be the model's opinion about
 * its own confidence (OD5: numeric confidence is never rendered).
 *
 * THE CASE IT EXISTS FOR: a `met` check whose cited span is not in the answer.
 * That is invented credit and it is INVISIBLE in the score — the points look
 * ordinary — so if this misses it, nothing sends her there.
 *
 * One look per DISTINCT marker: a scope carrying two different problems earns
 * two looks; the same problem seen twice earns one.
 *
 * Audit marks are NOT counted — the consistency audit is deferred (ruling R-1),
 * and counting a surface that does not exist would inflate every card by
 * nothing.
 */

/** Flags meaning "a human should check this", not the pricer's eval-only ones. */
const LOOK_FLAGS: ReadonlySet<string> = new Set([
    'bounds_clamped', 'closed_world_violation', 'unverified_check', 'evidence_unverified',
]);

/** v3-era drafts carry no checks, so their quote problems live only as flags. */
const V3_QUOTE_FLAGS: ReadonlySet<string> = new Set(['quote_not_found', 'fuzzy_match']);

const UNVALIDATED: ReadonlySet<string> = new Set(['not_found', 'fuzzy']);

export interface LookCountCheck {
    check_id: string;
    quote_status?: string | null;
}

export interface LookCountFlag {
    reason: string;
}

export interface LookCountLeaf {
    criterion_id?: string;
    sub_criterion_id?: string;
    checks?: LookCountCheck[] | null;
    flags?: LookCountFlag[] | null;
    /** Vivi's points (wire: decimal strings). Read only for the figure-deduction marker. */
    points_awarded?: string | number | null;
    points_possible?: string | number | null;
}

export interface LookCountCriterion extends LookCountLeaf {
    criterion_id: string;
    sub_criterion_outcomes?: LookCountLeaf[] | null;
}

export interface LookCountScope {
    question_id: string;
    sub_question_id?: string | null;
    graded_by: string;
    criterion_outcomes?: LookCountCriterion[] | null;
    /** EVD-1: the answer this scope was graded against. */
    student_answer?: { text?: string | null } | null;
}

const FIGURE_LINE = /\[איור\s*\d+\s*:/;

/**
 * MATH_RENDERING_PLAN §5 (OD-M5): a DEDUCTION in a scope whose graded answer names a
 * drawing is a marker. A reader misses what is drawn while calling the figure complete
 * (measured 10/10), so a point taken there must be checked against the ink. Mirrors
 * backend `look_count._has_figure` + the `figure_deduction` rule exactly.
 */
export function isFigureDeduction(scope: LookCountScope, leaf: LookCountLeaf): boolean {
    if (!FIGURE_LINE.test(scope.student_answer?.text ?? '')) return false;
    if (leaf.points_awarded == null || leaf.points_possible == null) return false;
    return Number(leaf.points_awarded) < Number(leaf.points_possible);
}

export interface LookCountDraft {
    scope_outcomes?: LookCountScope[] | null;
}

export function scopeId(scope: LookCountScope): string {
    return scope.sub_question_id == null
        ? scope.question_id
        : `${scope.question_id}.${scope.sub_question_id}`;
}

export function lookCount(draft: LookCountDraft): number {
    const seen = new Set<string>();
    const mark = (a: string, b: string) => seen.add(`${a}\x00${b}`);

    for (const scope of draft.scope_outcomes ?? []) {
        // An excluded scope was never owed. Counting it would send her hunting
        // for a problem that does not exist — the needs_eyes over-count lesson
        // (CLAUDE.md §3.5a).
        if (scope.graded_by === 'excluded_by_selection') continue;
        if (scope.graded_by === 'skipped_no_answer' || scope.graded_by === 'failed') {
            mark(scopeId(scope), scope.graded_by);
            continue;
        }

        for (const criterion of scope.criterion_outcomes ?? []) {
            const leaves: LookCountLeaf[] = criterion.sub_criterion_outcomes?.length
                ? criterion.sub_criterion_outcomes
                : [criterion];
            for (const leaf of leaves) {
                const terminalId = leaf.sub_criterion_id || criterion.criterion_id;
                const hasChecks = Boolean(leaf.checks && leaf.checks.length > 0);
                if (isFigureDeduction(scope, leaf)) mark(terminalId, 'figure_deduction');
                for (const flag of leaf.flags ?? []) {
                    if (LOOK_FLAGS.has(flag.reason)) {
                        mark(terminalId, flag.reason);
                    } else if (V3_QUOTE_FLAGS.has(flag.reason) && !hasChecks) {
                        // Counted only for a leaf with no checks — a v5 leaf
                        // would otherwise be counted twice, once as a flag and
                        // once as the check's quote_status.
                        mark(terminalId, flag.reason);
                    }
                }
                for (const check of leaf.checks ?? []) {
                    if (check.quote_status && UNVALIDATED.has(check.quote_status)) {
                        mark(check.check_id, check.quote_status);
                    }
                }
            }
        }
    }
    return seen.size;
}

/** The marker ids in document order — what `F` walks (R9). */
export function markerCheckIds(draft: LookCountDraft): string[] {
    const ids: string[] = [];
    for (const scope of draft.scope_outcomes ?? []) {
        if (scope.graded_by === 'excluded_by_selection') continue;
        for (const criterion of scope.criterion_outcomes ?? []) {
            const leaves: LookCountLeaf[] = criterion.sub_criterion_outcomes?.length
                ? criterion.sub_criterion_outcomes
                : [criterion];
            for (const leaf of leaves) {
                for (const check of leaf.checks ?? []) {
                    if (check.quote_status && UNVALIDATED.has(check.quote_status)) {
                        ids.push(check.check_id);
                    }
                }
            }
        }
    }
    return ids;
}
