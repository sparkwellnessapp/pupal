/**
 * The grader-v6 review view-model (owner rulings 2026-10-17 §7, the MVC).
 *
 *     (v6 response, envelope draft, her live overlay) → what the v6 surface renders
 *
 * Pure, so every number and every mark on the surface is testable without a DOM.
 *
 * ── ONE PRICER ────────────────────────────────────────────────────────────
 * Every figure comes from `priceV6` (`lib/pricing-v6.ts`, PRC-7: byte-equal to
 * the Python on every committed vector) over a view built EXACTLY as the
 * server's `DraftV6Content.to_view()` builds it. Nothing here re-sums a scope,
 * a criterion or the test (CLAUDE.md §5) — the pricer's `PricedTest` is read.
 *
 * ── WHERE EACH PIECE COMES FROM ──────────────────────────────────────────
 *   the grade, chips, charges   priceV6(view(content), HER LIVE overlay)
 *   Vivi's pick                 the record's `model_option_id`, as the pricer
 *                               resolved it with NO overlay (`claimed_option_id`)
 *   her criterion text          the ENVELOPE's criterion / sub-criterion
 *                               `description` — her rubric words, verbatim
 *   the student's answer        the envelope's `scope.student_answer` (EVD-1,
 *                               never re-derived)
 *   the reasoning line          the server's `lines` — written at grade time, or
 *                               by the fallback composer after her edit. The
 *                               client never composes one (no LLM, no mirror).
 *
 * ── TWO SERVER RULES ARE MIRRORED, AS EARLY WARNING ONLY ─────────────────
 * `undecidedChecks` mirrors `services/v6_review.undecided_checks` and
 * `blockersV6` mirrors the annotation half of `_compile_v6` — so a blocker is
 * named on the page BEFORE she presses אישור. The approval gate stays the
 * authority (§11); both are pinned against the server's own output by
 * `grade-review-v6-model.test.ts`.
 */

import type { components } from '@/lib/api-types';
import { cmp, dec } from '@/lib/decimal';
import {
    priceV6,
    type Chip,
    type DraftV6View,
    type FaultStatus,
    type PricedTest,
    type PricedTerminal,
    type PricingOverlay,
    type ResolutionSource,
    type ResolvedCheck,
} from '@/lib/pricing-v6';
import {
    answerViewOf,
    questionTextForScope,
    scopeIdOf,
    scopeTitle,
    type ApprovalBlocker,
    type QuestionText,
    type ScopeAnswerView,
    type WireDraft,
    type WireScope,
} from './grade-review-model';
import { RV_BLOCK_GENERIC, RV_BLOCK_UNDECIDED } from '@/copy/grade-review';
import { V6_BLOCK_FAILED } from '@/copy/grade-review-v6';

// ── wire types (GENERATED — never hand-mirrored) ───────────────────────────
export type GradedTestV6Response = components['schemas']['GradedTestV6Response'];
export type DraftV6Content = components['schemas']['DraftV6Content'];
export type CheckRecordV6 = components['schemas']['CheckRecordV6'];
export type OverlayPatchV6 = components['schemas']['OverlayPatchV6'];
export type V6ReasoningLine = components['schemas']['V6ReasoningLine'];

/** Her decision on one check, as this client holds it: an option, a comment, or both. */
export interface CheckChoice {
    option_id: string | null;
    comment: string | null;
}

/** Her working copy. The pricer's own input shape, restricted to what the MVC allows. */
export interface OverlayV6 {
    checks: Record<string, CheckChoice>;
    terminal_points: Record<string, string>;
}

export const emptyOverlayV6 = (): OverlayV6 => ({ checks: {}, terminal_points: {} });

// ── routing ────────────────────────────────────────────────────────────────

/**
 * Is this graded-test draft a grader-v6 grade? Exactly the server's rule:
 * `GradedTestDraft.v6` is non-null for a v6 grade only, and its `plan_schema`
 * is "plan/v6". Anything else — every v3/v5 draft — keeps the v5 surface.
 */
export function isV6Draft(draft: unknown): boolean {
    const v6 = (draft as { v6?: unknown } | null | undefined)?.v6;
    return typeof v6 === 'object' && v6 !== null
        && (v6 as { plan_schema?: unknown }).plan_schema === 'plan/v6';
}

