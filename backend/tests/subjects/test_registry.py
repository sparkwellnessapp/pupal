"""The subject registry + the prompt assembly rules (multisubject seam, Phase 1).

Pure tests — no DB, no provider. The CS byte-identity pins live in
test_prompt_identity.py; this file covers everything the seam promises for the
OTHER subjects: unknown keys refuse, stamps carry the suffix, fragments stay
short, and a non-CS verifier never sees the code-trace rules.
"""
from __future__ import annotations

import pytest

from app.subjects import UnknownSubject, get_profile, prompt_version, subject_keys
from app.schemas.ontology_types import QuestionType, SUBJECT_PROFILES


def test_registry_names_exactly_the_ontology_subjects():
    assert subject_keys() == ("computer_science", "english", "mathematics")
    assert set(subject_keys()) == set(SUBJECT_PROFILES)


@pytest.mark.parametrize("bad", ["physics", "math", "", None, "Computer_Science"])
def test_unknown_subject_refuses_never_defaults(bad):
    with pytest.raises(UnknownSubject):
        get_profile(bad)


def test_stamp_rule_d16():
    cs, en, ma = (get_profile(k) for k in ("computer_science", "english", "mathematics"))
    assert prompt_version("grader-v5.4", cs) == "grader-v5.4"
    assert prompt_version("grader-v5.4", en) == "grader-v5.4+english"
    assert prompt_version("t1.4-tables", ma) == "t1.4-tables+mathematics"
    assert prompt_version("3.10.0-fixsource", ma) == "3.10.0-fixsource+mathematics"


def test_baseline_profile_has_no_fragments_and_the_cs_keywords():
    cs = get_profile("computer_science")
    assert cs.is_baseline
    assert cs.extraction_fragment is None and cs.p1_fragment is None and cs.verify_fragment is None
    assert {"class", "int", "void", "while"} <= cs.p2_keywords
    assert cs.default_question_type is QuestionType.CODING_TASK


@pytest.mark.parametrize("key", ["english", "mathematics"])
def test_non_cs_fragments_are_short_and_present(key):
    p = get_profile(key)
    assert not p.is_baseline
    assert p.p2_keywords == frozenset()
    for name in ("extraction_fragment", "p1_fragment", "verify_fragment"):
        text = getattr(p, name)
        assert text, f"{key}.{name} missing"
        lines = [l for l in text.splitlines() if l.strip()]
        assert len(lines) <= 12, f"{key}.{name} has {len(lines)} lines (> 12, execution plan §4.1)"


def test_modalities_are_data_not_types():
    assert get_profile("english").modalities == frozenset({"prose"})
    assert get_profile("mathematics").modalities == frozenset({"math_notation", "prose", "figure"})
    assert get_profile("computer_science").modalities == frozenset({"code", "prose"})


# --- assembly: the non-CS prompts must not carry the CS rules -----------------

_CS_VERIFIER_STRINGS = (
    "SURFACE FORM IS NEVER A DEFECT",        # pinned by tests/agents/test_grader_v5_agent.py
    "is the authority on naming and form",   # pinned by tests/agents/test_grader_v5_agent.py
    "VERIFY WHAT THE WRITTEN CODE DOES",
    "a missing semicolon, garbled braces",
)


@pytest.mark.parametrize("key", ["english", "mathematics"])
def test_non_cs_verifier_assembly_excludes_the_pinned_cs_strings(key):
    from app.agents.grader.verifier_prompt import VERIFIER_SYSTEM_PROMPT, verifier_system_prompt

    text = verifier_system_prompt(get_profile(key))
    assert text != VERIFIER_SYSTEM_PROMPT
    for s in _CS_VERIFIER_STRINGS:
        assert s not in text, f"{key}: CS rule leaked into the verifier: {s!r}"
    # rules 1-2 and 6-8 + the output contract survive
    for kept in ("1. Verify ONLY the check IDs", "2. EVIDENCE BEFORE VERDICT",
                 "6. VERDICT MEANINGS", "8. basis_he is LEAN", "OUTPUT FORMAT"):
        assert kept in text, f"{key}: lost {kept!r}"
    assert "3. VERIFY WHAT THE STUDENT WROTE" in text


