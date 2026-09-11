/**
 * The review view-model: (draft, overlay, policy, answers, rubric) → what the
 * surface renders. Pure, so the whole R4–R11 shape is testable without a DOM.
 *
 * ── WHERE THE PIECES COME FROM ────────────────────────────────────────────
 * The graded-test wire carries the grade AND the student answer it was graded
 * against (EVD-1). Only the question text is still fetched separately, and this
 * module is where that join lives so no component has to know:
 *
 *   answer        THE GRADED-TEST WIRE ITSELF (`scope.student_answer`). It is
 *                 EVIDENCE of what the grader consumed (EVD-1), resolved
 *                 server-side by the one compiler that owns the rule — not a
 *                 client join against a second artifact. The join that used to
 *                 live here re-implemented the backend's nearest-ancestor
 *                 fallback as "exact, else whole-question" and silently failed
 *                 at depth 2; do not reintroduce one.
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

import { markRangesFor, spansForChecks } from '@/utils/evidence-highlight';
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
import { RV_BLOCK_GENERIC, RV_BLOCK_LLM_FAILURE } from '@/copy/grade-review';
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
    /**
     * [EVD-1] The answer this scope was graded against, resolved server-side.
     * Optional on the type because a row graded before the field exists — and
     * one whose inputs have since moved, so the server REFUSED to resolve it
     * rather than guess — legitimately has none.
     */
    student_answer?: {
        text: string;
        source: 'own' | 'inherited';
        inherited_from?: string | null;
    } | null;
}

export interface WireFeedbackText { text: string; basis_hash?: string }

export interface WireAnnotation {
    severity?: string | null;
    annotation_type?: string | null;
    target_id?: string | null;
    message?: string | null;
}

export interface WireDraft {
    scope_outcomes?: WireScope[] | null;
    feedback?: {
        scopes?: Record<string, WireFeedbackText>;
        summary?: WireFeedbackText;
    } | null;
    plan_version?: string | null;
    /**
     * The teacher-facing diagnostic surface (§6). This page never read it, so
     * an ERROR that blocks approval was invisible until the server refused —
     * and the refusal carried no sentence either, so she saw «שגיאת שרת (422)»
     * and clicked again (2026-09-09).
     */
    annotations?: WireAnnotation[] | null;
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
    /**
     * Whether a mark will actually be painted for this quote — decided by the
     * real matcher against the real answer, not inferred from `quote_status`.
     * The button renders on THIS, so an affordance that lands nowhere cannot
     * exist.
     */
    canHighlight: boolean;
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
    /**
     * [EVD-1] What this scope was GRADED AGAINST, as the server resolved it.
     *
     * A discriminated union, not `string | null` beside a separate flag: the
     * bug this replaced was two fields that could disagree, and did — a leaf
     * whose answer was inherited from its parent rendered «no answer in the
     * approved transcription» next to a full-marks grade and a verbatim quote
     * from that same answer. One field cannot contradict itself.
     *
     * `unavailable` is NOT `missing`. Missing means the student wrote nothing;
     * unavailable means we cannot show what was graded (a legacy row whose
     * inputs have since moved). Collapsing them would put a false accusation
     * on screen, which is the failure §3.5a exists to prevent.
     */
    answer: ScopeAnswerView;
    possible: string;
    awarded: string;
    overridden: boolean;
    gradedBy: string;
    criteria: ReviewCriterion[];
    feedback: { text: string; state: FeedbackState };
    markerCount: number;
}

export interface ApprovalBlocker {
    /** The scope it anchors to (`q1.ב`), or null for a whole-test blocker. */
    scopeId: string | null;
    message: string;
}

