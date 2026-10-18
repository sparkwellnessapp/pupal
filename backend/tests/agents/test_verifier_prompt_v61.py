"""[AM-G21, owner rulings 2026-10-18 Item C] the grader-v6.1 verifier prompt: V-8 literal check,
the shown-mistake rule, V-3 in neutral third person — selectable by config, v6.0 unchanged and
still the production default. Pure: no provider."""
from __future__ import annotations

import re

import pytest

from app.agents.grader.verifier_prompt_v6 import (VERIFIER_V6_CORE, VERIFIER_V6_CORE_V61,
                                                  VERIFIER_V6_PROMPT_V61, VERIFIER_V6_PROMPT_VERSION,
                                                  verifier_v6_system_prompt)
from app.subjects import get_profile


def _rules(core: str):
    return {m.group(1): m.group(0) for m in re.finditer(r"(?ms)^(\d+)\. .*?(?=^\d+\. |\Z)", core)}


def test_v60_is_unchanged_and_the_default():
    from app.config import settings
    cs = get_profile("computer_science")
    assert verifier_v6_system_prompt(cs) == verifier_v6_system_prompt(cs, VERIFIER_V6_PROMPT_VERSION)
    assert settings.v6_verifier_prompt_version == VERIFIER_V6_PROMPT_VERSION == "grader-v6.0"
    assert "LITERALLY" not in verifier_v6_system_prompt(cs)


def test_v61_is_v60_with_rule_4_reworded_and_rules_9_10_added():
    old, new = _rules(VERIFIER_V6_CORE), _rules(VERIFIER_V6_CORE_V61)
    assert set(new) == set(old) | {"9", "10"}
    assert all(new[k] == old[k] for k in old if k != "4")             # every other rule, byte for byte
    assert "neutral third" in new["4"] and "first person" in new["4"]
    assert "CHECK THE LABEL LITERALLY" in new["9"] and "highest eligible option" in new["9"]
    assert "A SHOWN MISTAKE IS SELECTED" in new["10"] and "quote the line" in new["10"]


def test_v61_examples_carry_no_fixture_vocabulary():
    """General rules with domain-shifted examples: nothing from the CS fixtures' GT or wording."""
    added = (_rules(VERIFIER_V6_CORE_V61)["4"] + _rules(VERIFIER_V6_CORE_V61)["9"]
             + _rules(VERIFIER_V6_CORE_V61)["10"])
    for token in ("Hobby", "TvShow", "tvRate", "Channel", "מערך", "מונה", "array", "counter", "index"):
        assert token not in added, token


def test_unknown_version_refused():
    with pytest.raises(ValueError):
        verifier_v6_system_prompt(get_profile("computer_science"), "grader-v9")


def test_the_grader_runs_and_stamps_the_configured_version():
    import asyncio

    from app.agents.grader.grader_v6 import OptionsVerifyGrader
    from app.agents.grader.plan_schemas import GradingPlanV6
    from tests.agents.test_grader_v6 import MODEL, _Fake, _full
    from tests.grading_eval_suite.fixtures import SUITE_DIR, load_bundle
    plan = GradingPlanV6.model_validate_json(
        (SUITE_DIR / "plans" / "v6" / "hobby_tvshow.plan.json").read_text(encoding="utf-8"))
    bundle = load_bundle("din_ezra", require_gt=False)
    agent = OptionsVerifyGrader(plan, bundle.rubric_contract, llm=_Fake(_full), model_version=MODEL,
                                profile=get_profile("computer_science"),
                                verifier_prompt_version=VERIFIER_V6_PROMPT_V61)
    assert "CHECK THE LABEL LITERALLY" in agent._system
    draft = asyncio.run(agent.grade(bundle.gradable_test))
    assert draft.v6["verifier_prompt_version"] == VERIFIER_V6_PROMPT_V61
    assert draft.prompt_version.startswith(VERIFIER_V6_PROMPT_V61)


def test_the_eval_runner_reports_the_configured_v6_version():
    from tests.grading_eval_suite.runner import _effective_prompt_version_for
    assert _effective_prompt_version_for({"architecture": "v6"}) == VERIFIER_V6_PROMPT_VERSION
    assert _effective_prompt_version_for({"architecture": "v6",
                                          "verifier_prompt_version": VERIFIER_V6_PROMPT_V61}) == "grader-v6.1"
