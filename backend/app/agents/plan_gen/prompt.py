"""
The generator's prompt, and the scope corpus it reads.

**The corpus IS V9's grounding corpus.** The model is shown exactly the text its
quotes will be checked against, per scope — so a groundable citation is always
reachable, and an ungrounded one is a real failure rather than an artefact of
showing the model something the validator cannot see.

Subject-agnostic by construction (§3.3): nothing here knows about computer
science. Subject-specific clauses arrive through `constitution.clauses_for`,
keyed on `contract.subject`.
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

from app.agents.plan_gen.constitution import Clause

PLAN_GEN_PROMPT_VERSION = "plan-gen/v1"

_TEXT_ATTRS = ("question_text", "text", "title", "example_solution",
               "description", "evaluation_guidance", "notes")
_TABLE_ATTRS = ("trace_tables", "context_tables")


def _texts(node, attrs=_TEXT_ATTRS) -> List[str]:
    out = []
    for attr in attrs:
        value = getattr(node, attr, None)
        if isinstance(value, str) and value.strip():
            out.append(value)
    for attr in _TABLE_ATTRS:
        value = getattr(node, attr, None)
        if value:
            out.append(json.dumps(value, ensure_ascii=False))
    return out


def scope_corpus(question, sub_question, *, include_solution: bool = True) -> str:
    """Everything the teacher wrote that bears on this scope, and nothing else.

    `include_solution=False` is the V-nosol arm: the six production rubrics
    carry no embedded example solution, so that arm measures whether v5 can ship
    to a real teacher TODAY.
    """
    attrs = _TEXT_ATTRS if include_solution else tuple(
        a for a in _TEXT_ATTRS if a != "example_solution")
    parts = _texts(question, tuple(a for a in ("question_text", "title",
                                               "example_solution") if a in attrs))
    node = sub_question or question
    parts += _texts(node, attrs)
    for criterion in getattr(node, "criteria", []) or []:
        parts += _texts(criterion, attrs)
        for sub in (getattr(criterion, "sub_criteria", None) or []):
            parts += _texts(sub, attrs)
    return "\n".join(parts)


SYSTEM_PROMPT = """You decompose a teacher's grading criterion into discrete, \
independently checkable requirements.

You are NOT grading. No student answer exists. You are turning what the teacher \
wrote into a checklist that a later reader will rule on, one item at a time.

RULES, in order of importance.

1. CITE, THEN CLAIM. Every check begins with `rubric_quote`: a VERBATIM span of \
the scope text you were given. Copy it exactly — including any typo or missing \
space. Elide the middle of a long span with … but NEVER paraphrase, and never \
cite text you were not shown. A check you cannot cite is a check you must not \
write.

2. THE POINTS MUST ADD UP EXACTLY. For each terminal, the `points` of its \
`required` checks must sum to EXACTLY that terminal's `points_possible`. Not \
approximately. Every value must be a multiple of the stated precision, and \
`points × partial_fraction` must also be a multiple of it.

3. DECOMPOSE AS FINELY AS THE TEACHER'S OWN TEXT DOES, AND NO FINER. If she \
names three attributes, that is three components. If she writes one \
undifferentiated requirement, that is one check. Over-splitting invents \
distinctions she did not make; under-splitting makes the terminal \
all-or-nothing and destroys the partial credit she intended.

4. THREE KINDS.
   · `required` — earns points. `met` = the requirement is satisfied.
   · `tariff` — a deduction the teacher NAMES ("...להוריד 2"). It earns no \
points; `tariff_amount` is exactly the number she wrote. If she says to charge \
it only once, give every instance the same `charge_group`.
   · `note_only` — she says to note it and NOT deduct ("לציין, לא להוריד").

5. PHRASE EVERY CHECK SO THAT "MET" MEANS SATISFIED. Write the requirement, \
never the defect.

6. NEVER STATE POINTS IN `description_he`. The reader who rules on these checks \
is deliberately blind to the numbers; putting one in the text hands them the \
answer.

7. `equivalence_note` is for alternative forms the scope text or the example \
solution licenses — different names, an optional check the teacher excused. \
Leave it empty when nothing licenses one."""


def build_generation_message(scope_key: Tuple[str, Optional[str]],
                             corpus: str,
                             terminals: List[Tuple[str, str]],
                             precision: str,
                             clauses: List[Clause],
                             subject: Optional[str],
                             programming_language: Optional[str]) -> str:
    """`terminals` is [(terminal_id, points_possible)] — the DERIVED set. The
    model never chooses which terminals exist (validator V6); it only fills
    them, and echoing the ids back lets assembly catch a misalignment."""
    qid, sqid = scope_key
    lines = [
        f"SUBJECT: {subject or 'unspecified'}",
    ]
    if programming_language:
        lines.append(f"LANGUAGE: {programming_language}")
    lines += [
        f"POINT PRECISION: every value must be a multiple of {precision}",
        f"SCOPE: {qid}" + (f".{sqid}" if sqid else ""),
        "",
        "=== THE TEACHER'S TEXT FOR THIS SCOPE ===",
        "(your rubric_quote must be a verbatim span of what follows)",
        corpus,
        "",
        "=== TERMINALS TO DECOMPOSE ===",
        "(exactly these, no more and no fewer; required points must sum to the "
        "stated value for each)",
    ]
    for tid, pts in terminals:
        lines.append(f"  · {tid} — points_possible = {pts}")

    policy = [c for c in clauses if c.kind == "policy"]
    authoring = [c for c in clauses if c.kind == "authoring"]
    if authoring:
        lines += ["", "=== AUTHORING RULES ==="]
        lines += [f"  · [{c.clause_id}] {c.text_he}" for c in authoring]
    if policy:
        lines += ["", "=== STANDING POLICY (append to a check only where it "
                       "bears on that check) ==="]
        lines += [f"  · [{c.clause_id}] {c.text_he}" for c in policy]
    return "\n".join(lines)


def repair_message(errors: List[str]) -> str:
    """Validator errors are already tagged and human-readable; they go back
    verbatim rather than being re-narrated, so the model sees the exact rule it
    broke and the exact arithmetic."""
    return ("Your previous decomposition failed validation. Fix EXACTLY these "
            "and change nothing else:\n\n" + "\n".join(f"  · {e}" for e in errors))
