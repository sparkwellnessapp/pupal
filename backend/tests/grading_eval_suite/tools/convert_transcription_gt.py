"""
F1 — sibling draft-GT markdown -> TranscriptionContract JSON.

Deliberately built ON the transcription suite's own loader (one definition of
the `=== Q{n}.{sub} ===` format — the strongest form of the parity guard), with
the parity test (`test_fixture_tools.py`) asserting the emitted contract's
answers reproduce the loader's answers byte-identically on all five seed docs.

The GT referent ruling [R3]: the draft-GT text IS the faithful transcription —
exactly what production grading consumes post-review, so the contract built
here is the production-realistic grading input.
"""
from __future__ import annotations

from pathlib import Path

from app.schemas.transcription import TranscriptionContract, TranscriptionContractAnswer
from tests.transcription_eval_suit.ground_truth import GoldDocument, load_ground_truth

SUITE_DIR = Path(__file__).resolve().parents[1]
SIBLING_DRAFTS = SUITE_DIR.parents[0] / "transcription_eval_suit" / "draft_benchmarks"


def convert_gold_document(gold: GoldDocument) -> TranscriptionContract:
    """Pure: keys map (question_number, sub_question_id) -> answer, text verbatim."""
    return TranscriptionContract(
        contract_version=f"gt-{gold.doc_id}",   # deterministic: snapshots are diffable
        answers=[TranscriptionContractAnswer(
            question_number=a.question_number,
            sub_question_id=a.sub_question_id,
            answer_text=a.answer_text)
            for a in gold.answers],
    )


def convert_file(path: Path) -> TranscriptionContract:
    return convert_gold_document(load_ground_truth(path))


def convert_sibling_doc(doc_id: str) -> TranscriptionContract:
    return convert_file(SIBLING_DRAFTS / f"{doc_id}.md")
