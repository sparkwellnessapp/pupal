"""
The plan constitution — general grading policy, versioned and separable.

OD-5 (owner, 2026-08-31) classifies every accumulated ruling into four classes.
Only the first three are ever attached by the GENERATOR; the fourth arrives only
through layer 1 (the ruling ledger), because it encodes a judgement about one
exam that no amount of reading a different rubric could produce.

The split is what makes V-rubric vs V-const a meaningful measurement: if a
clause here changes DECOMPOSITION, the two variants diverge; if it only appends
prose, they cannot (policy clauses move no number, so they cannot change the
reachable-award set — the Phase 0 pre-registration turns on exactly this).
"""
from __future__ import annotations

from typing import Dict, List, Literal

CONSTITUTION_VERSION = "constitution/v1"

ClauseKind = Literal["policy", "authoring"]


class Clause:
    """`policy` appends prose to a check. `authoring` changes how the model
    DECOMPOSES — which is the only way a clause can move expressibility."""

    def __init__(self, clause_id: str, kind: ClauseKind, text_he: str,
                 subject: str | None = None):
        self.clause_id = clause_id
        self.kind = kind
        self.text_he = text_he
        self.subject = subject          # None = every subject (§3.3)

    def __repr__(self) -> str:          # pragma: no cover - debugging aid
        return f"<Clause {self.clause_id} {self.kind}>"


# ── class 1 — GENERAL (every subject, always attached) ──────────────────────
GENERAL: List[Clause] = [
    Clause("PL-1", "policy",
           "בדיקה נחשבת מתקיימת רק אם הרכיב הנדרש קיים בפועל בתשובת התלמיד/ה, "
           "ולא מכוח כוונה משוערת."),
    Clause("PL-3", "policy",
           "צורה שקולה תקפה: אין לפסול רכיב רק משום שנכתב אחרת מהפתרון לדוגמה, "
           "כל עוד הוא מקיים את הדרישה."),
    Clause("PL-10", "policy",
           "השמה ליעד שאינו מוכרז באף הצהרה — של התלמיד/ה או של הפתרון — היא "
           "שדה שלא אותחל, כלומר פגם מהותי, ולא החלקה בזיהוי."),
    Clause("R-alpha", "policy",
           "הפתרון לדוגמה הוא סמכות השמות: שם התואם את הפתרון תקף תמיד."),
    Clause("R-beta", "policy",
           "קנס נקוב חל בכל אתר גישה; שימוש נכון במקום אחר אינו מרפא גישה "
           "ישירה באתר הנבדק."),
    Clause("A-6", "policy",
           "קנס אינו מצטבר על פסיקה שכבר הופחתה — אין לחייב פעמיים על אותו פגם."),
    Clause("charge-once", "policy",
           "פגם שהרובריקה מורה לחייב «רק פעם אחת» מקבל charge_group משותף, "
           "והחיוב נגבה פעם אחת בלבד בתוך הסעיף."),
    Clause("credit-once", "policy",
           "רכיב שכבר זוּכה בבדיקה אחרת אינו נחשב קיים פעם נוספת — הזיכוי "
           "חד-פעמי, כשם שהחיוב חד-פעמי."),
    # THE ONLY clause here that changes decomposition, and therefore the only
    # one that can move expressibility between V-rubric and V-const. If the two
    # variants differ ANYWHERE this clause does not touch, policy is leaking
    # into decomposition — a pre-registered finding, not noise.
    Clause("P-A", "authoring",
           "כאשר טקסט הקריטריון מונה N רכיבים נבדלים, פרקו אותו ל-N בדיקות "
           "נפרדות, אחת לכל רכיב, וחלקו את הניקוד ביניהן."),
]

# ── class 2 — GENERAL-DEFAULT, teacher-overridable via layer 1 ──────────────
GENERAL_DEFAULT: List[Clause] = [
    Clause("PL-9", "policy",
           "רכיב תקף במונחי עצמו נחשב קיים גם כשהוא פועל על אוסף שגוי, כאשר "
           "הקריאה השגויה כבר חויבה בבדיקות המכונן שנעדרו. אין לחייב את "
           "הקריאה השגויה פעמיים."),
]

# ── class 3 — SUBJECT-SCOPED (attached by contract.subject only) ────────────
SUBJECT_SCOPED: Dict[str, List[Clause]] = {
    "computer_science": [
        Clause("PL-2", "policy",
               "קיצורי כתיב מקובלים בכיתה (cw, CR וכדומה) תקפים כאשר הכוונה "
               "חד-משמעית.",
               subject="computer_science"),
    ],
}

# ── class 4 — EXAM-SPECIFIC: never attached by the generator ────────────────
# PL-8, Q-1, din's credit-side note, P-B's tariff. They reach a plan only
# through the ruling ledger. Listed here as a NEGATIVE manifest so that
# promoting one becomes a visible edit rather than a quiet import.
NEVER_GENERATED = ("PL-8", "Q-1", "din-credit-side", "P-B-tariff")


def clauses_for(subject: str | None, *, include_constitution: bool) -> List[Clause]:
    """The clause set for one generation run.

    `include_constitution=False` is the V-rubric arm: pure decomposition from
    rubric text, with nothing attached. That arm exists because attaching
    rulings derived from THIS exam's ground truth would make the Phase 0 A/B
    say nothing about generalisation.
    """
    if not include_constitution:
        return []
    out = list(GENERAL) + list(GENERAL_DEFAULT)
    out += SUBJECT_SCOPED.get((subject or "").strip().lower(), [])
    return out
