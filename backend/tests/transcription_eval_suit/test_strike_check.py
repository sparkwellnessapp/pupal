"""
Strike-check pass (strike_check.py + the pipeline hook) — zero-network tests.

Pins the four load-bearing properties:
1. apply_struck_ranges is pure, validated, and can only DELETE whole lines.
2. The pass is OFF by default — an unset key produces zero checker calls
   (production PROD_CONFIG stays byte-identical in behavior).
3. When ON: one single-image call per NONEMPTY page; flagged lines removed;
   P1's own call/prompt untouched.
4. Fail-safe: a checker parse failure keeps the page text unchanged.
"""
from __future__ import annotations

import asyncio
import json

from PIL import Image

from app.services.transcription.providers.fake import FakeProvider
from app.services.transcription.scheduler import ProviderLimit, ProviderScheduler
from app.services.transcription.two_phase.prompts import P1_SYSTEM
from app.services.transcription.two_phase.strike_check import (
    STRIKE_CHECK_SYSTEM,
    apply_struck_ranges,
    numbered_lines,
)

from .pipelines import PipelineConfig, build_pipeline


def _run(coro):
    return asyncio.run(coro)


# --- the pure post-pass -------------------------------------------------------------

def test_apply_struck_ranges_deletes_named_lines_only():
    text = "keep1\nstruck1\nstruck2\nkeep2"
    new, removed = apply_struck_ranges(
        text, [{"start_line": 2, "end_line": 3}])
    assert new == "keep1\nkeep2"
    assert removed == ("struck1", "struck2")


def test_apply_struck_ranges_discards_single_line_ranges_by_default():
    # sc1.2 guard: the observed false-positive class (a kept line with an
    # inline scribbled-out word) is single-line — discarded by construction.
    text = "a\nb\nc\nd"
    new, removed = apply_struck_ranges(
        text, [{"start_line": 2, "end_line": 2},
               {"start_line": 3, "end_line": 4}])
    assert new == "a\nb"
    assert removed == ("c", "d")
    # min_block_lines=1 re-enables single-line deletion (config escape hatch).
    new1, removed1 = apply_struck_ranges(
        text, [{"start_line": 2, "end_line": 2}], min_block_lines=1)
    assert new1 == "a\nc\nd"
    assert removed1 == ("b",)


def test_apply_struck_ranges_multiple_and_overlapping():
    text = "a\nb\nc\nd\ne"
    new, removed = apply_struck_ranges(
        text, [{"start_line": 1, "end_line": 2},
               {"start_line": 2, "end_line": 3}])
    assert new == "d\ne"
    assert removed == ("a", "b", "c")


def test_apply_struck_ranges_ignores_malformed_and_out_of_bounds():
    text = "a\nb\nc"
    for bad in (
        None,
        "junk",
        [{"start_line": 0, "end_line": 2}],      # below range
        [{"start_line": 2, "end_line": 9}],      # beyond range
        [{"start_line": 3, "end_line": 1}],      # inverted
        [{"start_line": "2", "end_line": 3}],    # wrong type
        [{"start_line": True, "end_line": 2}],   # bool is not a line number
        [{"end_line": 2}],                       # missing key
        ["not a dict"],
    ):
        new, removed = apply_struck_ranges(text, bad)
        assert (new, removed) == (text, ()), f"mutated on {bad!r}"


def test_apply_struck_ranges_full_page_becomes_empty():
    new, removed = apply_struck_ranges(
        "x\ny", [{"start_line": 1, "end_line": 2}])
    assert new == ""
    assert removed == ("x", "y")


def test_numbered_lines_matches_span_rendering():
    assert numbered_lines("a\nb") == "  1| a\n  2| b"


# --- pipeline wiring ---------------------------------------------------------------

def _fake_renderer(n_pages: int):
    def render(pdf_bytes: bytes, dpi: int):
        return [Image.new("RGB", (400, 600), "white") for _ in range(n_pages)]
    return render


def _p1_response(pages: dict[int, str]):
    return FakeProvider.ok(json.dumps(
        {"pages": [{"page_number": n, "text": t} for n, t in pages.items()]}
    ))


def _strike_response(ranges):
    return FakeProvider.ok(json.dumps({"struck_line_ranges": ranges}))


def _pipe(fake, cfg, n_pages):
    return build_pipeline(
        cfg, {"gemini": fake, "openai": fake},
        ProviderScheduler({"gemini": ProviderLimit(), "openai": ProviderLimit()}),
        pdf_renderer=_fake_renderer(n_pages),
    )


def _cfg(**kw) -> PipelineConfig:
    base = dict(p1_model_key="gemini-3.1-pro-preview", p1_pages_per_call=3)
    base.update(kw)
    return PipelineConfig(**base)


