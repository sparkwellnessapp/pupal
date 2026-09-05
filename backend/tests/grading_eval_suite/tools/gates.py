"""
Kills-first gate evaluator (mission §1.1/§2) — MECHANIZED because hand
arithmetic has erred twice in this suite's history (the Q2-share slip; the E8
K2 hand count). Every trial's analysis STARTS with this tool's output.

    python -m tests.grading_eval_suite.tools.gates <results_dir>

Prints, in order: KILLS (K1/K2/K4) → GA gate table → the R.3 partial-credit
cross-tab. Pure functions over results.json rows; terminal points_possible
comes from the REAL fixture bundles (the same loader grade mode uses).

K2's bar is the C2 baseline stated in the mission as 2.4%, encoded as the
actual measured fraction 6/245 (=0.024489…): "vs the C2 baseline" compares to
the baseline, not to a rounding of it. A run landing between 2.40% and 2.449%
is inside the rounding sliver — flag it for the owner rather than adjudicating.
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

K2_BAR = Decimal("6") / Decimal("245")          # C2 baseline, exact
K4_BAR = 8.25                                    # E8's confirmed max spread
GA = {
    "GA-2": ("terminal_within_precision_rate", ">=", 0.85),
    "GA-3": ("strict_shippable_rate", ">=", 0.50),
    "GA-4": ("boundary_flip_rate", "<=", 0.10),
    "GA-5": ("max_ai_total_spread", "<=", 3.0),
}
# [R-3, owner ruling 2026-08-29 FP2] was 0.08/0.05; OVER-CEILING stamps
# re-evaluate against the new hard bar.
GA7_HARD, GA7_TARGET = 0.15, 0.10


def _cls(v: Decimal, possible: Decimal) -> str:
    if v == 0:
        return "ZERO"
    return "FULL" if v == possible else "PARTIAL"


def _included_rows(trials: List[dict]) -> List[dict]:
    rows = []
    for t in trials:
        if not t.get("valid") or t.get("diagnostic_subset"):
            continue
        for r in t.get("terminals", []):
            # [R-2] `unattempted` (transcription-derived) keeps unselected
            # scopes out of K1's denominator; `excluded_by_selection` (best-k on
            # the total) stays the totals fact. Old rows lack the key → False.
            if r.get("unattempted") or r.get("ungradable_scope"):
                continue
            rows.append({**r, "fixture": t["fixture"]})
    return rows


def cross_tab(trials: List[dict],
              points: Dict[Tuple[str, str], Decimal]) -> Dict[Tuple[str, str], int]:
    tab: Dict[Tuple[str, str], int] = {}
    for r in _included_rows(trials):
        possible = points[(r["fixture"], r["terminal_id"])]
        key = (_cls(Decimal(r["gt_awarded"]), possible),
               _cls(Decimal(r["ai_awarded"]), possible))
        tab[key] = tab.get(key, 0) + 1
    return tab


def kills(trials: List[dict], points: Dict[Tuple[str, str], Decimal],
          aggregates: dict) -> Dict[str, dict]:
    tab = cross_tab(trials, points)
    gt_zero = sum(n for (g, _), n in tab.items() if g == "ZERO")
    gt_zero_ai_zero = tab.get(("ZERO", "ZERO"), 0)
    gt_partial = sum(n for (g, _), n in tab.items() if g == "PARTIAL")
    p2f = tab.get(("PARTIAL", "FULL"), 0)
    k2_rate = (Decimal(p2f) / Decimal(gt_partial)) if gt_partial else Decimal("0")
    spread = float((aggregates.get("instability") or {}).get("max_ai_total_spread", 0.0))
    out = {
        "K1": {"pass": gt_zero_ai_zero == gt_zero,
               "value": f"{gt_zero_ai_zero}/{gt_zero}",
               "bar": "GT-ZERO→AI-ZERO must be total (any false credit kills)"},
        "K2": {"pass": k2_rate <= K2_BAR,
               "value": f"{p2f}/{gt_partial} = {float(k2_rate) * 100:.2f}%",
               "bar": "≤ C2 baseline 2.4% (6/245)",
               "rounding_sliver": bool(Decimal("0.024") < k2_rate <= K2_BAR)},
        "K4": {"pass": spread <= K4_BAR,
               "value": spread, "bar": f"max ai_total_spread ≤ {K4_BAR}"},
    }
    return out


def gates(trials: List[dict], points: Dict[Tuple[str, str], Decimal],
          aggregates: dict) -> Dict[str, dict]:
    tab = cross_tab(trials, points)
    gt_zero = sum(n for (g, _), n in tab.items() if g == "ZERO")
    clean = tab.get(("ZERO", "ZERO"), 0)
    g: Dict[str, dict] = {
        "GA-1": {"value": f"{clean}/{gt_zero}", "target": "100% — inviolable",
                 "pass": clean == gt_zero}}
    flat = dict(aggregates)
    flat["max_ai_total_spread"] = (aggregates.get("instability") or {}).get(
        "max_ai_total_spread")
    for name, (key, op, bar) in GA.items():
        v = flat.get(key)
        ok = None if v is None else (v >= bar if op == ">=" else v <= bar)
        g[name] = {"value": v, "target": f"{op} {bar}", "pass": ok}
    eb = aggregates.get("edit_burden") or {}
    g["GA-6"] = {"value": f"median {eb.get('median')} / max {eb.get('max')}",
                 "target": "median ≤ 4 AND max ≤ 8",
                 "pass": (None if not eb else
                          (eb.get("median", 99) <= 4 and eb.get("max", 99) <= 8))}
    cost = (aggregates.get("cost_usd") or {}).get("mean")
    g["GA-7"] = {"value": cost, "target": f"≤ ${GA7_HARD} hard / ${GA7_TARGET} target",
                 "pass": None if cost is None else cost <= GA7_HARD,
                 "target_met": None if cost is None else cost <= GA7_TARGET}
    return g


def render(run_dir: Path, kills_d: dict, gates_d: dict, tab: dict,
           provenance: dict) -> str:
    L: List[str] = []
    L.append(f"# Gates — {run_dir.name}")
    L.append(f"provenance: model `{provenance.get('model_key')}` · arch "
             f"`{provenance.get('architecture', 'v3')}` · prompt "
             f"`{provenance.get('prompt_version')}` · plan "
             f"`{provenance.get('plan_version', '-')}` · sut `{provenance.get('sut_hash')}`"
             + (f" · **{'SCREENING' if provenance.get('SCREENING') else ''}**"
                if provenance.get("SCREENING") else ""))
    L.append("")
    L.append("## KILLS — evaluated first, before any headline number")
    L.append("| kill | bar | this run | verdict |")
    L.append("|---|---|---|---|")
    for k in ("K1", "K2", "K4"):
        d = kills_d[k]
        verdict = "PASS" if d["pass"] else "**✗ KILLED**"
        if k == "K2" and d.get("rounding_sliver"):
            verdict += " ⚠ rounding sliver — surface to owner"
        L.append(f"| {k} | {d['bar']} | {d['value']} | {verdict} |")
    L.append("")
    L.append("## GA gates")
    L.append("| gate | target | this run | verdict |")
    L.append("|---|---|---|---|")
    for name, d in gates_d.items():
        v = "-" if d["pass"] is None else ("PASS" if d["pass"] else "✗")
        if name == "GA-7" and d.get("pass") and not d.get("target_met"):
            v += f" (over ${GA7_TARGET} target)"
        L.append(f"| {name} | {d['target']} | {d['value']} | {v} |")
    L.append("")
    L.append("## R.3 partial-credit cross-tab (GT rows × AI cols)")
    L.append("| GT \\ AI | ZERO | PARTIAL | FULL |")
    L.append("|---|---|---|---|")
    for g in ("ZERO", "PARTIAL", "FULL"):
        L.append(f"| {g} | " + " | ".join(
            str(tab.get((g, a), 0)) for a in ("ZERO", "PARTIAL", "FULL")) + " |")
    return "\n".join(L)


def evaluate_run(run_dir: Path, *, write: bool = True) -> str:
    res = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    trials, prov, agg = res["trials"], res["provenance"], res["aggregates"]

    from ..fixtures import load_bundle
    points: Dict[Tuple[str, str], Decimal] = {}
    for fx in prov.get("fixtures", []):
        b = load_bundle(fx)
        for tid, info in b.terminal_infos.items():
            points[(fx, tid)] = info.points

    text = render(run_dir, kills(trials, points, agg),
                  gates(trials, points, agg), cross_tab(trials, points), prov)
    if write:
        (run_dir / "gates.md").write_text(text + "\n", encoding="utf-8")
    return text


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m tests.grading_eval_suite.tools.gates <results_dir>")
    print(evaluate_run(Path(sys.argv[1])))


if __name__ == "__main__":
    main()
