"""
relocation.py — apply a student's own "move this text there" instructions.

A student sometimes writes part of an answer somewhere else and links it to
where it belongs: an arrow, a matching pair of symbols, a caret, «המשך». P1
transcribes ink where it PHYSICALLY sits, so without this step the answer the
grader consumes is out of order. This module is the pure function between P1 and
P2 that moves it (MISSION_transcription_accuracy.md §3.3), and nothing else.

Two kinds, defined by what the text IS rather than where it lands:
  * insertion  — answer content, spliced in verbatim between two anchors, which
                 may sit between lines or mid-line (e.g. into a condition);
  * attachment — a note ABOUT one line, hung at that line's end as ` ⟦note⟧`.
                 `⟦ ⟧` (U+27E6/U+27E7) is the one sanctioned non-ink addition
                 (OD-A3): `//` would invent ink, and is CS-only besides.

THE ALGORITHM IS FOUR STEPS, AND THEIR ORDER IS THE CORRECTNESS ARGUMENT:
  1. LOCATE everything in the ORIGINAL page text before changing anything, so no
     instruction's anchors can be disturbed by another's edit.
  2. REJECT a case whose locations are missing or ambiguous, whose source and
     target overlap, or whose spans overlap another case's (reject BOTH).
  3. APPLY the accepted cases per page from the END backwards, so every offset
     computed in step 1 is still valid when it is used.
  4. RETURN one record per applied case, and one per rejected case.

MATCHING IS EXACT ON EVERY NON-WHITESPACE CHARACTER, AND BLIND TO WHITESPACE.
Anchors are compared with all whitespace removed — the same equality the scorer
uses (normalize.py deletes all whitespace), so an anchor copied as
`int x=0;` finds `int x = 0;` and `{\\n` finds `{`. There is NO edit-distance
fuzz, and there must never be: a relocation that lands on a near-match is a
FALSE relocation, and a false relocation silently reorders what the grader
reads, where a missed one is merely visible on the scan beside the text.
Loosening this is a decision to surface with evidence, never a tuning knob.

AMBIGUITY STAYS IN PLACE. Anything unresolved is returned in `rejected` with
its reason and the text is left exactly where the student wrote it — review-
first, not guess (CLAUDE.md §2). Provenance is SILENT by ruling (OD-A2): records
feed the eval metrics and one operational log line, and are never written to a
TranscriptionDraft or turned into an annotation.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

log = logging.getLogger("transcription.two_phase.relocation")

INSERTION = "insertion"
ATTACHMENT = "attachment"
ATTACH_OPEN = "⟦"   # ⟦
ATTACH_CLOSE = "⟧"  # ⟧


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Instruction:
    """One "move this text" instruction, in either of its two source forms.

    The SOURCE is given either as its full verbatim text (`source_text` — the
    owner-authored eval cases) or by its first and last words (`source_first` /
    `source_last` — what P1 reports, which costs a fraction of the output
    tokens). The target is `after`/`before` for an insertion (either may be ""
    at an answer's start or end, never both) and `line` for an attachment."""
    id: str
    kind: str
    source_page: int
    target_page: int
    source_text: str | None = None
    source_first: str | None = None
    source_last: str | None = None
    after: str | None = None
    before: str | None = None
    line: str | None = None
    marker: str = "other"


@dataclass(frozen=True)
class Relocation:
    """An APPLIED instruction. Offsets are in the ORIGINAL page texts."""
    id: str
    kind: str
    source_page: int
    source_start: int
    source_end: int
    target_page: int
    target_pos: int          # insertion point, or the end of the attached line
    text: str                # exactly what was spliced (the note, for attachments)


@dataclass(frozen=True)
class Rejection:
    id: str
    reason: str


@dataclass(frozen=True)
class RelocationResult:
    pages: dict[int, str]
    applied: tuple[Relocation, ...]
    rejected: tuple[Rejection, ...]


@dataclass(frozen=True)
class _Located:
    inst: Instruction
    src: tuple[int, int]            # original span to CUT (possibly line-extended)
    src_core: tuple[int, int]       # the span the anchors matched (no extension)
    region: tuple[int, int]         # the target's footprint, for overlap checks
    target_pos: int
    insert_text: str


# ---------------------------------------------------------------------------
# Whitespace-blind exact search
# ---------------------------------------------------------------------------

def strip_ws(s: str) -> str:
    return "".join(s.split())


def collapse_ws(s: str) -> str:
    return " ".join(s.split())


def _index(text: str) -> tuple[str, list[int]]:
    """`text` without whitespace, and the original index of each kept char."""
    kept, idx = [], []
    for i, ch in enumerate(text):
        if not ch.isspace():
            kept.append(ch)
            idx.append(i)
    return "".join(kept), idx


def find_all(text: str, needle: str) -> list[tuple[int, int]]:
    """Every whitespace-blind occurrence of `needle` in `text`, as ORIGINAL
    [start, end) spans. Overlapping occurrences are all returned, because an
    overlap is still an ambiguity."""
    n = strip_ws(needle)
    if not n:
        return []
    hay, idx = _index(text)
    out, start = [], 0
    while True:
        k = hay.find(n, start)
        if k < 0:
            return out
        out.append((idx[k], idx[k + len(n) - 1] + 1))
        start = k + 1


def _line_bounds(text: str, pos: int) -> tuple[int, int]:
    """[start, end) of the line containing `pos`, end excluding its newline."""
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    return start, (len(text) if end < 0 else end)


def _overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


# ---------------------------------------------------------------------------
# Step 1 — locate (pure, against the ORIGINAL text)
# ---------------------------------------------------------------------------

def _locate_source(inst: Instruction, page: str) -> tuple[int, int] | str:
    if inst.source_text is not None:
        hits = find_all(page, inst.source_text)
        if not hits:
            return "source text not found on its page"
        if len(hits) > 1:
            return f"source text occurs {len(hits)} times on its page"
        return hits[0]
    if not inst.source_first or not inst.source_last:
        return "source has neither full text nor first/last words"
    firsts = find_all(page, inst.source_first)
    if len(firsts) != 1:
        return (f"source first_words occurs {len(firsts)} times "
                "(needs exactly one)")
    f0 = firsts[0][0]
    lasts = [s for s in find_all(page, inst.source_last) if s[0] >= f0]
    if len(lasts) != 1:
        return (f"source last_words occurs {len(lasts)} times at or after "
                "first_words (needs exactly one)")
    return (f0, lasts[0][1])


def _extend_to_whole_lines(page: str, span: tuple[int, int]) -> tuple[int, int]:
    """A source that fills its lines takes their line break with it, so the cut
    leaves no empty line behind. A source sharing its line keeps the line."""
    s, e = span
    ls, _ = _line_bounds(page, s)
    _, le = _line_bounds(page, max(s, e - 1))
    if page[ls:s].strip() or page[e:le].strip():
        return span
    if le < len(page):
        return (ls, le + 1)            # own lines, plus the newline after them
    if ls > 0:
        return (ls - 1, le)            # last lines of the page: take the one before
    return (ls, le)


def _locate_insertion(inst: Instruction, page: str,
                      text: str) -> tuple[tuple[int, int], int, str] | str:
    after, before = inst.after or "", inst.before or ""
    a_s, b_s = strip_ws(after), strip_ws(before)
    if not a_s and not b_s:
        return "insertion target has neither `after` nor `before`"
    if a_s and b_s:
        hits = find_all(page, after + before)
        if len(hits) != 1:
            return (f"insertion target after+before occurs {len(hits)} times "
                    "(needs exactly one)")
        start, end = hits[0]
        hay, idx = _index(page[start:end])
        a_end = start + idx[len(a_s) - 1] + 1      # just past the last `after` char
        b_start = start + idx[len(a_s)]            # the first `before` char
        gap = page[a_end:b_start]
        if "\n" in gap:
            pos = a_end + gap.rfind("\n") + 1      # start of the before-line
            return (start, end), pos, text + "\n"
        return (start, end), b_start, (" " if not gap else "") + text + " "
    if b_s:                                         # answer start: before only
        hits = find_all(page, before)
        if len(hits) != 1:
            return f"insertion target `before` occurs {len(hits)} times"
        start, end = hits[0]
        ls, _ = _line_bounds(page, start)
        if not page[ls:start].strip():
            return (start, end), ls, text + "\n"
        return (start, end), start, text + " "
    hits = find_all(page, after)                    # answer end: after only
    if len(hits) != 1:
        return f"insertion target `after` occurs {len(hits)} times"
    start, end = hits[0]
    _, le = _line_bounds(page, end - 1)
    if not page[end:le].strip():
        return (start, end), le, "\n" + text
    return (start, end), end, " " + text


def _locate_attachment(inst: Instruction, page: str,
                       note: str) -> tuple[tuple[int, int], int, str] | str:
    if not inst.line or not strip_ws(inst.line):
        return "attachment target has no `line`"
    want = strip_ws(inst.line)
    matches, pos = [], 0
    for raw_line in page.split("\n"):
        if strip_ws(raw_line) == want:
            matches.append((pos, pos + len(raw_line)))
        pos += len(raw_line) + 1
    if len(matches) != 1:
        return (f"attachment target line occurs {len(matches)} times as a "
                "complete line (needs exactly one)")
    ls, le = matches[0]
    end = ls + len(page[ls:le].rstrip())
    return (ls, le), end, f" {ATTACH_OPEN}{collapse_ws(note)}{ATTACH_CLOSE}"


def locate(inst: Instruction, pages: dict[int, str]) -> _Located | Rejection:
    """Step 1 + the single-case half of step 2, against ORIGINAL pages."""
    if inst.kind not in (INSERTION, ATTACHMENT):
        return Rejection(inst.id, f"unknown kind {inst.kind!r}")
    if inst.source_page not in pages or inst.target_page not in pages:
        return Rejection(inst.id, "source or target page does not exist")
    src_page = pages[inst.source_page]
    core = _locate_source(inst, src_page)
    if isinstance(core, str):
        return Rejection(inst.id, core)
    text = src_page[core[0]:core[1]]
    tgt_page = pages[inst.target_page]
    placed = (_locate_insertion(inst, tgt_page, text) if inst.kind == INSERTION
              else _locate_attachment(inst, tgt_page, text))
    if isinstance(placed, str):
        return Rejection(inst.id, placed)
    region, target_pos, insert_text = placed
    src = _extend_to_whole_lines(src_page, core)
    if inst.source_page == inst.target_page:
        if _overlaps(core, region) or core[0] <= target_pos < core[1]:
            return Rejection(inst.id, "source and target overlap")
        if src[0] < target_pos < src[1]:
            src = core                 # never let a line extension swallow the target
    return _Located(inst, src, core, region, target_pos, insert_text)


# ---------------------------------------------------------------------------
# Steps 2–4
# ---------------------------------------------------------------------------

def relocate(pages: dict[int, str],
             instructions: Iterable[Instruction]) -> RelocationResult:
    """Apply every instruction that locates unambiguously; leave the rest in
    place and say why. Pure: same input, same output, no I/O."""
    located: list[_Located] = []
    rejected: list[Rejection] = []
    for inst in instructions:
        r = locate(inst, pages)
        (rejected if isinstance(r, Rejection) else located).append(r)

    # Cross-case overlap: two cases that CONFLICT are BOTH rejected — which one
    # "wins" is exactly the guess this module refuses. A conflict is an EDIT
    # meeting something another case depends on:
    #   * their sources overlap (the same ink moved twice);
    #   * one's source cuts through the other's anchors (its context moves away
    #     under it);
    #   * both insert at the same point (their order is unknowable).
    # Two targets merely SHARING anchor text — one insertion's `before` line is
    # the next one's `after` — is not a conflict: anchors are read-only context,
    # each point was located uniquely on the original text, and neither edit
    # touches the other's point.
    def conflict(a: _Located, b: _Located) -> bool:
        ai, bi = a.inst, b.inst
        if ai.source_page == bi.source_page and _overlaps(a.src, b.src):
            return True
        if ai.source_page == bi.target_page and _overlaps(a.src, b.region):
            return True
        if bi.source_page == ai.target_page and _overlaps(b.src, a.region):
            return True
        return ai.target_page == bi.target_page and a.target_pos == b.target_pos

    clash: set[str] = set()
    for i, a in enumerate(located):
        for b in located[i + 1:]:
            if conflict(a, b):
                clash.update((a.inst.id, b.inst.id))
    kept = [c for c in located if c.inst.id not in clash]
    rejected += [Rejection(c.inst.id, "overlaps another instruction's spans")
                 for c in located if c.inst.id in clash]

    # Step 3: edits per page, applied from the end so step-1 offsets hold.
    # At an equal position a cut runs before an insert, so an insertion that
    # lands where a source began is never cut away with it.
    edits: dict[int, list[tuple[int, int, int, str]]] = {}
    for c in kept:
        edits.setdefault(c.inst.source_page, []).append((c.src[0], 1, c.src[1], ""))
        edits.setdefault(c.inst.target_page, []).append(
            (c.target_pos, 0, c.target_pos, c.insert_text))
    out = dict(pages)
    for page_no, page_edits in edits.items():
        text = out[page_no]
        for start, _prio, end, ins in sorted(page_edits, reverse=True):
            text = text[:start] + ins + text[end:]
        out[page_no] = text

    applied = tuple(
        Relocation(
            id=c.inst.id, kind=c.inst.kind,
            source_page=c.inst.source_page,
            source_start=c.src_core[0], source_end=c.src_core[1],
            target_page=c.inst.target_page, target_pos=c.target_pos,
            text=(collapse_ws(pages[c.inst.source_page][c.src_core[0]:c.src_core[1]])
                  if c.inst.kind == ATTACHMENT
                  else pages[c.inst.source_page][c.src_core[0]:c.src_core[1]]),
        )
        for c in kept
    )
    return RelocationResult(out, applied, tuple(rejected))


def log_line(doc_id: str, result: RelocationResult) -> str:
    """The ONE operational line per document (OD-A2: silent to the teacher).
    Everything worth querying is in the message string — `extra=` is never
    rendered in this service (CLAUDE.md §8)."""
    moves = ";".join(
        f"{r.kind}:p{r.source_page}@{r.source_start}-{r.source_end}"
        f"->p{r.target_page}@{r.target_pos}" for r in result.applied)
    return (f"relocation doc={doc_id} applied={len(result.applied)} "
            f"rejected={len(result.rejected)} moves=[{moves}] "
            f"rejections=[{';'.join(r.reason for r in result.rejected)}]")
