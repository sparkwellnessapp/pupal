"""
The production grader pin — OWNER VERDICT 2026-08-31 (Sonnet-5), made LIVE by
the owner's instruction of 2026-09-05/06 (PLAN_production_wiring.md, W-4).

This guards the verdict itself, so a later edit that quietly moves the pin has
to argue with a test instead of slipping through a config diff.
"""
from __future__ import annotations

from pathlib import Path


def test_production_grader_pin_is_sonnet_5():
    """The verdict, in config. gemini-3.1-pro failed T1-COST on 10/10 trials at
    2.5x the ceiling; Sonnet-5 grades 3.4x faster for 42% of the cost."""
    from app.config import settings

    assert settings.grader_model_key == "claude-sonnet-5"
    assert settings.grader_model_provider == "anthropic"


def test_the_prompt_half_of_the_pin_is_v54():
    """Model and prompt are a PACKAGE. v6 was killed on both arms and is kept
    only as a dated artifact. v5.4 (OD-W6) is v5.3's system prompt
    byte-for-byte plus the `counted` rule in the user message, rendered only
    when a counted check exists — for every other plan the messages are what
    the verdict measured."""
    from app.agents.grader.grader_v5 import VERIFIER_PROMPT_VERSION
    from app.agents.grader.verifier_prompt import VERIFIER_SYSTEM_PROMPT

    assert VERIFIER_PROMPT_VERSION == "grader-v5.4"
    assert "units_correct" not in VERIFIER_SYSTEM_PROMPT


def test_v5_is_the_default_and_v3_is_only_the_rollback():
    """W-4: v5 for every rubric. The old two-value activation (a plan file +
    the one rubric id it was ratified for) is gone with the file it bound."""
    from app.config import settings
    from app.services.grader_selection import grader_kind_for

    assert settings.grader_architecture == "v5"
    assert grader_kind_for("any-rubric") == "v5"
    assert not hasattr(settings, "grader_plan_path")
    assert not hasattr(settings, "grader_plan_rubric_id")
    assert not Path("app/agents/grader/plans").exists(), (
        "the file-based plan pin was retired; plans live in grading_plans")