// ── the pricer's input ─────────────────────────────────────────────────────

/** `DraftV6Content.to_view()`, field for field. */
export function viewOf(content: DraftV6Content): DraftV6View {
    return {
        precision: content.precision,
        terminals: content.view_terminals,
        selection: content.selection,
        checks: content.checks.map((c) => ({
            plan: c.plan,
            plan_index: c.plan_index,
            model_option_id: c.model_option_id ?? null,
            quote_status: c.quote_status ?? null,
        })),
    };
}

/** The overlay as the pricer reads it. */
export function pricingOverlayOf(overlay: OverlayV6): PricingOverlay {
    return { checks: overlay.checks, terminal_points: overlay.terminal_points };
}

// ── her working copy, normalised ───────────────────────────────────────────

const blank = (s: string | null | undefined): boolean => !s || s.trim() === '';

/**
 * The server's overlay (`GradedTestV6Response.overlay`) as this client holds it.
 * `amount` and `evidence_disputed` are v6.1 — refused by the server — so they
 * are not carried; a stored record that has neither an option nor a comment
 * is no record at all (`merge_overlay`'s own rule).
 */
export function overlayFromWire(wire: PricingOverlay | null | undefined): OverlayV6 {
    const out = emptyOverlayV6();
    for (const [id, d] of Object.entries(wire?.checks ?? {})) {
        const option = d?.option_id ?? null;
        const comment = blank(d?.comment) ? null : (d?.comment as string);
        if (option !== null || comment !== null) out.checks[id] = { option_id: option, comment };
    }
    for (const [id, v] of Object.entries(wire?.terminal_points ?? {})) {
        if (v != null) out.terminal_points[id] = String(v);
    }
    return out;
}

function withChoice(overlay: OverlayV6, checkId: string, choice: CheckChoice | null): OverlayV6 {
    const checks = { ...overlay.checks };
    if (choice === null || (choice.option_id === null && blank(choice.comment))) {
        delete checks[checkId];
    } else {
        checks[checkId] = {
            option_id: choice.option_id,
            comment: blank(choice.comment) ? null : choice.comment,
        };
    }
    return { ...overlay, checks };
}

/**
 * She chose `optionId` for a check.
 *
 * Choosing what Vivi's own pick ALREADY resolves to withdraws her decision
 * instead of recording a copy of it — that is the way back to Vivi. Only when
 * Vivi's pick STANDS, though (`source === 'model'`): on a check Vivi left
 * undecided, or whose credit was held back for want of evidence, the same
 * click is a real decision of hers and is kept (OD-4; AM-G2: her selection is
 * never gated).
 */
export function chooseOption(
    overlay: OverlayV6,
    checkId: string,
    optionId: string,
    vivi: Pick<ResolvedCheck, 'source' | 'option_id'>,
): OverlayV6 {
    const comment = overlay.checks[checkId]?.comment ?? null;
    if (vivi.source === 'model' && vivi.option_id === optionId) {
        return withChoice(overlay, checkId, { option_id: null, comment });
    }
    return withChoice(overlay, checkId, { option_id: optionId, comment });
}

/** «חזרה להצעת ויוי» — her option goes; her comment, if any, stays. */
export function withdrawOption(overlay: OverlayV6, checkId: string): OverlayV6 {
    const comment = overlay.checks[checkId]?.comment ?? null;
    return withChoice(overlay, checkId, { option_id: null, comment });
}

export function setComment(overlay: OverlayV6, checkId: string, text: string | null): OverlayV6 {
    const option = overlay.checks[checkId]?.option_id ?? null;
    return withChoice(overlay, checkId, { option_id: option, comment: text });
}

/** She set the criterion's grade by hand. `amount` is already validated (PointsInput). */
export function setPin(overlay: OverlayV6, terminalId: string, amount: string): OverlayV6 {
    return { ...overlay, terminal_points: { ...overlay.terminal_points, [terminalId]: amount } };
}

export function clearPin(overlay: OverlayV6, terminalId: string): OverlayV6 {
    const terminal_points = { ...overlay.terminal_points };
    delete terminal_points[terminalId];
    return { ...overlay, terminal_points };
}

// ── what a PATCH carries ───────────────────────────────────────────────────

