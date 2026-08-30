"""
The feedback prompt (PR-G4, parent spec C2).

Feedback runs AFTER pricing, on the priced verdicts. It can only describe what
was already decided — which is the whole point of separating it from the
grader: one call that both picks a verdict and argues for it would let the
prose anchor the verdict.
"""

FEEDBACK_PROMPT_VERSION = "feedback-v1"

FEEDBACK_SYSTEM_PROMPT = """\
את/ה כותב/ת משוב קצר לתלמיד/ה על מבחן שכבר נבדק. הציון כבר נקבע — תפקידך רק
לתאר, בעברית, מה נעשה נכון ומה חסר.

<address>
פנייה בגוף שני בזמן עבר בלבד ("הגדרת", "סכמת", "החזרת"), או בצורות שמניות
("ההגדרה תקינה", "חסרה בדיקת טווח").

לעולם לא: "אתה"/"אתם", ציווי ("בדוק", "שימי לב"), או הווה ("אתה כותב", "צריך").
בעברית לא מנוקדת גוף שני בעבר נכתב זהה לשני המגדרים — זו הסיבה שזו צורת הפנייה
היחידה שאינה מנחשת את מגדר התלמיד/ה.
</address>

<per_scope>
לכל סעיף, שלושה חלקים ובסדר הזה:
1. מה זוכה — רכיב אחד או שניים שנעשו נכון, במילים של התשובה עצמה.
2. מה חסר — הרכיב הנדרש שלא נמצא, בניסוח ענייני.
3. מצביע אחד — משפט אחד שמכוון לאן להסתכל. לא פתרון, לא קוד.

בלי לחזור על מספר הנקודות. הציון מוצג במקום אחר; חזרה עליו הופכת את המשוב
לנימוק של הציון במקום לתיאור של העבודה.
</per_scope>

<summary>
סיכום קצר לכל המבחן: שני דפוסים שחוזרים על פני סעיפים, ואז מצביע אחד.
לא סיכום של הסעיפים בזה אחר זה, ולא הציון הכולל.
</summary>

<tone>
עניינית, מכבדת, בלי שבחים מוגזמים ובלי ריכוך. תיאור, לא שיפוט.
</tone>
"""


def build_feedback_message(scopes) -> str:
    """One message per TEST: every scope's priced verdicts, in document order.

    The model sees verdicts and quotes — never points and never the total —
    because the text must describe the work, not justify a number.
    """
    parts = ["דירוג המבחן הושלם. להלן, לכל סעיף, הבדיקות שזוכו ושלא זוכו.", ""]
    for scope_id, rendered in scopes:
        parts.append("═" * 60)
        parts.append(f"סעיף {scope_id}")
        parts.append("═" * 60)
        parts.append(rendered)
        parts.append("")
    parts.append("כתבי משוב לכל סעיף, ולאחר מכן סיכום אחד למבחן כולו.")
    return "\n".join(parts)


def render_scope_for_feedback(scope_outcome) -> str:
    """The priced view of one scope: each check, its verdict, and the student's
    own words where a span was verified. No points anywhere."""
    mark = {"met": "זוכה", "partially_met": "זוכה חלקית", "not_met": "לא זוכה"}
    lines = []
    for criterion in scope_outcome.criterion_outcomes:
        for leaf in (criterion.sub_criterion_outcomes or [criterion]):
            for check in (leaf.checks or []):
                line = f"[{mark.get(check.verdict, check.verdict)}] {check.text}"
                if check.quote and check.quote_status in ("exact", "fuzzy"):
                    line += f"\n    מתוך התשובה: {check.quote}"
                elif check.basis_he:
                    line += f"\n    {check.basis_he}"
                lines.append(line)
    return "\n".join(lines) or "אין בדיקות לסעיף זה."
