"""
Grading runner (S8; execution substrate = Cloud Tasks since the 2026-08
migration).

run_grading(graded_test_id) drives a pending GradedTest row through
the full grading pipeline:
    pending → grading → draft   (or → failed on catastrophic error)

Design constraints:
  - Request-context-free: takes only a UUID, owns its own AsyncSession.
  - Runs INSIDE the Cloud Tasks request (/internal/grading-jobs/{id}/run —
    CPU guaranteed) or an asyncio task (inline dev mode).
  - CAS idempotency FIRST: UPDATE ... SET status='grading' WHERE id=:id AND
    status='pending'; zero rows ⇒ silent no-op. This is what makes the
    queue's maxAttempts=3 redelivery safe — the old load-then-check guard
    had a race window under duplicate delivery (two loads both see
    'pending' → the agent runs twice, double LLM cost).
  - Two-commit structure: the DB CHECK graded_tests_status_consistency
    requires status='grading' with draft_json IS NULL (the claim), then
    status='draft' with draft_json IS NOT NULL (commit 2).
  - model_dump(mode="json") is mandatory before JSONB writes: Decimal → str.
  - Recovery for stuck rows is grading_job_liveness (pending: dispatch
    backstop; grading: updated_at TTL) → 'failed' → the existing
    revision-retry chain.
"""
import asyncio
import logging
import math
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import update

from app.config import settings
from app.database import get_db_context
from app.models.grading import GradedTest
from app.models.transcription import Transcription
from app.models.grading import Rubric  # Rubric is co-located in grading.py
from app.schemas.transcription import TranscriptionContract
from app.schemas.ontology_types import GradingRubricContract
from app.services.gradable_compiler import compile as compile_gradable_test
from app.services.selection_scoring import ScopeScore, score_with_selection
from app.agents.grader.grader import MAX_CONCURRENT_SCOPES
from app.services.grader_selection import build_grader

logger = logging.getLogger(__name__)

# [PR-G2] Row-level budget. None ⇒ DERIVED per test from its own scope count,
# which is the only honest shape: a 3-scope test and a 15-scope test are one
# wave and three waves of the same per-scope wall. A float here is a flat
# override (tests; an operator capping a runaway).
GRADING_ROW_BUDGET_S = None


def _row_budget_s(scope_count: int) -> float:
    """timeout × waves + grace (spec §2 PR-G2). The grace covers compile,
    assembly, and one GA-3 retry landing inside the last wave — the per-scope
    wall can legitimately spend 2× on a retried scope."""
    if GRADING_ROW_BUDGET_S is not None:
        return float(GRADING_ROW_BUDGET_S)
    waves = math.ceil(max(scope_count, 1) / MAX_CONCURRENT_SCOPES)
    return settings.grader_llm_timeout_s * waves + settings.grader_row_grace_s


class AllScopesFailed(Exception):
    """Every scope failed to grade. Not a budget overrun — a distinct class, so
    the row's error_message says what actually happened to whoever reads it."""


class GradingBudgetExceeded(Exception):
    """The whole-task wall fired. Distinct from a per-scope expiry: the row
    has no exit of its own otherwise, and would sit in `grading` until the
    30-minute liveness reaper noticed."""

# gpt-4o pricing (per 1 000 tokens) — update when model changes
_INPUT_COST_PER_1K  = Decimal("0.005")
_OUTPUT_COST_PER_1K = Decimal("0.015")


def _compute_cost(input_tokens: int, output_tokens: int) -> Decimal:
    return (
        Decimal(input_tokens)  / 1000 * _INPUT_COST_PER_1K
        + Decimal(output_tokens) / 1000 * _OUTPUT_COST_PER_1K
    ).quantize(Decimal("0.0001"))


