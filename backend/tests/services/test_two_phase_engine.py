"""build_draft_from_trust_run: TrustRun -> TranscriptionDraft (v2 adapter).
Pure; synthetic TrustRun, zero network."""
from app.schemas.transcription import TranscriptionDraft
from app.services.transcription.flagging import FlagSpan, LintFinding
from app.services.transcription.page_provenance import PageAttribution
from app.services.transcription.two_phase.instrument import Trace
from app.services.transcription.two_phase.pipeline import PipelineRun
from app.services.transcription.two_phase.trust import TrustRun
from app.services.transcription.two_phase_engine import (
    TWO_PHASE_ENGINE_VERSION,
    build_draft_from_trust_run,
)


def _trust_run() -> TrustRun:
    run = PipelineRun(
        pages={1: "if(x == null)\n{\n}", 2: "return y;"},
        answers={(1, "א"): "if(x == null)\n{\n}", (1, "ב"): "return y;"},
        spec_mismatches=(), routing_notes=(), trace=Trace(doc_id="d"),
    )
    return TrustRun(
        run=run,
        flags=(
            FlagSpan(page=1, i1=2, i2=3, char_start=5, char_end=7,
                     base_text="==", alternatives=("!=",), n_readers=2,
                     kind="code", context_line="if(x == null)",
                     anchor_key="q1.א", anchor_similarity=1.0),
            FlagSpan(page=2, i1=0, i2=1, char_start=0, char_end=6,
                     base_text="return", alternatives=("retorn",), n_readers=1,
                     kind="code", context_line="return y;",
                     anchor_key="q1.ב", anchor_similarity=0.9),
            FlagSpan(page=1, i1=0, i2=1, char_start=0, char_end=2,
                     base_text="שאלה 1", alternatives=("א .",), n_readers=3,
                     kind="marker", context_line="שאלה 1"),
        ),
        attributions={
            "q1.א": PageAttribution(page_weights={1: 1.0}, confidence=0.98, n_lines=3),
            "q1.ב": PageAttribution(page_weights={2: 1.0}, confidence=0.91, n_lines=1),
        },
        lint=(LintFinding(answer_key="q1.א", balance=1),),
    )


def test_draft_carries_baseline_text_provenance_and_annotations():
    draft = build_draft_from_trust_run(_trust_run(), page_count=2, duration_ms=1234)
    assert isinstance(draft, TranscriptionDraft)
    assert draft.model_version == TWO_PHASE_ENGINE_VERSION
    assert draft.page_count == 2
    assert draft.student_name_suggestion is None   # default: no identity hint


def test_shared_infra_is_one_scheduler_per_loop():
    """2026-08-12 root-cause fix: providers + scheduler are shared across ALL
    documents on a loop — per-doc schedulers made the per-model concurrency
    cap a no-op (3×N concurrent uploads) and doc_priority meaningless."""
    import asyncio
    from app.services.transcription import two_phase_engine as eng

    async def two_calls():
        p1, a1, s1 = eng._shared_infra()
        p2, a2, s2 = eng._shared_infra()
        return (s1 is s2, p1 is p2,
                s1._limiters[eng.PROD_CONFIG.p1_model_key]._cfg.max_concurrent
                if hasattr(s1._limiters[eng.PROD_CONFIG.p1_model_key], "_cfg")
                else None)

    same_sched, same_providers, _ = asyncio.run(two_calls())
    assert same_sched and same_providers

    # A fresh loop gets fresh infra (test isolation / loop-binding safety).
    async def once():
        _, _, s = eng._shared_infra()
        return s

    s_a = asyncio.run(once())
    s_b = asyncio.run(once())
    assert s_a is not s_b


def test_draft_carries_identity_pass_suggestion():
    """B-25 fix: the identity pass's name flows into the draft hint field
    (P1's verbatim output still excludes the identity block by design)."""
    draft = build_draft_from_trust_run(
        _trust_run(), page_count=2, duration_ms=1,
        student_name_suggestion="דין עזרא",
    )
    assert draft.student_name_suggestion == "דין עזרא"

    a1, a2 = draft.answers
    assert (a1.question_number, a1.sub_question_id) == (1, "א")
    assert a1.answer_text == "if(x == null)\n{\n}"     # baseline verbatim
    assert a1.page_numbers == [1] and a1.confidence == 0.98
    assert a2.page_numbers == [2]

    by_type = {}
    for ann in draft.annotations:
        by_type.setdefault(ann.annotation_type, []).append(ann)

    # 2-reader code flag -> WARNING on its anchored answer, metadata intact
    high = [a for a in by_type["reader_disagreement"] if a.severity == "warning"]
    assert len(high) == 1
    assert high[0].target_id == "q1.א"
    assert high[0].metadata["alternatives"] == ["!="]
    assert high[0].metadata["page"] == 1

    # 1-reader code flag -> INFO; marker chrome flag -> dropped entirely
    info = [a for a in by_type["reader_disagreement"] if a.severity == "info"]
    assert len(info) == 1 and info[0].target_id == "q1.ב"
    assert not any("שאלה" in a.message for a in draft.annotations)

    # lint -> INFO code_lint on the answer
    assert by_type["code_lint"][0].target_id == "q1.א"
    assert by_type["code_lint"][0].metadata["balance"] == 1


