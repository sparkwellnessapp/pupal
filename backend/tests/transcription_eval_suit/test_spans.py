"""
The P2 span contract (two_phase/spans.py) — pure, zero mocks.

The contract's whole value is what it makes IMPOSSIBLE: these tests pin the
by-construction guarantees (verbatim slicing, closed target enum, partition
validation, deterministic salvage) plus the pipeline wiring on fakes.
"""
import json

from .pipelines import PipelineConfig, build_pipeline
from app.services.transcription.providers.fake import FakeProvider
from app.services.transcription.scheduler import ProviderLimit, ProviderScheduler
from app.services.transcription.two_phase.parsing import ExamSpec
from app.services.transcription.two_phase.parsing import load_exam_spec
from app.services.transcription.two_phase.spans import (
    build_span_schema,
    numbered_pages_block,
    parse_and_slice,
    spec_targets,
)

from .test_pipeline_and_runner import _fake_renderer, _p1_response, _run


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _spec(tmp_path) -> ExamSpec:
    p = tmp_path / "spec.json"
    p.write_text(json.dumps({"questions": [
        {"number": 1, "sub_questions": ["א", "ב"], "context": "Hobby"},
        {"number": 2, "sub_questions": [], "context": "bonus"},
    ]}), encoding="utf-8")
    return load_exam_spec(p)


PAGES = {
    1: "שאלה 1\npublic class Hobby\n{\n    int x;\n}",
    2: "ב.\npublic bool F()\n{\n    return true;\n}",
}


def _targets(tmp_path):
    return spec_targets(_spec(tmp_path))


# ---------------------------------------------------------------------------
# Targets + schema
# ---------------------------------------------------------------------------

def test_spec_targets_labels_and_keys(tmp_path):
    ts = _targets(tmp_path)
    assert [(t.label, t.key) for t in ts] == [
        ("1.א", (1, "א")), ("1.ב", (1, "ב")), ("2", (2, None)),
    ]


def test_schema_targets_are_a_closed_enum(tmp_path):
    schema = build_span_schema(_targets(tmp_path))
    enum = schema["properties"]["assignments"]["items"]["properties"]["target"]["enum"]
    assert enum == ["1.א", "1.ב", "2"]
    # Class A (key corruption) is unrepresentable: the key field admits only
    # spec labels, and anchor/plan have their own legal channels.
    assert "anchor" in schema["properties"]["assignments"]["items"]["properties"]
    assert "plan" in schema["properties"]


def test_numbered_pages_block_format():
    block = numbered_pages_block({1: "a\nb"})
    assert block == "--- PAGE 1 (2 lines) ---\n  1| a\n  2| b"


# ---------------------------------------------------------------------------
# Slicing — verbatim by construction
# ---------------------------------------------------------------------------

def _map(assignments, notes=()):
    return {"plan": "x", "assignments": assignments, "notes": list(notes)}


def test_clean_map_slices_verbatim(tmp_path):
    r = parse_and_slice(_map([
        {"target": "1.א", "anchor": "Hobby", "spans": [{"page": 1, "from_line": 2, "to_line": 5}]},
        {"target": "1.ב", "anchor": "F", "spans": [{"page": 2, "from_line": 2, "to_line": 5}]},
        {"target": "2", "anchor": "skip", "spans": []},
    ]), PAGES, _targets(tmp_path))
    assert r.ok
    assert r.answers[(1, "א")] == "public class Hobby\n{\n    int x;\n}"
    assert r.answers[(1, "ב")] == "public bool F()\n{\n    return true;\n}"
    assert r.answers[(2, None)] == ""          # declared skip
    # Marker lines (שאלה 1 / ב.) excluded because the spans exclude them —
    # the slicer adds nothing and drops nothing.


