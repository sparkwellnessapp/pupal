"""
GT authoring tool. Extracts criteria text/points programmatically from the מחוון
tables (exact Hebrew, no transcription error) and applies an EXPLICIT per-exam
structure (sub-questions, nesting, selection, totals) that I author by reading.

This is the artifact that produced benchmarks/*.json. Re-runnable. Every built GT
is validated: type-valid, INV-PS sums reported, achievable == declared total (or a
rubric_mismatch annotation is attached for a faithful teacher error).

NOTE: criterion descriptions strip a leading 'סעיף X [בתוך Y]:' tag (used only to
group the criterion under its sub-question); the remainder is the criterion text.
"""
from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from typing import List, Optional, Tuple

from docx import Document

from app.schemas.ontology_types import (
    Annotation, AnnotationSeverity, Criterion, ExtractRubricResponse,
    PedagogicalMistake, PedagogicalMistakeKind, Question, SelectionGroup,
    SubCriterion, SubQuestion, SuggestedFix,
)

FIX = Path(__file__).resolve().parent / "fixtures"
BENCH = Path(__file__).resolve().parent / "benchmarks"
_HEB_LETTERS = "אבגדהוזחט"


def D(x) -> Decimal:
    return Decimal(str(x))


def read_tables(docx_name: str):
    doc = Document(str(FIX / docx_name))
    out = []
    for t in doc.tables:
        rows = [[c.text.strip() for c in r.cells] for r in t.rows]
        out.append(rows)
    return out


def parse_points(s: str) -> Optional[Decimal]:
    """Extract a point value. Handles 'ערך חדש N' (revision -> take N), '2 נק'', '3.75'."""
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    m = re.search(r"ערך\s*חדש\s*([0-9]+(?:\.[0-9]+)?)", s)  # point revision -> new value
    if m:
        return D(m.group(1))
    nums = re.findall(r"[0-9]+(?:\.[0-9]+)?", s)
    if not nums:
        return None
    return D(nums[0])


def strip_sahuf(desc: str) -> Tuple[Optional[str], str]:
    """('א', 'remainder') if desc begins with a 'סעיף X[ בתוך Y]:' tag, else (None, desc)."""
    m = re.match(r"\s*סעיף\s*([" + _HEB_LETTERS + r"])['׳]?\s*(?:בתוך[^:]*)?:?\s*(.*)", desc, re.S)
    if m:
        letter, rest = m.group(1), m.group(2).strip()
        return letter, (rest if rest else desc.strip())
    return None, desc.strip()


def is_skip_row(desc: str, pts: Optional[Decimal]) -> bool:
    d = (desc or "").strip()
    if not d:
        return True
    if re.match(r"^\s*סה[\"״']כ", d):   # PURE total rows only; inline '(סה"כ N)' notes are kept
        return True
    if pts is None:                     # section-header rows with no points
        return True
    if d in ("רכיב", "רכיב הערכה", "ניקוד", "נק'", "תיאור"):
        return True
    return False


def crit(desc: str, pts: Decimal, idx: int, qn: str, sq: str = "", k: int = 0) -> Criterion:
    cid = f"{qn}{('.' + sq) if sq else ''}.c{k}"
    return Criterion(criterion_id=cid, index=idx, description=desc, points=pts)


def validate(r: ExtractRubricResponse, name: str):
    """Type-valid (already, since constructed), plus INV-PS + achievable checks."""
    issues = []
    def node_sum(node):
        if getattr(node, "sub_questions", None):
            return sum((sq.points for sq in node.sub_questions), Decimal("0"))
        return sum((c.points for c in node.criteria), Decimal("0"))
    for q in r.questions:
        s = node_sum(q)
        if abs(s - q.total_points) > Decimal("0.001"):
            issues.append(f"{q.question_id}: children {s} != total {q.total_points}")
        for sq in q.all_sub_questions:
            ss = node_sum(sq)
            if abs(ss - sq.points) > Decimal("0.001"):
                issues.append(f"{q.question_id}.{sq.sub_question_id}: children {ss} != {sq.points}")
    ach = r.achievable_points
    if abs(ach - r.total_points) > Decimal("0.001"):
        issues.append(f"achievable {ach} != total_points {r.total_points}")
    print(f"\n=== {name} === questions={len(r.questions)} total={r.total_points} "
          f"achievable={ach} sel={[ (g.choose_k, g.of_question_ids) for g in r.selection_groups]}")
    print(f"    criteria={r.num_criteria} sub_questions={r.num_sub_questions}")
    if issues:
        print("    INV/ACHIEVABLE ISSUES (expected only where a faithful rubric_mismatch is attached):")
        for i in issues:
            print("      -", i)
    else:
        print("    sums OK (INV-PS holds, achievable == total)")
    return issues


