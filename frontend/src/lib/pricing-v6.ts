/**
 * The grader-v6 pricer, client side — a faithful port of
 * `backend/app/services/pricing_v6.py` (PR_grader_v6_options.md §4).
 *
 *     priceV6(view: DraftV6View, overlay?: PricingOverlay | null) -> PricedTest
 *
 * PRC-7: the TypeScript mirror computes the same result from the same JSON.
 * Everything the pricer needs is in the view, so there is nothing to look up:
 * the server prices a draft, this module re-prices it under her hand, and the
 * two must agree to the byte — `pricing_v6_vectors.json` is the seam, read in
 * place by `pricing-v6.test.ts`. If they ever disagree, both sides fail the
 * shared vectors together (CLAUDE.md §5: one number, one derivation — the
 * selection-scoring incident is what two derivations cost).
 *
 * PURE (PRC-8): no I/O, clock, logging or randomness. A logic-bug signal (an
 * upper clamp V13 should make impossible) is RETURNED in `PricedTest.flags`
 * for the caller to log, rather than logged here.
 *
 * Points are EXACT decimals (`./decimal`), never JS floats: the wire carries
 * `str(Decimal)` strings, and `"0.50"`, `"0.5"` and `"0"` there are different
 * exponents of the same arithmetic. Every Python operator below maps to the
 * decimal helper that CPython probes pinned (`+` → `add`, `min`/`max` →
 * `pyMin`/`pyMax` — the FIRST argument wins a tie, `<`/`==` → `cmp`).
 *
 * The algorithm, in order (§4.2, as amended at STOP-1 and by AM-G13):
 *   1 Resolve   her typed amount (credit only, AM-G3) › her option › the model's
 *               option — evidence-gated (AM-G2): a MODEL selection of a
 *               non-default option on an `evidence_required` check whose quote is
 *               not exact/fuzzy resolves to the default; hers never is ›
 *               the default (zero / `none`) with UNVERIFIED_CHECK (PRC-1).
 *   2 Activity  a fault that `requires` T is active iff T resolved > 0 (PRC-2);
 *               an active fault with a fault option is a CANDIDATE charge.
 *   3 BehaviorCap  [AM-G13, PRC-3] the charges of all charged faults requiring
 *               one credit check T sum to ≥ −value(T); an excess is removed
 *               LATEST plan order first, and a reduced charge is `capped`.
 *   4 ChargedOnce  [AM-G13, PRC-4] every charge group with a candidate charges
 *               EXACTLY one member. The members are chosen JOINTLY across the
 *               scope's groups: the assignment giving the LOWEST scope total, the
 *               total taken with steps 3, 5 and her terminal overrides (6)
 *               applied (census Q-23). Assignments are enumerated
 *               lexicographically — groups in plan order (a group's place is its
 *               first member's), members in plan order — and the FIRST that
 *               attains the minimum is kept. The rest are `superseded`.
 *   5 Terminal  raw = credit + charges; below 0, charges are reduced in REVERSE
 *               plan order until the terminal reaches 0 (`floored`,
 *               BOUNDS_CLAMPED); awarded = clamp(raw, 0, P) (PRC-5).
 *   6 Override  her terminal award replaces it; charge statuses stay for display.
 *   7 Notes     never priced (Q-10); observed ones are reported.
 *   8 Totals    `score_with_selection`, unchanged (ported below as
 *               `scoreWithSelection`, from `services/selection_scoring.py`).
 *
 * Statuses: inactive · no_fault · applied · capped · superseded · floored.
 *
 * [AM-G1] There are no reduction terminals and no home statuses.
 *
 * @see backend/app/services/pricing_v6.py — the source of truth
 * @see backend/app/services/selection_scoring.py — step 8
 * @see pricing-v6.test.ts — every vector of `pricing_v6_vectors.json`
 */

import {
    add,
    cmp,
    dec,
    pyMax,
    pyMin,
    sub,
    toString as decToString,
    type Dec,
} from './decimal';

const ZERO: Dec = dec('0');
const _VERIFIED: ReadonlyArray<string> = ['exact', 'fuzzy'];