def test_multi_span_cross_page_join_in_listed_order(tmp_path):
    r = parse_and_slice(_map([
        {"target": "1.א", "anchor": "h", "spans": [
            {"page": 1, "from_line": 2, "to_line": 3},
            {"page": 2, "from_line": 3, "to_line": 4},
        ]},
        {"target": "1.ב", "anchor": "f", "spans": [{"page": 2, "from_line": 2, "to_line": 2}]},
        {"target": "2", "anchor": "s", "spans": []},
    ]), PAGES, _targets(tmp_path))
    assert r.answers[(1, "א")] == "public class Hobby\n{\n{\n    return true;"


# ---------------------------------------------------------------------------
# Validation — the partition is CHECKED, not requested
# ---------------------------------------------------------------------------

def test_overlap_is_a_problem_and_first_assignment_wins(tmp_path):
    r = parse_and_slice(_map([
        {"target": "1.א", "anchor": "h", "spans": [{"page": 1, "from_line": 2, "to_line": 4}]},
        {"target": "1.ב", "anchor": "f", "spans": [{"page": 1, "from_line": 4, "to_line": 5}]},
        {"target": "2", "anchor": "s", "spans": []},
    ]), PAGES, _targets(tmp_path))
    assert not r.ok
    assert any("overlap" in p for p in r.problems)
    # Salvage: line 4 stays with 1.א; 1.ב keeps only line 5.
    assert r.answers[(1, "א")].endswith("    int x;")
    assert r.answers[(1, "ב")] == "}"


def test_out_of_range_span_is_clipped_and_flagged(tmp_path):
    r = parse_and_slice(_map([
        {"target": "1.א", "anchor": "h", "spans": [{"page": 1, "from_line": 4, "to_line": 99}]},
        {"target": "1.ב", "anchor": "f", "spans": [{"page": 2, "from_line": 2, "to_line": 5}]},
        {"target": "2", "anchor": "s", "spans": []},
    ]), PAGES, _targets(tmp_path))
    assert any("out of range" in p for p in r.problems)
    assert r.answers[(1, "א")] == "    int x;\n}"   # clipped to lines 4-5


def test_missing_target_is_a_problem_but_yields_empty_answer(tmp_path):
    r = parse_and_slice(_map([
        {"target": "1.א", "anchor": "h", "spans": [{"page": 1, "from_line": 2, "to_line": 5}]},
    ]), PAGES, _targets(tmp_path))
    assert any("missing from assignments" in p for p in r.problems)
    assert r.answers[(1, "ב")] == "" and r.answers[(2, None)] == ""


def test_duplicate_target_concatenates_with_problem(tmp_path):
    r = parse_and_slice(_map([
        {"target": "1.א", "anchor": "h", "spans": [{"page": 1, "from_line": 2, "to_line": 2}]},
        {"target": "1.א", "anchor": "h2", "spans": [{"page": 1, "from_line": 3, "to_line": 3}]},
        {"target": "1.ב", "anchor": "f", "spans": [{"page": 2, "from_line": 2, "to_line": 5}]},
        {"target": "2", "anchor": "s", "spans": []},
    ]), PAGES, _targets(tmp_path))
    assert any("duplicate" in p for p in r.problems)
    assert r.answers[(1, "א")] == "public class Hobby\n{"


# ---------------------------------------------------------------------------
# Pipeline wiring on fakes — contract retry with feedback, honest parse_ok
# ---------------------------------------------------------------------------

def _span_response(assignments):
    return FakeProvider.ok(json.dumps(
        {"plan": "p", "assignments": assignments, "notes": []},
        ensure_ascii=False,
    ))


def _cfg_spans(**kw):
    base = dict(p1_model_key="gemini-3.1-flash-lite",
                p2_model_key="gpt-5.4-nano-2026-03-17",
                p1_pages_per_call=1, p2_output_contract="spans")
    base.update(kw)
    return PipelineConfig(**base)