def write(r: ExtractRubricResponse, name: str):
    BENCH.mkdir(exist_ok=True)
    (BENCH / f"{name}.json").write_text(r.model_dump_json(indent=2), encoding="utf-8")


# =============================================================================
# FILE 4 — hobby_tvshow (canonical; answer-all; σעיף-tagged single table/question)
# =============================================================================
def build_hobby_tvshow():
    name = "hobby_tvshow"
    tables = read_tables(name + ".docx")
    # table indices: T2 = Q1 מחוון (20 rows), T4 = Q2 מחוון (13 rows). desc=col0, pts=col1.
    def crits_by_sahuf(rows, qn):
        groups: dict = {}
        for row in rows[1:]:
            desc_raw, pts_raw = row[0], row[1]
            pts = parse_points(pts_raw)
            if is_skip_row(desc_raw, pts):
                continue
            letter, desc = strip_sahuf(desc_raw)
            letter = letter or "?"
            groups.setdefault(letter, []).append((desc, pts))
        return groups

    q1g = crits_by_sahuf(tables[1], "q1")   # T2
    q2g = crits_by_sahuf(tables[3], "q2")   # T4

    def mk_subqs(groups, qn):
        sqs = []
        for i, letter in enumerate(sorted(groups, key=lambda L: _HEB_LETTERS.index(L) if L in _HEB_LETTERS else 99)):
            items = groups[letter]
            cs = [crit(d, p, k, qn, letter, k) for k, (d, p) in enumerate(items)]
            pts = sum((c.points for c in cs), Decimal("0"))
            sqs.append(SubQuestion(sub_question_id=letter, index=i, points=pts, criteria=cs,
                                   example_solution=None))  # solutions are images -> null
        return sqs

    q1 = Question(question_id="q1", total_points=D(40), sub_questions=mk_subqs(q1g, "q1"))
    q2 = Question(question_id="q2", total_points=D(60), sub_questions=mk_subqs(q2g, "q2"))
    r = ExtractRubricResponse(rubric_id="hobby_tvshow", rubric_name="hobby_tvshow",
                              subject="computer_science", programming_language="csharp",
                              total_points=D(100), questions=[q1, q2], selection_groups=[])
    # Teacher-induced rubric error: PrintLowRatingChannel is tagged 'סעיף ב' but its content is the
    # ג operation. The Draft stays FAITHFUL (it sits under ב); the detector records the mislabel + a
    # suggested reassignment for the teacher to approve in RubricEditor.
    r.pedagogical_mistakes.append(PedagogicalMistake(
        mistake_id="hobby_q2_mislabel", kind=PedagogicalMistakeKind.STRUCTURAL_MISLABEL,
        severity=AnnotationSeverity.WARNING, target_id="q2",
        explanation=("במחוון, רכיב הפעולה PrintLowRatingChannel מתויג כ'סעיף ב', אך לפי ניסוח השאלה "
                     "מדובר בפעולת סעיף ג'. יש להעביר את הרכיב לסעיף ג'."),
        evidence={"operation": "PrintLowRatingChannel", "tagged_as": "ב", "belongs_to": "ג", "points": 16},
        suggested_fix=SuggestedFix(operation="reassign_subquestion",
            description="העברת רכיב PrintLowRatingChannel מסעיף ב' לסעיף ג'.",
            params={"criterion_contains": "PrintLowRatingChannel", "from": "ב", "to": "ג"}),
        requires_teacher_input=False, confidence=0.9))
    validate(r, name)
    # show the grouped structure for review
    for q in r.questions:
        for sq in q.sub_questions:
            print(f"    {q.question_id}.{sq.sub_question_id} ({sq.points}) — {len(sq.criteria)} criteria")
            for c in sq.criteria:
                print(f"        [{c.points}] {c.description[:70]}")
    return r, name



