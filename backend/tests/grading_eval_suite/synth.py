"""
Synthetic fixtures for the instrument's own guards [§10 of the mission].

Everything here is constructed in memory — zero files, zero API calls. The
contracts are built directly as frozen pydantic objects (the compilers'
zero-mock batteries already pin Draft→Contract; the eval guards test the
EVAL instrument, so they start from contracts).

Used by test_scoring.py / test_gt_loader.py / test_runner_policy.py.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from app.schemas.gradable import GradableScope
from app.schemas.graded_test_draft import (
    CriterionOutcome,
    GradedTestDraft,
    GradingAnnotation,
    ScopeOutcome,
    SubCriterionOutcome,
)
from app.schemas.ontology_types import (
    AnnotationSeverity,
    AnswerQuotation,
    Criterion,
    FlaggedOutcome,
    FlagReason,
    GradingRubricContract,
    NumericPolicy,
    Question,
    QuoteValidationStatus,
    SelectionGroup,
    SubCriterion,
    SubQuestion,
)
from app.schemas.transcription import TranscriptionContract, TranscriptionContractAnswer

from .fixtures import FixtureBundle, assemble_bundle
from .schemas import FixtureGT, ScopeUngradable, TerminalGT

GT_STAMP = dict(gt_source="teacher_manual", authored_by="owner",
                authored_at="2026-08-24T10:00:00", blind=True)


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------

def make_contract() -> GradingRubricContract:
    """q1 direct (c_a 2 + c_b 3 with sub-criteria 1+2) + q2.א (d_a 4). Total 9."""
    q1 = Question(
        question_id="q1", total_points=Decimal("5"),
        criteria=[
            Criterion(criterion_id="q1.c0", index=0, description="loop header correct",
                      points=Decimal("2")),
            Criterion(criterion_id="q1.c1", index=1, description="aggregation correct",
                      points=Decimal("3"),
                      sub_criteria=[
                          SubCriterion(sub_criterion_id="q1.c1.s0", index=0,
                                       description="accumulator initialized", points=Decimal("1")),
                          SubCriterion(sub_criterion_id="q1.c1.s1", index=1,
                                       description="accumulator updated in loop", points=Decimal("2")),
                      ]),
        ],
    )
    q2 = Question(
        question_id="q2", total_points=Decimal("4"),
        sub_questions=[
            SubQuestion(sub_question_id="א", index=0, points=Decimal("4"),
                        criteria=[Criterion(criterion_id="q2.א.c0", index=0,
                                            description="return value correct",
                                            points=Decimal("4"))]),
        ],
    )
    return GradingRubricContract(
        contract_version="synthetic-contract-v1", rubric_id="synthetic",
        subject="computer_science", numeric_policy=NumericPolicy(),
        total_points=Decimal("9"), questions=[q1, q2],
    )


def make_selection_contract() -> GradingRubricContract:
    """Choose 1 of {q1, q2} (10 pts each) + mandatory q3 (5). Achievable = 15."""
    def q(qid: str, pts: str) -> Question:
        return Question(question_id=qid, total_points=Decimal(pts),
                        criteria=[Criterion(criterion_id=f"{qid}.c0", index=0,
                                            description=f"criterion of {qid}",
                                            points=Decimal(pts))])
    return GradingRubricContract(
        contract_version="synthetic-selection-v1", rubric_id="synthetic-selection",
        subject="computer_science", numeric_policy=NumericPolicy(),
        total_points=Decimal("15"),
        questions=[q("q1", "10"), q("q2", "10"), q("q3", "5")],
        selection_groups=[SelectionGroup(group_id="sg0", choose_k=1,
                                         of_question_ids=["q1", "q2"])],
    )


def make_transcription(answers: List[Tuple[int, Optional[str], str]]) -> TranscriptionContract:
    return TranscriptionContract(
        contract_version="synthetic-transcription-v1",
        answers=[TranscriptionContractAnswer(question_number=q, sub_question_id=s,
                                             answer_text=t)
                 for q, s, t in answers],
    )


ANSWER_Q1 = "the loop runs over items and total accumulates each value correctly"
ANSWER_Q2A = "the function returns the maximum channel of the array"


def make_bundle(gt: Optional[FixtureGT] = None, *, with_q2_answer: bool = True) -> FixtureBundle:
    answers = [(1, None, ANSWER_Q1)]
    if with_q2_answer:
        answers.append((2, "א", ANSWER_Q2A))
    return assemble_bundle("synthetic", make_contract(), make_transcription(answers), gt=gt)


def make_selection_bundle(gt: Optional[FixtureGT] = None) -> FixtureBundle:
    answers = [(1, None, "answer to q one"), (2, None, "answer to q two"),
               (3, None, "answer to q three")]
    return assemble_bundle("synthetic-selection", make_selection_contract(),
                           make_transcription(answers), gt=gt)


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------

def make_gt(awards: Dict[str, str], *, fixture: str = "synthetic",
            ungradable: Optional[List[Tuple[str, Optional[str], str]]] = None,
            evidence: Optional[Dict[str, bool]] = None,
            **overrides) -> FixtureGT:
    evidence = evidence or {}
    fields = dict(GT_STAMP)
    fields.update(overrides)
    return FixtureGT(
        fixture=fixture, rubric_contract_hash="", transcription_contract_hash="",
        terminals=[TerminalGT(terminal_id=t, awarded=Decimal(a),
                              evidence_exists=evidence.get(t, True))
                   for t, a in awards.items()],
        ungradable_scopes=[ScopeUngradable(question_id=q, sub_question_id=s, reason=r)
                           for q, s, r in (ungradable or [])],
        **fields,
    )


GT_PERFECT = {"q1.c0": "2", "q1.c1.s0": "1", "q1.c1.s1": "2", "q2.א.c0": "4"}


# ---------------------------------------------------------------------------
# Drafts (what the agent would return) — constructed directly
# ---------------------------------------------------------------------------

def _quote(text: Optional[str], status: Optional[QuoteValidationStatus]) -> Optional[AnswerQuotation]:
    if text is None:
        return None
    return AnswerQuotation(quote_text=text, validation_status=status or QuoteValidationStatus.EXACT)


TerminalSpec = Tuple[str, float, Optional[str], Optional[QuoteValidationStatus]]
# (awarded, confidence, quote_text|None, status|None)


def make_scope_outcome(scope: GradableScope,
                       terminals: Dict[str, TerminalSpec],
                       *, graded_by: str = "llm",
                       extra_flags: Optional[List[FlaggedOutcome]] = None) -> ScopeOutcome:
    """Build a ScopeOutcome mirroring the agent's assembly for one scope."""
    criterion_outcomes: List[CriterionOutcome] = []
    confidences: List[float] = []
    for criterion in scope.criteria:
        if criterion.sub_criteria:
            subs = []
            for sc in criterion.sub_criteria:
                a, conf, qt, qs = terminals[sc.sub_criterion_id]
                subs.append(SubCriterionOutcome(
                    sub_criterion_id=sc.sub_criterion_id, description=sc.description,
                    points_possible=sc.points, points_awarded=Decimal(a),
                    reasoning="נימוק", confidence=conf, evidence_quote=_quote(qt, qs)))
                confidences.append(conf)
            criterion_outcomes.append(CriterionOutcome(
                criterion_id=criterion.criterion_id, description=criterion.description,
                points_possible=criterion.points,
                points_awarded=sum((s.points_awarded for s in subs), Decimal("0")),
                reasoning="", confidence=min(c.confidence for c in subs) if subs else 0.0,
                evidence_quote=None, sub_criterion_outcomes=subs))
        else:
            a, conf, qt, qs = terminals[criterion.criterion_id]
            criterion_outcomes.append(CriterionOutcome(
                criterion_id=criterion.criterion_id, description=criterion.description,
                points_possible=criterion.points, points_awarded=Decimal(a),
                reasoning="נימוק", confidence=conf, evidence_quote=_quote(qt, qs)))
            confidences.append(conf)
    return ScopeOutcome(
        scope_kind=scope.scope_kind, question_id=scope.question_id,
        sub_question_id=scope.sub_question_id, points_possible=scope.points,
        points_awarded=sum((c.points_awarded for c in criterion_outcomes), Decimal("0")),
        min_confidence=min(confidences) if confidences else 0.0,
        criterion_outcomes=criterion_outcomes,
        flags=list(extra_flags or []), graded_by=graded_by,
        input_tokens=1000, output_tokens=400,
    )


