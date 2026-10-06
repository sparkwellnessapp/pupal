"""The explainer prompt (PR_grader_v6_options.md §7.3, §7.4). Pure: no I/O, no model.

SYSTEM  = the core rules (X-1..X-11, subject-agnostic, numbered 1..11 in the text) + the
          subject pack's explainer fragment + the pack's precedents (their Hebrew text
          only — never an id, AM-G5) + three DOMAIN-SHIFTED examples + the output
          contract. Identical for every scope of every test of one pack: it is the
          provider's cached prefix.
USER    = `render_scope_message(inp)`: the per-batch-identical part FIRST (question,
          example solution, each criterion's teacher text, points and interpretation
          notes), then — from `STUDENT_SECTION_HEADER` on — this answer's part (grades,
          resolved labels and values, quotes or absence pointers, deductions and their
          statuses, observed notes). Every id in it is an AM-G17 alias (`t1…`, one per
          criterion); no check id and no option id appears at all — the explainer
          addresses criteria only.

Rule ids (X-1, PL-9, …) are never rendered: E-3 rejects a line that names one, and the
model cannot name what it was never shown.

The three examples are DATA (`EXAMPLES`), rendered through the same
`render_scope_message` a real scope goes through, and each example line passes E-1..E-5
against its own input (tests/agents/test_explainer_prompt.py). They come from no fixture's
vocabulary (no TV shows or hobbies, no employees/courses/planes, no bagrut topic) and from
three subjects, so the core they share stays subject-agnostic (§3.3). They show the SHAPE
of the five §7.4 target-register situations — a deduction that applied, a zero where the
deduction did not apply, a partial, full marks, a misspelled name — plus a mistake
already deducted elsewhere (X-10). Reviewed at REVIEW-2.

A change to any byte of the CS assembly moves the pin in
tests/agents/test_explainer_prompt.py — deliberate, logged in RUNLOG, with
EXPLAINER_PROMPT_VERSION bumped.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Tuple

from pydantic import BaseModel

from app.agents.explainer.payload import (
    CreditCheckInput,
    FaultCheckInput,
    ScopeExplainerInput,
    TerminalExplainerInput,
)

__all__ = ["EXPLAINER_PROMPT_VERSION", "ExplanationLine", "ScopeExplanations",
           "explainer_system_prompt", "render_scope_message", "STUDENT_SECTION_HEADER",
           "EXAMPLES", "Example"]

EXPLAINER_PROMPT_VERSION = "explainer-v1.0"

STUDENT_SECTION_HEADER = "=== THIS ANSWER ==="


# ═══════════════════════════════════════════════════════════════════════════
# the output contract (§7.5) — field order as written: the id, then the line
# ═══════════════════════════════════════════════════════════════════════════

class ExplanationLine(BaseModel):
    terminal_id: str                      # an AM-G17 alias (t1…), exactly as listed
    text_he: str


class ScopeExplanations(BaseModel):
    lines: List[ExplanationLine]


# ═══════════════════════════════════════════════════════════════════════════
# the system prompt
# ═══════════════════════════════════════════════════════════════════════════

EXPLAINER_CORE = """\
You write the reasoning line a teacher reads beside each criterion of a graded answer. The
grading is finished: for every criterion you receive the grade it got and what decided it.
Your job is to say WHY, in one short Hebrew sentence, the way an experienced teacher
explains a grade to a colleague. You never grade, and nothing you write changes a grade.

=== WHAT YOU RECEIVE ===
- The question, and the teacher's example solution when she wrote one.
- Per CRITERION (named t1, t2, …): the teacher's own text, the points it is worth, and
  notes on how her text was read where it was ambiguous.