def test_default_off_no_checker_calls():
    fake = FakeProvider(script=[_p1_response({1: "a", 2: "b"})])
    pages, trace = _run(_pipe(fake, _cfg(), 2).run_phase1(b"pdf", "doc"))
    assert pages == {1: "a", 2: "b"}
    assert [c.phase for c in trace.calls] == ["p1"]
    assert len(fake.calls) == 1


def test_checker_removes_struck_block_and_skips_empty_pages():
    # Page 1 nonempty (lines 2-3 struck), page 2 empty (skipped).
    fake = FakeProvider(script=[
        _p1_response({1: "kept\nstruck ink\nstruck ink2\nkept2", 2: ""}),
        _strike_response([{"start_line": 2, "end_line": 3}]),
    ])
    cfg = _cfg(p1_strike_check_model_key="gemini-3.5-flash-lite")
    pages, trace = _run(_pipe(fake, cfg, 2).run_phase1(b"pdf", "doc"))
    assert pages == {1: "kept\nkept2", 2: ""}
    assert [c.phase for c in trace.calls] == ["p1", "strike_check"]
    p1_call, sc_call = fake.calls
    # P1's prompt/schema untouched; checker sends ONE image + its own prompt.
    assert p1_call.system == P1_SYSTEM
    assert sc_call.system == STRIKE_CHECK_SYSTEM
    assert sc_call.n_images == 1
    assert "  2| struck ink" in sc_call.user
    assert sc_call.max_tokens == 4000


def test_checker_single_line_report_is_discarded_in_pipeline():
    # A single-line checker report (the moran false-positive class) must not
    # delete anything at the default min_block_lines=2.
    fake = FakeProvider(script=[
        _p1_response({1: "a\nb\nc"}),
        _strike_response([{"start_line": 2, "end_line": 2}]),
    ])
    cfg = _cfg(p1_strike_check_model_key="gemini-3.5-flash-lite")
    pages, _ = _run(_pipe(fake, cfg, 1).run_phase1(b"pdf", "doc"))
    assert pages == {1: "a\nb\nc"}


def test_checker_empty_ranges_keeps_pages_verbatim():
    fake = FakeProvider(script=[
        _p1_response({1: "a\nb"}),
        _strike_response([]),
    ])
    cfg = _cfg(p1_strike_check_model_key="gemini-3.5-flash-lite")
    pages, _ = _run(_pipe(fake, cfg, 1).run_phase1(b"pdf", "doc"))
    assert pages == {1: "a\nb"}


def test_checker_parse_failure_is_fail_safe():
    # Checker emits junk twice (parse layer re-requests once) -> page unchanged,
    # failures recorded on the trace, doc never throws.
    fake = FakeProvider(script=[
        _p1_response({1: "a\nb"}),
        FakeProvider.ok("not json"),
        FakeProvider.ok("still not json"),
    ])
    cfg = _cfg(p1_strike_check_model_key="gemini-3.5-flash-lite")
    pages, trace = _run(_pipe(fake, cfg, 1).run_phase1(b"pdf", "doc"))
    assert pages == {1: "a\nb"}
    sc_calls = [c for c in trace.calls if c.phase == "strike_check"]
    assert len(sc_calls) == 2 and not any(c.parse_ok for c in sc_calls)


def test_checker_two_votes_union_and_call_count():
    # votes=2: two checker calls per page; deletions are the UNION of both
    # votes' guard-filtered ranges.
    fake = FakeProvider(script=[
        _p1_response({1: "a\nb\nc\nd\ne\nf"}),
        _strike_response([{"start_line": 2, "end_line": 3}]),
        _strike_response([{"start_line": 4, "end_line": 5}]),
    ])
    cfg = _cfg(p1_strike_check_model_key="gemini-3.5-flash-lite",
               p1_strike_check_votes=2)
    pages, trace = _run(_pipe(fake, cfg, 1).run_phase1(b"pdf", "doc"))
    assert pages == {1: "a\nf"}
    assert [c.phase for c in trace.calls] == ["p1", "strike_check", "strike_check"]


def test_checker_two_votes_one_empty_still_deletes():
    # The union is the recall margin: one silent vote does not mask the other.
    fake = FakeProvider(script=[
        _p1_response({1: "a\nb\nc"}),
        _strike_response([{"start_line": 2, "end_line": 3}]),
        _strike_response([]),
    ])
    cfg = _cfg(p1_strike_check_model_key="gemini-3.5-flash-lite",
               p1_strike_check_votes=2)
    pages, _ = _run(_pipe(fake, cfg, 1).run_phase1(b"pdf", "doc"))
    assert pages == {1: "a"}


