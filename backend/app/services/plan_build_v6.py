"""
grader-v6 production plans — built LAZILY at grade time (owner rulings 2026-10-17 §9:
"production v6 plans build lazily on the production credentials").

    resolve_plan_v6_for_grade(rubric_id, contract_json) -> ResolvedPlanV6

The same lifecycle as the v5 resolver (`plan_build_runner.resolve_plan_for_grade`), under
the v6 KEY of the plan cache (migration 035: (contract_sha256, config_hash)), so a v5 plan
and a v6 plan of one contract live side by side:

  ready → use it · a live builder → wait on its heartbeat (OD-W3) · queued / absent /
  failed / dead builder → build IN PLACE under this grade job, then use it.

The build is the evaluated pipeline, frozen (§2): Stage 1 (`compile_stage1_v6`) → the v6
planner (planner-v6.2, the configured model and effort, ≤ 1 repair, rule 7 strict →
lenient, else the deterministic fallback per scope) → `assemble_plan` → the plan hash.
Scopes are planned in parallel (`plan_all`), which keeps a rubric's build within a grade
job's budget. The config hash is a function of the stage-1 version, the planner model and
prompt version, and the subject pack — so a change to any of them is a NEW key: old drafts
keep their pinned plan (`graded_tests.plan_hash`), new grades build a new one.

Two v5 columns are re-read for v6 rows (decided — pending owner veto): `wording_source` is
`segmented` when every planned scope came from the model and `placeholder` when any scope
fell back (the CHECK admits only those two); `plan_version` is `plan/v6:<hash12>`.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from app.agents.grader import plan_values as pv
from app.agents.grader.plan_schemas import GradingPlanV6, PackRef
from app.config import settings
from app.database import get_db_context
from app.models.grading_plan import GradingPlanRecord

from . import plan_store
from .plan_build_runner import POLL_S, PlanUnavailable, _heartbeat_loop
from .plan_store import WORDING_PLACEHOLDER, WORDING_SEGMENTED, contract_sha256
from .provider_billing import log_billing_exhausted

logger = logging.getLogger(__name__)


def _profile(contract):
    from app.subjects import get_profile
    return get_profile(getattr(contract, "subject", None) or "computer_science")


def v6_config_hash(contract) -> str:
    from app.agents.plan_compiler.models import MODEL_CARDS
    from app.agents.plan_compiler.stage1_v6 import STAGE1_V6_VERSION
    profile = _profile(contract)
    return pv.config_hash(compiler_version=STAGE1_V6_VERSION,
                          planner_model=MODEL_CARDS[settings.v6_planner_model_key].model_id,
                          planner_prompt_version=settings.v6_planner_prompt_version,
                          pack_id=profile.pack_id, pack_version=profile.pack_version)


async def build_plan_v6(contract, *, sha: str, call=None) -> Tuple[GradingPlanV6, Dict[str, Any], Decimal, str]:
    """(plan, telemetry, cost_usd, wording_source). `call` is the injected planner call
    (tests); production builds the live one from the settings."""
    from app.agents.plan_compiler.stage1_v6 import compile_stage1_v6
    from app.agents.planner.planner import assemble_plan, plan_all
    from app.agents.planner.prompt import am_g20_applies, planner_system_prompt, render_scope_input
    from app.agents.planner.stage1_input import scope_planner_input
    profile = _profile(contract)
    s1 = compile_stage1_v6(contract, exam_id=str(contract.rubric_id), rubric_contract_sha256=sha)
    if call is None:
        from app.agents.planner.planner_llm import build_planner_call
        call = build_planner_call(model_key=settings.v6_planner_model_key, effort=settings.v6_planner_effort)
    version = settings.v6_planner_prompt_version              # [Item C] config-selected
    results = await plan_all(s1, system_prompt=planner_system_prompt(profile, version),
                             render=lambda scope: render_scope_input(scope_planner_input(scope)), call=call,
                             am_g20=am_g20_applies(version))
    plan = assemble_plan(results, config_hash=v6_config_hash(contract),
                         rubric_contract_version=str(contract.contract_version),
                         pack=PackRef(pack_id=profile.pack_id, pack_version=profile.pack_version))
    cost = sum((Decimal(str(u.get("cost_usd") or 0)) for r in results for u in r.usage), Decimal("0"))
    planned = [r for r in results if r.origin != "compiled"]
    wording = WORDING_PLACEHOLDER if any(r.origin == "fallback" for r in planned) else WORDING_SEGMENTED
    telemetry = {"scopes": {r.scope: {"origin": r.origin, "errors": r.errors, "telemetry": r.telemetry,
                                      "usage": r.usage} for r in results}}
    return plan, telemetry, cost.quantize(Decimal("0.0001")), wording


async def _build_row(row_id: UUID, contract, sha: str, config_hash: str, *, call=None) -> None:
    from app.agents.plan_compiler.models import MODEL_CARDS
    from app.agents.plan_compiler.stage1_v6 import STAGE1_V6_VERSION
    hb = asyncio.create_task(_heartbeat_loop(row_id))
    try:
        plan, telemetry, cost, wording = await build_plan_v6(contract, sha=sha, call=call)
    except Exception as e:                                       # noqa: BLE001 — never propagates
        log_billing_exhausted(e, site="plan_build_v6", plan_id=row_id, rubric_id=None)
        logger.exception("plan_build_v6_failed row_id=%s", row_id)
        async with get_db_context() as db:
            await plan_store.mark_failed(db, row_id, f"{type(e).__name__}: {str(e)[:300]}")
        return
    finally:
        hb.cancel()
    async with get_db_context() as db:
        await plan_store.mark_ready(
            db, row_id, plan_json=plan.model_dump(mode="json"),
            plan_version=f"plan/v6:{plan.plan_hash[:12]}", skeleton_json=telemetry,
            compiler_version=STAGE1_V6_VERSION, segmenter_model=None,
            router_model=MODEL_CARDS[settings.v6_planner_model_key].model_id,
            wording_source=wording, cost_usd=cost, sha=sha, config_hash=config_hash,
            plan_hash=plan.plan_hash)
    logger.info(f"plan_build_v6_ready row_id={row_id} plan_hash={plan.plan_hash[:12]} "
                f"wording={wording} cost_usd={cost}")


@dataclass
class ResolvedPlanV6:
    plan: GradingPlanV6
    row_id: UUID
    plan_hash: str
    built_in_place: bool
    waited_s: float


async def resolve_plan_v6_for_grade(rubric_id: Optional[UUID], contract_json: Dict[str, Any], *,
                                    call=None, wait_s: Optional[float] = None) -> ResolvedPlanV6:
    from app.schemas.ontology_types import GradingRubricContract
    contract = GradingRubricContract.model_validate(contract_json)
    sha = contract_sha256(contract_json)
    config_hash = v6_config_hash(contract)
    wait_s = float(settings.plan_wait_s if wait_s is None else wait_s)
    ttl = timedelta(minutes=settings.plan_build_heartbeat_ttl_minutes)
    loop = asyncio.get_event_loop()
    t0, built = loop.time(), False
    while True:
        now = datetime.now(timezone.utc)
        async with get_db_context() as db:
            row = await plan_store.find_live(db, sha, config_hash=config_hash)
            if row is not None and row.status == "ready":
                return ResolvedPlanV6(GradingPlanV6.model_validate(row.plan_json), row.id,
                                      row.plan_hash, built, loop.time() - t0)
            if row is None:
                row, _created = await plan_store.insert_queued(
                    db, rubric_id=rubric_id, contract_version=str(contract_json.get("contract_version") or ""),
                    sha=sha, config_hash=config_hash)
            row_id, status, hb_at = row.id, row.status, row.updated_at
        if status == "queued":
            async with get_db_context() as db:
                claimed = await plan_store.claim_building(db, row_id)
            if claimed:
                await _build_row(row_id, contract, sha, config_hash, call=call)
                built = True
                continue
        elif status == "building":
            hb = hb_at if hb_at.tzinfo else hb_at.replace(tzinfo=timezone.utc)
            if hb < now - ttl:                                       # a dead builder (OD-W3)
                async with get_db_context() as db:
                    claimed = await plan_store.claim_building(db, row_id, stale_before=now - ttl)
                if claimed:
                    await _build_row(row_id, contract, sha, config_hash, call=call)
                    built = True
                    continue
            if loop.time() - t0 > 2 * wait_s:
                raise PlanUnavailable(f"v6 plan {row_id} still building after {loop.time() - t0:.0f}s")
            await asyncio.sleep(POLL_S)
            continue
        async with get_db_context() as db:
            fresh = await db.get(GradingPlanRecord, row_id)
        if fresh is not None and fresh.status == "failed":
            raise PlanUnavailable(f"v6 plan build {row_id} failed: {fresh.error_message}")
        await asyncio.sleep(POLL_S)