/** `FlagReason` values (`backend/app/schemas/ontology_types.py`). */
export const UNVERIFIED_CHECK = 'unverified_check';
export const EVIDENCE_UNVERIFIED = 'evidence_unverified';
export const BOUNDS_CLAMPED = 'bounds_clamped';
export const UPPER_CLAMP_LOGIC_BUG = 'upper_clamp_logic_bug';

/**
 * CPython's `-x` for a Decimal: the exponent is kept, and a zero negates to
 * +0 (`__neg__` takes `copy_abs` of a zero outside ROUND_FLOOR). `Dec` holds a
 * bigint coefficient, which has no −0, so both rules fall out of `-c`.
 */
function neg(a: Dec): Dec {
    return { c: -a.c, e: a.e };
}

/** Python's `sum(xs, ZERO)`: a left fold that STARTS at `Decimal("0")` —
 *  the start's exponent 0 takes part in the result's exponent. */
function dsum(xs: Iterable<Dec>): Dec {
    let total = ZERO;
    for (const x of xs) total = add(total, x);
    return total;
}

function own<V>(record: Record<string, V> | null | undefined, key: string): V | undefined {
    if (record == null) return undefined;
    return Object.prototype.hasOwnProperty.call(record, key) ? record[key] : undefined;
}

// ═══════════════════════════════════════════════════════════════════════════
// plan/v6 types — the subset of `agents/grader/plan_schemas.py` pricing reads
// ═══════════════════════════════════════════════════════════════════════════

export type CheckRole = 'credit' | 'fault' | 'note';
export type CheckShape = 'binary' | 'ladder' | 'levels' | 'count' | 'fault' | 'note';
export type CheckOrigin = 'compiler' | 'planner' | 'fallback' | 'legacy';
export type CreditElement = 'binary' | 'non_binary';
export type QuoteStatus = 'exact' | 'fuzzy' | 'not_found';

/** One possible answer to a check. `value` is a `str(Decimal)` on the grid:
 *  credit 0..max, fault ≤ 0, note 0 (V12, V17). */
export interface CheckOption {
    option_id: string;
    label_he?: string;
    value: string;
    marker_id?: string | null;
}

/** One check. Display order of `options`: credit highest-first; fault and
 *  note `none` first. Text fields are display data the pricer never reads,
 *  hence optional here. */
export interface PlanCheckV6 {
    check_id: string;
    role: CheckRole;
    shape?: CheckShape;
    description_he?: string;
    source_span?: string;
    options: CheckOption[];
    /** fault only: a credit check on the same priced terminal */
    requires?: string | null;
    /** fault only */
    charge_group?: string | null;
    priced_terminal_id: string;
    equivalence_note_he?: string | null;
    /** [AM-G2] defaults to true, as on the Python model. */
    evidence_required?: boolean;
    origin?: CheckOrigin;
    element?: CreditElement | null;
}

/** `PlanCheckV6.option` — the option with that id, or null. */
function planOption(plan: PlanCheckV6, optionId: string | null | undefined): CheckOption | null {
    for (const o of plan.options) {
        if (o.option_id === optionId) return o;
    }
    return null;
}

/** `PlanCheckV6.default_option` — what a check resolves to with no valid
 *  selection (PRC-1): the zero option for credit (the LAST option in display
 *  order — V12), `none` for fault and note (the FIRST). */
function defaultOption(plan: PlanCheckV6): CheckOption {
    return plan.role === 'credit' ? plan.options[plan.options.length - 1] : plan.options[0];
}

// ═══════════════════════════════════════════════════════════════════════════
// inputs — the view of one draft (§9.1) and of her overlay (§9.2)
// ═══════════════════════════════════════════════════════════════════════════

export interface ViewTerminal {
    terminal_id: string;
    question_id: string;
    sub_question_id?: string | null;
    points_possible: string;
}

/** One plan check, copied into the draft, with the model's selection. */
export interface ViewCheck {
    plan: PlanCheckV6;
    /** position in the plan: THE order */
    plan_index: number;
    model_option_id?: string | null;
    quote_status?: QuoteStatus | null;
}

export interface SelectionGroupView {
    of_question_ids: string[];
    choose_k: number;
}

