"""
A teacher's correction of ONE answer at the grading gate, and the regrade of exactly the
scopes it changes (owner rulings 2026-11-01, D1–D13).

THE PROBLEM. At the grading gate she sees that a grade is wrong because the TRANSCRIPTION
is wrong — a missed line, a misread symbol. The approved transcription was read-only
(LCY-1) and no revision path started from a `draft`, so her only recourse was to override
every check by hand while the evidence kept pointing at the wrong text.

THE SHAPE (D1 = A, D2 = synchronous). One request, all or nothing:

  1. guards — hers, `draft`, the chain's leaf, a v6 grade, the rubric and transcription
     pins still current, the plan it was graded with still loadable, the same grader
  2. freeze a NEW transcription contract with that one answer replaced (fresh version;
     the answer keeps `original_text`, the text as first approved)
  3. no connection held: compile both tests, regrade exactly the scopes whose GRADER
     INPUT changed (SRG-1), price + select the whole test again, rewrite the regraded
     scopes' feedback and the summary (D6)
  4. one transaction: the transcription's current contract moves (the superseded one is
     appended to `contract_history` — LCY-1 is append-only now, never lost), and the
     chain is extended with the regraded draft pinned to the new transcription version
     (VER-3, as VER-2 does for the rubric)

NAMED PROTOCOLS (the spec — §0.3):
  SRG-1 RegradeWhatChanged — the regrade set is every scope whose rendered verifier input
        differs between the old and the corrected transcription: the scope she edited, a
        sibling that inherits the same answer (D3), and — while
        GRADER_PRIOR_CONTEXT_ENABLED is on — every later part of the question that reads
        it as context (D12). Plus the edited scope itself when it had FAILED (D10: a
        retry with the text unchanged).
  SRG-2 CarriedIsUntouched — every other scope's outcome, records, lines and annotations
        are the prior draft's (`OptionsVerifyGrader.regrade`).
  SRG-3 SamePlanSameGrader — the plan the draft was graded with (by `plan_hash`), the same
        rubric contract version, the same verifier model and prompt stamp, or refuse: a
        graft across any of them would mix two graders in one grade.

WHAT IS CLEARED (D5): her decisions on a regraded scope judged text that no longer
exists — option picks, typed amounts, criterion pins and evidence disputes go; her notes
(on checks and criteria) and her own feedback text stay.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grading import GradedTest, Rubric
from app.models.grading_plan import GradingPlanRecord
from app.models.transcription import Transcription
from app.schemas.graded_test_draft import FeedbackBlock, GradedTestDraft, GradedTestOverrides
from app.schemas.graded_test_draft_v6 import DraftV6Content, v6_content
from app.schemas.ontology_types import GradingRubricContract
from app.schemas.transcription import TranscriptionContract, TranscriptionContractAnswer

logger = logging.getLogger(__name__)

AnswerKey = Tuple[int, Optional[str]]          # (question_number, sub_question_id)
ScopeKey = Tuple[str, Optional[str]]           # (question_id, sub_question_id)

ANSWER_MAX_CHARS = 20000


class RegradeRefused(Exception):
    """A guard fired. `code` is stable for the client; `message_he` is what she reads."""

    def __init__(self, status: int, code: str, message_he: str, **extra: Any):
        super().__init__(f"{code}: {message_he}")
        self.status, self.code, self.message_he, self.extra = status, code, message_he, extra


# ═══════════════════════════════════════════════════════════════════════════
# pure parts
# ═══════════════════════════════════════════════════════════════════════════

def question_numbers(rubric: GradingRubricContract) -> Dict[str, int]:
    """question_id → the transcription's question_number, by the compiler's own rule."""
    from app.services.gradable_compiler import _q_num
    return {q.question_id: _q_num(q.question_id, i) for i, q in enumerate(rubric.questions)}


def answer_key_for(scope, q_num: int) -> AnswerKey:
    """The transcription answer this scope READS. An inheriting leaf reads its ancestor's
    answer (D3 — the edit changes that shared answer); a scope with no answer reads its
    own key, where a new answer goes (D4)."""
    if scope.answer_source == "inherited":
        return (q_num, scope.answer_inherited_from)
    return (q_num, scope.sub_question_id)


def corrected_contract(contract: TranscriptionContract, key: AnswerKey,
                       text: str) -> Optional[TranscriptionContract]:
    """The contract with the answer at `key` replaced by `text` (appended when absent), a
    fresh `contract_version`, or None when nothing changes.

    `original_text` keeps the FIRST approved text through any number of corrections and
    is cleared when she restores it exactly. Figures (D9) are read-only here: an edit
    that drops a figure's `[איור N: …]` line is refused, never silently detached (FIG-1)."""
    from app.services.figures import match_figures
    answers = list(contract.answers)
    idx = next((i for i, a in enumerate(answers)
                if (a.question_number, a.sub_question_id) == key), None)
    current = answers[idx] if idx is not None else None
    if current is not None and current.answer_text == text:
        return None
    if current is None and not text.strip():
        return None
    original = (current.original_text if current is not None and current.original_text is not None
                else (current.answer_text if current is not None else ""))
    figures = list(current.figures) if current is not None else []
    if figures and match_figures(text, figures).orphans:
        raise RegradeRefused(422, "figure_line_removed",
                             "אי אפשר למחוק או לשנות שורת איור בעריכה הזו — "
                             "השאירי את שורות «[איור …]» כפי שהן.")
    replaced = TranscriptionContractAnswer(
        question_number=key[0], sub_question_id=key[1], answer_text=text,
        page_numbers=list(current.page_numbers) if current is not None else [],
        figures=figures, original_text=None if text == original else original)
    if idx is None:
        answers.append(replaced)
    else:
        answers[idx] = replaced
    return TranscriptionContract(schema_version=contract.schema_version, answers=answers)


