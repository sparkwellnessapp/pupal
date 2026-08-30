"""
spans.py — the P2 SPAN OUTPUT CONTRACT (2026-08-11 redesign).

Why this exists (the k=5 evidence, results/20260811_130925_v0): the generative
P2 contract asked the model to RE-EMIT text the harness already holds. Both
measured luna defect classes live in that copy job:
  A. key-field corruption (3/25 records) — anchor prose leaking into
     sub_question_id under a schema that forbade the anchor field;
  B. boundary trim (14/25) — 1-2 structural chars (class wrapper / final `}`)
     stochastically dropped during re-emission.

Under this contract the model NEVER writes answer text. The harness numbers
the input lines; the model emits, per spec target, the LINE SPANS that make up
that answer; the harness slices the text back out VERBATIM. Consequences by
construction, not by prompting:
  * targets are a closed enum in the schema — class A unrepresentable;
  * answer text is a byte-exact slice of the input — class B impossible below
    line granularity, and the verbatim contract is physics, not a plea;
  * exclusivity ("segmentation is a PARTITION") becomes a checkable validator
    with ONE targeted re-request, instead of a prompt paragraph;
  * output shrinks from thousands of tokens to ~hundreds (latency/cost down,
    'length'-truncation stops being an empty-answer-set catastrophe).

Everything here is pure. The stochastic stage decides only WHERE units begin,
end, and belong — the one thing that needs intelligence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .parsing import ExamSpec
from .keys import Key


# ---------------------------------------------------------------------------
# Targets — the closed label set
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SpecTarget:
    label: str                    # "1.א" / "5" — what the model emits (enum)
    key: Key                      # (question_number, sub_question_id|None)
    signature: str                # spec signature (routing context)


def spec_targets(spec: ExamSpec) -> tuple[SpecTarget, ...]:
    out: list[SpecTarget] = []
    for q in spec.questions:
        if q.sub_questions:
            for sq in q.sub_questions:
                out.append(SpecTarget(
                    label=f"{q.number}.{sq.id}",
                    key=(q.number, sq.id),
                    signature=sq.signature,
                ))
        else:
            out.append(SpecTarget(
                label=str(q.number), key=(q.number, None), signature=q.context,
            ))
    return tuple(out)


# ---------------------------------------------------------------------------
# Input numbering
# ---------------------------------------------------------------------------

def numbered_pages_block(pages: dict[int, str]) -> str:
    """Render pages with per-page 1-based line numbers the model references."""
    blocks: list[str] = []
    for n in sorted(pages):
        lines = pages[n].split("\n")
        body = "\n".join(f"{i:>3}| {line}" for i, line in enumerate(lines, 1))
        blocks.append(f"--- PAGE {n} ({len(lines)} lines) ---\n{body}")
    return "\n".join(blocks)


# ---------------------------------------------------------------------------
# Schema — strict, dynamic target enum
# ---------------------------------------------------------------------------

def build_span_schema(targets: tuple[SpecTarget, ...]) -> dict:
    labels = [t.label for t in targets]
    return {
        "type": "object",
        "properties": {
            "plan": {"type": "string"},
            "assignments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "enum": labels},
                        "anchor": {"type": "string"},
                        "spans": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "page": {"type": "integer"},
                                    "from_line": {"type": "integer"},
                                    "to_line": {"type": "integer"},
                                },
                                "required": ["page", "from_line", "to_line"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["target", "anchor", "spans"],
                    "additionalProperties": False,
                },
            },
            "notes": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["plan", "assignments", "notes"],
        "additionalProperties": False,
    }


# ---------------------------------------------------------------------------
# Parse → validate → slice
# ---------------------------------------------------------------------------

@dataclass
class SliceResult:
    answers: dict[Key, str]
    notes: tuple[str, ...]
    problems: tuple[str, ...]      # validator violations (empty = clean)

    @property
    def ok(self) -> bool:
        return not self.problems


def parse_and_slice(
    data: dict,
    pages: dict[int, str],
    targets: tuple[SpecTarget, ...],
) -> SliceResult:
    """
    Assignment map -> verbatim sliced answers, with validation.

    STRICT view: `problems` non-empty means the map violated the contract
    (out-of-range span, overlap between targets, duplicate/unknown target) —
    the caller uses that to spend its ONE re-request. SALVAGE view: the
    returned answers are always the best-effort slice under deterministic
    resolution (clip out-of-range; first assignment wins an overlap; duplicate
    targets concatenate) so a second bad attempt still degrades per-unit,
    never throws — every resolution is recorded in `notes`.
    """
    by_label = {t.label: t for t in targets}
    page_lines = {n: pages[n].split("\n") for n in pages}
    problems: list[str] = []
    notes: list[str] = []

    # (page, line) -> owning label, for overlap detection (first wins).
    owned: dict[tuple[int, int], str] = {}
    answers: dict[Key, str] = {}
    seen_labels: set[str] = set()

    for a in data.get("assignments", []):
        label = a.get("target")
        if label not in by_label:
            problems.append(f"unknown target {label!r}")
            continue
        t = by_label[label]
        if label in seen_labels:
            problems.append(f"duplicate assignment for target {label}")
            notes.append(f"duplicate assignment for {label}: spans concatenated")
        seen_labels.add(label)

        pieces: list[str] = []
        for s in a.get("spans", []):
            try:
                page = int(s["page"])
                lo = int(s["from_line"])
                hi = int(s["to_line"])
            except (KeyError, TypeError, ValueError):
                problems.append(f"{label}: malformed span {s!r}")
                continue
            if page not in page_lines:
                problems.append(f"{label}: unknown page {page}")
                continue
            n_lines = len(page_lines[page])
            if lo > hi or lo < 1 or hi > n_lines:
                problems.append(
                    f"{label}: span P{page} L{lo}-L{hi} out of range (1-{n_lines})"
                )
                lo, hi = max(1, lo), min(n_lines, hi)   # salvage: clip
                if lo > hi:
                    continue
            kept: list[str] = []
            for ln in range(lo, hi + 1):
                owner = owned.get((page, ln))
                if owner is not None and owner != label:
                    problems.append(
                        f"overlap: P{page} L{ln} claimed by {owner} and {label}"
                    )
                    continue                             # salvage: first wins
                owned[(page, ln)] = label
                kept.append(page_lines[page][ln - 1])
            if kept:
                pieces.append("\n".join(kept))
        text = "\n".join(pieces).strip("\n")
        if t.key in answers and answers[t.key]:
            answers[t.key] = answers[t.key] + "\n" + text if text else answers[t.key]
        else:
            answers[t.key] = text

    # Every spec target accounted for: absent -> declared-skip (empty answer),
    # flagged as a problem so attempt 1 re-requests a complete map.
    for t in targets:
        if t.label not in seen_labels:
            problems.append(f"target {t.label} missing from assignments")
            answers.setdefault(t.key, "")

    for n in data.get("notes", []) or []:
        notes.append(str(n))

    return SliceResult(
        answers=answers, notes=tuple(notes), problems=tuple(problems),
    )
