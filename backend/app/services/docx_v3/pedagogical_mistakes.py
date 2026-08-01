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

  TIER B — ONE structured LLM call PER ANOMALOUS QUESTION (D6), read-only, scoped
    to the closed PedagogicalMistakeKind taxonomy. It receives every anomaly the
    question exhibits at once — structural trigger + point-sum mismatches — names
    the root cause, proposes the fix as an ordered list of EditSteps (the general
    edit wire), and marks which anomalies that one fix resolves (explained_by, D3).
    Detection of point-sum facts stays Tier A's; Tier B only chooses fixes. No
    agent, no tool loop, no mutation of the Draft. When Tier B cannot run, every
    point mismatch keeps its deterministic adjust-declared fallback fix.

The Draft stays FAITHFUL; mistakes live only here; fixes apply only at Contract time on
teacher approval. This pass is read-only and structurally cannot violate that.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable, Dict, List, Literal, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field

from ...schemas.ontology_types import (
    AnnotationSeverity, EditStep, ExtractRubricResponse, PedagogicalMistake,
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


def _walk_sub_questions(q: Question):
    """Yield (FULL PATH, sub-question) depth-first — `q1.א`, `q1.א.1`, `q1.ב`, …

    The full path IS the scope-anchor vocabulary every other surface already
    speaks: the client validator's `target_id`, the compiler's INV-2 target, the
    mirror's `data-scope-id`. Emitting a BARE `sub_question_id` here (the old
    behaviour) made a pedagogical finding unpairable with its own live blocker —
    and ambiguous besides, since every question has a 'א'. `Question.all_sub_questions`
    cannot be used for this: it flattens the tree and drops the parent chain.
    """
    def walk(nodes, prefix: str):
        for sq in nodes or []:
            path = f"{prefix}.{sq.sub_question_id}"
            yield path, sq
            yield from walk(getattr(sq, "sub_questions", None), path)
    yield from walk(getattr(q, "sub_questions", None), q.question_id)


def _fmt_points(d: Decimal) -> str:
    """Teacher-facing number: no exponent, no trailing zeros ('44.0' → '44')."""
    s = format(d, "f")
    return s.rstrip("0").rstrip(".") if "." in s else s


def _adjust_points_fix(new_value: Decimal, current: Decimal, scope: str) -> SuggestedFix:
    """The DETERMINISTIC fallback correction for a point-sum mismatch: set the
    DECLARED value to the sum the node's own children already state.

    It INVENTS NOTHING — `new_value` is the teacher's own arithmetic read back to
    her (§2 FC), which is exactly why it is the only fix Tier A may emit on its
    own: when Tier B is unavailable (budget/disabled), a proposal that fabricates
    no number is the only safe degrade. When Tier B runs, it may REPLACE this fix
    with a smarter one (reassign / child edits) per the decision ladder.

    `requires_teacher_input` stays True on the mistake it rides on: that flag
    means "never apply without the teacher", and a one-click PROPOSAL she must
    click is that flag implemented, not overridden.
    """
    return SuggestedFix(
        operation="adjust_points",
        description=(f"עדכני את סך נקודות המחוון ל-{_fmt_points(new_value)}" if scope == "rubric"
                     else f"עדכני את הניקוד המוצהר ל-{_fmt_points(new_value)}"),
        steps=[EditStep(op="set_points", scope=scope,
                        value=str(new_value), current_value=str(current))],
    )


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
                suggested_fix=_adjust_points_fix(s, q.total_points, q.question_id),
                requires_teacher_input=True, confidence=1.0))
        for path, sq in _walk_sub_questions(q):
            ss = _node_children_sum(sq)
            if abs(ss - sq.points) > _EPS:
                out.append(PedagogicalMistake(
                    mistake_id=f"pts:{path}",
                    kind=PedagogicalMistakeKind.POINT_SUM_MISMATCH,
                    severity=AnnotationSeverity.WARNING, target_id=path,
                    explanation=(f"רכיבי סעיף {sq.sub_question_id} מסתכמים ל-{ss} אך נקודות הסעיף הן "
                                 f"{sq.points}."),
                    evidence={"children_sum": str(ss), "declared": str(sq.points)},
                    suggested_fix=_adjust_points_fix(ss, sq.points, path),
                    requires_teacher_input=True, confidence=1.0))
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
            suggested_fix=_adjust_points_fix(ach, draft.total_points, "rubric"),
            requires_teacher_input=True, confidence=1.0))
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
                # DELIBERATELY no suggested_fix — unlike a point-sum mismatch, there is
                # no correction to propose here. The normalization INTENT is unknowable
                # (does she want the weights equalised? the low-weight question dropped?
                # a scaling rule?), and the model's own contract says so:
                # requires_teacher_input exists for "no auto-fix exists (e.g.
                # normalization intent is unknowable)". Emitting an 'adjust_points' fix
                # would fabricate a number the teacher never wrote — the one thing
                # Faithful Capture forbids. This stays card variant 3 (info-only).
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
# TIER B — LLM adjudication, ONE batched call per anomalous question (D6).
#
# Tier A stays the only DETECTOR of point-sum facts (arithmetic is not a matter
# of opinion). Tier B decides the FIX: given every anomaly a question exhibits —
# structural trigger + point-sum mismatches together — it names the root cause,
# proposes one fix as an ordered list of EditSteps (the general edit wire), and
# marks which anomalies that single fix resolves (D3 subordination). Batching
# per question is what makes root-cause reasoning possible at all: the hobby q2
# mislabel explains BOTH of that question's point mismatches, and an adjudicator
# shown one anomaly at a time could never see that.
# =============================================================================

