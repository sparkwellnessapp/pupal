"""Pure unit tests for the ground-truth parser. Zero mocks; runs in `pytest -q`."""
from pathlib import Path

import pytest

from .ground_truth import load_ground_truth, parse_ground_truth

DRAFT_BENCHMARKS = Path(__file__).parent / "draft_benchmarks"
RAW_BENCHMARKS = Path(__file__).parent / "raw_benchmarks"


def test_parses_two_answers_with_keys_and_bodies():
    md = (
        "=== Q1.א ===\n"
        "public class Hobby\n"
        "{\n}\n"
        "\n"
        "=== Q1.ב ===\n"
        "While (x)\n"
    )
    doc = parse_ground_truth(md, doc_id="t")
    assert [a.key for a in doc.answers] == [(1, "א"), (1, "ב")]
    assert doc.answers[0].answer_text == "public class Hobby\n{\n}"
    # Body preserved verbatim (the "While" capitalization bug is kept).
    assert doc.answers[1].answer_text == "While (x)"


def test_question_without_sub_id():
    doc = parse_ground_truth("=== Q3 ===\nreturn x;\n", doc_id="t")
    assert doc.answers[0].key == (3, None)


def test_duplicate_key_raises():
    md = "=== Q2.ג ===\na\n=== Q2.ג ===\nb\n"
    with pytest.raises(ValueError, match="duplicate"):
        parse_ground_truth(md, doc_id="t")


def test_no_delimiters_raises():
    with pytest.raises(ValueError, match="no '=== Q"):
        parse_ground_truth("just some text", doc_id="t")


def test_as_dict_and_order():
    doc = parse_ground_truth("=== Q1 ===\na\n=== Q2 ===\nb\n", doc_id="t")
    assert doc.keys_in_order() == [(1, None), (2, None)]
    assert doc.as_dict() == {(1, None): "a", (2, None): "b"}


@pytest.mark.skipif(
    not (DRAFT_BENCHMARKS / "hobby_tvshow.moran_aharon.md").exists(),
    reason="benchmark fixture not present (real student data lives outside git)",
)
def test_moran_aharon_fixture_structure():
    """The real converted fixture parses into the six expected answers."""
    doc = load_ground_truth(DRAFT_BENCHMARKS / "hobby_tvshow.moran_aharon.md")
    assert doc.doc_id == "hobby_tvshow.moran_aharon"
    assert doc.keys_in_order() == [
        (1, "א"), (1, "ב"), (1, "ג"),
        (2, "א"), (2, "ב"), (2, "ג"),
    ]
    # Verbatim preservation spot-checks: abbreviations and student bugs kept,
    # Hebrew section headers excluded from bodies.
    q1b = doc.as_dict()[(1, "ב")]
    assert "CW(" in q1b and "CR()" in q1b        # abbreviations preserved
    assert "While (" in q1b                       # capitalization bug preserved
    assert "שאלה" not in q1b                       # header excluded from body
    q2g = doc.as_dict()[(2, "ג")]
    # NOTE: the original spot-check asserted "[?]" here; Noam's GT verification
    # pass (2026-06) resolved that illegible span, so the fixture legitimately
    # no longer contains it (the [?] convention itself is covered by the parser
    # tests above). Keep the structural checks that remain true of the fixture.
    assert "שאלה 2 ג" not in q2g                   # duplicate header line removed


# --- Phase-1 (raw / per-page) format ---------------------------------------------

from .ground_truth import load_page_ground_truth, parse_page_ground_truth


def test_page_parser_basic():
    doc = parse_page_ground_truth(
        "=== PAGE 1 ===\nשאלה 1\ncode here\n\n=== PAGE 2 ===\nmore code\n",
        doc_id="t",
    )
    assert [p.page_number for p in doc.pages] == [1, 2]
    # Headers are ink — verbatim format KEEPS them (unlike per-question format).
    assert "שאלה 1" in doc.pages[0].text
    assert doc.pages[1].text == "more code"


def test_page_parser_duplicate_page_raises():
    with pytest.raises(ValueError, match="duplicate page"):
        parse_page_ground_truth("=== PAGE 1 ===\na\n=== PAGE 1 ===\nb\n", doc_id="t")


def test_page_parser_gap_raises():
    with pytest.raises(ValueError, match="not contiguous"):
        parse_page_ground_truth("=== PAGE 1 ===\na\n=== PAGE 3 ===\nb\n", doc_id="t")


def test_page_parser_requires_delimiters():
    with pytest.raises(ValueError, match="no '=== PAGE"):
        parse_page_ground_truth("plain text", doc_id="t")


