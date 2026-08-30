"""
FeedbackAgent — one call per test, strictly after pricing (PR-G4).

Two invariants live here and neither is negotiable:

* **Never before pricing.** The input is the priced verdicts, so the text can
  only describe a decision already made. A single call that both picked a
  verdict and justified it would let the prose anchor the verdict.
* **Never blocks the grade.** If the call fails, the draft lands with
  `feedback = None` and an INFO annotation. A teacher losing a whole graded test
  because a nice-to-have sentence could not be written is the opposite of
  review-first, not guess. `None` is a first-class wire state.

The model dial is separate from the grader's (OD10/OD-B3): feedback is prose, it
is cheaper, and tying it to the grading pin would make every grading-model
decision also a feedback decision.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Sequence, Tuple

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.feedback.prompt import (
    FEEDBACK_PROMPT_VERSION,
    FEEDBACK_SYSTEM_PROMPT,
    build_feedback_message,
)
from app.agents.feedback.schemas import FeedbackResponse
from app.schemas.graded_test_draft import (
    FeedbackBlock,
    FeedbackText,
    GradingAnnotation,
)
from app.schemas.ontology_types import AnnotationSeverity

logger = logging.getLogger(__name__)


class FeedbackAgent:
    """generate(scopes) -> (FeedbackBlock | None, [GradingAnnotation])."""

    def __init__(self, llm, model_version: str) -> None:
        self._model_version = model_version
        # A raw runner (the test fake) is used as-is; a real chat model gets the
        # structured-output wrapper. One seam, no branch at the call site.
        self._runner = (llm.with_structured_output(FeedbackResponse)
                        if hasattr(llm, "with_structured_output") else llm)

    async def generate(
        self,
        scopes: Sequence[Tuple[str, str]],
    ) -> Tuple[Optional[FeedbackBlock], List[GradingAnnotation]]:
        """`scopes` is [(scope_id, rendered_priced_view)] in document order."""
        try:
            parsed = await self._runner.ainvoke([
                SystemMessage(content=FEEDBACK_SYSTEM_PROMPT),
                HumanMessage(content=build_feedback_message(scopes)),
            ])
        except Exception as exc:                       # noqa: BLE001 — see docstring
            logger.warning("feedback_generation_failed",
                           extra={"exception_class": type(exc).__name__})
            return None, [GradingAnnotation(
                severity=AnnotationSeverity.INFO,
                target_id="",
                annotation_type="feedback_unavailable",
                message="לא נוצר משוב לתלמיד/ה עבור מבחן זה. הציון והנימוקים אינם מושפעים.",
                metadata={"exception_class": type(exc).__name__},
            )]

        by_scope = {s.scope_id: s.text for s in (parsed.scopes or [])}
        return FeedbackBlock(
            scopes={sid: FeedbackText(text=by_scope.get(sid, ""))
                    for sid, _ in scopes if by_scope.get(sid)},
            summary=FeedbackText(text=parsed.summary or ""),
            model_version=self._model_version,
            prompt_version=FEEDBACK_PROMPT_VERSION,
        ), []