def test_marker_mismatch_emits_warning_with_proposal():
    """A block whose leading marker contradicts its assigned key gets a
    segmentation_mismatch WARNING carrying the proposed swap target."""
    run = PipelineRun(
        pages={1: "x"},
        answers={
            (2, "א"): "א) 3\npublic static int[] DiceStatistics(int[] arr)",
            (3, "א"): "א) 4\npublic int TotalEarnings()",
            (4, "א"): "שאלה 5\nא.",
            (5, None): "",
        },
        spec_mismatches=(), routing_notes=(), trace=Trace(doc_id="d"),
    )
    draft = build_draft_from_trust_run(
        TrustRun(run=run), page_count=1, duration_ms=1,
    )
    anns = [a for a in draft.annotations
            if a.annotation_type == "segmentation_mismatch"]
    by_target = {a.target_id: a for a in anns}
    assert set(by_target) == {"q2.א", "q3.א", "q4.א"}
    assert all(a.severity == "warning" for a in anns)
    assert by_target["q2.א"].metadata["declared_question"] == 3
    assert by_target["q2.א"].metadata["proposed_target"] == "q3.א"
    assert by_target["q4.א"].metadata["proposed_target"] == "q5"  # bare fallback
    assert "שאלה 3" in by_target["q2.א"].message


def test_shared_infra_covers_every_prod_config_model_key():
    """Every model key PROD_CONFIG can dispatch to must have a provider, an
    alias and a scheduler slot.

    This is not hypothetical bookkeeping. `_strike_check_pages` resolves its
    model OUTSIDE the per-page try/except, so a key that is set in the config
    but missing from `_shared_infra` turns a one-line config flip into a
    KeyError that kills the ENTIRE document instead of degrading the checker.
    Enabling the strike-check pass (2026-08-23) hit exactly that gap.
    """
    import asyncio
    from app.services.transcription import two_phase_engine as eng

    cfg = eng.PROD_CONFIG
    expected = {k for k in (cfg.p1_model_key, cfg.p2_model_key,
                            cfg.p1_strike_check_model_key,
                            *cfg.reader_model_keys) if k}

    # Stub provider construction: this test pins the KEY WIRING, not the
    # SDK clients, so it must not require Gemini/OpenAI credentials.
    import unittest.mock as _mock

    async def go():
        eng._shared_infra_cache = None          # bypass any cached real infra
        with _mock.patch.object(eng, "_make_provider", lambda m: object()):
            providers, aliased, scheduler = eng._shared_infra()
        eng._shared_infra_cache = None          # don't leak stubs to other tests
        return set(providers), set(aliased), set(scheduler._limiters)

    got_providers, got_aliased, got_limiters = asyncio.run(go())
    assert expected <= got_providers, f"no provider for {expected - got_providers}"
    assert expected <= got_aliased, f"no alias for {expected - got_aliased}"
    assert expected <= got_limiters, f"no scheduler slot for {expected - got_limiters}"
    # ...and every one of them must be a known model, or _make_provider raises.
    assert expected <= set(eng._MODELS), f"not in _MODELS: {expected - set(eng._MODELS)}"


def test_prod_strike_check_matches_the_gated_configuration():
    """The strike-check pass ships with the params it was GATED at.

    gemini-3.5-flash (not flash-lite, which deleted 3 real lines on moran p2),
    min_block_lines=2, votes=1. Changing any of these means the paired-k=3
    evidence in results/strike_check_2026-08-19/ no longer describes what runs.
    """
    from app.services.transcription.two_phase_engine import PROD_CONFIG as c
    assert c.p1_strike_check_model_key == "gemini-3.5-flash"
    assert c.p1_strike_check_min_block_lines == 2
    assert c.p1_strike_check_votes == 1
    assert c.p1_strike_check_max_tokens == 4000