const sameChoice = (a: CheckChoice | undefined, b: CheckChoice | undefined): boolean =>
    (a?.option_id ?? null) === (b?.option_id ?? null)
    && (a?.comment ?? '').trim() === (b?.comment ?? '').trim();

const samePin = (a: string | undefined, b: string | undefined): boolean =>
    a === undefined || b === undefined ? a === b : cmp(dec(a), dec(b)) === 0;

/**
 * The keys she changed since `saved` (what the server last confirmed) — and only
 * those, because PATCH /v6/draft MERGES: a present key sets that decision, a
 * null withdraws it, and an absent key is left exactly as stored. Sending her
 * whole overlay would be correct too, but it would also overwrite a decision
 * made in another tab with this tab's stale copy of it.
 *
 * A check's record travels WHOLE (`option_id` and `comment` together): the
 * server replaces the record, it does not merge its fields.
 *
 * `null` when nothing changed.
 */
export function overlayPatch(saved: OverlayV6, current: OverlayV6): OverlayPatchV6 | null {
    const checks: NonNullable<OverlayPatchV6['checks']> = {};
    for (const id of new Set([...Object.keys(saved.checks), ...Object.keys(current.checks)])) {
        const before = saved.checks[id];
        const now = current.checks[id];
        if (sameChoice(before, now)) continue;
        checks[id] = now ? { option_id: now.option_id, comment: now.comment } : null;
    }
    const terminal_points: NonNullable<OverlayPatchV6['terminal_points']> = {};
    for (const id of new Set([
        ...Object.keys(saved.terminal_points), ...Object.keys(current.terminal_points),
    ])) {
        const before = saved.terminal_points[id];
        const now = current.terminal_points[id];
        if (samePin(before, now)) continue;
        terminal_points[id] = now ?? null;
    }
    const anyChecks = Object.keys(checks).length > 0;
    const anyPins = Object.keys(terminal_points).length > 0;
    if (!anyChecks && !anyPins) return null;
    return {
        ...(anyChecks ? { checks } : {}),
        ...(anyPins ? { terminal_points } : {}),
    };
}

/** Feedback texts she changed since the last save (`summary` or a scope id). */
export function feedbackPatch(
    saved: Record<string, string>,
    current: Record<string, string>,
): Record<string, string | null> {
    const out: Record<string, string | null> = {};
    for (const key of new Set([...Object.keys(saved), ...Object.keys(current)])) {
        if (saved[key] === current[key]) continue;
        out[key] = current[key] ?? null;
    }
    return out;
}

/**
 * The criteria an overlay change touches — the ones whose reasoning line the
 * server will rewrite (`v6_review.touched_terminals`: a decided option or a
 * pin). A comment alone moves no grade and rewrites no line.
 */
export function touchedTerminals(
    before: OverlayV6,
    after: OverlayV6,
    terminalOfCheck: ReadonlyMap<string, string>,
): Set<string> {
    const out = new Set<string>();
    for (const id of new Set([...Object.keys(before.checks), ...Object.keys(after.checks)])) {
        if ((before.checks[id]?.option_id ?? null) !== (after.checks[id]?.option_id ?? null)) {
            const tid = terminalOfCheck.get(id);
            if (tid) out.add(tid);
        }
    }
    for (const id of new Set([
        ...Object.keys(before.terminal_points), ...Object.keys(after.terminal_points),
    ])) {
        if (!samePin(before.terminal_points[id], after.terminal_points[id])) out.add(id);
    }
    return out;
}

// ── the two mirrored server rules ──────────────────────────────────────────

const scopeKey = (questionId: string, subQuestionId: string | null | undefined): string =>
    subQuestionId ? `${questionId}.${subQuestionId}` : questionId;

/**
 * [OD-4] Mirror of `v6_review.undecided_checks`: a check a call SHOULD have
 * answered (its scope was graded, or failed) for which no valid pick came back,
 * that she has not decided (an option of hers, or the criterion set by hand).
 * Notes never block, and a blank answer's checks are not undecided.
 */