# generic helpers for explicit-structure exams ------------------------------
def extract_rows(table, desc_col, pts_col, drop_zero=True):
    """Yield (desc, points) from a table, skipping headers/totals/blank and (optionally) 0-pt rows."""
    out = []
    for row in table:
        if max(desc_col, pts_col) >= len(row):
            continue
        desc_raw, pts = row[desc_col], parse_points(row[pts_col])
        if is_skip_row(desc_raw, pts):
            continue
        if drop_zero and pts == Decimal("0"):
            continue  # schema forbids 0-pt criteria; these are non-scoring header items
        out.append((desc_raw.strip(), pts))
    return out


def mk_leaf_subq(letter, idx, items, qn):
    cs = [crit(d, p, k, qn, letter, k) for k, (d, p) in enumerate(items)]
    pts = sum((c.points for c in cs), Decimal("0"))
    return SubQuestion(sub_question_id=letter, index=idx, points=pts, criteria=cs, example_solution=None)


# =============================================================================
# FILE 5 — employee_course_select1 (SELECTION: choose 1 of 3, non-uniform 15/50/35)
# =============================================================================
def build_employee_course_select1():
    name = "employee_course_select1"
    T = read_tables(name + ".docx")
    # T1 Q1 (8r x 3: %,pts,desc), T2 Q2 (9r), T3 Q3 (8r). desc=col2, pts=col1.
    q1_items = extract_rows(T[0], desc_col=2, pts_col=1)   # 6 criteria, no sub-q
    q2_items = extract_rows(T[1], desc_col=2, pts_col=1)   # 7 rows -> sub-q א..ז (1 crit each)
    q3_items = extract_rows(T[2], desc_col=2, pts_col=1)   # 5 rows -> sub-q א..ה (1 crit each)

    q1 = Question(question_id="q1", total_points=D(15),
                  criteria=[crit(d, p, k, "q1", "", k) for k, (d, p) in enumerate(q1_items)])
    q2 = Question(question_id="q2", total_points=D(50),
                  sub_questions=[mk_leaf_subq(_HEB_LETTERS[i], i, [it], "q2") for i, it in enumerate(q2_items)])
    q3 = Question(question_id="q3", total_points=D(35),
                  sub_questions=[mk_leaf_subq(_HEB_LETTERS[i], i, [it], "q3") for i, it in enumerate(q3_items)])
    # choose 1 of 3, non-uniform weights -> achievable = max = 50. total_points := achievable.
    sel = [SelectionGroup(group_id="sg0", choose_k=1, of_question_ids=["q1", "q2", "q3"],
                          label="ענו על שאלה אחת בלבד")]
    r = ExtractRubricResponse(rubric_id=name, rubric_name=name, subject="computer_science",
                              programming_language="csharp", total_points=D(50),
                              questions=[q1, q2, q3], selection_groups=sel)
    # Teacher-induced error: choose-1-of-3 with non-uniform weights (15/50/35). Answering Q1 alone caps
    # the score at 15/100. The intended normalization is unknowable from the rubric -> no auto-fix;
    # surfaced for the teacher to decide (e.g. grade each chosen question out of 100%).
    r.pedagogical_mistakes.append(PedagogicalMistake(
        mistake_id="employee_normalization", kind=PedagogicalMistakeKind.SELECTION_NORMALIZATION,
        severity=AnnotationSeverity.WARNING, target_id=None,
        explanation=("הבחירה היא שאלה אחת מתוך שלוש, אך לשאלות ניקוד שונה (15/50/35). מענה על שאלה 1 "
                     "בלבד חוסם את הציון ל-15 מתוך 100. יש להבהיר כיצד מנרמלים את הציון."),
        evidence={"choose_k": 1, "question_points": {"q1": 15, "q2": 50, "q3": 35}, "max_achievable": 50},
        suggested_fix=None, requires_teacher_input=True, confidence=1.0))
    validate(r, name)
    print(f"    Q1 {len(q1.criteria)} crit; Q2 {len(q2.sub_questions)} sub-q; Q3 {len(q3.sub_questions)} sub-q")
    return r, name


