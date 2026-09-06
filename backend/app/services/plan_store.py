"""
The plan store — `grading_plans` row lifecycle and the contract hash
(PLAN_production_wiring.md §3/§7; rulings W-1, OD-W4).

One concept, one place: every write to `grading_plans` goes through this
module, and the contract hash is computed here and nowhere else.

  contract_sha256(contract_json)   the key (OD-W4, ratified: contract_version BLANKED)
  find_live / get_ready            lookups by hash
  insert_queued                    the race is decided by the partial unique index
  claim_building                   CAS queued→building (+ a stale `building` under OD-W3)
  heartbeat                        updated_at while building
  mark_ready / mark_failed         the terminal transitions; ready supersedes the old ready
  ensure_plan_for_contract         the compile-time trigger's DB half (W-2)

Sessions: the CAS/transition helpers take a session so a runner can keep them
short; `ensure_plan_for_contract` opens its own because it runs after the
request's commit, when the request session is already closed.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_context
from ..models.grading_plan import GradingPlanRecord

logger = logging.getLogger(__name__)

WORDING_SEGMENTED = "segmented"
WORDING_PLACEHOLDER = "placeholder"
LIVE_STATUSES = ("queued", "building", "ready")


# ── the key ──────────────────────────────────────────────────────────────────

def contract_sha256(contract_json: Dict[str, Any]) -> str:
    """sha256 over the canonical JSON of the contract with `contract_version`
    BLANKED (OD-W4, ratified): a recompile of unchanged content reuses its
    plan and spends nothing. Canonical = sorted keys, UTF-8, no whitespace —
    the rule OD-G1.4 declined to invent for the pilot, now written down once
    and pinned by `tests/services/test_plan_store.py`."""
    doc = dict(contract_json)
    doc.pop("contract_version", None)
    canon = json.dumps(doc, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── lookups ──────────────────────────────────────────────────────────────────

async def find_live(db: AsyncSession, sha: str) -> Optional[GradingPlanRecord]:
    """The one queued/building/ready row for this hash, if any."""
    result = await db.execute(
        select(GradingPlanRecord)
        .where(GradingPlanRecord.contract_sha256 == sha,
               GradingPlanRecord.status.in_(LIVE_STATUSES))
        .limit(1))
    return result.scalar_one_or_none()


async def get_ready(db: AsyncSession, sha: str) -> Optional[GradingPlanRecord]:
    result = await db.execute(
        select(GradingPlanRecord)
        .where(GradingPlanRecord.contract_sha256 == sha,
               GradingPlanRecord.status == "ready")
        .limit(1))
    return result.scalar_one_or_none()


# ── transitions ──────────────────────────────────────────────────────────────

async def insert_queued(db: AsyncSession, *, rubric_id: Optional[UUID],
                        contract_version: str, sha: str
                        ) -> Tuple[GradingPlanRecord, bool]:
    """(row, created). A concurrent writer loses on
    `idx_grading_plans_one_live_per_contract` and gets the winner's row —
    the extraction-submit idempotency shape. Commits."""
    row = GradingPlanRecord(rubric_id=rubric_id, contract_version=contract_version,
                            contract_sha256=sha, status="queued")
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await find_live(db, sha)
        if existing is None:              # the winner finished and was superseded between? re-read
            raise
        return existing, False
    await db.refresh(row)
    return row, True


async def claim_building(db: AsyncSession, row_id: UUID, *,
                         stale_before: Optional[datetime] = None) -> bool:
    """CAS queued→building. With `stale_before`, a `building` row whose
    heartbeat is older than that is claimed too (OD-W3: a dead builder is
    dead; the grade job takes over). False = someone else holds it. Commits."""
    now = _now()
    where = [GradingPlanRecord.id == row_id]
    if stale_before is None:
        where.append(GradingPlanRecord.status == "queued")
    else:
        where.append(((GradingPlanRecord.status == "queued")
                      | ((GradingPlanRecord.status == "building")
                         & (GradingPlanRecord.updated_at < stale_before))))
    result = await db.execute(
        update(GradingPlanRecord).where(*where)
        .values(status="building", updated_at=now))
    await db.commit()
    return result.rowcount == 1


async def heartbeat(db: AsyncSession, row_id: UUID) -> None:
    await db.execute(
        update(GradingPlanRecord)
        .where(GradingPlanRecord.id == row_id, GradingPlanRecord.status == "building")
        .values(updated_at=_now()))
    await db.commit()


async def mark_ready(db: AsyncSession, row_id: UUID, *, plan_json: Dict[str, Any],
                     plan_version: str, skeleton_json: Optional[Dict[str, Any]],
                     compiler_version: str, segmenter_model: Optional[str],
                     router_model: Optional[str], wording_source: str,
                     cost_usd: Decimal, error_message: Optional[str] = None,
                     sha: str) -> None:
    """building → ready, and every OTHER ready row for the hash → superseded,
    in ONE transaction (append-only: the old plan_json is never touched)."""
    assert wording_source in (WORDING_SEGMENTED, WORDING_PLACEHOLDER)
    now = _now()
    await db.execute(
        update(GradingPlanRecord)
        .where(GradingPlanRecord.contract_sha256 == sha,
               GradingPlanRecord.status == "ready",
               GradingPlanRecord.id != row_id)
        .values(status="superseded", updated_at=now))
    result = await db.execute(
        update(GradingPlanRecord)
        .where(GradingPlanRecord.id == row_id, GradingPlanRecord.status == "building")
        .values(status="ready", plan_json=plan_json, plan_version=plan_version,
                skeleton_json=skeleton_json, compiler_version=compiler_version,
                segmenter_model=segmenter_model, router_model=router_model,
                wording_source=wording_source, cost_usd=cost_usd,
                error_message=error_message, built_at=now, updated_at=now))
    await db.commit()
    if result.rowcount != 1:
        raise RuntimeError(f"grading_plans {row_id}: mark_ready found no building row")


async def mark_failed(db: AsyncSession, row_id: UUID, error_message: str,
                      cost_usd: Decimal = Decimal("0")) -> None:
    await db.execute(
        update(GradingPlanRecord)
        .where(GradingPlanRecord.id == row_id,
               GradingPlanRecord.status.in_(("queued", "building")))
        .values(status="failed", error_message=error_message[:2000], cost_usd=cost_usd,
                updated_at=_now()))
    await db.commit()


# ── the compile-time trigger (W-2), DB half ──────────────────────────────────

async def ensure_plan_for_contract(*, rubric_id: Optional[UUID], contract_json: Dict[str, Any]
                                   ) -> Optional[UUID]:
    """A live row exists for this contract's hash → None (nothing to do — the
    hash is why a re-save of unchanged content costs nothing). Otherwise
    INSERT queued and return its id for the caller to enqueue. Own session."""
    sha = contract_sha256(contract_json)
    version = str(contract_json.get("contract_version") or "")
    async with get_db_context() as db:
        if await find_live(db, sha) is not None:
            return None
        row, created = await insert_queued(db, rubric_id=rubric_id,
                                           contract_version=version, sha=sha)
        return row.id if created else None


async def kick_plan_build(rubric_id: UUID) -> Optional[UUID]:
    """ensure + enqueue for a rubric that was just compiled, never raises (the
    queued row is durable; the grade path builds on demand if the enqueue is
    lost — OD-W1). Called by the three contract-writing endpoints AFTER their
    commit, with the request session closed. Returns the new row id, if any."""
    try:
        from ..models.grading import Rubric
        async with get_db_context() as db:
            rubric = await db.get(Rubric, rubric_id)
            contract_json = rubric.contract_json if rubric is not None else None
        if not contract_json:
            return None
        row_id = await ensure_plan_for_contract(rubric_id=rubric_id, contract_json=contract_json)
        if row_id is None:
            return None
        from .cloud_tasks_service import enqueue_plan_build_task_or_log
        await enqueue_plan_build_task_or_log(row_id)
        return row_id
    except Exception:
        logger.exception("plan_build_kick_failed rubric_id=%s", rubric_id)
        return None
