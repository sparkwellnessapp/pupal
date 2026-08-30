"""
Which grader runs in production — the config seam (PR-G1(a), the owed R-4 PR).

Before this module, `grading_runner` constructed `GraderAgent()` unconditionally
and no `GRADER_MODEL_KEY` existed, so the ratified pilot-bridge pin
(gemini-3.1-pro, plan `hobby_tvshow/v3` + `grader-v5.1`) had no way to reach
production at all.

**Dark, default-off (OD-G1.1).** With nothing configured the decision is the
historical v3 path, byte-for-byte. Landing this seam cannot move production
behaviour; flipping four env vars does, deliberately.

**Why the plan binds to a rubric ID and not to a contract hash (OD-G1.4 —
surfaced, owner to rule).** A `GradingPlan` is ratified against ONE rubric
contract, and the eval suite pins that with `sha256` of the contract *file
bytes*. Production has no contract file: the contract lives in a JSONB column,
so the same bytes do not exist and that pin cannot bind here. Re-deriving a
hash from the JSON would need a canonicalisation rule — a new invariant, and a
silent-drift risk the moment two serializers disagree. For a pilot with one
exam the honest binding is the explicit one: config names the rubric the plan
was ratified for. Every other teacher's rubric has no ratified plan and is
graded by v3 — a fallback, never a guess.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal, Optional

from app.config import settings

logger = logging.getLogger(__name__)

GraderKind = Literal["v3", "v5"]


def grader_kind_for(rubric_id: Optional[str]) -> GraderKind:
    """Pure: config + the rubric being graded -> which grader runs.

    Every part of the pin must be present. A half-configured pin is a
    misconfiguration, and resolving it to v5 would surface the mistake as a
    per-scope failure at call time — far from the cause, and after spend.
    """
    if (settings.grader_architecture or "v3").lower() != "v5":
        return "v3"

    if not settings.grader_model_key:
        logger.warning("grader_pin_incomplete", extra={"missing": "grader_model_key"})
        return "v3"

    plan_path = settings.grader_plan_path
    if not plan_path or not Path(plan_path).is_file():
        logger.warning("grader_pin_incomplete",
                       extra={"missing": "grader_plan_path", "value": plan_path})
        return "v3"

    ratified_for = settings.grader_plan_rubric_id
    if not ratified_for:
        logger.warning("grader_pin_incomplete",
                       extra={"missing": "grader_plan_rubric_id"})
        return "v3"

    if str(rubric_id) != str(ratified_for):
        # Not an error: this is every non-pilot teacher, every day.
        logger.info("grader_v5_not_ratified_for_rubric",
                    extra={"rubric_id": str(rubric_id)})
        return "v3"

    return "v5"


def build_grader(rubric_id: Optional[str], numeric_policy):
    """Construct the grader this rubric gets. The ONLY place production decides.

    The v5 branch is lazy on purpose: importing the plan schemas and the model
    factory costs nothing on the v3 path, which is every non-pilot grade.
    """
    kind = grader_kind_for(rubric_id)

    if kind == "v3":
        from app.agents.grader.grader import GraderAgent      # lazy: pulls langchain
        return GraderAgent(numeric_policy=numeric_policy)

    from app.agents.grader.grader_v5 import PlanVerifyGrader
    from app.agents.grader.llm_factory import build_chat_model
    from app.agents.grader.plan_schemas import GradingPlan

    plan = GradingPlan.model_validate_json(
        Path(settings.grader_plan_path).read_text(encoding="utf-8"))
    llm = build_chat_model(settings.grader_model_provider, settings.grader_model_key)
    logger.info("grader_v5_selected",
                extra={"rubric_id": str(rubric_id),
                       "model": settings.grader_model_key,
                       "plan_version": plan.plan_version})
    return PlanVerifyGrader(plan, numeric_policy, llm=llm,
                            model_version=settings.grader_model_key)
