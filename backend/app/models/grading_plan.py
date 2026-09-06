"""
grading_plans — a compiled GradingPlan per rubric contract (migration 026).

The ORM mirrors the migrated schema; it does not generate it. Lifecycle,
uniqueness and the hash live in `app/services/plan_store.py` — the only writer.
The teacher never sees a row of this table (ruling W-3): no API response
carries it, and nothing here is teacher-facing text.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ..database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GradingPlanRecord(Base):
    """One build of a plan for one contract hash. `plan_json` is written once
    (building → ready) and never rewritten; a rebuild is a new row and the old
    `ready` row becomes `superseded` (W-1, append-only)."""

    __tablename__ = "grading_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rubric_id = Column(UUID(as_uuid=True), ForeignKey("rubrics.id", ondelete="SET NULL"),
                       nullable=True, index=True)
    contract_version = Column(Text, nullable=False)
    contract_sha256 = Column(Text, nullable=False)     # THE key; partial-unique among live rows
    status = Column(String(20), nullable=False, default="queued")
    plan_version = Column(Text, nullable=True)
    plan_json = Column(JSONB(none_as_null=True), nullable=True)
    skeleton_json = Column(JSONB(none_as_null=True), nullable=True)
    compiler_version = Column(Text, nullable=True)
    segmenter_model = Column(Text, nullable=True)
    router_model = Column(Text, nullable=True)
    wording_source = Column(String(20), nullable=True)   # segmented | placeholder
    cost_usd = Column(Numeric(10, 4), nullable=False, server_default=text("0"))
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)   # the building heartbeat
    built_at = Column(DateTime(timezone=True), nullable=True)
