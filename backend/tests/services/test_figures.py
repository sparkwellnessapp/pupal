"""Figure lines ↔ readings, FIG-1, and what the grader reads (MATH_RENDERING_PLAN §5). Pure."""
from __future__ import annotations

from types import SimpleNamespace as A

import pytest
from pydantic import ValidationError

from app.schemas.transcription import (
    Figure, FigureFeature, TranscriptionContractAnswer, TranscriptionDraft, TranscriptionDraftAnswer,
)
from app.services.figures import expand_figure_lines, feature_line, figure_lines, match_figures
from app.services.transcription_contract import build_transcription_contract

ASYM = FigureFeature(kind="vertical_asymptote", as_written="x=2", point=[400, 520])
MIN = FigureFeature(kind="minimum", as_written=r"(\sqrt{e}, -2.25)", point=[700, 610])
PINK = FigureFeature(kind="vertical_asymptote", as_written="x=0", ink="other", uncertain=True)


def fig(page, n, *features):
    return Figure(figure_no=n, page_number=page, kind="function_sketch",
                  box_2d=[300, 100, 800, 900], features=list(features))


TEXT = "ב.\n[איור 1: סקיצה של f]\n\\(f'(x)=0\\)\n[איור 1: סקיצה של g]"


def test_figure_lines_are_found_in_order():
    assert figure_lines(TEXT) == [(1, 1), (3, 1)]
    assert figure_lines("no figures") == []


def test_two_pages_numbered_one_are_told_apart_by_page_order():
    f10, f11 = fig(10, 1, ASYM), fig(11, 1, MIN)
    m = match_figures(TEXT, [f11, f10])
    assert [(i, f.page_number) for i, f in m.pairs] == [(1, 10), (3, 11)]
    assert m.unread_lines == () and m.orphans == ()


def test_an_unread_line_is_allowed_and_recorded():
    m = match_figures(TEXT, [fig(10, 1, ASYM)])
    assert m.unread_lines == (3,)
    assert m.orphans == ()


def test_a_figure_without_its_line_is_an_orphan():
    m = match_figures("ב.\n\\(x=2\\)", [fig(10, 1, ASYM)])
    assert len(m.orphans) == 1


# ── FIG-1 on the contract type ────────────────────────────────────────────────

def test_fig1_refuses_a_frozen_figure_with_no_line():
    with pytest.raises(ValidationError, match="FIG-1"):
        TranscriptionContractAnswer(question_number=1, answer_text="\\(x=2\\)",
                                    figures=[fig(10, 1, ASYM)])


def test_fig1_accepts_a_figure_on_its_line_and_an_unread_line():
    a = TranscriptionContractAnswer(question_number=1, answer_text=TEXT, figures=[fig(10, 1, ASYM)])
    assert len(a.figures) == 1


def _draft(text, figures):
    return TranscriptionDraft(page_count=12, answers=[TranscriptionDraftAnswer(
        question_number=4, sub_question_id="ב", answer_text=text, confidence=0.9,
        page_numbers=[10, 11], figures=figures)])


def test_the_builder_freezes_the_drafts_figures_untouched():
    d = _draft(TEXT, [fig(10, 1, ASYM), fig(11, 1, MIN)])
    c = build_transcription_contract(d.answers, d)
    assert [f.page_number for f in c.answers[0].figures] == [10, 11]


def test_her_reviewed_figures_win():
    d = _draft(TEXT, [fig(10, 1, ASYM)])
    mine = [fig(10, 1, FigureFeature(kind="vertical_asymptote", as_written="x=3", source="teacher"))]
    c = build_transcription_contract(
        [A(question_number=4, sub_question_id="ב", answer_text=TEXT, figures=mine)], d)
    assert c.answers[0].figures[0].features[0].as_written == "x=3"


def test_a_figure_whose_line_she_deleted_goes_with_the_line():
    d = _draft(TEXT, [fig(10, 1, ASYM), fig(11, 1, MIN)])
    edited = "ב.\n[איור 1: סקיצה של f]\n\\(f'(x)=0\\)"          # the g sketch line removed
    c = build_transcription_contract(
        [A(question_number=4, sub_question_id="ב", answer_text=edited)], d)
    assert [f.page_number for f in c.answers[0].figures] == [10]


# ── what the grader reads ─────────────────────────────────────────────────────

def test_each_reading_becomes_one_quotable_line_after_its_figure_line():
    out = expand_figure_lines(TEXT, [fig(10, 1, ASYM, MIN), fig(11, 1, PINK)])
    assert out.split("\n") == [
        "ב.",
        "[איור 1: סקיצה של f]",
        "איור 1 · אסימפטוטה אנכית: \\(x=2\\)",
        "איור 1 · נקודת מינימום: \\((\\sqrt{e}, -2.25)\\)",
        "\\(f'(x)=0\\)",
        "[איור 1: סקיצה של g]",
        "איור 1 · אסימפטוטה אנכית: \\(x=0\\) (לא ודאי, בצבע אחר)",
    ]


def test_no_figures_is_the_identity():
    assert expand_figure_lines(TEXT, []) == TEXT


def test_an_expanded_line_is_not_a_figure_line():
    assert figure_lines(expand_figure_lines(TEXT, [fig(10, 1, ASYM)])) == [(1, 1), (4, 1)]


def test_a_quote_of_a_reading_validates_against_the_expanded_answer():
    from app.agents.grader.validator import quote_match_status
    from app.schemas.ontology_types import QuoteValidationStatus

    answer = expand_figure_lines(TEXT, [fig(10, 1, ASYM)])
    assert quote_match_status(feature_line(1, ASYM), answer) == QuoteValidationStatus.EXACT


def test_the_gradable_compiler_hands_the_grader_the_expanded_text():
    """EVD-1: `student_answer_text` is what the grader consumes and what the gate shows."""
    from tests.services.test_gradable_compiler import _contract, _criterion, _question
    from app.services import gradable_compiler

    draft = TranscriptionDraft(page_count=12, answers=[TranscriptionDraftAnswer(
        question_number=4, answer_text=TEXT, confidence=0.9, page_numbers=[10],
        figures=[fig(10, 1, ASYM)])])
    transcription = build_transcription_contract(draft.answers, draft)
    rubric = _contract([_question("q4", 10, [_criterion("q4.c0")])])
    scope = gradable_compiler.compile(rubric, transcription).scopes[0]
    assert scope.student_answer_text == expand_figure_lines(TEXT, [fig(10, 1, ASYM)])
    assert "איור 1 · אסימפטוטה אנכית: \\(x=2\\)" in scope.student_answer_text
