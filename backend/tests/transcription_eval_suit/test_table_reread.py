"""Recommendation #1 wiring on fakes: a page with a table is re-read by the table
model and only its grid is swapped in; a page without one costs nothing."""
import asyncio
import json

from PIL import Image

from app.services.transcription.providers.fake import FakeProvider
from app.services.transcription.scheduler import ProviderLimit, ProviderScheduler

from .pipelines import PipelineConfig, build_pipeline

SPLIT = "א.\n| x | i\n(cond) |\n| 6 | 0 |\n2) הסבר"
GRID = "א.\n| x | i | cond |\n| 6 | 0 | T |\n2) הסבר אחר"


def _p(text):
    return FakeProvider.ok(json.dumps({"pages": [{"page_number": 1, "text": text}]}))


def _perceive(script, **kw):
    fake = FakeProvider(script=script)
    cfg = PipelineConfig(p1_model_key="gemini-3.1-flash-lite", p1_pages_per_call=1, **kw)
    pipe = build_pipeline(
        cfg, {"gemini": fake, "openai": fake},
        ProviderScheduler({"gemini": ProviderLimit(), "openai": ProviderLimit()}),
        pdf_renderer=lambda b, d: [Image.new("RGB", (40, 60), "white")])
    pages, _ = asyncio.new_event_loop().run_until_complete(pipe.run_phase1(b"pdf", "doc"))
    return pages, fake


ON = dict(p1_table_reread_model_key="gemini-3.1-flash-lite")


def test_off_is_one_call_and_untouched():
    pages, fake = _perceive([_p(SPLIT)])
    assert len(fake.calls) == 1 and pages[1] == SPLIT


def test_on_swaps_only_the_grid():
    pages, fake = _perceive([_p(SPLIT), _p(GRID)], **ON)
    assert len(fake.calls) == 2
    assert pages[1] == "א.\n| x | i | cond |\n| 6 | 0 | T |\n2) הסבר"      # P1's prose kept


def test_a_page_without_a_table_is_never_reread():
    pages, fake = _perceive([_p("int x = 0; // מונה")], **ON)
    assert len(fake.calls) == 1


def test_a_failed_reread_keeps_p1s_page():
    pages, fake = _perceive([_p(SPLIT), FakeProvider.ok("not json")], **ON)
    assert pages[1] == SPLIT