export interface ReviewModel {
    scopes: ReviewScope[];
    total: string;
    possible: string;
    anyOverride: boolean;
    summary: { text: string; state: FeedbackState };
    /** A pre-v5 draft cannot be reviewed here — the surface refuses. */
    renderable: boolean;
    /** Unresolved ERRORs — non-empty means the server WILL refuse (§11). */
    blockers: ApprovalBlocker[];
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
export type ScopeAnswerView =
    | { kind: 'own'; text: string }
    | { kind: 'inherited'; text: string; from: string | null }
    | { kind: 'missing' }
    | { kind: 'unavailable' };

/**
 * Read the answer the SERVER resolved. No join, no fallback, no re-derivation.
 *
 * This replaced a client-side join that re-implemented the backend's
 * nearest-ancestor rule as "exact, else whole-question" — a mirror whose own
 * header comment claimed parity with `gradable_compiler` while silently
 * failing at depth 2. Two derivations of one fact cannot be kept in agreement;
 * the server now sends the fact.
 *
 * The `unavailable` branch is the important one: a scope the grader actually
 * graded, with no evidence attached, is a contradiction in the data — never a
 * statement that the student left it blank.
 */
export function answerViewOf(scope: WireScope): ScopeAnswerView {
    const answer = scope.student_answer;
    if (answer) {
        return answer.source === 'inherited'
            ? { kind: 'inherited', text: answer.text, from: answer.inherited_from ?? null }
            : { kind: 'own', text: answer.text };
    }
    return scope.graded_by === 'skipped_no_answer'
        ? { kind: 'missing' }
        : { kind: 'unavailable' };
}

/**
 * A scope's own path, then each ANCESTOR path, then the whole question (null).
 *
 * "א.1" → ["א.1", "א", null].  "א" → ["א", null].  null → [null].
 *
 * One walk, shared, mirroring `gradable_compiler`'s nearest-ancestor rule. The
 * two-probe version this replaced (exact, else whole-question) skipped every
 * INTERMEDIATE ancestor, so it worked at depth 1 and silently failed at depth 2
 * — which is precisely how the answer bug hid, and why this is a walk rather
 * than another pair of lookups.
 */
export function ancestorPaths(subQuestionId: string | null | undefined): (string | null)[] {
    const out: (string | null)[] = [];
    let cursor = subQuestionId ?? null;
    while (cursor) {
        out.push(cursor);
        const cut = cursor.lastIndexOf('.');
        cursor = cut === -1 ? null : cursor.slice(0, cut);
    }
    out.push(null);                      // the whole question, always last
    return out;
}

/**
 * The prose for this scope: its own, else the nearest ancestor's, else the
 * question's. Null when the rubric carries none at any level.
 *
 * Unlike the answer (EVD-1) this is NOT evidence — it is rubric content the
 * client already holds — so resolving it here is legitimate. What was not
 * legitimate was resolving it at only two depths.
 */
export function questionTextForScope(
    scope: WireScope,
    questions: readonly QuestionText[],
): string | null {
    for (const path of ancestorPaths(scope.sub_question_id)) {
        const match = questions.find((q) => q.question_id === scope.question_id
            && (q.sub_question_id ?? null) === path);
        if (match) return match.text;
    }
    return null;
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

/**
 * The ERRORs that will make the server refuse this approval.
 *
 * EARLY WARNING, never authority — `compile_graded_test` is the authority and
 * says so (§11). The point is that she should never REACH a 422: the blocker
 * is named on the page, anchored to the scope that carries it, before she
 * presses אישור.
 *
 * [OD-R1] `llm_failure` is the one class her own verdicts resolve, mirroring
 * `graded_test_contract_compiler::_llm_failure_resolved_by_teacher` — and it
 * mirrors the same BAR: every check in the scope, because a check she has not
 * decided still carries the crash's unread zero. A scope with no checks is
 * never vacuously resolved, which is what keeps pre-OD-R1 drafts refusing.
 */
function approvalBlockers(
    draft: WireDraft,
    overlay: OverlayTerminals,
): ApprovalBlocker[] {
    const errors = (draft.annotations ?? []).filter(
        (a) => (a.severity ?? '').toUpperCase() === 'ERROR');
    if (errors.length === 0) return [];

    const decided = overriddenCheckIds(overlay);
    const checksByScope = new Map<string, string[]>();
    for (const scope of draft.scope_outcomes ?? []) {
        checksByScope.set(scopeIdOf(scope), leavesOf(scope).flatMap(
            ({ leaf }) => (leaf.checks ?? []).map((c) => c.check_id)));
    }

    return errors.flatMap((annotation): ApprovalBlocker[] => {
        const scopeId = annotation.target_id ?? null;
        if (annotation.annotation_type === 'llm_failure' && scopeId) {
            const checks = checksByScope.get(scopeId) ?? [];
            if (checks.length > 0 && checks.every((id) => decided.has(id))) return [];
            return [{ scopeId, message: RV_BLOCK_LLM_FAILURE(scopeId) }];
        }
        return [{ scopeId, message: annotation.message || RV_BLOCK_GENERIC }];
    });
}

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
        draft, overlay, policy, questions,
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
        // The text every check in this scope cites. Read ONCE: it is the same
        // answer for all of them, and it is what decides whether a quote can
        // be placed at all.
        const answerText = scope.student_answer?.text ?? '';
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
                    // [quote highlight] Whether a mark will ACTUALLY appear.
                    //
                    // Decided here because this is the only place that holds
                    // both the check and the answer it cites. `hasQuoteButton`
                    // used to answer it from `quote_status` alone — but that
                    // status is the SERVER's verdict under ITS normalisation,
                    // so it said "yes" for spans the renderer could not place
                    // and the button landed nowhere. Asking the real matcher
                    // makes the affordance true by construction: the button
                    // exists exactly when the highlight does.
                    //
                    // BOTH halves, from the one source. `spansForChecks` is the
                    // eligibility rule the highlight resolver itself applies —
                    // a `not_found` quote is never painted, because painting a
                    // best guess for invented credit manufactures the very
                    // evidence the flag exists to report as missing. Asking the
                    // matcher ALONE let that case back in: the client's fuzzy
                    // floor (0.6) is looser than the server's certification
                    // (0.85), so a quote the server rated `not_found` can still
                    // be placed here — `canHighlight` said yes, the resolver
                    // said no, and the button landed nowhere after all. That is
                    // the exact defect this field was introduced to remove, so
                    // it is removed on both paths at once (S3 review).
                    canHighlight: spansForChecks([{
                        check_id: check.check_id,
                        quote: check.quote,
                        quote_status: check.quote_status,
                    }]).some((s) => markRangesFor(answerText, s.quote, s.kind).length > 0),
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
            answer: answerViewOf(scope),
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
        blockers: approvalBlockers(draft, overlay),
    };
}

export { basisHash };