/** What `score_with_selection` reads from the contract: the ACHIEVABLE
 *  total, the question order (its tie-break), and the groups. */
export interface SelectionView {
    total_points: string;
    question_order: string[];
    groups?: SelectionGroupView[];
}

export interface DraftV6View {
    /** Carried for the caller; the pricer itself never reads it (as in Python). */
    precision: string;
    terminals: ViewTerminal[];
    checks: ViewCheck[];
    selection: SelectionView;
}

/** Her decision on one check (AM-G3). `amount` is valid on credit checks
 *  only — CW-3 refuses it elsewhere; the pricer ignores it elsewhere. */
export interface CheckDecision {
    option_id?: string | null;
    amount?: string | null;
    comment?: string | null;
    evidence_disputed?: boolean;
}

export interface PricingOverlay {
    checks?: Record<string, CheckDecision>;
    terminal_points?: Record<string, string>;
}

// ═══════════════════════════════════════════════════════════════════════════
// outputs (§4.3) — decimals as `str(Decimal)`, exactly as `model_dump_json`
// ═══════════════════════════════════════════════════════════════════════════

export type ResolutionSource = 'amount' | 'overlay' | 'model' | 'gated' | 'default';
export type FaultStatus = 'inactive' | 'no_fault' | 'applied' | 'capped' | 'superseded' | 'floored';
export type Chip = 'full' | 'partial' | 'zero';

export interface ResolvedCheck {
    check_id: string;
    /** null only for a typed amount */
    option_id: string | null;
    value: string;
    source: ResolutionSource;
    /** no valid selection at all */
    missing: boolean;
    /** the model's own (valid) pick */
    claimed_option_id: string | null;
}

export interface PricedCharge {
    check_id: string;
    option_id: string;
    /** the resolved option's value (≤ 0) */
    amount: string;
    /** what was actually deducted (≤ 0) */
    charged: string;
    status: FaultStatus;
    /** [AM-G15] the group charge landed HERE because she set a terminal's grade
     *  by hand: with no terminal pinned, the scope's enumeration charges another
     *  member. `moved_from_terminal_id` is that member's terminal. */
    moved_by_pin: boolean;
    moved_from_terminal_id: string | null;
}

export interface PricedTerminal {
    terminal_id: string;
    awarded: string;
    credit_points: string;
    chip: Chip;
    primary_check_id: string | null;
    charges: PricedCharge[];
    notes_observed: string[];
    flags: string[];
    overridden: boolean;
    /** [AM-G3] an amount on any of its checks */
    typed: boolean;
}

export interface PricedScope {
    question_id: string;
    sub_question_id: string | null;
    points_possible: string;
    awarded: string;
    counted: boolean;
}

export interface PricedTest {
    terminals: PricedTerminal[];
    checks: ResolvedCheck[];
    scopes: PricedScope[];
    total_score: string;
    total_possible: string;
    flags: string[];
}

// ═══════════════════════════════════════════════════════════════════════════
// the algorithm
// ═══════════════════════════════════════════════════════════════════════════

/** `ResolvedCheck` with its value still a Dec (the arithmetic's own form). */
interface Resolved {
    check_id: string;
    option_id: string | null;
    value: Dec;
    source: ResolutionSource;
    missing: boolean;
    claimed_option_id: string | null;
}

/** Step 1 — PRC-1 as amended (AM-G2, AM-G3). */
function _resolve(vc: ViewCheck, decision: CheckDecision | undefined): Resolved {
    const plan = vc.plan;
    const deflt = defaultOption(plan);
    const claimed = planOption(plan, vc.model_option_id);
    const claimedId = claimed !== null ? claimed.option_id : null;

    if (decision !== undefined && decision !== null) {
        if (plan.role === 'credit' && decision.amount != null) {
            return { check_id: plan.check_id, option_id: null, value: dec(decision.amount),
                     source: 'amount', missing: false, claimed_option_id: claimedId };
        }
        const mine = planOption(plan, decision.option_id);
        if (mine !== null) {
            return { check_id: plan.check_id, option_id: mine.option_id,
                     value: dec(mine.value), source: 'overlay', missing: false,
                     claimed_option_id: claimedId };
        }
    }

    if (claimed === null) {
        return { check_id: plan.check_id, option_id: deflt.option_id,
                 value: dec(deflt.value), source: 'default', missing: true,
                 claimed_option_id: null };
    }
    const evidenceRequired = plan.evidence_required ?? true;
    if (evidenceRequired && claimed.option_id !== deflt.option_id
            && !_VERIFIED.includes(vc.quote_status as string)) {
        return { check_id: plan.check_id, option_id: deflt.option_id,
                 value: dec(deflt.value), source: 'gated', missing: false,
                 claimed_option_id: claimedId };
    }
    return { check_id: plan.check_id, option_id: claimed.option_id,
             value: dec(claimed.value), source: 'model', missing: false,
             claimed_option_id: claimedId };
}

