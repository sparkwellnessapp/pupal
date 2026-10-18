"""The planner prompt (PR_grader_v6_options.md §5.2, §5.4). Pure: no I/O, no model.

SYSTEM  = the core constitution (P-1..P-10, subject-agnostic, numbered 1..10 in the
          text) + the subject pack's planner fragment + the pack's precedents
          (constitution clauses, AM-G5) + the three domain-shifted few-shots
          (`examples.py`) + the output contract. Identical for every scope of every
          rubric of one pack, so the provider caches it.
USER    = `render_scope_input(inp)`: a closed-list preamble naming the ONLY ids and
          enum values the model may output, stating P-10, then the scope. Every id is
          an AM-G17 alias (t1, k1, m1, n1 — `stage1_input.planner_aliases`); the scope's
          own id is not rendered at all.

Rule ids (P-1, PL-9, …) are never rendered: everything the planner writes in Hebrew is
read by the teacher, and no grading string she reads names an id (CWV-5). The
precedents are rendered as their Hebrew text alone for the same reason.

A change to any byte of the CS assembly moves the pin in
tests/subjects/test_subject_packs.py — deliberate, logged in RUNLOG, with
PLANNER_PROMPT_VERSION (and PACK_VERSION if a pack file moved) bumped.
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import List, get_args

from app.agents.grader.plan_schemas import CreditElement, PartialFraction

from .examples import FEW_SHOTS, FewShot
from .inputs import AMOUNT_MASK, SPLIT_REFS, ScopePlannerInput, TerminalInput
from .schemas import Decomposition

PLANNER_PROMPT_VERSION = "planner-v6.2"          # [AM-G19] rule 7 amended; element; teacher_span
# [AM-G20, owner rulings 2026-10-18 Item C] rule 7's 2-point line is evaluated on the
# TEACHER'S criterion, so a non_binary part of a split keeps a partial whatever its share.
# Selectable by config (`settings.v6_planner_prompt_version`): v6.2 stays the production
# default until run 11 is adopted, and a v6.2 plan replays to the same bytes and hash.
PLANNER_PROMPT_V63 = "planner-v6.3"
PLANNER_PROMPT_VERSIONS = (PLANNER_PROMPT_VERSION, PLANNER_PROMPT_V63)
AM_G20_VERSIONS = (PLANNER_PROMPT_V63,)

DECOMPOSITIONS = get_args(Decomposition)         # ("as_compiled", "binary", "ladder", "split")
FRACTIONS = tuple(f.value for f in PartialFraction)
DISPOSITIONS = ("fault", "merged", "not_a_deduction")
ELEMENTS = get_args(CreditElement)               # ("binary", "non_binary")
PRE_AM_G19_VERSIONS = ("planner-v6.0", "planner-v6.1")


def am_g19_applies(prompt_version: str) -> bool:
    """[AM-G19] Rule 7 binds outputs of planner-v6.2 on. A recording made under an earlier
    prompt replays without it, so its plan — and its hash — are what they were."""
    return prompt_version not in PRE_AM_G19_VERSIONS


def am_g20_applies(prompt_version: str) -> bool:
    """[AM-G20] rule 7(a)/(b) read the teacher's criterion, not the credit's share."""
    return prompt_version in AM_G20_VERSIONS

PLANNER_CORE = f"""\
You plan how ONE scope of a teacher's rubric (a question, or one sub-question) will be
checked. Later, a verifier reads each student's answer and answers a set of CHECKS: small
multiple-choice questions about the answer. You write those checks and their options, in
Hebrew, from the teacher's own text. You never see a student's answer and you never grade.
Code assigns every id and computes every value: points, partial values and deduction
amounts are never yours.

=== WHAT YOU RECEIVE ===
- The question, and the teacher's example solution when she wrote one.
- Per TERMINAL (her finest scoring unit): its id, its points (context only), her text, and
  the compiler's COMPONENTS, each with its points (context only). A `fixed` component was
  enumerated by her text: phrase it, never split, merge or reorder it. A `monolith` is one
  undivided requirement: you choose how it is checked. A terminal marked COMPILED (levels or
  count) is read-only: do not plan it.
