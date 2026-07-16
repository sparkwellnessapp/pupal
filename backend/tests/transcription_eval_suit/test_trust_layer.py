"""Trust-layer tests: the run_with_trust orchestrator (FakeProviders, zero
network) and the flag_metrics instrument (pure)."""
import asyncio
import json

from PIL import Image

from app.services.transcription.providers.fake import FakeProvider
from app.services.transcription.scheduler import ProviderLimit, ProviderScheduler
from app.services.transcription.two_phase.trust import run_with_trust

from .flag_metrics import score_flags
from .ground_truth import parse_page_ground_truth
from .parsing import load_exam_spec
from .pipelines import PipelineConfig, build_pipeline


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _fake_renderer(n_pages):
    def render(pdf_bytes, dpi):
        return [Image.new("RGB", (100, 140), "white") for _ in range(n_pages)]
    return render


def _p1_response(pages: dict[int, str]):
    return FakeProvider.ok(json.dumps({
        "pages": [{"page_number": n, "text": t} for n, t in pages.items()]
    }))


def _p2_response(answers):
    return FakeProvider.ok(json.dumps({
        "answers": answers, "routing_notes": []
    }))


BASE_PAGE = "public bool Populate()\n{\nif(hobbies[i] == null)\n{\ncount++;\n}\n}"
READER_PAGE = BASE_PAGE.replace("==", "!=")


def _spec(tmp_path):
    p = tmp_path / "spec.json"
    p.write_text(json.dumps({
        "questions": [{"number": 1, "sub_questions":
                       [{"id": "א", "signature": "Populate"}],
                       "context": "SchoolHobbies"}]
    }), encoding="utf-8")
    return load_exam_spec(p)


def _trust_pipeline(gem_script, ant_script, oai_script):
    cfg = PipelineConfig(
        p1_model_key="gemini-3.1-flash-lite",
        reader_model_keys=("claude-haiku-4.5", "chatgpt-4o-mini"),
        p2_model_key="gpt-5.4-nano-2026-03-17",
        p1_pages_per_call=3,
    )
    providers = {
        "gemini": FakeProvider(script=gem_script),
        "anthropic": FakeProvider(script=ant_script),
        "openai": FakeProvider(script=oai_script),
    }
    sched = ProviderScheduler({n: ProviderLimit() for n in providers})
    return build_pipeline(cfg, providers, sched,
                          pdf_renderer=_fake_renderer(1)), providers


def test_run_with_trust_flags_reader_disagreement(tmp_path):
    """Both readers read `!=` where the baseline read `==` -> one HIGH flag,
    anchored into the answer, with page provenance; draft text stays baseline."""
    pipe, providers = _trust_pipeline(
        gem_script=[_p1_response({1: BASE_PAGE})],
        ant_script=[_p1_response({1: READER_PAGE})],
        oai_script=[_p1_response({1: READER_PAGE}),
                    _p2_response([{"question_number": 1, "sub_question_id": "א",
                                   "answer_text": BASE_PAGE}])],
    )
    tr = _run(run_with_trust(pipe, b"pdf", "doc", _spec(tmp_path)))

    # Draft text is the BASELINE's verbatim output — readers never touch it.
    assert tr.run.answers[(1, "א")] == BASE_PAGE

    high = [f for f in tr.flags if f.severity == "high"]
    assert len(high) == 1
    f = high[0]
    assert f.base_text == "==" and f.alternatives == ("!=",)
    assert f.n_readers == 2 and f.page == 1
    assert f.anchor_key == "q1.א" and f.anchor_similarity == 1.0

    att = tr.attributions["q1.א"]
    assert att.pages == [1] and att.confidence > 0.95

    # reader calls: distinct phase in the trace, cost accounted
    reader_calls = [c for c in tr.trace.calls if c.phase == "reader"]
    assert len(reader_calls) == 2
    assert tr.trace.total_cost_usd() > 0


def test_run_with_trust_reader_failure_casts_no_votes(tmp_path):
    """A reader whose output never parses degrades to empty pages -> zero
    flags from it; the doc still completes (per-unit isolation)."""
    pipe, _ = _trust_pipeline(
        gem_script=[_p1_response({1: BASE_PAGE})],
        ant_script=[FakeProvider.ok("NOT JSON"), FakeProvider.ok("NOT JSON")],
        oai_script=[_p1_response({1: BASE_PAGE}),  # agrees with baseline
                    _p2_response([{"question_number": 1, "sub_question_id": "א",
                                   "answer_text": BASE_PAGE}])],
    )
    tr = _run(run_with_trust(pipe, b"pdf", "doc", _spec(tmp_path)))
    assert tr.run.answers[(1, "א")] == BASE_PAGE
    assert tr.flags == ()          # broken reader casts no disagreement votes