export function undecidedChecks(
    content: DraftV6Content,
    aiPriced: PricedTest,
    overlay: OverlayV6,
): string[] {
    const called = new Set(content.scopes
        .filter((s) => s.graded_by === 'llm' || s.graded_by === 'failed')
        .map((s) => scopeKey(s.question_id, s.sub_question_id)));
    const scopeOf = new Map(content.view_terminals.map(
        (t) => [t.terminal_id, scopeKey(t.question_id, t.sub_question_id)]));
    const plans = new Map(content.checks.map((c) => [c.plan.check_id, c.plan]));
    const out: string[] = [];
    for (const r of aiPriced.checks) {
        const plan = plans.get(r.check_id);
        if (!plan || plan.role === 'note' || !r.missing) continue;
        const tid = plan.priced_terminal_id;
        const decided = (overlay.checks[r.check_id]?.option_id ?? null) !== null;
        const pinned = overlay.terminal_points[tid] !== undefined;
        if (called.has(scopeOf.get(tid) ?? '') && !decided && !pinned) out.push(r.check_id);
    }
    return out;
}

/**
 * Mirror of `_compile_v6`'s gate, early warning only: every unresolved ERROR
 * annotation (a stray machine verdict — `closed_world_violation` — never
 * blocks; an `llm_failure` is resolved once she decided every non-note check of
 * that question, or set its criteria by hand), then one blocker per question
 * with undecided checks, anchored so the surface can take her there.
 */
export function blockersV6(
    draft: WireDraft,
    content: DraftV6Content,
    overlay: OverlayV6,
    undecided: readonly string[],
): ApprovalBlocker[] {
    const terminalsOfScope = new Map<string, string[]>();
    for (const t of content.view_terminals) {
        const key = scopeKey(t.question_id, t.sub_question_id);
        terminalsOfScope.set(key, [...(terminalsOfScope.get(key) ?? []), t.terminal_id]);
    }
    const resolved = (scopeId: string): boolean => {
        const tids = new Set(terminalsOfScope.get(scopeId) ?? []);
        if (tids.size === 0) return false;
        return content.checks.every((c) => !tids.has(c.plan.priced_terminal_id)
            || c.plan.role === 'note'
            || overlay.terminal_points[c.plan.priced_terminal_id] !== undefined
            || (overlay.checks[c.plan.check_id]?.option_id ?? null) !== null);
    };
    const titleOf = (scopeId: string): string => {
        const scope = (draft.scope_outcomes ?? []).find((s) => scopeIdOf(s) === scopeId);
        return scope ? scopeTitle(scope) : scopeId;
    };

    const out: ApprovalBlocker[] = [];
    for (const a of draft.annotations ?? []) {
        if ((a.severity ?? '').toUpperCase() !== 'ERROR') continue;
        if (a.annotation_type === 'closed_world_violation') continue;
        const scopeId = a.target_id ?? null;
        if (a.annotation_type === 'llm_failure' && scopeId) {
            if (!resolved(scopeId)) out.push({ scopeId, message: V6_BLOCK_FAILED(titleOf(scopeId)) });
            continue;
        }
        out.push({ scopeId, message: a.message || RV_BLOCK_GENERIC });
    }

    const terminalOf = new Map(content.checks.map((c) => [c.plan.check_id, c.plan.priced_terminal_id]));
    const scopeOfTerminal = new Map(content.view_terminals.map(
        (t) => [t.terminal_id, scopeKey(t.question_id, t.sub_question_id)]));
    const openByScope = new Map<string, number>();
    for (const id of undecided) {
        const scopeId = scopeOfTerminal.get(terminalOf.get(id) ?? '');
        if (scopeId) openByScope.set(scopeId, (openByScope.get(scopeId) ?? 0) + 1);
    }
    for (const [scopeId, n] of openByScope) out.push({ scopeId, message: RV_BLOCK_UNDECIDED(n) });
    return out;
}

// ── the view model ─────────────────────────────────────────────────────────

const VERIFIED = new Set(['exact', 'fuzzy']);

export interface V6Option {
    optionId: string;
    label: string;
    /** `str(Decimal)`: credit 0..max, a fault ≤ 0. */
    value: string;
    /** Vivi's own pick (the record's valid `model_option_id`). */
    vivi: boolean;
    /** Her pick. */
    hers: boolean;
    /** What the pricer resolved this check to — false everywhere on an undecided check. */
    effective: boolean;
}

export interface V6Charge {
    status: FaultStatus;
    /** the chosen option's value (≤ 0) */
    amount: string;
    /** what was actually deducted (≤ 0) */
    charged: string;
    /** [AM-G15] the group charge moved here because she pinned that criterion. */
    movedFrom: { terminalId: string; description: string } | null;
}

