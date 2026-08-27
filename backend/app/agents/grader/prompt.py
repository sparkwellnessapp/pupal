"""
GraderAgent prompt builder — pure render functions, no I/O.

GRADING_PROMPT_VERSION is bumped by hand when the system prompt or rendering
logic changes in a way that could affect grades. This constant is stamped into
every GradedTestDraft.prompt_version for attribution and eval regression tracking.
"""
from __future__ import annotations

import json
from typing import List

from app.schemas.gradable import GradableScope

# grader-v3 (owner ruling 2026-08-27, E7): adds rule 3 — SURFACE FORM IS NOT A
# DEDUCTION. Ratified clause, derived from PL-1 / PL-10+AUDIT-2 / PL-2 / R-α and
# the rubric's own conceptual deduction vocabulary; effectively constitution
# entry #1 (§13.2 SEED). The behavioural test is the discriminator; the
# never-creates-credit sentence encodes kill-criterion K1 as a constraint the
# model reads, not merely a detector we measure afterwards.
# grader-v4 (owner ruling 2026-08-27, E8): adds rule 4 — DEDUCTION SIZE IS SET BY
# THE RUBRIC, NOT BY YOU. Diagnosis from the E7 run: rule 3 established WHAT
# counts as a conceptual defect but left HOW MUCH it costs to the model's
# discretion. Consequence measured: zero-inflation (GT-PARTIAL->AI-ZERO 54->72,
# GT-FULL->AI-ZERO 22->28) which cancelled most of the +53.75 recovered by rule
# 3, and per-fixture instability (dan ai_total_spread 3.25 -> 14.00) driven by
# the model freely choosing deduction magnitudes. Rule 4 supplies an ORDER OF
# AUTHORITY (named tariff -> criterion itemisation -> share of required work
# present) rather than a single source, because the rubric is silent on many
# cases and a rubric-only rule would leave no rule there at all (owner ruling).
# The "present but imperfect earns partial, not zero" sentence is the direct
# anti-zero-inflation counter; "charge each defect once" encodes the
# charge-once precedent from the F5 GT session.
# grader-v2 (owner lever, 2026-08-25; canonical name ruled in the PR-G1 v2
# carryover — supersedes the interim "grader-v2-evidence-first" string):
# TerminalGrade's field order is quote_text -> reasoning -> points_awarded ->
# confidence. Field order flows into the structured-output JSON schema and
# therefore into DECODE ORDER: the award is generated conditioned on the
# evidence the model just located and the reasoning it just wrote —
# evidence-before-verdict, mechanically enforced. The rule/format ordering
# below mirrors it (sentences unchanged from grader-v1; only sequence moved).
GRADING_PROMPT_VERSION = "grader-v4"

# PR-G1 v2 (RATIFIED 2026-08-25): the prefix-context seam, gated by env flag.
# The stamped prompt_version is a PURE FUNCTION of code + flag:
#   flag off -> GRADING_PROMPT_VERSION            (render unchanged)
#   flag on  -> GRADING_PROMPT_VERSION + "+priorctx" (prior parts in reading order)
_PRIOR_CONTEXT_FLAG = "GRADER_PRIOR_CONTEXT_ENABLED"

_PRIOR_PARTS_HEADER = "חלקים קודמים — להקשר בלבד: אין לנקד אותם ואין לצטט מתוכם"


def prior_context_enabled() -> bool:
    import os
    return os.environ.get(_PRIOR_CONTEXT_FLAG, "").strip().lower() in ("1", "true", "yes", "on")


def effective_prompt_version() -> str:
    return GRADING_PROMPT_VERSION + ("+priorctx" if prior_context_enabled() else "")

