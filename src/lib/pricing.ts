/**
 * THE client pricing mirror (PR spec §3, phase F0) — a faithful port of
 * `backend/app/services/pricing.py`.
 *
 * Points are DERIVED from verdicts, in one direction, everywhere. The teacher
 * never types a number: she decides a verdict on a check and the points follow.
 * This module is what lets the review surface re-price instantly under her
 * hand; the server prices the same way on `PATCH /draft` and `/approve` and
 * compares. If the two ever disagree, both sides fail the shared vectors
 * together — that is the seam working, and it is why this file exists instead
 * of a second, convenient arithmetic (CLAUDE.md §5: the selection-scoring
 * incident happened because one number had two derivations).
 *
 * TWO RULES IN HERE ARE POLICY, NOT ARITHMETIC — both carried over verbatim:
 *
 *   * Evidence gating applies to the MODEL, not to the teacher. A `met` whose
 *     cited span is not in the answer earns nothing — the invented-credit
 *     guard. But a check SHE overrode is priced on her verdict alone: she has
 *     the paper in front of her, and refusing her credit because the model's
 *     citation failed would make her argue with the machine about a fact she
 *     can see. The teacher is the authority (CLAUDE.md §2).
 *   * Charge groups dedup across the whole SCOPE, not per terminal: the same
 *     defect is charged once, by the first firing member in document order, at
 *     the maximum amount fired in the group. Price a terminal alone and a
 *     defect the grader charged once gets charged twice on review.
 *
 * ── THE NUMERIC POLICY (OD-F8, ruled and shipped 2026-08-31) ──────────────
 * `numeric_policy` now rides `GradedTestDraftResponse` and
 * `GradedTestApprovedResponse`, and ALL THREE fields travel — `precision`
 * alone would still let the client round an exact .5 differently from the
 * server, and on a 0.25 grid that is exactly where the boundaries fall.
 *
 * It is a REQUIRED argument here and this module will not default it. The wire
 * field is `Optional` and is omitted rather than defaulted when the contract
 * will not parse; a caller holding `null` therefore cannot price, which is the
 * correct outcome. Pricing is a CONSUMING path, not a display one (§3.5a): it
 * feeds the number she reviews and approves, so it refuses loudly instead of
 * degrading to a plausible grid.
 *
 * `rounding_mode` is honoured by REFUSAL. See the rounding-mode block in
 * pricing.test.ts: no backend code reads that field — `services/pricing.py:48`
 * and `agents/grader/pricer.py:81` both hardcode ROUND_HALF_UP — so a client
 * that obeyed a `half_even` policy would diverge from the server rather than
 * converge on it. Until the server reads its own policy, this mirror accepts
 * `half_up` and throws on anything else. Surfaced, not silently accommodated.
 *
 * ⚠ `numeric_policy` comes from the rubric's CURRENT contract. When
 * `rubric_contract_stale` is true it may differ from the policy that priced
 * the draft — but a stale contract means the test needs RE-GRADING, not
 * re-pricing, and that flag is already on the wire for the UI to surface.
 *
 * @see backend/app/services/pricing.py — the source of truth
 * @see pricing.test.ts — `pricer-parity` against the published §1.7 vectors
 */

import {
    add,
    cmp,
    dec,
    divideContext,
    divideExact,
    mul,
    pyMax,
    pyMin,
    sub,
    toIntegralValueHalfUp,
    toString as decToString,
    type Dec,
} from './decimal';

export type Verdict = 'met' | 'partially_met' | 'not_met';
export type CheckKind = 'required' | 'tariff' | 'note_only' | 'counted';
export type QuoteStatus = 'exact' | 'fuzzy' | 'not_found';

/**
 * The rubric's numeric policy, as it arrives on the graded-test responses
 * (`components['schemas']['NumericPolicy']`). Decimals are strings on the
 * wire so nobody does binary-float arithmetic on a grade.
 */
export interface NumericPolicy {
    /** Smallest point increment, e.g. "0.25". */
    precision?: string;
    /** Python decimal rounding mode. Only "half_up" is honoured — see below. */
    rounding_mode: string;
    /** Point-sum validation tolerance. Not used by pricing; carried whole so
     *  callers pass the policy rather than picking fields out of it. */
    sum_tolerance?: string;
}

