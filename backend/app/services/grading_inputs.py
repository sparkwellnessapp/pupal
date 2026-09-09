"""The two pinned inputs to a grade, and their provenance.

A grade is a function of four things (§7): the rubric contract, the
transcription contract, the model, and the prompt. Three of those were already
recorded on the row. The transcription contract was not — it was identified
only by `transcription_id`, so "what did the grader consume?" was a RECORDED
fact for the rubric and an INFERRED one for the transcription, resting on LCY-1
immutability holding elsewhere in the system.

Migration 029 closes that. This module owns reading the pin off a transcription
row, so the three graded-test creation sites do it one way instead of three.
"""
import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:                       # pragma: no cover
    from ..schemas.graded_test_draft import ScopeAnswer

logger = logging.getLogger(__name__)


def transcription_contract_version(transcription) -> Optional[str]:
    """The `contract_version` of an approved transcription's contract, or None.

    The version lives INSIDE `contract_json` (Phase 0a RD-3 — it is a field of
    the contract, not a column), so this reads it out rather than selecting it.

    None is a legitimate answer and is stored as such:
      * the transcription has not been approved yet (no contract), or
      * the contract predates the field.
    Both mean "unverified provenance", which is a different and more honest
    claim than a fabricated version string. NEVER substitute a placeholder —
    the whole point of the pin is that it can be checked.
    """
    contract = getattr(transcription, "contract_json", None)
    if not isinstance(contract, dict):
        return None
    version = contract.get("contract_version")
    if version is None:
        return None
    if not isinstance(version, str):
        # A non-string here means the contract shape drifted. Say so loudly
        # rather than coercing: `str(version)` would record a provenance that
        # matches nothing.
        logger.warning(
            "transcription_contract_version_not_a_string transcription_id=%s type=%s",
            getattr(transcription, "id", "?"), type(version).__name__,
        )
        return None
    return version


def scope_answer(scope) -> "Optional[ScopeAnswer]":
    """The `ScopeAnswer` evidence for one `GradableScope`, or None.

    ONE translation, used by every grader, so "what was this scope graded
    against?" is recorded identically no matter which architecture produced the
    grade (v3 and v5 both call it).

    None exactly when the scope had no answer — which is also exactly when the
    grader emits `graded_by="skipped_no_answer"`. Those two must agree, and
    they do because both are derived from the same `alignment`, not from two
    independent judgements.
    """
    from ..schemas.graded_test_draft import ScopeAnswer   # local: avoids a cycle

    text = getattr(scope, "student_answer_text", None)
    if text is None:
        return None
    source = getattr(scope, "answer_source", None) or "own"
    return ScopeAnswer(
        text=text,
        source=source,
        # Never carried on an "own" answer: there is no ancestor to name, and a
        # stale path here would claim an inheritance that did not happen.
        inherited_from=(getattr(scope, "answer_inherited_from", None)
                        if source == "inherited" else None),
    )


async def backfill_scope_answers(
    db, row, draft, *, rubric, rubric_contract_stale: bool,
) -> int:
    """Fill `student_answer` on draft scopes written before the field existed.

    LEGACY ONLY, and read-only: nothing is persisted. A row graded after EVD-1
    already carries its evidence and never reaches the body of this function.

    IT REFUSES RATHER THAN GUESSES, in four situations, because a resolved
    answer is a claim about what the grader consumed and a wrong one is worse
    than an absent one (§3.5a — degrade by OMISSION, never by substitution):

      1. the rubric contract is STALE. `rubrics.contract_json` holds only the
         LATEST contract, so the scope tree the grader used is gone. Resolving
         against today's tree can silently attach a different ancestor's answer
         to a leaf.
      2. the row's pinned transcription contract (029) does not match the
         transcription's current one — the input moved under the grade. This is
         the check the pin exists for; without it this case is invisible.
      3. either contract will not parse.
      4. the recompiled scope set does not contain this scope id.

    Returns the number of scopes filled, for the caller's log line.
    """
    from ..models.transcription import Transcription
    from ..schemas.ontology_types import GradingRubricContract
    from ..schemas.transcription import TranscriptionContract
    from .gradable_compiler import compile as compile_gradable

    pending = [
        s for s in draft.scope_outcomes
        if s.student_answer is None and s.graded_by != "skipped_no_answer"
    ]
    if not pending:
        return 0

    def _refuse(why: str) -> int:
        # Message string, not `extra=`: this service renders neither (§8), and
        # the graded_test id is the whole point of the line.
        logger.warning(
            "scope_answer_backfill_refused graded_test_id=%s scopes=%d reason=%s",
            getattr(row, "id", "?"), len(pending), why,
        )
        return 0

    if rubric_contract_stale:
        return _refuse("rubric_contract_stale")
    if rubric is None or not rubric.contract_json:
        return _refuse("no_rubric_contract")

    transcription = await db.get(Transcription, row.transcription_id)
    if transcription is None or not transcription.contract_json:
        return _refuse("no_transcription_contract")

    pinned = getattr(row, "transcription_contract_version", None)
    current = transcription_contract_version(transcription)
    if pinned is not None and current is not None and pinned != current:
        return _refuse("transcription_contract_moved")

    try:
        gradable = compile_gradable(
            GradingRubricContract.model_validate(rubric.contract_json),
            TranscriptionContract.model_validate(transcription.contract_json),
        )
    except Exception:                                        # noqa: BLE001
        logger.exception("scope_answer_backfill_compile_failed graded_test_id=%s",
                         getattr(row, "id", "?"))
        return 0

    by_key = {(s.question_id, s.sub_question_id): s for s in gradable.scopes}
    filled = 0
    for outcome in pending:
        source = by_key.get((outcome.question_id, outcome.sub_question_id))
        if source is None:
            continue                       # refusal (4), per scope
        answer = scope_answer(source)
        if answer is None:
            continue
        outcome.student_answer = answer
        filled += 1

    if filled:
        logger.info("scope_answer_backfill graded_test_id=%s filled=%d of=%d",
                    getattr(row, "id", "?"), filled, len(pending))
    return filled
