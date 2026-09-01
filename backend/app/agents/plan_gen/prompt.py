"""
The generator's prompt, and the scope corpus it reads.

**The corpus IS V9's grounding corpus.** The model is shown exactly the text its
quotes will be checked against, per scope — so a groundable citation is always
reachable, and an ungrounded one is a real failure rather than an artefact of
showing the model something the validator cannot see.

**Deductions are DETECTED, not noticed (plan-gen/v2).** Phase 0 measured tariff
recall 11/14; the one derivable miss was read conceptually and then mis-anchored
and mis-valued (amount 1 where the teacher wrote 3). Locating a deduction phrase
in Hebrew text, copying its number, and knowing which node's text contains it are
string and lookup tasks — deterministic, and now done in code. The model disposes
of a supplied list; it never has to notice. Only "which sub-criterion does this
modify" remains judgement, and it is a bounded choice among named candidates.

Subject-agnostic by construction (§3.3): nothing here knows about computer
science. Subject-specific clauses arrive through `constitution.clauses_for`,
keyed on `contract.subject`.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

from app.agents.plan_gen.constitution import Clause

PLAN_GEN_PROMPT_VERSION = "plan-gen/v2"

_TEXT_ATTRS = ("question_text", "text", "title", "example_solution",
               "description", "evaluation_guidance", "notes")
_TABLE_ATTRS = ("trace_tables", "context_tables")

# ── Deterministic deduction detection ────────────────────────────────────────
# Calibration target (red-first): every one of the reference plan's 12
# generated-source tariffs must be detected from its own source text, and the
# single note_only must be detected with polarity="no_deduct". Patterns are
# extended only to satisfy that target — never to make a candidate plan pass.

_NUM = r"(\d+(?:[.,]\d+)?)"

# Order matters: negative forms are tested first so "לא להוריד" is never read
# as a deduction.
_NO_DEDUCT_PATTERNS = (
    r"לא\s+להוריד",
    r"אין\s+להוריד",
    r"לא\s+מורידים",
    r"do\s+not\s+deduct",
)
_DEDUCT_PATTERNS = (
    rf"להוריד\s+{_NUM}",
    rf"יש\s+להוריד\s+{_NUM}",
    rf"מורידים\s+{_NUM}",
    rf"הורדה\s+של\s+{_NUM}",
    rf"מינוס\s+{_NUM}",
    rf"deduct\s+{_NUM}",
    rf"minus\s+{_NUM}",
    rf"[-–]\s*{_NUM}\s*(?:נקודות|נקודה|נק['׳]?|points?|pts?)",
)

# A detected phrase is reported with surrounding context so the model can judge
# what it modifies. Sentence-ish boundaries for RTL rubric prose.
_CLAUSE_SPLIT = re.compile(r"[.\n·•]|(?<=\s)-\s")


class DetectedDeduction(NamedTuple):
    marker_id: str                      # d1, d2, ...
    quote: str                          # verbatim clause containing the phrase
    amount: Optional[Decimal]           # captured number; None when polarity is no_deduct
    polarity: str                       # "deduct" | "no_deduct"
    source_field: str                   # which attribute the phrase was found in
    candidate_terminal_ids: Tuple[str, ...]   # terminals derived from the owning node


def _clause_around(text: str, start: int, end: int) -> str:
    """The verbatim clause containing [start, end) — never a paraphrase."""
    left = 0
    right = len(text)
    for m in _CLAUSE_SPLIT.finditer(text):
        if m.end() <= start:
            left = m.end()
        elif m.start() >= end:
            right = m.start()
            break
    return text[left:right].strip()


def _scan(text: str) -> List[Tuple[str, Optional[Decimal], str]]:
    hits: List[Tuple[str, Optional[Decimal], str]] = []
    claimed: List[Tuple[int, int]] = []

    def overlaps(a: int, b: int) -> bool:
        return any(not (b <= s or a >= e) for s, e in claimed)

    for pat in _NO_DEDUCT_PATTERNS:
        for m in re.finditer(pat, text):
            if overlaps(*m.span()):
                continue
            claimed.append(m.span())
            hits.append((_clause_around(text, *m.span()), None, "no_deduct"))
    for pat in _DEDUCT_PATTERNS:
        for m in re.finditer(pat, text):
            if overlaps(*m.span()):
                continue
            claimed.append(m.span())
            raw = m.group(1).replace(",", ".")
            hits.append((_clause_around(text, *m.span()), Decimal(raw), "deduct"))
    return hits


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


def _terminals_of(criterion) -> Tuple[str, ...]:
    subs = getattr(criterion, "sub_criteria", None) or []
    if subs:
        return tuple(s.sub_criterion_id for s in subs)
    return (criterion.criterion_id,)


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


def detect_deductions(question, sub_question, *,
                      include_solution: bool = True) -> List[DetectedDeduction]:
    """Every deduction phrase in this scope's text, with its number and the
    terminals of the node whose text contains it.

    Deterministic and total: the model is handed this list and must dispose of
    every entry (validator V11). It is never asked to find them.
    """
    attrs = _TEXT_ATTRS if include_solution else tuple(
        a for a in _TEXT_ATTRS if a != "example_solution")
    node = sub_question or question
    found: List[DetectedDeduction] = []
    seen: set = set()

    def add(owner_terminals: Tuple[str, ...], field: str, text: str) -> None:
        for quote, amount, polarity in _scan(text):
            key = (quote, str(amount), polarity)
            if key in seen:
                continue
            seen.add(key)
            found.append(DetectedDeduction(
                marker_id=f"d{len(found) + 1}",
                quote=quote,
                amount=amount,
                polarity=polarity,
                source_field=field,
                candidate_terminal_ids=owner_terminals,
            ))

    all_terminals: List[str] = []
    for criterion in getattr(node, "criteria", []) or []:
        all_terminals.extend(_terminals_of(criterion))

    # Scope-level prose owns every terminal in the scope as a candidate.
    for field in attrs:
        value = getattr(node, field, None)
        if isinstance(value, str) and value.strip():
            add(tuple(all_terminals), f"scope.{field}", value)

    for criterion in getattr(node, "criteria", []) or []:
        owners = _terminals_of(criterion)
        for field in attrs:
            value = getattr(criterion, field, None)
            if isinstance(value, str) and value.strip():
                add(owners, f"{criterion.criterion_id}.{field}", value)
        for sub in (getattr(criterion, "sub_criteria", None) or []):
            for field in attrs:
                value = getattr(sub, field, None)
                if isinstance(value, str) and value.strip():
                    add((sub.sub_criterion_id,), f"{sub.sub_criterion_id}.{field}", value)
    return found


SYSTEM_PROMPT = """You decompose a teacher's grading criterion into discrete, \
independently checkable requirements.