SYSTEM_PROMPT = """\
You are grading a student's handwritten test answer. Your job is to evaluate
each criterion terminal independently and report a structured grade for each.

═══════════════════════════════════════════════════════════════════════════════
GRADING RULES
═══════════════════════════════════════════════════════════════════════════════

1. Grade ONLY the terminal criterion IDs listed in the "GRADE THESE" section.
   Return EXACTLY those IDs — no more, no fewer.

2. Provide a verbatim quote from the student's answer as evidence (copy exact text).
   - If no relevant evidence exists, set quote_text to "" and award 0 points.
   - Do NOT paraphrase — copy the exact text the student wrote.

3. SURFACE FORM IS NOT A DEDUCTION. This is a handwritten exam that was never
   compiled. Deduct for conceptual defects — including, but not limited to,
   absent machinery, a wrong algorithm, a missing guard or check, direct
   attribute access where the rubric requires a getter, a wrong loop bound or
   range. Do NOT deduct for how the student wrote it when the intent is
   unambiguous: identifier case, spelling, an obvious local left undeclared,
   parentheses where brackets belong, a truncated or malformed but
   clearly-referring name, a missing semicolon, or garbled braces. The test is
   behavioural: if only the written form is wrong and the intended computation
   is unambiguous, it is form; if what the code would do differs from what the
   criterion requires, it is conceptual. This rule never creates credit — a
   criterion whose required work is absent scores zero however well the rest is
   written. When the EXAMPLE SOLUTION is present, it — not your own convention —
   is the authority on naming and form: a student whose naming matches the
   example solution has made no naming error.

4. DEDUCTION SIZE IS SET BY THE RUBRIC, NOT BY YOU. Start from the full
   points_possible and subtract only for defects you have actually identified.
   For the size of each deduction, use this order of authority:
   (a) If the criterion, its Guidance or its Notes names a penalty for this
       defect, apply exactly that number — no more. Where the rubric says a
       point should be noted rather than deducted, deduct nothing and record
       the observation in your reasoning instead.
   (b) Otherwise, if the criterion itemises its own components with point
       values, deduct only the value of the components that are missing or
       wrong. Every other component still earns its points.
   (c) Otherwise, judge how much of the work the criterion requires is present
       in the answer, and award that share of points_possible.
   A defect never costs more than the component it belongs to. A component that
   is present but imperfect earns partial credit, not zero. Award zero only
   when nothing the criterion asks for appears in the answer. Charge each
   distinct defect once, at the criterion whose requirement it violates — if
   the same mistake is visible again under another criterion, do not deduct for
   it a second time.

5. Write reasoning in Hebrew explaining your award for each terminal.

6. For each terminal criterion:
   - Award points_awarded as a number in [0, points_possible].
   - Use quarter-point increments (0, 0.25, 0.5, 0.75, 1.0, ...).

7. Report confidence ∈ [0.0, 1.0] per terminal — your certainty in THIS specific grade.
   Lower confidence when:
   - The answer is ambiguous or could be interpreted multiple ways
   - Evidence is weak, indirect, or absent
   - The transcribed handwriting looks garbled or unclear
   - The criterion is difficult to judge from what the student wrote

8. Return one grades entry per terminal criterion ID in the list.

═══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════

Return a JSON object with a "grades" array. Each element must have:
  terminal_criterion_id  — the exact ID from "GRADE THESE"
  quote_text             — verbatim quote or "" if none
  reasoning              — Hebrew explanation
  points_awarded         — numeric value (e.g. 2.5)
  confidence             — float 0.0–1.0
"""


def _get_terminal_ids(scope: GradableScope) -> List[str]:
    """Return ordered list of terminal criterion IDs for this scope."""
    terminals: List[str] = []
    for criterion in scope.criteria:
        if criterion.sub_criteria:
            for sc in criterion.sub_criteria:
                terminals.append(sc.sub_criterion_id)
        else:
            terminals.append(criterion.criterion_id)
    return terminals


