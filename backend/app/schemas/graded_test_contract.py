"""
GradedTestContract — frozen, provenance-preserving approved grade.

Produced by compile_graded_test() (app/services/graded_test_contract_compiler.py)
at the moment the teacher approves a GradedTestDraft.

Stored in graded_tests.contract_json.

Provenance design (D4): every terminal carries both ai_points_awarded (what
the AI awarded, immutable record) and final_points_awarded (what was approved),
plus was_overridden. This makes "where did the teacher disagree with the AI" a
first-class, queryable property of every approved grade.

The legacy GradedTestContract in ontology_types.py is from the deprecated
TestGraderAgent system and has a different shape. This is the S9 contract.
"""
from __future__ import annotations

from decimal import Decimal
from typing import List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, field_serializer

from app.schemas.ontology_types import AnswerQuotation


class ContractTerminalOutcome(BaseModel):
    """Frozen, provenance-preserving record for one terminal criterion."""
    model_config = {"frozen": True}

    terminal_id: str                        # criterion_id (leaf) or sub_criterion_id
    terminal_kind: Literal["criterion", "sub_criterion"]
    description: str
    points_possible: Decimal

    # Provenance — AI's original grade (immutable, never changes after approval)
    ai_points_awarded: Decimal
    ai_reasoning: str
    ai_evidence_quote: Optional[AnswerQuotation] = None

    # Teacher decision
    was_overridden: bool                    # True iff teacher changed the points
    teacher_comment: Optional[str] = None
    final_points_awarded: Decimal           # authoritative: override if present, else AI

    @field_serializer("points_possible", "ai_points_awarded", "final_points_awarded")
    def _sd(self, v: Decimal) -> str:
        return str(v)


class ContractScopeOutcome(BaseModel):
    """Frozen scope record. final_points_awarded = Σ terminal_outcomes[*].final_points_awarded."""
    model_config = {"frozen": True}

    scope_kind: Literal["direct", "sub_question"]
    question_id: str
    sub_question_id: Optional[str] = None
    points_possible: Decimal
    final_points_awarded: Decimal
    # PR-3 — the AUTHORITATIVE selection mark, frozen at approval.
    # False ⇒ this scope belongs to a "choose k of N" member that did not make the
    # student's best-k, so it contributes to NEITHER the numerator nor the
    # denominator. Recomputed by the approval gate from POST-override scores (a
    # teacher override can flip which member is best-k), which is why the draft's
    # provisional mark is not simply copied here.
    # Default True ⇒ every stored contract (all selection-free) re-parses unchanged.
    counted_in_total: bool = True
    terminal_outcomes: List[ContractTerminalOutcome]

    @field_serializer("points_possible", "final_points_awarded")
    def _sd(self, v: Decimal) -> str:
        return str(v)


class GradedTestContract(BaseModel):
    """
    Frozen, approved graded test. Written to graded_tests.contract_json at approval.

    contract_version lives inside this JSONB — no separate column (consistent
    with the transcription contract pattern).
    """
    model_config = {"frozen": True}

    schema_version: str = "1.0"
    contract_version: str               # fresh uuid4 at approval
    rubric_contract_version: str        # rubric version this was graded against (pinned)
    transcription_contract_version: str
    model_version: str                  # LLM model that produced the draft
    prompt_version: str

    scope_outcomes: List[ContractScopeOutcome]
    total_score: Decimal                # Σ scope final_points_awarded
    total_possible: Decimal
    percentage: Decimal                 # total_score / total_possible * 100 (0 if /0)
    approved_at: str                    # ISO-8601 UTC timestamp

    @field_serializer("total_score", "total_possible", "percentage")
    def _sd(self, v: Decimal) -> str:
        return str(v)