def _scope_render(scope, plan) -> Tuple[str, str]:
    from app.agents.grader.grader import _get_terminal_map
    from app.agents.grader.verifier_prompt_v6 import build_verifier_v6_parts, verifier_aliases
    tids = set(_get_terminal_map(scope))
    checks = [c for c in plan.checks if c.priced_terminal_id in tids]
    return build_verifier_v6_parts(scope, checks, verifier_aliases(checks))


def affected_scopes(old_test, new_test, plan) -> List[ScopeKey]:
    """SRG-1: the scopes whose rendered verifier input differs, in test order. Comparing
    what the grader would READ — not the scope objects — is what makes the set follow
    inheritance and the prior-context flag without a rule for either."""
    old = {(s.question_id, s.sub_question_id): s for s in old_test.scopes}
    out: List[ScopeKey] = []
    for s in new_test.scopes:
        key = (s.question_id, s.sub_question_id)
        if key not in old or _scope_render(s, plan) != _scope_render(old[key], plan):
            out.append(key)
    return out


def scope_terminal_ids(content: DraftV6Content, keys: Set[ScopeKey]) -> Set[str]:
    return {t.terminal_id for t in content.view_terminals
            if (t.question_id, t.sub_question_id) in keys}


def clear_scope_decisions(overrides: GradedTestOverrides, content: DraftV6Content,
                          keys: Set[ScopeKey]) -> Tuple[GradedTestOverrides, int]:
    """D5. Returns the overrides with her decisions on `keys` cleared, and how many there
    were. A check decision that carried a note keeps the note alone; criterion notes and
    her feedback text are untouched."""
    from app.services.pricing_v6 import CheckDecision
    from app.services.v6_review import overlay_doc, overlay_of
    tids = scope_terminal_ids(content, keys)
    cids = {c.plan.check_id for c in content.checks if c.plan.priced_terminal_id in tids}
    overlay = overlay_of(overrides)
    checks, cleared = {}, 0
    for cid, d in overlay.checks.items():
        if cid not in cids:
            checks[cid] = d
            continue
        if d.option_id is not None or d.amount is not None or d.evidence_disputed:
            cleared += 1
        if d.comment and d.comment.strip():
            checks[cid] = CheckDecision(comment=d.comment)
    pins = {}
    for tid, v in overlay.terminal_points.items():
        if tid in tids:
            cleared += 1
        else:
            pins[tid] = v
    if not cleared and len(checks) == len(overlay.checks):
        return overrides, 0
    kept = overlay.model_copy(update={"checks": checks, "terminal_points": pins})
    return overrides.model_copy(update={"v6": overlay_doc(kept)}), cleared


