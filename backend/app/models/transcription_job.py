"""
Transcription job model — durable per-document batch transcription
(Cloud Tasks migration, migration 016).

One row per PDF in a batch, created in the SAME COMMIT as the batch row, so
Σ jobs == grading_batches.test_count always: "in flight" is a fact, never an
inference over absence (the phantom-item class the 015 ledger + Δ15 residue
approximated is structurally dead).

Lifecycle: queued → running → completed | failed; failed/expired → queued only
via the per-document retry endpoint (source PDF is in GCS — no re-upload).
Liveness is LIV-1 via `transcription_job_liveness`: 'queued' runs on
created_at (dispatch backstop — batch backlog makes long waits honest),
'running' on updated_at (heartbeat sidecar, ~60s). DB CHECK
transcription_jobs_status_consistency shapes every write — mirror it, don't
fight it. transcription_id is set in the same commit that INSERTs the
transcriptions row, but is deliberately NOT in the CHECK (FK is SET NULL).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..database import Base


def _utcnow() -> datetime:
    """Timezone-AWARE UTC now (see rubric_extraction_job._utcnow: naive
    utcnow() binds through the session timezone on TIMESTAMPTZ and skews
    heartbeats)."""
    return datetime.now(timezone.utc)


ACTIVE_TRANSCRIPTION_JOB_STATUSES = ("queued", "running")


class TranscriptionJob(Base):
    __tablename__ = "transcription_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True),
                     ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    batch_id = Column(UUID(as_uuid=True),
                      ForeignKey("grading_batches.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    rubric_id = Column(UUID(as_uuid=True),
                       ForeignKey("rubrics.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False, default="queued")

    # Source document (durability: per-doc retry without re-upload)
    source_gcs_object_path = Column(Text, nullable=False)
    source_filename = Column(String(500), nullable=True)
    doc_priority = Column(Integer, nullable=False, default=0)
    # B9 append idempotency (migration 017): client-generated per-file UUID;
    # (batch_id, client_file_id) partial-unique — a retried append returns the
    # existing job. NULL on pre-017 rows and legacy-created jobs.
    client_file_id = Column(UUID(as_uuid=True), nullable=True)

    # Outcome
    transcription_id = Column(UUID(as_uuid=True),
                              ForeignKey("transcriptions.id", ondelete="SET NULL"),
                              nullable=True)
    error_message = Column(Text, nullable=True)
    net_verdict = Column(String(30), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)

    # Lifecycle clocks (LIV-1: queued→created_at, running→updated_at heartbeat)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=_utcnow,
                        onupdate=_utcnow, nullable=False)

    batch = relationship("GradingBatch", back_populates="transcription_jobs")
    transcription = relationship("Transcription")

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_TRANSCRIPTION_JOB_STATUSES

    def __repr__(self):
        return (f"<TranscriptionJob(id={self.id}, status={self.status}, "
                f"file={self.source_filename})>")