function _chip(awarded: Dec, possible: Dec): Chip {
    if (cmp(awarded, possible) === 0) return 'full';
    return cmp(awarded, ZERO) === 0 ? 'zero' : 'partial';
}

/** One terminal under one choice of charged faults (steps 3, 5, 6). */
interface _Settled {
    charged: Map<string, Dec>;
    status: Map<string, FaultStatus>;
    credit: Dec;
    final: Dec;
    floored: boolean;
    upper_bug: boolean;
    pin_clamped: boolean;
}

/** `sorted(ids, key=lambda x: order[x], reverse=True)` — later plan order first. */
function byOrderDesc(ids: Iterable<string>, order: Map<string, number>): string[] {
    return [...ids].sort((a, b) => (order.get(b) as number) - (order.get(a) as number));
}

function _settle(t: ViewTerminal, tchecks: ViewCheck[], chosen: Set<string>,
                 candidate: Map<string, Dec>, resolved: Map<string, Resolved>,
                 order: Map<string, number>, pin: Dec | undefined): _Settled {
    const charged = new Map<string, Dec>();
    for (const c of tchecks) {
        if (chosen.has(c.plan.check_id)) {
            charged.set(c.plan.check_id, candidate.get(c.plan.check_id) as Dec);
        }
    }
    const status = new Map<string, FaultStatus>();
    for (const cid of charged.keys()) status.set(cid, 'applied');

    // 3 — BehaviorCap: a behavior's faults together never cost more than it earned
    const byBehavior = new Map<string, string[]>();
    for (const c of tchecks) {
        const requires = c.plan.requires;
        if (charged.has(c.plan.check_id) && requires != null) {
            if (!byBehavior.has(requires)) byBehavior.set(requires, []);
            (byBehavior.get(requires) as string[]).push(c.plan.check_id);
        }
    }
    for (const [behavior, members] of byBehavior) {
        let room = add((resolved.get(behavior) as Resolved).value,
                       dsum(members.map((m) => charged.get(m) as Dec)));
        for (const m of byOrderDesc(members, order)) {
            if (cmp(room, ZERO) >= 0) break;
            const relief = pyMin(neg(room), neg(charged.get(m) as Dec));
            charged.set(m, add(charged.get(m) as Dec, relief));
            room = add(room, relief);
            status.set(m, 'capped');
        }
    }

    // 5 — the terminal floor, reverse plan order
    const credit = dsum(tchecks.filter((c) => c.plan.role === 'credit')
        .map((c) => (resolved.get(c.plan.check_id) as Resolved).value));
    let raw = add(credit, dsum(charged.values()));
    const floored = cmp(raw, ZERO) < 0;
    if (floored) {
        let deficit = neg(raw);
        for (const cid of byOrderDesc(charged.keys(), order)) {
            if (cmp(deficit, ZERO) <= 0) break;
            const relief = pyMin(deficit, neg(charged.get(cid) as Dec));
            charged.set(cid, add(charged.get(cid) as Dec, relief));
            deficit = sub(deficit, relief);
            status.set(cid, 'floored');
        }
        raw = add(credit, dsum(charged.values()));
    }
    const possible = dec(t.points_possible);
    const upperBug = cmp(raw, possible) > 0;
    if (upperBug) raw = possible;

    // 6 — her terminal override
    let final = raw;
    let pinClamped = false;
    if (pin !== undefined) {
        final = pyMin(pyMax(pin, ZERO), possible);
        pinClamped = cmp(final, pin) !== 0;
    }
    return { charged, status, credit, final, floored, upper_bug: upperBug,
             pin_clamped: pinClamped };
}

