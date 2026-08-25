"""
LLM structured-output I/O schemas for GraderAgent.

These are the types passed to with_structured_output(QuestionGradingResponse)
and returned by the LLM per scope.

points_awarded is float (not Decimal) to avoid JSON schema friction with
LangChain's with_structured_output. The validator converts to Decimal at the
boundary — never does arithmetic in float.
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel


class TerminalGrade(BaseModel):
    """LLM's grade for one terminal criterion (leaf grading unit).

    FIELD ORDER IS LOAD-BEARING (grader-v2, 2026-08-25): pydantic
    preserves definition order into the JSON schema's properties, which sets the
    structured-output DECODE order — the model locates evidence, writes its
    reasoning, and only then commits the award (evidence-before-verdict,
    enforced mechanically by autoregressive conditioning). Do not reorder these
    fields without bumping GRADING_PROMPT_VERSION; the order is pinned by
    tests/agents/test_grader_agent.py::test_terminal_grade_decode_order_is_evidence_first.
    """

    terminal_criterion_id: str
    quote_text: str             # 1st: verbatim from student answer; "" if no evidence
    reasoning: str              # 2nd: Hebrew explanation, conditioned on the quote
    points_awarded: float       # 3rd: committed AFTER evidence+reasoning; Decimal in validator
    confidence: float           # 4th: 0.0–1.0 self-assessed certainty for this terminal


class QuestionGradingResponse(BaseModel):
    """LLM structured output for one GradableScope — one entry per terminal criterion."""

    grades: List[TerminalGrade]
