"""Tests for prompts, parsing, exam_spec, pipelines, and the runner.

Zero network: pipelines run on FakeProvider with an injected PDF renderer;
the runner writes real artifacts into a tmp_path.
"""
import asyncio
import json

import pytest
from PIL import Image

from app.services.transcription.providers.fake import FakeProvider
from app.services.transcription.scheduler import ProviderLimit, ProviderScheduler

from .parsing import load_exam_spec, parse_model_json, spec_from_rubric_draft
from .pipelines import PipelineConfig, build_pipeline
from .prompts import p1_user_prompt, p2_system_prompt


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# --- parsing -------------------------------------------------------------------------

def test_parse_strips_fences_and_prose():
    ok, d = parse_model_json('```json\n{"pages": []}\n```', required_keys=("pages",))
    assert ok and d == {"pages": []}
    ok, d = parse_model_json('Here you go:\n{"pages": [1]} thanks!',
                             required_keys=("pages",))
    assert ok and d == {"pages": [1]}


def test_parse_failures_return_outcome_never_raise():
    assert parse_model_json("", required_keys=("x",)) == (False, {})
    assert parse_model_json("not json at all", required_keys=("x",)) == (False, {})
    assert parse_model_json('{"wrong": 1}', required_keys=("x",)) == (False, {})
    assert parse_model_json('[1,2]', required_keys=("x",)) == (False, {})


# --- prompts ------------------------------------------------------------------------

def test_p1_user_prompt_packing_variants():
    assert "page 4" in p1_user_prompt([4], "multi_image")
    assert "stacked vertically" in p1_user_prompt([4, 5, 6], "stitched")
    assert "3 images" in p1_user_prompt([4, 5, 6], "multi_image")


def test_p2_prompt_is_pure_segmentation():
    p = p2_system_prompt()
    assert "SEGMENTATION" in p
    # no-correction contract (wording per prompt t1.2)
    assert "You never correct, complete, or modify the text in any way" in p
    assert "Do not change a `Mobby` to a `Hobby`" in p
    assert "spec_mismatches" not in p  # correction is the deterministic post-pass now


# --- exam spec ----------------------------------------------------------------------

def test_exam_spec_canonical_and_rubric_draft(tmp_path):
    canonical = tmp_path / "spec.json"
    canonical.write_text(json.dumps({
        "questions": [{"number": 1, "sub_questions": ["א", "ב"],
                       "context": "Hobby class"}]
    }), encoding="utf-8")
    s = load_exam_spec(canonical)
    assert tuple(sq.id for sq in s.questions[0].sub_questions) == ("א", "ב")
    assert "Hobby" in s.to_prompt_json()

    rubric = tmp_path / "draft.json"
    rubric.write_text(json.dumps({
        "questions": [{
            "question_number": "2",
            "name": "TvShow",
            "sub_questions": [{"sub_question_id": "א", "name": "constructor"}],
        }]
    }), encoding="utf-8")
    s2 = spec_from_rubric_draft(rubric)
    assert s2.questions[0].number == 2
    assert tuple(sq.id for sq in s2.questions[0].sub_questions) == ("א",)
    assert s2.questions[0].sub_questions[0].signature == "constructor"  # carried, not dropped
    assert "TvShow" in s2.questions[0].context
    # the signature must reach the prompt JSON P2 consumes
    assert '"signature"' in s2.to_prompt_json() and "constructor" in s2.to_prompt_json()

    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="questions"):
        spec_from_rubric_draft(bad)


def test_real_draft_subquestion_signatures_name_the_methods():
    """Regression for the omer Q2.ב↔ג swap / yonatan Q2.ג drop: the spec P2 sees
    must carry each sub-question's discriminating method name, not bare letters.
    Q2.ב is LowestRateChannel, Q2.ג is PrintLowRatingChannel — and both must reach
    to_prompt_json (the text handed to P2)."""
    from pathlib import Path
    draft = Path(__file__).parent / "draft.json"
    if not draft.exists():
        import pytest as _pytest
        _pytest.skip("real draft.json not present")
    spec = spec_from_rubric_draft(draft)
    q2 = next(q for q in spec.questions if q.number == 2)
    sigs = {sq.id: sq.signature for sq in q2.sub_questions}
    assert "LowestRateChannel" in sigs.get("ב", "")
    assert "PrintLowRatingChannel" in sigs.get("ג", "")
    pj = spec.to_prompt_json()
    assert "LowestRateChannel" in pj and "PrintLowRatingChannel" in pj


# --- pipeline on fakes ----------------------------------------------------------------

def _fake_renderer(n_pages: int):
    def render(pdf_bytes: bytes, dpi: int):
        return [Image.new("RGB", (400, 600), "white") for _ in range(n_pages)]
    return render