def test_score_flags_covered_and_missed_critical(tmp_path):
    """flag_metrics: a flagged real error counts covered; an unflagged critical
    error lands in missed_critical; info flags don't dilute the severity split."""
    from app.services.transcription.flagging import compute_flags

    base_pages = {1: "if(x == null)\nint y = 1\nreturn y;"}   # GT: != and 'int y = 1;'
    gold = parse_page_ground_truth(
        "=== PAGE 1 ===\nif(x != null)\nint y = 1;\nreturn y;", doc_id="d")
    # one reader catches the operator; nobody catches the missing ';'
    flags = compute_flags(base_pages, [{1: "if(x != null)\nint y = 1\nreturn y;"}])
    sc = score_flags("d", base_pages, gold, flags, lint=())

    assert sc.n_labels_critical == 2
    assert sc.covered_critical == 1
    assert sc.critical_recall == 0.5
    assert len(sc.missed_critical) == 1
    assert ";" in sc.missed_critical[0]["gt"]
    assert sc.n_flags == 1 and sc.true_flags == 1 and sc.precision == 1.0


def test_p2_truncation_gets_one_rerequest(tmp_path):
    """R4: nano truncation is stochastic — a 'length' parse failure on P2 is
    re-requested ONCE (P1 truncation stays no-retry: deterministic)."""
    from app.services.transcription.vlm_provider import Usage, VLMResponse

    def truncated(text):
        return VLMResponse(text=text, usage=Usage(100, 50), total_ms=5.0,
                           model_id="fake", raw_finish_reason="length")

    pipe, providers = _trust_pipeline(
        gem_script=[_p1_response({1: BASE_PAGE})],
        ant_script=[_p1_response({1: BASE_PAGE})],
        oai_script=[_p1_response({1: BASE_PAGE}),
                    truncated('{"answers": [{"question_'),   # cut mid-JSON
                    _p2_response([{"question_number": 1, "sub_question_id": "א",
                                   "answer_text": BASE_PAGE}])],
    )
    tr = _run(run_with_trust(pipe, b"pdf", "doc", _spec(tmp_path)))
    assert tr.run.answers[(1, "א")] == BASE_PAGE      # retry recovered the doc
    p2_calls = [c for c in tr.trace.calls if c.phase == "p2"]
    assert len(p2_calls) == 2 and p2_calls[1].parse_ok


def test_p1_truncation_is_not_rerequested(tmp_path):
    from app.services.transcription.vlm_provider import Usage, VLMResponse
    trunc = VLMResponse(text='{"pages": [{"page_num', usage=Usage(100, 50),
                        total_ms=5.0, model_id="fake",
                        raw_finish_reason="MAX_TOKENS")
    pipe, providers = _trust_pipeline(
        gem_script=[trunc, _p1_response({1: BASE_PAGE})],  # 2nd item must NOT be used
        ant_script=[_p1_response({1: BASE_PAGE})],
        oai_script=[_p1_response({1: BASE_PAGE}),
                    _p2_response([{"question_number": 1, "sub_question_id": "א",
                                   "answer_text": ""}])],
    )
    tr = _run(run_with_trust(pipe, b"pdf", "doc", _spec(tmp_path)))
    p1_calls = [c for c in tr.trace.calls if c.phase == "p1"]
    assert len(p1_calls) == 1 and not p1_calls[0].parse_ok  # no re-request


def test_reader_max_tokens_caps_reader_calls(tmp_path):
    """R2: readers use reader_max_tokens (per page) when set; baseline keeps
    p1_max_tokens."""
    from app.services.transcription.providers.fake import FakeProvider
    from app.services.transcription.scheduler import ProviderLimit, ProviderScheduler
    from .pipelines import PipelineConfig, build_pipeline

    cfg = PipelineConfig(
        p1_model_key="gemini-3.1-flash-lite",
        reader_model_keys=("claude-haiku-4.5",),
        p2_model_key="gpt-5.4-nano-2026-03-17",
        p1_pages_per_call=3, p1_max_tokens=5000, reader_max_tokens=8000,
    )
    gem = FakeProvider(script=[_p1_response({1: BASE_PAGE})])
    ant = FakeProvider(script=[_p1_response({1: BASE_PAGE})])
    oai = FakeProvider(script=[_p2_response(
        [{"question_number": 1, "sub_question_id": "א", "answer_text": BASE_PAGE}])])
    pipe = build_pipeline(cfg, {"gemini": gem, "anthropic": ant, "openai": oai},
                          ProviderScheduler({n: ProviderLimit()
                                             for n in ("gemini", "anthropic", "openai")}),
                          pdf_renderer=_fake_renderer(1))
    _run(run_with_trust(pipe, b"pdf", "doc", _spec(tmp_path)))
    assert gem.calls[0].max_tokens == 5000     # baseline: p1_max_tokens × 1 page
    assert ant.calls[0].max_tokens == 8000     # reader: reader_max_tokens × 1 page