def make_skip_outcome(scope: GradableScope) -> ScopeOutcome:
    """Mirror of the agent's _build_skip_result shape (zero awards + NO_ANSWER)."""
    cos = []
    for criterion in scope.criteria:
        cos.append(CriterionOutcome(
            criterion_id=criterion.criterion_id, description=criterion.description,
            points_possible=criterion.points, points_awarded=Decimal("0"),
            reasoning="", confidence=0.0, evidence_quote=None,
            sub_criterion_outcomes=None,
            flags=[FlaggedOutcome(criterion_id=criterion.criterion_id,
                                  reason=FlagReason.NO_ANSWER)]))
    return ScopeOutcome(
        scope_kind=scope.scope_kind, question_id=scope.question_id,
        sub_question_id=scope.sub_question_id, points_possible=scope.points,
        points_awarded=Decimal("0"), min_confidence=0.0, criterion_outcomes=cos,
        flags=[FlaggedOutcome(question_id=scope.question_id, reason=FlagReason.NO_ANSWER)],
        graded_by="skipped_no_answer")


def make_failure_outcome(scope: GradableScope, exception_class: str) -> Tuple[ScopeOutcome, GradingAnnotation]:
    """Mirror of _build_failure_result: flagged zero outcome + llm_failure annotation."""
    cos = [CriterionOutcome(
        criterion_id=c.criterion_id, description=c.description,
        points_possible=c.points, points_awarded=Decimal("0"), reasoning="",
        confidence=0.0, evidence_quote=None,
        flags=[FlaggedOutcome(criterion_id=c.criterion_id, reason=FlagReason.LLM_UNCERTAINTY)])
        for c in scope.criteria]
    target = scope.question_id if scope.sub_question_id is None else f"{scope.question_id}.{scope.sub_question_id}"
    ann = GradingAnnotation(severity=AnnotationSeverity.ERROR, target_id=target,
                            annotation_type="llm_failure", message="שגיאת LLM",
                            metadata={"exception_class": exception_class, "retry_count": 0})
    return ScopeOutcome(
        scope_kind=scope.scope_kind, question_id=scope.question_id,
        sub_question_id=scope.sub_question_id, points_possible=scope.points,
        points_awarded=Decimal("0"), min_confidence=0.0, criterion_outcomes=cos,
        flags=[FlaggedOutcome(question_id=scope.question_id, reason=FlagReason.LLM_UNCERTAINTY)],
        graded_by="failed"), ann


