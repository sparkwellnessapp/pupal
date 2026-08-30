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


def test_p2_reasoning_effort_reaches_only_the_p2_call(tmp_path):
    """cfg.p2_reasoning_effort rides the P2 provider call (gpt-5.6-luna knob,
    2026-08-11); P1 calls never carry it; empty config sends None."""
    fake = FakeProvider(script=[
        _p1_response({1: "שאלה 1\nclass Hobby {}"}),
        _p2_response([{"question_number": 1, "sub_question_id": "a",
                       "answer_text": "class Hobby {}"}]),
    ])
    pipe = build_pipeline(
        _cfg(p1_pages_per_call=1, p2_reasoning_effort="medium"),
        {"gemini": fake, "openai": fake},
        ProviderScheduler({"gemini": ProviderLimit(), "openai": ProviderLimit()}),
        pdf_renderer=_fake_renderer(1),
    )
    _run(pipe.run(b"pdf", "doc", _spec(tmp_path)))
    p1_call, p2_call = fake.calls
    assert p1_call.reasoning_effort is None          # P1 (perception) untouched
    assert p2_call.reasoning_effort == "medium"      # P2 carries the knob

    # Unset config -> None on the wire (nano-baseline behavior unchanged).
    fake2 = FakeProvider(script=[
        _p1_response({1: "x"}),
        _p2_response([{"question_number": 1, "sub_question_id": "a",
                       "answer_text": "x"}]),
    ])
    pipe2 = build_pipeline(
        _cfg(p1_pages_per_call=1),
        {"gemini": fake2, "openai": fake2},
        ProviderScheduler({"gemini": ProviderLimit(), "openai": ProviderLimit()}),
        pdf_renderer=_fake_renderer(1),
    )
    _run(pipe2.run(b"pdf", "doc", _spec(tmp_path)))
    assert all(c.reasoning_effort is None for c in fake2.calls)


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

    draft_path = runner_mod.SUITE_DIR / "draft_benchmarks" / "hobby_tvshow.moran_aharon.md"
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
        fixtures=("hobby_tvshow.moran_aharon",), repeats=1, mode="p2_only",
        exam_spec_path=str(spec_path),
    )
    out_dir = run_plan(plan, pipeline=pipe)
    try:
        results = json.loads((out_dir / "results.json").read_text(encoding="utf-8"))
        agg = results["aggregates"]
        assert agg["per_doc"]["hobby_tvshow.moran_aharon"]["ratio_strict_mean"] == 1.0
        assert agg["accuracy_gate_pass_all_docs"]
        assert agg["cost_gate_pass"]
        assert agg["worst_doc"] == "hobby_tvshow.moran_aharon"
        assert not agg["flag_metrics_trustworthy"]  # n=1 < 10 — honesty flag
        assert (out_dir / "summary.md").exists()
        report = (out_dir / "report_hobby_tvshow.moran_aharon.md").read_text(encoding="utf-8")
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


# --- per-fixture exam resolution (multi-rubric fixtures) -------------------------------