# =============================================================================
# FILE 3 — foundations_cs (answer-all; Q1 inline sub-q, Q2 flat table, Q3 inline+table FP3)
# =============================================================================
def build_foundations_cs():
    name = "foundations_cs"
    T = read_tables(name + ".docx")
    # T1=Q1 trace(context), T2=Q2 solution code, T3=Q2 מחוון(16r: desc=col0,pts=col1),
    # T4=Q3.ב solution code, T5=Q3.ב מחוון(14r: desc=col0,pts=col1)
    # Q1: inline -> 3 sub-q, each 1 holistic criterion (text authored from the paragraphs).
    q1 = Question(question_id="q1", total_points=D(30), sub_questions=[
        mk_leaf_subq("א", 0, [("טבלת מעקב עבור זימון הפעולה what(22,5) — כל עדכון 2/3 נק'", D(15))], "q1"),
        mk_leaf_subq("ב", 1, [("טענת כניסה וטענת יציאה לפעולה — כל טעות 5 נק'", D(10))], "q1"),
        mk_leaf_subq("ג", 2, [("בחירת ההוראה/ות המתאימה/ות להחלפת ההוראה החסרה", D(5))], "q1"),
    ])
    # Q2: 16 direct criteria from T3, no sub-q.
    q2_items = extract_rows(T[2], desc_col=0, pts_col=1)
    q2 = Question(question_id="q2", total_points=D(35),
                  criteria=[crit(d, p, k, "q2", "", k) for k, (d, p) in enumerate(q2_items)])
    # Q3: א inline (3 criteria, FP3), ב from T5 table.
    q3a = SubQuestion(sub_question_id="א", index=0, points=D(10), example_solution=None, criteria=[
        crit("כותרת", D(3), 0, "q3", "א", 0),
        crit("שימוש בפרמטרים + בדיקת תנאי", D(5), 1, "q3", "א", 1),
        crit("החזרת ערך בכל תרחיש", D(2), 2, "q3", "א", 2),
    ])
    q3b_items = extract_rows(T[4], desc_col=0, pts_col=1)   # drops the two 0-pt כותרת rows
    q3b = mk_leaf_subq("ב", 1, q3b_items, "q3")
    q3 = Question(question_id="q3", total_points=D(35), sub_questions=[q3a, q3b])
    r = ExtractRubricResponse(rubric_id=name, rubric_name=name, subject="computer_science",
                              programming_language="csharp", total_points=D(100),
                              questions=[q1, q2, q3], selection_groups=[])
    validate(r, name)
    print(f"    Q1 {len(q1.sub_questions)} sub-q; Q2 {len(q2.criteria)} crit; "
          f"Q3 א {len(q3a.criteria)} crit / ב {len(q3b.criteria)} crit")
    return r, name



