"""
grader-v6 G2 — LIVE compiles of the fixture rubrics (PR_grader_v6_options.md §12, Phase 2).

    python tests/grading_eval_suite/tools/plan_v6.py --exam hobby_tvshow --dry-run
    python tests/grading_eval_suite/tools/plan_v6.py --exam bagrut_899371 --confirm-spend
    python tests/grading_eval_suite/tools/plan_v6.py --exam hobby_tvshow --replay   # $0, recorded

Per exam: Stage 1 → the planner (Sonnet 5, adaptive, effort high — PREDICTIONS.md
«GRADER v6 — model & effort pre-registration») one call per scope that needs language,
≤ 1 repair, else the fallback → assembly → validators → the plan hash.

Writes (committed as the G2 evidence and the recorded fixtures offline tests replay):
  plans/v6/<exam>.recorded.json   per scope: origin, raw outputs, usage, validator messages
  plans/v6/<exam>.plan.json       the assembled GradingPlanV6
  docs/plans/<exam>_v6_render.md  the REVIEW-2 render

Standing rules: a one-token credit canary before any spend (after-AM-G13 ruling); a
hard per-exam cap (`--max-usd`, default $3; the watch value is $2 per rubric) — a scope
never STARTS once the running total has reached it, and the untouched scopes are
reported, not silently dropped.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND))

from app.agents.grader import plan_values as pv                                     # noqa: E402
from app.agents.grader.plan_schemas import PackRef                                  # noqa: E402
from app.agents.plan_compiler.stage1_v6 import STAGE1_V6_VERSION, compile_stage1_v6  # noqa: E402
from app.agents.planner.planner import (ScopePlanResult, assemble_plan,             # noqa: E402
                                        plan_scope)
from app.agents.planner.prompt import (PLANNER_PROMPT_VERSION, planner_system_prompt,  # noqa: E402
                                       render_scope_input)
from app.agents.planner.render import render_plan_md                                # noqa: E402
from app.agents.planner.schemas import ScopePlanOutput                              # noqa: E402
from app.agents.planner.stage1_input import scope_planner_input                     # noqa: E402
from app.subjects.registry import get_profile                                       # noqa: E402
from tests.grading_eval_suite.fixtures import SUITE_DIR, load_bundle                # noqa: E402

EXAMS = {"hobby_tvshow": "din_ezra", "bagrut_899371": "bagrut_899371.din_ezra"}
SUBJECT = {"hobby_tvshow": "computer_science", "bagrut_899371": "computer_science"}
OUT_DIR = SUITE_DIR / "plans" / "v6"
RENDER_DIR = BACKEND.parent / "docs" / "plans"


def _canary() -> None:
    """One token to the planner's provider before any spend; refuses on failure."""
    import anthropic
    from app.config import settings
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key.get_secret_value())
    try:
        client.messages.create(model="claude-sonnet-5", max_tokens=1,
                               messages=[{"role": "user", "content": "ok"}])
    except anthropic.APIStatusError as e:
        raise SystemExit(f"credit canary FAILED ({e.status_code}) — no spend; offline work continues")
    print("credit canary: claude-sonnet-5 OK")


def _recorded_call(recorded: dict):
    async def call(system, user):
        scope = user.split("\n", 1)[0]
        raise RuntimeError(f"replay: no live call ({scope[:40]})")
    return call