def test_checker_transport_failure_is_fail_safe():
    from app.services.transcription.vlm_provider import ErrorKind, VLMCallError
    fake = FakeProvider(script=[
        _p1_response({1: "a\nb"}),
        VLMCallError(ErrorKind.TIMEOUT, "boom", provider="gemini"),
        VLMCallError(ErrorKind.TIMEOUT, "boom", provider="gemini"),
    ])
    cfg = _cfg(p1_strike_check_model_key="gemini-3.5-flash-lite")
    pages, _ = _run(_pipe(fake, cfg, 1).run_phase1(b"pdf", "doc"))
    assert pages == {1: "a\nb"}


# --- wire encoding: format is a pipeline decision, mime is derived from bytes ---

def test_image_format_default_is_png_and_mime_is_sniffed():
    """Default stays PNG (inert change) and the mime comes from the bytes, so a
    format switch can never mislabel the payload."""
    from app.services.transcription.vlm_provider import image_mime_for
    from app.services.transcription.two_phase.pipeline import _to_b64_image
    img = Image.new("RGB", (40, 30), "white")
    assert PipelineConfig(p1_model_key="x").image_format == "png"
    assert image_mime_for(_to_b64_image(img, "png")) == "image/png"
    assert image_mime_for(_to_b64_image(img, "jpeg")) == "image/jpeg"
    assert image_mime_for("") == "image/png"          # empty -> safe default


def test_jpeg_config_reaches_the_p1_call_payload():
    fake = FakeProvider(script=[_p1_response({1: "a"})])
    cfg = _cfg(p1_pages_per_call=1, image_format="jpeg", image_jpeg_quality=90)
    _run(_pipe(fake, cfg, 1).run_phase1(b"pdf", "doc"))
    from app.services.transcription.vlm_provider import image_mime_for
    assert image_mime_for(fake.calls[0].images_b64[0]) == "image/jpeg"


def test_strike_check_uses_the_same_wire_format():
    """The checker uploads every page a SECOND time — it must not silently
    keep sending PNG when the pipeline switched to JPEG."""
    fake = FakeProvider(script=[_p1_response({1: "a\nb"}), _strike_response([])])
    cfg = _cfg(p1_pages_per_call=1, image_format="jpeg",
               p1_strike_check_model_key="gemini-3.5-flash-lite")
    _run(_pipe(fake, cfg, 1).run_phase1(b"pdf", "doc"))
    from app.services.transcription.vlm_provider import image_mime_for
    sc_call = fake.calls[-1]
    assert image_mime_for(sc_call.images_b64[0]) == "image/jpeg"



def _p2_response(answers):
    return FakeProvider.ok(json.dumps(
        {"answers": answers, "routing_notes": []}))


def test_trust_path_runs_the_strike_check_too():
    """The PRODUCTION entry (`trust.run_with_trust`) must run the pass.

    run_with_trust does NOT call run_phase1 — it drives perception directly and
    then run_phase2. While the strike-check hook lived only inside run_phase1,
    enabling it in PROD_CONFIG changed NOTHING in production even though the
    eval suite (p1_only -> run_phase1) exercised it perfectly. This test is
    that divergence's tripwire: it drives the real production function.
    """
    import json as _json, pathlib, tempfile
    from app.services.transcription.two_phase.parsing import load_exam_spec
    from app.services.transcription.two_phase.trust import run_with_trust

    fake = FakeProvider(script=[
        _p1_response({1: "kept\nstruck a\nstruck b\nkept2"}),
        _strike_response([{"start_line": 2, "end_line": 3}]),
        _p2_response([{"question_number": 1, "sub_question_id": "א",
                       "answer_text": "kept\nkept2"}]),
    ])
    cfg = _cfg(p1_pages_per_call=1,
               p1_strike_check_model_key="gemini-3.5-flash",
               p2_model_key="gpt-5.4-nano-2026-03-17")
    pipe = _pipe(fake, cfg, 1)

    with tempfile.TemporaryDirectory() as td:
        spec_path = pathlib.Path(td) / "spec.json"
        spec_path.write_text(_json.dumps({"questions": [
            {"number": 1, "sub_questions": ["א"], "context": "Hobby"}]}),
            encoding="utf-8")
        spec = load_exam_spec(spec_path)
        tr = _run(run_with_trust(pipe, b"pdf", "doc", spec))

    # The struck lines are gone from the pages that feed P2 and the draft.
    assert tr.run.pages == {1: "kept\nkept2"}
    assert any(c.phase == "strike_check" for c in tr.run.trace.calls),         "production path never invoked the strike-check pass"
