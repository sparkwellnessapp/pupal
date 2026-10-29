"""Bet 3 wiring on fakes: P1 reports instruction marks, the pure relocation
function applies them between P1 and P2, P2 sees the moved text, P1 stays scored
on the physical pages — and with the flag OFF nothing about the pipeline changes."""
import asyncio
import json

from PIL import Image

from app.services.transcription.providers.fake import FakeProvider
from app.services.transcription.scheduler import ProviderLimit, ProviderScheduler
from app.services.transcription.two_phase.prompts import (
    P1_SCHEMA, P1_SCHEMA_WITH_INSTRUCTIONS, P1_SYSTEM,
)

from .parsing import load_exam_spec
from .pipelines import PipelineConfig, build_pipeline

PAGE = "public void F()\n{\nreturn;\n}\nint y = 1;"


def _run(c):
    return asyncio.new_event_loop().run_until_complete(c)


def _spec(tmp_path):
    p = tmp_path / "spec.json"
    p.write_text(json.dumps({"questions": [{"number": 1, "sub_questions": [],
                                            "context": "F"}]}), encoding="utf-8")
    return load_exam_spec(p)


def _p1(instructions=None):
    page = {"page_number": 1, "text": PAGE}
    if instructions is not None:
        page["instructions"] = instructions
    return FakeProvider.ok(json.dumps({"pages": [page]}))


def _p2_echo():
    # legacy text contract: P2 returns whatever page text it was handed
    return FakeProvider.ok(json.dumps({"answers": [], "spec_mismatches": [],
                                       "routing_notes": []}))


INSERT = [{"kind": "insertion", "marker": "arrow", "first_words": "int y",
           "last_words": "= 1;", "target_page": 1, "after": "{",
           "before": "return;", "line": ""}]


def _pipe(fake, **kw):
    cfg = PipelineConfig(p1_model_key="gemini-3.1-flash-lite",
                         p2_model_key="gpt-5.4-nano-2026-03-17",
                         p1_pages_per_call=1, **kw)
    return build_pipeline(
        cfg, {"gemini": fake, "openai": fake},
        ProviderScheduler({"gemini": ProviderLimit(), "openai": ProviderLimit()}),
        pdf_renderer=lambda b, d: [Image.new("RGB", (40, 60), "white")],
    )


def test_flag_on_relocates_between_p1_and_p2(tmp_path):
    fake = FakeProvider(script=[_p1(INSERT), _p2_echo()])
    run = _run(_pipe(fake, p1_instructions=True).run(b"pdf", "doc", _spec(tmp_path)))
    # P1 asked with the instruction schema and the extended prompt
    p1_call = fake.calls[0]
    assert "instructions" in json.dumps(p1_call.json_schema)
    assert "Instruction marks" in p1_call.system
    # the physical page is preserved for P1 scoring; P2 got the moved text
    assert run.pages_before_relocation == {1: PAGE}
    assert run.pages[1] == "public void F()\n{\nint y = 1;\nreturn;\n}"
    assert "int y = 1;" in fake.calls[1].user and len(run.relocation.applied) == 1


def test_flag_off_is_the_historical_pipeline(tmp_path):
    fake = FakeProvider(script=[_p1(), _p2_echo()])
    run = _run(_pipe(fake).run(b"pdf", "doc", _spec(tmp_path)))
    assert fake.calls[0].system == P1_SYSTEM
    assert fake.calls[0].json_schema == P1_SCHEMA
    assert run.relocation is None and run.pages_before_relocation is None
    assert run.pages == {1: PAGE}


def test_an_ambiguous_instruction_leaves_the_text_in_place(tmp_path):
    bad = [dict(INSERT[0], after="", before="")]         # no target at all
    fake = FakeProvider(script=[_p1(bad), _p2_echo()])
    run = _run(_pipe(fake, p1_instructions=True).run(b"pdf", "doc", _spec(tmp_path)))
    assert run.pages == {1: PAGE}
    assert run.relocation.rejected and not run.relocation.applied


def test_malformed_instruction_items_are_dropped_not_guessed(tmp_path):
    junk = [{"kind": "teleport"}, "nonsense", {"kind": "insertion", "target_page": "x"}]
    fake = FakeProvider(script=[_p1(junk), _p2_echo()])
    run = _run(_pipe(fake, p1_instructions=True).run(b"pdf", "doc", _spec(tmp_path)))
    assert run.pages == {1: PAGE} and not run.relocation.applied


def test_the_instruction_schema_is_the_page_schema_plus_one_field():
    base = P1_SCHEMA["properties"]["pages"]["items"]["properties"]
    ext = P1_SCHEMA_WITH_INSTRUCTIONS["properties"]["pages"]["items"]["properties"]
    assert set(ext) - set(base) == {"instructions"}


def test_the_prompt_stamp_names_every_prompt_variant_that_is_on():
    from app.services.transcription.two_phase.pipeline import _prompt_base
    from app.services.transcription.two_phase.prompts import TRANSCRIPTION_PROMPT_VERSION as V
    assert _prompt_base(PipelineConfig(p1_model_key="x")) == V   # all off: unchanged
    on = PipelineConfig(p1_model_key="x", p1_table_rows=True, p1_instructions=True)
    assert _prompt_base(on) == V + "+rows+instr-r1"
