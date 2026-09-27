"""
Gates tool guards — kills-first arithmetic on engineered data.

The live known-answer check was run at build time against the E8 results dir
and reproduced the ratified record exactly (K1 80/80 PASS · K2 7/245 = 2.86%
KILLED · K4 8.25 PASS · cross-tab 72/32/7). These tests pin the logic on
synthetic rows so they survive results-dir pruning.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

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


# ---------------------------------------------------------------------------
# Track B 1c (owner ruling 2026-09-27): CONTESTED cells. A GT terminal can be
# marked contested (the award stands; the owner has ruled the cell counts as a
# kill for NEITHER side until it is resolved). gates.py excludes it from every
# CELL-level measure — K1, K2, the cross-tab, GA-1, GA-2, GA-6 — and names it
# in gates.md. The first: hobby din q2.ב.c4.s2 (RUNLOG.md:1771-1775).
# ---------------------------------------------------------------------------

import json as _json

from .tools.gates import render

CONTESTED = {("fx", "t1"): {"ruled": "2026-08-31", "ref": "RUNLOG.md:1771-1775",
                            "why": "wrong-target answer; teacher to rule"}}


def _contested_trials():
    rows = [_row("t1", "0", "2", within_precision=False, burden_precision=True),
            _row("t2", "1.5", "1.5", within_precision=True),
            _row("t3", "0", "0", within_precision=True)]
    return [_trial(rows), _trial([dict(r) for r in rows])]


def test_a_contested_cell_is_excluded_from_the_cell_level_kills_and_gates():
    trials = _contested_trials()
    agg = {"terminal_within_precision_rate": 4 / 6, "edit_burden": {"median": 1, "max": 1},
           "instability": {"max_ai_total_spread": 0.0}}
    for t in trials:
        t["edit_burden"] = 1
    # without the ruling, the false credit kills
    assert not kills(trials, POINTS, agg)["K1"]["pass"]
    k = kills(trials, POINTS, agg, contested=CONTESTED)
    assert k["K1"]["pass"] and k["K1"]["value"] == "2/2"
    assert cross_tab(trials, POINTS, contested=CONTESTED) == {
        ("PARTIAL", "PARTIAL"): 2, ("ZERO", "ZERO"): 2}
    g = gates(trials, POINTS, agg, contested=CONTESTED)
    assert g["GA-1"]["pass"]
    assert g["GA-2"]["value"] == 1.0            # recomputed without the cell
    assert g["GA-6"]["value"] == "median 0.0 / max 0"   # each trial's burden less the cell's


def test_gates_md_names_every_excluded_contested_cell():
    trials = _contested_trials()
    agg = {"instability": {"max_ai_total_spread": 0.0}}
    text = render(Path("run"), kills(trials, POINTS, agg, contested=CONTESTED),
                  gates(trials, POINTS, agg, contested=CONTESTED),
                  cross_tab(trials, POINTS, contested=CONTESTED), {},
                  contested=CONTESTED, trials=trials)
    assert "CONTESTED" in text
    assert "fx" in text and "t1" in text and "RUNLOG.md:1771-1775" in text
    assert "2 trial rows" in text


def test_without_contested_cells_the_gates_read_the_aggregates_unchanged():
    agg = {"terminal_within_precision_rate": 0.86, "edit_burden": {"median": 4, "max": 8}}
    g = gates([_trial([_row("t1", "0", "0")])], POINTS, agg, contested=CONTESTED)
    assert g["GA-2"]["value"] == 0.86 and g["GA-6"]["value"] == "median 4 / max 8"


def test_din_q2_bet_c4_s2_is_the_first_contested_cell_and_its_award_is_untouched():
    from .fixtures import SUITE_DIR, load_bundle
    gt = load_bundle("din_ezra").gt
    cell = next(t for t in gt.terminals if t.terminal_id == "q2.ב.c4.s2")
    assert cell.contested is not None and cell.awarded == Decimal("0")
    assert cell.contested.ruled == "2026-08-31"
    # the citation must point at the ruling's own words
    for ref in cell.contested.ref.split(";"):
        path, span = ref.strip().rsplit(":", 1)
        lo, hi = (int(x) for x in span.split("-"))
        lines = (SUITE_DIR / path).read_text(encoding="utf-8").splitlines()[lo - 1:hi]
        assert any("CONTESTED" in line for line in lines), ref
    others = [(fx, t.terminal_id) for fx in ("dan_basiuk", "moran_aharon", "omer_gelber",
                                              "yonatan_basiuk")
              for t in load_bundle(fx).gt.terminals if t.contested is not None]
    assert others == [], "no other cell has been ruled contested"