def merge_feedback(prior: Optional[FeedbackBlock], generated: Optional[FeedbackBlock],
                   regraded_ids: Set[str], hers: Dict[str, str]) -> Optional[FeedbackBlock]:
    """D6 + the summary. The regraded scopes' texts and the summary are rewritten; every
    other scope's text is one she may already have read and stays (a gap is filled, as
    the summary regenerate fills one). Her own text always stands (OD-G4.2). A failed
    call changes nothing: the regraded scopes then read as stale and the surface
    rewrites them, as it does for any stale scope."""
    if generated is None:
        return prior
    if prior is None:
        return generated
    scopes = dict(prior.scopes)
    for sid in regraded_ids:
        if sid in hers:
            continue
        if sid in generated.scopes:
            scopes[sid] = generated.scopes[sid]
        else:
            scopes.pop(sid, None)            # no longer graded by the model: nothing to say
    for sid, text in generated.scopes.items():
        if sid not in hers and not (scopes.get(sid) and scopes[sid].text.strip()):
            scopes[sid] = text
    summary = prior.summary if "summary" in hers else generated.summary
    return prior.model_copy(update={"scopes": scopes, "summary": summary,
                                    "model_version": generated.model_version,
                                    "prompt_version": generated.prompt_version})


# ═══════════════════════════════════════════════════════════════════════════
# what the editor opens on
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AnswerSource:
    """The RAW transcription answer a scope reads — what the editor opens on. Never the
    text on screen: that one has each figure's readings expanded under its line (EVD-1
    records what the grader read), and saving it back would write derived lines into the
    transcription."""
    question_number: int
    sub_question_id: Optional[str]
    answer_text: str                    # "" when the transcription has no answer here (D4)
    original_text: Optional[str]
    shared_scope_ids: List[str]         # D3: every scope that reads this same answer
    has_figures: bool                   # D9: its `[איור …]` lines are read-only


async def answer_source(db: AsyncSession, *, graded_test_id: UUID, user_id: UUID,
                        question_id: str, sub_question_id: Optional[str]) -> AnswerSource:
    """Resolved by the same rule the regrade uses (`answer_key_for`), from the
    transcription's CURRENT contract — one resolution, so the editor and the regrade can
    never disagree about which answer she is editing."""
    from app.services.gradable_compiler import compile as compile_gradable_test
    row = (await db.execute(select(GradedTest).where(
        GradedTest.id == graded_test_id, GradedTest.user_id == user_id))).scalar_one_or_none()
    if row is None:
        raise RegradeRefused(404, "not_found", "המבחן לא נמצא.")
    transcription = await db.get(Transcription, row.transcription_id)
    rubric = await db.get(Rubric, row.rubric_id)
    if transcription is None or not transcription.contract_json or rubric is None             or not rubric.contract_json:
        raise RegradeRefused(409, "transcription_not_approved", "התמלול של המבחן הזה אינו מאושר.")
    tc = TranscriptionContract.model_validate(transcription.contract_json)
    rc = GradingRubricContract.model_validate(rubric.contract_json)
    test = compile_gradable_test(rc, tc)
    numbers = question_numbers(rc)
    scope = next((s for s in test.scopes
                  if (s.question_id, s.sub_question_id) == (question_id, sub_question_id)), None)
    if scope is None:
        raise RegradeRefused(404, "unknown_scope", "הסעיף לא נמצא במבחן הזה.")
    key = answer_key_for(scope, numbers[question_id])
    answer = next((a for a in tc.answers if (a.question_number, a.sub_question_id) == key), None)
    shared = [_scope_id((s.question_id, s.sub_question_id)) for s in test.scopes
              if s.question_id == question_id and answer_key_for(s, numbers[s.question_id]) == key]
    return AnswerSource(question_number=key[0], sub_question_id=key[1],
                        answer_text=answer.answer_text if answer is not None else "",
                        original_text=answer.original_text if answer is not None else None,
                        shared_scope_ids=shared,
                        has_figures=bool(answer is not None and answer.figures))