class EditStepOut(BaseModel):
    """Strict transport twin of ontology EditStep (B2: extra='forbid' everywhere,
    Literal op — the schema itself is the leash; the model cannot emit an op we
    did not teach it)."""
    model_config = ConfigDict(extra="forbid")
    op: Literal["set_points", "move_criterion", "move_text"]
    scope: str = Field(..., description="Dotted scope path ('q2', 'q2.ב') or 'rubric'.")
    criterion_index: Optional[int] = Field(None, description="0-based [i] from the numbered spec.")
    to_scope: Optional[str] = Field(None, description="Destination scope; created if absent.")
    text: Optional[str] = Field(None, description="Verbatim substring to move (move_text).")
    value: Optional[str] = Field(None, description="New points, decimal string (set_points).")
    current_value: Optional[str] = Field(None, description="The current value (set_points).")


class FixProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(..., description="Hebrew imperative one-liner — the button label.")
    steps: List[EditStepOut] = Field(..., description="Ordered edits, applied atomically.")


class AdjudicatedFinding(BaseModel):
    """One decision: either a NEW root-cause finding (structural_mislabel /
    orphan_criterion) or the chosen fix for a listed point-sum anomaly."""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["structural_mislabel", "orphan_criterion", "point_sum_mismatch"]
    target_id: str = Field(..., description="The anomaly's target exactly as listed; for a new structural finding, the question id.")
    explanation: str = Field(..., description="Standalone Hebrew display copy for the teacher (per the output rules).")
    fix: Optional[FixProposal] = Field(None, description="The proposed correction; null when none is safe to propose.")
    resolves: List[str] = Field(default_factory=list,
                                description="Targets of OTHER listed anomalies this finding's single fix settles.")
    confidence: float = Field(..., ge=0.0, le=1.0)


class QuestionAdjudication(BaseModel):
    """Structured output contract for the per-question Tier-B call."""
    model_config = ConfigDict(extra="forbid")
    findings: List[AdjudicatedFinding] = Field(default_factory=list)


class StructuredLLM(Protocol):
    """The seam. Inject whatever the codebase uses (langchain `with_structured_output`,
    the OpenAI client, etc.) wrapped to this shape."""
    def __call__(self, *, system: str, user: str, schema: type) -> BaseModel: ...


