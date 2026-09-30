"""The planner's three few-shot examples (PR_grader_v6_options.md §5.4). Reviewed at REVIEW-2.

DOMAIN-SHIFTED: from no fixture rubric and in no fixture's vocabulary — no TV shows or
hobbies, no SetPeople / employees / courses / departments, no planes or array-combining,
no valid-array / even-odd checks, no trace tables, none of the bagrut topics. One
example per live subject (a line's slope · counting vowels · grammar in a paragraph),
so the core the three share stays subject-agnostic (§3.3).

Each example is DATA — a `ScopePlannerInput` and the `ScopePlanOutput` a correct plan
returns — so `prompt.py` renders the input through the same `render_scope_input` a real
scope goes through, and the test validates every output against the schema and against
its own input's closed lists. Inputs are written as a real input arrives: marker
amounts already masked, and every id an AM-G17 alias (t1, k1, m1, n1). `scope_id` is
never rendered.

  1  a monolith becomes a LADDER (beside a fixed, as-compiled terminal)
  2  a criterion plus a deduction: the P-3 rewrite and `requires` (on a split monolith;
     a no-deduct marker is not_a_deduction)
  3  a tier ladder with overlapping conditions: the P-5 rewrite and a P-6 merge
     (plus one P-9 interpretation note)
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Tuple

from app.agents.grader.plan_schemas import MarkerDisposition, PartialFraction

from .inputs import (AMOUNT_MASK, MarkerInput, ScopePlannerInput, SkeletonComponent,
                     TerminalInput)
from .schemas import (PlannedCredit, PlannedFault, PlannedFaultOption, PlannedPartial,
                      PlannedTerminal, ScopePlanOutput)


@dataclass(frozen=True)
class FewShot:
    title: str
    input: ScopePlannerInput
    output: ScopePlanOutput


_M = AMOUNT_MASK

# ── 1 · a monolith becomes a ladder ─────────────────────────────────────────────
_EX1 = FewShot(
    title="a monolith becomes a ladder",
    input=ScopePlannerInput(
        scope_id="q4",
        question_text="נתונות הנקודות A(1, 2) ו-B(3, 8). חשבו את שיפוע הישר AB וכתבו את משוואת הישר.",
        example_solution="m = (8 − 2) / (3 − 1) = 6 / 2 = 3\ny − 2 = 3(x − 1)\ny = 3x − 1",
        terminals=(
            TerminalInput(
                terminal_id="t1", points_possible=Decimal("4"),
                teacher_text="חישוב שיפוע הישר AB (4 נק')",
                components=(SkeletonComponent("k1", "חישוב שיפוע הישר AB", "monolith"),)),
            TerminalInput(
                terminal_id="t2", points_possible=Decimal("2"),
                teacher_text=("משוואת הישר: הצבת השיפוע ונקודה על הישר (1 נק'), "
                              "כתיבת המשוואה בצורה y = mx + b (1 נק')"),
                components=(
                    SkeletonComponent("k2", "הצבת השיפוע ונקודה על הישר", "fixed"),
                    SkeletonComponent("k3", "כתיבת המשוואה בצורה y = mx + b", "fixed"),
                )),
        ),
    ),
    output=ScopePlanOutput(
        terminals=[
            PlannedTerminal(
                terminal_id="t1", decomposition="ladder",
                credits=[PlannedCredit(
                    component_ref="k1",
                    description_he="חישוב שיפוע הישר AB",
                    source_span="חישוב שיפוע הישר AB",
                    full_label_he="הפרש ערכי y חולק בהפרש ערכי x של אותן נקודות, והחישוב נכון",
                    absent_label_he="לא חושב שיפוע מהפרשי הקואורדינטות",
                    partials=[PlannedPartial(
                        label_he="הפרשי הקואורדינטות הוצבו בנוסחת השיפוע, אך בחישוב נפלה טעות",
                        fraction=PartialFraction.HALF)],
                    equivalence_note_he="החסרה בסדר ההפוך, במונה ובמכנה יחד, שקולה",
                )]),
            PlannedTerminal(
                terminal_id="t2", decomposition="as_compiled",
                credits=[
                    PlannedCredit(
                        component_ref="k2",
                        description_he="הצבת השיפוע ונקודה על הישר",
                        source_span="הצבת השיפוע ונקודה על הישר",
                        full_label_he="השיפוע ונקודה מהישר הוצבו במשוואת ישר",
                        absent_label_he="לא הוצבו שיפוע ונקודה במשוואת ישר"),
                    PlannedCredit(
                        component_ref="k3",
                        description_he="כתיבת המשוואה בצורה y = mx + b",
                        source_span="כתיבת המשוואה בצורה y = mx + b",
                        full_label_he="המשוואה כתובה בצורה y = mx + b",
                        absent_label_he="המשוואה אינה כתובה בצורה y = mx + b"),
                ]),
        ],
    ),
)

# ── 2 · a criterion plus a deduction: P-3 + requires ────────────────────────────
_EX2_TEXT = (f"ספירת התנועות במחרוזת והחזרת מספרן (5 נק'). "
             f"לא נספרות תנועות באותיות גדולות — יורדו {_M} נק'. "
             f"על שכחת נקודה-פסיק לא מורידים.")
_EX2 = FewShot(
    title="a criterion plus a deduction: the credit without the fault, and requires",
    input=ScopePlannerInput(
        scope_id="q2",
        question_text=("כתבו פעולה בשם CountVowels המקבלת מחרוזת ומחזירה את מספר התנועות "
                       "(a, e, i, o, u) שבה, באותיות קטנות וגדולות."),
        example_solution=("public static int CountVowels(string s)\n"
                          "{\n"
                          "    int count = 0;\n"
                          "    foreach (char c in s.ToLower())\n"
                          "    {\n"
                          "        if (\"aeiou\".IndexOf(c) >= 0)\n"
                          "            count++;\n"
                          "    }\n"
                          "    return count;\n"
                          "}"),
        terminals=(
            TerminalInput(
                terminal_id="t1", points_possible=Decimal("5"), teacher_text=_EX2_TEXT,
                components=(SkeletonComponent("k1", "ספירת התנועות במחרוזת והחזרת מספרן",
                                              "monolith"),)),
        ),
        markers=(
            MarkerInput("m1", f"לא נספרות תנועות באותיות גדולות — יורדו {_M} נק'",
                        "deduct", "t1", ("t1",)),
            MarkerInput("m2", "על שכחת נקודה-פסיק לא מורידים",
                        "no_deduct", "t1", ("t1",)),
        ),
    ),
    output=ScopePlanOutput(
        terminals=[PlannedTerminal(
            terminal_id="t1", decomposition="split",
            credits=[
                PlannedCredit(
                    component_ref="n1",
                    description_he="ספירת התנועות במחרוזת",
                    source_span="ספירת התנועות במחרוזת",
                    full_label_he="מעבר על כל תווי המחרוזת והגדלת מונה על כל תנועה",
                    absent_label_he="אין ספירה של התנועות במחרוזת",
                    equivalence_note_he="זיהוי תנועה בהשוואה לכל אחת מהאותיות, במקום חיפוש במחרוזת aeiou, שקול"),
                PlannedCredit(
                    component_ref="n2",
                    description_he="החזרת מספר התנועות",
                    source_span="והחזרת מספרן",
                    full_label_he="הפעולה מחזירה את המונה",
                    absent_label_he="הפעולה אינה מחזירה את מספר התנועות"),
            ])],
        faults=[PlannedFault(
            anchor_terminal_id="t1",
            requires_component_ref="n1",
            description_he="תנועות באותיות גדולות אינן נספרות",
            options=[PlannedFaultOption(
                marker_id="m1",
                label_he="הספירה מזהה רק תנועות באותיות קטנות, ותנועה באות גדולה אינה נספרת")])],
        dispositions=[
            MarkerDisposition(marker_id="m1", disposition="fault"),
            MarkerDisposition(marker_id="m2", disposition="not_a_deduction",
                              reason_he="הנחיה שלא להוריד נקודות על שכחת נקודה-פסיק"),
        ],
    ),
)

# ── 3 · a tier ladder with overlapping conditions: P-5 + P-6 ────────────────────
_EX3_M1 = f"שגיאת דקדוק אחת לפחות — יורדו {_M} נק'"
_EX3_M2 = f"שתי שגיאות דקדוק או יותר — יורדו {_M} נק'"
_EX3_M3 = f"על שגיאות דקדוק להוריד {_M} נק'"
_EX3 = FewShot(
    title="a tier ladder with overlapping conditions: disjoint tiers and a merge",
    input=ScopePlannerInput(
        scope_id="q5",
        question_text="Write a paragraph (60–80 words) about a trip you took.",
        example_solution=None,
        terminals=(
            TerminalInput(
                terminal_id="t1", points_possible=Decimal("6"),
                teacher_text=f"דקדוק (6 נק'): {_EX3_M1}. {_EX3_M2}. {_EX3_M3}.",
                components=(SkeletonComponent("k1", "דקדוק", "monolith"),)),
        ),
        markers=(
            MarkerInput("m1", _EX3_M1, "deduct", "t1", ("t1",)),
            MarkerInput("m2", _EX3_M2, "deduct", "t1", ("t1",)),
            MarkerInput("m3", _EX3_M3, "deduct", "t1", ("t1",)),
        ),
    ),
    output=ScopePlanOutput(
        terminals=[PlannedTerminal(
            terminal_id="t1", decomposition="binary",
            credits=[PlannedCredit(
                component_ref="k1",
                description_he="כתיבת הפסקה",
                source_span="Write a paragraph",
                full_label_he="נכתבה פסקה באנגלית על טיול",
                absent_label_he="לא נכתבה פסקה")],
            interpretation_notes_he=["שגיאת כתיב אינה נספרת כשגיאת דקדוק."])],
        faults=[PlannedFault(
            anchor_terminal_id="t1",
            requires_component_ref="k1",
            description_he="שגיאות דקדוק בפסקה",
            options=[
                PlannedFaultOption(marker_id="m1", label_he="שגיאת דקדוק אחת בדיוק"),
                PlannedFaultOption(marker_id="m2", label_he="שתי שגיאות דקדוק או יותר"),
            ])],
        dispositions=[
            MarkerDisposition(marker_id="m1", disposition="fault"),
            MarkerDisposition(marker_id="m2", disposition="fault"),
            MarkerDisposition(marker_id="m3", disposition="merged",
                              merged_into_marker_id="m1",
                              reason_he=("«על שגיאות דקדוק להוריד» חוזר על המצב «שגיאת דקדוק אחת "
                                         "לפחות», ולכן שתי ההנחיות אוחדו.")),
        ],
    ),
)

FEW_SHOTS: Tuple[FewShot, ...] = (_EX1, _EX2, _EX3)
