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
                # A credit verdict whose span did not verify was REFUSED by the
                # pricer (the invented-credit guard). Presenting it as «זוכה»
                # here let the feedback say «written as required» over a 0 —
                # three surfaces, three stories (graded_test a0cd07ff,
                # 2026-09-15). The prose must describe what was priced.
                refused = (check.kind in ("required", "counted")
                           and check.verdict in ("met", "partially_met")
                           and check.quote_status not in ("exact", "fuzzy"))
                label = ("לא אומת — לא זוכה" if refused
                         else mark.get(check.verdict, check.verdict))
                line = f"[{label}] {check.text}"
                if check.quote and check.quote_status in ("exact", "fuzzy"):
                    line += f"\n    מתוך התשובה: {check.quote}"
                elif check.basis_he:
                    line += f"\n    {check.basis_he}"
                lines.append(line)
    return "\n".join(lines) or "אין בדיקות לסעיף זה."


def render_scope_v6(content, priced, scope_key) -> str:
    """[grader-v6, AM-G7; owner rulings 2026-10-17 §7] the priced view of one v6 scope: per
    check, the label of the option that PRICED (the pricer's resolution — the evidence gate
    included, so a credit Vivi claimed without a verified quote reads as not credited), then
    the student's own words where the quote verified, or Vivi's absence pointer where she
    found nothing. Faults appear only when charged; observed notes as notes. No points."""
    terminals = {t.terminal_id for t in content.view_terminals
                 if (t.question_id, t.sub_question_id) == scope_key}
    resolved = {r.check_id: r for r in priced.checks}
    charges = {c.check_id: c for t in priced.terminals if t.terminal_id in terminals for c in t.charges}
    lines = []
    for rec in sorted(content.checks, key=lambda c: c.plan_index):
        plan = rec.plan
        if plan.priced_terminal_id not in terminals:
            continue
        r = resolved.get(plan.check_id)
        option = plan.option(r.option_id) if r is not None and r.option_id else None
        if plan.role == "credit":
            label = option.label_he if option is not None else plan.default_option.label_he
            line = f"[{label}] {plan.description_he}"
            if r is not None and r.source == "gated":
                line = f"[לא אומת — לא זוכה] {plan.description_he}"
            elif rec.evidence_quote and rec.quote_status in ("exact", "fuzzy") \
                    and r is not None and r.option_id == rec.model_option_id:
                line += f"\n    מתוך התשובה: {rec.evidence_quote}"
            elif rec.absence_pointer_he and r is not None and r.option_id == plan.default_option.option_id:
                line += f"\n    {rec.absence_pointer_he}"
            lines.append(line)
        elif plan.role == "fault":
            ch = charges.get(plan.check_id)
            if ch is not None and ch.charged < 0 and option is not None:
                lines.append(f"[טעות] {option.label_he}")
        elif plan.role == "note" and option is not None and option.option_id != plan.options[0].option_id:
            lines.append(f"[הערה] {option.label_he}")
    return "\n".join(lines) or "אין בדיקות לסעיף זה."