# ═══════════════════════════════════════════════════════════════════════════
# the operation
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class RegradeOutcome:
    graded_test_id: UUID
    regraded_scope_ids: List[str]
    cleared_decisions: int
    feedback_rewritten: bool
    transcription_corrected: bool
    cost_usd: Decimal = Decimal("0")
    timings: Dict[str, float] = field(default_factory=dict)


def _scope_id(key: ScopeKey) -> str:
    return key[0] if key[1] is None else f"{key[0]}.{key[1]}"


async def _load_plan(db: AsyncSession, plan_hash: str):
    from app.agents.grader.plan_schemas import GradingPlanV6
    plan_json = (await db.execute(
        select(GradingPlanRecord.plan_json)
        .where(GradingPlanRecord.plan_hash == plan_hash, GradingPlanRecord.plan_json.isnot(None))
        .order_by(GradingPlanRecord.created_at.desc()).limit(1))).scalar_one_or_none()
    return None if plan_json is None else GradingPlanV6.model_validate(plan_json)


def _refuse_if_not_open(row: GradedTest) -> None:
    if row.status != "draft":
        raise RegradeRefused(409, "not_draft",
                             "אפשר לתקן תמלול רק במבחן שעדיין לא אושר.")
    if row.regraded_to_id is not None:
        raise RegradeRefused(409, "superseded",
                             "יש גרסה חדשה יותר של המבחן הזה — פתחי אותה ונסי שוב.",
                             successor_id=str(row.regraded_to_id))


