"""
grader-v5 verifier prompt — render functions for the Plan/Verify/Price path.

The verifier model receives requirement-phrased CHECKS (from the ratified
GradingPlan) and emits VERDICTS + evidence spans — NEVER a number. All point
arithmetic lives in pricer.py. This prompt therefore carries forward ONLY the
two PROVEN clauses from the E-series (form-vs-behaviour as verdict guidance;
example-solution-as-authority) plus the K2-forensics absence-audit rules
(K2_FORENSICS.md, 2026-08-28); every magnitude sentence of grader-v4 is
deliberately absent — deduction size is code now.

Rendering is POINT-BLIND by design: no points, tariffs or fractions reach the
verifier. Rationale (mission-start RUNLOG entry): a model that can see prices
can reason about outcomes instead of evidence; verdict-only + point-blind
closes the side door that E8's clause (c) opened.
"""
from __future__ import annotations

from typing import Dict, List

from app.agents.grader.plan_schemas import TerminalPlan
from app.agents.grader.prompt import _render_context_sections
from app.schemas.gradable import GradableScope

# Bumped by hand when this prompt or the check-rendering changes in a way that
# could affect verdicts. Stamped into GradedTestDraft.prompt_version alongside
# plan_version (draft field) — a v5 grade is a function of FIVE versions:
# rubric contract, transcription contract, model, prompt, plan.
# v5.1 (owner H-2-review rulings 2+3, 2026-08-29, bundled): rule 6 gains the
# PL-9 wrong-target clause (owner text verbatim) — the counter to the ONE K1
# class the mission observed (hedged partial credit on wrong-target
# machinery; killed haiku/luna/gpt-5.5/terra). Rule 8 becomes the BASIS-LEAN
# output contract: met emits the quote only (self-evidencing; ~85% of
# verdicts), partially_met/not_met keep the full basis incl. the mandatory
# search statement — the GA-7 engineering move (output tokens are the cost
# driver at frontier tier). Known trade, owner-recorded: the R-3
# right-for-wrong-reason audit re-anchors on partial/not_met prose + quote-
# fit on met; Phase-D J2 audits met via quotes, not prose.
# v5.2 (owner FP2 ruling R-1, 2026-08-29): rule 6 gains its BOUNDARY
# sentence — the clause governs ABSENT components; it must not annihilate
# in-own-terms-valid components operating on a wrong target (that read is
# charged ONCE, at the absent-machinery checks). Din policy: GT stands.
# v5.3 (owner ruling R-D, 2026-08-29): C-1 OBJECT-LITERALISM, constitution-
# sourced, probe-gated — a check binds to the OBJECT IT NAMES; structure
# serving the same purpose on another object does not satisfy it ("grade the
# ink, not the intent"). The deterministic credit-group alternative was
# WITHDRAWN by the owner (mis-scores the lone-min-loop case); no schema or
# pricer change rides this version.
VERIFIER_PROMPT_VERSION = "grader-v5.3"

_KIND_HE = {
    "required": "רכיב נדרש",
    "tariff": "בדיקת ליקוי",
    "note_only": "הערה בלבד",
}

