"""
Attach feedback to a priced draft (PR-G4).

Called from `grading_runner` AFTER the draft is built and priced, and after the
selection marks are resolved — so the input is the final verdict set, and the
text cannot influence a grade that is already decided.

Unconfigured is not a failure. Until a feedback model is pinned this returns the
draft untouched: production behaviour does not change by landing the code, only
by setting the dial (the same discipline as the grader pin).
"""
from __future__ import annotations

import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


def build_feedback_model():
    """The feedback chat model — ONE construction for every caller. [owner 2026-10-18]
    Sonnet 5.5 is built only with an explicit effort and thinking (AM-G18); the
    regenerate endpoint once built it bare, and every rewrite would have failed."""
    from app.agents.grader.llm_factory import NATIVE_SCHEMA_MODELS, build_chat_model
    knobs = ({"reasoning_effort": settings.feedback_effort, "thinking": settings.feedback_thinking}
             if settings.feedback_model_key in NATIVE_SCHEMA_MODELS else {})
    return build_chat_model(settings.feedback_model_provider, settings.feedback_model_key, **knobs)


def subject_has_math_notation(subject: Optional[str]) -> bool:
    """The subject's capability, from the registry — never a string compare (§3.3).
    An unknown or absent subject is the default profile's answer."""
    from app.subjects import UnknownSubject, get_profile
    try:
        return "math_notation" in get_profile(subject or "computer_science").modalities
    except UnknownSubject:
        return False


async def attach_feedback(draft, *, graded_test_id=None, usage: Optional[dict] = None,
                          subject: Optional[str] = None):
    """draft -> draft (with `feedback`, or unchanged). Never raises.

    `subject` — the rubric's subject; a math-notation subject's feedback is written in
    `\\( … \\)` spans (`FeedbackAgent(math_notation=…)`).

    `graded_test_id` only names the row in an A-8 billing alert. `usage`, when given,
    receives the call's model and tokens — [D-7] a v6 grade counts them in its cost."""
    if not settings.feedback_model_key:
        return draft

    from app.agents.feedback.agent import FeedbackAgent
    from app.agents.feedback.inputs import feedback_inputs

    # [D-6] only scopes the LLM graded, never one a selection group excluded (the runner
    # marks those first); v6 scopes are described from their own block (AM-G7)
    inputs = feedback_inputs(draft, draft.teacher_overrides)
    if not inputs:
        return draft

    try:
        llm = build_feedback_model()
    except Exception as exc:                        # noqa: BLE001
        logger.warning("feedback_model_unavailable",
                       extra={"exception_class": type(exc).__name__})
        return draft

    agent = FeedbackAgent(llm, model_version=settings.feedback_model_key,
                          graded_test_id=graded_test_id,
                          math_notation=subject_has_math_notation(subject))
    block, annotations = await agent.generate([(i.scope_id, i.rendered) for i in inputs])
    if usage is not None:
        usage.update(model=settings.feedback_model_key, **dict(agent.last_usage))

    if block is None:
        return draft.model_copy(update={
            "annotations": list(draft.annotations) + annotations})

    # stamp each text with the verdict vector it was written for, so staleness
    # is derived later rather than remembered
    stamped = {}
    for i in inputs:
        text = block.scopes.get(i.scope_id)
        if text is not None:
            stamped[i.scope_id] = text.model_copy(update={"basis_hash": i.basis})
    return draft.model_copy(update={
        "feedback": block.model_copy(update={"scopes": stamped}),
        "annotations": list(draft.annotations) + annotations,
    })
