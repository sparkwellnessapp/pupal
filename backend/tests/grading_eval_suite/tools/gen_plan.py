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

# [two-exam prep] The corpus is a REGISTRY, not a literal. Exam 2 is a data
# drop: add its entry, and every consumer below resolves plans, corpora and
# GT per exam without a refactor.
EXAMS = {
    "hobby_tvshow": ["dan_basiuk", "din_ezra", "moran_aharon",
                     "omer_gelber", "yonatan_basiuk"],
    # [exam 2] Fixture names are EXAM-NAMESPACED because din_ezra sat both
    # papers and the hobby fixture already owns the bare name and a ratified GT.
    "bagrut_899371": [f"bagrut_899371.{s}" for s in
                      ["din_ezra", "itay_kraft", "noam_breinshtein", "raz_cohen",
                       "roni_ben_ezra", "yael_kogan", "yahli_cohen"]],
}
DEFAULT_EXAM = "hobby_tvshow"
FIXTURES = EXAMS[DEFAULT_EXAM]
OUT = SUITE / "plans" / "generated"
GEN_MODEL = ("anthropic", "claude-opus-5")      # top tier — the plan is the ceiling
# WHY THERE IS NO TIMEOUT OVERRIDE HERE, after one was added and removed:
# a 13-scope run died on APITimeoutError and the first diagnosis was "240s is
# too short for plan-gen". MEASURED, that is not supported — hobby's const run
# is 15 calls for 37.6K output tokens, i.e. ~2.5K output per call, comfortably
# under a minute on opus-5. Raising the ceiling to 900s treated a symptom nobody
# measured and made the bound WORSE: a genuinely hung call would then sit for
# fifteen minutes (PR-2 watched one unbounded attempt run 1736s).
#
# The real defect is that plan-gen inherits HALF of PR-2's discipline. Its
# factory sets max_retries=0 — deliberately, so the SDK cannot hide retries —
# but nothing supplies the one owned retry layer PR-2 pairs that with. So a
# single dropped connection is fatal, and with no per-scope persistence it was
# fatal to twelve other scopes that had already been paid for.
MAX_RUN_ATTEMPTS = 3            # transient transport only; resumes from cache
def hand_plan_for(exam: str):
    return SUITE / "plans" / f"{exam}.plan.json"


def generated_plan_for(exam: str, variant: str):
    return OUT / (f"{variant}.plan.json" if exam == DEFAULT_EXAM
                  else f"{exam}.{variant}.plan.json")


HAND = hand_plan_for(DEFAULT_EXAM)

VARIANTS = {
    "rubric": dict(include_constitution=False, include_solution=True),
    "const":  dict(include_constitution=True,  include_solution=True),
    "nosol":  dict(include_constitution=True,  include_solution=False),
    # SAME-ARM CONTROL (mandatory, owner 2026-09-01): byte-identical
    # inputs to `const`. The only way to separate clause-leak from
    # run-to-run stochasticity — the stop condition cannot be ruled
    # on without it.
    "const2": dict(include_constitution=True,  include_solution=True),
}


