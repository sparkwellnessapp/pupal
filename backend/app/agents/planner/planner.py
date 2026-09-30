"""
grader-v6 Stage 2 — PLAN (PR_grader_v6_options.md §5.5, §5.6): one call per scope
that needs language, one repair, then the deterministic fallback.

The model call is INJECTED (`LLMCall`): tests pass recorded outputs and the
LLM is never called in tests (G2). The live call — Sonnet 5, adaptive thinking,
effort `high` [Q-14], native json_schema structured output, one app-level retry
on transient transport errors only — is built by `planner_llm.py`, not here.

Per scope:
  1. the call; a call that fails (after its own transport retry) → fallback;
  2. map + validate (V12–V20); clean → origin "planner";
  3. otherwise ONE repair call: the same input, plus the prior output, plus the
     validator messages verbatim (§5.6 — the only content-level retry in the
     system, allowed because validation is deterministic and the repair input
     is exact); clean → origin "repaired";
  4. otherwise the fallback, `planner_fallback` telemetry with the reason.
A scope whose terminals are all compiled (C7) is assembled with no call.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Awaitable, Callable, Dict, List, Literal, Optional, Sequence, Tuple

from app.agents.grader import plan_values as pv
from app.agents.grader.plan_schemas import (GradingPlanV6, MarkerDisposition, PackRef, PlanCheckV6,
                                            TerminalPlanV6)
from app.agents.plan_compiler.stage1_v6 import Stage1V6, V6Scope

from .assemble import MappingError, fallback_scope, map_scope, validate_scope
from .schemas import ScopePlanOutput

PLANNER_MAX_CONCURRENCY = 6

# (system prompt, user message) -> (parsed output, usage dict). Raises on failure.
LLMCall = Callable[[str, str], Awaitable[Tuple[ScopePlanOutput, Dict[str, Any]]]]
Origin = Literal["planner", "repaired", "fallback", "compiled"]

REPAIR_HEADER = ("\n\n### תיקון נדרש\n"
                 "הפלט הקודם שלך נדחה על ידי הבודק. החזר את התוכנית כולה מחדש, מתוקנת, "
                 "באותו מבנה. אלה ההודעות של הבודק, מילה במילה:\n")
PRIOR_HEADER = "\n\n### הפלט הקודם שלך\n"


@dataclass
class ScopePlanResult:
    scope: str
    origin: Origin
    terminals: List[TerminalPlanV6]
    checks: List[PlanCheckV6]
    dispositions: List[MarkerDisposition]
    telemetry: List[str] = field(default_factory=list)
    outputs: List[Dict[str, Any]] = field(default_factory=list)     # raw outputs, for recorded fixtures
    usage: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)                 # what sent it to repair / fallback

    @property
    def model_fallback(self) -> bool:
        """[AM-G18] a call was served by another model than requested; eval runs
        exclude the scope from gate math and report the count."""
        return any(u.get("model_fallback") for u in self.usage)


def repair_message(user_message: str, prior_output_json: str, errors: Sequence[str]) -> str:
    return (user_message + PRIOR_HEADER + prior_output_json + REPAIR_HEADER
            + "\n".join(f"- {e}" for e in errors))


def _attempt(scope: V6Scope, out: ScopePlanOutput, precision: Decimal):
    try:
        terminals, checks, disps, tel = map_scope(scope, out, precision)
    except MappingError as e:
        return None, e.errors
    errs = validate_scope(scope, terminals, checks, disps, precision)
    return ((terminals, checks, disps, tel), errs) if not errs else (None, errs)


def _fallback(scope: V6Scope, precision: Decimal, origin: Origin, reason: str,
              errors: Sequence[str] = (), outputs=(), usage=()) -> ScopePlanResult:
    terminals, checks, disps = fallback_scope(scope, precision)
    telemetry = [] if origin == "compiled" else [f"planner_fallback {scope.scope}: {reason}"]
    return ScopePlanResult(scope.scope, origin, terminals, checks, disps, telemetry,
                           list(outputs), list(usage), list(errors))


async def plan_scope(scope: V6Scope, *, precision: Decimal, system_prompt: str, user_message: str,
                     call: LLMCall) -> ScopePlanResult:
    if not scope.needs_planner:
        return _fallback(scope, precision, "compiled", "all terminals compiled")
    outputs: List[Dict[str, Any]] = []
    usage: List[Dict[str, Any]] = []
    try:
        out, u = await call(system_prompt, user_message)
    except Exception as e:                                    # noqa: BLE001 — isolated per scope (§3.6)
        return _fallback(scope, precision, "fallback", f"call_failed: {type(e).__name__}")
    outputs.append(out.model_dump(mode="json"))
    usage.append(u)
    done, errs = _attempt(scope, out, precision)
    if done:
        t, c, d, tel = done
        return ScopePlanResult(scope.scope, "planner", t, c, d, tel, outputs, usage)

    try:
        out2, u2 = await call(system_prompt, repair_message(user_message, out.model_dump_json(), errs))
    except Exception as e:                                    # noqa: BLE001
        return _fallback(scope, precision, "fallback", f"repair_call_failed: {type(e).__name__}",
                         errs, outputs, usage)
    outputs.append(out2.model_dump(mode="json"))
    usage.append(u2)
    done, errs2 = _attempt(scope, out2, precision)
    if done:
        t, c, d, tel = done
        return ScopePlanResult(scope.scope, "repaired", t, c, d, tel, outputs, usage, list(errs))
    return _fallback(scope, precision, "fallback", "repair_failed", errs2, outputs, usage)


async def plan_all(stage1: Stage1V6, *, system_prompt: str, render: Callable[[V6Scope], str],
                   call: LLMCall, concurrency: int = PLANNER_MAX_CONCURRENCY
                   ) -> List[ScopePlanResult]:
    """Every scope, in parallel under `concurrency`, results in rubric order."""
    sem = asyncio.Semaphore(concurrency)

    async def one(scope: V6Scope) -> ScopePlanResult:
        async with sem:
            return await plan_scope(scope, precision=stage1.precision, system_prompt=system_prompt,
                                    user_message=render(scope), call=call)

    return list(await asyncio.gather(*(one(s) for s in stage1.scopes)))


def assemble_plan(results: Sequence[ScopePlanResult], *, config_hash: str,
                  rubric_contract_version: str, pack: PackRef) -> GradingPlanV6:
    terminals = [t for r in results for t in r.terminals]
    checks = [c for r in results for c in r.checks]
    return GradingPlanV6(plan_schema="plan/v6", plan_hash=pv.plan_hash(terminals, checks),
                         config_hash=config_hash, rubric_contract_version=rubric_contract_version,
                         subject_pack=pack, terminals=terminals, checks=checks)
