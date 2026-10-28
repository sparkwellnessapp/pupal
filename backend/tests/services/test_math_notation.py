"""app/services/math_notation — pure, zero mocks (MATH_RENDERING_PLAN §4).

The spans vectors are shared with the frontend (`src/utils/math-spans.test.ts`): one
definition of "where the math is", two languages, one file of cases.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.math_notation import (
    canonicalize, check_math_answer, has_math, linearize, split_math,
)
from app.services.math_notation.canonical import canonical_math_body
from app.services.math_notation.linearize import LRE, NBSP, PDF, linearize_math_body

VECTORS = json.loads((Path(__file__).parents[1] / "fixtures" / "math_spans_vectors.json")
                     .read_text(encoding="utf-8"))


# ── spans ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("case", VECTORS["cases"], ids=[c["name"] for c in VECTORS["cases"]])
def test_spans_match_the_shared_vectors(case):
    res = split_math(case["text"])
    got = [[s.kind, s.start, s.end, s.body_start, s.body_end] for s in res.segments]
    assert got == case["segments"]
    assert list(res.unclosed_at) == case["unclosed"]
    assert list(res.stray_close_at) == case["stray"]


@pytest.mark.parametrize("case", VECTORS["cases"], ids=[c["name"] for c in VECTORS["cases"]])
def test_segments_tile_the_string_exactly(case):
    """No byte is lost or doubled: the answer string stays the only truth."""
    text = case["text"]
    segs = split_math(text).segments
    assert "".join(text[s.start:s.end] for s in segs) == text


def test_has_math():
    assert has_math(r"ש \(x\)")
    assert not has_math("public int x;")
    assert not has_math("")


# ── validator ─────────────────────────────────────────────────────────────────

def _codes(text):
    return [i.code for i in check_math_answer(text)]


def test_a_clean_math_answer_has_no_issues():
    text = ("נגזרת: \\(f'(x) = \\frac{1}{x} - 2x\\)\n"
            "\\(\\begin{cases} x + y = 3 \\\\ x - y = 1 \\end{cases}\\)\n"
            "| x | \\(0<x<\\sqrt{e}\\) | \\(\\sqrt{e}\\) |\n"
            "| f'(x) | - | 0 |\n"
            "| f(x) | \\(\\searrow\\) | \\(\\cup\\) |")
    assert check_math_answer(text) == []


@pytest.mark.parametrize("text,code", [
    (r"ש \(x+1", "unclosed_span"),
    (r"x\) ו", "stray_close"),
    (r"\(\frac{1}{2\)", "unbalanced_braces"),
    (r"\(x}\)", "unbalanced_braces"),
    (r"\(\begin{aligned} a &= b \end{aligned}\)", "forbidden_env"),
    (r"\(\begin{gather} a \end{gather}\)", "forbidden_env"),
    (r"\(\begin{cases} a \end{matrix}\)", "env_mismatch"),
    (r"\(\begin{cases} a \)", "env_mismatch"),
    (r"\[x=2\]", "display_math"),
    (r"$$x$$", "display_math"),
    (r"שווה ל- \frac{1}{2}", "command_outside_span"),
    (r"\(x \text{ מ\"ר}\)", "hebrew_in_span"),
])
def test_each_defect_is_reported(text, code):
    assert code in _codes(text)


def test_literal_braces_are_not_unbalanced():
    assert check_math_answer(r"\(\{x \mid x>0\}\)") == []
    assert check_math_answer(r"\(\left\{ x \right.\)") == []


def test_cases_is_allowed_and_aligned_is_not():
    assert _codes(r"\(\begin{cases} a \\ b \end{cases}\)") == []
    assert _codes(r"\(\begin{aligned} a \\ b \end{aligned}\)") == ["forbidden_env"]


def test_an_unclosed_span_reports_once_not_once_per_command():
    assert _codes(r"\(\frac{1}{2} + \sqrt{3}") == ["unclosed_span"]


def test_the_validator_never_changes_the_text():
    text = r"ש \(\frac{1}{2\) ו \frac x"
    before = str(text)
    check_math_answer(text)
    assert text == before


# ── canonicaliser ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("a,b", [
    (r"\dfrac{1}{e}", r"\frac{1}{e}"),
    (r"\frac12", r"\frac{1}{2}"),
    (r"x^2", r"x^{2}"),
    (r"x_1", r"x_{1}"),
    (r"\sqrt e", r"\sqrt{e}"),
    (r"\left( \frac{1}{e}, 0 \right)", r"(\frac{1}{e},0)"),
    (r"a \le b", r"a\leq b"),
    (r"a \leq b", r"a\leq b"),
    (r"x \to 0", r"x\rightarrow0"),
    (r"\lvert x \rvert", r"|x|"),
    (r"a\,b\;c\!d \quad e", r"abcde"),
    (r"\displaystyle \int", r"\int"),
])
def test_typographic_variants_collapse(a, b):
    assert canonical_math_body(a) == canonical_math_body(b)


@pytest.mark.parametrize("a,b", [
    (r"\sqrt{e}", r"e^{1/2}"),           # form is answer content (convention 1)
    (r"\frac{1}{e}", r"e^{-1}"),
    (r"\cdot", r"\times"),               # different symbols the student chose
    (r"0.5", r"\frac{1}{2}"),
    (r"x^{2}", r"x_{2}"),
    (r"2x", r"x2"),
])
def test_mathematical_equivalents_stay_different(a, b):
    assert canonical_math_body(a) != canonical_math_body(b)


def test_a_control_word_does_not_swallow_the_next_letter():
    assert canonical_math_body(r"\cdot x") == r"\cdot x"
    assert canonical_math_body(r"\ln x") == r"\ln x"


def test_text_keeps_its_spaces():
    assert canonical_math_body(r"\text{if } x") == r"\text{if }x"


def test_canonicalize_touches_only_math():
    assert canonicalize("public  int x;") == "public  int x;"
    assert canonicalize(r"שווה  \( \dfrac12 \)  כן") == r"שווה  \(\frac{1}{2}\)  כן"


def test_canonicalize_is_idempotent():
    for s in (r"\(\left(\dfrac12, x^2\right)\)", r"\(\sqrt[3] x \le \frac ab\)"):
        once = canonicalize(s)
        assert canonicalize(once) == once


def test_an_unclosed_group_is_never_closed_by_the_canonicaliser():
    assert canonical_math_body(r"\frac{1}{2") == r"\frac{1}{2"


# ── linearisation (the student's PDF) ─────────────────────────────────────────

@pytest.mark.parametrize("body,expected", [
    (r"\frac{1}{e}", "1/e"),
    (r"\sqrt{e}", "√e"),
    (r"e^{1/2}", "e^(1/2)"),                 # NOT √e: the form survives
    (r"x^{2}", "x²"),
    (r"x^{-1}", "x⁻¹"),
    (r"S_{10} = 1.875 S_5", "S₁₀ = 1.875S₅"),
    (r"\frac{a+b}{2}", "(a+b)/2"),
    (r"\sqrt[3]{x+1}", "³√(x+1)"),
    (r"\left( \frac{1}{e}, 0 \right)", "(1/e, 0)"),
    (r"a \leq b", "a ≤ b"),
    (r"x \to \infty", "x → ∞"),
    (r"f'(x) = \ln x + 1", "f'(x) = ln x+1"),
    (r"\text{if } x", "if x"),
    (r"\log_{2} 8", "log₂8"),
    (r"\searrow", "↘"),
    (r"\unknowncommand{x}", "unknowncommandx"),   # its name, never nothing
])
def test_linearize_body(body, expected):
    assert linearize_math_body(body) == expected


def test_linearize_isolates_each_span_and_keeps_prose():
    text = r"נקודת מינימום \((\sqrt{e}, -2.25)\) כלומר"
    assert linearize(text) == f"נקודת מינימום {LRE}(√e,{NBSP}-2.25){PDF} כלומר"


def test_linearize_is_identity_without_math():
    for s in ("", "public int x;", "תשובה מלאה (2, 3)"):
        assert linearize(s) == s


def test_cases_linearize_with_a_brace():
    body = "\\begin{cases} x+y=3 \\\\ x-y=1 \\end{cases}"
    assert linearize_math_body(body) == "{ x+y = 3; x-y = 1 }"