You are NOT grading. No student answer exists. You are turning what the teacher \
wrote into a checklist that a later reader will rule on, one item at a time. \
That reader never sees her rubric — only your checks. Anything she wrote that \
changes a grade must survive into a check, or the grade will never apply it.

Work through these three steps in order.

STEP 1 — DISPOSE OF EVERY DETECTED DEDUCTION.
The message gives you DEDUCTIONS DETECTED: every deduction phrase found in this \
scope's text, each with an id, the verbatim clause, the number the teacher \
wrote, and the terminal(s) whose text contains it. The list is mechanical and \
exhaustive — finding them is not your job. Disposing of each one is.

Return exactly one disposition per entry:
 · `tariff` — she deducts. Emit a tariff check. Its `tariff_amount` is the \
number given in the entry, copied verbatim. Never re-derive that number, never \
round it, never substitute your own judgement of what the deduction is worth.
 · `note_only` — her text says to record it and not deduct.
 · `not_a_deduction` — the phrase is not a grading instruction at all. Say why.

ANCHORING. If the entry lists one candidate terminal, anchor there. If it lists \
several, anchor to the one whose requirement the deduction modifies, and name \
your reason in the disposition. A deduction anchored to the wrong terminal fires \
on the wrong work — it is as wrong as a missing one.

