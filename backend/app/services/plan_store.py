"""
The plan store — `grading_plans` row lifecycle and the contract hash
(PLAN_production_wiring.md §3/§7; rulings W-1, OD-W4; grader-v6 §5.7 / AM-G6).

One concept, one place: every write to `grading_plans` goes through this
module, and the contract hash is computed here and nowhere else.

THE KEY is (contract_sha256, config_hash) since migration 035 [AM-G6]:

  contract_sha256(contract_json)   the contract half (OD-W4, ratified: contract_version BLANKED)
  config_hash                      the plan-config half — `V5_CONFIG_HASH` for every v5
                                   plan (one constant; the column's DB DEFAULT), or a v6
                                   `plan_values.config_hash(...)` digest

so a v5 and a v6 plan of one contract coexist as two live rows. Every lookup and
every write that selects rows by key takes BOTH halves, as a required keyword: a
caller that forgot its config would otherwise read or supersede another
planner's plan. The row-id transitions (claim / heartbeat / failed) need no key —
the id already names exactly one row.

  find_live / get_ready            lookups by key
  insert_queued                    the race is decided by the partial unique index
  claim_building                   CAS queued→building (+ a stale `building` under OD-W3)
  heartbeat                        updated_at while building
  mark_ready / mark_failed         the terminal transitions; ready supersedes the old
                                   ready of the SAME key only
  requeue_for_rebuild              a deliberate rebuild: ready → superseded + a new queued row, ONE txn
  ensure_plan_for_contract         the compile-time trigger's DB half (W-2)

Sessions: the CAS/transition helpers take a session so a runner can keep them
short; `ensure_plan_for_contract` opens its own because it runs after the
request's commit, when the request session is already closed.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
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

# [AM-G6] The ONE key every v5 plan carries — the backfill value of migration 035
# and its column DEFAULT (a pre-035 revision inserts without naming the column).
# Pinned equal to the migration by tests/services/test_plan_cache.py. A v6 key is
# a sha256 hex digest, so it can never collide with this literal.
V5_CONFIG_HASH = "v5"

V6_PLAN_SCHEMA = "plan/v6"
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")


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


def _check_config_hash(config_hash: str) -> None:
    """A key is the v5 constant or a sha256 digest — anything else is a caller
    passing the wrong string (a plan_hash, a label) into the key slot."""
    if config_hash != V5_CONFIG_HASH and not (
            isinstance(config_hash, str) and _SHA256_HEX.fullmatch(config_hash)):
        raise ValueError(f"config_hash must be {V5_CONFIG_HASH!r} or a sha256 hex digest, "
                         f"got {config_hash!r}")


def _plan_identity_problem(plan_json: Dict[str, Any], *, config_hash: str,
                           plan_hash: Optional[str]) -> Optional[str]:
    """The plan must belong to the key it is stored under. A v5 plan lives only
    under V5_CONFIG_HASH and carries no plan_hash; a plan/v6 plan lives only
    under its own config_hash and is stored with the plan_hash it declares.
    A mismatch is a wiring bug (the wrong builder for the row) — refused before
    anything is written, never repaired."""
    is_v6 = isinstance(plan_json, dict) and plan_json.get("plan_schema") == V6_PLAN_SCHEMA
    if config_hash == V5_CONFIG_HASH:
        if is_v6:
            return "a plan/v6 plan cannot be stored under the v5 key"
        if plan_hash is not None:
            return "a v5 plan carries no plan_hash"
        return None
    if not is_v6:
        return f"only a {V6_PLAN_SCHEMA} plan can be stored under config {config_hash[:12]}…"
    if plan_json.get("config_hash") != config_hash:
        return (f"the plan declares config {str(plan_json.get('config_hash'))[:12]}… "
                f"but the row is keyed {config_hash[:12]}…")
    if plan_hash is None or not _SHA256_HEX.fullmatch(plan_hash):
        return "a plan/v6 plan is stored with its sha256 plan_hash"
    if plan_json.get("plan_hash") != plan_hash:
        return "plan_hash disagrees with the hash the plan declares"
    return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _key(sha: str, config_hash: str):
    return (GradingPlanRecord.contract_sha256 == sha,
            GradingPlanRecord.config_hash == config_hash)


# ── lookups ──────────────────────────────────────────────────────────────────

async def find_live(db: AsyncSession, sha: str, *, config_hash: str
                    ) -> Optional[GradingPlanRecord]:
    """The one queued/building/ready row for this key, if any."""
    result = await db.execute(
        select(GradingPlanRecord)
        .where(*_key(sha, config_hash),
               GradingPlanRecord.status.in_(LIVE_STATUSES))
        .limit(1))
    return result.scalar_one_or_none()


async def get_ready(db: AsyncSession, sha: str, *, config_hash: str
                    ) -> Optional[GradingPlanRecord]:
    result = await db.execute(
        select(GradingPlanRecord)
        .where(*_key(sha, config_hash),
               GradingPlanRecord.status == "ready")
        .limit(1))
    return result.scalar_one_or_none()


# ── transitions ──────────────────────────────────────────────────────────────

async def insert_queued(db: AsyncSession, *, rubric_id: Optional[UUID],
                        contract_version: str, sha: str, config_hash: str
                        ) -> Tuple[GradingPlanRecord, bool]:
    """(row, created). A concurrent writer of the SAME key loses on
    `idx_grading_plans_one_live_per_contract_config` and gets the winner's row
    — the extraction-submit idempotency shape. Another config of the same
    contract is a different key and never collides. Commits."""
    _check_config_hash(config_hash)
    row = GradingPlanRecord(rubric_id=rubric_id, contract_version=contract_version,
                            contract_sha256=sha, config_hash=config_hash, status="queued")
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await find_live(db, sha, config_hash=config_hash)
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
                     sha: str, config_hash: str, plan_hash: Optional[str] = None) -> None:
    """building → ready, and every OTHER ready row of the SAME KEY → superseded,
    in ONE transaction (append-only: the old plan_json is never touched). A
    ready row of another config of this contract is not this plan's
    predecessor and is left alone — that is what lets v5 and v6 coexist.
    `plan_hash` is stored for a v6 plan (it must equal the hash the plan
    declares); a v5 plan has none."""
    assert wording_source in (WORDING_SEGMENTED, WORDING_PLACEHOLDER)
    _check_config_hash(config_hash)
    problem = _plan_identity_problem(plan_json, config_hash=config_hash, plan_hash=plan_hash)
    if problem is not None:
        raise ValueError(f"grading_plans {row_id}: {problem}")
    now = _now()
    await db.execute(
        update(GradingPlanRecord)
        .where(*_key(sha, config_hash),
               GradingPlanRecord.status == "ready",
               GradingPlanRecord.id != row_id)
        .values(status="superseded", updated_at=now))
    result = await db.execute(
        update(GradingPlanRecord)
        .where(GradingPlanRecord.id == row_id, GradingPlanRecord.status == "building",
               *_key(sha, config_hash))
        .values(status="ready", plan_json=plan_json, plan_version=plan_version,
                skeleton_json=skeleton_json, compiler_version=compiler_version,
                segmenter_model=segmenter_model, router_model=router_model,
                wording_source=wording_source, cost_usd=cost_usd,
                error_message=error_message, plan_hash=plan_hash,
                built_at=now, updated_at=now))
    if result.rowcount != 1:
        # Nothing may land — not even the supersede above — when the row is
        # not the building row of this key.
        await db.rollback()
        raise RuntimeError(f"grading_plans {row_id}: mark_ready found no building row "
                           f"for key ({sha[:12]}…, {config_hash[:12]})")
    await db.commit()


async def mark_failed(db: AsyncSession, row_id: UUID, error_message: str,
                      cost_usd: Decimal = Decimal("0")) -> None:
    await db.execute(
        update(GradingPlanRecord)
        .where(GradingPlanRecord.id == row_id,
               GradingPlanRecord.status.in_(("queued", "building")))
        .values(status="failed", error_message=error_message[:2000], cost_usd=cost_usd,
                updated_at=_now()))
    await db.commit()


async def requeue_for_rebuild(db: AsyncSession, sha: str, *, rubric_id: Optional[UUID],
                              contract_version: str, config_hash: str) -> GradingPlanRecord:
    """A DELIBERATE rebuild of a contract's plan (first use: D-13, owner-authorized
    2026-09-30 — plans built while the router lost JSON-string payloads).

    ONE transaction: the `ready` row → `superseded` (its plan_json untouched —
    append-only, W-1), then a new `queued` row. The order matters: the partial unique
    index admits one LIVE row per hash, and it is checked per statement. The build
    then takes the ordinary path (`claim_building` → `mark_ready`), and while it
    runs a grade finds a live builder and waits on it (OD-W3) instead of grading on
    the superseded plan. Existing drafts are untouched: a draft carries its own copy
    of the checks it was graded with. Refuses when the hash has no `ready` row (a
    queued/building row is already a build; nothing to rebuild)."""
    now = _now()
    result = await db.execute(
        update(GradingPlanRecord)
        .where(GradingPlanRecord.contract_sha256 == sha, GradingPlanRecord.config_hash == config_hash,
               GradingPlanRecord.status == "ready")
        .values(status="superseded", updated_at=now))
    if result.rowcount != 1:
        await db.rollback()
        raise RuntimeError(f"grading_plans {sha[:12]}/{config_hash[:12]}: no ready row to rebuild")
    # [035] the rebuild stays inside its own key: a v5 rebuild never retires a v6 plan
    row = GradingPlanRecord(rubric_id=rubric_id, contract_version=contract_version,
                            contract_sha256=sha, config_hash=config_hash, status="queued")
    db.add(row)
    await db.commit()
    await db.refresh(row)
    logger.info(f"plan_rebuild_requeued sha={sha[:12]} row_id={row.id} rubric_id={rubric_id}")
    return row


# ── the compile-time trigger (W-2), DB half ──────────────────────────────────

async def ensure_plan_for_contract(*, rubric_id: Optional[UUID], contract_json: Dict[str, Any],
                                   config_hash: str) -> Optional[UUID]:
    """A live row exists for this key → None (nothing to do — the hash is why
    a re-save of unchanged content costs nothing). Otherwise INSERT queued and
    return its id for the caller to enqueue. Own session."""
    sha = contract_sha256(contract_json)
    version = str(contract_json.get("contract_version") or "")
    async with get_db_context() as db:
        if await find_live(db, sha, config_hash=config_hash) is not None:
            return None
        row, created = await insert_queued(db, rubric_id=rubric_id, contract_version=version,
                                           sha=sha, config_hash=config_hash)
        return row.id if created else None


async def kick_plan_build(rubric_id: UUID) -> Optional[UUID]:
    """ensure + enqueue the plan of the ACTIVE grader for a rubric that was just
    compiled, never raises (the queued row is durable; the grade path builds on
    demand if the enqueue is lost — OD-W1). Called by the three contract-writing
    endpoints AFTER their commit, with the request session closed. Returns the new
    row id, if any.

    [owner 2026-10-18, plan at save] Under GRADER_ARCHITECTURE=v6 this queues the v6
    plan (its config key, `plan_build_v6.v6_config_hash`) and NO v5 plan — building a
    plan no grader will read is spend for nothing. Otherwise the v5 plan, as before."""
    try:
        from ..models.grading import Rubric
        async with get_db_context() as db:
            rubric = await db.get(Rubric, rubric_id)
            contract_json = rubric.contract_json if rubric is not None else None
        if not contract_json:
            return None
        from .grader_selection import grader_kind_for
        if grader_kind_for(str(rubric_id)) == "v6":
            from ..schemas.ontology_types import GradingRubricContract
            from .plan_build_v6 import v6_config_hash
            config_hash = v6_config_hash(GradingRubricContract.model_validate(contract_json))
        else:
            config_hash = V5_CONFIG_HASH
        row_id = await ensure_plan_for_contract(rubric_id=rubric_id, contract_json=contract_json,
                                                config_hash=config_hash)
        if row_id is None:
            return None
        from .cloud_tasks_service import enqueue_plan_build_task_or_log
        await enqueue_plan_build_task_or_log(row_id)
        return row_id
    except Exception:
        logger.exception("plan_build_kick_failed rubric_id=%s", rubric_id)
        return None
