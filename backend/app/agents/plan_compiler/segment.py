"""
PLAN COMPILER v2 — Stage 2: the SEGMENTER (PR §4). Wording only.

One call per SCOPE (its terminals batched while the message stays under a
budget; otherwise one call per terminal). Input: each slot's kind, its verbatim
span, and — for a tariff — the requirement it guards; the scope's example
solution when the scope has one. NOT input: points, amounts, counts.

Output, schema-enforced: exactly the requested slot ids, each with
`rubric_quote` (decoded FIRST — cite, then claim), `description_he`, and an
`equivalence_note` that is empty unless it carries a licensing citation. The
output type has no `points`, `kind`, `tariff_amount` or `unit_count` field —
the model cannot emit a number, a kind, an amount, an anchor or a count.

Validation runs the plan validator's OWN rules on every entry (V9 grounding
against the scope corpus, V10 point-blindness) — one place, one concept. A
failure retries ONCE with the errors verbatim; a slot still failing gets its
span SUBSTITUTED as its wording and is flagged — a plan is never blocked on
wording. Cost is accounted per call against the registry price card and a
hard envelope (A1 ≤ $2, PR §7) aborts the run before it can be exceeded.

Design law: this module may not write a number into a Slot. `assemble_plan`
takes the wording and the skeleton separately and the skeleton wins.
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.agents.grader.plan_validator import _POINT_TEXT, _tight, quote_is_grounded

from .assemble import PLACEHOLDER_REMAINDER_HE, point_blind
from .skeleton import Flag, PlanSkeleton, Slot, TerminalSkeleton

SEGMENTER_PROMPT_VERSION = "segmenter/v1"
SEGMENTER_MODEL_KEY = "claude-haiku-4.5"       # models_registry key; model_id claude-haiku-4-5
MESSAGE_CHAR_BUDGET = 9000                     # ≈ 2k tokens; above it, one call per terminal


class EnvelopeExceeded(RuntimeError):
    """The spend envelope would be exceeded — the run stops, nothing is written."""


# ── the output type: text only, by construction ─────────────────────────────

class SegmentedSlot(BaseModel):
    slot_id: str
    rubric_quote: str            # decoded first: a verbatim span of the teacher's text
    description_he: str          # phrased so that "met" = satisfied
    equivalence_note: str = ""   # empty unless it cites the licensing text


class SegmenterResponse(BaseModel):
    entries: List[SegmentedSlot]


assert not any(f in SegmentedSlot.model_fields for f in
               ("points", "kind", "tariff_amount", "unit_count", "charge_group")), \
    "the segmenter's output type must not be able to carry a number, a kind or an anchor"


# ── prompt ──────────────────────────────────────────────────────────────────

SEGMENTER_SYSTEM_PROMPT = """\
You turn a teacher's grading rubric into short, checkable requirement statements — in the
teacher's language (Hebrew when the rubric is Hebrew). You are NOT grading; no student answer
exists. Someone will later rule "met / partially met / not met" on each statement without
seeing the rubric, so each statement must stand alone.

You receive SLOTS. Each slot already has its kind and its verbatim span of the rubric. The
structure is decided; you only write the words. Return EXACTLY the slots you were given, in
the same order, with the same slot_id — no more, no fewer.

THREE PRINCIPLES

1. CITE, THEN CLAIM. `rubric_quote` is a VERBATIM span of the text you were shown — copy it
   exactly (typos, missing spaces and all). You may elide the middle of a long span with …
   but never paraphrase, and never cite text you were not shown. Write the quote first.

2. MET MEANS SATISFIED. `description_he` states the requirement, never the defect. For a
   requirement slot: what a correct answer contains. For a tariff slot: the requirement
   whose ABSENCE fires the deduction («בדיקת null מבוצעת», not «לא בדקו null»). For a note
   slot: the observation to record. Never state points, amounts, or counts — a number in
   the text hands the ruler the answer.

