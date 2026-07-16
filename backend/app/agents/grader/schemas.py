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
    """LLM's grade for one terminal criterion (leaf grading unit)."""

    terminal_criterion_id: str
    points_awarded: float       # converted to Decimal in validator; float avoids schema friction
    reasoning: str              # Hebrew explanation
    quote_text: str             # verbatim from student answer; "" if no evidence
    confidence: float           # 0.0–1.0 self-assessed certainty for this terminal


class QuestionGradingResponse(BaseModel):
    """LLM structured output for one GradableScope — one entry per terminal criterion."""

    grades: List[TerminalGrade]
