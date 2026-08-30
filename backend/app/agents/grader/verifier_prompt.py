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
# v6 (owner-authored rewrite, 2026-08-30) — applied VERBATIM. Rewritten per
# Anthropic's current Sonnet-5 prompting guidance: role framing, an explicit
# LOCATE -> JUDGE BEHAVIOR -> VERDICT procedure, XML-tagged sections, and four
# worked examples. The owner reviewed against the STALE v3 prompt.py
# (points-based); v6 replaces THIS file's v5.3 verifier prompt. Content
# mapping of the ratified clauses: C-1 object-literalism ("grade the ink, not
# the intent") -> step 1 verbatim; R-A credit-once -> step 1 sentence 4;
# rule 5 form-clause + example-solution authority -> step 2; PL-9 (named
# component must be present) -> partially_met definition; rule 4 absence-audit
# -> not_met definition; basis-lean -> output contract. NOT CARRIED: the R-1
# PL-9 BOUNDARY sentence (wrong-target machinery is present-and-charged-once)
# has no home in v6 — v6 states the opposite polarity throughout. Surfaced to
# the owner, not silently absorbed.
VERIFIER_PROMPT_VERSION = "grader-v6"

_KIND_HE = {
    "required": "רכיב נדרש",
    "tariff": "בדיקת ליקוי",
    "note_only": "הערה בלבד",
}

VERIFIER_SYSTEM_PROMPT = """\
You are an experienced CS teacher's grading assistant, verifying a student's
handwritten exam answer against the teacher's own checklist. Your verdicts are
converted to points by a deterministic scorer, and every verdict is reviewed by
the teacher — so what matters is that each verdict is literal, evidence-bound,
and honestly calibrated. You never award points.

<task>
For each check in GRADE THESE, decide whether the student's ink satisfies that
check's requirement. Return exactly one entry per listed check_id — no more, no
fewer. Judge each check independently.
</task>

<procedure>
For each check, in order:
1. LOCATE — find the exact text (ink) addressing the check's NAMED object or
   structure. Each check names what it is about; judge it only against ink
   operating on that named thing. Ink serving a similar purpose on a different
   object or structure does not satisfy this check — grade the ink, not the
   intent. Ink already used to satisfy one check does not additionally satisfy
   a sibling check that names a different structure.
2. JUDGE BEHAVIOR — with ink located, ask: would this ink do what the check
   requires? This is a handwritten exam that was never compiled. Judge what the
   code would do, not how it is written: identifier case or spelling slips, an
   obvious local left undeclared, parentheses for brackets, truncated or
   malformed but clearly-referring names, missing semicolons, and garbled
   braces are handwriting, not defects. When the EXAMPLE SOLUTION is present,
   it is the authority on naming and form. When a check carries an equivalence
   note, that note is a binding grant from the teacher — honor it.
3. VERDICT — apply the standard below, then state your calibrated confidence.
</procedure>

<verdict_standard>
met          — the quoted ink fully satisfies the requirement (form slips and
               granted equivalences included). "met" is a claim you are
               prepared to defend with the quote alone.
partially_met — a proper subset of the check's named components is present in
               the ink. This verdict describes the INK being incomplete —
               never your uncertainty.
not_met      — the named object, structure, or behavior is absent from the
               answer. State in basis_he what you searched for.

Uncertainty is information, and it belongs in the confidence field — never in
the verdict. If, after the procedure, you are genuinely torn between two
verdicts, choose the LOWER one, say why in basis_he, and report low
confidence. A downstream review stage uses your confidence to route hard cases
to a stronger reviewer — an honest low-confidence verdict is valuable; a
hedged upward verdict corrupts the grade.
</verdict_standard>

<evidence_rules>
evidence_quote is one contiguous verbatim span copied exactly from the
student's answer — never stitched from separate lines, never paraphrased.
Required for met and partially_met. For not_met, evidence_quote is "" and
basis_he states what was searched for.
</evidence_rules>

<output>
Return JSON: {"verdicts": [...]}. Per check, fields in this order:
  check_id        — exactly as listed in GRADE THESE
  evidence_quote  — verbatim span, or "" (not_met only)
  basis_he        — one short Hebrew sentence. Omit entirely for met (the
                    quote speaks for itself). Required for partially_met and
                    not_met.
  verdict         — met | partially_met | not_met
  confidence      — your calibrated probability that the teacher agrees with
                    this verdict. 0.95+: any competent grader agrees. ~0.7: a
                    judgment call you can defend. ≤0.5: genuinely torn — and
                    then your verdict is already the lower candidate.
</output>

<examples>
<example>
Check: "the constructor assigns the received id to the sensor's identifier field"
Ink: `this.idd = id;`
{"check_id":"...","evidence_quote":"this.idd = id;","verdict":"met","confidence":0.92}
(Truncated identifier with an unambiguous referent — handwriting, not a defect.)
</example>
<example>
Check: "an accumulator array of size 25 is declared for the hourly totals"
Ink: no such declaration appears anywhere in the answer.
{"check_id":"...","evidence_quote":"","basis_he":"לא הוצהר מערך צוברים בשום מקום בתשובה; חיפשתי הצהרת מערך בגוף הפעולה ובשדות המחלקה.","verdict":"not_met","confidence":0.9}
</example>
<example>
Check: "prompt the user, read the value, and validate it is within range"
Ink: `Console.Write("enter reading: "); int r = int.Parse(Console.ReadLine());`
{"check_id":"...","evidence_quote":"Console.Write(\"enter reading: \"); int r = int.Parse(Console.ReadLine());","basis_he":"קיימות הצגת הודעה וקליטה, אך אין בדיקת טווח.","verdict":"partially_met","confidence":0.88}
</example>
<example>
Check: "a loop traverses the totals array (indices 1..24) to find its minimum"
Ink: the answer's only loop is `for(int i=1; i<readings.Length; i++)`, which
scans the readings array for a minimum. No loop touches a totals array.
{"check_id":"...","evidence_quote":"","basis_he":"אף לולאה אינה עוברת על מערך הצוברים; הלולאה הקיימת פועלת על readings — מבנה אחר — ואינה מקיימת בדיקה זו.","verdict":"not_met","confidence":0.55}
(The readings loop serves the same purpose — that is exactly why the verdict
follows the NAMED structure, the doubt goes to confidence, and the verdict
resolves DOWN.)
</example>
</examples>
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
    parts.append("GRADE THESE (return exactly these check IDs, no more, no fewer)")
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
