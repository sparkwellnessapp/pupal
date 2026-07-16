"""
Known-answer self-tests for the pedagogical-mistake detector and the renderer signals.
Run: PYTHONPATH=. python tests/rubric_eval_suite/tests/test_pedagogical.py
No OpenAI: Tier B is exercised with a mock StructuredLLM.
"""
import tempfile
from decimal import Decimal as D
from pathlib import Path

from docx import Document

from app.schemas.ontology_types import (
    ExtractRubricResponse, PedagogicalMistakeKind,
)
from app.services.docx_v3 import pedagogical_mistakes as pm
from app.services.docx_v3 import parser_render as pr
from app.services.docx_v3.pedagogical_mistakes import AdjudicationResult
from tests.rubric_eval_suite import reporting
from tests.rubric_eval_suite.schemas import AnnotationCheck, RubricScore

# parents[0] = the suite dir (tests/rubric_eval_suite/), which holds fixtures/ and
# benchmarks/. Was parents[1] — a stale path from when these test files lived one dir
# deeper (see the "Run:" docstring); the move up was never reflected here.
FIX = Path(__file__).resolve().parents[0] / "fixtures"
BEN = Path(__file__).resolve().parents[0] / "benchmarks"


def _prose(name):
    return "\n".join(p.text for p in Document(str(FIX / f"{name}.docx")).paragraphs)


def _draft(name):
    r = ExtractRubricResponse.model_validate_json((BEN / f"{name}.json").read_text())
    return r.model_copy(update={"pedagogical_mistakes": []})


def test_prose_marker_parse_handles_continuations():
    decl = pm.declared_subquestions_from_prose(_prose("hobby_tvshow"))
    assert decl.get(1) == ["א", "ב", "ג"], decl
    assert decl.get(2) == ["א", "ב", "ג"], decl  # despite the '(המשך שאלה 2)' continuation
    print("  [ok] prose markers parsed, continuation markers unioned")


def test_tier_a_point_sum_mismatch():
    d = _draft("foundations_cs")
    d.questions[1].criteria[0].points = D("99")          # break Q2
    ms = pm._check_point_sums(d)
    kinds = {(m.kind, m.target_id) for m in ms}
    assert (PedagogicalMistakeKind.POINT_SUM_MISMATCH, "q2") in kinds, kinds
    print("  [ok] point_sum_mismatch detected deterministically")


def test_tier_a_selection_normalization():
    ms = pm._check_selection_normalization(_draft("employee_course_select1"))
    assert any(m.kind == PedagogicalMistakeKind.SELECTION_NORMALIZATION for m in ms)
    assert ms[0].requires_teacher_input is True and ms[0].suggested_fix is None
    print("  [ok] selection_normalization detected, flagged needs-teacher (no auto-fix)")


def test_trigger_fires_only_on_real_mislabel():
    fires = {}
    for name in ["hobby_tvshow", "bagrut_899371", "csharp_plane_combine",
                 "foundations_cs", "employee_course_select1"]:
        r = pm.detect_deterministic(_draft(name), _prose(name))
        fires[name] = [(t.question_id, tuple(t.missing), tuple(t.extra)) for t in r.triggers]
    assert fires["hobby_tvshow"] == [("q2", ("ג",), ())], fires["hobby_tvshow"]
    for other in ["bagrut_899371", "csharp_plane_combine", "foundations_cs", "employee_course_select1"]:
        assert fires[other] == [], (other, fires[other])   # ZERO false-fires
    print("  [ok] declared-vs-extracted trigger: 1 true fire, 0 false fires across 4 consistent exams")