/** The only mode both backend pricing sites actually implement. */
const SUPPORTED_ROUNDING_MODE = 'half_up';

/**
 * The pricing-relevant projection of the wire `Check`
 * (`components['schemas']['Check']` in the generated api-types).
 *
 * Deliberately structural rather than an alias of the generated type: this is
 * the arithmetic's INPUT contract, it must stay callable from a fixture vector
 * as well as from a live draft, and every field it names is one the pricer
 * actually reads. `text`, `basis_he` and `confidence` are display/eval data
 * and have no business in here.
 */
export interface PricingCheck {
    check_id: string;
    // ALPHA-GAP A-1 (D-3): no 'level_select' kind — a band ladder is ONE 'required' check at the top
    // band (C8-lite). Alpha adds the kind to CheckKind and a selected-band field beside it,
    // and both price() arms below gain a branch. Mirrors backend pricer.py.
    kind: CheckKind;
    /** Required checks: the credit at stake. Serializes as `string | null`. */
    points: string | null;
    /** Tariff checks: the named deduction. */
    tariff?: string | null;
    /** Defaults to the plan's 0.5 when the wire omits it. */
    partial_fraction?: string | null;
    verdict: Verdict;
    quote_status?: QuoteStatus | null;
    /** Same-defect-once, scope-wide. */
    charge_group?: string | null;
    /** Counted checks (PLAN COMPILER v2, C3): the uniform units the terminal
     *  prices, and the count the verifier reported. A partially_met with no
     *  count earns NOTHING — an invented count is a number the model never
     *  emitted (`pricing.py::counted_units`). */
    unit_count?: number | null;
    units_correct?: number | null;
}

/** One terminal (leaf criterion / sub-criterion) and its checks. */
export interface ScopeTerminal {
    terminal_id: string;
    points_possible: string;
    checks: readonly PricingCheck[];
}

export interface TerminalPrice {
    /** Clamped to [0, possible] and snapped to the grid — what she sees. */
    awarded: string;
    /** earned − deducted, before clamp/snap. A `raw` that differs from
     *  `awarded` is exactly the backend's BOUNDS_CLAMPED event. */
    raw: string;
}

/** The teacher's decision on one check (`TeacherOverride`, PR-G5). */
export interface CheckOverride {
    check_id: string;
    verdict: Verdict;
}

const VERIFIED: readonly (QuoteStatus | null | undefined)[] = ['exact', 'fuzzy'];
const ZERO = dec('0');
const DEFAULT_PARTIAL_FRACTION = '0.5';

/**
 * A null `points` earns nothing.
 *
 * `Check.points` is required and non-null in Python; the generated TS types it
 * as `string | null` because the Decimal field serializer is annotated
 * Optional. Treating the artifact as zero is the conservative direction: it can
 * refuse credit that was owed (visible, and the server's own number disagrees
 * loudly on save) but it can never invent credit that was not.
 */
function points(check: PricingCheck): Dec {
    return check.points == null ? ZERO : dec(check.points);
}

function partialFraction(check: PricingCheck): Dec {
    return dec(check.partial_fraction ?? DEFAULT_PARTIAL_FRACTION);
}

function tariffAmount(check: PricingCheck): Dec {
    return check.tariff == null ? ZERO : dec(check.tariff);
}

/**
 * `pricing.py::counted_units` — met ⇒ every unit, not_met ⇒ none,
 * partially_met ⇒ the reported count clamped into [0, unit_count]; a partial
 * verdict with no count is null (no credit; the backend flags COUNT_MISSING).
 */
function countedUnits(check: PricingCheck): number | null {
    const n = check.unit_count ?? 0;
    if (check.verdict === 'met') return n;
    if (check.verdict === 'not_met') return 0;
    if (check.units_correct == null) return null;
    return Math.max(0, Math.min(n, Math.trunc(check.units_correct)));
}

/** `points × units / unit_count`, left to right, under Python's context —
 *  snapped with the TERMINAL, never here (12 × 15/17 → 10.5 on a 0.25 grid). */
function countedCredit(check: PricingCheck): Dec | null {
    const units = countedUnits(check);
    if (units === null) return null;
    const n = check.unit_count || 1;
    return divideContext(mul(points(check), dec(units)), dec(n));
}

