"""grader-v6 PLANNER RE-RECORD report (owner ruling 2026-09-30), per model, $0.

    python tests/grading_eval_suite/tools/planner_report.py

Reads every plans/v6/<exam>.<model>.recorded.json, REBUILDS each plan from its
recording (the same replay path the offline tests take: map → validate → fallback),
and reports per model and exam: repairs, fallbacks, validator messages, V19
candidates, expressibility against every GT cell (§13.1, priced by THE pricer),
cost, latency, and the served-model provenance (AM-G18). Then applies the §13.1
choice rule. Grading-eval kill/gate failures (rule step 2) do not exist before
Phase 6; when the first step ties within 1 cell, the report says so and applies
step 3 (cost), which the owner reviews at STOP-3.
"""
from __future__ import annotations

import asyncio
import json
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND))

from app.agents.grader import plan_values as pv                                     # noqa: E402
from app.agents.grader.plan_schemas import PackRef                                  # noqa: E402
from app.agents.grader.plan_validator_v6 import v19_fault_leak_candidates           # noqa: E402
from app.agents.plan_compiler.stage1_v6 import compile_stage1_v6                    # noqa: E402
from app.agents.planner.planner import assemble_plan, plan_scope                    # noqa: E402
from app.agents.planner.schemas import ScopePlanOutput                              # noqa: E402
from tests.grading_eval_suite.fixtures import SUITE_DIR, load_bundle, read_gt_judgments  # noqa: E402
from tests.grading_eval_suite.plan_v6_expressibility import (expressibility_v6,     # noqa: E402
                                                             plan_decision)
from tests.grading_eval_suite.tools.compile_plan import discover_exams              # noqa: E402

EXAMS = {"hobby_tvshow": "din_ezra", "bagrut_899371": "bagrut_899371.din_ezra"}
OUT_DIR = SUITE_DIR / "plans" / "v6"


async def _replay(exam: str, rec: dict):
    s1 = compile_stage1_v6(load_bundle(EXAMS[exam], require_gt=False).rubric_contract,
                           exam_id=exam, rubric_contract_sha256="x")
    results = []
    for scope in s1.scopes:
        r = rec["scopes"].get(scope.scope, {})
        queue = [ScopePlanOutput.model_validate(o) for o in r.get("outputs", [])]
        usage = list(r.get("usage", []))

        async def call(system_, user_, q=queue, u=usage):
            if not q:
                raise RuntimeError("replay exhausted")
            return q.pop(0), (u.pop(0) if u else {})

        results.append(await plan_scope(scope, precision=s1.precision, system_prompt="S",
                                        user_message="U", call=call))
    plan = assemble_plan(results, config_hash=rec["config_hash"], rubric_contract_version="x",
                         pack=PackRef(pack_id="computer_science", pack_version="v1"))
    return s1, results, plan


def main() -> None:
    exams = discover_exams()
    rows = defaultdict(dict)
    for path in sorted(OUT_DIR.glob("*.*.recorded.json")):
        exam, model = path.name[:-len(".recorded.json")].split(".", 1)
        rec = json.loads(path.read_text(encoding="utf-8"))
        s1, results, plan = asyncio.run(_replay(exam, rec))
        judgments = {n: read_gt_judgments(n)[1] for n in exams[exam]}
        total, misses = expressibility_v6(plan, judgments, s1.precision)
        v19 = sum(len(v19_fault_leak_candidates([c for c in plan.checks
                                                  if any(c.priced_terminal_id == t.terminal_id
                                                         for t in sc.terminals)],
                                                 list(sc.markers)))
                  for sc in s1.scopes)
        calls = [u for r in rec["scopes"].values() for u in r.get("usage", [])]
        rows[model][exam] = dict(
            origins=rec["origins"], replay_origins={o: sum(r.origin == o for r in results)
                                                    for o in ("planner", "repaired", "fallback", "compiled")},
            validator_msgs=sum(len(r.get("errors", [])) for r in rec["scopes"].values()),
            v19=v19, expressible=total - len(misses), total=total,
            planner_miss=sum(m.label == "planner_miss" for m in misses),
            unwritten=sum(m.label == "unwritten_ruling" for m in misses),
            misses=[(m, plan_decision(plan, m.terminal_id)) for m in misses],
            cost=rec["cost_usd"], wall=rec["wall_s"], calls=len(calls),
            out_tokens=sum(u.get("output_tokens", 0) for u in calls),
            served=rec.get("served_models"), model_fallback=rec.get("model_fallback_scopes", []),
            plan_hash=plan.plan_hash, recorded_hash=rec["plan_hash"],
            prompt=rec["planner_prompt_version"])

    L = ["# grader-v6 planner re-record — per-model report", ""]
    L.append("| model | exam | prompt | origins (planner/repaired/fallback/compiled) | validator msgs | V19 | "
             "expressible | planner miss | unwritten | $ | wall s | calls | out tok | served | fallback scopes |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for model, per in rows.items():
        for exam, r in per.items():
            o = r["origins"]
            L.append(f"| {model} | {exam} | {r['prompt']} | {o['planner']}/{o['repaired']}/{o['fallback']}/"
                     f"{o['compiled']} | {r['validator_msgs']} | {r['v19']} | **{r['expressible']}/{r['total']}** | "
                     f"{r['planner_miss']} | {r['unwritten']} | {r['cost']:.4f} | {r['wall']:.0f} | {r['calls']} | "
                     f"{r['out_tokens']} | {','.join(r['served'] or ['?'])} | {len(r['model_fallback'])} |")
            assert r["plan_hash"] == r["recorded_hash"], (model, exam, "replay does not reproduce the recording")
    L.append("")
    complete = {m: per for m, per in rows.items() if set(per) == set(EXAMS)}
    totals = {m: (sum(r["planner_miss"] + r["unwritten"] for r in per.values()),
                  sum(r["planner_miss"] for r in per.values()),
                  sum(r["cost"] for r in per.values())) for m, per in complete.items()}
    L.append("## §13.1 choice rule")
    for m in sorted(set(rows) - set(complete)):
        L.append(f"- {m}: INCOMPLETE ({sorted(rows[m])} recorded) — not compared")
    for m, (miss, pmiss, cost) in totals.items():
        L.append(f"- {m}: inexpressible {miss} (planner misses {pmiss}) · ${cost:.4f} for both exams")
    if len(totals) >= 2:
        ranked = sorted(totals.items(), key=lambda kv: kv[1][0])
        (a, (ma, _, ca)), (b, (mb, _, cb)) = ranked[0], ranked[1]
        if mb - ma > 1:
            L.append(f"- step 1: **{a}** (fewer inexpressible cells by {mb - ma})")
        else:
            winner = a if ca <= cb else b
            L.append(f"- step 1: within 1 cell ({ma} vs {mb}) → step 2 needs grading-eval kills/gates, "
                     f"which do not exist before Phase 6 → step 3 (cheaper): **{winner}** — for STOP-3")
    L.append("")
    for model, per in rows.items():
        for exam, r in per.items():
            if not r["misses"]:
                continue
            L.append(f"### {model} · {exam} — inexpressible cells")
            L.append("| fixture | terminal | GT | label | reachable | plan decision |")
            L.append("|---|---|---|---|---|---|")
            for m, dec in r["misses"]:
                L.append(f"| {m.fixture} | {m.terminal_id} | {m.award} | {m.label} | "
                         f"{', '.join(m.reachable) or 'capped'} | {dec} |")
            L.append("")
    text = "\n".join(L) + "\n"
    out = BACKEND.parent / "docs" / "plans" / "v6_planner_rerecord_report.md"
    out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