- Then THIS ANSWER, per criterion: the grade it got, and what decided it.
  - Each requirement it was graded on: what was looked for, what was found, the points it
    earned, and either words quoted from the answer that show it, or — when it was not
    found — what the answer contains instead.
  - Each deduction that could apply to it: the mistake, what was found, its amount, what
    was actually deducted, and its status:
      applied     deducted in full;
      capped      deducted only in part: a deduction never costs more than the
                  requirement it concerns earned;
      floored     deducted only in part: a criterion never goes below zero;
      superseded  not deducted here: the same mistake was already deducted at the
                  criterion named;
      inactive    not deducted: the requirement this mistake concerns is missing from
                  the answer;
      no_fault    the mistake is not in the answer.
    A deduction marked "moved here" was deducted at this criterion because the teacher
    set the grade of the criterion named by hand.
  - Remarks the teacher asked to note without deducting, when the answer shows them:
    context only, never part of a grade.

=== RULES ===
1. EXPLAIN THE GRADE AS GIVEN. The grade is final. Never re-grade, disagree, or hint at a
   different grade.
2. LEAD WITH WHAT DECIDED THE GRADE. State what cost points first. With full marks, state
   what satisfied the criterion.
3. BE CONCRETE, like a teacher to a colleague. Say what the answer did: name the name,
   value, step or phrase, in the teacher's vocabulary.
4. APPLY THE PRINCIPLES; NEVER STATE THEM. A deduction counts only when the behavior it
   concerns exists; the same mistake is deducted once; a criterion never goes below zero;
   a misspelled name is not a conceptual error. These shape WHAT you say; they never appear
   AS what you say. Not «לפי הכלל, טעות כתיב בשם אינה פוגעת בציון» — instead «השם כתוב
   lenght במקום length, אבל השימוש בו נכון».
5. ONE SENTENCE; TWO ONLY IF NEEDED. Aim for 20 words or fewer. Never more than 200
   characters.
6. PLAIN HEBREW that a tired teacher reads in two seconds. No hedging, no praise, no
   filler, and do not restate the criterion.
7. NEUTRAL ABOUT THE STUDENT. No gender, no second person, no first person: describe the
   answer, never the student or yourself.
8. NEVER MENTION how the grade was produced: no checks, options, plans, verifier, model,
   AI, Vivi or "the system", and no rule names or rule numbers.
9. NUMBERS ONLY FROM WHAT YOU RECEIVED: the grade, the points, the deduction amounts, and
   numbers written in the teacher's text, the question, the solution or the quoted words.
   Write every number as digits.
10. SAY PLAINLY WHEN A DEDUCTION DID NOT APPLY, if it matters for understanding the grade:
    the behavior it concerns was missing, or the same mistake was already deducted.
11. NAMES, SYMBOLS, FORMULAS AND CODE EXACTLY AS THE ANSWER WROTE THEM, in their own script:
    never translate or transliterate them into Hebrew.