- What a credit is worth: a fixed component's points; for a monolith checked as one credit,
  its points; the credits of a split share the monolith's points evenly.
- NOTE CHECKS: lines she asked to remark on without deducting. Compiled and read-only; never
  turn one into a credit or a fault.
- MARKERS: deduction phrases found in her text, each with its polarity, the terminal where
  she wrote it, and the terminals it may be anchored on. Amounts are masked as {AMOUNT_MASK}.

=== WHAT YOU RETURN ===
- `terminals`: one entry per terminal you plan, with its `decomposition`:
  - as_compiled — the components are `fixed`: one credit per component, in the same order,
    component_ref = the component id.
  - binary — a monolith checked as one credit, no partials; component_ref = its id.
  - ladder — a monolith checked as one credit with 1 or 2 partials; component_ref = its id.
  - split — a monolith split into 2 to 6 credits; component_ref = "n1", "n2", … in order.
  Each credit: description_he (the thing checked), source_span (verbatim from her text, the
  question or the solution), element (binary or non_binary, rule 7), full_label_he and
  absent_label_he (what an answer looks like at full credit and at none), 0 to 2 partials
  (label_he + fraction + teacher_span: her verbatim words when rule 7(b) keeps the partial,
  else null), and equivalence_note_he (forms she accepts) or null. Up to 3
  interpretation_notes_he per terminal.
- `faults`: one per fault. anchor_terminal_id is a candidate anchor of EVERY marker among its
  options; requires_component_ref is the credit on that anchor whose behavior the fault
  modifies, or null; options are 1 to 7 of (marker_id, label_he).
- `dispositions`: exactly one per marker — `fault` (it is an option of a fault), `merged` (into
  another marker of the same fault: merged_into_marker_id and reason_he), or
  `not_a_deduction` (reason_he). A `no_deduct` marker is never a fault option.

=== RULES ===
1. TEACHER'S WORDS. Descriptions and labels reuse the teacher's vocabulary. Every check cites
   a verbatim span.
2. INVENT NOTHING. Add no requirement, fault or condition absent from the teacher's text and
   the example solution.
3. ONE OWNER PER FAULT. When a marker concerns a behavior, the credit for that behavior
   describes the behavior itself, WITHOUT the fault. The fault lives only in its fault check,
   which requires that credit.
4. ONE FAULT, ONE CHECK. Markers that describe severities of the same fault form ONE fault
   whose options are the severities. Independent faults get separate faults. A fault check
   lives on one criterion. The same mistake at two criteria is two fault checks; code links
   them.
5. MUTUALLY EXCLUSIVE OPTIONS. Rewrite overlapping conditions ("at least one" vs. "both")
   into disjoint descriptions, so that exactly one option can match any answer.
6. SAME CONDITION, DIFFERENT AMOUNTS → MERGE. Markers that state the same condition are
   merged even when their (masked) amounts differ: one stays an option, the others are
   `merged` into it, and reason_he says so. Code applies the lenient amount.
7. PARTIAL CREDIT. Decide every credit's `element` first, then its partials.
   - binary: the credit names one atomic element that is either present or absent (a return
     statement, a keyword, a signature token, a single condition).
   - non_binary: an answer can satisfy it in part (several sub-elements, a computation, a
     loop with its body, a structure).
   (a) A non_binary credit worth 2 points or more has at least one partial. Prefer a concrete
       partial state: what is present, and what is missing or wrong. If none can be named,
       use HALF with an observable label of the form "present, but incomplete or containing
       an error". When the credit allows, give two levels: a minor slip (THREE_QUARTERS) and
       a major gap (HALF or QUARTER).
   (b) A credit worth less than 2 points, and every binary credit, has no partial — unless
       the teacher's own text states a partial value for that element. Then write exactly the
       partial she states, and quote her words verbatim in its teacher_span.
   (c) A partial never applies to an answer that addresses a different object, variable,
       collection or quantity than the credit names: that answer takes the absent option. Name
       the credit's own object in every partial label, so it cannot match work on another.
   Never a bare "partially correct".
8. SPLIT ALONG INDEPENDENT FAILURES. Split where one part can be present without the other;
   otherwise don't.
