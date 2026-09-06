"""
Which grader runs in production — the config seam (PR-G1(a)), re-cut for
PLAN COMPILER v2's production wiring (PLAN_production_wiring.md §6; ruling W-4).

**v5 for every rubric.** Every compiled rubric has a compiled GradingPlan
(built at compile time, or in place at the first grade — `plan_build_runner`),
so the pilot-era binding of one hand-ratified plan file to one rubric id is
gone: no `grader_plan_path`, no `grader_plan_rubric_id`, no per-rubric
fallback to v3. The plan arrives from the caller (the runner resolves it from
the `grading_plans` store); this module never reads a file.

**One knob remains — the emergency rollback.** `GRADER_ARCHITECTURE=v3` sends
every grade down the historical v3 path, byte-for-byte, with no data change.
It is the only reason the v3 branch still exists here.

**The fit guard stays.** A ready plan is keyed by the contract's content hash,
so it fits by construction — but the guard is the SECOND, independent check
(OD-G1.4's lesson): a mismatched plan must fail here, before any spend, naming
the cause, never as a KeyError inside every scope after paying for them all.
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

from app.config import settings

logger = logging.getLogger(__name__)

GraderKind = Literal["v3", "v5"]


def grader_kind_for(rubric_id: Optional[str] = None) -> GraderKind:
    """v5 (W-4) unless the rollback knob says v3. The rubric id is accepted
    for the call sites' sake and for logging; it no longer decides anything."""
    if (settings.grader_architecture or "v5").lower() == "v3":
        return "v3"
    return "v5"


def _validate_plan_against(plan, gradable_test, precision) -> None:
    """Refuse a plan that does not fit the test it is about to grade.

    The eval runner refuses BEFORE spend for exactly this reason. Without it a
    mismatched plan surfaces as a KeyError inside each scope — loud, but only
    after every scope has been paid for, and reported as a grading failure
    rather than as the configuration error it is.
    """
    from app.agents.grader.plan_validator import validate_plan

    points, scopes = {}, {}
    for scope in gradable_test.scopes:
        key = (scope.question_id if scope.sub_question_id is None
               else f"{scope.question_id}.{scope.sub_question_id}")
        for criterion in scope.criteria:
            terminals = ([(sc.sub_criterion_id, sc.points) for sc in criterion.sub_criteria]
                         if criterion.sub_criteria
                         else [(criterion.criterion_id, criterion.points)])
            for tid, pts in terminals:
                points[tid] = pts
                scopes[tid] = key

    errors = validate_plan(plan, contract_terminal_points=points,
                           terminal_scopes=scopes, precision=precision)
    if errors:
        raise ValueError(
            f"plan {plan.plan_version!r} does not fit this test: "
            + "; ".join(errors[:5]))


def build_grader(rubric_id: Optional[str], numeric_policy, gradable_test=None, *,
                 plan=None, plan_wording_source: Optional[str] = None):
    """Construct the grader this rubric gets. The ONLY place production decides.

    `plan` is the resolved GradingPlan (the runner gets it from the store);
    `plan_wording_source` is stamped into the draft so a placeholder-worded
    grade stays distinguishable in the ledger (OD-W11). The v5 branch is lazy
    so the rollback path never imports the model factory.
    """
    kind = grader_kind_for(rubric_id)

    if kind == "v3":
        from app.agents.grader.grader import GraderAgent      # lazy: pulls langchain
        return GraderAgent(numeric_policy=numeric_policy)

    if plan is None:
        raise ValueError("grader-v5 needs a GradingPlan — the runner resolves it from "
                         "grading_plans (plan_build_runner.resolve_plan_for_grade)")
    if not settings.grader_model_key:
        # W-4 forbids a silent fallback: a missing model pin is a misconfiguration,
        # and the grade must fail naming it rather than quietly grade with v3.
        raise ValueError("GRADER_MODEL_KEY is unset — grader-v5 cannot construct its model")

    from app.agents.grader.grader_v5 import PlanVerifyGrader
    from app.agents.grader.llm_factory import build_chat_model

    # Validate BEFORE constructing the client: the plan check is free and its
    # failure names the real cause.
    if gradable_test is not None:
        _validate_plan_against(plan, gradable_test, numeric_policy.precision)

    llm = build_chat_model(settings.grader_model_provider, settings.grader_model_key)
    logger.info("grader_v5_selected rubric_id=%s model=%s plan_version=%s wording=%s",
                rubric_id, settings.grader_model_key, plan.plan_version, plan_wording_source)
    return PlanVerifyGrader(plan, numeric_policy, llm=llm,
                            model_version=settings.grader_model_key,
                            plan_wording_source=plan_wording_source)