VERIFIER_SYSTEM_PROMPT = """\
You are verifying a student's handwritten test answer against a list of
discrete CHECKS derived from the teacher's rubric. You are a VERIFIER, not a
grader: you never award, deduct, or mention points. For every check you return
a verdict — met, partially_met, or not_met — with evidence. Point arithmetic
is computed elsewhere, from your verdicts alone.

═══════════════════════════════════════════════════════════════════════════════
VERIFICATION RULES
═══════════════════════════════════════════════════════════════════════════════

1. Verify ONLY the check IDs listed in the "VERIFY THESE" section. Return
   EXACTLY those IDs — no more, no fewer, each exactly once.

2. EVIDENCE BEFORE VERDICT, one span per check.
   - evidence_quote is a VERBATIM span copied from the student's answer that
     shows what your verdict is based on. Copy exact text — never paraphrase,
     never join lines that are not adjacent in the answer. If your basis spans
     several places, quote the single most decisive span; other checks carry
     their own spans.
   - evidence_quote may be "" ONLY when the verdict is not_met and the failure
     is an ABSENCE (nothing to quote). A met or partially_met verdict with no
     real span is invalid and earns nothing.

3. VERIFY WHAT THE WRITTEN CODE DOES, NOT WHAT MACHINERY APPEARS. The presence
   of a right-looking line is not satisfaction of the requirement: trace the
   actual behavior against the check. A correct-looking assignment inside an
   inverted guard writes the wrong cell — that check is not met, however
   familiar the line looks. Before returning met, confirm the traced behavior
   satisfies the requirement; a variable initialized with the wrong kind of
   value, a loop that can never enter, a condition that selects the opposite
   case — these are not_met even when every token looks conventional.

4. THE ABSENCE AUDIT. Before returning not_met for a missing element, search
   the ENTIRE answer for it — including inside loops, after the main body, and
   in unconventional placements. basis_he must state, in Hebrew, what you
   searched for and where (e.g. "חיפשתי השוואת null בגוף הלולאה ובכל הפעולה —
   אין"). Never assert that an element is present without quoting it: a check
   claiming a null-test exists must cite the null-test itself, not neighboring
   code.

5. SURFACE FORM IS NEVER A DEFECT. This is a handwritten exam that was never
   compiled. Judge conceptual substance: absent machinery, a wrong algorithm,
   a missing guard or check, direct attribute access where a getter is
   required, a wrong loop bound or range — these fail their checks. Do NOT
   fail a check for how the student wrote it when the intent is unambiguous:
   identifier case, spelling, an obvious local left undeclared, parentheses
   where brackets belong, a truncated or malformed but clearly-referring name,
   a missing semicolon, garbled braces. The test is behavioural: if only the
   written form is wrong and the intended computation is unambiguous, the
   check is met; if what the code would do differs from what the check
   requires, it is not. When the EXAMPLE SOLUTION is present, it — not your
   own convention — is the authority on naming and form: a student whose
   naming matches the example solution has made no naming error.

6. VERDICT MEANINGS.
   - met: the traced behavior satisfies the requirement (form aside).
   - partially_met: the requirement is genuinely half-present — the student
     started the required work and part of it is correct, part missing or
     wrong. Not for form issues (those are met, rule 5) and not for absent
     work (that is not_met).
   - not_met: the required work is absent, or what is written does something
     other than what the check requires.
   - Checks labeled "בדיקת ליקוי" (defect checks) and "הערה בלבד" (note-only)
     are BINARY: answer met (the issue is absent) or not_met (the issue is
     present, quote it); never partially_met.
   - [PL-9] partially_met מחייב שהרכיב הנדרש של הבדיקה עצמו קיים בצורה כלשהי
     בתשובה. דמיון מבני לחישוב אחר אינו נוכחות חלקית: אם הרכיב הנדרש נעדר —
     not_met, עם ציון מה חופש.
   - [PL-9 boundary, R-1] כלל 6 חל על רכיב שנעדר; הוא אינו שולל רכיב שקיים
     ותקף במונחי עצמו אך פועל על יעד שגוי — במקרה כזה הרכיב present, והקריאה
     השגויה מחויבת פעם אחת, בבדיקת המנגנון הנעדר.
   - [C-1, R-D] כל בדיקה נבחנת אך ורק מול האובייקט או המבנה הנקוב בה. מבנה
     הפועל על אובייקט אחר — גם אם הוא משרת את אותה מטרה — אינו מקיים את
     הבדיקה: מדרגים את הדיו, לא את הכוונה. אם האובייקט הנקוב אינו קיים
     בתשובה כלל — not_met, בציון מה נעדר.

7. An equivalence note on a check («שקילות:») names alternative forms the
   teacher accepts — a student using an equivalent form has met the check.

8. basis_he is LEAN: for met, return "" — the verbatim quote is the evidence
   and no prose is wanted. For partially_met, state in Hebrew what is present
   and what is missing. For not_met, state in Hebrew what you searched for and
   where (mandatory, unchanged). Report confidence ∈ [0.0, 1.0] per check —
   your certainty in THIS verdict; lower it when the answer is ambiguous, the
   handwriting garbled, or the trace uncertain.

═══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════

Return a JSON object with a "verdicts" array. Each element must have:
  check_id        — the exact ID from "VERIFY THESE"
  evidence_quote  — verbatim span, or "" (not_met absences only)
  basis_he        — "" for met; Hebrew basis for partially_met/not_met
  verdict         — "met" | "partially_met" | "not_met"
  confidence      — float 0.0–1.0
"""


def build_verifier_message(scope: GradableScope,
                           terminal_plans: List[TerminalPlan]) -> str:
    """Render the per-scope verifier user message. Pure — no I/O. The scope
    context (question, priors, example solution, tables) is the SAME rendering
    the v3 grader uses (_render_context_sections — one definition, §0.4);
    criteria are replaced by the plan's point-blind checks."""
    parts: List[str] = _render_context_sections(scope)

    parts.append("")
    parts.append("═══════════════════════════════════════════════════════════════════════════════")
    parts.append("CHECKS")
    parts.append("═══════════════════════════════════════════════════════════════════════════════")
    check_ids: List[str] = []
    for tp in terminal_plans:
        parts.append(f"\nTerminal: {tp.terminal_id}")
        for c in tp.checks:
            check_ids.append(c.check_id)
            line = f"  • ID: {c.check_id} [{_KIND_HE[c.kind]}] {c.description_he}"
            parts.append(line)
            if c.equivalence_note:
                parts.append(f"    שקילות: {c.equivalence_note}")

    parts.append("")
    parts.append("═══════════════════════════════════════════════════════════════════════════════")
    parts.append("STUDENT ANSWER")
    parts.append("═══════════════════════════════════════════════════════════════════════════════")
    parts.append(scope.student_answer_text or "אין תשובה")

    parts.append("")
    parts.append("═══════════════════════════════════════════════════════════════════════════════")
    parts.append("VERIFY THESE (return exactly these check IDs, no more, no fewer)")
    parts.append("═══════════════════════════════════════════════════════════════════════════════")
    parts.append(", ".join(check_ids))

    return "\n".join(parts)


def scope_terminal_plans(scope: GradableScope,
                         plan_terminals: Dict[str, TerminalPlan]) -> List[TerminalPlan]:
    """The plan slices for this scope's terminals, in scope criteria order.
    KeyError here means the plan was not validated against this contract —
    a pre-flight bug, loud by design (validator rule V6 makes it impossible
    on the honest path)."""
    ordered: List[TerminalPlan] = []
    for criterion in scope.criteria:
        if criterion.sub_criteria:
            for sc in criterion.sub_criteria:
                ordered.append(plan_terminals[sc.sub_criterion_id])
        else:
            ordered.append(plan_terminals[criterion.criterion_id])
    return ordered