CHARGE GROUPS. If her text says a deduction is charged only once across several \
places, give every instance the same `charge_group`.

STEP 2 — DECOMPOSE THE REQUIRED POINTS.
For each terminal, write the `required` checks whose points sum to EXACTLY its \
`points_possible`. Decompose as finely as the teacher's own text does and no \
finer: if she names three attributes, that is three components; if she writes one \
undifferentiated requirement, that is one check. Over-splitting invents \
distinctions she did not make; under-splitting makes the terminal all-or-nothing \
and destroys the partial credit she intended.

STEP 3 — EQUIVALENCE NOTES, SPARINGLY.
An `equivalence_note` records an alternative form the teacher's own text or her \
example solution licenses — a different name she used herself, an option she \
excused. Write one only when you can point to the licensing text, and say in the \
note what licenses it. If nothing licenses an alternative, leave it empty. Notes \
you invent grant credit she did not give.

INVARIANTS — these hold for every check you write.

CITE, THEN CLAIM. Every check carries `rubric_quote`: a VERBATIM span of the \
scope text you were given. Copy it exactly, including any typo or missing space. \
Elide the middle of a long span with … but NEVER paraphrase, and never cite text \
you were not shown. A check you cannot cite is a check you must not write.

THE POINTS MUST ADD UP EXACTLY. Per terminal, `required` points sum to exactly \
`points_possible` — not approximately. Every value, and every \
`points × partial_fraction`, is a multiple of the stated precision. `tariff` \
checks carry no points; `note_only` checks carry no points.

PHRASE EVERY CHECK SO THAT "MET" MEANS SATISFIED. Write the requirement, never \
the defect.

NEVER STATE POINTS IN `description_he`. The reader who rules on these checks is \
deliberately blind to the numbers; putting one in the text hands them the answer.

<examples>
<example>
Entry: [d1] amount 2 — candidates: q3.ב.c1.s0, q3.ב.c1.s1
  "אם הלולאה מתחילה מ-1 במקום מ-0 להוריד 2"
Disposition: tariff, amount 2, anchored to q3.ב.c1.s0
  ("s0 is the loop-definition check; s1 is the body, which the start index does
   not modify")
</example>
<example>
Entry: [d2] no_deduct — candidates: q3.ב.c2
  "אם לא בדקו שהקובץ קיים - לא להוריד, לציין בהערה"
Disposition: note_only. No points, no tariff_amount.
</example>
<example>
Entry: [d3] amount 5 — candidates: q1.א.c0
  "התלמיד קיבל 5 נקודות על סעיף זה במבחן קודם"
Disposition: not_a_deduction ("describes a past score, not a grading rule for
  this criterion").
</example>
</examples>"""


def build_generation_message(scope_key: Tuple[str, Optional[str]],
                             corpus: str,
                             terminals: List[Tuple[str, str]],
                             precision: str,
                             clauses: List[Clause],
                             subject: Optional[str],
                             programming_language: Optional[str],
                             deductions: Sequence[DetectedDeduction] = ()) -> str:
    """`terminals` is [(terminal_id, points_possible)] — the DERIVED set. The
    model never chooses which terminals exist (validator V6); it only fills
    them, and echoing the ids back lets assembly catch a misalignment.

    `deductions` is the deterministic detection (V11); every entry must be
    disposed of in the response."""
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

    lines += ["", "=== DEDUCTIONS DETECTED (dispose of every entry) ==="]
    if deductions:
        for d in deductions:
            amount = "no_deduct" if d.polarity == "no_deduct" else f"amount {d.amount}"
            cands = ", ".join(d.candidate_terminal_ids) or "(scope)"
            lines.append(f"  · [{d.marker_id}] {amount} — candidates: {cands}")
            lines.append(f"    \"{d.quote}\"")
    else:
        lines.append("  (none found — emit no tariff checks for this scope)")

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