type ScopeTuple = readonly [string, string | null];

/** A scope key as one string, so it can key a Map / Set (`(q, sq)` in Python). */
function scopeKey(questionId: string, subQuestionId: string | null | undefined): string {
    return JSON.stringify([questionId, subQuestionId ?? null]);
}

/** V7 is a PRECONDITION of step 4: a scope's groups are assigned jointly, so a
 *  group whose members sat in two scopes would be charged once in EACH. Plans
 *  are validated at assembly (V7), so this never fires on a real plan; if it
 *  does, the input is wrong and pricing it would be a silent repair (§3.5a:
 *  a consuming path refuses). */
function _requireScopeLocalGroups(checks: ViewCheck[], scopeOf: Map<string, string>): void {
    const seen = new Map<string, string | undefined>();
    for (const c of checks) {
        const group = c.plan.charge_group;
        if (group == null) continue;
        const scope = scopeOf.get(c.plan.priced_terminal_id);
        if (!seen.has(group)) seen.set(group, scope);
        if (seen.get(group) !== scope) {
            throw new Error(`charge group ${JSON.stringify(group)} spans scopes ${seen.get(group)} `
                + `and ${scope} (V7): the pricer assigns a scope's groups jointly (AM-G13)`);
        }
    }
}

/** `itertools.product(*lists)` — lexicographic, the LAST list advancing fastest;
 *  no lists yields one empty tuple, an empty list yields nothing. */
function* product<T>(lists: T[][]): Generator<T[]> {
    if (lists.some((l) => l.length === 0)) return;
    const idx = lists.map(() => 0);
    for (;;) {
        yield idx.map((i, k) => lists[k][i]);
        let k = lists.length - 1;
        while (k >= 0) {
            idx[k] += 1;
            if (idx[k] < lists[k].length) break;
            idx[k] = 0;
            k -= 1;
        }
        if (k < 0) return;
    }
}

