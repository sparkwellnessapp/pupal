"""
The v6 block of a graded-test draft (PR_grader_v6_options.md §9.1) — M3 shape.

What a v6 grade records so that every number is RE-DERIVABLE by the one pricer
(`services/pricing_v6.price`) from this document alone: the plan's checks copied
in full (options with values, `requires`, `charge_group`, `evidence_required`…),
the model's selected option per check with its evidence, and the terminals and
selection facts the pricer reads. `DraftV6Content.to_view()` is the pricer's input.

M3 scope (Oct 6 amendment A.6): this is what the EVAL HARNESS needs. It rides on
the existing `GradedTestDraft` envelope as `GradedTestDraft.v6`; the envelope's
scope/criterion outcomes carry the PRICER's awards as a projection, so the v5
scorer measures v6 with byte-identical instrument code. Phase 4 owns the final
persisted shape (overlay, contract, legacy view, `criterion_explanations`).

No reasoning text is authoritative here: `explanations` is the grade-time record
the eval reads; the product's lines live in `criterion_explanations` (§7.6, Phase 4).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_serializer

from app.agents.grader.plan_schemas import PackRef, PlanCheckV6, TerminalPlanV6
from app.services.pricing_v6 import DraftV6View, SelectionView, ViewCheck, ViewTerminal

__all__ = ["CheckRecordV6", "ScopeRecordV6", "ExplanationV6", "UsageV6", "DraftV6Content",
           "v6_content"]

QuoteStatus = Literal["exact", "fuzzy", "not_found"]
GradedBy = Literal["llm", "skipped_no_answer", "failed", "excluded_by_selection"]
ReasoningSource = Literal["model", "fallback", "teacher_override"]


class CheckRecordV6(BaseModel):
    """One plan check as graded: the full plan copy + the model's selection."""
    plan: PlanCheckV6
    plan_index: int                                  # position in the plan: THE order
    model_option_id: Optional[str] = None            # None = no valid verdict (PRC-1 default)
    evidence_quote: str = ""
    absence_pointer_he: str = ""
    quote_status: Optional[QuoteStatus] = None       # every non-default option is checked
    flags: List[str] = Field(default_factory=list)   # FlagReason values


class UsageV6(BaseModel):
    """Tokens of one component (verifier or explainer), with its served model ids."""
    model: str
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    served_models: List[str] = Field(default_factory=list)
    model_fallback: bool = False                     # [AM-G18] a call served by another model


class ScopeRecordV6(BaseModel):
    question_id: str
    sub_question_id: Optional[str] = None
    graded_by: GradedBy
    retry_count: int = 0
    usage: Optional[UsageV6] = None                  # the verifier's calls for this scope
    flags: List[str] = Field(default_factory=list)   # scope-level (closed world, …)


class ExplanationV6(BaseModel):
    """The reasoning line for one CREDIT terminal (§7.5)."""
    terminal_id: str
    text_he: str
    source: ReasoningSource
    failed_rules: List[str] = Field(default_factory=list)   # E-1..E-5 that rejected a model line


class DraftV6Content(BaseModel):
    plan_schema: Literal["plan/v6"] = "plan/v6"
    plan_hash: str
    config_hash: str
    pack: PackRef
    verifier_prompt_version: str
    explainer_prompt_version: Optional[str] = None
    precision: Decimal
    terminals: List[TerminalPlanV6]
    view_terminals: List[ViewTerminal]               # scope placement, as the pricer reads it
    selection: SelectionView
    checks: List[CheckRecordV6]
    scopes: List[ScopeRecordV6]
    explanations: List[ExplanationV6] = Field(default_factory=list)
    verifier_usage: Optional[UsageV6] = None         # summed over scopes
    explainer_usage: Optional[UsageV6] = None
    # [eval only] the explainer's per-scope payloads, recorded for the §13.4 arms
    explainer_payloads: List[Dict[str, Any]] = Field(default_factory=list)

    @field_serializer("precision")
    def _sd(self, v: Decimal) -> str:
        return str(v)

    def to_view(self) -> DraftV6View:
        """The pricer's input — a pure function of this document."""
        return DraftV6View(
            precision=self.precision, terminals=list(self.view_terminals),
            selection=self.selection,
            checks=[ViewCheck(plan=c.plan, plan_index=c.plan_index,
                              model_option_id=c.model_option_id, quote_status=c.quote_status)
                    for c in self.checks])


def v6_content(draft) -> Optional[DraftV6Content]:
    """The typed v6 block of a `GradedTestDraft`, or None for a v3/v5 grade."""
    raw = getattr(draft, "v6", None)
    return None if raw is None else DraftV6Content.model_validate(raw)