9. AMBIGUITY. (a) Choose the reading most consistent with the question and the example
   solution. (b) If it is still ambiguous, choose the lenient reading. (c) Record the call as
   one teacher-readable Hebrew line, in neutral voice, in interpretation_notes_he.
10. CLOSED LISTS. Never output a number: no points, no value and no amount, in any field or
    label. Choose ids and enum values only from the closed lists you are given.

Everything you write in Hebrew is read by the teacher. Never mention a rule, an id, a check,
an option, the verifier, a model or AI in it.
"""

_RULE_7AB_V62 = """\
   (a) A non_binary credit worth 2 points or more has at least one partial. Prefer a concrete
       partial state: what is present, and what is missing or wrong. If none can be named,
       use HALF with an observable label of the form "present, but incomplete or containing
       an error". When the credit allows, give two levels: a minor slip (THREE_QUARTERS) and
       a major gap (HALF or QUARTER).
   (b) A credit worth less than 2 points, and every binary credit, has no partial — unless
       the teacher's own text states a partial value for that element. Then write exactly the
       partial she states, and quote her words verbatim in its teacher_span.
"""

_RULE_7AB_V63 = """\
   (a) A non_binary credit has at least one partial when the teacher's CRITERION it comes
       from is worth 2 points or more: the component she priced, or the whole monolith when
       you split it — whatever the credit's own share. (A 3-point chemistry requirement
       split into three parts: «balancing the equation» is non_binary and keeps a partial
       although the part is worth 1 point.) Prefer a concrete partial state: what is
       present, and what is missing or wrong. If none can be named, use HALF with an
       observable label of the form "present, but incomplete or containing an error". When
       the credit allows, give two levels: a minor slip (THREE_QUARTERS) and a major gap
       (HALF or QUARTER).
   (b) A credit whose criterion is worth less than 2 points, and every binary credit —
       a binary part of a split included — has no partial, unless the teacher's own text
       states a partial value for that element. Then write exactly the partial she states,
       and quote her words verbatim in its teacher_span.