3. EQUIVALENCE ONLY WITH A LICENCE. `equivalence_note` names an alternative form ONLY when
   the teacher's own text or her example solution licenses it, and it must quote that
   licence: «מותר X כי הפתרון לדוגמה עושה X». If nothing licenses an alternative, leave it
   empty. A note you invent grants credit the teacher did not give.

EXAMPLES (different subjects on purpose — the rules do not depend on the subject)

Rubric (chemistry): «רישום ניסוח מאוזן של התגובה (2) + ציון מצב הצבירה של כל מגיב (1)»
  slot k1 [requirement], span «רישום ניסוח מאוזן של התגובה»
    rubric_quote: רישום ניסוח מאוזן של התגובה
    description_he: ניסוח התגובה רשום ומאוזן
  slot k2 [requirement], span «ציון מצב הצבירה של כל מגיב»
    rubric_quote: ציון מצב הצבירה של כל מגיב
    description_he: מצב הצבירה מצוין לכל אחד מהמגיבים

Rubric (history): «הצגת שתי סיבות למלחמה. אם הוצגה סיבה אחת בלבד להוריד 2»
  slot k1 [requirement], span «הצגת שתי סיבות למלחמה»
    description_he: מוצגות שתי סיבות למלחמה
  slot t1 [tariff], clause «אם הוצגה סיבה אחת בלבד להוריד 2», guards «הצגת שתי סיבות למלחמה»
    rubric_quote: אם הוצגה סיבה אחת בלבד להוריד 2
    description_he: מוצגות שתי סיבות, לא אחת
    (no number in the description; the amount is not yours to state)

Rubric (arithmetic): «תשובה סופית 24. אם לא צוינו יחידות – לא להוריד, לציין בהערה. ניתן
לפתור גם בדרך של חילוק ארוך (ראו פתרון)»
  slot n1 [note], clause «אם לא צוינו יחידות – לא להוריד, לציין בהערה»
    description_he: היחידות מצוינות בתשובה הסופית
  slot k1 [requirement], span «תשובה סופית 24»
    description_he: התשובה הסופית נכונה
    equivalence_note: מותר לפתור בחילוק ארוך כי הרובריקה אומרת «ניתן לפתור גם בדרך של חילוק ארוך»