async def generate(variant: str, exam: str = DEFAULT_EXAM) -> None:
    from app.agents.grader.llm_factory import build_chat_model

    cfg = VARIANTS[variant]
    # GT is not needed to GENERATE — the plan is a function of the contract
    # alone. Requiring it would block exam 2 on an authoring session that this
    # step exists to unblock.
    bundle = load_bundle(EXAMS[exam][0], require_gt=False)
    llm = build_chat_model(*GEN_MODEL).with_structured_output(
        ScopeDecomposition, include_raw=True)

    # PER-SCOPE CACHE. A sequential 13-scope run that assembles only at the end
    # is all-or-nothing, and one timeout already threw away a paid-for run. Each
    # scope is written as it lands; a retry resumes and pays only for the gap.
    cache_path = OUT / f"{exam}.{variant}.scopes.json"
    cache: dict = {}
    if cache_path.exists():
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
        from app.agents.grader.plan_schemas import TerminalPlan
        cache = {k: [TerminalPlan.model_validate(t) for t in v]
                 for k, v in raw.items()}
        print(f"[resume] {len(cache)} scope(s) cached — not re-generating them")

    def _persist(label, terminals):
        cache[label] = terminals
        OUT.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(
            {k: [json.loads(t.model_dump_json()) for t in v]
             for k, v in cache.items()}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        print(f"[scope] {label}: {len(terminals)} terminal(s) cached")

    gen = PlanGenerator(llm, plan_version=f"generated-{variant}/v1", **cfg)

    # The retry lives HERE, not inside PlanGenerator, and it is bounded. Because
    # `resume` reads the cache each attempt, a transient failure costs ONE
    # scope's re-attempt rather than the whole run — which is the actual
    # protection; the retry just saves a manual re-invocation.
    for attempt in range(1, MAX_RUN_ATTEMPTS + 1):
        try:
            plan, meta = await gen.generate(bundle.rubric_contract, exam_id=exam,
                                            resume=cache, on_scope=_persist)
            break
        except Exception as exc:                       # noqa: BLE001
            if attempt == MAX_RUN_ATTEMPTS:
                raise
            print(f"[retry {attempt}/{MAX_RUN_ATTEMPTS - 1}] "
                  f"{type(exc).__name__}: {str(exc)[:120]} — "
                  f"{len(cache)} scope(s) already cached, resuming")

    # The plan the runner will hash-pin must carry the contract it was built
    # from, or _load_plan refuses it (D5). Stamped here, from the bundle's own
    # snapshot, so it can never name a contract nobody generated against.
    plan = plan.model_copy(
        update={"rubric_contract_sha256": bundle.rubric_contract_hash or ""})

    OUT.mkdir(parents=True, exist_ok=True)
    generated_plan_for(exam, variant).write_text(
        plan.model_dump_json(indent=1), encoding="utf-8")
    meta_name = generated_plan_for(exam, variant).name.replace(".plan.json", ".meta.json")
    (OUT / meta_name).write_text(
        json.dumps({k: v for k, v in meta.items() if k != "scope_corpora"},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    u = meta["usage"]
    cost = u["input_tokens"] / 1e6 * 15 + u["output_tokens"] / 1e6 * 75
    print(f"[{variant}] {u['calls']} calls  in={u['input_tokens']} "
          f"out={u['output_tokens']}  ~${cost:.2f}  repairs={meta['repairs']}")


def _tight(t: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", t or ""))


def score(path: Path, label: str, exam: str = DEFAULT_EXAM) -> dict:
    """0a — validation + expressibility, plus the structural comparison."""
    plan = GradingPlan.model_validate_json(path.read_text(encoding="utf-8"))
    fixtures = EXAMS[exam]
    bundle = load_bundle(fixtures[0], require_gt=False)
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
    for name in fixtures:
        try:
            b = load_bundle(name)
        except Exception as exc:            # GT not authored yet
            print(f"  [expressibility] {name}: SKIPPED — {type(exc).__name__}")
            continue
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
    ap.add_argument("--exam", default=DEFAULT_EXAM, choices=sorted(EXAMS))
    args = ap.parse_args()

    if args.variant and not args.score_only:
        asyncio.run(generate(args.variant, args.exam))
        score(generated_plan_for(args.exam, args.variant), args.variant, args.exam)
        return

    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    hand = hand_plan_for(args.exam)
    if hand.exists():
        rows.append(score(hand, "hand (reference)", args.exam))
    for v in sorted(VARIANTS):
        p = generated_plan_for(args.exam, v)
        if p.exists():
            rows.append(score(p, v, args.exam))
    (OUT / "0a_summary.json").write_text(
        json.dumps([{k: v for k, v in r.items() if k != "misses"} for r in rows],
                   ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
