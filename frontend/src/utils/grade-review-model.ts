/**
 * The review view-model: (draft, overlay, policy, answers, rubric) → what the
 * surface renders. Pure, so the whole R4–R11 shape is testable without a DOM.
 *
 * ── WHERE THE PIECES COME FROM ────────────────────────────────────────────
 * The graded-test wire carries the GRADE and nothing else — no student answer,
 * no question text. Both are reachable, and this module is where the join
 * lives so no component has to know:
 *
 *   answer        GET /batches/{id} → transcriptions[] matched on
 *                 `graded_test_id` → `approved_answers`
 *   question text GET /rubrics/{id} → the contract's questions
 *
 * Reported as OD-F9: two extra round trips for data the review route always
 * needs. A `?include=answers,questions` on the graded-test GET would collapse
 * them, and the seam here is deliberately one function so that change is a
 * one-line swap rather than a component rewrite.
 *
 * ── THE ANSWER FALLBACK IS LOAD-BEARING ───────────────────────────────────
 * The transcription pipeline segments to depth 1, so a nested leaf (`q1.א.2`)
 * often has no answer of its own and inherits its nearest ancestor's — the same
 * rule `gradable_compiler` applies when it builds the grading input. Without it
 * every nested rubric renders an empty answer box next to a real grade, which
 * is the worst possible pairing: it looks like the student wrote nothing and
 * was marked anyway.
 */

import {
    priceScopeCheckContributions,
    priceScopeChecksDetailed,
    type NumericPolicy,
    type PricingCheck,
    type ScopeTerminal,
    type Verdict,
} from '@/lib/pricing';
import {
    effectiveVerdict,
    findOverride,
    isOverridden,
    overriddenCheckIds,
    type OverlayTerminals,
} from './verdict-cycle';
import { basisHash, feedbackState, type FeedbackState } from './feedback-staleness';
import { add, dec, toString as decToString } from '@/lib/decimal';

// ── wire shapes (structural, so fixtures type as readily as live payloads) ──

export interface WireCheck extends PricingCheck {
    text: string;
    basis_he?: string;
    /** The verbatim span the model cited. Not a pricing input — the pricer
     *  reads only `quote_status` — but the review surface highlights it. */
    quote?: string | null;
}

export interface WireLeaf {
    criterion_id?: string;
    sub_criterion_id?: string;
    description?: string;
    points_possible: string;
    points_awarded: string;
    checks?: WireCheck[] | null;
    flags?: { reason: string }[] | null;
}

export interface WireCriterion extends WireLeaf {
    criterion_id: string;
    sub_criterion_outcomes?: WireLeaf[] | null;
}

export interface WireScope {
    question_id: string;
    sub_question_id?: string | null;
    points_possible: string;
    points_awarded: string;
    graded_by: string;
    criterion_outcomes?: WireCriterion[] | null;
}

export interface WireFeedbackText { text: string; basis_hash?: string }

export interface WireDraft {
    scope_outcomes?: WireScope[] | null;
    feedback?: {
        scopes?: Record<string, WireFeedbackText>;
        summary?: WireFeedbackText;
    } | null;
    plan_version?: string | null;
}

export interface AnswerItem {
    question_number: number;
    sub_question_id?: string | null;
    answer_text: string;
}

export interface QuestionText {
    question_id: string;
    sub_question_id?: string | null;
    text: string;
}

// ── the view model ─────────────────────────────────────────────────────────

export interface ReviewCheck {
    check_id: string;
    text: string;
    basis_he?: string;
    kind: PricingCheck['kind'];
    quote?: string | null;
    quote_status?: PricingCheck['quote_status'];
    /** Counted checks: «k מתוך N» beside the verdict (PLAN COMPILER v2, C3). */
    unit_count?: number | null;
    units_correct?: number | null;
    /** Vivi's proposal — immutable provenance. */
    aiVerdict: Verdict;
    /** What Vivi's own verdict was worth, for the struck-through proposal. */
    aiAwarded: string;
    /** After the overlay. */
    verdict: Verdict;
    overridden: boolean;
    note: string | null;
    evidenceDisputed: boolean;
    awarded: string;
    outOf: string;
    terminalId: string;
}

export interface ReviewCriterion {
    terminalId: string;
    description: string;
    awarded: string;
    possible: string;
    overridden: boolean;
    checks: ReviewCheck[];
}

export interface ReviewScope {
    scopeId: string;
    title: string;
    questionText: string | null;
    answer: string | null;
    possible: string;
    awarded: string;
    overridden: boolean;
    gradedBy: string;
    criteria: ReviewCriterion[];
    feedback: { text: string; state: FeedbackState };
    markerCount: number;
}

export interface ReviewModel {
    scopes: ReviewScope[];
    total: string;
    possible: string;
    anyOverride: boolean;
    summary: { text: string; state: FeedbackState };
    /** A pre-v5 draft cannot be reviewed here — the surface refuses. */
    renderable: boolean;
}

/** `q1` + `א` → «שאלה 1.א»; the id keeps the full path for anchoring. */
export function scopeIdOf(scope: WireScope): string {
    return scope.sub_question_id
        ? `${scope.question_id}.${scope.sub_question_id}`
        : scope.question_id;
}