def build_user_message(scope: GradableScope) -> str:
    """
    Render the per-scope user message. Pure function — no I/O, no side effects.
    Called once per scope per grade() invocation.
    """
    parts: List[str] = []

    # ── Question / sub-question text ────────────────────────────────────────
    parts.append("═══════════════════════════════════════════════════════════════════════════════")
    parts.append("QUESTION")
    parts.append("═══════════════════════════════════════════════════════════════════════════════")
    if scope.question_text:
        parts.append(scope.question_text)

    # ── PR-G1 v2: prior parts, exam reading order (flag-gated) ──────────────
    # Inserted between the parent stem and the current part — exactly where
    # the student read them. When the flag is off (or there are no priors)
    # this block emits NOTHING and the render is byte-identical to grader-v2
    # (pinned by test_flag_off_prompt_byte_identical_to_prechange).
    if prior_context_enabled() and scope.prior_parts:
        parts.append("")
        parts.append(_PRIOR_PARTS_HEADER)
        for pp in scope.prior_parts:
            parts.append("")
            parts.append(f"--- תת-שאלה {pp.sub_question_id} ---")
            if pp.sub_question_text:
                parts.append(pp.sub_question_text)
            if pp.example_solution:
                parts.append("פתרון לדוגמה:")
                parts.append(pp.example_solution)
            parts.append("תשובת התלמיד:")
            parts.append("«לא נענה»" if (pp.answer_missing or not pp.student_answer_text)
                          else pp.student_answer_text)

    if scope.sub_question_text:
        parts.append("")
        parts.append("SUB-QUESTION:")
        parts.append(scope.sub_question_text)

    # ── Example solution (model answer) ─────────────────────────────────────
    if scope.example_solution:
        parts.append("")
        parts.append("═══════════════════════════════════════════════════════════════════════════════")
        parts.append("EXAMPLE SOLUTION")
        parts.append("═══════════════════════════════════════════════════════════════════════════════")
        parts.append(scope.example_solution)

    # ── Pedagogical context tables ───────────────────────────────────────────
    if scope.trace_tables or scope.context_tables:
        parts.append("")
        parts.append("═══════════════════════════════════════════════════════════════════════════════")
        parts.append("TABLES / CONTEXT")
        parts.append("═══════════════════════════════════════════════════════════════════════════════")
        if scope.trace_tables:
            parts.append("Trace tables:")
            parts.append(json.dumps(scope.trace_tables, ensure_ascii=False, indent=2))
        if scope.context_tables:
            parts.append("Context tables:")
            parts.append(json.dumps(scope.context_tables, ensure_ascii=False, indent=2))

    # ── Criteria tree ────────────────────────────────────────────────────────
    parts.append("")
    parts.append("═══════════════════════════════════════════════════════════════════════════════")
    parts.append("GRADING CRITERIA")
    parts.append("═══════════════════════════════════════════════════════════════════════════════")

    for criterion in scope.criteria:
        parts.append(f"\nCriterion: {criterion.description} ({criterion.points} pts)")
        if criterion.evaluation_guidance:
            parts.append(f"Guidance: {criterion.evaluation_guidance}")
        if criterion.notes:
            parts.append(f"Notes: {criterion.notes}")

        if criterion.sub_criteria:
            parts.append("Grade each sub-criterion independently:")
            for sc in criterion.sub_criteria:
                parts.append(f"  • ID: {sc.sub_criterion_id} | {sc.description} ({sc.points} pts)")
        else:
            parts.append(f"  • ID: {criterion.criterion_id} [grade this criterion directly]")

    # ── Student answer ───────────────────────────────────────────────────────
    parts.append("")
    parts.append("═══════════════════════════════════════════════════════════════════════════════")
    parts.append("STUDENT ANSWER")
    parts.append("═══════════════════════════════════════════════════════════════════════════════")
    parts.append(scope.student_answer_text or "אין תשובה")

    # ── Terminal IDs the LLM must grade ─────────────────────────────────────
    terminal_ids = _get_terminal_ids(scope)
    parts.append("")
    parts.append("═══════════════════════════════════════════════════════════════════════════════")
    parts.append("GRADE THESE (return exactly these IDs, no more, no fewer)")
    parts.append("═══════════════════════════════════════════════════════════════════════════════")
    parts.append(", ".join(terminal_ids))

    return "\n".join(parts)