def _spec(tmp_path):
    p = tmp_path / "spec.json"
    p.write_text(json.dumps({"questions": [
        {"number": 1, "sub_questions": ["א"], "context": "Hobby"}
    ]}), encoding="utf-8")
    return load_exam_spec(p)


def _p1_response(pages: dict[int, str]):
    return FakeProvider.ok(json.dumps(
        {"pages": [{"page_number": n, "text": t} for n, t in pages.items()]}
    ))


def _p2_response(answers, mismatches=(), notes=()):
    return FakeProvider.ok(json.dumps({
        "answers": answers,
        "spec_mismatches": list(mismatches),
        "routing_notes": list(notes),
    }))


def _cfg(**kw) -> PipelineConfig:
    base = dict(p1_model_key="gemini-3.1-flash-lite",
                p2_model_key="gpt-5.4-nano-2026-03-17",
                p1_pages_per_call=3)
    base.update(kw)
    return PipelineConfig(**base)


def test_pipeline_chunking_and_packing(tmp_path):
    """5 pages at 3/call -> 2 calls; multi_image sends 3 then 2 images;
    stitched sends exactly 1 image per call."""
    for packing, expected_images in (("multi_image", [3, 2]), ("stitched", [1, 1])):
        fake = FakeProvider(script=[
            _p1_response({1: "a", 2: "b", 3: "c"}),
            _p1_response({4: "d", 5: "e"}),
        ])
        pipe = build_pipeline(
            _cfg(p1_image_packing=packing),
            {"gemini": fake, "openai": fake},
            ProviderScheduler({"gemini": ProviderLimit(), "openai": ProviderLimit()}),
            pdf_renderer=_fake_renderer(5),
        )
        pages, trace = _run(pipe.run_phase1(b"pdf", "doc"))
        assert pages == {1: "a", 2: "b", 3: "c", 4: "d", 5: "e"}
        assert sorted(c.n_images for c in fake.calls) == sorted(expected_images)
        assert all(c.parse_ok for c in trace.calls)


def test_pipeline_deterministic_correction_spec_tier(tmp_path):
    """LLM stays verbatim (emits Mobby); the deterministic post-pass corrects
    Mobby->Hobby under policy='spec' because Hobby is a spec identifier."""
    fake = FakeProvider(script=[
        _p1_response({1: "שאלה 1\nclass Mobby {}"}),
        _p2_response([{"question_number": 1, "sub_question_id": "a",
                       "answer_text": "class Mobby {}"}]),
    ])
    pipe = build_pipeline(
        _cfg(p1_pages_per_call=1, correction_policy="spec"),
        {"gemini": fake, "openai": fake},
        ProviderScheduler({"gemini": ProviderLimit(), "openai": ProviderLimit()}),
        pdf_renderer=_fake_renderer(1),
    )
    run = _run(pipe.run(b"pdf", "doc", _spec(tmp_path)))
    # Raw (verbatim) answer keeps Mobby; corrected answer has Hobby.
    assert run.answers == {(1, "א"): "class Mobby {}"}
    assert run.corrected_answers == {(1, "א"): "class Hobby {}"}
    assert run.corrections[0].original == "Mobby"
    assert run.corrections[0].corrected == "Hobby"
    assert run.corrections[0].tier == "spec"
    # evidence preserved as a spec_mismatch record keyed to the answer
    assert run.spec_mismatches[0].original == "Mobby"
    assert run.spec_mismatches[0].key == (1, "א")
    assert {c.phase for c in run.trace.calls} == {"p1", "p2"}


def test_pipeline_correction_off_is_verbatim(tmp_path):
    """policy='off' leaves Mobby untouched; no corrections."""
    fake = FakeProvider(script=[
        _p1_response({1: "class Mobby {}"}),
        _p2_response([{"question_number": 1, "sub_question_id": "a",
                       "answer_text": "class Mobby {}"}]),
    ])
    pipe = build_pipeline(
        _cfg(p1_pages_per_call=1, correction_policy="off"),
        {"gemini": fake, "openai": fake},
        ProviderScheduler({"gemini": ProviderLimit(), "openai": ProviderLimit()}),
        pdf_renderer=_fake_renderer(1),
    )
    run = _run(pipe.run(b"pdf", "doc", _spec(tmp_path)))
    assert run.corrections == ()
    assert run.corrected_answers == {(1, "א"): "class Mobby {}"}