@pytest.mark.parametrize("key", ["english", "mathematics"])
def test_non_cs_p1_assembly_replaces_only_the_ink_rules(key):
    from app.services.transcription.two_phase.prompts import P1_SYSTEM, p1_system

    text = p1_system(get_profile(key))
    assert text != P1_SYSTEM
    for cs_only in ("`CW`", "minuteS", "wrong comment delimiters", "code, comments"):
        assert cs_only not in text, f"{key}: CS ink rule leaked into P1: {cs_only!r}"
    # everything else survives: markers, identity exclusion, [?], table grid, output shape
    for kept in ("Section markers are the ONE formatting exception", "EXCLUDE the student's identity",
                 "Use `[?]`", "A hand-drawn TABLE", '{"pages": [{"page_number": <int>'):
        assert kept in text, f"{key}: lost {kept!r}"
    # P1 stays spec-blind: no rubric vocabulary in the fragment
    assert "rubric" not in text.lower().split("exam pages")[0]


def test_p1_math_fragment_prescribes_the_linear_convention_and_the_figure_line():
    from app.services.transcription.two_phase.prompts import p1_system

    text = p1_system(get_profile("mathematics"))
    assert "Never solve, simplify, or correct" in text
    assert "`(numerator)/(denominator)`" in text and "`sqrt(...)`" in text
    assert "[איור:" in text


def test_p1_english_fragment_keeps_paragraphs_and_misspellings():
    from app.services.transcription.two_phase.prompts import p1_system

    text = p1_system(get_profile("english"))
    assert "Preserve paragraph breaks as one blank line" in text
    assert "Transcribe misspellings exactly" in text


def test_extraction_assembly_appends_the_subject_section_only():
    from app.services.docx_v3.pipeline import EXTRACTION_SYSTEM_PROMPT, RubricExtraction, extraction_system_prompt

    for key in ("english", "mathematics"):
        text = extraction_system_prompt(get_profile(key))
        assert text.startswith(EXTRACTION_SYSTEM_PROMPT)
        assert f"SUBJECT: {key.upper()}" in text
    # D-10: the model never chooses the subject
    assert "subject" not in RubricExtraction.model_json_schema()["properties"]


def test_p2_is_the_same_text_for_every_profile_this_cycle():
    """ALPHA-GAP A-8 — P2 wording per modality is alpha; today the seam exists but is inert."""
    from app.services.transcription.two_phase.prompts import (
        P2_SPAN_SYSTEM, p2_span_system, p2_system_prompt,
    )

    base = p2_system_prompt()
    for key in subject_keys():
        p = get_profile(key)
        assert p2_system_prompt(p) == base
        assert p2_span_system(p) == P2_SPAN_SYSTEM


def test_p2_identifier_filter_uses_the_profile_keyword_set():
    from app.services.transcription.two_phase.parsing import _extract_identifiers

    text = "public class Interface Hobby"
    cs = _extract_identifiers(text, keywords=get_profile("computer_science").p2_keywords)
    en = _extract_identifiers(text, keywords=get_profile("english").p2_keywords)
    assert "Hobby" in cs and "Interface" not in cs           # `interface` is a CS keyword
    assert "Interface" in en                                 # prose: no keyword filter
    assert _extract_identifiers(text) == cs                  # default == the pre-seam behaviour


def test_gradable_test_carries_the_contract_subject_as_a_key_only():
    from app.schemas.gradable import GradableTest

    fields = GradableTest.model_fields
    assert "subject" in fields and fields["subject"].default == "computer_science"
    assert "modalities" not in fields  # C2 "where it leaks": never on the grader's input type


def test_question_type_coercion_is_a_log_never_an_error(caplog):
    from decimal import Decimal

    from app.schemas.ontology_types import Criterion, Question
    from app.services.contract_compiler import _coerce_question_types

    q = Question(question_id="q1", question_type=QuestionType.CODING_TASK,
                 total_points=Decimal("10"),
                 criteria=[Criterion(criterion_id="q1.c0", index=0, description="x", points=Decimal("10"))])
    # CS: coding_task is in-profile → untouched (byte-identical contracts)
    assert _coerce_question_types("computer_science", [q])[0].question_type is QuestionType.CODING_TASK
    # english: coding_task is out-of-profile → coerced to the default, logged
    with caplog.at_level("INFO"):
        out = _coerce_question_types("english", [q])
    assert out[0].question_type is QuestionType.SHORT_ANSWER
    assert any("question_type_coerced" in r.message for r in caplog.records)
    # unknown subject: untouched, logged, never raises
    assert _coerce_question_types("physics", [q])[0].question_type is QuestionType.CODING_TASK
