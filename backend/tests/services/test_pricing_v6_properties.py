"""grader-v6 Phase 1 — pricer properties (Hypothesis, ≥ 2,000 examples each;
PR_grader_v6_options.md §14). Random cases come from the one case builder
(`pricing_v6_cases.build_random_case`) driven by Hypothesis draws, so a
counterexample shrinks over real structure, not over a seed.

Profiles: routine runs use `routine` (200 examples); the G1 gate evidence is
`HYPOTHESIS_PROFILE=phase1` (2,000 each, §12 G1); `fast` (150) is for tight loops."""
from __future__ import annotations

import os
import random
from decimal import Decimal as D

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.agents.explainer.fallback import compose_reasoning_he
from app.services.pricing_v6 import CheckDecision, price
from tests.services.pricing_v6_cases import HypothesisDraw, build_random_case

# [A-10] Two tiers: "dev" is the inner loop (T0, 100 examples), "gate" is every
# phase gate (T1, 2,000). A gate run (VIVI_TEST_GATE=1) uses "gate" unless a
# profile is named. "phase1" / "routine" / "fast" are kept as aliases.
_QUIET = dict(deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
for _name, _n in (("dev", 100), ("gate", 2000), ("phase1", 2000), ("routine", 200), ("fast", 150)):
    settings.register_profile(_name, max_examples=_n, **_QUIET)
settings.load_profile(os.environ.get(
    "HYPOTHESIS_PROFILE",
    "gate" if os.environ.get("VIVI_TEST_GATE", "").strip() not in ("", "0", "false") else "dev"))


def _case(data):
    return build_random_case(HypothesisDraw(data))


def _values(view):
    return {c.plan.check_id: c.plan for c in view.checks}


@given(st.data())
def prop_bounds_hold(data):
    view, ov = _case(data)
    p = price(view, ov)
    possible = {t.terminal_id: t.points_possible for t in view.terminals}
    for t in p.terminals:
        assert D("0") <= t.awarded <= possible[t.terminal_id]           # PRC-5


@given(st.data())
def prop_inactive_faults_charge_zero(data):
    view, ov = _case(data)
    for t in price(view, ov).terminals:
        for ch in t.charges:
            if ch.status in ("inactive", "no_fault", "superseded"):
                assert ch.charged == D("0")                             # PRC-2


@given(st.data())
def prop_fault_capped_by_behavior(data):
    view, ov = _case(data)
    p = price(view, ov)
    resolved = {r.check_id: r.value for r in p.checks}
    plan = _values(view)
    for t in p.terminals:
        by_behavior = {}
        for ch in t.charges:
            req = plan[ch.check_id].requires
            if req is not None:
                by_behavior[req] = by_behavior.get(req, D("0")) + ch.charged
        for req, total in by_behavior.items():
            assert total >= -resolved[req]              # PRC-3 BehaviorCap: the SUM [AM-G13]


@given(st.data())
def prop_charge_once(data):
    view, ov = _case(data)
    plan = _values(view)
    candidates, charged = {}, {}
    for t in price(view, ov).terminals:
        for ch in t.charges:
            g = plan[ch.check_id].charge_group
            if g is None or ch.status in ("inactive", "no_fault"):
                continue
            candidates[g] = candidates.get(g, 0) + 1
            if ch.status == "superseded":
                assert ch.charged == D("0")
            else:
                charged[g] = charged.get(g, 0) + 1
    assert all(charged.get(g, 0) == 1 for g in candidates)  # PRC-4 ChargedOnce: EXACTLY one [AM-G13]


@given(st.data())
def prop_total_monotone(data):
    """PRC-6: moving a credit check to a HIGHER-valued option, or a fault check
    to `none`, never lowers the test total. The move is made through the
    overlay (never evidence-gated) so the test isolates the pricing algebra."""
    view, ov = _case(data)
    before = price(view, ov)
    resolved = {r.check_id: r for r in before.checks}
    candidates = [c.plan for c in view.checks if c.plan.role in ("credit", "fault")]
    check = data.draw(st.sampled_from(candidates))
    if check.role == "credit":
        cur = resolved[check.check_id].value
        higher = [o for o in check.options if o.value > cur]
        if not higher:
            return
        move = CheckDecision(option_id=data.draw(st.sampled_from(higher)).option_id)
    else:
        move = CheckDecision(option_id="none")
    ov2 = ov.model_copy(update={"checks": {**ov.checks, check.check_id: move}})
    after = price(view, ov2)
    assert after.total_score >= before.total_score, (check.check_id, move)


@given(st.data())
def prop_total_invariant_under_check_permutation(data):
    view, ov = _case(data)
    shuffled = list(view.checks)
    random.Random(data.draw(st.integers(0, 10_000))).shuffle(shuffled)
    assert price(view.model_copy(update={"checks": shuffled}), ov) == price(view, ov)


@given(st.data())
def prop_fallback_reasoning_is_deterministic(data):
    view, ov = _case(data)
    p = price(view, ov)
    shuffled = list(view.checks)
    random.Random(data.draw(st.integers(0, 10_000))).shuffle(shuffled)
    p2 = price(view.model_copy(update={"checks": shuffled}), ov)
    for t in p.terminals:
        a = compose_reasoning_he(p, view, t.terminal_id)
        b = compose_reasoning_he(p2, view.model_copy(update={"checks": shuffled}), t.terminal_id)
        assert a == b
        assert 1 <= len(a) <= 200


# pytest collects `test_*`; the catalog names are `prop_*` (§14). Bind both.
test_prop_bounds_hold = prop_bounds_hold
test_prop_inactive_faults_charge_zero = prop_inactive_faults_charge_zero
test_prop_fault_capped_by_behavior = prop_fault_capped_by_behavior
test_prop_charge_once = prop_charge_once
test_prop_total_monotone = prop_total_monotone
test_prop_total_invariant_under_check_permutation = prop_total_invariant_under_check_permutation
test_prop_fallback_reasoning_is_deterministic = prop_fallback_reasoning_is_deterministic