_TIER_B_SYSTEM = """את מבקרת האיכות של חילוץ מחווני בחינה ב-Vivi, ויועצת התיקונים שלה.

הקשר: המחוון חולץ בנאמנות מלאה למסמך המקור — כולל טעויות של המורה. את מקבלת,
עבור שאלה אחת: מפרט ממוספר (עם סכומים והפרשים מחושבים), את טקסטי הסעיפים,
ואת רשימת האנומליות שזוהו דטרמיניסטית. תפקידך להכריע מהי טעות-השורש ולהציע את
התיקון הסביר ביותר. ההצעה מוגשת תמיד למורה לאישור; היא לעולם אינה מוחלת
אוטומטית.

עקרונות יסוד:
1. שמרנות: אנומליה מבנית שיש לה הסבר תמים (הסעיף קיים תחת שם אחר; הקריטריון
   מפנה כדין לפעולה מסעיף אחר) — אינה ממצא; אל תחזירי עבורה דבר. אי-התאמת
   נקודות היא עובדה חשבונית — היא תמיד ממצא, והשאלה היחידה היא מהו התיקון.
2. שקיפות: כל ערך מוצע נגזר באופן גלוי מהמסמך — ערך שהמורה כתבה, או חשבון
   פשוט עליו — ומנומק בהסבר.
3. תיקון-שורש אחד: טעות אחת מטילה כמה צללים — אי-התאמות סכום בכמה רמות, סעיף
   חסר. זהי את טעות-השורש, הציעי עבורה תיקון אחד שמיישב את כולם, וסמני
   ב-resolves את שאר האנומליות שהוא מיישב — אל תחזירי להן finding נפרד ואל
   תציעי להן תיקון-סכום מקומי.

סדר ההכרעה לאי-התאמת נקודות (עברי לפי הסדר; עצרי בכלל הראשון שמתקיים):
א. שיוך שגוי: השתמשי בהפרש (delta) המחושב שסופק. אם קיים קריטריון (או קבוצה)
   שנקודותיו שוות בדיוק ל-delta ותוכנו (שמות פעולות, מושגים, ניסוח) תואם סעיף
   אחר — זהו תיקון-השורש: העבירי אותו לסעיפו הנכון. ודאי שההעברה מיישבת גם את
   סכום השאלה כולה. אם סעיף היעד לא חולץ כלל — ההעברה תיצור אותו, והעבירי אליו
   ב-move_text גם את קטע הטקסט השייך לו מתוך הסעיף שבו נלכד בטעות.
ב. טעות-סופר בערך בודד: אם שינוי של ערך אחד ברכיב אחד, לערך עגול וסביר, מיישב
   את החשבון — הציעי את השינוי הזה בלבד.
ג. ברירת המחדל — המוצהר הוא הסמכות: התאימי את נקודות הרכיבים אל הסך המוצהר.
   אל תפזרי את ההפרש על כל הרכיבים; שני רכיב אחד או שניים בלבד, בחרי את אלה
   שההתאמה בהם סבירה ביותר פדגוגית, ושמרי על ערכים עגולים — שלמים או חצאים
   בלבד.
ד. עקיפה מנומקת: אם הראיות מצביעות בבירור על טעות בכותרת דווקא (רכיבים עגולים
   ועקביים שמסתכמים יפה; ערך מוצהר חריג) — הציעי לעדכן את הערך המוצהר, ונמקי.

פעולות התיקון (steps — רשימה סדורה, מוחלת כיחידה אחת):
* set_points — קביעת ניקוד: scope (נתיב הסעיף/השאלה, "rubric" לסך המחוון, או
  קריטריון בעזרת criterion_index), value (מחרוזת עשרונית), current_value.
* move_criterion — העברת קריטריון: scope + criterion_index של המקור, to_scope
  היעד.
* move_text — העברת קטע טקסט: scope המקור, to_scope היעד, text — ציטוט מדויק,
  מילה במילה, מתוך טקסט הסעיף שסופק במפרט. לעולם אל תנסחי מחדש ואל תצטטי
  מהמסמך המעובד — רק מטקסט הסעיף.
יעד (to_scope) שאינו קיים ייווצר אוטומטית — כך יוצרים סעיף חסר. סעיף שנוצר כך
מקבל אוטומטית ניקוד השווה לסכום הקריטריונים שהועברו אליו; הוסיפי set_points
עבורו רק אם הניקוד הנכון שונה מסכום זה.
criterion_index מפנה לאינדקסים [i] שבמפרט הממוספר.

confidence: ‎0.9 ומעלה — התאמה חד-משמעית (delta מדויק + התאמת תוכן);
‎0.7–0.9 — התאמה טובה עם אי-ודאות קלה; מתחת ל-0.7 — עדיין הציעי את התיקון
הטוב ביותר, ונסחי את ההסבר בזהירות בהתאם.

כללי פלט (מחייבים):
- explanation: טקסט תצוגה עצמאי המופנה למורה, בלשון נקבה. לעולם לא תשובה
  לשאלה — אל תפתחי ב"כן"/"לא" ואל תתארי את תהליך הבדיקה. מבנה: מה לא מסתדר
  במסמך → מהי טעות-השורש → מה יעשה התיקון.
- description (של fix): כותרת כפתור — משפט ציווי אחד, קצר וקונקרטי, למשל:
  "העבירי את רכיבי PrintLowRatingChannel לסעיף ג'".
- kind: אך ורק structural_mislabel / orphan_criterion / point_sum_mismatch.
- target_id: בדיוק ה-target של האנומליה מהרשימה (לממצא-שורש מבני: מזהה
  השאלה)."""