Write exactly one line for each criterion listed under THIS ANSWER, and for no other.
"""

FRAGMENT_HEADER = "=== SUBJECT GUIDANCE ==="

PRECEDENTS_HEADER = """\
=== PRINCIPLES OF THIS SUBJECT ===
Let them shape what you say. Never quote or name them."""

EXAMPLES_HEADER = """\
=== EXAMPLES ===
Three worked examples, from topics unrelated to the answers you will explain. They show
the SHAPE of a good line; never copy their wording."""

OUTPUT_CONTRACT = """\
=== OUTPUT ===
Return one JSON object: {"lines": [{"terminal_id": "t1", "text_he": "…"}, …]} — one entry
per criterion listed under THIS ANSWER, in the order listed, each terminal_id exactly as
written there."""


def explainer_system_prompt(profile) -> str:
    """The explainer system prompt for a subject pack (`registry.get_profile(key)`)."""
    parts: List[str] = [EXPLAINER_CORE.rstrip("\n")]
    if profile.explainer_fragment and profile.explainer_fragment.strip():
        parts += ["", FRAGMENT_HEADER, profile.explainer_fragment.rstrip("\n")]
    if profile.precedents:
        parts += ["", PRECEDENTS_HEADER]
        parts += [f"- {c.text_he}" for c in profile.precedents]
    parts += ["", EXAMPLES_HEADER]
    for i, ex in enumerate(EXAMPLES, 1):
        parts += ["", _render_example(i, ex)]
    parts += ["", OUTPUT_CONTRACT]
    return "\n".join(parts) + "\n"


def _render_example(i: int, ex: "Example") -> str:
    out = json.dumps(ex.output.model_dump(mode="json"), ensure_ascii=False, indent=2)
    return "\n".join([f"--- Example {i}: {ex.title} ---",
                      "<input>", render_scope_message(ex.input), "</input>",
                      "<output>", out, "</output>"])


# ═══════════════════════════════════════════════════════════════════════════
# the user message
# ═══════════════════════════════════════════════════════════════════════════

def _num(d: Decimal) -> str:
    s = format(abs(Decimal(d)), "f")
    return s.rstrip("0").rstrip(".") if "." in s else s


def _block(text: str) -> str:
    return (text or "").strip() or "(not given)"


def render_scope_message(inp: ScopeExplainerInput) -> str:
    """The per-scope user message. Pure and deterministic. Batch-identical part first
    (everything above `STUDENT_SECTION_HEADER` is a function of the rubric alone, for
    the same set of criteria), then this answer."""
    lines: List[str] = [
        "=== QUESTION ===", _block(inp.question_text),
        "",
        "=== EXAMPLE SOLUTION ===", _block(inp.example_solution),
        "",
        "=== CRITERIA ===",
    ]
    for t in inp.terminals:
        lines += ["", f"--- {t.alias} · points: {_num(t.points_possible)} ---",
                  "Teacher's text:", t.teacher_text.strip()]
        if t.interpretation_notes_he:
            lines += ["How her text was read:"]
            lines += [f"- {n}" for n in t.interpretation_notes_he]

    lines += ["", STUDENT_SECTION_HEADER]
    for t in inp.terminals:
        lines += ["", f"--- {t.alias} · grade: {_num(t.awarded)} of {_num(t.points_possible)} ---"]
        lines += _render_terminal_answer(t)
    if inp.observed_notes_he:
        lines += ["", "Remarks the teacher asked to note (context only, never part of a grade):"]
        lines += [f"- «{n}»" for n in inp.observed_notes_he]
    lines += ["", f"Write one line for each of: {', '.join(t.alias for t in inp.terminals)}."]
    return "\n".join(lines)


def _render_terminal_answer(t: TerminalExplainerInput) -> List[str]:
    lines: List[str] = ["Requirements:"]
    for c in t.credit_checks:
        lines += [f"- «{c.description_he}»",
                  f"  found: «{c.selected_label_he}» · earned {_num(c.selected_value)}"]
        if c.evidence_quote:
            lines += [f"  quoted from the answer: «{c.evidence_quote}»"]
        elif c.absence_pointer_he:
            lines += [f"  the answer contains instead: «{c.absence_pointer_he}»"]
    if t.fault_checks:
        lines += ["Deductions:"]
        for f in t.fault_checks:
            lines += [f"- «{f.description_he}»",
                      f"  found: «{f.selected_label_he}» · amount {_num(f.amount)}"
                      f" · deducted {_num(f.charged)} · {f.status}"]
            if f.charged_elsewhere_he:
                lines += [f"  already deducted at: «{f.charged_elsewhere_he.strip()}»"]
            if f.moved_by_pin and f.pinned_criterion_he:
                lines += [f"  moved here: the teacher set the grade of "
                          f"«{f.pinned_criterion_he.strip()}» by hand"]
    return lines


# ═══════════════════════════════════════════════════════════════════════════
# the three examples (DATA; REVIEW-2)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Example:
    title: str
    input: ScopeExplainerInput
    output: ScopeExplanations


D = Decimal


def _t(alias: str, tid: str, text: str, points: str, awarded: str,
       credits: Tuple[CreditCheckInput, ...], faults: Tuple[FaultCheckInput, ...] = (),
       fallback: str = "") -> TerminalExplainerInput:
    return TerminalExplainerInput(alias=alias, terminal_id=tid, teacher_text=text,
                                  points_possible=D(points), awarded=D(awarded),
                                  credit_checks=credits, fault_checks=faults,
                                  fallback_he=fallback or text)


def _lines(*pairs: Tuple[str, str]) -> ScopeExplanations:
    return ScopeExplanations(lines=[ExplanationLine(terminal_id=a, text_he=t) for a, t in pairs])


# ── 1 · a deduction that applied, and a misspelled name with full marks ─────────
_EX1 = Example(
    title="a deduction that applied, and a misspelled name",
    input=ScopeExplainerInput(
        question_id="q2",
        question_text=("כתבו פעולה בשם CountChar המקבלת מחרוזת s ותו c, ומחזירה כמה פעמים c "
                       "מופיע ב-s. אין להשתמש בפעולות ספירה מובנות."),
        example_solution=("public static int CountChar(string s, char c)\n"
                          "{\n"
                          "    int count = 0;\n"
                          "    for (int i = 0; i < s.Length; i++)\n"
                          "        if (s[i] == c)\n"
                          "            count++;\n"
                          "    return count;\n"
                          "}"),
        terminals=(
            _t("t1", "q2.c1",
               "ספירת המופעים של התו במחרוזת (4 נק'). שימוש בפעולת ספירה מובנית — יורדו 2 נק'.",
               "4", "2",
               (CreditCheckInput(description_he="ספירת המופעים של התו במחרוזת",
                                 selected_label_he="כל מופע של התו במחרוזת נספר",
                                 selected_value=D("4"),
                                 evidence_quote="int count = s.Count(x => x == c);"),),
               (FaultCheckInput(description_he="שימוש בפעולת ספירה מובנית",
                                selected_label_he="הספירה נעשית בפעולה מובנית ולא בלולאה",
                                amount=D("-2"), charged=D("-2"), status="applied"),)),
            _t("t2", "q2.c2", "החזרת מספר המופעים (1 נק')", "1", "1",
               (CreditCheckInput(description_he="החזרת מספר המופעים",
                                 selected_label_he="הפעולה מחזירה את מספר המופעים",
                                 selected_value=D("1"), evidence_quote="return conut;"),)),
        ),
    ),
    output=_lines(
        ("t1", "המופעים נספרו בעזרת s.Count, פעולה מובנית, ולא בלולאה, ולכן ירדו 2 נקודות."),
        ("t2", "בשורת ההחזרה כתוב conut במקום count, טעות כתיב בשם, והערך המוחזר נכון."),
    ),
)

# ── 2 · a partial step, and a zero where the deduction did not apply ────────────
_EX2 = Example(
    title="a partial step, and a zero where the deduction did not apply",
    input=ScopeExplainerInput(
        question_id="q4",
        question_text=("במשולש ABC אורך הצלע BC הוא 6 ס\"מ, הגובה לצלע BC הוא 4 ס\"מ, "
                       "ואורך הצלע AB הוא 5 ס\"מ. חשבו את שטח המשולש."),
        example_solution="S = (BC · h) / 2 = (6 · 4) / 2 = 12 סמ\"ר",
        terminals=(
            _t("t1", "q4.c1", "חישוב שטח המשולש לפי צלע והגובה לה (3 נק')", "3", "1.5",
               (CreditCheckInput(description_he="חישוב שטח המשולש לפי צלע והגובה לה",
                                 selected_label_he="הנוסחה נכונה, אך במקום הגובה הוצבה צלע אחרת",
                                 selected_value=D("1.5"),
                                 evidence_quote="S = (6 · 5) / 2 = 15"),)),
            _t("t2", "q4.c2",
               ("כתיבת יחידות המידה של השטח (1 נק'). יחידות של אורך במקום יחידות של שטח — "
                "יורדו 1 נק'."),
               "1", "0",
               (CreditCheckInput(description_he="כתיבת יחידות המידה של השטח",
                                 selected_label_he="לא נכתבו יחידות מידה",
                                 selected_value=D("0"),
                                 absence_pointer_he="התוצאה 15 כתובה בלי יחידות"),),
               (FaultCheckInput(description_he="יחידות של אורך במקום יחידות של שטח",
                                selected_label_he="ללא הטעות הזו",
                                amount=D("0"), charged=D("0"), status="inactive"),)),
        ),
    ),
    output=_lines(
        ("t1", "הנוסחה נכונה, אבל במקום הגובה 4 הוצבה הצלע AB שאורכה 5."),
        ("t2", "לתוצאה לא נכתבו יחידות מידה כלל, ולכן אין נקודות על הסעיף."),
    ),
)

# ── 3 · full marks, and a mistake already deducted at another criterion ─────────
_EX3_GRAMMAR = "דקדוק ואיות (2 נק'). אות קטנה בתחילת משפט — יורדו 0.5 נק', פעם אחת בכל המייל."
_EX3 = Example(
    title="full marks, and a mistake already deducted elsewhere",
    input=ScopeExplainerInput(
        question_id="q6",
        question_text=("Write a short email (40–60 words) inviting a friend to a picnic. "
                       "Say when and where it will be."),
        example_solution="",
        terminals=(
            _t("t1", "q6.c1", "תוכן: המייל מציין מתי ואיפה ייערך הפיקניק (3 נק')", "3", "3",
               (CreditCheckInput(description_he="ציון המועד", selected_label_he="המועד מצוין",
                                 selected_value=D("1.5"), evidence_quote="on Saturday at 11"),
                CreditCheckInput(description_he="ציון המקום", selected_label_he="המקום מצוין",
                                 selected_value=D("1.5"),
                                 evidence_quote="by the lake near my house"))),
            _t("t2", "q6.c2",
               "פתיחה וסיום של מייל (2 נק'). אות קטנה בתחילת משפט — יורדו 0.5 נק', פעם אחת בכל המייל.",
               "2", "2",
               (CreditCheckInput(description_he="פתיחה וסיום של מייל",
                                 selected_label_he="המייל נפתח בפנייה ומסתיים בחתימה",
                                 selected_value=D("2"), evidence_quote="Hi Dana,"),),
               (FaultCheckInput(description_he="אות קטנה בתחילת משפט",
                                selected_label_he="משפט שמתחיל באות קטנה",
                                amount=D("-0.5"), charged=D("0"), status="superseded",
                                charged_elsewhere_he=_EX3_GRAMMAR),)),
            _t("t3", "q6.c3", _EX3_GRAMMAR, "2", "1.5",
               (CreditCheckInput(description_he="דקדוק ואיות",
                                 selected_label_he="המשפטים כתובים בדקדוק ובאיות תקינים",
                                 selected_value=D("2"), evidence_quote="I hope you can come!"),),
               (FaultCheckInput(description_he="אות קטנה בתחילת משפט",
                                selected_label_he="משפט שמתחיל באות קטנה",
                                amount=D("-0.5"), charged=D("-0.5"), status="applied"),)),
        ),
    ),
    output=_lines(
        ("t1", "המייל מציין גם מועד (on Saturday at 11) וגם מקום (by the lake near my house), כנדרש."),
        ("t2", "המייל נפתח ב-Hi Dana ומסתיים בחתימה; האות הקטנה בתחילת משפט כבר נוכתה בסעיף הדקדוק."),
        ("t3", "משפט אחד במייל מתחיל באות קטנה, ולכן ירדו 0.5 נקודות."),
    ),
)

EXAMPLES: Tuple[Example, ...] = (_EX1, _EX2, _EX3)
