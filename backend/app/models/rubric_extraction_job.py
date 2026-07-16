"""
Rubric extraction job model — the async extraction lifecycle (PR-1, migration 012).

A job row is the durable record of one extraction: source doc (GCS), status,
progress heartbeat, result payload, and provenance. The result is NEVER
auto-saved as a rubric (ADR-2) — the teacher reviews it in the wizard and
rubric creation stays on the existing save_ontology_draft path, which stamps
rubrics.extraction_job_id to close the provenance chain.

Lifecycle: queued → extracting → completed | failed; failed → queued only via
the retry endpoint. Staleness of 'extracting' rows is COMPUTED from updated_at
(heartbeat) against settings.extraction_heartbeat_ttl_minutes — never stored.
DB CHECK rubric_extraction_jobs_status_consistency enforces which fields are
set per status (mirror it here in write paths, don't fight it).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from ..database import Base


def _utcnow() -> datetime:
    """Timezone-AWARE UTC now. Naive datetime.utcnow() binds through the
    driver's session timezone on TIMESTAMPTZ columns — a non-UTC session TZ
    would skew heartbeats and make fresh rows read as stale."""
    return datetime.now(timezone.utc)

# Statuses the ADR-3 partial unique index treats as "active"
ACTIVE_JOB_STATUSES = ("queued", "extracting")


class RubricExtractionJob(Base):
    __tablename__ = "rubric_extraction_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(20), nullable=False, default="queued")

    # Source document (durability: retry / re-extract without re-upload)
    source_gcs_uri = Column(Text, nullable=False)
    source_filename = Column(String(255), nullable=False)
    source_sha256 = Column(String(64), nullable=False)
    request_params = Column(JSONB, nullable=False, default=dict)

    # Result payload (ADR-2)
    result_json = Column(JSONB, nullable=True)      # ExtractRubricResponse.model_dump(mode="json")
    warnings = Column(JSONB, nullable=False, default=list)
    errors = Column(JSONB, nullable=False, default=list)
    requires_review = Column(Boolean, nullable=True)

    # Provenance (closes the extraction-side gap; grading already stamps these)
    prompt_version = Column(String(50), nullable=True)
    pipeline_version = Column(String(50), nullable=True)
    llm_model = Column(String(100), nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    retry_count = Column(Integer, nullable=True)
    finish_reason = Column(String(50), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    llm_config = Column(JSONB, nullable=True)       # effective env at run start

    # Progress / lifecycle
    progress_stage = Column(String(30), nullable=True)
    progress_detail = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    # Heartbeat: the runner touches this on every progress write; status reads
    # compute stale = (status='extracting' AND updated_at older than TTL).
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    user = relationship("User", back_populates="extraction_jobs")

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_JOB_STATUSES

    @property
    def is_terminal(self) -> bool:
        return self.status in ("completed", "failed")

    def __repr__(self):
        return (
            f"<RubricExtractionJob(id={self.id}, status={self.status}, "
            f"file={self.source_filename})>"
        )
