"""
The deduction DETECTOR and the scope corpus — PLAN COMPILER v2's C1/C2 input
(kept per R-4 when the Opus decomposer was retired; its prompt, its message
builder and its repair loop are gone).

**The corpus IS V9's grounding corpus.** `scope_corpus` is exactly the text a
plan's quotes are checked against, per scope.

**Deductions are DETECTED, not noticed (plan-gen/v2).** Phase 0 measured tariff
recall 11/14; the one derivable miss was read conceptually and then mis-anchored
and mis-valued (amount 1 where the teacher wrote 3). Locating a deduction phrase
in Hebrew text, copying its number, and knowing which node's text contains it
are string and lookup tasks — deterministic, and done in code. The compiler
(`plan_compiler.compile.scan_deductions`) re-scans these same patterns
POSITIONALLY; `detect_deductions` remains the per-scope, candidate-terminal view
the authoring tools use.

Subject-agnostic by construction (§3.3): nothing here knows about computer
science.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import List, NamedTuple, Optional, Tuple

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
# [PLAN COMPILER v2, C1] deduction VERBS that carry no number in the two-exam
# corpus («לקנוס פעם אחת אם לא בדקו…», «להוריד רק פעם אחת»). The amount is
# resolved by the compiler (OD-15); here they are reported with amount=None.
# Tested after the numbered forms so «להוריד 2» is never re-read as amountless.
_DEDUCT_AMOUNTLESS_PATTERNS = (
    r"לקנוס",
    r"(?<![֐-׿])קנס(?![֐-׿])",
    r"להוריד(?=\s+רק\s+פעם)",
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
    for pat in _DEDUCT_AMOUNTLESS_PATTERNS:
        for m in re.finditer(pat, text):
            if overlaps(*m.span()):
                continue
            claimed.append(m.span())
            hits.append((_clause_around(text, *m.span()), None, "deduct"))
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
