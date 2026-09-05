"""
A0 — the compiler-only acceptance (PR_plan_compiler_v2.md §7). ZERO SPEND.

    python tests/grading_eval_suite/tools/compile_plan.py            # both exams
    python tests/grading_eval_suite/tools/compile_plan.py --exam hobby_tvshow

Per exam, Stages 0/1/3 run with the slot's own span standing in for wording:

  1. compile the contract → PlanSkeleton (pure)
  2. assemble the placeholder GradingPlan → the REAL validator (V1–V12, V9 against
     the scope corpora, V10 point-blindness) — zero errors or A0 fails
  3. every ratified GT judgment on an ATTEMPTED scope (R-2 reader) must be
     reachable under the plan algebra; each miss is CLASSIFIED:
        routed         the terminal is a C7 monolith — A2 (the router) closes it (OD-13)
        granularity    the award is below the plan's finest positive step — OD-12's
                       class, the partial_fraction floor, deferred by design
        decomposition  the award sits between two reachable values above the finest
                       step — a different split would reach it: a COMPILER finding
  4. the PR's named outcomes are checked by name (tariffs, notes, counted, Case 3,
     Case 4, OD-10, OD-11) and printed ✓/✗

Artefacts (append-only, provenance-stamped, no timestamps so re-runs are
byte-identical): plans/compiled/<exam>.plan.json · <exam>.skeleton.json ·
<exam>.meta.json, and app/agents/plan_gen/A0_REPORT.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Tuple

SUITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SUITE.parents[1]))

from app.agents.grader.plan_validator import validate_plan                    # noqa: E402
from app.agents.plan_compiler import compile_contract                         # noqa: E402
from app.agents.plan_compiler.assemble import assemble_placeholder_plan       # noqa: E402
from app.agents.plan_compiler.stage0 import contract_scopes, terminals_of     # noqa: E402
from app.agents.plan_gen.prompt import scope_corpus                           # noqa: E402
from tests.grading_eval_suite.fixtures import load_bundle, read_gt_judgments  # noqa: E402
from tests.grading_eval_suite.plan_expressibility import reachable_awards     # noqa: E402

OUT_DIR = SUITE / "plans" / "compiled"
REPORT = SUITE.parents[1] / "app" / "agents" / "plan_gen" / "A0_REPORT.md"

# The PR's named outcomes (§7), checked by name.
EXPECTED = {
    "hobby_tvshow": dict(tariffs=12, notes=1, counted=0, bar=189, gt=190,
                         routed_pr={"q1.א.c0", "q1.א.c1", "q2.א.c0", "q2.א.c1"}),
    "bagrut_899371": dict(tariffs=10, notes=2, counted=1, bar=295, gt=298,
                          routed_pr={"q2.א.c4", "q2.ב.c3", "q3.ב.c4", "q4.א.c1",
                                     "q5.א.c1", "q5.ב.c2", "q6.c8"}),
}


def discover_exams() -> Dict[str, List[str]]:
    """exam_id → fixture names, from the manifests themselves (no second registry)."""
    exams: Dict[str, List[str]] = defaultdict(list)
    for p in sorted((SUITE / "fixtures").glob("*.json")):
        m = json.loads(p.read_text(encoding="utf-8"))
        exams[m["exam_id"]].append(p.stem)
    return dict(exams)


def _json_default(o):
    if isinstance(o, Decimal):
        return str(o)
    raise TypeError(type(o))


def classify(t, award: Decimal, reach, ruling_terminals) -> str:
    """routed        C7 monolith — A2 closes it (OD-13)
    ruling        the hand plan reaches it only through an owner RULING (no text)
    granularity-floor   below the plan's finest positive step (OD-12's class)
    granularity-ladder  P × k/4 — a finer partial_fraction on the SAME structure
    decomposition       none of the above: a different split would reach it"""
    if t.routed:
        return "routed"
    if t.terminal_id in ruling_terminals:
        return "ruling"
    positives = sorted(v for v in reach if v > 0)
    if positives and award < positives[0]:
        return "granularity-floor"
    if any(award == t.points_possible * Decimal(k) / Decimal(4) for k in (1, 2, 3)):
        return "granularity-ladder"
    return "decomposition"


def run_exam(exam: str, fixtures: List[str]) -> dict:
    b0 = load_bundle(fixtures[0], require_gt=False)
    manifest = json.loads((SUITE / "fixtures" / f"{fixtures[0]}.json").read_text(encoding="utf-8"))
    contract_path = SUITE / manifest["rubric_contract"]
    sha = hashlib.sha256(contract_path.read_bytes()).hexdigest()
    contract = b0.rubric_contract
    precision = Decimal(str(contract.numeric_policy.precision))

    skeleton = compile_contract(contract, exam_id=exam, rubric_contract_sha256=sha)
    plan = assemble_placeholder_plan(skeleton)

    # ── the real validator ────────────────────────────────────────────────
    points, scopes, corpora = {}, {}, {}
    for key, q, sub in contract_scopes(contract):
        lbl = f"{key[0]}.{key[1]}" if key[1] else key[0]
        corpora[lbl] = scope_corpus(q, sub)
        for tid, pts in terminals_of(sub or q):
            points[tid] = pts
            scopes[tid] = lbl
    errors = validate_plan(plan, contract_terminal_points=points, terminal_scopes=scopes,
                           precision=precision, scope_corpora=corpora)

    # ── expressibility, every attempted judgment ─────────────────────────
    ruling_terminals = set()
    hand_path = SUITE / "plans" / f"{exam}.plan.json"
    if hand_path.exists():
        from app.agents.grader.plan_schemas import GradingPlan
        hand = GradingPlan.model_validate_json(hand_path.read_text(encoding="utf-8"))
        ruling_terminals = {t.terminal_id for t in hand.terminals
                            if any(c.source == "ruling" for c in t.checks)}
    by_tid = {t.terminal_id: t for t in skeleton.terminals}
    plan_by = {t.terminal_id: t for t in plan.terminals}
    total = 0
    misses: List[dict] = []
    per_fixture: Dict[str, Tuple[int, int]] = {}
    routed_judgments = 0
    for name in fixtures:
        _bundle, judgments = read_gt_judgments(name)
        ok = 0
        for tid, award in judgments:
            total += 1
            if by_tid[tid].routed:
                routed_judgments += 1
            reach = reachable_awards(plan_by[tid], precision)
            if award in reach:
                ok += 1
            else:
                misses.append(dict(fixture=name, terminal=tid, award=str(award),
                                   cls=classify(by_tid[tid], award, reach, ruling_terminals),
                                   reachable=sorted(str(v) for v in reach)))
        per_fixture[name] = (ok, len(judgments))

    # ── named outcomes ────────────────────────────────────────────────────
    slots = [s for t in skeleton.terminals for s in t.slots]
    kinds = Counter(s.kind for s in slots)
    routed = {t.terminal_id for t in skeleton.terminals if t.routed}
    exp = EXPECTED[exam]
    flag_counts = Counter(f.code for f in skeleton.all_flags)
    detected = (kinds.get("tariff", 0) + flag_counts["tariff_folded_into_component"]
                + flag_counts["tariff_reclassified_as_value"] + flag_counts["deduction_verb_only"])
    named = {
        f"tariff phrases detected ≥ {exp['tariffs']}": (detected, exp["tariffs"]),
        "tariff slots after dispositions (folded / value / verb-only)": (
            (kinds.get("tariff", 0), flag_counts["tariff_folded_into_component"],
             flag_counts["tariff_reclassified_as_value"], flag_counts["deduction_verb_only"]),
            "informational"),
        f"notes {exp['notes']}": (kinds.get("note_only", 0), exp["notes"]),
        f"counted {exp['counted']}": (kinds.get("counted", 0), exp["counted"]),
    }
    if exam == "bagrut_899371":
        c4 = [str(s.points) for s in by_tid["q4.ב.c4"].earn_slots]
        c7 = [str(s.points) for s in by_tid["q4.ב.c7"].earn_slots]
        c6 = [str(s.tariff_amount) for s in by_tid["q6.c6"].tariff_slots]
        named["Case 3 q4.ב.c4 → (1,2,1,1)"] = (c4, ["1", "2", "1", "1"])
        named["Case 3 q4.ב.c7 → (0.5,0.5,2,1,1)"] = (c7, ["0.5", "0.5", "2", "1", "1"])
        named["Case 4 q6.c6 → 1"] = (c6, ["1"])
    if exam == "hobby_tvshow":
        s3 = by_tid["q2.ב.c4.s3"]
        named["OD-10 q2.ב.c4 tariff 3 on the first child that can carry it (s3) + group"] = (
            [(str(s.tariff_amount), bool(s.charge_group)) for s in s3.tariff_slots], [("3", True)])
    named[f"OD-11 routed set == PR list"] = (sorted(routed), sorted(exp["routed_pr"]))

    cls_counts = Counter(m["cls"] for m in misses)

    # ── OD-24 counterfactual: OD-11's threshold at 3 instead of 4 ──────────
    # Reported, never applied: the compiled artefacts above are the ratified rule.
    cf = compile_contract(contract, exam_id=exam, rubric_contract_sha256=sha,
                          route_min_points=Decimal("3"))
    cf_by = {t.terminal_id: t for t in cf.terminals}
    cf_counts: Counter = Counter()
    for m in misses:
        t = cf_by[m["terminal"]]
        cf_counts["routed" if t.routed else m["cls"]] += 1
    counterfactual = dict(route_min_points="3", miss_classes=dict(cf_counts),
                          routed=sorted(t.terminal_id for t in cf.terminals if t.routed))

    result = dict(
        exam=exam, fixtures=fixtures, contract_sha256=sha, precision=str(precision),
        compiler_version=skeleton.compiler_version, plan_version=plan.plan_version,
        terminals=len(skeleton.terminals), slots=len(slots), kinds=dict(kinds),
        validator_errors=errors, expressible=total - len(misses), gt_total=total,
        routed_judgments=routed_judgments,
        bar=exp["bar"], misses=misses, miss_classes=dict(cls_counts),
        per_fixture=per_fixture, routed=sorted(routed), named=named,
        counterfactual=counterfactual,
        flags=[asdict(f) for f in skeleton.all_flags],
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{exam}.plan.json").write_text(
        json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT_DIR / f"{exam}.skeleton.json").write_text(
        json.dumps(asdict(skeleton), ensure_ascii=False, indent=1, default=_json_default),
        encoding="utf-8")
    meta = {k: v for k, v in result.items() if k not in ("flags", "misses", "named")}
    meta["misses"] = misses
    (OUT_DIR / f"{exam}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1, default=_json_default), encoding="utf-8")
    return result


def _fmt_named(named: dict) -> List[str]:
    rows = []
    for label, (got, want) in named.items():
        if want == "informational":
            mark = "·"
        elif label.startswith("tariff phrases detected"):
            mark = "✓" if got >= want else "✗"
        else:
            mark = "✓" if got == want else "✗"
        rows.append(f"| {label} | `{got}` | `{want}` | {mark} |")
    return rows


def _verdict(r: dict) -> List[str]:
    """Computed, not asserted: the bar as the PR states it, then the classes."""
    L: List[str] = []
    cls = r["miss_classes"]
    accepted = cls.get("routed", 0) + cls.get("ruling", 0)          # OD-13 · PR §7 exemption
    granularity = cls.get("granularity-floor", 0) + cls.get("granularity-ladder", 0)   # OD-12
    decomposition = cls.get("decomposition", 0)
    non_routed_total = r["gt_total"] - sum(1 for m in r["misses"] if m["cls"] == "routed") \
        - r["routed_judgments"]
    L.append(f"- Ratified bar: **≥{r['bar']}/{r['gt_total']}**, every miss granularity-class. "
             f"Measured: **{r['expressible']}/{r['gt_total']}**.")
    L.append(f"- Routed-class misses (OD-13, closed by A2): {cls.get('routed', 0)} · "
             f"owner-ruling misses (PR §7 exempt): {cls.get('ruling', 0)} · "
             f"granularity (OD-12, expected): {granularity} · "
             f"**decomposition: {decomposition}**.")
    L.append(f"- Non-routed judgments: {non_routed_total}; of them expressible "
             f"{non_routed_total - (len(r['misses']) - cls.get('routed', 0))}.")
    if decomposition == 0:
        L.append("- **A0 verdict: GREEN** on the compiler's own class — no decomposition-class miss.")
    else:
        L.append(f"- **A0 verdict: NOT GREEN as ratified** — {decomposition} decomposition-class "
                 f"miss(es); see the classified table and the OD-24 counterfactual below.")
    cf = r["counterfactual"]
    L.append(f"- OD-24 counterfactual (OD-11 threshold at P ≥ {cf['route_min_points']}, "
             f"REPORTED not applied): misses would classify as `{cf['miss_classes']}`; "
             f"routed set would be {len(cf['routed'])} terminals.")
    return L


def write_report(results: List[dict]) -> None:
    L: List[str] = []
    L.append("# A0 — compiler-only acceptance (zero spend)")
    L.append("")
    L.append("Generated by `tests/grading_eval_suite/tools/compile_plan.py` — Stages 0/1/3 of "
             "PLAN COMPILER v2 with every slot's own span standing in for wording. "
             "Measures the ALGEBRA alone (PR §7 A0). Re-running is byte-identical. "
             "The standing guard `tests/grading_eval_suite/test_compiled_plan_guard.py` pins "
             "every number here.")
    L.append("")
    L.append("Miss classes: `routed` — a C7 monolith, A2 closes it (OD-13) · `ruling` — the hand "
             "plan reaches it only through an owner ruling that cites no text (PR §7 exempts one) · "
             "`granularity-floor` — below the plan's finest positive step (OD-12's class) · "
             "`granularity-ladder` — P×k/4, a finer partial_fraction on the same structure · "
             "`decomposition` — a different split would reach it: the compiler's own class.")
    L.append("")
    L.append("## Scorecard")
    L.append("")
    L.append("| exam | compiler | terminals | slots | kinds | validator | expressible | bar | misses by class |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for r in results:
        L.append(f"| {r['exam']} | `{r['compiler_version']}` | {r['terminals']} | {r['slots']} | "
                 f"`{r['kinds']}` | {len(r['validator_errors'])} errors | "
                 f"**{r['expressible']}/{r['gt_total']}** | ≥{r['bar']} | `{r['miss_classes']}` |")
    L.append("")
    for r in results:
        L.append(f"## {r['exam']}")
        L.append("")
        L.append(f"plan `{r['plan_version']}` · contract sha256 `{r['contract_sha256'][:12]}…` · "
                 f"precision {r['precision']}")
        L.append("")
        L.append("### Verdict")
        L.append("")
        L.extend(_verdict(r))
        L.append("")
        L.append("### Named outcomes (PR §7)")
        L.append("")
        L.append("| outcome | got | expected | |")
        L.append("|---|---|---|---|")
        L.extend(_fmt_named(r["named"]))
        L.append("")
        L.append("### Per fixture")
        L.append("")
        L.append("| fixture | expressible |")
        L.append("|---|---|")
        for name, (ok, n) in r["per_fixture"].items():
            L.append(f"| {name} | {ok}/{n} |")
        L.append("")
        if r["validator_errors"]:
            L.append("### Validator errors")
            L.append("")
            for e in r["validator_errors"]:
                L.append(f"- `{e}`")
            L.append("")
        L.append(f"### Every miss ({len(r['misses'])}), classified")
        L.append("")
        if r["misses"]:
            L.append("| fixture | terminal | award | class | reachable |")
            L.append("|---|---|---|---|---|")
            for m in r["misses"]:
                L.append(f"| {m['fixture']} | {m['terminal']} | {m['award']} | **{m['cls']}** | "
                         f"`{', '.join(m['reachable'])}` |")
        else:
            L.append("none")
        L.append("")
        L.append(f"### Routed (C7): {len(r['routed'])}")
        L.append("")
        L.append(", ".join(f"`{t}`" for t in r["routed"]) or "none")
        L.append("")
        L.append(f"### Every flag ({len(r['flags'])})")
        L.append("")
        by_code = Counter(f["code"] for f in r["flags"])
        L.append("| code | count |")
        L.append("|---|---|")
        for code, n in sorted(by_code.items(), key=lambda kv: -kv[1]):
            L.append(f"| `{code}` | {n} |")
        L.append("")
        L.append("<details><summary>flag detail</summary>")
        L.append("")
        for f in r["flags"]:
            L.append(f"- `{f['code']}` **{f['terminal_id']}** — {f['detail']}")
        L.append("")
        L.append("</details>")
        L.append("")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exam", default=None)
    args = ap.parse_args()
    exams = discover_exams()
    todo = [args.exam] if args.exam else list(exams)
    results = []
    for exam in todo:
        r = run_exam(exam, exams[exam])
        results.append(r)
        print(f"\n===== A0 · {exam} =====")
        print(f"  terminals {r['terminals']} · slots {r['slots']} · kinds {r['kinds']}")
        print(f"  VALIDATOR errors: {len(r['validator_errors'])}")
        for e in r["validator_errors"][:12]:
            print(f"     {e[:160]}")
        print(f"  EXPRESSIBLE: {r['expressible']}/{r['gt_total']} (bar ≥{r['bar']}) · "
              f"misses {r['miss_classes']}")
        for m in r["misses"]:
            print(f"     {m['cls']:13s} {m['fixture']}/{m['terminal']} award {m['award']} "
                  f"reachable {m['reachable']}")
        for row in _fmt_named(r["named"]):
            print("  " + row)
    if not args.exam:
        write_report(results)
        print(f"\nreport → {REPORT.relative_to(SUITE.parents[1])}")


if __name__ == "__main__":
    main()