# =============================================================================
# FILE 1 — csharp_plane_combine (answer-all; Q1 revisions+bonus -> faithful mismatch; Q2 6 sub-q)
# =============================================================================
def build_csharp_plane_combine():
    name = "csharp_plane_combine"
    T = read_tables(name + ".docx")
    # T2 = Q1 מחוון. Run-level strikethrough is load-bearing: old struck values are superseded by the
    # adjacent 'ערך חדש' value (6->8, 18->20, 4->0) and the fully-struck 'אם נוסף' bonus is excluded.
    # extract_rows() cannot see strikethrough, so Q1 is authored explicitly from the honored markup.
    # NOTE: arr2[i]=0 is revised 4->0 by strikethrough; a 0-pt criterion is schema-invalid, so it is
    # dropped. [FLAG: you said this criterion is 4; the document shows its 4 struck through -> 0.]
    q1_crits = [
        ("כותרת הפעולה וחתימה תקינה", D(4)),
        ("חישוב נכון של אורך המערך החדש", D(8)),
        ("יצירת מערך חדש לפי החישוב", D(4)),
        ("לולאות ומילוי תקין של הערכים", D(20)),
        ("החזרת מערך תקינה", D(2)),
        ("כתיבה תקינה, רווחים, שמות משתנים תקינים", D(2)),
    ]
    q1 = Question(question_id="q1", total_points=D(40),
                  criteria=[crit(d, p, k, "q1", "", k) for k, (d, p) in enumerate(q1_crits)])
    # T4..T9 = Q2 sub-q א..ו מחוון (ניקוד|רכיב): pts=col0, desc=col1.
    q2_tables = [(T[3], "א"), (T[4], "ב"), (T[5], "ג"), (T[6], "ד"), (T[7], "ה"), (T[8], "ו")]
    q2_subs = []
    for i, (tbl, letter) in enumerate(q2_tables):
        items = extract_rows(tbl, desc_col=1, pts_col=0)
        q2_subs.append(mk_leaf_subq(letter, i, items, "q2"))
    q2 = Question(question_id="q2", total_points=D(60), sub_questions=q2_subs)

    r = ExtractRubricResponse(rubric_id=name, rubric_name=name, subject="computer_science",
                              programming_language="csharp", total_points=D(100),
                              questions=[q1, q2], selection_groups=[])
    q1_sum = sum((c.points for c in q1.criteria), Decimal("0"))  # == 40 with honored strikethrough
    validate(r, name)
    print(f"    Q1 {len(q1.criteria)} crit (sum {q1_sum}); Q2 {len(q2_subs)} sub-q; "
          f"annotations={[a.target_id for a in r.annotations]}")
    return r, name



def group_by_sahuf(table, qn, desc_col=0, pts_col=1):
    """{letter: [(desc, pts)]} grouping σעיף-tagged criteria. Untagged continuation rows
    carry forward the last-seen σעיף letter (rubrics tag inconsistently — e.g. tag ב's
    'readable code' row but not א's). '?' only if a row precedes any σעיף tag."""
    groups = {}
    last = None
    for row in table[1:]:
        if max(desc_col, pts_col) >= len(row):
            continue
        desc_raw, pts = row[desc_col], parse_points(row[pts_col])
        if is_skip_row(desc_raw, pts):
            continue
        letter, desc = strip_sahuf(desc_raw)
        if letter is not None:
            last = letter
        key = letter or last or "?"
        groups.setdefault(key, []).append((desc, pts))
    return groups


