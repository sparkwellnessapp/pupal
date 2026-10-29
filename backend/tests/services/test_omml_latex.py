r"""ALPHA-GAP A-2 closed: Word equations reach the extractor as the LaTeX they draw.

Before: `1/e` and `x²` rendered as `1 e and x 2` — the structure was gone before any model
saw the rubric. Every case here is real OMML as Word writes it, and every output must be a
span the rest of the system accepts (`check_math_answer` finds no issue) and renders.
"""
from __future__ import annotations

import io

import pytest
from lxml import etree

from app.services.docx_v3.omml_latex import omml_to_latex
from app.services.math_notation import check_math_answer

M = 'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'


def r(text: str) -> str:
    return f"<m:r><m:t>{text}</m:t></m:r>"


def omath(inner: str) -> str:
    return f"<m:oMath {M}>{inner}</m:oMath>"


def latex(inner: str) -> str:
    return omml_to_latex(etree.fromstring(omath(inner)))


CASES = [
    ("a fraction", f"<m:f><m:num>{r('1')}</m:num><m:den>{r('e')}</m:den></m:f>", r"\(\frac{1}{e}\)"),
    ("a power", f"<m:sSup><m:e>{r('x')}</m:e><m:sup>{r('2')}</m:sup></m:sSup>", r"\({x}^{2}\)"),
    ("a subscript", f"<m:sSub><m:e>{r('a')}</m:e><m:sub>{r('n')}</m:sub></m:sSub>{r('=3')}",
     r"\({a}_{n}=3\)"),
    ("a square root", f"<m:rad><m:radPr><m:degHide m:val=\"1\"/></m:radPr><m:deg/><m:e>{r('e')}</m:e></m:rad>",
     r"\(\sqrt{e}\)"),
    ("a cube root", f"<m:rad><m:deg>{r('3')}</m:deg><m:e>{r('x+1')}</m:e></m:rad>", r"\(\sqrt[3]{x+1}\)"),
    ("parentheses", f"<m:d><m:e>{r('x+1')}</m:e></m:d>", r"\((x+1)\)"),
    ("a point", f"<m:d><m:dPr><m:sepChr m:val=\",\"/></m:dPr><m:e>{r('2')}</m:e><m:e>{r('3')}</m:e></m:d>",
     r"\((2,3)\)"),
    ("a system", "<m:d><m:dPr><m:begChr m:val=\"{\"/><m:endChr m:val=\"\"/></m:dPr><m:e><m:eqArr>"
     f"<m:e>{r('x+y=5')}</m:e><m:e>{r('x-y=1')}</m:e></m:eqArr></m:e></m:d>",
     r"\(\begin{cases}x+y=5 \\ x-y=1\end{cases}\)"),
    ("symbols", r("2×3≤x≠4"), r"\(2\times 3\leq x\neq 4\)"),
    ("a function", f"<m:func><m:fName>{r('ln')}</m:fName><m:e>{r('x')}</m:e></m:func>", r"\(\ln x\)"),
    ("a limit", f"<m:func><m:fName><m:limLow><m:e>{r('lim')}</m:e><m:lim>{r('x→∞')}</m:lim></m:limLow>"
     f"</m:fName><m:e>{r('f(x)')}</m:e></m:func>", r"\(\lim_{x\rightarrow \infty } f(x)\)"),
    ("a sum", f"<m:nary><m:naryPr><m:chr m:val=\"∑\"/></m:naryPr><m:sub>{r('i=1')}</m:sub>"
     f"<m:sup>{r('n')}</m:sup><m:e>{r('i')}</m:e></m:nary>", r"\(\sum_{i=1}^{n} i\)"),
    ("an overline", f"<m:bar><m:barPr><m:pos m:val=\"top\"/></m:barPr><m:e>{r('AB')}</m:e></m:bar>",
     r"\(\overline{AB}\)"),
    ("a vector", f"<m:acc><m:accPr><m:chr m:val=\"⃗\"/></m:accPr><m:e>{r('v')}</m:e></m:acc>",
     r"\(\vec{v}\)"),
    ("a framed answer", f"<m:borderBox><m:e>{r('x=3')}</m:e></m:borderBox>", r"\(\boxed{x=3}\)"),
    ("the probe's limit, nested", f"<m:f><m:num><m:sSup><m:e>{r('x')}</m:e><m:sup>{r('2')}</m:sup></m:sSup>"
     f"{r('+1')}</m:num><m:den>{r('x-1')}</m:den></m:f>", r"\(\frac{{x}^{2}+1}{x-1}\)"),
    ("degrees", r("45°"), r"\(45^{\circ}\)"),
]