async def _run(exam: str, *, live: bool, max_usd: float, replay: bool, live_scopes=()):
    bundle = load_bundle(EXAMS[exam], require_gt=False)
    contract = bundle.rubric_contract
    sha = hashlib.sha256(contract.model_dump_json().encode("utf-8")).hexdigest()
    s1 = compile_stage1_v6(contract, exam_id=exam, rubric_contract_sha256=sha)
    profile = get_profile(SUBJECT[exam])
    system = planner_system_prompt(profile)
    recorded_path = OUT_DIR / f"{exam}.recorded.json"

    live_scopes = set(live_scopes)
    if replay or live_scopes:
        rec = json.loads(recorded_path.read_text(encoding="utf-8"))
        outputs = {s: [ScopePlanOutput.model_validate(o) for o in r["outputs"]]
                   for s, r in rec["scopes"].items()}

        prior_usage = {s: r.get("usage", []) for s, r in rec["scopes"].items()}
        live_call = None
        if live_scopes:
            from app.agents.planner.planner_llm import build_planner_call
            live_call = build_planner_call()

        def call_for(scope):
            if scope.scope in live_scopes:
                return live_call
            queue = list(outputs.get(scope.scope, []))
            usage = list(prior_usage.get(scope.scope, []))

            async def call(system_, user_):
                if not queue:
                    raise RuntimeError("replay exhausted")
                return queue.pop(0), (usage.pop(0) if usage else {})
            return call
    else:
        from app.agents.planner.planner_llm import build_planner_call
        live_call = build_planner_call() if live else None

        def call_for(scope):
            return live_call

    results, spent, skipped = [], 0.0, []
    t0 = time.monotonic()
    for scope in s1.scopes:                       # sequential: the cap is checked before each start
        if scope.needs_planner and not replay and spent >= max_usd:
            skipped.append(scope.scope)
            continue
        user = render_scope_input(scope_planner_input(scope))
        if not live and not replay and not live_scopes:
            print(f"  [dry] {scope.scope}: {'planner' if scope.needs_planner else 'compiled'} · "
                  f"system {len(system)} chars · user {len(user)} chars")
            continue
        r: ScopePlanResult = await plan_scope(scope, precision=s1.precision, system_prompt=system,
                                              user_message=user, call=call_for(scope))
        cost = sum(u.get("cost_usd", 0.0) for u in r.usage)
        spent += cost
        results.append(r)
        print(f"  {scope.scope}: {r.origin} · {len(r.usage)} call(s) · ${cost:.4f}"
              + (f" · {len(r.errors)} validator msg(s)" if r.errors else ""))
    if not live and not replay and not live_scopes:
        return
    wall = time.monotonic() - t0
    if skipped:
        print(f"  CAP ${max_usd} reached — scopes NOT planned: {skipped}")
        return
    config = pv.config_hash(compiler_version=STAGE1_V6_VERSION, planner_model="claude-sonnet-5",
                            planner_prompt_version=PLANNER_PROMPT_VERSION,
                            pack_id=profile.pack_id, pack_version=profile.pack_version)
    plan = assemble_plan(results, config_hash=config, rubric_contract_version=str(contract.contract_version),
                         pack=PackRef(pack_id=profile.pack_id, pack_version=profile.pack_version))
    origins = {o: sum(r.origin == o for r in results) for o in ("planner", "repaired", "fallback", "compiled")}
    print(f"== {exam}: ${spent:.4f} · wall {wall:.0f}s · origins {origins} · plan_hash {plan.plan_hash[:16]}")
    if replay and not live_scopes:
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    recorded_path.write_text(json.dumps({
        "exam": exam, "stage1_version": s1.version, "planner_prompt_version": PLANNER_PROMPT_VERSION,
        "config_hash": config, "plan_hash": plan.plan_hash, "cost_usd": round(spent, 4),
        "wall_s": round(wall, 1), "origins": origins,
        "scopes": {r.scope: {"origin": r.origin, "outputs": r.outputs, "usage": r.usage,
                             "errors": r.errors, "telemetry": r.telemetry} for r in results},
    }, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    (OUT_DIR / f"{exam}.plan.json").write_text(plan.model_dump_json(indent=1), encoding="utf-8")
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    (RENDER_DIR / f"{exam}_v6_render.md").write_text(
        render_plan_md(exam, plan, s1, results), encoding="utf-8")
    print(f"  wrote {recorded_path.name}, {exam}.plan.json, docs/plans/{exam}_v6_render.md")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exam", choices=sorted(EXAMS) + ["all"], default="all")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--confirm-spend", action="store_true")
    ap.add_argument("--replay", action="store_true")
    ap.add_argument("--max-usd", type=float, default=3.0)
    ap.add_argument("--live-scopes", default="",
                    help="comma-separated scopes to re-plan LIVE; every other scope replays its recording")
    args = ap.parse_args()
    live_scopes = [x for x in args.live_scopes.split(",") if x]
    if not (args.dry_run or args.confirm_spend or args.replay):
        raise SystemExit("pass --dry-run, --replay, or --confirm-spend (a live run spends money)")
    if live_scopes and not args.confirm_spend:
        raise SystemExit("--live-scopes spends money: add --confirm-spend")
    if args.confirm_spend:
        _canary()
    for exam in (sorted(EXAMS) if args.exam == "all" else [args.exam]):
        print(f"===== {exam} =====")
        asyncio.run(_run(exam, live=args.confirm_spend and not live_scopes, max_usd=args.max_usd,
                         replay=args.replay or bool(live_scopes), live_scopes=live_scopes))


if __name__ == "__main__":
    main()