OUTPUT: a JSON object {"entries": [...]} with one entry per slot, in order. Fields per entry:
rubric_quote, description_he, equivalence_note (may be ""), slot_id.
"""


def _slot_line(t: TerminalSkeleton, s: Slot) -> str:
    if s.kind == "tariff":
        guard = s.anchor_span or t.text.strip().split("\n")[0]
        return (f"  · slot {s.slot_id} [tariff — write the REQUIREMENT whose absence fires it]\n"
                f"      clause: «{s.source_span}»\n"
                f"      guards: «{guard}»")
    if s.kind == "note_only":
        return f"  · slot {s.slot_id} [note — write the observation to record]\n      clause: «{s.source_span}»"
    if s.kind == "counted":
        return (f"  · slot {s.slot_id} [counted requirement — one statement covering every unit]\n"
                f"      span: «{s.source_span}»")
    if "case2_remainder" in s.flags:
        return (f"  · slot {s.slot_id} [requirement — the REST of the criterion, beyond the parts "
                f"named by the other slots]\n      span: «{s.source_span}»")
    return f"  · slot {s.slot_id} [requirement]\n      span: «{s.source_span}»"


def build_segmenter_message(scope: str, terminals: Sequence[TerminalSkeleton],
                            solution: Optional[str]) -> str:
    lines = [f"SCOPE: {scope}", "", "=== THE TEACHER'S TEXT (your rubric_quote must be a verbatim span of this) ==="]
    for t in terminals:
        lines.append(f"[{t.terminal_id}] {t.text.strip()}")
    if solution:
        lines += ["", "=== THE TEACHER'S EXAMPLE SOLUTION (a licence for an equivalence note; quote it) ===",
                  solution.strip()]
    lines += ["", "=== SLOTS (return exactly these, in this order) ==="]
    for t in terminals:
        lines.append(f"Terminal {t.terminal_id} ({len(t.slots)} slots)")
        for s in t.slots:
            lines.append(_slot_line(t, s))
    return "\n".join(lines)


def repair_suffix(errors: Sequence[str]) -> str:
    return ("\n\n=== YOUR PREVIOUS ANSWER FAILED VALIDATION — fix EXACTLY these and change nothing else ===\n"
            + "\n".join(f"  · {e}" for e in errors))


# ── validation, the validator's own rules ───────────────────────────────────

def validate_entries(entries: Sequence[SegmentedSlot], slots: Sequence[Slot], *,
                     corpus: str, corpus_lines: frozenset) -> Tuple[List[str], Dict[str, str]]:
    """(errors, notes_dropped). Errors are retryable; an unlicensed equivalence
    note is DROPPED (not retried) and reported by slot id."""
    errs: List[str] = []
    want = [s.slot_id for s in slots]
    got = [e.slot_id for e in entries]
    if got != want:
        errs.append(f"slot ids must be exactly {want} in this order; got {got}")
    corpus_tight = _tight(corpus)
    dropped: Dict[str, str] = {}
    by_id = {e.slot_id: e for e in entries}
    for s in slots:
        e = by_id.get(s.slot_id)
        if e is None:
            continue
        if not e.description_he.strip():
            errs.append(f"{s.slot_id}: description_he is empty")
        elif _POINT_TEXT.search(e.description_he):
            errs.append(f"{s.slot_id}: description_he states a point value — the ruler is point-blind; "
                        f"remove every number of points / deduction from the text")
        if not quote_is_grounded(e.rubric_quote, corpus_tight, corpus_lines):
            errs.append(f"{s.slot_id}: rubric_quote is not a verbatim span of the text you were shown "
                        f"(copy exactly; elide the middle with … if long)")
        note = (e.equivalence_note or "").strip()
        if note:
            frags = [_tight(f) for f in re.split(r"«|»|\"|…", note)]
            licensed = any(len(f) >= 10 and f in corpus_tight for f in frags)
            if not licensed:
                dropped[s.slot_id] = note
    return errs, dropped


# ── the run ─────────────────────────────────────────────────────────────────

@dataclass
class CallStat:
    scope: str
    terminals: Tuple[str, ...]
    attempt: int
    input_tokens: int
    output_tokens: int
    cached_tokens: Optional[int]
    cost_usd: float
    latency_s: float
    errors: Tuple[str, ...] = ()


@dataclass
class SegmentRun:
    wording: Dict[str, Tuple[str, Optional[str], Optional[str]]] = field(default_factory=dict)
    calls: List[CallStat] = field(default_factory=list)
    substituted: List[str] = field(default_factory=list)
    notes_dropped: Dict[str, str] = field(default_factory=dict)
    flags: List[Flag] = field(default_factory=list)

    @property
    def cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def clean_first_try(self) -> int:
        return sum(1 for c in self.calls if c.attempt == 1 and not c.errors)


CostFn = Callable[[int, int, Optional[int]], float]


def _usage(result) -> Tuple[int, int, Optional[int]]:
    raw = result.get("raw")
    usage = (getattr(raw, "usage_metadata", None) or {}) if raw is not None else {}
    cached = (usage.get("input_token_details") or {}).get("cache_read")
    return usage.get("input_tokens", 0), usage.get("output_tokens", 0), cached


def substitute(slot: Slot, terminal: TerminalSkeleton) -> Tuple[str, Optional[str], Optional[str]]:
    """The compiler's own placeholder wording — the same text A0 used."""
    if slot.kind == "tariff":
        desc = slot.anchor_span or point_blind(slot.summary or slot.source_span)
    else:
        desc = slot.summary or point_blind(slot.source_span)
    if "case2_remainder" in slot.flags:
        desc = PLACEHOLDER_REMAINDER_HE
    desc = point_blind(desc) or PLACEHOLDER_REMAINDER_HE
    quote = slot.source_span or terminal.text.strip()
    if len(re.sub(r"\s+", "", quote)) < 10:
        quote = terminal.text.strip().split("\n")[0].strip() or quote
    return desc, quote or None, None