export function priceV6(view: DraftV6View, overlay?: PricingOverlay | null): PricedTest {
    const ovChecks = overlay?.checks ?? {};
    const ovPins = overlay?.terminal_points ?? {};
    const pinOf = (tid: string, pins: Record<string, string>): Dec | undefined => {
        const p = own(pins, tid);
        return p === undefined ? undefined : dec(p);
    };

    // plan order, always (a stable sort, as Python's)
    const checks = [...view.checks].sort((a, b) => a.plan_index - b.plan_index);
    const order = new Map<string, number>();
    checks.forEach((c, i) => order.set(c.plan.check_id, i));

    // 1 — resolve
    const resolved = new Map<string, Resolved>();
    for (const c of checks) {
        resolved.set(c.plan.check_id, _resolve(c, own(ovChecks, c.plan.check_id)));
    }

    // 2 — activity: the candidate charges
    const candidate = new Map<string, Dec>();
    const baseStatus = new Map<string, FaultStatus>();
    for (const c of checks) {
        const plan = c.plan;
        if (plan.role !== 'fault') continue;
        const r = resolved.get(plan.check_id) as Resolved;
        const requires = plan.requires;
        const active = requires == null || (
            resolved.has(requires) && cmp((resolved.get(requires) as Resolved).value, ZERO) > 0);
        if (!active) {
            baseStatus.set(plan.check_id, 'inactive');
        } else if (cmp(r.value, ZERO) >= 0) {
            baseStatus.set(plan.check_id, 'no_fault');
        } else {
            candidate.set(plan.check_id, r.value);
        }
    }

    const byTerminal = new Map<string, ViewCheck[]>();
    for (const c of checks) {
        const tid = c.plan.priced_terminal_id;
        if (!byTerminal.has(tid)) byTerminal.set(tid, []);
        (byTerminal.get(tid) as ViewCheck[]).push(c);
    }
    const byScope = new Map<string, ViewTerminal[]>();
    const scopeOf = new Map<string, string>();
    for (const t of view.terminals) {
        const key = scopeKey(t.question_id, t.sub_question_id);
        if (!byScope.has(key)) byScope.set(key, []);
        (byScope.get(key) as ViewTerminal[]).push(t);
        scopeOf.set(t.terminal_id, key);
    }
    _requireScopeLocalGroups(checks, scopeOf);

    // 3–6 — one scope at a time; its charge groups are assigned jointly (4)
    const settled = new Map<string, _Settled>();
    const superseded = new Set<string>();
    const moved = new Map<string, string>();     // charged check → the unpinned choice's terminal
    const terminalOf = new Map<string, string>();
    for (const c of checks) terminalOf.set(c.plan.check_id, c.plan.priced_terminal_id);
    for (const terms of byScope.values()) {
        const tids = new Set(terms.map((t) => t.terminal_id));
        const inScope = checks.filter((c) => tids.has(c.plan.priced_terminal_id));
        const ungrouped = new Set(inScope
            .filter((c) => candidate.has(c.plan.check_id) && c.plan.charge_group == null)
            .map((c) => c.plan.check_id));
        const firstMember = new Map<string, number>();
        const members = new Map<string, string[]>();
        for (const c of inScope) {
            const group = c.plan.charge_group;
            if (group == null) continue;
            if (!firstMember.has(group)) firstMember.set(group, order.get(c.plan.check_id) as number);
            if (candidate.has(c.plan.check_id)) {
                if (!members.has(group)) members.set(group, []);
                (members.get(group) as string[]).push(c.plan.check_id);
            }
        }
        const groups = [...members.keys()].sort(
            (a, b) => (firstMember.get(a) as number) - (firstMember.get(b) as number));

        const assign = (pins: Record<string, string>): [Set<string>, Map<string, _Settled>] => {
            let best: [Dec, Set<string>, Map<string, _Settled>] | null = null;
            for (const assignment of product(groups.map((g) => members.get(g) as string[]))) {
                const chosen = new Set<string>([...ungrouped, ...assignment]);
                const trial = new Map<string, _Settled>();
                for (const t of terms) {
                    trial.set(t.terminal_id, _settle(t, byTerminal.get(t.terminal_id) ?? [], chosen,
                                                     candidate, resolved, order,
                                                     pinOf(t.terminal_id, pins)));
                }
                const total = dsum([...trial.values()].map((st) => st.final));
                if (best === null || cmp(total, best[0]) < 0) {     // the FIRST minimum
                    best = [total, chosen, trial];
                }
            }
            const found = best as [Dec, Set<string>, Map<string, _Settled>];
            return [found[1], found[2]];
        };

        const [chosen, trial] = assign(ovPins);
        for (const [tid, st] of trial) settled.set(tid, st);
        for (const g of groups) {
            for (const cid of members.get(g) as string[]) {
                if (!chosen.has(cid)) superseded.add(cid);
            }
        }
        // [AM-G15] where would each group charge land if she had pinned nothing?
        if (groups.length > 0 && terms.some((t) => own(ovPins, t.terminal_id) !== undefined)) {
            const [unpinned] = assign({});
            for (const g of groups) {
                const here = exactlyOne((members.get(g) as string[]).filter((cid) => chosen.has(cid)));
                const there = exactlyOne((members.get(g) as string[]).filter((cid) => unpinned.has(cid)));
                if (here !== there) moved.set(here, terminalOf.get(there) as string);
            }
        }
    }

    // 7 — terminals, as priced
    const testFlags: string[] = [];
    const pricedTerminals: PricedTerminal[] = [];
    const awardedOf = new Map<string, Dec>();
    for (const t of view.terminals) {
        const tchecks = byTerminal.get(t.terminal_id) ?? [];
        const st = settled.get(t.terminal_id) as _Settled;
        const res = (c: ViewCheck) => resolved.get(c.plan.check_id) as Resolved;
        const flags: string[] = [];
        if (tchecks.some((c) => res(c).missing)) flags.push(UNVERIFIED_CHECK);
        if (tchecks.some((c) => res(c).source === 'gated')) flags.push(EVIDENCE_UNVERIFIED);
        if (st.floored) flags.push(BOUNDS_CLAMPED);
        if (st.upper_bug) {
            flags.push(BOUNDS_CLAMPED);
            testFlags.push(`${UPPER_CLAMP_LOGIC_BUG}:${t.terminal_id}`);
        }
        if (st.pin_clamped) flags.push(BOUNDS_CLAMPED);

        const charges: PricedCharge[] = [];
        for (const c of tchecks) {
            if (c.plan.role !== 'fault') continue;
            const cid = c.plan.check_id;
            const r = res(c);
            const status: FaultStatus = st.status.get(cid)
                ?? (superseded.has(cid) ? 'superseded' : baseStatus.get(cid) as FaultStatus);
            charges.push({
                check_id: cid,
                option_id: r.option_id || defaultOption(c.plan).option_id,
                amount: decToString(r.value),
                charged: decToString(st.charged.get(cid) ?? ZERO),
                status,
                moved_by_pin: moved.has(cid),
                moved_from_terminal_id: moved.get(cid) ?? null,
            });
        }

        let primary: string | null = null;
        let top = ZERO;
        for (const c of tchecks) {
            if (c.plan.role !== 'credit') continue;
            const v = res(c).value;
            if (cmp(v, top) > 0) {
                primary = c.plan.check_id;
                top = v;
            }
        }

        awardedOf.set(t.terminal_id, st.final);
        pricedTerminals.push({
            terminal_id: t.terminal_id,
            awarded: decToString(st.final),
            credit_points: decToString(st.credit),
            chip: _chip(st.final, dec(t.points_possible)),
            primary_check_id: primary,
            charges,
            notes_observed: tchecks
                .filter((c) => c.plan.role === 'note' && res(c).option_id === 'observed')
                .map((c) => c.plan.check_id),
            flags: _dedup(flags),
            overridden: own(ovPins, t.terminal_id) !== undefined,
            typed: tchecks.some((c) => res(c).source === 'amount'),
        });
    }

    // 8 — scopes and totals, unchanged (score_with_selection)
    const [scopes, scoring] = _aggregate(view, awardedOf);
    return {
        terminals: pricedTerminals,
        checks: checks.map((c) => {
            const r = resolved.get(c.plan.check_id) as Resolved;
            return {
                check_id: r.check_id,
                option_id: r.option_id,
                value: decToString(r.value),
                source: r.source,
                missing: r.missing,
                claimed_option_id: r.claimed_option_id,
            };
        }),
        scopes,
        total_score: decToString(scoring.total_score),
        total_possible: decToString(scoring.total_possible),
        flags: testFlags,
    };
}

