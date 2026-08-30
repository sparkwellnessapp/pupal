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


async def attach_feedback(draft):
    """draft -> draft (with `feedback`, or unchanged). Never raises."""
    if not settings.feedback_model_key:
        return draft

    from app.agents.feedback.agent import FeedbackAgent
    from app.agents.feedback.prompt import render_scope_for_feedback
    from app.agents.feedback.staleness import basis_hash, flatten_checks
    from app.agents.grader.llm_factory import build_chat_model

    # only scopes the LLM actually graded have verdicts to describe
    scopes = [(so.question_id if so.sub_question_id is None
               else f"{so.question_id}.{so.sub_question_id}", so)
              for so in draft.scope_outcomes if so.graded_by == "llm"]
    if not scopes:
        return draft

    try:
        llm = build_chat_model(settings.feedback_model_provider,
                               settings.feedback_model_key)
    except Exception as exc:                        # noqa: BLE001
        logger.warning("feedback_model_unavailable",
                       extra={"exception_class": type(exc).__name__})
        return draft

    agent = FeedbackAgent(llm, model_version=settings.feedback_model_key)
    block, annotations = await agent.generate(
        [(sid, render_scope_for_feedback(so)) for sid, so in scopes])

    if block is None:
        return draft.model_copy(update={
            "annotations": list(draft.annotations) + annotations})

    # stamp each text with the verdict vector it was written for, so staleness
    # is derived later rather than remembered
    stamped = {}
    for sid, so in scopes:
        text = block.scopes.get(sid)
        if text is not None:
            stamped[sid] = text.model_copy(
                update={"basis_hash": basis_hash(list(flatten_checks(so)))})
    return draft.model_copy(update={
        "feedback": block.model_copy(update={"scopes": stamped}),
        "annotations": list(draft.annotations) + annotations,
    })
