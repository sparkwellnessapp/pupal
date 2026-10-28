"""The figure pass (MATH_RENDERING_PLAN §5) — FakeProviders, zero network.

  * it reads only pages that NAME a drawing, and returns readings tied to those names;
  * it is OPTIONAL: a provider failure or a garbled answer yields no figures, never an error,
    and the transcription text is never touched;
  * the engine adapter attaches each reading to the answer holding its caption line, and only
    under the `figure` modality.
"""
from __future__ import annotations

import asyncio
import json

from PIL import Image

from app.services.transcription.providers.fake import FakeProvider
from app.services.transcription.scheduler import ProviderLimit, ProviderScheduler
from app.services.transcription.two_phase.figure_pass import parse_figures
from app.services.transcription.two_phase.instrument import Trace
from app.services.transcription.two_phase.pipeline import PipelineRun
from app.services.transcription.two_phase.trust import TrustRun
from tests.transcription_eval_suit.pipelines import PipelineConfig, build_pipeline

PAGE = "ב.\n\\(f'(x)=0\\)\n[איור 1: סקיצה של \\(f\\) עם אסימפטוטה]\n[איור 2: סקיצה של \\(g\\)]"
READING = {"figures": [
    {"figure_no": 1, "kind": "function_sketch", "box_2d": [300, 100, 700, 900], "features": [
        {"kind": "vertical_asymptote", "as_written": "x=2", "point": [420, 515.6],
         "ink": "primary", "uncertain": False},
        {"kind": "minimum", "as_written": "(\\sqrt{e}, -2.25)", "point": [650, 600],
         "ink": "primary", "uncertain": False}]},
    {"figure_no": 7, "kind": "other", "box_2d": [0, 0, 1, 1], "features": []},      # not named
]}


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _pipeline(fig_script, figure_key="claude-haiku-4.5"):
    cfg = PipelineConfig(p1_model_key="gemini-3.1-flash-lite", p2_model_key="gpt-5.4-nano-2026-03-17",
                         p1_figure_model_key=figure_key)
    providers = {"gemini": FakeProvider(script=[]), "anthropic": FakeProvider(script=fig_script),
                 "openai": FakeProvider(script=[])}
    sched = ProviderScheduler({n: ProviderLimit() for n in providers})
    return build_pipeline(cfg, providers, sched), providers


IMAGES = [Image.new("RGB", (100, 140), "white"), Image.new("RGB", (100, 140), "white")]


def test_parse_keeps_named_figures_and_clamps_the_grid():
    figs = parse_figures(READING, page_number=3, wanted={1, 2})
    assert [f.figure_no for f in figs] == [1]                   # 7 is not named on the page
    assert figs[0].page_number == 3
    assert figs[0].features[0].point == [420, 516]
    assert figs[0].features[1].as_written == "(\\sqrt{e}, -2.25)"


def test_parse_drops_a_malformed_feature_not_the_figure():
    data = {"figures": [{"figure_no": 1, "kind": "geometry", "box_2d": [1, 2, 3],
                         "features": [{"kind": "not_a_kind", "as_written": "a"},
                                      {"kind": "side_label", "as_written": "a=3.6", "point": [1, 2],
                                       "ink": "primary", "uncertain": False}]}]}
    figs = parse_figures(data, 1, {1})
    assert figs[0].box_2d is None                               # 3 numbers is not a box
    assert [f.as_written for f in figs[0].features] == ["a=3.6"]


def test_the_pass_reads_only_pages_that_name_a_drawing():
    pipe, providers = _pipeline([FakeProvider.ok(json.dumps(READING))])
    pages = {1: "\\(x=2\\)", 2: PAGE}
    figs = _run(pipe.read_figures(IMAGES, pages, "d", 0, Trace(doc_id="d")))
    assert list(figs) == [2]
    assert [f.figure_no for f in figs[2]] == [1]
    assert len(providers["anthropic"].calls) == 1
    assert "[איור 2:" in providers["anthropic"].calls[0].user      # the names travel with the call


def test_a_failed_or_garbled_pass_yields_no_figures_and_no_error():
    pipe, _ = _pipeline([FakeProvider.ok("NOT JSON"), FakeProvider.ok("NOT JSON")])
    assert _run(pipe.read_figures(IMAGES, {1: "", 2: PAGE}, "d", 0, Trace(doc_id="d"))) == {}


def test_off_when_no_model_key():
    pipe, providers = _pipeline([], figure_key="")
    assert _run(pipe.read_figures(IMAGES, {1: PAGE}, "d", 0, Trace(doc_id="d"))) == {}
    assert providers["anthropic"].calls == []


# ── attachment in the engine adapter ─────────────────────────────────────────

def _trust_run(figures):
    run = PipelineRun(pages={1: "שאלה 4\nא.\n\\(x=1\\)", 2: PAGE},
                      answers={(4, "א"): "\\(x=1\\)", (4, "ב"): PAGE},
                      spec_mismatches=(), routing_notes=(), trace=Trace(doc_id="d"))
    return TrustRun(run=run, flags=(), attributions={}, figures=figures)


def test_each_reading_lands_on_the_answer_holding_its_caption_line():
    from app.services.transcription.two_phase_engine import build_draft_from_trust_run

    figs = {2: parse_figures(READING, 2, {1, 2})}
    draft = build_draft_from_trust_run(_trust_run(figs), page_count=2, duration_ms=1, subject="mathematics")
    by = {(a.question_number, a.sub_question_id): a for a in draft.answers}
    assert [f.figure_no for f in by[(4, "ב")].figures] == [1]
    assert by[(4, "א")].figures == []
    assert by[(4, "ב")].answer_text == PAGE                      # text untouched


def test_no_figures_outside_the_figure_modality():
    from app.services.transcription.two_phase_engine import build_draft_from_trust_run

    figs = {2: parse_figures(READING, 2, {1, 2})}
    draft = build_draft_from_trust_run(_trust_run(figs), page_count=2, duration_ms=1,
                                       subject="computer_science")
    assert all(a.figures == [] for a in draft.answers)