async def _claim_grading(db, graded_test_id: UUID) -> bool:
    """CAS pending→grading — the claim IS commit 1 (draft_json stays NULL, so
    the status-consistency CHECK holds). False = duplicate delivery or an
    already-advanced/terminal row: silent no-op."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(GradedTest)
        .where(GradedTest.id == graded_test_id,
               GradedTest.status == "pending")
        .values(status="grading", grading_started_at=now, updated_at=now)
    )
    await db.commit()
    return result.rowcount == 1


async def run_grading(graded_test_id: UUID) -> bool:
    """
    Entry point for the Cloud Tasks handler (and inline dev mode). Never
    propagates: failures land on the row as status='failed'.
    Returns True if this invocation ran the grade, False on no-op.
    """
    async with get_db_context() as db:
        try:
            if not await _claim_grading(db, graded_test_id):
                logger.info(
                    "run_grading_skipped",
                    extra={"graded_test_id": str(graded_test_id)},
                )
                return False
            await _do_grade(db, graded_test_id)
        except Exception:
            logger.exception(
                "run_grading_session_failure",
                extra={"graded_test_id": str(graded_test_id)},
            )
        return True


async def _do_grade(db, graded_test_id: UUID) -> None:
    # ── 1. Load the row just claimed by _claim_grading (status='grading') ────
    graded_test: GradedTest | None = await db.get(GradedTest, graded_test_id)
    if graded_test is None:
        logger.warning("run_grading_row_vanished",
                       extra={"graded_test_id": str(graded_test_id)})
        return

    try:
        # ── 3. Load contracts ─────────────────────────────────────────────────
        transcription: Transcription = await db.get(Transcription, graded_test.transcription_id)
        rubric: Rubric = await db.get(Rubric, graded_test.rubric_id)

        transcription_contract = TranscriptionContract.model_validate(
            transcription.contract_json
        )
        rubric_contract = GradingRubricContract.model_validate(rubric.contract_json)

        # ── 4. Compile GradableTest (S6) ─────────────────────────────────────
        gradable_test = compile_gradable_test(rubric_contract, transcription_contract)

        # ── 5. Grade (S7) ─────────────────────────────────────────────────────
        # [PR-G1(a)] the config seam — dark and default-off, so this is
        # the historical v3 construction until the pin is deliberately set.
        agent = build_grader(str(graded_test.rubric_id),
                             rubric_contract.numeric_policy,
                             gradable_test=gradable_test)
        budget = _row_budget_s(len(gradable_test.scopes))
        try:
            draft = await asyncio.wait_for(agent.grade(gradable_test), timeout=budget)
        except asyncio.TimeoutError as exc:
            raise GradingBudgetExceeded(
                f"grading exceeded its row budget of {budget:.0f}s for "
                f"{len(gradable_test.scopes)} scope(s)") from exc

        # [PR-G2] Every scope failed ⇒ this is a failed RUN, not a grade of zero.
        # Landing it as `draft` would offer the teacher an all-zero review screen
        # indistinguishable from a genuine zero — review-first, not guess.
        if draft.scope_outcomes and all(
                so.graded_by == "failed" for so in draft.scope_outcomes):
            raise AllScopesFailed(
                f"all {len(draft.scope_outcomes)} scope(s) failed to grade; "
                f"row is terminal — the chain continues via retry")

        # ── 6. Compute row-level aggregates (all Decimal, guard divide-by-zero) ──
        # PR-3: SELECTION-AWARE, via the one shared helper. The denominator is the
        # contract's ACHIEVABLE total — we do NOT re-sum scope points (that
        # re-derivation is what halved every selection-exam grade). Scopes beyond the
        # student's best-k in a choose-k group are EXCLUDED from both totals and
        # marked, so the review UI can say "not selected" instead of "scored 0".
        #
        # These marks are PROVISIONAL: a teacher override can flip which member is
        # best-k, so the approval gate recomputes them from post-override scores and
        # that recomputation is the authoritative one.
        scoring = score_with_selection(
            [
                ScopeScore(
                    question_id=so.question_id,
                    sub_question_id=so.sub_question_id,
                    awarded=so.points_awarded,
                )
                for so in draft.scope_outcomes
            ],
            rubric_contract,
        )
        if scoring.excluded:
            draft = draft.model_copy(update={
                "scope_outcomes": [
                    so.model_copy(update={"graded_by": "excluded_by_selection"})
                    if not scoring.is_counted((so.question_id, so.sub_question_id))
                    else so
                    for so in draft.scope_outcomes
                ]
            })

        total_possible = scoring.total_possible
        total_score    = scoring.total_score
        percentage     = (
            (total_score / total_possible * 100).quantize(Decimal("0.01"))
            if total_possible > 0
            else Decimal("0")
        )
        cost = _compute_cost(draft.total_input_tokens, draft.total_output_tokens)
        now2 = datetime.now(timezone.utc)

        # ── 7. COMMIT 2: grading → draft ──────────────────────────────────────
        # draft_json IS NOT NULL — satisfies graded_tests_status_consistency CHECK.
        # model_dump(mode="json") converts Decimal → str for JSONB serialisation.
        graded_test.draft_json          = draft.model_dump(mode="json")
        graded_test.draft_created_at    = now2
        graded_test.total_score         = total_score
        graded_test.total_possible      = total_possible
        graded_test.percentage          = percentage
        graded_test.llm_calls_count     = draft.llm_calls_count
        graded_test.grading_duration_ms = draft.grading_duration_ms
        graded_test.model_version       = draft.model_version
        graded_test.prompt_version      = draft.prompt_version
        graded_test.total_input_tokens  = draft.total_input_tokens
        graded_test.total_output_tokens = draft.total_output_tokens
        graded_test.total_cost_usd      = cost
        graded_test.status              = "draft"
        graded_test.updated_at          = now2
        await db.commit()

        logger.info(
            "grading_completed",
            extra={
                "graded_test_id": str(graded_test_id),
                "total_score": str(total_score),
                "total_possible": str(total_possible),
                "llm_calls": draft.llm_calls_count,
                "duration_ms": draft.grading_duration_ms,
                "total_input_tokens": draft.total_input_tokens,
                "total_output_tokens": draft.total_output_tokens,
                "total_cost_usd": str(cost),
            },
        )

    except Exception as e:
        # Catastrophic failure — status='failed' requires error_message IS NOT NULL.
        logger.exception(
            "grading_failed",
            extra={
                "graded_test_id": str(graded_test_id),
                "exception_class": type(e).__name__,
            },
        )
        await db.rollback()
        graded_test.status        = "failed"
        graded_test.error_message = f"{type(e).__name__}: {str(e)[:200]}"
        graded_test.updated_at    = datetime.now(timezone.utc)
        await db.commit()