@dataclass
class QuestionAnomalies:
    """Everything anomalous about ONE question — the unit of a Tier-B call."""
    question_id: str
    trigger: Optional[MislabelTrigger] = None
    point_mistakes: List[PedagogicalMistake] = field(default_factory=list)


def _bundle_anomalies(draft: ExtractRubricResponse, tier_a: TierAResult) -> List[QuestionAnomalies]:
    """Group Tier-A anomalies by root question, in draft order. The rubric-level
    mismatch (target None) stays deterministic (D4), and selection_normalization
    is deliberately never adjudicated (D8: intent unknowable)."""
    by_q: Dict[str, QuestionAnomalies] = {}
    for m in tier_a.mistakes:
        if m.kind is not PedagogicalMistakeKind.POINT_SUM_MISMATCH or not m.target_id:
            continue
        qid = m.target_id.split(".")[0]
        by_q.setdefault(qid, QuestionAnomalies(question_id=qid)).point_mistakes.append(m)
    for t in tier_a.triggers:
        by_q.setdefault(t.question_id, QuestionAnomalies(question_id=t.question_id)).trigger = t
    order = {q.question_id: i for i, q in enumerate(draft.questions)}
    return sorted(by_q.values(), key=lambda b: order.get(b.question_id, len(order)))


def _question_spec(draft: ExtractRubricResponse, question_id: str) -> str:
    """The numbered spec Tier B reasons over: per node — declared vs children-sum
    vs delta (precomputed; the model corroborates arithmetic, never performs it),
    the node's verbatim text (the ONLY legal source for move_text quotes), and its
    criteria enumerated with the [i] indices the EditStep wire joins on."""
    q = next((q for q in draft.questions if q.question_id == question_id), None)
    if q is None:
        return ""
    lines: List[str] = []

    def node_line(label: str, declared: Decimal, children_sum: Decimal) -> str:
        delta = abs(declared - children_sum)
        return (f"{label} — ניקוד מוצהר: {_fmt_points(declared)}; "
                f"סכום רכיביו: {_fmt_points(children_sum)}; הפרש: {_fmt_points(delta)}")

    def emit_criteria(node) -> None:
        for i, c in enumerate(node.criteria):
            lines.append(f"  [{i}] ({_fmt_points(c.points)} נק') {c.description}")

    lines.append(node_line(f"שאלה {q.question_id}", q.total_points, _node_children_sum(q)))
    if q.question_text:
        lines.append(f"טקסט השאלה:\n<<<\n{q.question_text}\n>>>")
    if q.criteria:
        lines.append("קריטריונים ישירים:")
        emit_criteria(q)
    for path, sq in _walk_sub_questions(q):
        lines.append("")
        lines.append(node_line(f"סעיף {path}", sq.points, _node_children_sum(sq)))
        if sq.text:
            lines.append(f"טקסט הסעיף (ציטוטי move_text — מכאן בלבד, מילה במילה):\n<<<\n{sq.text}\n>>>")
        if sq.criteria:
            emit_criteria(sq)
    return "\n".join(lines)