ALL_FIXTURES = [
    # doc_id = "<exam_id>.<student>" — the corpus spans several exams, so a bare
    # student name no longer identifies a fixture (2026-08-29).
    "hobby_tvshow.moran_aharon", "hobby_tvshow.dan_basiuk", "hobby_tvshow.din_ezra",
    "hobby_tvshow.omer_gelber", "hobby_tvshow.yonatan_basiuk",
]


@pytest.mark.skipif(
    not (Path(__file__).parent / "raw_benchmarks").exists()
    or not list((Path(__file__).parent / "raw_benchmarks").glob("*.md")),
    reason="raw benchmark fixtures not present (real student data lives outside git)",
)
def test_all_raw_fixtures_parse():
    for name in ALL_FIXTURES:
        path = RAW_BENCHMARKS / f"{name}.md"
        assert path.exists(), f"missing raw fixture {name}"
        doc = load_page_ground_truth(path)
        assert len(doc.pages) >= 3
        # Canonical vocabulary: author-marks converted, only [?] remains.
        joined = "\n".join(p.text for p in doc.pages)
        assert "[crossed out]" not in joined
        assert "[illegible]" not in joined


@pytest.mark.skipif(
    not (Path(__file__).parent / "draft_benchmarks").exists()
    or not list((Path(__file__).parent / "draft_benchmarks").glob("*.md")),
    reason="draft benchmark fixtures not present (real student data lives outside git)",
)
def test_all_draft_fixtures_conform_to_their_exam_spec():
    """Every draft fixture's answer keys are EXACTLY its own exam's keys.

    This replaces a hardcoded six-key list that was true only of the hobby/TvShow
    corpus and failed a new-exam fixture by construction. It is also strictly
    stronger: nothing previously checked a fixture's GT against the exam it
    claims to answer, so a key the spec does not declare — which P2 can never
    emit, since `spans.spec_targets` builds a closed enum from the spec — used
    to sit undetected until it showed up as a permanent coverage failure.

    EQUALITY, not subset (D3 ruling, Noam 2026-08-28): a question the student
    left blank still gets its `=== Q.. ===` block with an empty body. This is
    load-bearing for SELECTION exams ("answer 4 of 6"), where whole unanswered
    questions are the norm — the span contract emits every spec target's key
    regardless (spans.py: absent target -> empty answer), so an empty gold meets
    an empty prediction and scores 1.0, while a model that INVENTS content for an
    unanswered question scores 0.0 and is flagged. Omitting the block instead
    would hide that invention in `extra_keys`."""
    from .exam_resolution import resolve_exam, spec_keys
    from .keys import normalize_key

    for name in ALL_FIXTURES:
        path = DRAFT_BENCHMARKS / f"{name}.md"
        assert path.exists(), f"missing draft fixture {name}"
        doc = load_ground_truth(path)

        exam = resolve_exam(name, fallback_spec_path="draft.json")
        assert exam is not None, f"{name}: no exam spec resolved"
        expected = spec_keys(exam.spec)
        actual = [normalize_key(k) for k in doc.keys_in_order()]
        assert actual == expected, (
            f"{name}: draft GT keys {actual} != exam {exam.ref} keys {expected}. "
            f"Every declared answer gets exactly one block, in spec order; an "
            f"unanswered question gets an EMPTY body, not a missing block."
        )

        joined = "\n".join(a.answer_text for a in doc.answers)
        assert "[crossed out]" not in joined
        assert "[illegible]" not in joined
        assert "שאלה" not in joined  # headers excluded from answer bodies


def test_all_fixtures_list_matches_the_raw_benchmarks_folder():
    """`raw_benchmarks/` IS the runner's fixture registry — the default eval run
    globs it (runner.main), so a raw GT landing there joins every run and the
    /goal STOP gate the moment it is written. Requiring the list and the folder
    to agree turns a half-landed fixture into a loud `pytest -q` failure instead
    of a silent change to what the benchmark means."""
    on_disk = {p.stem for p in RAW_BENCHMARKS.glob("*.md")}
    if not on_disk:
        pytest.skip("raw benchmark fixtures not present")
    assert set(ALL_FIXTURES) == on_disk, (
        f"ALL_FIXTURES and raw_benchmarks/ disagree — "
        f"only in list: {sorted(set(ALL_FIXTURES) - on_disk)}; "
        f"only on disk: {sorted(on_disk - set(ALL_FIXTURES))}. "
        f"Land a fixture's raw GT, draft GT, PDF and manifest together."
    )
