"""
GradableTest compiler — pure function, no DB, no LLM, no I/O.

Takes a frozen GradingRubricContract + TranscriptionContract and produces a
GradableTest with per-scope slicing, two-pass identity resolution, and orphan
collection. Deterministic: same inputs always produce the same output.

Two-pass identity resolution:
  Pass 1 (regex):     question_id matches ^q\\d+$ → use the integer suffix as question_number.
  Pass 2 (positional): any other format (e.g. q_{uid}) → use array_index + 1.
Both passes are happy paths; neither emits a warning.

Sub-question matching is direct string equality on sub_question_id (Hebrew letters,
Latin letters, numbers — whatever the DOCX had). This fixes the sub-question-collapse
defect where all sub-question answers were merged into a single text blob.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Set, Tuple

from ..schemas.gradable import (
    GradableCriterion,
    GradableScope,
    GradableSubCriterion,
    GradableTest,
    UnmatchedAnswer,
)
from ..schemas.ontology_types import Criterion, GradingRubricContract, SubCriterion
from ..schemas.transcription import TranscriptionContract

_Q_NUM_RE = re.compile(r"^q(\d+)$")


logger = logging.getLogger(__name__)

def _q_num(question_id: str, array_index: int) -> int:
    """
    Map a contract question_id to its corresponding transcription question_number.

    Pass 1: q{N} format — return N.
    Pass 2: anything else — return array_index + 1.
    """
    m = _Q_NUM_RE.match(question_id)
    return int(m.group(1)) if m else (array_index + 1)


def _to_gradable_sub_criterion(sc: SubCriterion) -> GradableSubCriterion:
    return GradableSubCriterion(
        sub_criterion_id=sc.sub_criterion_id,
        description=sc.description,
        points=sc.points,
    )


def _to_gradable_criterion(c: Criterion) -> GradableCriterion:
    return GradableCriterion(
        criterion_id=c.criterion_id,
        description=c.description,
        points=c.points,
        evaluation_guidance=c.evaluation_guidance,
        notes=c.notes,
        sub_criteria=(
            [_to_gradable_sub_criterion(sc) for sc in c.sub_criteria]
            if c.sub_criteria
            else None
        ),
    )


def _emit_leaf_scopes(
    *,
    sq,                       # SubQuestion (contract-side)
    path: str,                # id relative to the question: "א" | "א.2"
    question,                 # owning top-level Question
    q_num: int,
    answer_index: Dict[Tuple[int, Optional[str]], str],
    matched_answer_keys: Set[Tuple[int, Optional[str]]],
    scopes: List[GradableScope],
    fallback_scopes: List[str],
    inherited_answer: Optional[str],
) -> None:
    """Emit one GradableScope per LEAF of the sub-question tree (PR-3).

    ANSWER ALIGNMENT (R3) — exact id first, then PARENT-ANSWER FALLBACK.
    A leaf `q1.א.2` may face a transcription segmented only to depth 1 (`q1.א`),
    because depth-2 segmentation lives in the transcription pipeline, which has its
    own eval suite and cannot ride along in this PR. So a leaf with no exact-id
    answer inherits its nearest ancestor's answer text: the student's whole-סעיף
    answer physically contains both parts, and the grader scores this leaf's criteria
    against it. The grader gets more context than it strictly needs — correct, mildly
    wasteful.

    This fallback is LOAD-BEARING for every nested rubric, not a graceful
    degradation. `fallback_scopes` records each firing so its rate is the metric for
    when the transcription depth-2 follow-up becomes urgent.
    """
    # This node's own answer, if the transcription addressed it directly.
    own_key = (q_num, path)
    own_answer = answer_index.get(own_key)
    if own_answer is not None:
        matched_answer_keys.add(own_key)

    # What descendants inherit if they have no answer of their own.
    answer_for_subtree = own_answer if own_answer is not None else inherited_answer

    if sq.sub_questions:
        for child in sq.sub_questions:
            _emit_leaf_scopes(
                sq=child,
                path=f"{path}.{child.sub_question_id}",
                question=question,
                q_num=q_num,
                answer_index=answer_index,
                matched_answer_keys=matched_answer_keys,
                scopes=scopes,
                fallback_scopes=fallback_scopes,
                inherited_answer=answer_for_subtree,
            )
        return   # a parent is NOT a scope — its criteria live on its leaves

    # Leaf: this is a gradable scope.
    answer_text = own_answer if own_answer is not None else inherited_answer
    if own_answer is None and answer_text is not None:
        fallback_scopes.append(f"{question.question_id}.{path}")

    scopes.append(GradableScope(
        scope_kind="sub_question",
        question_id=question.question_id,
        sub_question_id=path,          # FULL PATH within the question: "א" | "א.2"
        criteria=[_to_gradable_criterion(c) for c in sq.criteria],
        points=sq.points,
        example_solution=sq.example_solution,
        # Question-level tables are context for sub-question answers too — a
        # sub-question answer may reference a trace table on the parent question.
        trace_tables=question.trace_tables,
        context_tables=question.context_tables,
        question_text=question.question_text,
        sub_question_text=sq.text,
        student_answer_text=answer_text,
        alignment="matched" if answer_text is not None else "answer_missing",
    ))


def compile(  # noqa: A001 — shadows built-in; intentional, matches ContractCompiler convention
    rubric_contract: GradingRubricContract,
    transcription_contract: TranscriptionContract,
) -> GradableTest:
    """
    Marry a GradingRubricContract + TranscriptionContract into a GradableTest.

    Pure function — no DB, no LLM, no I/O. Deterministic.

    Never raises. Missing answers and orphan transcription answers surface as
    data fields on the returned GradableTest, not as exceptions.
    """
    # Build (question_number, sub_question_id) → answer_text lookup in one pass
    answer_index: Dict[Tuple[int, Optional[str]], str] = {
        (a.question_number, a.sub_question_id): a.answer_text
        for a in transcription_contract.answers
    }

    scopes: List[GradableScope] = []
    matched_answer_keys: Set[Tuple[int, Optional[str]]] = set()
    fallback_scopes: List[str] = []   # leaf scopes that took the parent's answer (R3)

    for i, question in enumerate(rubric_contract.questions):
        q_num = _q_num(question.question_id, i)

        if question.sub_questions:
            # PR-3 — SCOPES ARE LEAVES, AT ANY DEPTH.
            #
            # This loop used to walk ONE level and read `sq.criteria` (flat). On a
            # nested rubric that silently produced a parent scope with ZERO criteria
            # but its full points, and NEVER created the inner scopes — the student's
            # answers to the inner parts were simply never graded. It was unreachable
            # only because the old compiler rejected every nested rubric; PR-3 un-gates
            # those rubrics, so this MUST be fixed in the same merge.
            #
            # A sub-question with children contributes no scope of its own; each LEAF
            # becomes a scope carrying ITS criteria and ITS points. With this, CW-1's
            # closed-world guarantee finally covers the scope set the grader receives.
            for sq in question.sub_questions:
                _emit_leaf_scopes(
                    sq=sq,
                    path=sq.sub_question_id,
                    question=question,
                    q_num=q_num,
                    answer_index=answer_index,
                    matched_answer_keys=matched_answer_keys,
                    scopes=scopes,
                    fallback_scopes=fallback_scopes,
                    inherited_answer=None,
                )

        else:
            # Direct-criteria question: one scope; answer has sub_question_id=None.
            answer_key = (q_num, None)
            answer_text = answer_index.get(answer_key)
            if answer_text is not None:
                matched_answer_keys.add(answer_key)

            scopes.append(GradableScope(
                scope_kind="direct",
                question_id=question.question_id,
                sub_question_id=None,
                criteria=[_to_gradable_criterion(c) for c in question.criteria],
                points=question.total_points,
                example_solution=question.example_solution,
                trace_tables=question.trace_tables,
                context_tables=question.context_tables,
                question_text=question.question_text,
                sub_question_text=None,
                student_answer_text=answer_text,
                alignment="matched" if answer_text is not None else "answer_missing",
            ))

    # Sets for building human-readable orphan reason messages
    matched_q_numbers: Set[int] = {
        _q_num(q.question_id, i) for i, q in enumerate(rubric_contract.questions)
    }
    q_num_to_id: Dict[int, str] = {
        _q_num(q.question_id, i): q.question_id
        for i, q in enumerate(rubric_contract.questions)
    }

    unmatched: List[UnmatchedAnswer] = []
    for a in transcription_contract.answers:
        key = (a.question_number, a.sub_question_id)
        if key in matched_answer_keys:
            continue
        if a.question_number not in matched_q_numbers:
            reason = f"no contract question at position {a.question_number}"
        elif a.sub_question_id is not None:
            q_id = q_num_to_id.get(a.question_number, f"q{a.question_number}")
            reason = f"sub_question '{a.sub_question_id}' not in contract question {q_id}"
        else:
            q_id = q_num_to_id.get(a.question_number, f"q{a.question_number}")
            reason = f"no direct-answer slot for question {q_id} (has sub-questions)"
        unmatched.append(UnmatchedAnswer(
            question_number=a.question_number,
            sub_question_id=a.sub_question_id,
            answer_text=a.answer_text,
            reason=reason,
        ))

    if fallback_scopes:
        logger.info(
            "gradable_parent_answer_fallback",
            extra={"scopes": fallback_scopes, "count": len(fallback_scopes)},
        )

    return GradableTest(
        schema_version="1.0",
        rubric_contract_version=rubric_contract.contract_version,
        transcription_contract_version=transcription_contract.contract_version,
        scopes=scopes,
        unmatched_transcription_answers=unmatched,
        # NOTE: this is the OFFERED sum of the sliced scopes and is NOT the grading
        # denominator. The denominator is contract.total_points (ACHIEVABLE), read by
        # services/selection_scoring.py. Re-summing scopes to get a denominator is
        # exactly the bug that made a perfect selection-exam answer score 50%.
        total_points=sum(s.points for s in scopes),
        parent_answer_fallback_scopes=fallback_scopes,
    )
