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

LIVE since grader-v6 Phase 2 ([AM-G5], owner 2026-09-27; closes census D-10).
The subject packs REFERENCE these clauses — never copy them — through `select`:
the CS pack's precedents are `select(...)` of the eleven clauses AM-G5 names,
and they feed the v6 PLANNER and EXPLAINER only, never the verifier. Class 4
(`NEVER_GENERATED`) cannot be selected: `select` refuses it by id, which is the
code form of «no PB-* in any prompt, ever».
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Tuple

CONSTITUTION_VERSION = "constitution/v1"

ClauseKind = Literal["policy", "authoring"]


@dataclass(frozen=True)
class Clause:
    """`policy` appends prose to a check. `authoring` changes how the model
    DECOMPOSES — which is the only way a clause can move expressibility.
    Frozen: a pack holds these by reference, so one cannot be edited in place."""

    clause_id: str
    kind: ClauseKind
    text_he: str
    subject: Optional[str] = None       # None = every subject (§3.3)


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
    Clause("R-beta", "authoring",
           "קנס נקוב חל בכל אתר גישה; שימוש נכון במקום אחר אינו מרפא גישה "
           "ישירה באתר הנבדק."),
    Clause("A-6", "authoring",
           "קנס אינו מצטבר על פסיקה שכבר הופחתה — אין לחייב פעמיים על אותו פגם."),
    Clause("charge-once", "authoring",
           "פגם שהרובריקה מורה לחייב «רק פעם אחת» מקבל charge_group משותף, "
           "והחיוב נגבה פעם אחת בלבד בתוך הסעיף."),
    Clause("credit-once", "policy",
           "רכיב שכבר זוּכה בבדיקה אחרת אינו נחשב קיים פעם נוספת — הזיכוי "
           "חד-פעמי, כשם שהחיוב חד-פעמי."),
    # RECLASSIFIED 2026-09-01 (owner, from my own Phase 0 finding): R-beta,
    # A-6 and charge-once were `policy` and are `authoring`. Their text
    # changes STRUCTURE — «gets a shared charge_group», «a tariff applies at
    # every access site» — which is what authoring means. Phase 0 measured
    # them moving the algebra on 5 of 38 terminals while P-A did not bind.
    # P-A remains the clearest example of the kind.
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


def _all_clauses() -> List[Clause]:
    out = list(GENERAL) + list(GENERAL_DEFAULT)
    for scoped in SUBJECT_SCOPED.values():
        out += scoped
    return out


def select(*clause_ids: str) -> Tuple[Clause, ...]:
    """The clauses named, in the order named — how a subject pack references
    its precedents ([AM-G5]). Refuses a class-4 id (`NEVER_GENERATED`), an
    unknown id and a repeated one, loudly and at import of the pack."""
    by_id: Dict[str, Clause] = {}
    for c in _all_clauses():
        if c.clause_id in by_id:            # pragma: no cover - a data bug in this module
            raise ValueError(f"constitution: duplicate clause id {c.clause_id!r}")
        by_id[c.clause_id] = c
    out: List[Clause] = []
    for cid in clause_ids:
        if cid in NEVER_GENERATED:
            raise ValueError(f"constitution: {cid!r} is an exam-specific ruling (class 4) "
                             "and never enters a prompt")
        if cid not in by_id:
            raise ValueError(f"constitution: unknown clause id {cid!r}")
        if by_id[cid] in out:
            raise ValueError(f"constitution: clause {cid!r} selected twice")
        out.append(by_id[cid])
    return tuple(out)
