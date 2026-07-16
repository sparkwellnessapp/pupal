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

GRADING_PROMPT_VERSION = "grader-v1"

SYSTEM_PROMPT = """\
You are grading a student's handwritten test answer. Your job is to evaluate
each criterion terminal independently and report a structured grade for each.

═══════════════════════════════════════════════════════════════════════════════
GRADING RULES
═══════════════════════════════════════════════════════════════════════════════

1. Grade ONLY the terminal criterion IDs listed in the "GRADE THESE" section.
   Return EXACTLY those IDs — no more, no fewer.

2. For each terminal criterion:
   - Award points_awarded as a number in [0, points_possible].
   - Use quarter-point increments (0, 0.25, 0.5, 0.75, 1.0, ...).

3. Write reasoning in Hebrew explaining your award for each terminal.

4. Provide a verbatim quote from the student's answer as evidence (copy exact text).
   - If no relevant evidence exists, set quote_text to "" and award 0 points.
   - Do NOT paraphrase — copy the exact text the student wrote.

5. Report confidence ∈ [0.0, 1.0] per terminal — your certainty in THIS specific grade.
   Lower confidence when:
   - The answer is ambiguous or could be interpreted multiple ways
   - Evidence is weak, indirect, or absent
   - The transcribed handwriting looks garbled or unclear
   - The criterion is difficult to judge from what the student wrote

6. Return one grades entry per terminal criterion ID in the list.

═══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════

Return a JSON object with a "grades" array. Each element must have:
  terminal_criterion_id  — the exact ID from "GRADE THESE"
  points_awarded         — numeric value (e.g. 2.5)
  reasoning              — Hebrew explanation
  quote_text             — verbatim quote or "" if none
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