/** Python's `(x,) = xs` — exactly one element, or the input is wrong. */
function exactlyOne<T>(xs: T[]): T {
    if (xs.length !== 1) throw new Error(`expected exactly one element, got ${xs.length}`);
    return xs[0];
}

function _aggregate(view: DraftV6View, awarded: Map<string, Dec>): [PricedScope[], SelectionScoring] {
    const keys: ScopeTuple[] = [];
    const possible = new Map<string, Dec>();
    const got = new Map<string, Dec>();
    for (const t of view.terminals) {
        const sq = t.sub_question_id ?? null;
        const key = scopeKey(t.question_id, sq);
        if (!possible.has(key)) {
            keys.push([t.question_id, sq]);
            possible.set(key, ZERO);
            got.set(key, ZERO);
        }
        possible.set(key, add(possible.get(key) as Dec, dec(t.points_possible)));
        got.set(key, add(got.get(key) as Dec, awarded.get(t.terminal_id) as Dec));
    }
    // `score_with_selection` reads exactly these three contract attributes;
    // the view carries them so the pricer stays a function of one document.
    const groups = view.selection.groups ?? [];
    const scoring = scoreWithSelection(
        keys.map(([q, s]) => ({ question_id: q, sub_question_id: s,
                                awarded: got.get(scopeKey(q, s)) as Dec })),
        {
            total_points: dec(view.selection.total_points),
            questions: view.selection.question_order.map((q) => ({ question_id: q })),
            selection_groups: groups.map((g) => ({ of_question_ids: [...g.of_question_ids],
                                                   choose_k: g.choose_k })),
        });
    const scopes: PricedScope[] = keys.map(([q, s]) => ({
        question_id: q,
        sub_question_id: s,
        points_possible: decToString(possible.get(scopeKey(q, s)) as Dec),
        awarded: decToString(got.get(scopeKey(q, s)) as Dec),
        counted: scoring.isCounted(q, s),
    }));
    return [scopes, scoring];
}

