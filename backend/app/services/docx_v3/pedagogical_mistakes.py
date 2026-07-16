"""
Pedagogical-mistake detection: teacher-induced rubric errors, surfaced (never auto-applied)
to the teacher in RubricEditor.

Two tiers, split by DECIDABILITY (deterministic decides *when* to look; the LLM decides
*what's wrong*):

  TIER A — deterministic, always-run, read-only over the faithful Draft.
    * point_sum_mismatch        : Σ(children) != declared total, per scope, selection-aware.
    * selection_normalization   : a selection group whose member questions have unequal totals
                                  (achievable depends on *which* you pick) -> ambiguous grade.
    Both are computed end-to-end here (an LLM would only add error to arithmetic).
    Plus it emits STRUCTURAL TRIGGERS for the semantic kinds:
    * declared_vs_extracted     : the question prose declares sub-questions {א,ב,ג} but the
                                  מחוון yielded {א,ב}. A reliable, high-precision anomaly —
                                  the general signal that the broken identifier-matching idea
                                  was approximating. This does NOT decide a mislabel; it hands
                                  a bounded question to Tier B.

  TIER B — ONE structured LLM call per trigger, read-only, scoped to the closed
    PedagogicalMistakeKind taxonomy. Given the scope spec + rendered text + the anomaly,
    it adjudicates ("is this a genuine mislabel, and what's the probable fix?") and returns a
    PedagogicalMistake or nothing. No agent, no tool loop, no mutation of the Draft.

The Draft stays FAITHFUL; mistakes live only here; fixes apply only at Contract time on
teacher approval. This pass is read-only and structurally cannot violate that.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field

from ...schemas.ontology_types import (
    AnnotationSeverity, ExtractRubricResponse, PedagogicalMistake,
    PedagogicalMistakeKind, Question, SelectionGroup, SubQuestion, SuggestedFix,
    compute_achievable_points,
)

_EPS = Decimal("0.001")
_HEB = "אבגדהוזחט"

logger = logging.getLogger(__name__)


# =============================================================================
# TIER A — deterministic detection + structural triggers
# =============================================================================

@dataclass
class MislabelTrigger:
    """A structural anomaly handed to Tier B. NOT itself a mistake."""
    question_id: str
    declared: List[str]       # sub-question letters the prose declares
    extracted: List[str]      # sub-question ids present in the Draft
    missing: List[str]        # declared but not extracted (candidate target of a misfiled criterion)
    extra: List[str]          # extracted but not declared


@dataclass
class TierAResult:
    mistakes: List[PedagogicalMistake] = field(default_factory=list)
    triggers: List[MislabelTrigger] = field(default_factory=list)


def _node_children_sum(node) -> Decimal:
    if getattr(node, "sub_questions", None):
        return sum((sq.points for sq in node.sub_questions), Decimal("0"))
    return sum((c.points for c in node.criteria), Decimal("0"))


def _check_point_sums(draft: ExtractRubricResponse) -> List[PedagogicalMistake]:
    out: List[PedagogicalMistake] = []
    for q in draft.questions:
        s = _node_children_sum(q)
        if abs(s - q.total_points) > _EPS:
            out.append(PedagogicalMistake(
                mistake_id=f"pts:{q.question_id}",
                kind=PedagogicalMistakeKind.POINT_SUM_MISMATCH,
                severity=AnnotationSeverity.WARNING, target_id=q.question_id,
                explanation=(f"רכיבי שאלה {q.question_id} מסתכמים ל-{s} אך הניקוד המוצהר הוא "
                             f"{q.total_points}."),
                evidence={"children_sum": str(s), "declared_total": str(q.total_points)},
                suggested_fix=None, requires_teacher_input=True, confidence=1.0))
        for sq in q.all_sub_questions:
            ss = _node_children_sum(sq)
            if abs(ss - sq.points) > _EPS:
                out.append(PedagogicalMistake(
                    mistake_id=f"pts:{q.question_id}.{sq.sub_question_id}",
                    kind=PedagogicalMistakeKind.POINT_SUM_MISMATCH,
                    severity=AnnotationSeverity.WARNING, target_id=sq.sub_question_id,
                    explanation=(f"רכיבי סעיף {sq.sub_question_id} מסתכמים ל-{ss} אך נקודות הסעיף הן "
                                 f"{sq.points}."),
                    evidence={"children_sum": str(ss), "declared": str(sq.points)},
                    suggested_fix=None, requires_teacher_input=True, confidence=1.0))
    # whole-rubric (selection-aware): achievable vs declared total
    ach = compute_achievable_points(draft.questions, draft.selection_groups)
    if abs(ach - draft.total_points) > _EPS:
        out.append(PedagogicalMistake(
            mistake_id="pts:rubric",
            kind=PedagogicalMistakeKind.POINT_SUM_MISMATCH,
            severity=AnnotationSeverity.WARNING, target_id=None,
            explanation=(f"הניקוד הניתן להשגה ({ach}) אינו תואם את סך נקודות המחוון "
                         f"({draft.total_points})."),
            evidence={"achievable": str(ach), "declared_total": str(draft.total_points)},
            suggested_fix=None, requires_teacher_input=True, confidence=1.0))
    return out


def _check_selection_normalization(draft: ExtractRubricResponse) -> List[PedagogicalMistake]:
    out: List[PedagogicalMistake] = []
    pts_by_q = {q.question_id: q.total_points for q in draft.questions}
    for g in draft.selection_groups:
        weights = {qid: pts_by_q.get(qid) for qid in g.of_question_ids}
        distinct = {w for w in weights.values() if w is not None}
        if len(distinct) > 1:
            mx = max(distinct)
            out.append(PedagogicalMistake(
                mistake_id=f"selnorm:{g.group_id}",
                kind=PedagogicalMistakeKind.SELECTION_NORMALIZATION,
                severity=AnnotationSeverity.WARNING, target_id=None,
                explanation=("הבחירה היא {k} מתוך {n} שאלות, אך לשאלות ניקוד שונה ({w}). "
                             "מענה על שאלה בעלת ניקוד נמוך חוסם את הציון. יש להבהיר כיצד מנרמלים."
                             ).format(k=g.choose_k, n=len(g.of_question_ids),
                                      w="/".join(str(weights[q]) for q in g.of_question_ids)),
                evidence={"choose_k": g.choose_k, "weights": {q: str(weights[q]) for q in g.of_question_ids},
                          "max_achievable": str(mx * g.choose_k)},
                suggested_fix=None, requires_teacher_input=True, confidence=1.0))
    return out


# --- declared-vs-extracted structural trigger --------------------------------

# A sub-question marker in the prose: an isolated Hebrew letter followed by '.' or '׳'/"'".
# Tolerant of the rendered-markdown delimiters AND of leading bidi control marks (U+200E/F,
# U+202A-E), which Hebrew DOCX commonly prefix to RTL lines, since we don't pin the format.
_SUBQ_MARKER = re.compile(
    r"(?m)^[\-*>#\s\u200e\u200f\u202a-\u202e\u2066-\u2069]*([" + _HEB + r"])[\.\u05F3']")
_QUESTION_HDR = re.compile(r"שאל[הת]\s*([0-9]+)")


def declared_subquestions_from_prose(rendered_markdown: str) -> Dict[int, List[str]]:
    """Per question NUMBER, the sub-question letters its prose declares (`א.`/`ב.`/`ג.`).

    Robust to the renderer's exact delimiters: it segments on `שאלה N` headers and within
    each segment collects line-initial Hebrew sub-question markers (deduped, in order).
    """
    result: Dict[int, List[str]] = {}
    # split into (question_number, text) segments by question headers
    matches = list(_QUESTION_HDR.finditer(rendered_markdown))
    for i, m in enumerate(matches):
        qnum = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(rendered_markdown)
        seg = rendered_markdown[start:end]
        # accumulate (union) across segments with the same number: a `(המשך שאלה N)`
        # continuation marker produces a second segment that must extend, not replace.
        seen = result.setdefault(qnum, [])
        for mk in _SUBQ_MARKER.finditer(seg):
            letter = mk.group(1)
            if letter not in seen:
                seen.append(letter)
    return {k: v for k, v in result.items() if v}


def _qnum(question_id: str) -> Optional[int]:
    digits = re.sub(r"\D", "", question_id or "")
    return int(digits) if digits else None


def _declared_vs_extracted(draft: ExtractRubricResponse,
                           rendered_markdown: str) -> List[MislabelTrigger]:
    declared = declared_subquestions_from_prose(rendered_markdown)
    triggers: List[MislabelTrigger] = []
    for q in draft.questions:
        qn = _qnum(q.question_id)
        if qn is None or qn not in declared:
            continue
        decl = declared[qn]
        extr = [sq.sub_question_id for sq in q.sub_questions]
        missing = [L for L in decl if L not in extr]
        extra = [L for L in extr if L not in decl]
        if missing or extra:
            triggers.append(MislabelTrigger(
                question_id=q.question_id, declared=decl, extracted=extr,
                missing=missing, extra=extra))
    return triggers


def detect_deterministic(draft: ExtractRubricResponse, rendered_markdown: str) -> TierAResult:
    res = TierAResult()
    res.mistakes += _check_point_sums(draft)
    res.mistakes += _check_selection_normalization(draft)
    res.triggers += _declared_vs_extracted(draft, rendered_markdown)
    return res


# =============================================================================
# TIER B — LLM adjudication of a structural trigger (closed taxonomy, read-only)
# =============================================================================

class SuggestedParams(BaseModel):
    """Closed, typed arg shape for Tier-B suggested operations (B2).

    The previous `Optional[Dict[str, object]]` could never satisfy OpenAI strict
    structured output — a free-form object has no way to declare
    `additionalProperties: false`, so EVERY Tier B call 400'd at transport
    (deterministically; Tier B had never succeeded end-to-end). The taxonomy's only
    fix-bearing operation is reassign_subquestion, whose args are from/to labels.
    `from` is a Python keyword -> field `from_label` with alias "from"
    (populate_by_name lets callers use either). extra="forbid" makes pydantic emit
    additionalProperties:false itself — the schema is strict-valid by construction.
    New operations must extend THIS model (a new arg is a schema change, reviewable),
    never regress to a free dict.
    """
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    from_label: Optional[str] = Field(None, alias="from",
                                      description="Source sub-question label, e.g. 'ב'.")
    to: Optional[str] = Field(None, description="Target sub-question label, e.g. 'ג'.")

    def as_params_dict(self) -> Dict[str, object]:
        """The downstream SuggestedFix.params dict shape ({'from':…,'to':…})."""
        return self.model_dump(by_alias=True, exclude_none=True)


class AdjudicationResult(BaseModel):
    """Structured output contract for the Tier-B adjudicator LLM call."""
    is_mistake: bool = Field(..., description="Is this a GENUINE teacher-induced error (not an innocent anomaly)?")
    kind: Optional[PedagogicalMistakeKind] = Field(None, description="Only a kind from the provided taxonomy.")
    target_id: Optional[str] = Field(None, description="Scope anchor (e.g. the question id).")
    explanation: Optional[str] = Field(None, description="Hebrew, teacher-facing: what is wrong.")
    suggested_operation: Optional[str] = Field(None, description="e.g. 'reassign_subquestion'; null if no fix.")
    suggested_params: Optional[SuggestedParams] = Field(None, description="Operation args, e.g. {'from':'ב','to':'ג'}.")
    suggested_description: Optional[str] = Field(None, description="Hebrew summary of the proposed fix.")
    confidence: float = Field(..., ge=0.0, le=1.0)


class StructuredLLM(Protocol):
    """The seam. Inject whatever the codebase uses (langchain `with_structured_output`,
    the OpenAI client, etc.) wrapped to this shape."""
    def __call__(self, *, system: str, user: str, schema: type) -> BaseModel: ...


_TIER_B_SYSTEM = (
    "אתה מבקר/ת חילוץ מובנה של מחוון בחינה לאיתור טעויות שמקורן במורה. "
    "מקבל/ת: אנומליה מבנית שזוהתה דטרמיניסטית, מפרט תתי-הסעיפים של השאלה, וטקסט המחוון המעובד. "
    "עליך להכריע האם מדובר בטעות פדגוגית אמיתית, ואם כן — מהו התיקון הסביר ביותר.\n"
    "כללים: (1) דווח/י אך ורק על kind מתוך הטקסונומיה הסגורה שסופקה. "
    "(2) היה/י שמרן/ית: אם לאנומליה יש הסבר תמים (למשל הסעיף באמת קיים תחת שם אחר, או הקריטריון "
    "מפנה לפעולה מסעיף אחר באופן לגיטימי) — החזר/י is_mistake=false. "
    "(3) להכרעת שיוך: השווה/י את תוכן הקריטריון (שמות פעולות, תיאור) למפרט תתי-הסעיפים, ובסס/י את "
    "ההצעה על התאמת תוכן, לא על הניסוח בלבד. (4) confidence משקף/ת את חד-משמעיות ההתאמה."
)

# Only these kinds may be returned by the adjudicator (the leash).
_ALLOWED_TIER_B_KINDS = (
    PedagogicalMistakeKind.STRUCTURAL_MISLABEL,
    PedagogicalMistakeKind.ORPHAN_CRITERION,
)


def _scope_spec(draft: ExtractRubricResponse, question_id: str) -> str:
    q = next((q for q in draft.questions if q.question_id == question_id), None)
    if q is None:
        return ""
    lines = [f"שאלה {q.question_id} (סה\"כ {q.total_points}):"]
    for sq in q.sub_questions:
        lines.append(f"  סעיף {sq.sub_question_id} ({sq.points}):")
        for c in sq.all_criteria:
            lines.append(f"    - [{c.points}] {c.description}")
    for c in q.criteria:
        lines.append(f"  - [{c.points}] {c.description}")
    return "\n".join(lines)


def _build_user_prompt(trigger: MislabelTrigger, draft: ExtractRubricResponse,
                       rendered_markdown: str) -> str:
    taxonomy = ", ".join(k.value for k in _ALLOWED_TIER_B_KINDS)
    return (
        f"טקסונומיה מותרת (kind): {taxonomy}\n\n"
        f"אנומליה מבנית (שאלה {trigger.question_id}): "
        f"ניסוח השאלה מצהיר על סעיפים {trigger.declared}, אך חולצו {trigger.extracted}. "
        f"חסרים: {trigger.missing}; עודפים: {trigger.extra}.\n\n"
        f"מפרט תתי-הסעיפים שחולצו:\n{_scope_spec(draft, trigger.question_id)}\n\n"
        f"טקסט המחוון המעובד (לאימות תוכן):\n{rendered_markdown}\n\n"
        "האם זו טעות פדגוגית אמיתית? אם כן — באיזה סעיף אמור הקריטריון להופיע, ומהו התיקון?"
    )


def adjudicate(trigger: MislabelTrigger, draft: ExtractRubricResponse,
               rendered_markdown: str, *, llm: StructuredLLM) -> Optional[PedagogicalMistake]:
    res = llm(system=_TIER_B_SYSTEM,
              user=_build_user_prompt(trigger, draft, rendered_markdown),
              schema=AdjudicationResult)
    assert isinstance(res, AdjudicationResult)
    if not res.is_mistake or res.kind is None:
        return None
    if res.kind not in _ALLOWED_TIER_B_KINDS:   # enforce the leash even if the model strays
        return None
    fix = None
    if res.suggested_operation:
        fix = SuggestedFix(operation=res.suggested_operation,
                           description=res.suggested_description or "",
                           params=(res.suggested_params.as_params_dict()
                                   if res.suggested_params else {}))
    return PedagogicalMistake(
        mistake_id=f"adj:{trigger.question_id}:{res.kind.value}",
        kind=res.kind, severity=AnnotationSeverity.WARNING,
        target_id=res.target_id or trigger.question_id,
        explanation=res.explanation or "",
        evidence={"declared": trigger.declared, "extracted": trigger.extracted,
                  "missing": trigger.missing, "extra": trigger.extra},
        suggested_fix=fix,
        requires_teacher_input=(fix is None),
        confidence=res.confidence)


# =============================================================================
# Orchestrator — the single entry point pipeline.extract_rubric_from_docx calls
# =============================================================================

def detect_pedagogical_mistakes(draft: ExtractRubricResponse, rendered_markdown: str,
                                *, llm: Optional[StructuredLLM] = None,
                                warnings_sink: Optional[List[str]] = None) -> List[PedagogicalMistake]:
    """Run Tier A always; Tier B only on triggers and only if an LLM is provided.

    Returns the list to assign to draft.pedagogical_mistakes. Pure w.r.t. the Draft
    (never mutates it). With llm=None, returns Tier-A mistakes only (degrades safely).

    warnings_sink: optional list that receives a message per swallowed Tier-B failure
    (B4). Per-trigger isolation is correct resilience but was an OBSERVABILITY hole:
    the deterministic Tier-B schema-transport 400 lived only in stdout logs for the
    detector's entire life — a swallowed failure must surface in the caller's
    warnings so it reaches ExtractionResult.warnings / the eval artifacts.
    """
    a = detect_deterministic(draft, rendered_markdown)
    mistakes = list(a.mistakes)
    if llm is not None:
        for trig in a.triggers:
            # Per-trigger isolation (the detector analog of the grader's per-scope
            # degrade): a Tier-B failure — transport error, adjudicator construction
            # failure, schema violation — skips THIS trigger and keeps everything
            # already found. Tier-A results are deterministic facts; an LLM outage
            # must never throw them away.
            try:
                m = adjudicate(trig, draft, rendered_markdown, llm=llm)
            except Exception as e:
                msg = (f"Tier B adjudication failed for trigger on {trig.question_id} "
                       f"(missing={trig.missing}, extra={trig.extra}): {e} — "
                       f"keeping Tier A results, skipping this trigger")
                logger.warning(msg)
                if warnings_sink is not None:
                    warnings_sink.append(msg)
                continue
            if m is not None:
                mistakes.append(m)
    return mistakes