"""
grader-v6 CS eval — gate math and the CS section of EVAL_REPORT_v6.md (Oct 6 rulings §3.7a).

    python -m tests.grading_eval_suite.tools.v6_report <v6_run_dir> <v5_baseline_run_dir> \\
        [--arm-b <arm_b.json>] [--out docs/EVAL_REPORT_v6.md]

Both runs are scored by the SAME instrument (runner → scoring → gates), so K1/K2/K4,
K3 and G-Z are read from `tools/gates.py` on each run, CONTESTED cells excluded by the
current GT (gates.py does it) and model_fallback trials excluded (the runner marks them
invalid; counted here). What only v6 has is read from the v6 block of every draft:

  G-D1  double-charged cells in D — two CHARGED fault checks at one terminal sharing a
        marker or a charge group, or one marker charged at two terminals of a test.
  G-D2  cells in D charged by more than one tier of one fault — two charged fault checks
        at one terminal whose markers are tiers of ONE fault (TIER_SETS: the census
        Appendix-B terminals that carry several markers of one fault).
  G-B   every bounds_clamped, with its plan cause.
  cost  per test by component (verifier · explainer arm A · arm B), on registry cards;
        the cache-hit rate (CL-2); the E-1..E-5 pass rate.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND))

from app.schemas.graded_test_draft import GradedTestDraft                      # noqa: E402
from app.schemas.graded_test_draft_v6 import v6_content                        # noqa: E402
from app.services.pricing_v6 import price                                      # noqa: E402
from app.services.transcription.two_phase.instrument import cost_usd           # noqa: E402
from app.services.transcription.vlm_provider import Usage                      # noqa: E402
from tests.eval_common.models_registry import MODELS as _REG                   # noqa: E402
from tests.grading_eval_suite.fixtures import load_bundle                      # noqa: E402
from tests.grading_eval_suite.plan_expressibility import UNWRITTEN_RULINGS      # noqa: E402
from tests.grading_eval_suite.tools.gates import cross_tab, gates, kills        # noqa: E402

# Census Appendix B: terminals carrying deductions (D), the once-group partners, and
# the multi-marker terminals G-D2 is measured over.
D_TERMINALS = {
    "hobby_tvshow": {"q1.ב.c6", "q1.ג.c3", "q1.ג.c6", "q1.ג.c7", "q2.ב.c3.s0", "q2.ב.c3.s2",
                     "q2.ב.c3.s3", "q2.ב.c4.s3", "q2.ג.c0.s2"},
    "bagrut_899371": {"q4.ב.c4", "q4.ב.c7", "q5.א.c0", "q5.ב.c2", "q5.ב.c4", "q6.c0", "q6.c6"},
}
# Tiers of ONE fault (several markers, one fault). q2.ב.c3.s0's three markers are
# independent faults (start index · getter · upper bound) and are not a tier set.
TIER_TERMINALS = {"q5.ב.c2", "q5.ב.c4"}
_CHARGED = ("applied", "capped", "floored")


def _card(model_id: str):
    for m in _REG.values():
        if m.model_id == model_id:
            return m.price
    raise SystemExit(f"no registry card for {model_id!r}")


def _usage_cost(u: Optional[dict]) -> float:
    if not u or not u.get("calls"):
        return 0.0
    return cost_usd(Usage(input_tokens=u["input_tokens"], output_tokens=u["output_tokens"],
                          cached_input_tokens=u.get("cached_input_tokens") or None),
                    _card(u["model"]))


def _load_run(run_dir: Path):
    res = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    points: Dict[Tuple[str, str], Decimal] = {}
    contested: Dict[Tuple[str, str], Any] = {}
    bundles = {}
    for fx in res["provenance"].get("fixtures", []):
        b = load_bundle(fx)
        bundles[fx] = b
        for tid, info in b.terminal_infos.items():
            points[(fx, tid)] = info.points
        for t in b.gt.terminals:
            if t.contested is not None:
                contested[(fx, t.terminal_id)] = t.contested
    return res, points, contested, bundles


def _gate_numbers(res, points, contested) -> Dict[str, Any]:
    trials, agg = res["trials"], res["aggregates"]
    k = kills(trials, points, agg, contested)
    g = gates(trials, points, agg, contested)
    tab = cross_tab(trials, points, contested)
    gt_partial = sum(n for (gc, _), n in tab.items() if gc == "PARTIAL")
    p2z = tab.get(("PARTIAL", "ZERO"), 0)
    return {"kills": k, "K3": g["GA-2"]["value"], "GZ": (p2z, gt_partial),
            "cost_mean": (agg.get("cost_usd") or {}).get("mean"),
            "n_valid": agg.get("n_valid"), "n_trials": len(trials)}


def _drafts(run_dir: Path):
    for p in sorted((run_dir / "drafts").glob("*_r*.json")):
        if p.name.endswith(".meta.json"):
            continue
        fixture, r = p.stem.rsplit("_r", 1)
        yield fixture, int(r), GradedTestDraft.model_validate_json(p.read_text(encoding="utf-8"))


def v6_measures(run_dir: Path, bundles) -> Dict[str, Any]:
    gd1, gd2, gb = [], [], []
    comp = defaultdict(list)
    cache = defaultdict(lambda: [0, 0])
    e_total = e_model = 0
    failed_rules = Counter()
    fallback_scopes = 0
    for fixture, r, draft in _drafts(run_dir):
        content = v6_content(draft)
        if content is None:
            continue
        exam = bundles[fixture].exam_id
        priced = price(content.to_view())
        checks = {c.plan.check_id: c.plan for c in content.checks}
        marker_terminals = defaultdict(set)
        for t in priced.terminals:
            charged = [ch for ch in t.charges if ch.status in _CHARGED]
            markers = [{o.marker_id for o in checks[ch.check_id].options if o.marker_id}
                       for ch in charged]
            for ms in markers:
                for m in ms:
                    marker_terminals[m].add(t.terminal_id)
            if t.terminal_id in D_TERMINALS.get(exam, set()):
                groups = [checks[ch.check_id].charge_group for ch in charged
                          if checks[ch.check_id].charge_group]
                shared_marker = any(markers[i] & markers[j] for i in range(len(markers))
                                    for j in range(i + 1, len(markers)))
                if shared_marker or len(groups) != len(set(groups)):
                    gd1.append((fixture, r, t.terminal_id, [ch.check_id for ch in charged]))
                if t.terminal_id in TIER_TERMINALS and len(charged) > 1:
                    gd2.append((fixture, r, t.terminal_id, [ch.check_id for ch in charged]))
            if "bounds_clamped" in t.flags:
                gb.append((fixture, r, t.terminal_id, str(t.awarded),
                           [(ch.check_id, str(ch.charged), ch.status) for ch in t.charges]))
        for m, tids in marker_terminals.items():
            if len(tids) > 1:
                gd1.append((fixture, r, f"marker {m}", sorted(tids)))
        v, e = content.verifier_usage, content.explainer_usage
        comp["verifier"].append(_usage_cost(v.model_dump() if v else None))
        comp["explainer_a"].append(_usage_cost(e.model_dump() if e else None))
        for name, u in (("verifier", v), ("explainer_a", e)):
            if u:
                cache[name][0] += u.cached_input_tokens
                cache[name][1] += u.input_tokens
        fallback_scopes += sum(1 for s in content.scopes if s.usage and s.usage.model_fallback)
        for x in content.explanations:
            e_total += 1
            e_model += x.source == "model"
            failed_rules.update(x.failed_rules)
    mean = {k: (statistics.mean(v) if v else 0.0) for k, v in comp.items()}
    return {"G-D1": gd1, "G-D2": gd2, "G-B": gb, "cost_mean": mean,
            "cache": {k: (a / b if b else 0.0) for k, (a, b) in cache.items()},
            "e_pass": (e_model, e_total), "failed_rules": dict(failed_rules),
            "model_fallback_scopes": fallback_scopes}


def _unwritten(res) -> List[str]:
    out = []
    for t in res["trials"]:
        for row in t.get("terminals", []):
            if (t["fixture"], row["terminal_id"]) in UNWRITTEN_RULINGS:
                out.append(f"{t['fixture']} r{t.get('trial_index')} {row['terminal_id']}: "
                           f"GT {row['gt_awarded']} · AI {row['ai_awarded']}")
    return out


def render(v6_dir: Path, v5_dir: Path, arm_b: Optional[dict]) -> str:
    res6, pts6, con6, bundles = _load_run(v6_dir)
    res5, pts5, con5, _ = _load_run(v5_dir)
    g6, g5 = _gate_numbers(res6, pts6, con6), _gate_numbers(res5, pts5, con5)
    m = v6_measures(v6_dir, bundles)
    kills_ok = all(x["pass"] for x in g6["kills"].values())
    k3_ok = g6["K3"] is not None and g5["K3"] is not None and g6["K3"] >= g5["K3"]
    gz6 = g6["GZ"][0] / g6["GZ"][1] if g6["GZ"][1] else 0.0
    gz5 = g5["GZ"][0] / g5["GZ"][1] if g5["GZ"][1] else 0.0
    gz_ok = gz6 <= gz5
    gd_ok = not m["G-D1"] and not m["G-D2"]
    v6_cost = m["cost_mean"].get("verifier", 0.0) + m["cost_mean"].get("explainer_a", 0.0)
    cost_ok = g5["cost_mean"] is not None and v6_cost < g5["cost_mean"]
    criteria = [("(1) kills hold", kills_ok), ("(2) G-D1 = G-D2 = 0", gd_ok),
                ("(3) K3 and G-Z no worse than v5", k3_ok and gz_ok),
                ("(4) cost per test below v5", cost_ok)]
    verdict = "PASS (1)–(4)" if all(ok for _, ok in criteria) else "NOT MET: " + ", ".join(
        n for n, ok in criteria if not ok)
    L = ["## CS eval (Phase 6, §13.2) — v6 vs the v5 production-pin baseline", "",
         f"**Verdict against ship criteria (1)–(4): {verdict}.** (5) is the Math/English smoke (Oct 7).", "",
         "| | criterion | met |", "|---|---|---|"]
    L += [f"| | {n} | {'✅' if ok else '❌'} |" for n, ok in criteria]
    L += ["", "### Kills and gates", "", "| | v6 | v5 baseline | bar |", "|---|---|---|---|"]
    for k in ("K1", "K2", "K4"):
        L.append(f"| {k} | {g6['kills'][k]['value']} {'✅' if g6['kills'][k]['pass'] else '❌'} | "
                 f"{g5['kills'][k]['value']} | {g6['kills'][k]['bar']} |")
    L.append(f"| K3 within-precision | {g6['K3']} | {g5['K3']} | ≥ v5 |")
    L.append(f"| G-Z GT-PARTIAL→AI-ZERO | {g6['GZ'][0]}/{g6['GZ'][1]} ({gz6:.1%}) | "
             f"{g5['GZ'][0]}/{g5['GZ'][1]} ({gz5:.1%}) | ≤ v5 |")
    L.append(f"| G-D1 double-charged cells in D | {len(m['G-D1'])} | — | 0 |")
    L.append(f"| G-D2 multi-tier charges in D | {len(m['G-D2'])} | — | 0 |")
    L.append(f"| G-B bounds_clamped | {len(m['G-B'])} | — | report all |")
    L.append(f"| valid trials | {g6['n_valid']}/{g6['n_trials']} | {g5['n_valid']}/{g5['n_trials']} | |")
    mf = res6["provenance"].get("model_fallback", {})
    L.append(f"| model_fallback (excluded) | {mf.get('trials', 0)} trials · "
             f"{m['model_fallback_scopes']} scopes | | AM-G18 |")
    L += ["", "### Cost per test (registry cards)", "",
          "| component | v6 mean $ | cache hit |", "|---|---|---|",
          f"| verifier (Sonnet 5.5) | {m['cost_mean'].get('verifier', 0):.4f} | {m['cache'].get('verifier', 0):.0%} |",
          f"| explainer arm A (Haiku 4.5) | {m['cost_mean'].get('explainer_a', 0):.4f} | {m['cache'].get('explainer_a', 0):.0%} |"]
    if arm_b:
        L.append(f"| explainer arm B (Sonnet 5.5, lowest) | {arm_b['cost_per_test']:.4f} | "
                 f"{arm_b.get('cache_hit', 0):.0%} |")
    L += [f"| **v6 total, arm A** | **{v6_cost:.4f}** | |",
          f"| v5 baseline (verifier, incl. basis_he) | {g5['cost_mean'] or 0:.4f} | |",
          "| aspirational target (AM-G11) | 0.1000 | |",
          "| student feedback | not run in the eval harness (reported at G3–5) | |", "",
          f"E-1..E-5: {m['e_pass'][0]}/{m['e_pass'][1]} lines passed "
          f"({m['e_pass'][0] / m['e_pass'][1]:.1%} — bar ≥ 98%); failed rules: {m['failed_rules'] or 'none'}."
          if m["e_pass"][1] else "E-1..E-5: no explainer lines.", ""]
    uw = _unwritten(res6)
    L += ["### Unwritten-ruling cells (reported apart, A-5)", ""] + [f"- {x}" for x in uw] + [""]
    for name in ("G-D1", "G-D2", "G-B"):
        if m[name]:
            L += [f"### {name} cells", ""] + [f"- {x}" for x in m[name]] + [""]
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("v6_run")
    ap.add_argument("v5_run")
    ap.add_argument("--arm-b", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    arm_b = json.loads(Path(a.arm_b).read_text(encoding="utf-8")) if a.arm_b else None
    text = render(Path(a.v6_run), Path(a.v5_run), arm_b)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
