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