def _anomaly_block(bundle: QuestionAnomalies) -> str:
    lines = ["האנומליות להכרעה:"]
    for m in bundle.point_mistakes:
        s = m.evidence.get("children_sum")
        d = m.evidence.get("declared") or m.evidence.get("declared_total")
        lines.append(f"- target={m.target_id} — אי-התאמת נקודות: סכום הרכיבים {s} ≠ מוצהר {d}")
    if bundle.trigger:
        t = bundle.trigger
        lines.append(f"- target={t.question_id} — אנומליה מבנית: ניסוח השאלה מצהיר סעיפים "
                     f"{t.declared}, אך חולצו {t.extracted} (חסרים: {t.missing}; עודפים: {t.extra})")
    return "\n".join(lines)


def _build_question_prompt(bundle: QuestionAnomalies, draft: ExtractRubricResponse,
                           rendered_markdown: str) -> str:
    return (
        f"{_question_spec(draft, bundle.question_id)}\n\n"
        f"{_anomaly_block(bundle)}\n\n"
        f"טקסט המסמך המלא (הקשר לאימות תוכן בלבד; ציטוטי move_text נלקחים אך ורק "
        f"מטקסטי הסעיפים שבמפרט למעלה):\n{rendered_markdown}\n\n"
        "משימה: הכריעי לפי סדר ההכרעה שבהנחיות והחזירי findings לפי כללי הפלט. "
        "לכל אנומליה שהתיקון שלה נגזר מטעות-שורש אחרת — אל תחזירי finding נפרד; "
        "כללי את ה-target שלה ב-resolves של ממצא-השורש."
    )


def adjudicate_question(bundle: QuestionAnomalies, draft: ExtractRubricResponse,
                        rendered_markdown: str, *, llm: StructuredLLM) -> QuestionAdjudication:
    res = llm(system=_TIER_B_SYSTEM,
              user=_build_question_prompt(bundle, draft, rendered_markdown),
              schema=QuestionAdjudication)
    assert isinstance(res, QuestionAdjudication)
    return res


_ROOT_KINDS = {
    "structural_mislabel": PedagogicalMistakeKind.STRUCTURAL_MISLABEL,
    "orphan_criterion": PedagogicalMistakeKind.ORPHAN_CRITERION,
}


def _fix_from_proposal(p: Optional[FixProposal]) -> Optional[SuggestedFix]:
    if p is None or not p.steps:
        return None
    steps = [EditStep(**s.model_dump()) for s in p.steps]
    # The operation label is analytics metadata; the client applies `steps` and
    # never dispatches on it. A move-bearing plan is a reassignment; pure
    # set_points is a point adjustment.
    operation = ("reassign_subquestion" if any(s.op != "set_points" for s in steps)
                 else "adjust_points")
    return SuggestedFix(operation=operation, description=p.description, steps=steps)


