"""
The grader-v6 verifier prompt (PR_grader_v6_options.md §6.1) — pure render functions.

SYSTEM = the core `grader-v6.0` rules V-1..V-7 (subject-agnostic) + the pack's
         verifier fragment (CS: grader-v5.4's own rules 3-5 + rule-6 clauses,
         verbatim by AM-G5). Identical for every scope of one pack: the cached prefix.
USER   = the scope context (the SAME `_render_context_sections` v3 and v5 render —
         one definition), then the CHECKS, then the student's approved answer.

Two closed-world facts make the payload safe (§6.1, AM-G17):
  * NO VALUES. No points, option values, amounts or fractions reach the verifier
    (`test_verifier_payload_has_no_values`). It picks options by their labels.
  * ALIASES ONLY. Checks are `c1…` and each check's options `o1…`, issued by an
    `AliasTable` that is a pure function of the scope's checks (`verifier_aliases`);
    the grader maps the output back with the same table. A real check id such as
    `q1.א.c0.c1` or a code-assigned option id never appears.
"""
from __future__ import annotations

from typing import Dict, List, Sequence

from app.agents.grader.payload_aliases import AliasTable
from app.agents.grader.plan_schemas import PlanCheckV6
from app.agents.grader.prompt import _render_context_sections
from app.schemas.gradable import GradableScope

VERIFIER_V6_PROMPT_VERSION = "grader-v6.0"

_RULE = "═" * 79

VERIFIER_V6_CORE = """\
You verify a student's answer against a list of CHECKS derived from the teacher's rubric.
You are a VERIFIER, not a grader: you never award, deduct or mention points. For every check
you choose exactly ONE of its options, with evidence. Points are computed elsewhere, from your
choices alone.

Every check has a ROLE:
- CREDIT — something the answer should do. Its options run from fully present to absent; its
  LAST option is the zero option: nothing of it is in the answer.
- FAULT — one specific mistake. Its FIRST option means the mistake is NOT in the answer; the
  others are the forms or severities of the mistake.
- NOTE — something to remark on, never scored. FIRST option: not present; second: present.

RULES
1. ONE OPTION PER CHECK. Return every check listed under VERIFY THESE, each exactly once, with
   exactly one of that check's own options. Options are mutually exclusive: choose the one whose
   description fits the answer.
2. QUOTE BEFORE DECIDING. Write evidence_quote first. For every option other than a CREDIT
   check's zero option or a FAULT or NOTE check's first option, copy the SHORTEST verbatim span
   of the student's answer that shows it. Copy exact text: never paraphrase, never join lines
   that are not adjacent in the answer.
3. AN OMISSION IS QUOTED WHERE IT BELONGS. When a FAULT is something missing, quote the part of
   the answer where the missing element should have been.
4. ABSENCE IS NAMED, NOT QUOTED. For a CREDIT check's zero option, leave evidence_quote empty
   and write absence_pointer_he: one Hebrew line of at most 120 characters naming what the
   answer contains in its place, or «אין תשובה». For every other option absence_pointer_he is "".
5. A FAULT NEEDS ITS BEHAVIOR. If a FAULT check describes a behavior the answer does not
   contain, choose its first option.
6. SUBSTANCE OVER SURFACE FORM. Judge what the answer does, not how neatly it is written; the
   subject guidance below says what that means in this subject.
7. THE EXAMPLE SOLUTION IS ONE CORRECT ANSWER, NOT THE ONLY ONE.
8. USE ONLY THE IDS YOU ARE SHOWN: the check ids (c1, c2, …) and, per check, its option ids
   (o1, o2, …).
"""

SUBJECT_HEADER = """\
=== SUBJECT GUIDANCE ===
Part of this guidance may use an older vocabulary: read «met» as a CREDIT check's full option
(for a FAULT check: its first option, the mistake is absent), «not_met» as a CREDIT check's zero
option (for a FAULT check: an option naming the mistake), «partially_met» as a partial option,
and «basis_he» as absence_pointer_he."""

OUTPUT_CONTRACT = """\
=== OUTPUT ===
Return {"verdicts": [{"check_id", "evidence_quote", "absence_pointer_he", "option_id"}, ...]}:
one entry per check, evidence before the decision."""

_ROLE = {"credit": "CREDIT", "fault": "FAULT", "note": "NOTE"}


def verifier_v6_system_prompt(profile) -> str:
    parts = [VERIFIER_V6_CORE.rstrip("\n")]
    if profile.verifier_fragment and profile.verifier_fragment.strip():
        parts += ["", SUBJECT_HEADER, profile.verifier_fragment.rstrip("\n")]
    parts += ["", OUTPUT_CONTRACT]
    return "\n".join(parts) + "\n"


class VerifierAliases:
    """[AM-G17] One scope call's aliases: checks c1…, and per check its options o1…
    in display order. A pure function of the scope's checks in plan order."""

    def __init__(self, checks: Sequence[PlanCheckV6]):
        self.checks = AliasTable((("c", [c.check_id for c in checks]),))
        self._opt: Dict[str, AliasTable] = {
            c.check_id: AliasTable((("o", [o.option_id for o in c.options]),)) for c in checks}

    def option_alias(self, check_id: str, option_id: str) -> str:
        return self._opt[check_id].alias(option_id)

    def option_real(self, check_id: str, alias: str):
        """The real option id, or None for an alias this check did not issue."""
        table = self._opt.get(check_id)
        return None if table is None else table.real(alias)


def verifier_aliases(checks: Sequence[PlanCheckV6]) -> VerifierAliases:
    return VerifierAliases(checks)


def build_verifier_v6_message(scope: GradableScope, checks: Sequence[PlanCheckV6],
                              aliases: VerifierAliases) -> str:
    """The per-scope user message. Pure. `checks` are the scope's plan checks in
    plan order (credit, fault, note within each terminal)."""
    return "\n".join(build_verifier_v6_parts(scope, checks, aliases))


def build_verifier_v6_parts(scope: GradableScope, checks: Sequence[PlanCheckV6],
                            aliases: VerifierAliases):
    """(rubric part, student part). The rubric part — context + checks — is identical for
    every student of the exam: the cached prefix (CL-2). The student part follows it."""
    parts: List[str] = _render_context_sections(scope)
    parts += ["", _RULE, "CHECKS", _RULE]
    for c in checks:
        cid = aliases.checks.alias(c.check_id)
        parts.append(f"\n{cid} [{_ROLE[c.role]}] {c.description_he}")
        if c.equivalence_note_he:
            parts.append(f"   שקילות: {c.equivalence_note_he}")
        for o in c.options:
            parts.append(f"   {aliases.option_alias(c.check_id, o.option_id)}: {o.label_he}")
    student = ["", _RULE, "STUDENT ANSWER", _RULE, scope.student_answer_text or "אין תשובה",
               "", _RULE, "VERIFY THESE (each exactly once)", _RULE,
               ", ".join(aliases.checks.alias(c.check_id) for c in checks)]
    return "\n".join(parts), "\n".join(student)
