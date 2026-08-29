"""
Runner policy pins [§7 of the mission] — config discipline, the D6-absent model
pin, wall bound + single re-run [D7][G-3], suite-hash coverage [D3].
Zero API calls: the agent is always faked.
"""
from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from pathlib import Path

import pytest

from . import synth
from . import runner as runner_mod
from .runner import (
    _hashed_paths,
    _load_config,
    _assert_draft_stamp,
    grade_fixture_trials,
)


# ---------------------------------------------------------------------------
# Config discipline (registry-era: model_key only; legacy keys refused)
# ---------------------------------------------------------------------------

def test_config_legacy_keys_refused(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "configs"
    cfg_dir.mkdir()
    (cfg_dir / "bad.json").write_text(
        json.dumps({"model": "gpt-4o", "price_per_1m_input": 1}), encoding="utf-8")
    with pytest.raises(SystemExit, match="legacy"):
        _load_config("bad", suite_dir=tmp_path)
    (cfg_dir / "nokey.json").write_text(json.dumps({"cost_ceiling": 0.1}), encoding="utf-8")
    with pytest.raises(SystemExit, match="model_key"):
        _load_config("nokey", suite_dir=tmp_path)


def test_shipped_config_resolves():
    cfg = _load_config("gpt-4o")
    from tests.eval_common.models_registry import spec
    s = spec(cfg["model_key"])
    assert s.provider == "openai" and s.model_id == "gpt-4o"
    assert cfg["cost_ceiling"] == 0.10           # Tier-1 default ceiling [§6]


def test_draft_stamp_assertion():
    """[DL-4 successor, seam era 2026-08-28] provenance may never claim a model
    the SUT didn't run — asserted per trial against the draft's OWN stamp (what
    actually ran), which is strictly stronger than the old env-pin check."""
    from tests.eval_common.models_registry import spec
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    draft = synth.draft_from_gt(bundle, gt)      # stamps model_version="gpt-4o"
    _assert_draft_stamp(draft, spec("gpt-4o"))   # match: no raise
    _assert_draft_stamp(None, spec("gpt-5.5"))   # invalid trial: nothing to assert
    with pytest.raises(SystemExit, match="stamp"):
        _assert_draft_stamp(draft, spec("gpt-5.5"))


def test_v5_config_shape_rules(tmp_path):
    """architecture v5 requires a plan; v3 refuses v5-only keys."""
    import json
    cfgdir = tmp_path / "configs"; cfgdir.mkdir()
    (cfgdir / "bad1.json").write_text(json.dumps(
        {"model_key": "gpt-4o", "architecture": "v5"}), encoding="utf-8")
    with pytest.raises(SystemExit, match="requires 'plan'"):
        _load_config("bad1", suite_dir=tmp_path)
    (cfgdir / "bad2.json").write_text(json.dumps(
        {"model_key": "gpt-4o", "plan": "plans/x.json"}), encoding="utf-8")
    with pytest.raises(SystemExit, match="v5-only"):
        _load_config("bad2", suite_dir=tmp_path)


# ---------------------------------------------------------------------------
# Wall bound + exactly one transport re-run [D7][DL-3][G-3]
# ---------------------------------------------------------------------------

class _HangingAgent:
    def __init__(self):
        self.calls = 0
    async def grade(self, gradable):
        self.calls += 1
        await asyncio.sleep(5)


class _GoodAgent:
    def __init__(self, draft):
        self.calls = 0
        self._draft = draft
    async def grade(self, gradable):
        self.calls += 1
        return self._draft


def test_wall_bound_invalidates_after_one_rerun(monkeypatch):
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    agent = _HangingAgent()
    trials = asyncio.run(grade_fixture_trials(
        agent, bundle, k=1, wall_s=0.05, cost_ceiling=0.10,
        price=None, drafts_dir=None))
    (draft, meta), = trials
    assert draft is None
    assert agent.calls == 2                       # first attempt + exactly ONE re-run
    assert meta["invalid_reason"] and "wall" in meta["invalid_reason"]
    assert meta["rerun_count"] == 1 and "wall" in meta["rerun_reason"]


def test_good_trial_single_call_and_draft_persisted(tmp_path):
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    draft = synth.draft_from_gt(bundle, gt)
    agent = _GoodAgent(draft)
    drafts_dir = tmp_path / "drafts"
    drafts_dir.mkdir()
    trials = asyncio.run(grade_fixture_trials(
        agent, bundle, k=2, wall_s=5.0, cost_ceiling=0.10,
        price=None, drafts_dir=drafts_dir))
    assert agent.calls == 2                       # k trials, no re-runs
    assert all(d is not None for d, _ in trials)
    persisted = sorted(p.name for p in drafts_dir.glob("synthetic_r*.json")
                       if not p.name.endswith(".meta.json"))
    assert persisted == ["synthetic_r0.json", "synthetic_r1.json"]
    # ...and each draft has its meta sidecar (latency/rerun facts for score_only)
    assert (drafts_dir / "synthetic_r0.meta.json").exists()


def test_transport_failed_draft_triggers_one_rerun():
    """A completed draft whose failed scopes are transport-class is retryable [D7]."""
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    s = {x.question_id: x for x in bundle.gradable_test.scopes}
    good = synth.draft_from_gt(bundle, gt).scope_outcomes[0]
    fail_t, ann = synth.make_failure_outcome(s["q2"], "APIConnectionError")
    bad_draft = synth.make_draft(bundle, [good, fail_t], [ann])

    class _FlakyAgent:
        def __init__(self):
            self.calls = 0
        async def grade(self, gradable):
            self.calls += 1
            return bad_draft if self.calls == 1 else synth.draft_from_gt(bundle, gt)

    agent = _FlakyAgent()
    trials = asyncio.run(grade_fixture_trials(
        agent, bundle, k=1, wall_s=5.0, cost_ceiling=0.10, price=None, drafts_dir=None))
    (draft, meta), = trials
    assert agent.calls == 2 and meta["rerun_count"] == 1
    assert draft is not None and meta["invalid_reason"] is None


def test_parse_failed_draft_not_rerun():
    """[R6] parse failure is deterministic model behavior — scored, never re-run."""
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    s = {x.question_id: x for x in bundle.gradable_test.scopes}
    good = synth.draft_from_gt(bundle, gt).scope_outcomes[0]
    fail_p, ann = synth.make_failure_outcome(s["q2"], "ValueError")
    parse_draft = synth.make_draft(bundle, [good, fail_p], [ann])
    agent = _GoodAgent(parse_draft)
    trials = asyncio.run(grade_fixture_trials(
        agent, bundle, k=1, wall_s=5.0, cost_ceiling=0.10, price=None, drafts_dir=None))
    (draft, meta), = trials
    assert agent.calls == 1 and meta["rerun_count"] == 0
    assert draft is not None


# ---------------------------------------------------------------------------
# Suite hash coverage [D3]
# ---------------------------------------------------------------------------

def test_suite_hash_covers_registry_and_snapshots():
    paths = [p.as_posix() for p in _hashed_paths()]
    assert any(p.endswith("eval_common/models_registry.py") for p in paths)
    assert any("/grading_eval_suite/scoring.py" in p for p in paths)
    # configs are DELIBERATELY excluded (the A/B knob; sibling precedent)
    assert not any("/configs/" in p for p in paths)


# ---------------------------------------------------------------------------
# numeric_policy passthrough (the one construction pin v0 needs) [§10]
# ---------------------------------------------------------------------------

def test_agent_factory_receives_contract_policy(monkeypatch):
    captured = {}

    class _FakeAgent:
        async def grade(self, gradable):
            raise AssertionError("not invoked in this test")

    def factory(numeric_policy):
        captured["policy"] = numeric_policy
        return _FakeAgent()

    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    agent = runner_mod.build_agent(bundle, agent_factory=factory)
    assert isinstance(agent, _FakeAgent)
    assert captured["policy"] is bundle.rubric_contract.numeric_policy


# ---------------------------------------------------------------------------
# sut_hash (owner ruling 2026-08-27, BLOCKING for E7): suite_hash pins the
# INSTRUMENT; nothing pinned the SYSTEM UNDER TEST. Two runs are only
# comparable if the grader-path code is byte-identical, and that was an
# assumption rather than a recorded fact. sut_hash makes it a fact.
# ---------------------------------------------------------------------------

def test_sut_hash_covers_exactly_the_grader_path():
    from .runner import _sut_paths, _sut_hash
    names = [p.as_posix() for p in _sut_paths()]
    expected_suffixes = [
        "app/agents/grader/grader.py", "app/agents/grader/prompt.py",
        "app/agents/grader/schemas.py", "app/agents/grader/validator.py",
        # grader-v5 path (mission V5-A) — the SUT grew; the hash must see it
        "app/agents/grader/plan_schemas.py", "app/agents/grader/plan_validator.py",
        "app/agents/grader/pricer.py", "app/agents/grader/verifier_prompt.py",
        "app/agents/grader/grader_v5.py", "app/agents/grader/llm_factory.py",
        "app/agents/grader/grader_cascade.py",   # Stage 3, FP2
        "app/services/gradable_compiler.py", "app/services/selection_scoring.py",
        "app/schemas/graded_test_draft.py", "app/schemas/gradable.py",
        "app/schemas/ontology_types.py",
    ]
    for suf in expected_suffixes:
        assert any(n.endswith(suf) for n in names), f"sut_hash misses {suf}"
    assert len(names) == len(expected_suffixes), f"unexpected extras: {names}"
    for p in _sut_paths():
        assert p.exists(), f"sut path missing on disk: {p}"
    h = _sut_hash()
    assert len(h) == 16 and h == _sut_hash()        # stable, short-form


def test_sut_hash_is_independent_of_suite_hash():
    """They must be separate signals: the instrument can change without the SUT
    changing, and vice versa. A single combined hash would make a C2<->E7
    comparison unverifiable — exactly the gap this closes."""
    from .runner import _sut_hash, _suite_hash, _sut_paths, _hashed_paths
    assert _sut_hash() != _suite_hash()
    sut = {p.as_posix() for p in _sut_paths()}
    suite = {p.as_posix() for p in _hashed_paths()}
    assert not (sut & suite), "sut_hash and suite_hash must not share files"


def test_provenance_carries_sut_hash():
    from tests.eval_common.models_registry import spec
    from .runner import _provenance, _sut_hash
    prov = _provenance("gpt-4o", {"cost_ceiling": 0.10, "prior_context": False},
                       spec("gpt-4o"), mode="grade", k=5, fixtures=["dan_basiuk"],
                       scopes=None)
    assert prov["sut_hash"] == _sut_hash()
    assert prov["suite_hash"] != prov["sut_hash"]