def _merge_adjudication(mistakes: List[PedagogicalMistake], bundle: QuestionAnomalies,
                        adj: QuestionAdjudication) -> None:
    """Fold Tier-B decisions into the Tier-A result set, deterministically.

    The leash, restated for the batched contract: Tier B may APPEND only root-cause
    kinds; for point_sum it may only ATTACH a fix to a mismatch Tier A already
    proved (an unknown target is ignored, never invented). Subordinated shadows
    keep their facts but lose their local fix — the root's single fix is the one
    answer, and offering a competing local correction would be actively wrong
    (hobby: "scale ב's criteria" next to "move the mislabeled criterion")."""
    by_target = {m.target_id: m for m in bundle.point_mistakes}
    for f in adj.findings:
        if f.kind in _ROOT_KINDS:
            fix = _fix_from_proposal(f.fix)
            root = PedagogicalMistake(
                mistake_id=f"adj:{bundle.question_id}:{f.kind}",
                kind=_ROOT_KINDS[f.kind],
                severity=AnnotationSeverity.WARNING,
                target_id=f.target_id or bundle.question_id,
                explanation=f.explanation,
                evidence=({"declared": bundle.trigger.declared, "extracted": bundle.trigger.extracted,
                           "missing": bundle.trigger.missing, "extra": bundle.trigger.extra}
                          if bundle.trigger else {}),
                suggested_fix=fix,
                requires_teacher_input=(fix is None),
                confidence=f.confidence)
            mistakes.append(root)
            for t in f.resolves:
                shadow = by_target.get(t)
                if shadow is None:
                    continue
                shadow.explained_by = root.mistake_id
                shadow.suggested_fix = None
        elif f.kind == "point_sum_mismatch":
            m = by_target.get(f.target_id)
            if m is None:
                continue
            fix = _fix_from_proposal(f.fix)
            if fix is not None:
                # The smarter fix replaces the deterministic fallback; detection
                # confidence stays 1.0 — the mismatch is arithmetic fact, only
                # the fix was adjudicated.
                m.suggested_fix = fix
                if f.explanation:
                    m.explanation = f.explanation


# =============================================================================
# Orchestrator — the single entry point pipeline.extract_rubric_from_docx calls
# =============================================================================

def detect_pedagogical_mistakes(draft: ExtractRubricResponse, rendered_markdown: str,
                                *, llm: Optional[StructuredLLM] = None,
                                warnings_sink: Optional[List[str]] = None) -> List[PedagogicalMistake]:
    """Run Tier A always; Tier B once per anomalous question when an LLM is provided.

    Returns the list to assign to draft.pedagogical_mistakes. Pure w.r.t. the Draft
    (never mutates it). With llm=None, returns Tier-A mistakes only — every
    point-sum mismatch still carries its deterministic adjust-declared fallback
    fix, so the product degrades to the pre-D6 behaviour, never to no-fix.

    warnings_sink: optional list that receives a message per swallowed Tier-B failure
    (B4). Per-question isolation is correct resilience but was an OBSERVABILITY hole:
    the deterministic Tier-B schema-transport 400 lived only in stdout logs for the
    detector's entire life — a swallowed failure must surface in the caller's
    warnings so it reaches ExtractionResult.warnings / the eval artifacts.
    """
    a = detect_deterministic(draft, rendered_markdown)
    mistakes = list(a.mistakes)
    if llm is not None:
        for bundle in _bundle_anomalies(draft, a):
            # Per-question isolation (the detector analog of the grader's per-scope
            # degrade): a Tier-B failure — transport error, adjudicator construction
            # failure, schema violation — skips THIS question's adjudication and
            # keeps everything already found. Tier-A results are deterministic
            # facts; an LLM outage must never throw them away.
            try:
                adj = adjudicate_question(bundle, draft, rendered_markdown, llm=llm)
            except Exception as e:
                msg = (f"Tier B adjudication failed for {bundle.question_id} "
                       f"({len(bundle.point_mistakes)} point anomaly(ies)"
                       f"{', structural trigger' if bundle.trigger else ''}): {e} — "
                       f"keeping Tier A results for this question")
                logger.warning(msg)
                if warnings_sink is not None:
                    warnings_sink.append(msg)
                continue
            _merge_adjudication(mistakes, bundle, adj)
    return mistakes