# =============================================================================
# FILE 2 — bagrut_899371 (SELECTION 4 of 6 @ 25; Q1 NESTING (1)/(2); strikethrough Q4)
# =============================================================================
def build_bagrut_899371():
    name = "bagrut_899371"
    T = read_tables(name + ".docx")

    # ---- Q1 (25): NESTING per spec. א=branch[(1)trace12,(2)purpose3]; ב=branch[(1)return6,(2)purpose4].
    # example_solution lives INSIDE each sub-sub-question (it is the red-font text in the source).
    a1 = SubQuestion(sub_question_id="1", index=0, points=D(12), example_solution="ערך מוחזר: T",
                     criteria=[crit("טבלת מעקב אחר Check(arr,6) — 17 תאים, 0.7 לכל תא", D(12), 0, "q1", "א.1", 0)])
    a2 = SubQuestion(sub_question_id="2", index=1, points=D(3),
                     example_solution=("הפעולה מקבלת מערך מספרים וערך x, ומטרתה לבדוק אם קיים במערך איבר שונה "
                                       "מ-x ושונה מ-1 שהוא מחלק של x; מחזירה true אם נמצא מחלק כזה, אחרת false."),
                     criteria=[crit("מטרת הפעולה Check", D(3), 0, "q1", "א.2", 0)])
    sqA = SubQuestion(sub_question_id="א", index=0, points=D(15), sub_questions=[a1, a2])
    b1 = SubQuestion(sub_question_id="1", index=0, points=D(6), example_solution="ערך מוחזר: 76 (0+8+4+15+40+9=76)",
                     criteria=[crit("הערך המוחזר מהפעולה What(arr) — 76", D(6), 0, "q1", "ב.1", 0)])
    b2 = SubQuestion(sub_question_id="2", index=1, points=D(4),
                     example_solution=("מטרת הפעולה לחשב ולהחזיר את סכום כל האיברים במערך שיש להם לפחות מחלק "
                                       "אחד בתוך המערך עצמו (למעט 1 והמספר עצמו)."),
                     criteria=[crit("מטרת הפעולה What", D(4), 0, "q1", "ב.2", 0)])
    sqB = SubQuestion(sub_question_id="ב", index=1, points=D(10), sub_questions=[b1, b2])
    q1 = Question(question_id="q1", total_points=D(25), sub_questions=[sqA, sqB])

    # ---- Q2..Q6 (25 each): σעיף-grouped extraction
    def build_q(qn, table, total):
        g = group_by_sahuf(table, qn)
        if set(g) == {"?"}:        # untagged -> flat criteria, no sub-questions
            items = g["?"]
            return Question(question_id=qn, total_points=D(total),
                            criteria=[crit(d, p, k, qn, "", k) for k, (d, p) in enumerate(items)])
        subs = []
        for i, L in enumerate(sorted(g, key=lambda x: _HEB_LETTERS.index(x) if x in _HEB_LETTERS else 99)):
            subs.append(mk_leaf_subq(L, i, g[L], qn))
        return Question(question_id=qn, total_points=D(total), sub_questions=subs)

    q2 = build_q("q2", T[10], 25)   # IsMirror/ArrangeMirror
    q3 = build_q("q3", T[13], 25)   # DiceStatistics/PrintStatistics
    # Q3.ב has nested (1)/(2): PrintStatistics prints (1) most-frequent value(s), (2) values that never appeared.
    # The מחוון does NOT sub-divide ב, so the (1)/(2) criterion boundary is a judgment: method scaffolding +
    # max-finding/printing -> (1); the 'print values that did not appear' loop -> (2). [FLAG]
    _b = next(sq for sq in q3.sub_questions if sq.sub_question_id == "ב")
    _bi = [(c.description, c.points) for c in _b.criteria]
    b1 = mk_leaf_subq("1", 0, _bi[:-1], "q3.ב")     # scaffolding..print-max
    b2 = mk_leaf_subq("2", 1, _bi[-1:], "q3.ב")     # print values that did not appear
    _newb = SubQuestion(sub_question_id="ב", index=_b.index, points=_b.points, sub_questions=[b1, b2])
    q3 = Question(question_id="q3", total_points=D(25),
                  sub_questions=[(_newb if sq.sub_question_id == "ב" else sq) for sq in q3.sub_questions])
    q4 = build_q("q4", T[14], 25)   # TotalEarnings/TopEarners (task has a strikethrough; מחוון unaffected)
    q5 = build_q("q5", T[15], 25)   # IsSimilarWorkshop/HandleNewWorkshop
    q6 = build_q("q6", T[16], 25)   # Q6 (untagged מחוון -> 9 flat criteria, no sub-questions)

    sel = [SelectionGroup(group_id="sg0", choose_k=4,
                          of_question_ids=["q1", "q2", "q3", "q4", "q5", "q6"],
                          label="ענו על 4 מתוך 6 שאלות")]
    r = ExtractRubricResponse(rubric_id=name, rubric_name=name, subject="computer_science",
                              programming_language="csharp", total_points=D(100),
                              questions=[q1, q2, q3, q4, q5, q6], selection_groups=sel)
    validate(r, name)
    for q in r.questions:
        kids = (f"{len(q.sub_questions)} sub-q" if q.sub_questions else f"{len(q.criteria)} crit")
        nested = sum(1 for sq in q.all_sub_questions if sq.sub_questions)
        print(f"    {q.question_id} ({q.total_points}) {kids}" + (f"  [{nested} nested]" if nested else ""))
    return r, name


if __name__ == "__main__":
    for builder in (build_hobby_tvshow, build_employee_course_select1, build_foundations_cs,
                    build_csharp_plane_combine, build_bagrut_899371):
        r, name = builder()
        write(r, name)
    print("\n[done] wrote 5 benchmarks")