"""

# [AM-G20] v6.3 = v6.2's exact bytes with rule 7 (a)/(b) replaced; built by replacement so a
# drift in the shared text fails here, and v6.2 itself never moves.
assert PLANNER_CORE.count(_RULE_7AB_V62) == 1, "rule 7(a)/(b) drifted: update both versions"
PLANNER_CORE_V63 = PLANNER_CORE.replace(_RULE_7AB_V62, _RULE_7AB_V63)
_CORES = {PLANNER_PROMPT_VERSION: PLANNER_CORE, PLANNER_PROMPT_V63: PLANNER_CORE_V63}

PRECEDENTS_HEADER = """\
=== PRECEDENTS OF THIS SUBJECT ===
Apply them when you phrase credits and choose partials and faults. Never quote or name them."""

EXAMPLES_HEADER = """\
=== EXAMPLES ===
Three worked examples, from topics unrelated to the rubric you will plan. They show the SHAPE
of a good plan; never copy their wording."""

OUTPUT_CONTRACT = """\
=== OUTPUT ===
Return one JSON object: {"terminals": [...], "faults": [...], "dispositions": [...]}.
Every marker has exactly one disposition; a scope with no markers returns empty lists."""


def planner_system_prompt(profile, version: str = PLANNER_PROMPT_VERSION) -> str:
    """The planner system prompt for a subject pack (`registry.get_profile(key)`), in a
    selectable prompt version (`PLANNER_PROMPT_VERSIONS`)."""
    if version not in _CORES:
        raise ValueError(f"unknown planner prompt version {version!r}; known {PLANNER_PROMPT_VERSIONS}")
    parts: List[str] = [_CORES[version].rstrip("\n")]
    if profile.planner_fragment and profile.planner_fragment.strip():
        parts += ["", "=== SUBJECT GUIDANCE ===", profile.planner_fragment.rstrip("\n")]
    if profile.precedents:
        parts += ["", PRECEDENTS_HEADER]
        parts += [f"- {c.text_he}" for c in profile.precedents]
    parts += ["", EXAMPLES_HEADER]
    for i, ex in enumerate(FEW_SHOTS, 1):
        parts += ["", _render_example(i, ex)]
    parts += ["", OUTPUT_CONTRACT]
    return "\n".join(parts) + "\n"


def _render_example(i: int, ex: FewShot) -> str:
    """The input exactly as a real user message renders; the output as the JSON a
    correct plan returns. Tagged, so the example's own `===` headers cannot be read
    as sections of this prompt."""
    out = json.dumps(ex.output.model_dump(mode="json"), ensure_ascii=False, indent=2)
    return "\n".join([f"--- Example {i}: {ex.title} ---",
                      "<input>", render_scope_input(ex.input), "</input>",
                      "<output>", out, "</output>"])


# ═══════════════════════════════════════════════════════════════════════════
# the user message
# ═══════════════════════════════════════════════════════════════════════════

def _points(d: Decimal) -> str:
    s = format(Decimal(d), "f")
    return s.rstrip("0").rstrip(".") if "." in s else s


def _component_points(c) -> str:
    return "" if c.points is None else f" · points (context only): {_points(c.points)}"


def _ids(values) -> str:
    values = list(values)
    return ", ".join(values) if values else "none"


def _component_line(t: TerminalInput) -> str:
    if t.is_monolith:
        return (f"  {t.terminal_id}: {t.components[0].component_id} [monolith]"
                f" · for a split: {', '.join(SPLIT_REFS)}")
    return f"  {t.terminal_id}: {_ids(c.component_id for c in t.components)} [fixed]"


def render_scope_input(inp: ScopePlannerInput) -> str:
    """The per-scope user message: closed lists first (P-10), then the scope. Pure and
    deterministic; carries no amount (there is none on the input) and no student work."""
    lines: List[str] = [
        "=== CLOSED LISTS — the only ids and values you may output ===",
        f"terminal_id (plan each one): {_ids(t.terminal_id for t in inp.planned_terminals)}",
        f"terminal_id (compiled, read-only — do not plan): "
        f"{_ids(t.terminal_id for t in inp.compiled_terminals)}",
        "component_ref:",
    ]
    lines += [_component_line(t) for t in inp.planned_terminals] or ["  none"]
    lines += [
        f"marker_id: {_ids(m.marker_id for m in inp.markers)}",
        "anchor_terminal_id: a candidate anchor of every marker in the fault (listed per marker)",
        f"decomposition: {' | '.join(DECOMPOSITIONS)}",
        f"element: {' | '.join(ELEMENTS)}",
        f"fraction: {' | '.join(FRACTIONS)}",
        f"disposition: {' | '.join(DISPOSITIONS)}",
        "Never output a number: no points, no value and no amount, in any field or label "
        f"(rule 10). Amounts in the teacher's text are masked as {AMOUNT_MASK}.",
        "",
        "=== SCOPE ===",
        "",
        "=== QUESTION ===",
        inp.question_text.strip() or "(none)",
        "",
        "=== EXAMPLE SOLUTION ===",
        (inp.example_solution or "").strip() or "(none)",
    ]
    for t in inp.terminals:
        lines += ["", f"=== TERMINAL {t.terminal_id} · points (context only): {_points(t.points_possible)} ===",
                  "Teacher's text:", t.teacher_text.strip()]
        if t.compiled is not None:
            lines += [f"COMPILED ({t.compiled.shape}), read-only: «{t.compiled.source_span}»"]
        else:
            lines += ["Components:"]
            lines += [f"  {c.component_id} [{c.status}]{_component_points(c)}: «{c.source_span}»"
                      for c in t.components]
    if inp.notes:
        lines += ["", "=== NOTE CHECKS (compiled, read-only) ==="]
        lines += [f"  {n.terminal_id}: «{n.text_span}»" for n in inp.notes]
    if inp.markers:
        lines += ["", "=== MARKERS ==="]
        for m in inp.markers:
            lines += [f"  {m.marker_id} [{m.polarity}] written in {m.home_terminal_id}"
                      f" · candidate anchors: {', '.join(m.candidate_anchors)}",
                      f"    «{m.text_span}»"]
    return "\n".join(lines)