export function scopeTitle(scope: WireScope): string {
    const number = scope.question_id.replace(/^q/i, '');
    return scope.sub_question_id
        ? `שאלה ${number}.${scope.sub_question_id}`
        : `שאלה ${number}`;
}

/** The digits in `q1` / `q12`. Non-numeric ids yield NaN and simply never match. */
function questionNumber(questionId: string): number {
    return Number.parseInt(questionId.replace(/^q/i, ''), 10);
}

/**
 * The answer for one scope: exact `(question, sub)` first, then the ancestor's
 * bare-question answer. See the module doc for why the fallback exists.
 */
export function answerForScope(
    scope: WireScope,
    answers: readonly AnswerItem[],
): string | null {
    const number = questionNumber(scope.question_id);
    const exact = answers.find((a) => a.question_number === number
        && (a.sub_question_id ?? null) === (scope.sub_question_id ?? null));
    if (exact) return exact.answer_text;
    const ancestor = answers.find((a) => a.question_number === number
        && (a.sub_question_id ?? null) === null);
    return ancestor ? ancestor.answer_text : null;
}

export function questionTextForScope(
    scope: WireScope,
    questions: readonly QuestionText[],
): string | null {
    const exact = questions.find((q) => q.question_id === scope.question_id
        && (q.sub_question_id ?? null) === (scope.sub_question_id ?? null));
    if (exact) return exact.text;
    const ancestor = questions.find((q) => q.question_id === scope.question_id
        && (q.sub_question_id ?? null) === null);
    return ancestor ? ancestor.text : null;
}

/** Leaves of one scope, flattened the way the pricer expects. */
function leavesOf(scope: WireScope): { criterion: WireCriterion; leaf: WireLeaf }[] {
    const out: { criterion: WireCriterion; leaf: WireLeaf }[] = [];
    for (const criterion of scope.criterion_outcomes ?? []) {
        const subs = criterion.sub_criterion_outcomes;
        const leaves = subs && subs.length ? subs : [criterion];
        for (const leaf of leaves) out.push({ criterion, leaf });
    }
    return out;
}

const terminalIdOf = (criterion: WireCriterion, leaf: WireLeaf): string =>
    leaf.sub_criterion_id || criterion.criterion_id;

/** The scope's checks in document order — the vector `basis_hash` covers. */
export function scopeBasisChecks(
    scope: WireScope,
    overlay: OverlayTerminals,
): { check_id: string; verdict: Verdict }[] {
    return leavesOf(scope).flatMap(({ criterion, leaf }) => {
        const terminalId = terminalIdOf(criterion, leaf);
        return (leaf.checks ?? []).map((check) => ({
            check_id: check.check_id,
            verdict: effectiveVerdict(overlay, terminalId, check.check_id, check.verdict),
        }));
    });
}

export interface BuildOptions {
    draft: WireDraft;
    overlay: OverlayTerminals;
    policy: NumericPolicy;
    answers: readonly AnswerItem[];
    questions: readonly QuestionText[];
    /** Feedback targets she has edited herself — never called stale. */
    editedFeedback?: ReadonlySet<string>;
    /** Her working copy of the feedback text, if any. */
    feedbackOverrides?: Record<string, string>;
    /**
     * `total_possible` from the wire — the contract's ACHIEVABLE total.
     *
     * NEVER re-summed from the scopes. On a "choose k of N" exam the achievable
     * total is the top-k by DECLARED POINTS while the scopes she can see are
     * whatever the grader scored, so a client sum silently disagrees with the
     * denominator the contract freezes. That is the selection-scoring incident
     * verbatim (CLAUDE.md §5: no consumer re-sums scopes).
     *
     * The sum is used only when the wire omits it, and then it is exactly the
     * legacy offered-Σ, which is correct on a rubric with no selection groups.
     */
    totalPossible?: string | null;
}

