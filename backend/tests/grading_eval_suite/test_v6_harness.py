"""grader-v6 M3 — the eval harness grades a fixture end to end on v6 OFFLINE: the
real config, the pinned plan gate, the v6 verifier (a scripted fake model), the
ONE pricer, and the v5 scorer reading the v6 draft. No provider is called."""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.schemas.graded_test_draft_v6 import v6_content
from app.services.pricing_v6 import price
from tests.agents.test_grader_v6 import _Fake, _full
from tests.eval_common.models_registry import spec as model_spec
from tests.grading_eval_suite.fixtures import SUITE_DIR, load_bundle
from tests.grading_eval_suite.runner import (_load_config, _load_plan_v6, _plans_provenance_v6,
                                             _score_pair)

CONFIG = "v6-cs-sonnet55"


@pytest.fixture(scope="module")
def config():
    return _load_config(CONFIG)


def test_the_cs_eval_config_is_a_valid_v6_config(config):
    assert config["architecture"] == "v6" and set(config["plans"]) == {"hobby_tvshow", "bagrut_899371"}
    assert model_spec(config["model_key"]).model_id == "claude-sonnet-5-5"
    assert model_spec(config["explainer"]["model_key"]).model_id == "claude-haiku-4-5"


@pytest.mark.parametrize("fixture", ["din_ezra", "bagrut_899371.din_ezra"])
def test_the_pinned_plan_gate_passes_before_any_spend(config, fixture):
    bundle = load_bundle(fixture, require_gt=True)
    plan, sha, resolved = _load_plan_v6(config, bundle, SUITE_DIR)
    assert plan.plan_hash == {"hobby_tvshow": "1d74b46ac5d1fcca7d49922473984608fa259e5208119da8ea6e692872804498",
                              "bagrut_899371": "229c46a8c7b4d5f5785da9839db697a2a666d8a2032c25835a053ce9c2175540"
                              }[bundle.exam_id]
    prov = _plans_provenance_v6(config, [bundle], SUITE_DIR)
    entry = prov[bundle.exam_id]
    e = entry["expressibility_v6"][bundle.name]
    assert 0 < e["expressible"] <= e["total"]


def test_a_plan_whose_content_moved_is_refused(config, tmp_path):
    import json
    import shutil
    bundle = load_bundle("din_ezra", require_gt=True)
    root = tmp_path / "suite"
    shutil.copytree(SUITE_DIR / "plans", root / "plans")
    p = root / "plans" / "v6" / "hobby_tvshow.plan.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["checks"][0]["options"][0]["value"] = "99"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SystemExit, match="re-hash"):
        _load_plan_v6(config, bundle, root)


async def test_m3_offline_one_fixture_end_to_end(config):
    """The M3 path with a fake model: verify → price → envelope → the v5 scorer.
    Every GT terminal gets a scored row; the scorer's total is the pricer's."""
    from app.agents.grader.grader_v6 import OptionsVerifyGrader
    from app.subjects import get_profile
    bundle = load_bundle("din_ezra", require_gt=True)
    plan, _sha, _r = _load_plan_v6(config, bundle, SUITE_DIR)
    spec = model_spec(config["model_key"])
    agent = OptionsVerifyGrader(plan, bundle.rubric_contract, llm=_Fake(_full),
                                model_version=spec.model_id,
                                profile=get_profile(plan.subject_pack.pack_id))
    draft = await agent.grade(bundle.gradable_test)
    meta = {"trial_index": 0, "latency_s": 1.0, "rerun_count": 0, "rerun_reason": None,
            "invalid_reason": None}
    ts = _score_pair(draft, meta, bundle, cost_ceiling=0.15, price=spec.price, provisional=True)
    assert ts.valid, ts.invalid_reason
    gt_scored = {t.terminal_id for t in bundle.gt.terminals if t.awarded is not None}
    assert {r.terminal_id for r in ts.terminals} == gt_scored
    content = v6_content(draft)
    priced = price(content.to_view())
    assert D(ts.ai_total) == priced.total_score
    assert ts.cost_usd is not None and ts.cost_usd > 0
