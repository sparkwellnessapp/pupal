"""parser_render carries the two structural signals a teacher draws without words
(2026-10-25): auto-numbered list labels and visual indentation.

Both were dropped before — `_para_text` stripped every paragraph and nothing read
`<w:numPr>` — so recursion_rubric's sub-criteria (indented under their criterion)
and its ג point list ("1. 25 / 2. 5 / 3. 5", auto-numbered) reached the LLM as
flat, unlabeled lines (owner report, extraction job daa36e9d).
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from docx import Document
from docx.oxml import parse_xml

from app.services.docx_v3.parser_render import (
    _format_ordinal, _hebrew_numeral, render_docx_to_markdown,
)

FIX = Path(__file__).resolve().parents[1] / "rubric_eval_suite" / "fixtures"
W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _lines(md: str) -> list:
    return [l for l in md.splitlines() if l.strip()]


def _docx(paragraph_xml: list, numbering_xml: str = "") -> bytes:
    """A real DOCX (python-docx's default template) with raw <w:p> bodies and,
    optionally, the abstractNum/num definitions appended to its numbering part."""
    doc = Document()
    body = doc.element.body
    sect = body[-1]
    for p in paragraph_xml:
        sect.addprevious(parse_xml(f"<w:p {W}>{p}</w:p>"))
    if numbering_xml:
        numbering = doc.part.numbering_part.element
        for el in parse_xml(f"<w:numbering {W}>{numbering_xml}</w:numbering>"):
            numbering.append(el)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _abstract(abs_id: int, fmt: str, text: str, start: int = 1) -> str:
    return (f'<w:abstractNum w:abstractNumId="{abs_id}"><w:lvl w:ilvl="0">'
            f'<w:start w:val="{start}"/><w:numFmt w:val="{fmt}"/>'
            f'<w:lvlText w:val="{text}"/></w:lvl></w:abstractNum>')


def _num(num_id: int, abs_id: int, restart_at: int = 0) -> str:
    override = (f'<w:lvlOverride w:ilvl="0"><w:startOverride w:val="{restart_at}"/>'
                f'</w:lvlOverride>') if restart_at else ""
    return (f'<w:num w:numId="{num_id}"><w:abstractNumId w:val="{abs_id}"/>'
            f'{override}</w:num>')


def _item(num_id: int, text: str) -> str:
    return (f'<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="{num_id}"/></w:numPr>'
            f'</w:pPr><w:r><w:t xml:space="preserve">{text}</w:t></w:r>')


# --- the counter's spelling ---------------------------------------------------

@pytest.mark.parametrize("n,heb", [(1, "א"), (9, "ט"), (10, "י"), (11, "יא"),
                                   (15, "טו"), (16, "טז"), (20, "כ"), (120, "קכ")])
def test_hebrew1_is_gematria(n, heb):
    assert _hebrew_numeral(n) == heb


def test_an_unspellable_ordinal_is_none_never_a_guess():
    assert _format_ordinal(1000, "hebrew1") is None
    assert _format_ordinal(27, "lowerLetter") is None
    assert _format_ordinal(3, "chicago") is None
    assert _format_ordinal(4, "lowerRoman") == "iv"


# --- list labels ----------------------------------------------------------------

def test_auto_numbered_labels_are_rendered_in_their_own_format():
    numbering = (_abstract(90, "hebrew1", "%1.") + _num(90, 90)
                 + _abstract(91, "decimal", "%1)") + _num(91, 91))
    md = render_docx_to_markdown(_docx(
        [_item(90, "first task"), _item(91, "trace"), _item(91, "example"),
         _item(90, "second task")], numbering))
    assert _lines(md) == ["א. first task", "1) trace", "2) example", "ב. second task"]


def test_two_num_instances_of_one_definition_continue_unless_restarted():
    numbering = (_abstract(92, "decimal", "%1.")
                 + _num(92, 92) + _num(93, 92) + _num(94, 92, restart_at=1))
    md = render_docx_to_markdown(_docx(
        [_item(92, "a"), _item(93, "b"), _item(94, "c")], numbering))
    assert _lines(md) == ["1. a", "2. b", "1. c"]


def test_bullets_and_unspellable_formats_render_no_label():
    numbering = (_abstract(95, "bullet", "") + _num(95, 95)
                 + _abstract(96, "chicago", "%1") + _num(96, 96))
    md = render_docx_to_markdown(_docx([_item(95, "dot"), _item(96, "odd")], numbering))
    assert _lines(md) == ["dot", "odd"]


def test_an_empty_numbered_paragraph_still_takes_its_number():
    numbering = _abstract(97, "decimal", "%1.") + _num(97, 97)
    md = render_docx_to_markdown(_docx(
        [_item(97, "one"), _item(97, ""), _item(97, "three")], numbering))
    assert _lines(md) == ["1. one", "3. three"]


# --- visual indent ----------------------------------------------------------------

def test_leading_tab_and_first_line_indent_survive_as_spaces():
    md = render_docx_to_markdown(_docx([
        '<w:r><w:t>parent 10</w:t></w:r>',
        '<w:r><w:tab/><w:t>part 4</w:t></w:r>',
        '<w:pPr><w:ind w:firstLine="720"/></w:pPr><w:r><w:t>part 6</w:t></w:r>',
        '<w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr><w:r><w:t>flush</w:t></w:r>',
        '<w:r><w:t xml:space="preserve">    code();</w:t></w:r>',
    ]))
    assert _lines(md) == ["parent 10", "    part 4", "    part 6", "flush", "    code();"]


# --- the reported document ----------------------------------------------------------

def test_recursion_rubric_reaches_the_llm_as_the_teacher_drew_it():
    md = render_docx_to_markdown((FIX / "recursion_rubric.docx").read_bytes())
    lines = _lines(md)
    assert [l[:2] for l in lines if l[:2] in ("א.", "ב.", "ג.")] == ["א.", "ב.", "ג."]
    assert [l[:2] for l in lines if l[:2] in ("1)", "2)", "3)")] == ["1)", "2)", "3)"]
    assert lines[-3:] == ["1. 25", "2. 5", "3. 5"]
    start = next(i for i, l in enumerate(lines) if l.startswith("יצירת Length"))
    breakdown = lines[start:start + 11]
    # three criteria flush, eight components indented beneath them
    assert [l.startswith("    ") for l in breakdown] == [
        False, True, True, True, False, True, True, True, False, True, True]


def test_a_nested_list_item_is_indented_by_its_level():
    numbering = ('<w:abstractNum w:abstractNumId="98">'
                 '<w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/><w:lvlText w:val="-"/></w:lvl>'
                 '<w:lvl w:ilvl="1"><w:numFmt w:val="bullet"/><w:lvlText w:val="-"/></w:lvl>'
                 '</w:abstractNum>' + _num(98, 98))
    lvl1 = ('<w:pPr><w:numPr><w:ilvl w:val="1"/><w:numId w:val="98"/></w:numPr></w:pPr>'
            '<w:r><w:t>part 4</w:t></w:r>')
    md = render_docx_to_markdown(_docx([_item(98, "parent 10"), lvl1], numbering))
    assert _lines(md) == ["parent 10", "    part 4"]