/** Tariffs are binary: `partially_met` is coerced to fired. */
function fired(check: PricingCheck): boolean {
    return check.verdict === 'not_met' || check.verdict === 'partially_met';
}

/** Whether a `required` check may earn its points at all. */
function credited(check: PricingCheck, overridden: boolean): boolean {
    if (check.verdict !== 'met' && check.verdict !== 'partially_met') return false;
    if (overridden) return true;                 // the teacher decided; see module doc
    return VERIFIED.includes(check.quote_status ?? null);
}

function groupOf(check: PricingCheck): string {
    return check.charge_group || `__solo__${check.check_id}`;
}

/**
 * Validate the policy and hand back the grid.
 *
 * Both refusals are deliberate and neither has a safe default:
 *   * a missing `precision` would mean inventing a grid, and every rounded
 *     award moves with it;
 *   * an unsupported `rounding_mode` would mean rounding differently from the
 *     server, which is the divergence the field was added to close.
 */
function gridOf(policy: NumericPolicy): string {
    if (policy?.precision == null || policy.precision === '') {
        throw new Error(
            'pricing: numeric_policy.precision is missing. The wire omits the '
            + 'policy rather than defaulting it when the rubric contract will '
            + 'not parse — such a test cannot be re-priced client-side, and a '
            + 'guessed grid would move every rounded award.',
        );
    }
    if (policy.rounding_mode !== SUPPORTED_ROUNDING_MODE) {
        throw new Error(
            `pricing: unsupported numeric_policy.rounding_mode `
            + `${JSON.stringify(policy.rounding_mode)}. This mirror implements `
            + `"${SUPPORTED_ROUNDING_MODE}" only, because that is what the `
            + 'server actually does — services/pricing.py and '
            + 'agents/grader/pricer.py both hardcode ROUND_HALF_UP and read '
            + 'this field nowhere. Honouring another mode here would make the '
            + 'client disagree with the server, not agree with the contract.',
        );
    }
    return policy.precision;
}

/** `clamp(value, lo, hi)` then grid-snap ROUND_HALF_UP — the backend `_snap`. */
function snap(value: Dec, lo: Dec, hi: Dec, precision: Dec): Dec {
    const clamped = pyMax(lo, pyMin(value, hi));
    return mul(toIntegralValueHalfUp(divideExact(clamped, precision)), precision);
}

/**
 * Price every terminal in ONE scope from its checks. Pure.
 *
 * Scope-wide by signature, not by convenience: charge-once dedup cannot be
 * computed a terminal at a time.
 */
export function priceScopeChecksDetailed(
    terminals: readonly ScopeTerminal[],
    policy: NumericPolicy,
    overriddenCheckIds?: ReadonlySet<string>,
): Record<string, TerminalPrice> {
    const overridden = overriddenCheckIds ?? new Set<string>();
    const grid = dec(gridOf(policy));

    // charge-once pre-pass, scope-wide: per group, the first firing check in
    // document order pays the MAX amount fired anywhere in that group.
    const firstFiring = new Map<string, string>();
    const groupAmount = new Map<string, Dec>();
    for (const terminal of terminals) {
        for (const check of terminal.checks) {
            if (check.kind !== 'tariff' || !fired(check)) continue;
            const group = groupOf(check);
            if (!firstFiring.has(group)) firstFiring.set(group, check.check_id);
            const amount = tariffAmount(check);
            const current = groupAmount.get(group);
            if (current === undefined || cmp(amount, current) > 0) {
                groupAmount.set(group, amount);
            }
        }
    }

    const out: Record<string, TerminalPrice> = {};
    for (const terminal of terminals) {
        let earned = ZERO;
        let deducted = ZERO;
        for (const check of terminal.checks) {
            if (check.kind === 'required') {
                if (!credited(check, overridden.has(check.check_id))) continue;
                earned = check.verdict === 'met'
                    ? add(earned, points(check))
                    : add(earned, mul(points(check), partialFraction(check)));
            } else if (check.kind === 'counted') {
                // evidence-gated like required; the count is the partial credit
                if (!credited(check, overridden.has(check.check_id))) continue;
                const credit = countedCredit(check);
                if (credit === null) continue;
                earned = add(earned, credit);
            } else if (check.kind === 'tariff') {
                if (!fired(check)) continue;
                const group = groupOf(check);
                if (firstFiring.get(group) === check.check_id) {
                    deducted = add(deducted, groupAmount.get(group) ?? ZERO);
                }
            }
            // note_only never moves points — the rubric's «לציין, לא להוריד»
        }
        const raw = sub(earned, deducted);
        out[terminal.terminal_id] = {
            awarded: decToString(snap(raw, ZERO, dec(terminal.points_possible), grid)),
            raw: decToString(raw),
        };
    }
    return out;
}