def test_tier_b_adjudication_and_leash():
    hobby, prose = _draft("hobby_tvshow"), _prose("hobby_tvshow")

    def good_llm(*, system, user, schema):
        assert schema is AdjudicationResult and "PrintLowRatingChannel" in user
        return AdjudicationResult(
            is_mistake=True, kind=PedagogicalMistakeKind.STRUCTURAL_MISLABEL, target_id="q2",
            explanation="רכיב PrintLowRatingChannel שייך לסעיף ג.",
            suggested_operation="reassign_subquestion",
            suggested_params={"from": "ב", "to": "ג"},
            suggested_description="העברה לסעיף ג.", confidence=0.92)

    out = pm.detect_pedagogical_mistakes(hobby, prose, llm=good_llm)
    adj = [m for m in out if m.mistake_id.startswith("adj:")]
    assert len(adj) == 1 and adj[0].kind == PedagogicalMistakeKind.STRUCTURAL_MISLABEL
    assert adj[0].suggested_fix.params["to"] == "ג"
    print("  [ok] Tier B turns the trigger into a structural_mislabel + reassign fix")

    # leash: a kind outside the allowed Tier-B set is dropped
    def stray_llm(*, system, user, schema):
        return AdjudicationResult(is_mistake=True, kind=PedagogicalMistakeKind.POINT_SUM_MISMATCH,
                                  target_id="q2", explanation="x", confidence=0.9)
    assert [m for m in pm.detect_pedagogical_mistakes(hobby, prose, llm=stray_llm)
            if m.mistake_id.startswith("adj:")] == []
    # not-a-mistake -> nothing
    def nomis_llm(*, system, user, schema):
        return AdjudicationResult(is_mistake=False, confidence=0.8)
    assert [m for m in pm.detect_pedagogical_mistakes(hobby, prose, llm=nomis_llm)
            if m.mistake_id.startswith("adj:")] == []
    print("  [ok] taxonomy leash + conservative is_mistake=false both honored")


def test_degrades_without_llm():
    out = pm.detect_pedagogical_mistakes(_draft("hobby_tvshow"), _prose("hobby_tvshow"), llm=None)
    assert all(not m.mistake_id.startswith("adj:") for m in out)  # Tier A only, no crash
    print("  [ok] llm=None degrades to Tier A only")


def test_tier_b_failure_keeps_tier_a():
    # Per-trigger isolation: a Tier B transport/construction failure must be
    # swallowed per-trigger — Tier A results are deterministic facts and survive.
    def _raising_llm(*, system, user, schema):
        raise RuntimeError("simulated transport failure")

    baseline = pm.detect_pedagogical_mistakes(_draft("hobby_tvshow"), _prose("hobby_tvshow"), llm=None)
    with_failure = pm.detect_pedagogical_mistakes(_draft("hobby_tvshow"), _prose("hobby_tvshow"), llm=_raising_llm)
    assert [m.mistake_id for m in with_failure] == [m.mistake_id for m in baseline], \
        "Tier B failure must yield exactly the Tier A result set"
    print("  [ok] Tier B failure isolated per-trigger — Tier A results survive")


def test_renderer_strikethrough_and_color():
    # csharp: strikethrough revisions preserved; uniformly-red table + C# syntax palette
    # must produce ZERO color marks (red-family + per-scope-baseline filtering).
    md = pr.render_docx_to_markdown((FIX / "csharp_plane_combine.docx").read_bytes())
    assert "~~6~~" in md and "ערך חדש 8" in md, "struck point revision missing"
    assert "~~4 נק" in md, "struck bonus row missing"
    assert md.count("[[color:") == 0, f"csharp should have no color noise, got {md.count('[[color:')}"

    # 899371: red teacher solutions marked (EE0000), no white/green/teal noise.
    md2 = pr.render_docx_to_markdown((FIX / "bagrut_899371.docx").read_bytes())
    assert "[[color:EE0000]]" in md2, "red solution not marked"
    import re
    bad = set(re.findall(r"\[\[color:([0-9A-F]{6})\]\]", md2)) - {"EE0000"}
    assert not bad, f"non-red colors leaked into marks: {bad}"
    # a real solution phrase survives as a readable span (not shredded per-character)
    assert any(len(s) > 20 for s in re.findall(r"\[\[color:EE0000\]\](.*?)\[\[/color\]\]", md2)), \
        "no multi-word red span — merging failed"
    print("  [ok] renderer: strikethrough preserved, red solutions marked, code/header noise excluded")