async def segment_skeleton(skeleton: PlanSkeleton, llm, *, corpora: Dict[str, str],
                           solutions: Dict[str, str], cost_fn: CostFn,
                           envelope_usd: float, timeout_s: float = 120.0,
                           char_budget: int = MESSAGE_CHAR_BUDGET) -> SegmentRun:
    """`llm` exposes with_structured_output(schema, include_raw=True).ainvoke(msgs)
    (the grader agents' surface). `corpora[scope]` is V9's corpus for the scope;
    `solutions[scope]` the example solution when present."""
    runner = llm.with_structured_output(SegmenterResponse, include_raw=True)
    run = SegmentRun()
    by_scope: Dict[str, List[TerminalSkeleton]] = {}
    for t in skeleton.terminals:
        by_scope.setdefault(t.scope, []).append(t)

    async def one_call(scope: str, terminals: List[TerminalSkeleton]) -> None:
        slots = [s for t in terminals for s in t.slots]
        corpus = corpora[scope]
        lines = frozenset(_tight(l) for l in corpus.split("\n") if l.strip())
        message = build_segmenter_message(scope, terminals, solutions.get(scope))
        errors: List[str] = []
        entries: List[SegmentedSlot] = []
        for attempt in (1, 2):
            if run.cost_usd >= envelope_usd:
                raise EnvelopeExceeded(f"spent ${run.cost_usd:.4f} ≥ envelope ${envelope_usd:.2f} "
                                       f"before scope {scope}")
            payload = message + (repair_suffix(errors) if errors else "")
            t0 = time.monotonic()
            result = await asyncio.wait_for(runner.ainvoke([
                SystemMessage(content=SEGMENTER_SYSTEM_PROMPT), HumanMessage(content=payload)]),
                timeout=timeout_s)
            latency = time.monotonic() - t0
            in_tok, out_tok, cached = _usage(result)
            cost = cost_fn(in_tok, out_tok, cached)
            if result.get("parsing_error") or result.get("parsed") is None:
                errors = [f"unparseable response: {result.get('parsing_error')}"]
                entries = []
            else:
                entries = list(result["parsed"].entries)
                errors, dropped = validate_entries(entries, slots, corpus=corpus, corpus_lines=lines)
                run.notes_dropped.update(dropped)
            run.calls.append(CallStat(scope, tuple(t.terminal_id for t in terminals), attempt,
                                      in_tok, out_tok, cached, cost, latency, tuple(errors)))
            if not errors:
                break
        by_id = {e.slot_id: e for e in entries}
        failing = {e.split(":")[0] for e in errors if ":" in e}
        wrong_set = any(e.startswith("slot ids must be") for e in errors)
        for t in terminals:
            for s in t.slots:
                e = by_id.get(s.slot_id)
                if e is None or wrong_set or s.slot_id in failing:
                    run.wording[s.slot_id] = substitute(s, t)
                    run.substituted.append(s.slot_id)
                    run.flags.append(Flag("segmenter_substituted", t.terminal_id,
                                          f"{s.slot_id}: {'; '.join(errors)[:160]}"))
                    continue
                note = (e.equivalence_note or "").strip()
                if s.slot_id in run.notes_dropped:
                    run.flags.append(Flag("equivalence_note_unlicensed", t.terminal_id,
                                          f"{s.slot_id}: {note[:80]}"))
                    note = ""
                run.wording[s.slot_id] = (e.description_he.strip(), e.rubric_quote.strip() or None,
                                          note or None)

    for scope, terminals in by_scope.items():
        if len(build_segmenter_message(scope, terminals, solutions.get(scope))) <= char_budget:
            await one_call(scope, terminals)
        else:
            for t in terminals:
                await one_call(scope, [t])
    return run