function _dedup(xs: string[]): string[] {
    const out: string[] = [];
    for (const x of xs) {
        if (!out.includes(x)) out.push(x);
    }
    return out;
}

// ═══════════════════════════════════════════════════════════════════════════
// step 8 — a port of `backend/app/services/selection_scoring.py`
// ═══════════════════════════════════════════════════════════════════════════
//
// * Denominator = `contract.total_points` (the ACHIEVABLE total). Read, never
//   recomputed.
// * Per group, the student's BEST-k answered members count toward the
//   numerator; ties break on contract question order.
// * Members beyond k are EXCLUDED — from numerator and denominator alike,
//   never "given 0".
// * Questions in no group are MANDATORY: always counted.

/** The minimum step 8 needs about one scope (`ScopeScore`). */
export interface ScopeScore {
    question_id: string;
    sub_question_id: string | null;
    awarded: Dec;
}

/** The three contract attributes `score_with_selection` reads. */
export interface SelectionContract {
    total_points: Dec;
    questions: { question_id: string }[];
    selection_groups: SelectionGroupView[];
}

export interface SelectionScoring {
    total_score: Dec;
    /** = contract.total_points (ACHIEVABLE) */
    total_possible: Dec;
    /** scope keys (`scopeKey`) that count toward neither total */
    excluded: ReadonlySet<string>;
    isCounted(questionId: string, subQuestionId: string | null): boolean;
}

/** Python's `xs[k:]`, negative `k` included. */
function sliceFrom<T>(xs: T[], k: number): T[] {
    return xs.slice(k < 0 ? Math.max(0, xs.length + k) : k);
}

export function scoreWithSelection(scopes: ScopeScore[], contract: SelectionContract): SelectionScoring {
    const make = (totalScore: Dec, excluded: Set<string>): SelectionScoring => ({
        total_score: totalScore,
        total_possible: contract.total_points,
        excluded,
        isCounted: (q, s) => !excluded.has(scopeKey(q, s)),
    });

    // Question -> its scopes' awarded total.
    const byQuestion = new Map<string, Dec>();
    const scopesOfQuestion = new Map<string, string[]>();
    for (const s of scopes) {
        byQuestion.set(s.question_id, add(byQuestion.get(s.question_id) ?? ZERO, s.awarded));
        if (!scopesOfQuestion.has(s.question_id)) scopesOfQuestion.set(s.question_id, []);
        (scopesOfQuestion.get(s.question_id) as string[]).push(scopeKey(s.question_id, s.sub_question_id));
    }

    // Fast path: no selection groups ⇒ nothing can be excluded.
    if (!contract.selection_groups || contract.selection_groups.length === 0) {
        return make(dsum(scopes.map((s) => s.awarded)), new Set());
    }

    // Deterministic tie-break: contract question order (a later duplicate wins,
    // as in the Python dict comprehension).
    const order = new Map<string, number>();
    contract.questions.forEach((q, i) => order.set(q.question_id, i));

    const excluded = new Set<string>();
    for (const group of contract.selection_groups) {
        const members = group.of_question_ids.filter((qid) => scopesOfQuestion.has(qid));
        if (members.length === 0) continue;
        // key = (-awarded, order): highest awarded first, then question order (stable)
        const ranked = [...members].sort((a, b) =>
            cmp(byQuestion.get(b) ?? ZERO, byQuestion.get(a) ?? ZERO)
            || (order.get(a) ?? 1_000_000) - (order.get(b) ?? 1_000_000));
        for (const qid of sliceFrom(ranked, group.choose_k)) {     // everything past the best-k
            for (const key of scopesOfQuestion.get(qid) as string[]) excluded.add(key);
        }
    }

    const totalScore = dsum(scopes
        .filter((s) => !excluded.has(scopeKey(s.question_id, s.sub_question_id)))
        .map((s) => s.awarded));
    // SINGLE SOURCE. Never Σ scope.points_possible.
    return make(totalScore, excluded);
}
