"""
The plan builder — `grading_plans` row → a ready GradingPlan
(PLAN_production_wiring.md §5/§6.2; rulings W-2, OD-W1, OD-W3, OD-W5, OD-W10, OD-W11).

Three entry points:

  build_plan_for_contract(contract, ...)    pure of the DB: compile → route → segment →
                                            assemble → validate. Raises ONLY CompilerBug.
  run_plan_build(row_id)                    the Cloud Tasks target (and the inline dev
                                            runner): CAS queued→building, heartbeat,
                                            build, mark ready | failed. Never raises.
  resolve_plan_for_grade(rubric_id, contract_json)
                                            the grade path: ready → use; live builder →
                                            wait; queued / failed / absent / dead builder →
                                            build in place, then use.

W-2's guarantee is STRUCTURAL: the model stages can only degrade the WORDING
(a provider outage, an envelope overrun, a validator surprise all fall back to
the compiler's own spans — `wording_source='placeholder'`), never the algebra.
The only way to a `failed` row is a CompilerBug, which is a defect in this
codebase and must be loud.

Sessions are short (CAS, heartbeat, terminal write); nothing holds a
transaction across a model call (the 2026-08-07 pooler lesson).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from ..agents.grader.plan_schemas import GradingPlan
from ..agents.grader.plan_validator import validate_plan
from ..agents.plan_compiler import compile_contract
from ..agents.plan_compiler.assemble import assemble_placeholder_plan, assemble_plan
from ..agents.plan_compiler.context import scope_maps
from ..agents.plan_compiler.models import (MODEL_CARDS, ROUTER_MODEL_KEY, SEGMENTER_MODEL_KEY,
                                           cost_fn)
from ..agents.plan_compiler.route import ROUTER_PROMPT_VERSION, route_monoliths
from ..agents.plan_compiler.segment import (SEGMENTER_PROMPT_VERSION, EnvelopeExceeded,
                                            segment_skeleton, substitute)
from ..agents.plan_compiler.skeleton import CompilerBug
from ..agents.plan_compiler.stage0 import contract_scopes, scope_label, terminals_of
from ..config import settings
from ..database import get_db_context
from ..models.grading import Rubric
from ..models.grading_plan import GradingPlanRecord
from ..schemas.ontology_types import GradingRubricContract
from . import plan_store
from .plan_store import WORDING_PLACEHOLDER, WORDING_SEGMENTED, contract_sha256

logger = logging.getLogger(__name__)

HEARTBEAT_S = 30.0
POLL_S = 5.0
LLMFactory = Callable[[str], Any]


class PlanUnavailable(RuntimeError):
    """A grade could not get a plan: the builder failed structurally or a live
    builder never finished inside the wait. Loud on purpose — the grade row
    fails with this message and the revision chain can retry."""


def default_llm_factory(model_key: str):
    """The production models (OD-W12: Anthropic, keys from settings)."""
    from ..agents.grader.llm_factory import build_chat_model
    card = MODEL_CARDS[model_key]
    if model_key == SEGMENTER_MODEL_KEY:
        return build_chat_model(card.provider, card.model_id, max_output_tokens=6000, timeout_s=120)
    return build_chat_model(card.provider, card.model_id, max_output_tokens=2000, timeout_s=180)


@dataclass
class BuildResult:
    plan: GradingPlan
    skeleton_json: Dict[str, Any]
    wording_source: str
    cost_usd: Decimal
    error_message: Optional[str]
    segmenter_model: Optional[str]
    router_model: Optional[str]
    substituted: int
    router_failed: List[str]


def _json_safe(o):
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, dict):
        return {k: _json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v) for v in o]
    return o


def _validator_inputs(contract):
    points, scopes, corpora = {}, {}, {}
    from ..agents.plan_gen.prompt import scope_corpus
    for key, q, sub in contract_scopes(contract):
        lbl = scope_label(key)
        corpora[lbl] = scope_corpus(q, sub)
        for tid, pts in terminals_of(sub or q):
            points[tid] = pts
            scopes[tid] = lbl
    return points, scopes, corpora


# ═══════════════════════════════════════════════════════════════════════════
# the build, pure of the DB
# ═══════════════════════════════════════════════════════════════════════════

async def build_plan_for_contract(contract: GradingRubricContract, *, plan_exam_id: str,
                                  llm_factory: Optional[LLMFactory] = None,
                                  route_min_points: Optional[int] = None,
                                  envelope_usd: Optional[float] = None) -> BuildResult:
    factory = llm_factory or default_llm_factory
    envelope = float(settings.plan_build_envelope_usd if envelope_usd is None else envelope_usd)
    threshold = Decimal(str(settings.plan_route_min_points if route_min_points is None
                            else route_min_points))
    contract_json = contract.model_dump(mode="json")
    sha = contract_sha256(contract_json)
    precision = Decimal(str(contract.numeric_policy.precision))

    # Stage 1 — the only stage that can fail the build (a CompilerBug propagates)
    skeleton = compile_contract(contract, exam_id=plan_exam_id, rubric_contract_sha256=sha,
                                route_min_points=threshold)
    corpora, solutions, questions = scope_maps(contract)
    errors: List[str] = []
    cost = Decimal("0")
    router_model: Optional[str] = None
    segmenter_model: Optional[str] = None
    router_failed: List[str] = []
    router_notes: List[str] = []

    # Stage 2b — router (a failure leaves every monolith whole)
    if any(t.routed for t in skeleton.terminals):
        try:
            rr = await route_monoliths(skeleton, factory(ROUTER_MODEL_KEY), corpora=corpora,
                                       solutions=solutions, questions=questions,
                                       cost_fn=cost_fn(ROUTER_MODEL_KEY), envelope_usd=envelope)
            skeleton, router_failed = rr.skeleton, list(rr.failed)
            # keep WHY a monolith stayed whole (ungrounded span, wrong count, …) —
            # the production smoke landed 5 refusals with no reason on the row
            router_notes = [f"{f.terminal_id}: {f.detail}" for f in rr.flags]
            cost += Decimal(str(round(rr.cost_usd, 6)))
            router_model = MODEL_CARDS[ROUTER_MODEL_KEY].model_id
        except EnvelopeExceeded as e:
            errors.append(f"router: {e}")
        except Exception as e:                       # provider / auth / transport / factory
            errors.append(f"router: {type(e).__name__}: {str(e)[:200]}")
            logger.warning("plan_build_router_skipped exam=%s err=%s", plan_exam_id, type(e).__name__)

    # Stage 2 — segmenter (a failure keeps the compiler's own spans as wording)
    wording = None
    substituted = 0
    remaining = max(0.0, envelope - float(cost))
    try:
        sr = await segment_skeleton(skeleton, factory(SEGMENTER_MODEL_KEY), corpora=corpora,
                                    solutions=solutions, cost_fn=cost_fn(SEGMENTER_MODEL_KEY),
                                    envelope_usd=remaining)
        wording, substituted = dict(sr.wording), len(sr.substituted)
        cost += Decimal(str(round(sr.cost_usd, 6)))
        segmenter_model = MODEL_CARDS[SEGMENTER_MODEL_KEY].model_id
    except EnvelopeExceeded as e:                    # OD-W10: keep what was worded, substitute the rest
        errors.append(f"segmenter: {e}")
        if e.run is not None:
            wording = dict(e.run.wording)
            cost += Decimal(str(round(e.run.cost_usd, 6)))
            segmenter_model = MODEL_CARDS[SEGMENTER_MODEL_KEY].model_id
    except Exception as e:
        errors.append(f"segmenter: {type(e).__name__}: {str(e)[:200]}")
        logger.warning("plan_build_segmenter_skipped exam=%s err=%s", plan_exam_id, type(e).__name__)

    if wording is not None:
        for t in skeleton.terminals:
            for s in t.slots:
                if s.slot_id not in wording:
                    wording[s.slot_id] = substitute(s, t)
                    substituted += 1
        plan = assemble_plan(skeleton, wording, segmenter_prompt_version=SEGMENTER_PROMPT_VERSION,
                             segmenter_model=segmenter_model, router_model=router_model)
        wording_source = WORDING_SEGMENTED
    else:
        plan = assemble_placeholder_plan(skeleton)
        wording_source = WORDING_PLACEHOLDER

    # Stage 3 — the real validator; a surprise here degrades to the placeholder plan
    points, scopes, v_corpora = _validator_inputs(contract)
    verrs = validate_plan(plan, contract_terminal_points=points, terminal_scopes=scopes,
                          precision=precision, scope_corpora=v_corpora)
    if verrs:
        errors.append("validator on segmented plan: " + "; ".join(verrs[:5]))
        plan = assemble_placeholder_plan(skeleton)
        wording_source = WORDING_PLACEHOLDER
        verrs2 = validate_plan(plan, contract_terminal_points=points, terminal_scopes=scopes,
                               precision=precision, scope_corpora=v_corpora)
        if verrs2:
            raise CompilerBug(f"placeholder plan fails the validator: {verrs2[:5]}")

    skeleton_json = _json_safe(asdict(skeleton))
    skeleton_json["build"] = dict(router_prompt_version=ROUTER_PROMPT_VERSION if router_model else None,
                                  segmenter_prompt_version=SEGMENTER_PROMPT_VERSION if segmenter_model else None,
                                  substituted=substituted, router_failed=router_failed,
                                  router_notes=router_notes, errors=errors)
    return BuildResult(plan=plan, skeleton_json=skeleton_json, wording_source=wording_source,
                       cost_usd=cost.quantize(Decimal("0.0001")),
                       error_message=("; ".join(errors)[:2000] or None),
                       segmenter_model=segmenter_model, router_model=router_model,
                       substituted=substituted, router_failed=router_failed)


# ═══════════════════════════════════════════════════════════════════════════
# the row lifecycle
# ═══════════════════════════════════════════════════════════════════════════

async def _heartbeat_loop(row_id: UUID) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_S)
        try:
            async with get_db_context() as db:
                await plan_store.heartbeat(db, row_id)
        except Exception:
            logger.warning("plan_build_heartbeat_failed row_id=%s", row_id)


async def _load_row_contract(row_id: UUID, contract_json: Optional[Dict[str, Any]]):
    async with get_db_context() as db:
        row = await db.get(GradingPlanRecord, row_id)
        if row is None:
            return None, None
        if contract_json is None:
            rubric = await db.get(Rubric, row.rubric_id) if row.rubric_id else None
            contract_json = rubric.contract_json if rubric is not None else None
        return row, contract_json


async def _build_claimed_row(row_id: UUID, *, llm_factory: Optional[LLMFactory],
                             contract_json: Optional[Dict[str, Any]] = None) -> None:
    """The row is `building` under THIS worker. Build, then ready | failed."""
    row, contract_json = await _load_row_contract(row_id, contract_json)
    if row is None:
        return
    if not contract_json:
        async with get_db_context() as db:
            await plan_store.mark_failed(db, row_id, "rubric or its contract vanished before the build")
        return
    hb = asyncio.create_task(_heartbeat_loop(row_id))
    try:
        contract = GradingRubricContract.model_validate(contract_json)
        result = await build_plan_for_contract(contract, plan_exam_id=str(row.rubric_id or "rubric"),
                                               llm_factory=llm_factory)
    except CompilerBug as e:
        logger.error("plan_build_compiler_bug row_id=%s err=%s", row_id, str(e)[:300])
        async with get_db_context() as db:
            await plan_store.mark_failed(db, row_id, f"CompilerBug: {e}")
        return
    except Exception as e:                            # unexpected — still never propagates
        logger.exception("plan_build_unexpected row_id=%s", row_id)
        async with get_db_context() as db:
            await plan_store.mark_failed(db, row_id, f"{type(e).__name__}: {str(e)[:300]}")
        return
    finally:
        hb.cancel()
    async with get_db_context() as db:
        await plan_store.mark_ready(
            db, row_id, plan_json=result.plan.model_dump(mode="json"),
            plan_version=result.plan.plan_version, skeleton_json=result.skeleton_json,
            compiler_version=result.plan.compiler_version or "",
            segmenter_model=result.segmenter_model, router_model=result.router_model,
            wording_source=result.wording_source, cost_usd=result.cost_usd,
            error_message=result.error_message, sha=row.contract_sha256)
    logger.info("plan_build_ready row_id=%s rubric_id=%s wording=%s cost_usd=%s substituted=%d "
                "router_failed=%d", row_id, row.rubric_id, result.wording_source,
                result.cost_usd, result.substituted, len(result.router_failed))


async def run_plan_build(row_id: UUID, *, llm_factory: Optional[LLMFactory] = None) -> bool:
    """Cloud Tasks / inline entry. CAS queued→building first (a redelivery or
    an already-claimed row is a no-op). Returns True iff this call built."""
    try:
        async with get_db_context() as db:
            if not await plan_store.claim_building(db, row_id):
                logger.info("plan_build_skipped row_id=%s", row_id)
                return False
        await _build_claimed_row(row_id, llm_factory=llm_factory)
    except Exception:
        logger.exception("plan_build_session_failure row_id=%s", row_id)
    return True


# ═══════════════════════════════════════════════════════════════════════════
# the grade path (OD-W1 / OD-W3)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ResolvedPlan:
    plan: GradingPlan
    wording_source: str
    row_id: UUID
    built_in_place: bool
    waited_s: float


async def resolve_plan_for_grade(rubric_id: Optional[UUID], contract_json: Dict[str, Any], *,
                                 llm_factory: Optional[LLMFactory] = None,
                                 wait_s: Optional[float] = None) -> ResolvedPlan:
    """ready → use it. building with a fresh heartbeat → wait (≤ wait_s, OD-W3).
    queued / absent / failed / dead builder → build IN PLACE, then use it."""
    sha = contract_sha256(contract_json)
    wait_s = float(settings.plan_wait_s if wait_s is None else wait_s)
    ttl = timedelta(minutes=settings.plan_build_heartbeat_ttl_minutes)
    t0 = asyncio.get_event_loop().time()
    built = False

    while True:
        now = datetime.now(timezone.utc)
        async with get_db_context() as db:
            row = await plan_store.find_live(db, sha)
            if row is not None and row.status == "ready":
                plan = GradingPlan.model_validate(row.plan_json)
                return ResolvedPlan(plan, row.wording_source or WORDING_PLACEHOLDER, row.id,
                                    built, asyncio.get_event_loop().time() - t0)
            row_id = row.id if row is not None else None
            status = row.status if row is not None else None
            hb_at = row.updated_at if row is not None else None
            if row is None:
                version = str(contract_json.get("contract_version") or "")
                row, _created = await plan_store.insert_queued(db, rubric_id=rubric_id,
                                                               contract_version=version, sha=sha)
                row_id, status, hb_at = row.id, row.status, row.updated_at
        if status == "queued":
            async with get_db_context() as db:
                claimed = await plan_store.claim_building(db, row_id)
            if claimed:
                await _build_claimed_row(row_id, llm_factory=llm_factory, contract_json=contract_json)
                built = True
                continue                                  # the loop reads ready | failed
        elif status == "building":
            hb = hb_at if hb_at.tzinfo else hb_at.replace(tzinfo=timezone.utc)
            if hb < now - ttl:                            # dead builder (OD-W3)
                async with get_db_context() as db:
                    claimed = await plan_store.claim_building(db, row_id, stale_before=now - ttl)
                if claimed:
                    await _build_claimed_row(row_id, llm_factory=llm_factory, contract_json=contract_json)
                    built = True
                    continue
            elapsed = asyncio.get_event_loop().time() - t0
            if elapsed > 2 * wait_s:
                raise PlanUnavailable(f"plan {row_id} still building after {elapsed:.0f}s")
            await asyncio.sleep(POLL_S)
            continue
        # a live row that is neither queued/building/ready cannot exist (the
        # index), and a row this worker just built lands as ready or failed:
        async with get_db_context() as db:
            fresh = await db.get(GradingPlanRecord, row_id)
        if fresh is not None and fresh.status == "failed":
            raise PlanUnavailable(f"plan build {row_id} failed: {fresh.error_message}")
        await asyncio.sleep(POLL_S)