def make_draft(bundle: FixtureBundle, scope_outcomes: List[ScopeOutcome],
               annotations: Optional[List[GradingAnnotation]] = None) -> GradedTestDraft:
    return GradedTestDraft(
        rubric_contract_version=bundle.rubric_contract.contract_version,
        transcription_contract_version=bundle.transcription_contract.contract_version,
        model_version="gpt-4o", prompt_version="grader-v1",
        scope_outcomes=scope_outcomes, teacher_overrides={},
        annotations=list(annotations or []),
        unmatched_transcription_answers=[],
        llm_calls_count=sum(1 for s in scope_outcomes if s.graded_by == "llm"),
        grading_duration_ms=1234,
        total_input_tokens=sum(s.input_tokens for s in scope_outcomes),
        total_output_tokens=sum(s.output_tokens for s in scope_outcomes),
    )


def draft_from_gt(bundle: FixtureBundle, gt: FixtureGT, *, confidence: float = 0.9) -> GradedTestDraft:
    """The known-answer draft: awards == GT, quotes exact from the answer text."""
    gt_map = {t.terminal_id: t.awarded for t in gt.terminals}
    outcomes = []
    for scope in bundle.gradable_test.scopes:
        if scope.alignment == "answer_missing" or not scope.student_answer_text:
            outcomes.append(make_skip_outcome(scope))
            continue
        quote = scope.student_answer_text[: min(20, len(scope.student_answer_text))]
        specs: Dict[str, TerminalSpec] = {}
        for criterion in scope.criteria:
            if criterion.sub_criteria:
                for sc in criterion.sub_criteria:
                    a = gt_map[sc.sub_criterion_id]
                    specs[sc.sub_criterion_id] = (
                        str(a), confidence,
                        quote if a > 0 else None,
                        QuoteValidationStatus.EXACT if a > 0 else None)
            else:
                a = gt_map[criterion.criterion_id]
                specs[criterion.criterion_id] = (
                    str(a), confidence,
                    quote if a > 0 else None,
                    QuoteValidationStatus.EXACT if a > 0 else None)
        outcomes.append(make_scope_outcome(scope, specs))
    return make_draft(bundle, outcomes)
