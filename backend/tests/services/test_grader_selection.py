"""
PR-G1(a) — the production grader pin, config-driven (the owed R-4 seam).

Census B: `grading_runner` constructs `GraderAgent()` unconditionally and no
`GRADER_MODEL_KEY` exists, so the ratified pilot-bridge pin has no way to reach
production. This is that seam.

OD-G1.1 (ratified): DARK, DEFAULT-OFF. With nothing configured the selection is
byte-identically the historical v3 path, so landing the seam cannot move
production behaviour on its own.

The decision is a PURE function of config + the rubric being graded, so it is
tested with zero mocks and no client construction.
"""
from uuid import uuid4

import pytest

from app.services.grader_selection import grader_kind_for


PILOT = str(uuid4())


def _cfg(monkeypatch, **kw):
    import app.services.grader_selection as mod
    for k, v in kw.items():
        monkeypatch.setattr(mod.settings, k, v, raising=False)


def test_default_is_v3_dark_and_off(monkeypatch):
    """Nothing configured ⇒ the historical path. The seam must be inert until
    it is deliberately flipped."""
    _cfg(monkeypatch, grader_architecture="v3", grader_model_key=None,
         grader_plan_path=None, grader_plan_rubric_id=None)
    assert grader_kind_for(rubric_id=PILOT) == "v3"


def test_v5_only_for_the_rubric_its_plan_was_ratified_for(monkeypatch, tmp_path):
    """A GradingPlan is ratified against ONE rubric contract. The eval suite
    pins that with sha256 of the contract FILE; production stores contracts in
    a JSONB column, so that pin cannot bind here — the binding is the rubric id
    the plan was ratified for, named in config (OD-G1.4)."""
    plan = tmp_path / "plan.json"
    plan.write_text("{}", encoding="utf-8")
    _cfg(monkeypatch, grader_architecture="v5", grader_model_key="gemini-3.1-pro-preview",
         grader_plan_path=str(plan), grader_plan_rubric_id=PILOT)

    assert grader_kind_for(rubric_id=PILOT) == "v5"

    # any OTHER teacher's rubric has no ratified plan -> v3, never a guess
    assert grader_kind_for(rubric_id=str(uuid4())) == "v3"


def test_v5_requires_every_part_of_the_pin(monkeypatch, tmp_path):
    """A half-configured pin is a misconfiguration, not a v5 run: grading with
    a missing plan file or no model key would fail per-scope at call time,
    which is a worse place to discover it than here."""
    plan = tmp_path / "plan.json"
    plan.write_text("{}", encoding="utf-8")

    _cfg(monkeypatch, grader_architecture="v5", grader_model_key=None,
         grader_plan_path=str(plan), grader_plan_rubric_id=PILOT)
    assert grader_kind_for(rubric_id=PILOT) == "v3", "no model key ⇒ not a v5 run"

    _cfg(monkeypatch, grader_architecture="v5", grader_model_key="gemini-3.1-pro-preview",
         grader_plan_path=str(tmp_path / "missing.json"), grader_plan_rubric_id=PILOT)
    assert grader_kind_for(rubric_id=PILOT) == "v3", "absent plan file ⇒ not a v5 run"
