"""[AM-G13 · G1] PRC-6 and PRC-4, EXHAUSTIVELY over 6,000 seeded cases.

Every case comes from the one case builder (`build_random_case`, the same one
the vectors and properties use), driven by a seeded PRNG so the run is
identical everywhere. For each case, EVERY improving move is tried — each
credit raised to each higher option, each fault set to `none` — and:

  PRC-6  the total never falls;
  PRC-4  in every charge group with a candidate, exactly one member is charged.

This is the search that found Q-22 (69 violations under §4.2 as written) and
Q-23 (3, all on pinned terminals, under the objective measured before
overrides); it must now find none. ~45 s, so it runs only when asked
(`VIVI_RUN_SLOW=1`) and in every gate run (`VIVI_TEST_GATE=1`).
"""
from __future__ import annotations

from typing import Dict, List

import pytest

from app.services.pricing_v6 import CheckDecision, _resolve, price
from tests.services.pricing_v6_cases import PrngDraw, build_random_case

SEEDS = 6000
KNOBS = dict(max_questions=2, max_subs=1, max_terminals=2)


def _improving_moves(v, ov):
    for vc in v.checks:
        c = vc.plan
        if c.role == "credit":
            current = _resolve(vc, ov.checks.get(c.check_id)).value
            for o in c.options:
                if o.value > current:
                    yield c.check_id, CheckDecision(option_id=o.option_id)
        elif c.role == "fault":
            yield c.check_id, CheckDecision(option_id="none")


def _charged_once_violations(v, priced) -> List[str]:
    group_of = {vc.plan.check_id: vc.plan.charge_group for vc in v.checks}
    candidates: Dict[str, int] = {}
    charged: Dict[str, int] = {}
    for t in priced.terminals:
        for ch in t.charges:
            g = group_of[ch.check_id]
            if g is None or ch.status in ("inactive", "no_fault"):
                continue
            candidates[g] = candidates.get(g, 0) + 1
            if ch.status != "superseded":
                charged[g] = charged.get(g, 0) + 1
    return [g for g in candidates if charged.get(g, 0) != 1]


@pytest.mark.slow
def test_prc6_and_prc4_hold_over_6000_seeded_cases():
    monotone, once, moves, pinned = [], [], 0, 0
    for seed in range(SEEDS):
        v, ov = build_random_case(PrngDraw(seed), **KNOBS)
        pinned += bool(ov.terminal_points)
        base = price(v, ov)
        once += [(seed, g) for g in _charged_once_violations(v, base)]
        for cid, move in _improving_moves(v, ov):
            moves += 1
            after = price(v, ov.model_copy(update={"checks": {**ov.checks, cid: move}}))
            if after.total_score < base.total_score:
                monotone.append((seed, cid, move.option_id, base.total_score, after.total_score))
            once += [(seed, g) for g in _charged_once_violations(v, after)]
    assert moves > 50_000 and pinned > 900, (moves, pinned)    # the search is the search
    assert monotone == [], f"PRC-6: {len(monotone)} violations, first {monotone[:3]}"
    assert once == [], f"PRC-4: {len(once)} violations, first {once[:3]}"
