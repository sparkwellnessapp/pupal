"""MATH_RENDERING_PLAN §4: the mathematics LaTeX P1 variant and its seams. Pure, zero network.

  * the variant is selected by config, stamped into the prompt version, and is a no-op for
    every subject that does not define it — CS stays `P1_SYSTEM` byte-for-byte;
  * the engine adapter writes a `math_notation` INFO only under `math_notation`, and
    `code_lint` only under `code` (a fraction is braces; it is not a code defect);
  * the grader's quote check compares math spans typographically, and only math spans.
"""
from __future__ import annotations

import pytest

from app.subjects import get_profile, transcription_prompt_version


# ── the variant ───────────────────────────────────────────────────────────────

def test_mathematics_defines_latex1_and_nobody_else_does():
    assert get_profile("mathematics").has_p1_variant("latex1")
    for key in ("computer_science", "english"):
        assert not get_profile(key).has_p1_variant("latex1")


def test_a_variant_cs_does_not_define_leaves_cs_byte_identical():
    from app.services.transcription.two_phase.prompts import P1_SYSTEM, p1_system

    cs = get_profile("computer_science")
    assert p1_system(cs, "latex1") == P1_SYSTEM
    assert p1_system(cs, "") == P1_SYSTEM


def test_the_default_math_fragment_is_still_the_linear_one():
    """The flip is env-only and waits for the Phase 1 gate (plan §7)."""
    from app.services.transcription.two_phase.prompts import p1_system

    ma = get_profile("mathematics")
    assert p1_system(ma) == p1_system(ma, "")
    assert "`sqrt(...)`" in p1_system(ma)
    assert "\\(" not in p1_system(ma)


def test_the_latex_fragment_carries_every_written_convention():
    from app.services.transcription.two_phase.prompts import p1_system

    text = p1_system(get_profile("mathematics"), "latex1")
    for rule in ("between \\( and \\)", "in the student's OWN form", "\\sqrt{e}", "\\frac{1}{e}",
                 "OUTSIDE the \\( \\) spans", "One written line is one transcribed line",
                 "\\begin{cases}", "Never use aligned", "is still wrapped in",
                 "\\(\\begin{cases} ... \\end{cases}\\)", "labels verbatim", "\\boxed{...}", "\\cancel{...}",
                 "\\nearrow", "\\searrow", "\\cup", "\\cap", "[איור N:", "Never solve, simplify, or correct"):
        assert rule in text, f"latex1 lost {rule!r}"
    # everything outside the ink rules survives, as for every non-CS fragment
    for kept in ("Section markers are the ONE formatting exception", "EXCLUDE the student's identity",
                 "Use `[?]`", "A hand-drawn TABLE", '{"pages": [{"page_number": <int>'):
        assert kept in text
    for cs_only in ("`CW`", "minuteS", "wrong comment delimiters", "code, comments"):
        assert cs_only not in text


def test_the_latex_fragment_is_short():
    frag = dict(get_profile("mathematics").p1_variants)["latex1"]
    lines = [l for l in frag.splitlines() if l.strip()]
    assert len(lines) <= 12, f"latex1 has {len(lines)} lines (> 12, execution plan §4.1)"


def test_the_stamp_names_the_variant_only_where_it_ran():
    ma, cs = get_profile("mathematics"), get_profile("computer_science")
    assert transcription_prompt_version("t1.4-tables", ma, "latex1") == "t1.4-tables+mathematics.latex1"
    assert transcription_prompt_version("t1.4-tables", ma, "") == "t1.4-tables+mathematics"
    assert transcription_prompt_version("t1.4-tables", cs, "latex1") == "t1.4-tables"


def test_the_pipeline_config_default_runs_no_variant():
    from app.services.transcription.two_phase.pipeline import PipelineConfig
    from app.services.transcription.two_phase_engine import PROD_CONFIG

    assert PipelineConfig.__dataclass_fields__["p1_variant"].default == ""
    assert PROD_CONFIG.p1_variant == ""


# ── the engine adapter ────────────────────────────────────────────────────────

def _trust_run(answers, lint=()):
    from app.services.transcription.two_phase.instrument import Trace
    from app.services.transcription.two_phase.pipeline import PipelineRun
    from app.services.transcription.two_phase.trust import TrustRun

    run = PipelineRun(pages={1: "\n".join(answers.values())}, answers=answers,
                      spec_mismatches=(), routing_notes=(), trace=Trace(doc_id="d"))
    return TrustRun(run=run, flags=(), attributions={}, lint=tuple(lint))


def _types(draft):
    return [a.annotation_type for a in draft.annotations]


def test_a_broken_span_gets_one_info_under_mathematics():
    from app.schemas.ontology_types import AnnotationSeverity
    from app.services.transcription.two_phase_engine import build_draft_from_trust_run

    tr = _trust_run({(1, "א"): r"\(\frac{1}{2\) ו \(\begin{aligned} a \end{aligned}\)",
                     (1, "ב"): r"\(x = \sqrt{e}\)"})
    draft = build_draft_from_trust_run(tr, page_count=1, duration_ms=1, subject="mathematics")
    math = [a for a in draft.annotations if a.annotation_type == "math_notation"]
    assert len(math) == 1                              # one per answer, never per issue
    assert math[0].target_id == "q1.א"
    assert math[0].severity == AnnotationSeverity.INFO
    assert {i["code"] for i in math[0].metadata["issues"]} == {"unbalanced_braces", "forbidden_env"}
    # the text is never touched
    assert draft.answers[0].answer_text == r"\(\frac{1}{2\) ו \(\begin{aligned} a \end{aligned}\)"