def test_tier_b_schema_strict_valid():
    """B2/B3 regression: the REAL transport schema for AdjudicationResult must be
    OpenAI-strict-valid. The fake-LLM seam bypasses schema serialization entirely —
    which is how a deterministic 400 (free-form Dict params lacking
    additionalProperties:false at properties.suggested_params.anyOf[0]) hid for the
    detector's entire life; Tier B had never succeeded end-to-end. This walks the
    OpenAI SDK's own strict converter — the wire path with_structured_output uses
    for json_schema mode. (Private SDK module: if an SDK upgrade moves it, this
    import breaks LOUDLY — re-point it, do not delete the guard.)"""
    from openai.lib._pydantic import to_strict_json_schema

    def violations(node, path="$"):
        out = []
        if isinstance(node, dict):
            if ((node.get("type") == "object" or "properties" in node)
                    and node.get("additionalProperties") is not False):
                out.append(path)
            for k, v in node.items():
                out += violations(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                out += violations(v, f"{path}[{i}]")
        return out

    schema = to_strict_json_schema(pm.AdjudicationResult)
    bad = violations(schema)
    assert not bad, f"strict-invalid object nodes (would 400 at transport): {bad}"

    # consumer contract: alias 'from' accepted on input; params dict shape preserved
    p = pm.SuggestedParams.model_validate({"from": "ב", "to": "ג"})
    assert p.as_params_dict() == {"from": "ב", "to": "ג"}
    r = pm.AdjudicationResult(is_mistake=True, confidence=0.9,
                              suggested_params={"from": "ב", "to": "ג"})
    assert r.suggested_params.as_params_dict() == {"from": "ב", "to": "ג"}
    print("  [ok] AdjudicationResult schema strict-valid; 'from' alias round-trips")


def test_tier_b_failure_surfaces_warning():
    """B4: a swallowed Tier-B failure must reach the warnings sink (observability),
    not just stdout — resilience without a record is how the 400 stayed invisible."""
    def _raising_llm(*, system, user, schema):
        raise RuntimeError("simulated transport failure")

    sink: list = []
    pm.detect_pedagogical_mistakes(_draft("hobby_tvshow"), _prose("hobby_tvshow"),
                                   llm=_raising_llm, warnings_sink=sink)
    assert len(sink) == 1 and "Tier B adjudication failed" in sink[0], sink
    assert "simulated transport failure" in sink[0]
    # llm=None: no Tier B attempted -> no warnings
    sink2: list = []
    pm.detect_pedagogical_mistakes(_draft("hobby_tvshow"), _prose("hobby_tvshow"),
                                   llm=None, warnings_sink=sink2)
    assert sink2 == []
    print("  [ok] swallowed Tier-B failure surfaces in warnings_sink; clean path stays silent")


def test_renderer_highlight_channel():
    """B1: run-level <w:highlight> is teacher ink and must render as [[hl:name]] marks.
    foundations q1.ג marks the correct option with yellow highlight and NO font color —
    it was invisible pre-B1. White highlight is a paste artifact (csharp: 362 white
    runs) and must stay unmarked. The audit (B1b) must be clean on the fixed render
    and FIRE on a highlight-stripped render (the pre-B1 output)."""
    import re
    b = (FIX / "foundations_cs.docx").read_bytes()
    md = pr.render_docx_to_markdown(b)
    assert "[[hl:yellow]]n1=n1+n3;[[/hl]]" in md, "marked option lost (the B1 bug)"
    assert pr.audit_annotation_channels(b, md) == [], "audit must be clean post-fix"
    # pre-B1 render simulated by stripping hl marks -> the audit must fire
    stripped = re.sub(r"\[\[hl:[a-zA-Z]+\]\]|\[\[/hl\]\]", "", md)
    warns = pr.audit_annotation_channels(b, stripped)
    assert any("highlight" in w for w in warns), f"audit blind to channel loss: {warns}"

    # white highlight excluded: csharp renders with ZERO hl marks
    md_cs = pr.render_docx_to_markdown((FIX / "csharp_plane_combine.docx").read_bytes())
    assert md_cs.count("[[hl:") == 0, "white-highlight paste artifacts must stay unmarked"
    print("  [ok] highlight channel rendered; audit guards the loss; white excluded")


def test_render_token_set_strips_markup():
    """B1b tokenizer fix: markers glue onto ink ('[[color:EE0000]]ניקוד:') and mangled
    the token set, mis-attributing marked-but-present GT content as render_loss
    (bagrut's phantom 'ניקוד: 6 נקודות'). Markup must be stripped for attribution."""
    from tests.rubric_eval_suite import normalize as nz
    toks = nz.render_token_set("[[color:EE0000]]ניקוד: 6 נקודות[[/color]] [[hl:yellow]]n1=n1+n3;[[/hl]] ~~struck~~")
    assert "ניקוד:" in toks and "נקודות" in toks and "n1=n1+n3;" in toks and "struck" in toks, toks
    assert nz.present_in_render("ניקוד: 6 נקודות", toks)
    print("  [ok] render_token_set strips [[color]]/[[hl]]/~~ markup before tokenizing")


def test_pedagogical_diffs_serialized_and_rendered():
    """F3 OUTPUT-SURFACE regression guard. The pedagogical fields exist on RubricScore,
    but a prior run's artifacts dropped them — the gate could fail on
    `pedagogical_mismatch` while NEITHER results.json NOR the report said what mismatched.
    This pins BOTH surfaces: a score that fails pedagogical in both directions (one
    missing + one spurious) must carry all three lists into to_dict() (results.json) AND
    render its diffs into report_<rubric>.md. expected_pedagogical is seeded with the
    missed item (real scoring semantics: missing ⊆ expected), so all three lists' content
    is present in the report text too — missing/spurious via their diff lines, expected via
    the missing one it contains."""
    missed = AnnotationCheck("structural_mislabel", "q2")        # GT expected it; model missed it
    invented = AnnotationCheck("selection_normalization", None)  # model hallucinated it
    rs = RubricScore(
        rubric_name="ped_probe", valid=True, gate_pass=False,
        gate_failures=["pedagogical_mismatch"], pedagogical_match=False,
        expected_pedagogical=[missed], missing_pedagogical=[missed],
        spurious_pedagogical=[invented],
    )

    # (1) serialization → results.json: all three lists survive to_dict() with content
    d = rs.to_dict()
    for key in ("expected_pedagogical", "missing_pedagogical", "spurious_pedagogical"):
        assert key in d, f"{key} dropped from RubricScore.to_dict()"
    assert d["expected_pedagogical"] == [{"annotation_type": "structural_mislabel", "target_id": "q2"}]
    assert d["missing_pedagogical"] == [{"annotation_type": "structural_mislabel", "target_id": "q2"}]
    assert d["spurious_pedagogical"] == [{"annotation_type": "selection_normalization", "target_id": None}]

    # (2) rendering → report_<rubric>.md: the diff section renders both directions
    with tempfile.TemporaryDirectory() as td:
        txt = reporting.write_rubric_report(rs, Path(td)).read_text(encoding="utf-8")
    assert "Pedagogical-mistake diffs" in txt, "pedagogical diff section missing from report"
    assert "MISSING expected: structural_mislabel @ q2" in txt, txt
    assert "SPURIOUS: selection_normalization @ None" in txt, txt
    print("  [ok] pedagogical diffs: three lists in to_dict(); missing+spurious rendered in report")


if __name__ == "__main__":
    print("PEDAGOGICAL-MISTAKE + RENDERER SELF-TESTS")
    test_prose_marker_parse_handles_continuations()
    test_tier_a_point_sum_mismatch()
    test_tier_a_selection_normalization()
    test_trigger_fires_only_on_real_mislabel()
    test_tier_b_adjudication_and_leash()
    test_degrades_without_llm()
    test_tier_b_failure_keeps_tier_a()
    test_renderer_strikethrough_and_color()
    test_tier_b_schema_strict_valid()
    test_tier_b_failure_surfaces_warning()
    test_renderer_highlight_channel()
    test_render_token_set_strips_markup()
    test_pedagogical_diffs_serialized_and_rendered()
    print("ALL PEDAGOGICAL + RENDERER SELF-TESTS PASSED")