@pytest.mark.parametrize("name,xml,expected", CASES, ids=[c[0] for c in CASES])
def test_the_equation_is_the_latex_it_draws(name, xml, expected):
    out = latex(xml)
    assert out == expected
    assert check_math_answer(out) == [], f"{name}: {check_math_answer(out)}"


def test_hebrew_at_the_top_level_is_lifted_out_of_the_span():
    out = latex(r("סה״כ") + r("=") + f"<m:f><m:num>{r('1')}</m:num><m:den>{r('2')}</m:den></m:f>")
    assert out == r"סה״כ \(=\frac{1}{2}\)"
    assert check_math_answer(out) == []


def test_hebrew_nested_in_a_structure_becomes_text():
    out = latex(f"<m:f><m:num>{r('מרחק')}</m:num><m:den>{r('זמן')}</m:den></m:f>")
    assert out == r"\(\frac{\text{מרחק}}{\text{זמן}}\)"


def test_an_empty_equation_contributes_nothing():
    assert latex("") == ""


def test_an_unknown_element_keeps_its_text():
    assert latex(f"<m:newThing><m:e>{r('x=1')}</m:e></m:newThing>") == r"\(x=1\)"


# ── through the renderer, as a DOCX ──────────────────────────────────────────────

def _docx(paragraph_xml_inner: list) -> bytes:
    from docx import Document
    doc = Document()
    for inner in paragraph_xml_inner:
        p = doc.add_paragraph()
        for el in etree.fromstring(
                f'<w:wrap xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
                f'xmlns:o="urn:schemas-microsoft-com:office:office" {M}>{inner}</w:wrap>'):
            p._p.append(el)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_a_docx_equation_renders_as_a_span_and_is_counted():
    from app.services.docx_v3.parser_render import render_docx_to_markdown_with_stats
    data = _docx(['<w:r><w:t xml:space="preserve">הפונקציה </w:t></w:r>' + omath(
        f"<m:f><m:num>{r('1')}</m:num><m:den>{r('e')}</m:den></m:f>")])
    md, stats = render_docx_to_markdown_with_stats(data)
    assert r"הפונקציה \(\frac{1}{e}\)" in md
    assert stats.omml_seen == stats.omml_rendered == 1


def test_superscript_runs_keep_their_power():
    from app.services.docx_v3.parser_render import render_docx_to_markdown_with_stats
    sup = '<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:t>2</w:t></w:r>'
    sub = '<w:r><w:rPr><w:vertAlign w:val="subscript"/></w:rPr><w:t>n+1</w:t></w:r>'
    md, _ = render_docx_to_markdown_with_stats(_docx([
        f'<w:r><w:t>x</w:t></w:r>{sup}<w:r><w:t xml:space="preserve"> ו a</w:t></w:r>{sub}']))
    assert "x^2 ו a_(n+1)" in md


def test_a_tracked_insertion_is_part_of_the_text():
    from app.services.docx_v3.parser_render import render_docx_to_markdown_with_stats
    md, _ = render_docx_to_markdown_with_stats(_docx([
        '<w:r><w:t xml:space="preserve">התשובה </w:t></w:r>'
        '<w:ins w:id="1" w:author="t"><w:r><w:t>נכונה</w:t></w:r></w:ins>']))
    assert "התשובה נכונה" in md


def test_a_mathtype_object_is_marked_and_counted_never_dropped():
    from app.services.docx_v3.parser_render import render_docx_to_markdown_with_stats
    ole = ('<w:r><w:object><o:OLEObject Type="Embed" ProgID="Equation.DSMT4" ShapeID="_x0000_i1025" '
           'DrawAspect="Content" ObjectID="_1"/></w:object></w:r>')
    md, stats = render_docx_to_markdown_with_stats(_docx(
        ['<w:r><w:t xml:space="preserve">הנוסחה </w:t></w:r>' + ole + '<w:r><w:t>סוף</w:t></w:r>']))
    assert "[IMAGE: equation]" in md
    assert stats.ole_equations == 1