export interface V6Check {
    checkId: string;
    role: 'credit' | 'fault' | 'note';
    description: string;
    options: V6Option[];
    /** Her option, or null when she has not chosen one. */
    herOptionId: string | null;
    source: ResolutionSource;
    /** Vivi proposed credit on evidence that is not in the answer (AM-G2) — held back. */
    gated: boolean;
    /** [OD-4] no answer came back and she has not decided — the empty amber ring. */
    undecided: boolean;
    comment: string | null;
    /** The words Vivi cited, when they ARE in the answer (exact / fuzzy). */
    quote: string | null;
    /** How `quote` was matched — what the answer pane paints it as. */
    quoteKind: 'exact' | 'fuzzy' | null;
    /** A note check the pricer reports as observed. */
    noteObserved: boolean;
    noteLabel: string | null;
    /** A fault check's line in the terminal's charges. */
    charge: V6Charge | null;
}

export interface V6Criterion {
    terminalId: string;
    /** HER criterion text, verbatim from the envelope. */
    description: string;
    possible: string;
    awarded: string;
    /** What Vivi alone awarded — before any decision of hers. */
    aiAwarded: string;
    chip: Chip;
    /** She set this criterion's grade by hand. */
    pinned: boolean;
    /** Any decision of hers lands here (an option, or the grade by hand). */
    decided: boolean;
    primaryQuote: string | null;
    line: { text: string; source: string } | null;
    /** Her edit is saving; the server's new line has not arrived. */
    linePending: boolean;
    undecidedCount: number;
    checks: V6Check[];
}

export interface V6Scope {
    scopeId: string;
    title: string;
    questionText: string | null;
    answer: ScopeAnswerView;
    possible: string;
    awarded: string;
    counted: boolean;
    gradedBy: string;
    overridden: boolean;
    criteria: V6Criterion[];
    feedback: { text: string; teacherEdited: boolean } | null;
    undecidedCount: number;
}

export interface V6ReviewModel {
    scopes: V6Scope[];
    total: string;
    possible: string;
    anyOverride: boolean;
    summary: { text: string; teacherEdited: boolean } | null;
    blockers: ApprovalBlocker[];
    undecided: string[];
    priced: PricedTest;
}

export interface BuildV6Options {
    /** The latest server response — `content` is Vivi's record and never changes. */
    review: Pick<GradedTestV6Response, 'content' | 'lines'> & {
        priced?: GradedTestV6Response['priced'];
    };
    /** The envelope (`GET /graded_test/{id}` → `draft`): her criterion text, the answers. */
    draft: WireDraft;
    /** Her LIVE working copy — what the grade on screen is priced from. */
    overlay: OverlayV6;
    questions?: readonly QuestionText[];
    /** Criteria whose line is being rewritten by an in-flight save (she edited them). */
    pendingLines?: ReadonlySet<string>;
    /**
     * While a save is pending, a criterion she did NOT touch can still move — a
     * group charge follows her pin elsewhere (AM-G15) — and the server rewrites
     * its line too. Any criterion whose live grade differs from the server's
     * last price (`review.priced`) is therefore also «מתעדכן» until it lands.
     */
    saving?: boolean;
    feedbackOverrides?: Record<string, string>;
    /** Feedback targets whose text is hers (stored or typed this session). */
    feedbackEdited?: ReadonlySet<string>;
}

/** terminal id → her criterion text, from the envelope (criterion or sub-criterion). */
export function criterionDescriptions(draft: WireDraft): Map<string, { description: string; scope: WireScope }> {
    const out = new Map<string, { description: string; scope: WireScope }>();
    for (const scope of draft.scope_outcomes ?? []) {
        for (const criterion of scope.criterion_outcomes ?? []) {
            const subs = criterion.sub_criterion_outcomes;
            if (subs && subs.length) {
                for (const sub of subs) {
                    if (sub.sub_criterion_id) {
                        out.set(sub.sub_criterion_id, { description: sub.description ?? '', scope });
                    }
                }
            } else {
                out.set(criterion.criterion_id, { description: criterion.description ?? '', scope });
            }
        }
    }
    return out;
}