export function buildReviewModel(options: BuildOptions): ReviewModel {
    const {
        draft, overlay, policy, answers, questions,
        editedFeedback = new Set<string>(), feedbackOverrides = {},
        totalPossible = null,
    } = options;

    const decided = overriddenCheckIds(overlay);
    const scopes: ReviewScope[] = [];
    let total = dec('0');
    let possibleTotal = dec('0');
    let anyOverride = false;
    let sawChecks = false;

    for (const scope of draft.scope_outcomes ?? []) {
        const scopeId = scopeIdOf(scope);
        const leaves = leavesOf(scope);

        // Effective checks first: the pricer must see HER verdicts, not the
        // AI's, or the number under her hand would lag her own decision.
        const terminals: ScopeTerminal[] = leaves.map(({ criterion, leaf }) => {
            const terminalId = terminalIdOf(criterion, leaf);
            return {
                terminal_id: terminalId,
                points_possible: leaf.points_possible,
                checks: (leaf.checks ?? []).map((check) => ({
                    ...check,
                    verdict: effectiveVerdict(
                        overlay, terminalId, check.check_id, check.verdict),
                })),
            };
        });
        const priced = priceScopeChecksDetailed(terminals, policy, decided);
        // Per-row numbers: scope-wide, so a tariff shows its DEDUCTION and a
        // charge-group duplicate honestly shows nothing.
        const contributions = priceScopeCheckContributions(terminals, policy, decided);
        // What Vivi alone would have contributed — the struck-through proposal.
        const aiContributions = priceScopeCheckContributions(
            leaves.map(({ criterion: c, leaf: l }) => ({
                terminal_id: terminalIdOf(c, l),
                points_possible: l.points_possible,
                checks: l.checks ?? [],
            })),
            policy,
        );

        const byTerminal = new Map<string, ReviewCriterion>();
        let scopeOverridden = false;
        let markerCount = 0;

        for (const { criterion, leaf } of leaves) {
            const terminalId = terminalIdOf(criterion, leaf);
            const checks: ReviewCheck[] = (leaf.checks ?? []).map((check) => {
                if (check.quote_status === 'not_found' || check.quote_status === 'fuzzy') {
                    markerCount += 1;
                }
                sawChecks = true;
                const override = findOverride(overlay, terminalId, check.check_id);
                const overridden = isOverridden(
                    overlay, terminalId, check.check_id, check.verdict);
                if (overridden) scopeOverridden = true;
                const verdict = override?.verdict ?? check.verdict;
                // Per-check award: price this check alone, in its terminal's
                // context, so the row's number and the terminal's total come
                // from ONE arithmetic.
                const awarded = contributions[check.check_id] ?? '0';
                // Priced WITHOUT the override set, so it is genuinely what Vivi
                // proposed — including the evidence gating she is exempt from.
                const aiAwarded = aiContributions[check.check_id] ?? '0';
                return {
                    check_id: check.check_id,
                    text: check.text,
                    basis_he: check.basis_he,
                    kind: check.kind,
                    quote: check.quote,
                    quote_status: check.quote_status,
                    unit_count: check.unit_count,
                    units_correct: check.units_correct,
                    aiVerdict: check.verdict,
                    aiAwarded,
                    verdict,
                    overridden,
                    note: override?.teacher_comment ?? null,
                    evidenceDisputed: Boolean(override?.evidence_disputed),
                    awarded,
                    outOf: check.kind === 'tariff' ? (check.tariff ?? '0') : (check.points ?? '0'),
                    terminalId,
                };
            });

            byTerminal.set(terminalId, {
                terminalId,
                description: leaf.description || criterion.description || terminalId,
                awarded: priced[terminalId]?.awarded ?? '0',
                possible: leaf.points_possible,
                overridden: checks.some((c) => c.overridden),
                checks,
            });
        }

        const criteria = [...byTerminal.values()];
        const scopeAwarded = criteria.reduce(
            (sum, c) => add(sum, dec(c.awarded)), dec('0'));
        if (scope.graded_by === 'skipped_no_answer' || scope.graded_by === 'failed') {
            markerCount += 1;
        }

        // Selection exclusion is derived server-side from post-override scores
        // (CLAUDE.md §5) — an excluded scope is shown but never summed here.
        if (scope.graded_by !== 'excluded_by_selection') {
            total = add(total, scopeAwarded);
            possibleTotal = add(possibleTotal, dec(scope.points_possible));
        }
        if (scopeOverridden) anyOverride = true;

        const wireText = draft.feedback?.scopes?.[scopeId];
        const edited = editedFeedback.has(scopeId);
        scopes.push({
            scopeId,
            title: scopeTitle(scope),
            questionText: questionTextForScope(scope, questions),
            answer: answerForScope(scope, answers),
            possible: scope.points_possible,
            awarded: decToString(scopeAwarded),
            overridden: scopeOverridden,
            gradedBy: scope.graded_by,
            criteria,
            feedback: {
                text: feedbackOverrides[scopeId] ?? wireText?.text ?? '',
                state: feedbackState(
                    feedbackOverrides[scopeId] !== undefined
                        ? { text: feedbackOverrides[scopeId] }
                        : wireText,
                    scopeBasisChecks(scope, overlay),
                    edited,
                ),
            },
            markerCount,
        });
    }

    const allChecks = (draft.scope_outcomes ?? [])
        .flatMap((scope) => scopeBasisChecks(scope, overlay));
    const summaryWire = draft.feedback?.summary;
    const summaryEdited = editedFeedback.has('summary');

    return {
        scopes,
        total: decToString(total),
        possible: totalPossible ?? decToString(possibleTotal),
        anyOverride,
        summary: {
            text: feedbackOverrides.summary ?? summaryWire?.text ?? '',
            state: feedbackState(
                feedbackOverrides.summary !== undefined
                    ? { text: feedbackOverrides.summary }
                    : summaryWire,
                allChecks,
                summaryEdited,
            ),
        },
        // A draft with no checks anywhere predates the v5 pin. Rendering it
        // would show empty checklists — "nothing to check" on a test nobody
        // checked — so the surface refuses instead (§3.5a).
        renderable: sawChecks,
    };
}

export { basisHash };