/**
 * What each individual check contributed to its terminal — the number the
 * checklist shows on its row.
 *
 * It cannot be derived by pricing a check in isolation. Two rules make the
 * contribution a property of the SCOPE, not of the check:
 *
 *   * a `tariff` check SUBTRACTS, so its contribution is negative; pricing it
 *     alone clamps to [0, 0] and renders `0` whether or not the defect fired,
 *     which hides the deduction on the row that exists to show it;
 *   * charge-once means a fired tariff may contribute NOTHING because an
 *     earlier member of its group already paid.
 *
 * Contributions are the raw, pre-clamp truth: they sum to the terminal's `raw`,
 * not necessarily to its `awarded` (a clamp at 0 is visible as the difference).
 */
export function priceScopeCheckContributions(
    terminals: readonly ScopeTerminal[],
    policy: NumericPolicy,
    overriddenCheckIds?: ReadonlySet<string>,
): Record<string, string> {
    const overridden = overriddenCheckIds ?? new Set<string>();
    gridOf(policy);            // validate the policy on this path too

    const firstFiring = new Map<string, string>();
    const groupAmount = new Map<string, Dec>();
    for (const terminal of terminals) {
        for (const check of terminal.checks) {
            if (check.kind !== 'tariff' || !fired(check)) continue;
            const group = groupOf(check);
            if (!firstFiring.has(group)) firstFiring.set(group, check.check_id);
            const amount = tariffAmount(check);
            const current = groupAmount.get(group);
            if (current === undefined || cmp(amount, current) > 0) {
                groupAmount.set(group, amount);
            }
        }
    }

    const out: Record<string, string> = {};
    for (const terminal of terminals) {
        for (const check of terminal.checks) {
            let value = ZERO;
            if (check.kind === 'required') {
                if (credited(check, overridden.has(check.check_id))) {
                    value = check.verdict === 'met'
                        ? points(check)
                        : mul(points(check), partialFraction(check));
                }
            } else if (check.kind === 'counted') {
                if (credited(check, overridden.has(check.check_id))) {
                    value = countedCredit(check) ?? ZERO;
                }
            } else if (check.kind === 'tariff' && fired(check)) {
                const group = groupOf(check);
                if (firstFiring.get(group) === check.check_id) {
                    value = sub(ZERO, groupAmount.get(group) ?? ZERO);
                }
            }
            out[check.check_id] = decToString(value);
        }
    }
    return out;
}

/** The awards only — the common case. */
export function priceScopeChecks(
    terminals: readonly ScopeTerminal[],
    policy: NumericPolicy,
    overriddenCheckIds?: ReadonlySet<string>,
): Record<string, string> {
    const detailed = priceScopeChecksDetailed(terminals, policy, overriddenCheckIds);
    const out: Record<string, string> = {};
    for (const [id, price] of Object.entries(detailed)) out[id] = price.awarded;
    return out;
}

/**
 * Lay the teacher's decisions over a terminal's checks.
 *
 * Returns `(effective checks, the ids she decided)` — the id set is what the
 * pricer needs to know NOT to evidence-gate. Sparse by construction: a check
 * with no override passes through untouched, so the AI's verdict remains the
 * record for everything she never looked at. Never mutates the draft.
 */
export function applyOverlay(
    checks: readonly PricingCheck[],
    overrides: readonly CheckOverride[] | undefined | null,
): { effective: PricingCheck[]; touched: Set<string> } {
    const byId = new Map((overrides ?? []).map((o) => [o.check_id, o]));
    const effective: PricingCheck[] = [];
    const touched = new Set<string>();
    for (const check of checks) {
        const override = byId.get(check.check_id);
        if (override === undefined) {
            effective.push(check);
            continue;
        }
        touched.add(check.check_id);
        effective.push({ ...check, verdict: override.verdict });
    }
    return { effective, touched };
}
