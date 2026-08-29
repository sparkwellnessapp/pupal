"""
Gates tool guards — kills-first arithmetic on engineered data.

The live known-answer check was run at build time against the E8 results dir
and reproduced the ratified record exactly (K1 80/80 PASS · K2 7/245 = 2.86%
KILLED · K4 8.25 PASS · cross-tab 72/32/7). These tests pin the logic on
synthetic rows so they survive results-dir pruning.
"""
from __future__ import annotations

from decimal import Decimal

from .tools.gates import K2_BAR, cross_tab, gates, kills


def _row(tid, gt, ai, fixture="fx", **kw):
    return {"terminal_id": tid, "gt_awarded": gt, "ai_awarded": ai,
            "excluded_by_selection": False, "ungradable_scope": False, **kw}


def _trial(rows, fixture="fx", valid=True):
    return {"fixture": fixture, "valid": valid, "diagnostic_subset": False,
            "terminals": rows}


POINTS = {("fx", "t1"): Decimal("2"), ("fx", "t2"): Decimal("3"),
          ("fx", "t3"): Decimal("1")}


def test_cross_tab_classes():
    trials = [_trial([_row("t1", "0", "0"),        # ZERO→ZERO
                      _row("t2", "1.5", "3"),      # PARTIAL→FULL
                      _row("t3", "1", "0.5")])]    # FULL→PARTIAL
    tab = cross_tab(trials, POINTS)
    assert tab == {("ZERO", "ZERO"): 1, ("PARTIAL", "FULL"): 1,
                   ("FULL", "PARTIAL"): 1}


def test_k1_kills_on_any_false_credit():
    ok = kills([_trial([_row("t1", "0", "0")])], POINTS, {})
    assert ok["K1"]["pass"]
    bad = kills([_trial([_row("t1", "0", "0.25")])], POINTS, {})
    assert not bad["K1"]["pass"]


def test_k2_bar_is_the_c2_fraction():
    # exactly at the C2 baseline (1 of ~40.8 == 6/245): engineered 6/245 scale
    rows = [_row("t2", "1.5", "3")] + [_row("t2", "1.5", "1.5")] * 244
    trials = [_trial(rows)]
    k = kills(trials, {("fx", "t2"): Decimal("3")}, {})
    assert k["K2"]["pass"]                      # 1/245 < 6/245
    rows = [_row("t2", "1.5", "3")] * 7 + [_row("t2", "1.5", "1.5")] * 238
    k = kills([_trial(rows)], {("fx", "t2"): Decimal("3")}, {})
    assert not k["K2"]["pass"]                  # 7/245 > 6/245 — the E8 case
    assert float(K2_BAR) * 245 == 6.0


def test_k4_reads_instability_aggregate():
    agg = {"instability": {"max_ai_total_spread": 9.0}}
    assert not kills([], POINTS, agg)["K4"]["pass"]
    agg = {"instability": {"max_ai_total_spread": 8.25}}
    assert kills([], POINTS, agg)["K4"]["pass"]


def test_ga_table_reads_aggregates():
    # [R-3, 2026-08-29] GA-7 ceilings are 0.15 hard / 0.10 target
    agg = {"terminal_within_precision_rate": 0.86, "strict_shippable_rate": 0.5,
           "boundary_flip_rate": 0.1, "edit_burden": {"median": 4, "max": 8},
           "cost_usd": {"mean": 0.12},
           "instability": {"max_ai_total_spread": 2.5}}
    g = gates([_trial([_row("t1", "0", "0")])], POINTS, agg)
    assert all(g[n]["pass"] for n in ("GA-1", "GA-2", "GA-3", "GA-4", "GA-5", "GA-6", "GA-7"))
    assert g["GA-7"]["target_met"] is False     # 0.12 > 0.10 target
    agg["edit_burden"] = {"median": 5, "max": 8}
    assert gates([], POINTS, agg)["GA-6"]["pass"] is False