def _suite(tmp_path, *, exams=None, manifests=None, fallback=None):
    """A throwaway suite tree: exams/<id>.json, fixtures/<doc>.json, and an
    optional run-level fallback spec at the root."""
    (tmp_path / "exams").mkdir(exist_ok=True)
    (tmp_path / "fixtures").mkdir(exist_ok=True)
    for name, data in (exams or {}).items():
        (tmp_path / "exams" / f"{name}.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8")
    for doc, data in (manifests or {}).items():
        (tmp_path / "fixtures" / f"{doc}.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8")
    if fallback is not None:
        (tmp_path / "fallback.json").write_text(
            json.dumps(fallback, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def _canonical(number, subs, context=""):
    return {"questions": [{"number": number, "sub_questions": subs, "context": context}]}


def test_profiles_registry_resolves_default_and_raises_on_unknown():
    from .critical_tokens import JAVA_BAGRUT
    from .profiles import DEFAULT_PROFILE, profile

    assert profile() is JAVA_BAGRUT
    assert profile(DEFAULT_PROFILE) is JAVA_BAGRUT
    with pytest.raises(ValueError, match="unknown critical-token profile"):
        profile("no_such_subject")


def test_manifest_wins_over_the_run_level_fallback(tmp_path):
    """The fixture's own declaration is authoritative: two fixtures in one run
    may answer different exams."""
    from .exam_resolution import resolve_exam

    root = _suite(
        tmp_path,
        exams={"exam_b": _canonical(3, ["א", "ב"], "Mirror array")},
        manifests={"student_b": {"exam_spec": "exams/exam_b.json"}},
        fallback=_canonical(1, ["א"], "Hobby"),
    )
    with_manifest = resolve_exam("student_b", fallback_spec_path="fallback.json",
                                 suite_dir=root)
    assert with_manifest.ref == "exams/exam_b.json"
    assert with_manifest.spec.questions[0].number == 3
    assert len(with_manifest.sha256) == 64

    # A fixture with no manifest keeps TODAY'S behaviour, byte-for-byte.
    without = resolve_exam("student_a", fallback_spec_path="fallback.json",
                           suite_dir=root)
    assert without.ref == "fallback.json"
    assert without.spec.questions[0].number == 1
    assert without.profile_name == "java_bagrut"


def test_no_manifest_and_no_fallback_resolves_to_none(tmp_path):
    """None is legal — only p1_only may use it; the runner enforces the mode."""
    from .exam_resolution import resolve_exam
    assert resolve_exam("nobody", suite_dir=_suite(tmp_path)) is None


def test_manifest_failures_are_loud(tmp_path):
    """A fixture scored against the wrong skeleton is a silently wrong benchmark,
    so every resolution failure raises rather than falling back."""
    from .exam_resolution import resolve_exam

    root = _suite(
        tmp_path,
        exams={"exam_b": _canonical(1, ["א"])},
        manifests={
            "no_key": {"provenance": {"exam": "b"}},
            "bad_target": {"exam_spec": "exams/does_not_exist.json"},
            "bad_profile": {"exam_spec": "exams/exam_b.json", "profile": "klingon"},
        },
    )
    with pytest.raises(ValueError, match="must name an"):
        resolve_exam("no_key", suite_dir=root)
    with pytest.raises(FileNotFoundError, match="does not exist"):
        resolve_exam("bad_target", suite_dir=root)
    with pytest.raises(ValueError, match="unknown critical-token profile"):
        resolve_exam("bad_profile", suite_dir=root)

    (root / "fixtures" / "broken.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        resolve_exam("broken", suite_dir=root)


def test_selection_groups_ride_along_as_provenance(tmp_path):
    """A choose-k-of-N exam must announce itself in results.json: an empty answer
    there is correct by design, not a segmentation failure. Recording it changes
    no prompt and no score."""
    from .exam_resolution import resolve_exam

    root = _suite(
        tmp_path,
        exams={"bagrut": {
            "rubric_name": "bagrut_899371",
            "questions": [
                {"question_number": str(n), "question_text": f"q{n}",
                 "sub_questions": [{"sub_question_id": "א", "text": f"method{n}"}]}
                for n in range(1, 7)
            ],
            "selection_groups": [{"group_id": "sg0", "choose_k": 4,
                                  "of_question_ids": [f"q{n}" for n in range(1, 7)]}],
        }},
        manifests={"doc": {"exam_spec": "exams/bagrut.json"}},
    )
    prov = resolve_exam("doc", suite_dir=root).as_provenance()
    assert prov["exam_name"] == "bagrut_899371"
    assert prov["selection_groups"][0]["choose_k"] == 4
    assert len(prov["selection_groups"][0]["of_question_ids"]) == 6
    assert prov["profile"] == "java_bagrut"


def test_spec_keys_mirror_the_span_contract_targets(tmp_path):
    """GT is authored against `spec_keys`; P2 is asked for `spec_targets`. If the
    two ever disagree the benchmark demands keys the model cannot emit."""
    from app.services.transcription.two_phase.spans import spec_targets
    from .exam_resolution import load_spec_file, spec_keys
    from .keys import normalize_key

    p = tmp_path / "mixed.json"
    p.write_text(json.dumps({"questions": [
        {"number": 1, "sub_questions": ["א", "ב"], "context": "with subs"},
        {"number": 6, "sub_questions": [], "context": "whole question"},
    ]}), encoding="utf-8")
    spec = load_spec_file(p)
    assert spec_keys(spec) == [normalize_key(t.key) for t in spec_targets(spec)]
    assert (6, None) in spec_keys(spec)     # a question with no sub-questions


def test_runner_stamps_exam_and_profile_per_fixture(tmp_path):
    """results.json must say which ruler measured each record."""
    from . import runner as runner_mod
    from .ground_truth import load_ground_truth
    from .runner import RunPlan, run_plan

    draft_path = runner_mod.SUITE_DIR / "draft_benchmarks" / "hobby_tvshow.moran_aharon.md"
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
    plan = RunPlan(
        config=_cfg(), config_name="fake_p2",
        fixtures=("hobby_tvshow.moran_aharon",), repeats=1, mode="p2_only",
        exam_spec_path="draft.json",
    )
    out_dir = run_plan(plan, pipeline=pipe)
    try:
        results = json.loads((out_dir / "results.json").read_text(encoding="utf-8"))
        prov = results["fixtures"]["hobby_tvshow.moran_aharon"]
        assert prov["exam_spec"] == "exams/hobby_tvshow.json"   # its manifest wins
        assert prov["profile"] == "java_bagrut"
        assert len(prov["exam_spec_sha256"]) == 64
        rec = results["records"][0]
        assert rec["exam_spec"] == "exams/hobby_tvshow.json"
        assert rec["profile"] == "java_bagrut"
    finally:
        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)


def test_per_doc_modes_demand_an_exam_spec():
    """No manifest and no --exam-spec is a loud refusal outside p1_only."""
    from .runner import RunPlan, resolve_fixtures

    # A doc with no manifest AND no --exam-spec — every seed now carries a
    # manifest, so the refusal is exercised with an unregistered doc_id.
    plan = RunPlan(config=_cfg(), config_name="x", fixtures=("no_such_exam.nobody",),
                   mode="p2_only", exam_spec_path=None)
    with pytest.raises(ValueError, match="requires an exam spec"):
        resolve_fixtures(plan)


def test_nested_sub_question_composes_its_signature_from_children(tmp_path):
    """A rubric that nests TWO levels puts the prompt on the grandchildren and
    leaves the depth-1 node's own `text` null. Transcription segments to depth 1,
    so without composition P2 receives a bare letter and can only guess ORDER —
    the omer Q2.ב↔ג swap condition, for a whole question, silently.

    Composition is concatenation of the children's own text, in document order.
    Nothing is invented, and a node WITH its own text is never overridden."""
    nested = tmp_path / "nested.json"
    nested.write_text(json.dumps({"questions": [{
        "question_number": "1",
        "sub_questions": [
            {"sub_question_id": "א", "text": None, "sub_questions": [
                {"sub_question_id": "1", "text": "trace public static bool Check(int[] arr, int x)"},
                {"sub_question_id": "2", "text": "what is Check for?"},
            ]},
            {"sub_question_id": "ב", "text": "own text wins", "sub_questions": [
                {"sub_question_id": "1", "text": "child text must NOT override"},
            ]},
        ],
    }]}), encoding="utf-8")

    spec = spec_from_rubric_draft(nested)
    sigs = {sq.id: sq.signature for sq in spec.questions[0].sub_questions}
    assert "Check" in sigs["א"] and "what is Check for?" in sigs["א"]
    assert sigs["ב"] == "own text wins"        # own text is authoritative
    assert "Check" in spec.to_prompt_json()     # and it reaches P2

    # A childless, textless sub-question stays honestly empty — the composer
    # invents nothing to fill a gap the rubric genuinely has.
    bare = tmp_path / "bare.json"
    bare.write_text(json.dumps({"questions": [
        {"question_number": "1", "sub_questions": [{"sub_question_id": "א"}]}
    ]}), encoding="utf-8")
    assert spec_from_rubric_draft(bare).questions[0].sub_questions[0].signature == ""


def test_seed_corpus_resolves_exactly_as_the_historical_loader_did():
    """The lift must be a NULL RESULT for the five seed fixtures.

    They carry no manifest, so they take the `--exam-spec` fallback — and this
    pins that the fallback reproduces the retired run-level `load_spec` exactly:
    the same ExamSpec, the same `to_prompt_json()` BYTES (the actual model
    input, so P2 cannot behave differently), and the same profile OBJECT. A
    zero-API proof of the property a noisy k=5 could only suggest."""
    from pathlib import Path
    from .critical_tokens import JAVA_BAGRUT
    from .exam_resolution import SUITE_DIR, resolve_exam
    from .parsing import load_exam_spec, spec_from_rubric_draft

    draft = SUITE_DIR / "draft.json"
    if not draft.exists():
        pytest.skip("real draft.json not present")
    try:                                    # verbatim historical load_spec body
        historical = load_exam_spec(draft)
    except (ValueError, KeyError):
        historical = spec_from_rubric_draft(draft)

    for doc in ("hobby_tvshow.dan_basiuk", "hobby_tvshow.din_ezra",
                "hobby_tvshow.moran_aharon", "hobby_tvshow.omer_gelber",
                "hobby_tvshow.yonatan_basiuk"):
        # Since 2026-08-29 the seeds carry manifests, so they resolve through
        # exams/hobby_tvshow.json rather than the fallback. The claim is unchanged
        # and STRONGER: whichever path resolves it, P2 receives the same bytes.
        resolved = resolve_exam(doc, fallback_spec_path="draft.json")
        assert resolved is not None and resolved.ref == "exams/hobby_tvshow.json"
        assert resolved.spec.questions == historical.questions, (
            f"{doc}: spec drifted from the historical loader")
        assert resolved.spec.identifiers == historical.identifiers
        assert resolved.spec.to_prompt_json() == historical.to_prompt_json(), (
            f"{doc}: the bytes handed to P2 changed — this is a model-behaviour "
            f"change masquerading as plumbing"
        )
        assert resolved.profile is JAVA_BAGRUT


def test_every_in_use_exam_gives_p2_a_routing_signature():
    """Every sub-question P2 must route into carries a non-empty signature.

    Generalizes `test_real_draft_subquestion_signatures_name_the_methods` from
    one hand-named pair to every exam the corpus actually uses. A bare letter is
    not routable: P2 can only guess sub-question ORDER, which is precisely the
    omer Q2.ב↔ג swap and the yonatan Q2.ג drop.

    SCOPE — deliberately "exams in use", not `exams/*.json`: an exam artifact
    may be staged in the tree before its fixtures are authored, and this test is
    the LANDING GATE for those fixtures. The moment a `fixtures/<doc>.json`
    manifest points at an exam, that exam must be routable, or the fixture is
    guaranteed to fail on routing for reasons that have nothing to do with the
    model. In use = referenced by a manifest, plus the seed corpus's fallback."""
    from pathlib import Path
    from .exam_resolution import SUITE_DIR, load_spec_file, read_manifest

    in_use: set[Path] = set()
    for manifest_path in (SUITE_DIR / "fixtures").glob("*.json"):
        manifest = read_manifest(manifest_path.stem) or {}
        ref = manifest.get("exam_spec")
        if isinstance(ref, str) and ref.strip():
            in_use.add(SUITE_DIR / ref.strip())
    seed = SUITE_DIR / "draft.json"          # the seed corpus's --exam-spec fallback
    if seed.exists():
        in_use.add(seed)
    if not in_use:
        pytest.skip("no exam artifacts in use")

    for path in sorted(in_use):
        spec = load_spec_file(path)
        blind = [f"Q{q.number}.{sq.id}"
                 for q in spec.questions for sq in q.sub_questions
                 if not sq.signature.strip()]
        assert not blind, (
            f"{path.name}: sub-question(s) {blind} carry NO routing signature, so "
            f"P2 can only guess their order. For a rubric draft_json this usually "
            f"means the sub-question nests deeper (its own `text` is null and the "
            f"content lives in ITS sub_questions), which "
            f"parsing.spec_from_rubric_draft_data does not descend into."
        )