async def regrade_answer(db: AsyncSession, *, graded_test_id: UUID, user_id: UUID,
                         question_id: str, sub_question_id: Optional[str],
                         answer_text: str) -> RegradeOutcome:
    """The whole operation. `db` is released before any model call (§7 sessions rule) and
    the write re-reads both rows under a lock, so her saves made meanwhile are carried."""
    from app.agents.feedback.runner import attach_feedback
    from app.config import settings
    from app.services.gradable_compiler import compile as compile_gradable_test
    from app.services.grader_selection import build_grader_v6
    from app.services.grading_runner import _usage_cost
    from app.services.graded_test_revision import extend_chain
    from app.services.selection_scoring import ScopeScore, score_with_selection
    from app.services.v6_review import review
    from app.tracing import student_data_run

    t0 = time.monotonic()
    if len(answer_text) > ANSWER_MAX_CHARS:
        raise RegradeRefused(422, "answer_too_long", "התשובה ארוכה מדי.")

    # ── 1. guards (one read) ────────────────────────────────────────────────
    row = (await db.execute(select(GradedTest).where(
        GradedTest.id == graded_test_id, GradedTest.user_id == user_id))).scalar_one_or_none()
    if row is None:
        raise RegradeRefused(404, "not_found", "המבחן לא נמצא.")
    _refuse_if_not_open(row)
    draft = GradedTestDraft.model_validate(row.draft_json)
    content = v6_content(draft)
    if content is None:
        raise RegradeRefused(409, "not_v6", "תיקון תמלול זמין רק במבחנים שנבדקו בגרסה הנוכחית של ויוי.")
    transcription = await db.get(Transcription, row.transcription_id)
    rubric = await db.get(Rubric, row.rubric_id)
    if transcription is None or transcription.status != "approved" or not transcription.contract_json:
        raise RegradeRefused(409, "transcription_not_approved", "התמלול של המבחן הזה אינו מאושר.")
    tc = TranscriptionContract.model_validate(transcription.contract_json)
    if tc.contract_version != draft.transcription_contract_version:
        raise RegradeRefused(409, "transcription_moved",
                             "התמלול השתנה מאז שהמבחן נבדק — רעני את הדף ונסי שוב.")
    if rubric is None or not rubric.contract_json or rubric.contract_version != row.rubric_contract_version:
        raise RegradeRefused(409, "rubric_changed",
                             "המחוון עודכן מאז שהמבחן נבדק, ולכן אי אפשר לבדוק מחדש סעיף בודד.")
    rc = GradingRubricContract.model_validate(rubric.contract_json)
    plan = await _load_plan(db, content.plan_hash)
    if plan is None:
        raise RegradeRefused(409, "plan_missing", "לא ניתן לבדוק מחדש את הסעיף הזה כרגע.")
    transcription_id, rubric_subject = row.transcription_id, rubric.subject
    prior_tc_version = tc.contract_version

    old_test = compile_gradable_test(rc, tc)
    scope = next((s for s in old_test.scopes
                  if (s.question_id, s.sub_question_id) == (question_id, sub_question_id)), None)
    if scope is None:
        raise RegradeRefused(404, "unknown_scope", "הסעיף לא נמצא במבחן הזה.")
    key = answer_key_for(scope, question_numbers(rc)[question_id])
    prior_outcome = next(so for so in draft.scope_outcomes
                         if (so.question_id, so.sub_question_id) == (question_id, sub_question_id))

    new_tc = corrected_contract(tc, key, answer_text)
    if new_tc is None:
        if prior_outcome.graded_by != "failed":                 # D11
            raise RegradeRefused(422, "unchanged", "התשובה לא השתנתה.")
        test, keys = old_test, [(question_id, sub_question_id)]  # D10: a retry, text unchanged
    else:
        test = compile_gradable_test(rc, new_tc)
        keys = affected_scopes(old_test, test, plan)
        if not keys:
            raise RegradeRefused(422, "unchanged", "התשובה לא השתנתה.")
    await db.close()

    # ── 2. the grade (no connection held) ───────────────────────────────────
    agent = build_grader_v6(plan, rc, gradable_test=test)
    if (agent.model_version, agent.prompt_version) != (draft.model_version, draft.prompt_version):
        raise RegradeRefused(409, "grader_changed",
                             "ויוי עודכנה מאז שהמבחן נבדק, ולכן אי אפשר לבדוק מחדש סעיף בודד.")
    with student_data_run(graded_test_id=graded_test_id, transcription_id=transcription_id):
        result = await agent.regrade(test, draft, keys)
    t_grade = time.monotonic() - t0
    regraded = result.draft
    by_key = {(so.question_id, so.sub_question_id): so for so in regraded.scope_outcomes}
    if any(by_key[k].graded_by == "failed" for k in keys):
        # the plan promises: nothing on the server changes, her text stays in the editor
        raise RegradeRefused(502, "regrade_failed",
                             "הבדיקה מחדש לא הצליחה הפעם. התיקון שלך לא נשמר — נסי שוב.")

    scoring = score_with_selection(
        [ScopeScore(question_id=so.question_id, sub_question_id=so.sub_question_id,
                    awarded=so.points_awarded) for so in regraded.scope_outcomes], rc)
    if scoring.excluded:                                   # [D-6] before feedback, as the runner does
        regraded = regraded.model_copy(update={"scope_outcomes": [
            so.model_copy(update={"graded_by": "excluded_by_selection"})
            if not scoring.is_counted((so.question_id, so.sub_question_id)) else so
            for so in regraded.scope_outcomes]})

    # D6: the regraded scopes' feedback and the summary, described under her decisions
    # as they will stand (D5 applied)
    new_content = v6_content(regraded)
    key_set = set(keys)
    cleared, _ = clear_scope_decisions(draft.teacher_overrides, new_content, key_set)
    feedback_usage: Dict[str, Any] = {}
    with student_data_run(graded_test_id=graded_test_id, transcription_id=transcription_id):
        written = await attach_feedback(
            regraded.model_copy(update={"feedback": None, "annotations": [],
                                        "teacher_overrides": cleared}),
            graded_test_id=graded_test_id, usage=feedback_usage, subject=rubric_subject)
    regraded_ids = {_scope_id(k) for k in keys}
    t_feedback = time.monotonic() - t0 - t_grade

    # ── 3. one transaction ──────────────────────────────────────────────────
    row = (await db.execute(select(GradedTest).where(
        GradedTest.id == graded_test_id, GradedTest.user_id == user_id)
        .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if row is None:
        raise RegradeRefused(404, "not_found", "המבחן לא נמצא.")
    _refuse_if_not_open(row)
    transcription = (await db.execute(select(Transcription).where(
        Transcription.id == transcription_id)
        .with_for_update().execution_options(populate_existing=True))).scalar_one()
    if (transcription.contract_json or {}).get("contract_version") != prior_tc_version:
        await db.rollback()
        raise RegradeRefused(409, "transcription_moved",
                             "התמלול השתנה בזמן הבדיקה — רעני את הדף ונסי שוב.")
    latest = GradedTestDraft.model_validate(row.draft_json)
    overrides, cleared_count = clear_scope_decisions(latest.teacher_overrides, new_content, key_set)
    feedback = merge_feedback(latest.feedback, written.feedback, regraded_ids,
                              overrides.feedback or {})
    annotations = list(regraded.annotations)
    if written.feedback is not None:                       # a fresh block retires the old failure note
        annotations = [a for a in annotations if a.annotation_type != "feedback_unavailable"]
    final = regraded.model_copy(update={"teacher_overrides": overrides, "feedback": feedback,
                                        "annotations": annotations})

    corrected = new_tc is not None
    now = datetime.now(timezone.utc)
    if corrected:
        transcription.contract_history = list(transcription.contract_history or []) + [{
            "contract": transcription.contract_json,
            "superseded_at": now.isoformat(),
            "superseded_by": new_tc.contract_version,
            "reason": "teacher_answer_correction",
            "answer_key": {"question_number": key[0], "sub_question_id": key[1]},
            "graded_test_id": str(graded_test_id),
        }]
        transcription.contract_json = new_tc.model_dump(mode="json")
        transcription.updated_at = now

    priced = review(final, overrides).final
    total_possible = scoring.total_possible
    cost = sum((_usage_cost(u.model, u.input_tokens, u.output_tokens, u.cached_input_tokens,
                            u.cache_write_input_tokens) for u in result.verifier_usage), Decimal("0"))
    if result.explainer_usage is not None:
        u = result.explainer_usage
        cost += _usage_cost(u.model, u.input_tokens, u.output_tokens, u.cached_input_tokens,
                            u.cache_write_input_tokens)
    if feedback_usage:
        cost += _usage_cost(feedback_usage.get("model"), int(feedback_usage.get("input_tokens") or 0),
                            int(feedback_usage.get("output_tokens") or 0))
    cost = cost.quantize(Decimal("0.0001"))
    r2 = await extend_chain(
        db, row, new_status="draft", new_rubric_contract_version=row.rubric_contract_version,
        new_draft_json=final.model_dump(mode="json"),
        new_transcription_contract_version=(new_tc.contract_version if corrected else None),
        row_fields={
            "draft_created_at": now,
            "total_score": priced.total_score,
            "total_possible": total_possible,
            "percentage": ((priced.total_score / total_possible * 100).quantize(Decimal("0.01"))
                           if total_possible > 0 else Decimal("0")),
            # the row records what producing IT cost: this operation alone
            "llm_calls_count": len(result.verifier_usage),
            "grading_duration_ms": int((time.monotonic() - t0) * 1000),
            "model_version": final.model_version,
            "prompt_version": final.prompt_version,
            "total_input_tokens": sum(u.input_tokens for u in result.verifier_usage),
            "total_output_tokens": sum(u.output_tokens for u in result.verifier_usage),
            "total_cost_usd": cost,
        })
    logger.info(f"scope_regrade graded_test_id={graded_test_id} successor={r2.id} "
                f"scopes={sorted(regraded_ids)} corrected={corrected} cleared={cleared_count} "
                f"feedback={'rewritten' if written.feedback is not None else 'kept'} "
                f"grade_s={t_grade:.1f} feedback_s={t_feedback:.1f} cost_usd={cost}")
    return RegradeOutcome(graded_test_id=r2.id, regraded_scope_ids=sorted(regraded_ids),
                          cleared_decisions=cleared_count,
                          feedback_rewritten=written.feedback is not None,
                          transcription_corrected=corrected, cost_usd=cost,
                          timings={"grade_s": t_grade, "feedback_s": t_feedback})
