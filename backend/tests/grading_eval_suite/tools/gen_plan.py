"""
Phase 0 — generate plan variants from a compiled contract, then run 0a.

0a is the PRE-SPEND gate: full validation + expressibility over the ratified GT.
A plan that cannot express the teacher's award will not reproduce it on any
model at any k, so the A/B is not attempted until this clears.

Usage:
    python -m tests.grading_eval_suite.tools.gen_plan --variant rubric
    python -m tests.grading_eval_suite.tools.gen_plan --variant const
    python -m tests.grading_eval_suite.tools.gen_plan --variant nosol
    python -m tests.grading_eval_suite.tools.gen_plan --score-only
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import re
import sys
import unicodedata
from collections import Counter
from decimal import Decimal
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SUITE.parents[1]))

from app.agents.grader.plan_schemas import GradingPlan          # noqa: E402
from app.agents.grader.plan_validator import validate_plan      # noqa: E402
from app.agents.plan_gen.generator import PlanGenerator         # noqa: E402
from app.agents.plan_gen.schemas import ScopeDecomposition      # noqa: E402
from tests.grading_eval_suite.fixtures import load_bundle       # noqa: E402
from tests.grading_eval_suite.plan_expressibility import (      # noqa: E402
    expressibility_errors)

FIXTURES = ["dan_basiuk", "din_ezra", "moran_aharon", "omer_gelber",
            "yonatan_basiuk"]
OUT = SUITE / "plans" / "generated"
GEN_MODEL = ("anthropic", "claude-opus-5")      # top tier — the plan is the ceiling
HAND = SUITE / "plans" / "hobby_tvshow.plan.json"

VARIANTS = {
    "rubric": dict(include_constitution=False, include_solution=True),
    "const":  dict(include_constitution=True,  include_solution=True),
    "nosol":  dict(include_constitution=True,  include_solution=False),
}


async def generate(variant: str) -> None:
    from app.agents.grader.llm_factory import build_chat_model

    cfg = VARIANTS[variant]
    bundle = load_bundle(FIXTURES[0])
    llm = build_chat_model(*GEN_MODEL).with_structured_output(
        ScopeDecomposition, include_raw=True)

    gen = PlanGenerator(llm, plan_version=f"generated-{variant}/v1", **cfg)
    plan, meta = await gen.generate(bundle.rubric_contract,
                                    exam_id="hobby_tvshow")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{variant}.plan.json").write_text(
        plan.model_dump_json(indent=1), encoding="utf-8")
    (OUT / f"{variant}.meta.json").write_text(
        json.dumps({k: v for k, v in meta.items() if k != "scope_corpora"},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    u = meta["usage"]
    cost = u["input_tokens"] / 1e6 * 15 + u["output_tokens"] / 1e6 * 75
    print(f"[{variant}] {u['calls']} calls  in={u['input_tokens']} "
          f"out={u['output_tokens']}  ~${cost:.2f}  repairs={meta['repairs']}")


def _tight(t: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", t or ""))


def score(path: Path, label: str) -> dict:
    """0a — validation + expressibility, plus the structural comparison."""
    plan = GradingPlan.model_validate_json(path.read_text(encoding="utf-8"))
    bundle = load_bundle(FIXTURES[0])
    contract = bundle.rubric_contract

    from app.agents.plan_gen.generator import contract_scopes, terminals_of
    from app.agents.plan_gen.prompt import scope_corpus

    points, scopes, corpora = {}, {}, {}
    for key, q, sub in contract_scopes(contract):
        lbl = f"{key[0]}.{key[1]}" if key[1] else key[0]
        corpora[lbl] = scope_corpus(q, sub)
        for tid, pts in terminals_of(sub or q):
            points[tid] = pts
            scopes[tid] = lbl

    errors = validate_plan(plan, contract_terminal_points=points,
                           terminal_scopes=scopes,
                           precision=contract.numeric_policy.precision,
                           scope_corpora=corpora)

    total = expr_bad = 0
    misses = []
    for name in FIXTURES:
        b = load_bundle(name)
        total += len(b.gt.terminals)
        errs = expressibility_errors(plan, b.gt, b.terminal_infos,
                                     contract.numeric_policy.precision)
        expr_bad += len(errs)
        misses.extend(errs)

    checks = [c for t in plan.terminals for c in t.checks]
    kinds = Counter(c.kind for c in checks)
    per_terminal = Counter(len(t.checks) for t in plan.terminals)

    print(f"\n===== 0a · {label} =====")
    print(f"  terminals {len(plan.terminals)} · checks {len(checks)} · "
          f"avg {len(checks)/max(len(plan.terminals),1):.1f}/terminal")
    print(f"  kinds {dict(kinds)} · equivalence_notes "
          f"{sum(1 for c in checks if c.equivalence_note)} · charge_groups "
          f"{sum(1 for c in checks if c.charge_group)}")
    print(f"  checks/terminal {sorted(per_terminal.items())}")
    print(f"  VALIDATOR errors: {len(errors)}")
    for e in errors[:8]:
        print(f"     {e}")
    print(f"  EXPRESSIBILITY: {total - expr_bad}/{total}")
    for m in misses[:8]:
        print(f"     {m[:150]}")
    return {"label": label, "checks": len(checks), "kinds": dict(kinds),
            "validator_errors": len(errors), "expressible": total - expr_bad,
            "gt_total": total, "misses": misses,
            "tariffs": kinds.get("tariff", 0),
            "note_only": kinds.get("note_only", 0),
            "equivalence_notes": sum(1 for c in checks if c.equivalence_note)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=sorted(VARIANTS))
    ap.add_argument("--score-only", action="store_true")
    args = ap.parse_args()

    if args.variant and not args.score_only:
        asyncio.run(generate(args.variant))
        score(OUT / f"{args.variant}.plan.json", args.variant)
        return

    OUT.mkdir(parents=True, exist_ok=True)
    rows = [score(HAND, "hand (reference)")]
    for v in sorted(VARIANTS):
        p = OUT / f"{v}.plan.json"
        if p.exists():
            rows.append(score(p, v))
    (OUT / "0a_summary.json").write_text(
        json.dumps([{k: v for k, v in r.items() if k != "misses"} for r in rows],
                   ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
