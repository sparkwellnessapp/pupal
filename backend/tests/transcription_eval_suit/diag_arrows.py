"""
diag_arrows.py — the ARROW diagnostic (MISSION §4.3). Additive: nothing in the
gate path reads it.

It scores the PIPELINE'S OWN relocation records (relocation.py) against the
owner's cases (insertion_cases.json):

  placed            a case whose text was moved, and landed at its boundary (an
                    insertion) or at the end of its line (an attachment). The
                    text leaving its source is guaranteed by construction — the
                    relocation function always cuts what it moves.
  missed            a case with no matching applied relocation.
  false_relocations applied relocations matching NO insertion/attachment case.
                    `false_on_decoy` is the subset that landed on a decoy — the
                    prompt's specific failure, so it is reported on its own.

A false relocation is WORSE than a missed one (§2): a missed arrow is visible on
the scan beside the text, a false one silently reorders what the grader reads.

MATCHING HERE IS TOLERANT ON PURPOSE, AND THAT IS NOT A CONTRADICTION. The
relocation FUNCTION matches exactly (fuzz is how false relocations are born).
This module only decides whether a record the function already applied
CORRESPONDS to a case — the model's transcription of the moved text differs from
the GT's by whatever it misread, and a diagnostic that called that a false
relocation would be measuring perception, not placement. The thresholds are
named constants, not hidden.
"""
from __future__ import annotations

import difflib

from app.services.transcription.normalize import normalize
from app.services.transcription.two_phase.relocation import (
    ATTACHMENT, INSERTION, Relocation,
)

#: A record CORRESPONDS to a case when its moved text is this similar to the
#: case's source (normalized). Below it, it is a different piece of ink.
SOURCE_MATCH = 0.80
#: A correspondence is PLACED when the context at the landing point is this
#: similar to the case's anchors (normalized, compared over the anchor length).
CONTEXT_MATCH = 0.80
#: A record lands on a DECOY when the decoy's `near` text is this similar to the
#: best window of the record's source or landing context.
DECOY_MATCH = 0.80


def _n(s: str) -> str:
    return normalize(s or "", strip_illegible=False)


def _ratio(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def _best_window(needle: str, hay: str) -> float:
    """Best similarity of `needle` against any same-length window of `hay`."""
    if not needle:
        return 0.0
    if len(hay) <= len(needle):
        return _ratio(needle, hay)
    step = max(1, len(needle) // 4)
    return max(_ratio(needle, hay[i:i + len(needle)])
               for i in range(0, len(hay) - len(needle) + 1, step))


def _context(page: str, pos: int, n_before: int, n_after: int) -> tuple[str, str]:
    """Normalized text just before and just after `pos`, sized to the anchors."""
    before = _n(page[:pos])
    after = _n(page[pos:])
    return before[-n_before:] if n_before else "", after[:n_after] if n_after else ""


def _placed(case: dict, rec: Relocation, pred_pages: dict[int, str]) -> bool:
    page = pred_pages.get(rec.target_page, "")
    tgt = case["target"]
    if case["kind"] == INSERTION:
        a, b = _n(tgt.get("after", "")), _n(tgt.get("before", ""))
        got_a, got_b = _context(page, rec.target_pos, len(a), len(b))
        return ((not a or _ratio(a, got_a) >= CONTEXT_MATCH)
                and (not b or _ratio(b, got_b) >= CONTEXT_MATCH))
    # attachment: the line the note was hung on is the case's line
    start = page.rfind("\n", 0, rec.target_pos) + 1
    return _ratio(_n(tgt.get("line", "")), _n(page[start:rec.target_pos])) >= CONTEXT_MATCH


def score_arrows(cases: list[dict], applied: list[Relocation],
                 pred_pages: dict[int, str]) -> dict:
    """`pred_pages` are the pages BEFORE relocation (the records' offsets live
    there). `cases` are the fixture's raw case dicts, decoys included."""
    live = [c for c in cases if c.get("kind") in (INSERTION, ATTACHMENT)]
    decoys = [c for c in cases if c.get("kind") == "decoy"]
    used: set[int] = set()
    details, placed = [], 0

    for c in live:
        best, best_r = None, 0.0
        for i, rec in enumerate(applied):
            if i in used or rec.kind != c["kind"]:
                continue
            if rec.source_page != int(c["source"]["page"]):
                continue
            if rec.target_page != int(c["target"]["page"]):
                continue
            r = _ratio(_n(c["source"]["text"]), _n(rec.text))
            if r >= SOURCE_MATCH and r > best_r:
                best, best_r = i, r
        if best is None:
            details.append({"id": c["id"], "outcome": "missed"})
            continue
        used.add(best)
        ok = _placed(c, applied[best], pred_pages)
        placed += ok
        details.append({"id": c["id"], "outcome": "placed" if ok else "misplaced",
                        "source_similarity": round(best_r, 4)})

    false_recs, on_decoy = [], 0
    for i, rec in enumerate(applied):
        if i in used:
            continue
        page = pred_pages.get(rec.target_page, "")
        ctx = "".join(_context(page, rec.target_pos, 60, 60))
        hit = next((d["id"] for d in decoys
                    if max(_best_window(_n(d.get("near", "")), _n(rec.text)),
                           _best_window(_n(d.get("near", "")), ctx)) >= DECOY_MATCH), None)
        on_decoy += hit is not None
        false_recs.append({"kind": rec.kind, "source_page": rec.source_page,
                           "target_page": rec.target_page, "text": rec.text[:80],
                           "decoy": hit})

    n = len(live)
    return {
        "cases": n,
        "placed": placed,
        "missed": sum(d["outcome"] == "missed" for d in details),
        "misplaced": sum(d["outcome"] == "misplaced" for d in details),
        "placement_rate": placed / n if n else None,
        "false_relocations": len(false_recs),
        "false_on_decoy": on_decoy,
        "details": details,
        "false": false_recs,
    }