def test_pipeline_parse_failure_degrades_not_throws(tmp_path):
    """Both parse attempts garbage -> empty pages, parse_ok recorded False twice."""
    fake = FakeProvider(script=[
        FakeProvider.ok("not json"),
        FakeProvider.ok("still not json"),
    ])
    pipe = build_pipeline(
        _cfg(p1_pages_per_call=2, p2_model_key=""),
        {"gemini": fake},
        ProviderScheduler({"gemini": ProviderLimit()}),
        pdf_renderer=_fake_renderer(2),
    )
    pages, trace = _run(pipe.run_phase1(b"pdf", "doc"))
    assert pages == {1: "", 2: ""}            # degraded, loud at scoring time
    assert [c.parse_ok for c in trace.calls] == [False, False]
    assert len(fake.calls) == 2               # exactly one re-request


def test_p1_only_config_refuses_phase2(tmp_path):
    fake = FakeProvider()
    pipe = build_pipeline(
        _cfg(p2_model_key=""),
        {"gemini": fake},
        ProviderScheduler({"gemini": ProviderLimit()}),
        pdf_renderer=_fake_renderer(1),
    )
    with pytest.raises(ValueError, match="p1_only"):
        _run(pipe.run_phase2({1: "x"}, _spec(tmp_path), "doc"))


# --- runner end-to-end on fakes --------------------------------------------------------

def test_runner_p2_only_writes_artifacts(tmp_path, monkeypatch):
    """p2_only: gold pages -> fake P2 echoing the draft GT -> perfect score,
    artifacts written, gates pass (cost is fake-cheap)."""
    from . import runner as runner_mod
    from .ground_truth import load_ground_truth
    from .runner import RunPlan, run_plan

    draft_path = runner_mod.SUITE_DIR / "draft_benchmarks" / "moran_aharon.md"
    if not draft_path.exists():
        pytest.skip("fixtures not on disk")
    gold = load_ground_truth(draft_path)

    fake = FakeProvider(script=[_p2_response([
        {"question_number": k[0], "sub_question_id": k[1], "answer_text": t}
        for k, t in gold.as_dict().items()
    ])])
    pipe = build_pipeline(
        _cfg(),
        {"gemini": fake, "openai": fake},
        ProviderScheduler({"gemini": ProviderLimit(), "openai": ProviderLimit()}),
        pdf_renderer=_fake_renderer(1),
    )

    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps({"questions": [
        {"number": 1, "sub_questions": ["א", "ב", "ג"], "context": "Hobby"},
        {"number": 2, "sub_questions": ["א", "ב", "ג"], "context": "TvShow"},
    ]}), encoding="utf-8")

    monkeypatch.setattr(runner_mod, "SUITE_DIR", runner_mod.SUITE_DIR)  # real fixtures
    # redirect results output
    out_root = tmp_path / "results"
    monkeypatch.setattr(runner_mod.time, "strftime", lambda fmt: "TEST")
    real_suite = runner_mod.SUITE_DIR

    plan = RunPlan(
        config=_cfg(), config_name="fake_p2",
        fixtures=("moran_aharon",), repeats=1, mode="p2_only",
        exam_spec_path=str(spec_path),
    )
    out_dir = run_plan(plan, pipeline=pipe)
    try:
        results = json.loads((out_dir / "results.json").read_text(encoding="utf-8"))
        agg = results["aggregates"]
        assert agg["per_doc"]["moran_aharon"]["ratio_strict_mean"] == 1.0
        assert agg["accuracy_gate_pass_all_docs"]
        assert agg["cost_gate_pass"]
        assert agg["worst_doc"] == "moran_aharon"
        assert not agg["flag_metrics_trustworthy"]  # n=1 < 10 — honesty flag
        assert (out_dir / "summary.md").exists()
        report = (out_dir / "report_moran_aharon.md").read_text(encoding="utf-8")
        assert "(identical)" in report            # real gold|pred diffs present
    finally:
        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)


def test_finish_reason_recorded_on_parse_failure(tmp_path):
    """Truncation diagnosis: the failed-parse call carries its finish_reason, and
    a token-cap truncation ("length") skips the parse re-request — re-requesting
    the identical call would deterministically truncate again."""
    from app.services.transcription.vlm_provider import Usage, VLMResponse
    truncated = VLMResponse(text='{"pages": [{"page_number": 1, "te',
                            usage=Usage(100, 3000), total_ms=5.0,
                            model_id="fake-1", raw_finish_reason="length")
    fake = FakeProvider(script=[truncated, truncated])
    pipe = build_pipeline(
        _cfg(p1_pages_per_call=1, p2_model_key=""),
        {"gemini": fake},
        ProviderScheduler({"gemini": ProviderLimit()}),
        pdf_renderer=_fake_renderer(1),
    )
    pages, trace = _run(pipe.run_phase1(b"pdf", "doc"))
    assert all(not c.parse_ok for c in trace.calls)
    # One call only: truncation is deterministic, so no wasteful re-request.
    assert [c.finish_reason for c in trace.calls] == ["length"]
