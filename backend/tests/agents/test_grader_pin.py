"""
The production grader pin — OWNER VERDICT 2026-08-31: Sonnet-5.

This guards the verdict itself, so a later edit that quietly moves the pin has
to argue with a test instead of slipping through a config diff.
"""
from __future__ import annotations

from pathlib import Path

PLAN_IN_IMAGE = Path("app/agents/grader/plans/hobby_tvshow.plan.json")
PLAN_IN_SUITE = Path("tests/grading_eval_suite/plans/hobby_tvshow.plan.json")


def test_production_grader_pin_is_sonnet_5():
    """The verdict, in config. gemini-3.1-pro failed T1-COST on 10/10 trials at
    2.5x the ceiling; Sonnet-5 grades 3.4x faster for 42% of the cost."""
    from app.config import settings

    assert settings.grader_model_key == "claude-sonnet-5"
    assert settings.grader_model_provider == "anthropic"


def test_the_prompt_half_of_the_pin_is_v53():
    """Model and prompt are a PACKAGE. v6 was killed on both arms and is kept
    only as a dated artifact."""
    from app.agents.grader.grader_v5 import VERIFIER_PROMPT_VERSION

    assert VERIFIER_PROMPT_VERSION == "grader-v5.3"


def test_the_ratified_plan_ships_inside_the_image():
    """The Dockerfile is `COPY app/ ./app/` and nothing else.

    A plan under tests/ does not exist in production: `Path(...).is_file()`
    fails, `grader_kind_for` logs `grader_pin_incomplete` and falls back to v3
    — and the fallback looks exactly like a working system. This is why the
    plan has a production copy at all.
    """
    from app.config import settings

    assert PLAN_IN_IMAGE.is_file(), f"{PLAN_IN_IMAGE} is missing from the image tree"
    assert settings.grader_plan_path == str(PLAN_IN_IMAGE).replace("\\", "/")
    assert Path(settings.grader_plan_path).is_file()


def test_the_shipped_plan_is_byte_identical_to_the_one_the_gate_measures():
    """Two copies, one plan. If they drift, production grades against something
    the eval suite has never scored — and every gate result becomes a claim
    about a different system."""
    assert PLAN_IN_IMAGE.read_bytes() == PLAN_IN_SUITE.read_bytes(), (
        "the production plan and the eval suite's plan have diverged")


def test_the_pin_is_still_dark_until_a_rubric_is_bound():
    """Deliberate, and the reason is written down.

    No production rubric has a ratified plan (checked 2026-08-31: 6 rubrics,
    none is this plan's exam, graded_tests = 0). Flipping architecture to v5
    without `grader_plan_rubric_id` makes grader_kind_for log
    `grader_pin_incomplete` on EVERY grade and fall back to v3 regardless — a
    warning that always fires, which is the INV-6 mistake this codebase already
    paid for once.

    When this test fails because someone set both values, that is the pin going
    live: update it deliberately, do not delete it.
    """
    from app.config import settings

    if settings.grader_architecture == "v5":
        assert settings.grader_plan_rubric_id, (
            "architecture is v5 with no rubric binding — every grade will warn "
            "and silently fall back to v3")
    else:
        assert settings.grader_plan_rubric_id is None
