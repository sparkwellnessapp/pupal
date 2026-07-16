"""
Shared chain-extension helper for S10 revision actions.

Implements the deferred-FK insert ordering required to atomically extend the
graded-test revision chain (same transcription_id + rubric_id) without tripping
the partial unique index idx_graded_tests_one_leaf_per_chain.

The ordering (requires migration 010 — regraded_to_id FK DEFERRABLE INITIALLY DEFERRED):

  1. R1.regraded_to_id = r2_id  [flush]  → R1 exits partial index (0 leaves);
                                           FK to R2 deferred, not checked yet
  2. INSERT R2 (id=r2_id)       [flush]  → R2 sole leaf; R2→R1 immediate FK OK
  3. COMMIT                              → deferred R1→R2 FK resolved (R2 exists)

Called by: regrade, manual_edit, retry endpoints in app/api/v0/grading.py.
"""
import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grading import GradedTest

logger = logging.getLogger(__name__)


async def extend_chain(
    db: AsyncSession,
    source: GradedTest,
    *,
    new_status: str,
    new_rubric_contract_version: str,
    new_draft_json: dict | None,
) -> GradedTest:
    """
    Insert successor row R2, link source row R1 forward, and commit — all in
    one transaction using the deferred-FK ordering.

    Preconditions (callers must verify):
      - source.regraded_to_id IS NULL (leaf)
      - source.status satisfies the action's requirement

    Args:
        db: open AsyncSession (will be committed inside this function)
        source: the current leaf GradedTest being superseded
        new_status: 'pending' (regrade/retry) or 'draft' (manual_edit)
        new_rubric_contract_version: the rubric contract version to pin on R2
        new_draft_json: serialised draft dict for R2, or None

    Returns:
        the newly committed R2 GradedTest instance
    """
    r2_id = uuid4()
    now = datetime.now(timezone.utc)

    # ── Step 1: link R1 forward ───────────────────────────────────────────────
    # R1 exits the partial unique index (regraded_to_id IS NULL → is not NULL).
    # The FK R1.regraded_to_id → R2 is deferred; Postgres won't check it yet.
    source.regraded_to_id = r2_id
    source.updated_at = now
    await db.flush()

    # ── Step 2: insert R2 ────────────────────────────────────────────────────
    # R2 has regraded_to_id IS NULL → sole new leaf; partial index satisfied.
    # R2.regraded_from_id → R1: immediate FK, satisfied because R1 exists.
    r2 = GradedTest(
        id=r2_id,
        user_id=source.user_id,
        rubric_id=source.rubric_id,
        transcription_id=source.transcription_id,
        student_id=source.student_id,
        student_name=source.student_name,
        filename=source.filename,
        rubric_contract_version=new_rubric_contract_version,
        status=new_status,
        draft_json=new_draft_json,
        contract_json=None,
        regraded_from_id=source.id,
        regraded_to_id=None,
        created_at=now,
        updated_at=now,
    )
    db.add(r2)
    await db.flush()

    # ── Step 3: commit ────────────────────────────────────────────────────────
    # Deferred FK R1.regraded_to_id → R2 is now checked: R2 exists → valid.
    await db.commit()

    logger.info(
        "chain_extended",
        extra={
            "source_id": str(source.id),
            "successor_id": str(r2_id),
            "new_status": new_status,
            "new_rubric_contract_version": new_rubric_contract_version,
        },
    )
    return r2