def test_pipeline_spans_end_to_end_on_fakes(tmp_path):
    fake = FakeProvider(script=[
        _p1_response({1: "שאלה 1\nclass Hobby {}\nreturn true;"}),
        _span_response([
            {"target": "1.א", "anchor": "Hobby", "spans": [{"page": 1, "from_line": 2, "to_line": 2}]},
            {"target": "1.ב", "anchor": "F", "spans": [{"page": 1, "from_line": 3, "to_line": 3}]},
            {"target": "2", "anchor": "skip", "spans": []},
        ]),
    ])
    pipe = build_pipeline(
        _cfg_spans(),
        {"gemini": fake, "openai": fake},
        ProviderScheduler({"gemini": ProviderLimit(), "openai": ProviderLimit()}),
        pdf_renderer=_fake_renderer(1),
    )
    run = _run(pipe.run(b"pdf", "doc", _spec(tmp_path)))
    assert run.answers == {
        (1, "א"): "class Hobby {}",
        (1, "ב"): "return true;",
        (2, None): "",
    }
    # One P1 + one P2 call — no retry burned on a clean map.
    assert len(fake.calls) == 2
    # The P2 call carried the enum schema (class-A guard on the wire).
    assert fake.calls[1].json_schema["properties"]["assignments"][
        "items"]["properties"]["target"]["enum"] == ["1.א", "1.ב", "2"]


def test_pipeline_spans_invalid_map_gets_one_feedback_remap(tmp_path):
    overlapping = [
        {"target": "1.א", "anchor": "h", "spans": [{"page": 1, "from_line": 2, "to_line": 3}]},
        {"target": "1.ב", "anchor": "f", "spans": [{"page": 1, "from_line": 3, "to_line": 3}]},
        {"target": "2", "anchor": "s", "spans": []},
    ]
    clean = [
        {"target": "1.א", "anchor": "h", "spans": [{"page": 1, "from_line": 2, "to_line": 2}]},
        {"target": "1.ב", "anchor": "f", "spans": [{"page": 1, "from_line": 3, "to_line": 3}]},
        {"target": "2", "anchor": "s", "spans": []},
    ]
    fake = FakeProvider(script=[
        _p1_response({1: "שאלה 1\nclass Hobby {}\nreturn true;"}),
        _span_response(overlapping),
        _span_response(clean),
    ])
    pipe = build_pipeline(
        _cfg_spans(),
        {"gemini": fake, "openai": fake},
        ProviderScheduler({"gemini": ProviderLimit(), "openai": ProviderLimit()}),
        pdf_renderer=_fake_renderer(1),
    )
    run = _run(pipe.run(b"pdf", "doc", _spec(tmp_path)))
    # Three calls: P1, invalid P2, feedback remap. Remap user names the violation.
    assert len(fake.calls) == 3
    assert "VIOLATED THE CONTRACT" in fake.calls[2].user
    assert "overlap" in fake.calls[2].user
    # The clean second map won; parse_ok stayed True on BOTH p2 records.
    assert run.answers[(1, "א")] == "class Hobby {}"
    assert all(c.parse_ok for c in run.trace.calls if c.phase == "p2")


def test_pipeline_spans_double_invalid_salvages_with_notes(tmp_path):
    overlapping = [
        {"target": "1.א", "anchor": "h", "spans": [{"page": 1, "from_line": 2, "to_line": 3}]},
        {"target": "1.ב", "anchor": "f", "spans": [{"page": 1, "from_line": 3, "to_line": 3}]},
        {"target": "2", "anchor": "s", "spans": []},
    ]
    fake = FakeProvider(script=[
        _p1_response({1: "שאלה 1\nclass Hobby {}\nreturn true;"}),
        _span_response(overlapping),
        _span_response(overlapping),
    ])
    pipe = build_pipeline(
        _cfg_spans(),
        {"gemini": fake, "openai": fake},
        ProviderScheduler({"gemini": ProviderLimit(), "openai": ProviderLimit()}),
        pdf_renderer=_fake_renderer(1),
    )
    run = _run(pipe.run(b"pdf", "doc", _spec(tmp_path)))
    # Salvage: first-wins on line 3; the resolution is VISIBLE in routing_notes.
    assert run.answers[(1, "א")] == "class Hobby {}\nreturn true;"
    assert run.answers[(1, "ב")] == ""
    assert any("span_contract" in n and "overlap" in n for n in run.routing_notes)