export function buildV6ReviewModel(options: BuildV6Options): V6ReviewModel {
    const {
        review, draft, overlay, questions = [], pendingLines = new Set<string>(),
        saving = false, feedbackOverrides = {}, feedbackEdited = new Set<string>(),
    } = options;
    const serverAward = new Map(
        (review.priced?.terminals ?? []).map((t) => [t.terminal_id, t.awarded]));
    const content = review.content;
    const view = viewOf(content);
    const priced = priceV6(view, pricingOverlayOf(overlay));
    const aiPriced = priceV6(view);
    const undecided = undecidedChecks(content, aiPriced, overlay);
    const undecidedSet = new Set(undecided);

    const records = new Map(content.checks.map((c) => [c.plan.check_id, c]));
    const resolved = new Map(priced.checks.map((r) => [r.check_id, r]));
    const aiResolved = new Map(aiPriced.checks.map((r) => [r.check_id, r]));
    const pricedT = new Map(priced.terminals.map((t) => [t.terminal_id, t]));
    const aiT = new Map(aiPriced.terminals.map((t) => [t.terminal_id, t]));
    const lineOf = new Map(review.lines.map((l) => [l.terminal_id, l]));
    const described = criterionDescriptions(draft);
    const checksOf = new Map<string, CheckRecordV6[]>();
    for (const c of [...content.checks].sort((a, b) => a.plan_index - b.plan_index)) {
        const tid = c.plan.priced_terminal_id;
        checksOf.set(tid, [...(checksOf.get(tid) ?? []), c]);
    }
    const descriptionOf = (tid: string): string => described.get(tid)?.description
        || (checksOf.get(tid) ?? []).find((c) => c.plan.role === 'credit')?.plan.source_span
        || '';

    const buildCheck = (record: CheckRecordV6, terminal: PricedTerminal): V6Check => {
        const plan = record.plan;
        const r = resolved.get(plan.check_id) as ResolvedCheck;
        const ai = aiResolved.get(plan.check_id) as ResolvedCheck;
        const choice = overlay.checks[plan.check_id];
        const herOptionId = choice?.option_id ?? null;
        const isUndecided = undecidedSet.has(plan.check_id);
        const viviId = ai.claimed_option_id ?? null;
        const quote = record.evidence_quote && VERIFIED.has(record.quote_status ?? '')
            ? record.evidence_quote : null;
        const charge = terminal.charges.find((c) => c.check_id === plan.check_id) ?? null;
        const observed = plan.role === 'note'
            && terminal.notes_observed.includes(plan.check_id);
        return {
            checkId: plan.check_id,
            role: plan.role,
            description: plan.description_he,
            options: plan.options.map((o) => ({
                optionId: o.option_id,
                label: o.label_he,
                value: o.value,
                vivi: o.option_id === viviId,
                hers: o.option_id === herOptionId,
                effective: !isUndecided && o.option_id === r.option_id,
            })),
            herOptionId,
            source: r.source,
            gated: r.source === 'gated',
            undecided: isUndecided,
            comment: choice?.comment ?? null,
            quote,
            quoteKind: quote ? (record.quote_status === 'fuzzy' ? 'fuzzy' : 'exact') : null,
            noteObserved: observed,
            noteLabel: observed
                ? plan.options.find((o) => o.option_id === r.option_id)?.label_he ?? null
                : null,
            charge: charge && plan.role === 'fault' ? {
                status: charge.status,
                amount: charge.amount,
                charged: charge.charged,
                movedFrom: charge.moved_by_pin && charge.moved_from_terminal_id
                    ? {
                        terminalId: charge.moved_from_terminal_id,
                        description: descriptionOf(charge.moved_from_terminal_id),
                    }
                    : null,
            } : null,
        };
    };

    const buildCriterion = (tid: string, possible: string): V6Criterion => {
        const t = pricedT.get(tid) as PricedTerminal;
        const checks = (checksOf.get(tid) ?? []).map((c) => buildCheck(c, t));
        const primary = t.primary_check_id ? records.get(t.primary_check_id) : undefined;
        const line = lineOf.get(tid);
        const pinned = overlay.terminal_points[tid] !== undefined;
        return {
            terminalId: tid,
            description: descriptionOf(tid),
            possible,
            awarded: t.awarded,
            aiAwarded: aiT.get(tid)?.awarded ?? t.awarded,
            chip: t.chip,
            pinned,
            decided: pinned || checks.some((c) => c.herOptionId !== null),
            primaryQuote: primary && primary.evidence_quote
                && VERIFIED.has(primary.quote_status ?? '') ? primary.evidence_quote : null,
            line: line ? { text: line.text_he, source: line.source } : null,
            linePending: pendingLines.has(tid) || (saving && serverAward.has(tid)
                && cmp(dec(serverAward.get(tid) as string), dec(t.awarded)) !== 0),
            undecidedCount: checks.filter((c) => c.undecided).length,
            checks,
        };
    };

    // Scopes in the envelope's order, criteria in the envelope's order — her
    // rubric's order. A terminal the envelope does not carry is never hidden:
    // it joins its question's section (or one of its own) at the end.
    const possibleOf = new Map(content.view_terminals.map((t) => [t.terminal_id, t.points_possible]));
    const placed = new Set<string>();
    const sections: { scopeId: string; wire: WireScope | null; questionId: string;
                      subQuestionId: string | null; terminals: string[] }[] = [];
    for (const scope of draft.scope_outcomes ?? []) {
        const terminals: string[] = [];
        for (const criterion of scope.criterion_outcomes ?? []) {
            const subs = criterion.sub_criterion_outcomes;
            const ids = subs && subs.length
                ? subs.map((s) => s.sub_criterion_id ?? '') : [criterion.criterion_id];
            for (const id of ids) {
                if (possibleOf.has(id) && !placed.has(id)) { terminals.push(id); placed.add(id); }
            }
        }
        sections.push({ scopeId: scopeIdOf(scope), wire: scope, questionId: scope.question_id,
                        subQuestionId: scope.sub_question_id ?? null, terminals });
    }
    for (const t of content.view_terminals) {
        if (placed.has(t.terminal_id)) continue;
        const scopeId = scopeKey(t.question_id, t.sub_question_id);
        let section = sections.find((s) => s.scopeId === scopeId);
        if (!section) {
            section = { scopeId, wire: null, questionId: t.question_id,
                        subQuestionId: t.sub_question_id ?? null, terminals: [] };
            sections.push(section);
        }
        section.terminals.push(t.terminal_id);
        placed.add(t.terminal_id);
    }

    const scopes: V6Scope[] = sections.map((section) => {
        const criteria = section.terminals.map((tid) => buildCriterion(tid, possibleOf.get(tid) as string));
        const pricedScope = priced.scopes.find((s) => s.question_id === section.questionId
            && (s.sub_question_id ?? null) === section.subQuestionId);
        const wire: WireScope = section.wire ?? {
            question_id: section.questionId, sub_question_id: section.subQuestionId,
            points_possible: pricedScope?.points_possible ?? '0', points_awarded: '0',
            graded_by: content.scopes.find((s) => s.question_id === section.questionId
                && (s.sub_question_id ?? null) === section.subQuestionId)?.graded_by ?? 'llm',
        };
        const feedbackText = feedbackOverrides[section.scopeId]
            ?? draft.feedback?.scopes?.[section.scopeId]?.text ?? '';
        return {
            scopeId: section.scopeId,
            title: scopeTitle(wire),
            questionText: questionTextForScope(wire, questions),
            answer: section.wire ? answerViewOf(section.wire) : { kind: 'unavailable' },
            possible: pricedScope?.points_possible ?? wire.points_possible,
            awarded: pricedScope?.awarded ?? '0',
            counted: pricedScope?.counted ?? true,
            gradedBy: wire.graded_by,
            overridden: criteria.some((c) => c.decided),
            criteria,
            feedback: feedbackText
                ? { text: feedbackText, teacherEdited: feedbackEdited.has(section.scopeId) }
                : null,
            undecidedCount: criteria.reduce((n, c) => n + c.undecidedCount, 0),
        };
    });

    const summaryText = feedbackOverrides.summary ?? draft.feedback?.summary?.text ?? '';
    return {
        scopes,
        total: priced.total_score,
        possible: priced.total_possible,
        anyOverride: Object.keys(overlay.terminal_points).length > 0
            || Object.values(overlay.checks).some((c) => c.option_id !== null),
        summary: summaryText
            ? { text: summaryText, teacherEdited: feedbackEdited.has('summary') }
            : null,
        blockers: blockersV6(draft, content, overlay, undecided),
        undecided,
        priced,
    };
}
