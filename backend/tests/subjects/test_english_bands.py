"""Phase 4a — the flattened band ladder (D-3 beta path, P-12).

A ministry-style English writing rubric scores each criterion with a LADDER: four columns
(CORRECT / PARTIALLY CORRECT / MINIMALLY CORRECT / INCORRECT), each carrying its own points.
Beta does NOT model discrete levels (that is ALPHA-GAP A-1). It flattens: one criterion at the
TOP band's points, with every band quoted verbatim in the description so the teacher — and the
grader reading the criterion — still see the ladder she wrote.

What is deterministic and therefore tested here: the fragment carries the rule and stays inside
its budget, and a flattened ladder COMPILES at the document's own total. Whether the model obeys
the rule is a provider question, answered once by the recorded run in
`tests/rubric_eval_suite/snapshots/2026-09-09_multisubject-ministry-fg/` (4 criteria,
8 / 10 / 16 / 6 = 40, compile OK, every band present in every description).
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.schemas.ontology_types import (
    Criterion, ExtractRubricResponse, NumericPolicy, Question, QuestionType,
)
from app.services.contract_compiler import ContractCompiler
from app.subjects import get_profile

D = Decimal

# The real ladder, from the Ministry of Education Module G (16582) / F (16584) writing rubric,
# Winter 2020. Top band first, as the document prints it.
MINISTRY_BANDS = [
    ("CONTENT AND ORGANIZATION", ["8", "5", "2", "0"]),
    ("VOCABULARY", ["10", "6", "3", "0"]),
    ("LANGUAGE USE", ["16", "10", "5", "0"]),
    ("MECHANICS", ["6", "4", "2", "0"]),
]
BAND_NAMES = ["CORRECT", "PARTIALLY CORRECT", "MINIMALLY CORRECT", "INCORRECT"]


def _flattened_criterion(index: int, name: str, bands: list[str]) -> Criterion:
    ladder = "\n".join(f"{b} ({p}): …" for b, p in zip(BAND_NAMES, bands))
    return Criterion(criterion_id=f"q1.c{index}", index=index,
                     description=f"{name}\n{ladder}", points=D(bands[0]))


def test_the_english_fragment_carries_the_band_rule_and_stays_in_budget():
    frag = get_profile("english").extraction_fragment
    assert frag is not None
    body = frag.strip().splitlines()
    assert len(body) <= 12, f"§4.1 budget: {len(body)} lines"
    text = frag.upper()
    # the rule names the ladder, fixes the points to the top band, and forbids both
    # failure modes: one criterion per band, and summing the bands
    assert "BAND LADDER" in text
    assert "HIGHEST BAND" in text
    assert "NEVER EMIT ONE CRITERION PER BAND" in text
    assert "NEVER ADD THE BANDS TOGETHER" in text
    # nothing pedagogical, and no CS vocabulary leaked in
    for forbidden in ("C#", "TRACE TABLE", "PSEUDOCODE"):
        assert forbidden not in text or "NO CODE, NO TRACE TABLES" in text


def test_a_flattened_ladder_compiles_at_the_documents_own_total():
    """4 criteria at their top bands sum to the 40 the document declares — no invented total,
    no per-band criteria, and INV-1/2 hold exactly."""
    crits = [_flattened_criterion(i, name, bands)
             for i, (name, bands) in enumerate(MINISTRY_BANDS)]
    q = Question(question_id="q1", question_type=QuestionType.SHORT_ANSWER,
                 total_points=D("40"), criteria=crits)
    draft = ExtractRubricResponse(rubric_id="r", rubric_name="Ministry F/G writing rubric",
                                  subject="english", total_points=D("40"), questions=[q])
    assert [str(c.points) for c in crits] == ["8", "10", "16", "6"]
    assert sum(c.points for c in crits) == D("40")
    contract = ContractCompiler().compile(draft, policy=NumericPolicy())
    assert contract.total_points == D("40")
    # the ladder the teacher wrote is still legible on every criterion
    for c in contract.questions[0].criteria:
        for band in BAND_NAMES:
            assert band in c.description


def test_english_never_enters_the_math_post_pass():
    """The ladder's points are the document's own; nothing rescales them."""
    assert get_profile("english").rescale_to_exam is False


@pytest.mark.parametrize("name,bands", MINISTRY_BANDS)
def test_the_top_band_is_the_criterion_points_never_the_sum(name, bands):
    c = _flattened_criterion(0, name, bands)
    assert c.points == D(bands[0])
    assert c.points != sum(D(b) for b in bands)