def test_no_math_check_outside_mathematics():
    from app.services.transcription.two_phase_engine import build_draft_from_trust_run

    tr = _trust_run({(1, None): r"\(\frac{1}{2\)"})
    for subject in ("computer_science", "english"):
        assert "math_notation" not in _types(build_draft_from_trust_run(
            tr, page_count=1, duration_ms=1, subject=subject))


def test_code_lint_is_written_only_under_the_code_modality():
    from app.services.transcription.flagging import LintFinding
    from app.services.transcription.two_phase_engine import build_draft_from_trust_run

    tr = _trust_run({(1, None): r"\(\{x\)"}, lint=[LintFinding(answer_key="q1", balance=1)])
    assert "code_lint" in _types(build_draft_from_trust_run(tr, page_count=1, duration_ms=1,
                                                            subject="computer_science"))
    assert "code_lint" not in _types(build_draft_from_trust_run(tr, page_count=1, duration_ms=1,
                                                                subject="mathematics"))


def test_math_notation_is_not_a_triage_reason():
    """Its false-flag rate is unmeasured — the code_lint lesson (owner ruling 2026-09-06)."""
    from app.services.batch_triage import StudentMatchResult, compute_flag_verdict
    from app.services.transcription.two_phase_engine import build_draft_from_trust_run

    tr = _trust_run({(1, None): r"\(\frac{1}{2\)"})
    draft = build_draft_from_trust_run(tr, page_count=1, duration_ms=1, subject="mathematics")
    assert "math_notation" in _types(draft)
    draft.answers[0].confidence = 1.0
    verdict = compute_flag_verdict(draft, StudentMatchResult("s", "דן", "exact"))
    assert verdict.review_needed is False and verdict.reasons == []


# ── the quote check ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("quote,answer", [
    (r"\(x = \dfrac{1}{e}\)", r"לכן \(x = \frac{1}{e}\) אסימפטוטה"),
    (r"\(\left(\sqrt e, -2.25\right)\)", r"מינימום \((\sqrt{e}, -2.25)\)"),
    (r"\(x^2 \le 4\)", r"\(x^{2} \leq 4\)"),
])
def test_a_typographic_variant_of_the_answer_is_an_exact_quote(quote, answer):
    from app.agents.grader.validator import quote_match_status
    from app.schemas.ontology_types import QuoteValidationStatus

    assert quote_match_status(quote, answer) == QuoteValidationStatus.EXACT


def test_a_different_form_is_not_the_same_quote():
    """`e^{-1}` is not what the student wrote when he wrote `\\frac{1}{e}`."""
    from app.agents.grader.validator import quote_match_status
    from app.schemas.ontology_types import QuoteValidationStatus

    assert quote_match_status(r"\(e^{-1}\)", r"\(\frac{1}{e}\)") != QuoteValidationStatus.EXACT


def test_cs_quotes_are_untouched():
    from app.agents.grader.validator import quote_match_status
    from app.schemas.ontology_types import QuoteValidationStatus

    answer = "for (int i = 0; i < n; i++) { sum += a[i]; }"
    assert quote_match_status("i < n; i++", answer) == QuoteValidationStatus.EXACT
    assert quote_match_status("while (i <= n)", answer) == QuoteValidationStatus.NOT_FOUND


# ── the variant is a PACKAGE: fragment + the packing it was measured at ───────

def test_latex1_runs_one_page_per_call_and_nothing_else_changes_packing():
    """Probe v3: at 3 pages per call the student's Hebrew on a dense page was misread
    (latex1 4/5 draws, today's linear fragment 5/5); at 1 page per call, 15/15 right."""
    ma, cs = get_profile("mathematics"), get_profile("computer_science")
    assert ma.p1_pages_per_call_for("latex1") == 1
    assert ma.p1_pages_per_call_for("") is None
    assert cs.p1_pages_per_call_for("latex1") is None


def _chunked_calls(subject, variant):
    import asyncio
    import json
    from PIL import Image
    from app.services.transcription.providers.fake import FakeProvider
    from app.services.transcription.scheduler import ProviderLimit, ProviderScheduler
    from app.services.transcription.two_phase.instrument import Trace
    from tests.transcription_eval_suit.pipelines import PipelineConfig, build_pipeline

    pages = {n: f"page {n}" for n in (1, 2, 3)}
    one = lambda nums: FakeProvider.ok(json.dumps(
        {"pages": [{"page_number": n, "text": pages[n]} for n in nums]}))
    script = [one([1]), one([2]), one([3])] if variant else [one([1, 2, 3])]
    gem = FakeProvider(script=script)
    cfg = PipelineConfig(p1_model_key="gemini-3.1-flash-lite", p2_model_key="gpt-5.4-nano-2026-03-17",
                         p1_pages_per_call=3, subject_key=subject, p1_variant=variant)
    providers = {"gemini": gem, "anthropic": FakeProvider(script=[]), "openai": FakeProvider(script=[])}
    pipe = build_pipeline(cfg, providers, ProviderScheduler({n: ProviderLimit() for n in providers}))
    images = [Image.new("RGB", (50, 70), "white") for _ in range(3)]
    asyncio.new_event_loop().run_until_complete(pipe._transcribe_pages(images, "d", 0, Trace(doc_id="d")))
    return len(gem.calls)


def test_the_pipeline_chunks_by_the_variants_packing():
    assert _chunked_calls("mathematics", "latex1") == 3
    assert _chunked_calls("mathematics", "") == 1
    assert _chunked_calls("computer_science", "latex1") == 1
