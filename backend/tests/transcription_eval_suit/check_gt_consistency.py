"""
Cross-corpus GT consistency check — the guard that would have caught the
2026-06-28 half-propagated typo batch.

The two GT corpora describe the SAME ink at different scopes:

    raw_benchmarks/<id>.md    all ink, per page      (scores Phase 1)
    draft_benchmarks/<id>.md  answer content only    (scores Phase 2 / e2e)

Draft is therefore a SUBSET of raw modulo the documented exclusions (section
markers, margin notes, identity). Wherever both cover the same ink they must
agree. A token that exists in draft but nowhere in raw is a defect in one of
them — see GT_ARTIFACTS_REPORT.md §8 F-0 for why this drifts: GT corrections
are verified with `mode=p1_only` runs, which never load the draft corpus.

Two divergence classes, because the subset relation is only half the story:

    ADDED   draft has text absent from the raw ink anywhere. Draft claims ink
            the page transcription does not have. Always a defect in one of them.
    DROPPED raw has text INTERIOR to an answer's alignment that draft lacks —
            i.e. a gap between two matched runs of the same answer, not a
            leading/trailing exclusion. `new` in `int[] arr = new int[tv]`
            (din_ezra Q2.ב) is the motivating case: it is invisible to a plain
            subset check, because a deletion looks exactly like a legitimate
            exclusion until you notice it sits mid-answer.

Raw text OUTSIDE any answer's alignment window is NOT reported: that is the
intentional-asymmetry case (headers, margin notes, dan_basiuk's closing note)
and is correct by design.

It cannot tell you WHICH corpus is right — only the source PDF can, and that
adjudication belongs to the GT author (CLAUDE.md §17.7). This just tells you
where to look.

Usage:
    python -m tests.transcription_eval_suit.check_gt_consistency          # all
    python -m tests.transcription_eval_suit.check_gt_consistency hobby_tvshow.din_ezra  # one

Exit 0 = consistent, 1 = draft-only text found.
"""
from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path

from app.services.transcription.normalize import normalize

from .ground_truth import load_ground_truth, load_page_ground_truth

SUITE_DIR = Path(__file__).parent
RAW_DIR = SUITE_DIR / "raw_benchmarks"
DRAFT_DIR = SUITE_DIR / "draft_benchmarks"

# Lines the draft format excludes by design: "שאלה 1", "א.", "שאלה 2 ג".
# Dropping them from the raw side is what makes the subset relation meaningful.
_HEADER_RE = re.compile(r"^\s*(שאלה\s*\d+\s*[א-ת]?\.?|[א-ת]\.)\s*$")

# Report a divergence only if it survives normalization AND is long enough to be
# a real token rather than a spacing artifact the normalizer already folded.
# Do NOT lower this to 1: a lone unmatched brace lets difflib pair an answer's
# trailing "}" with a "}" far later in the raw stream, and the whole span between
# them is then reported as one giant interior deletion. Verified on yonatan_basiuk.
# The cost of the floor is that single-character divergences are not reported.
_MIN_RUN = 2

# An "interior deletion" longer than this fraction of the answer is an alignment
# artifact, not a drop — a real omission from a transcribed answer is a token or
# a line, never most of the body.
_MAX_INTERIOR_FRACTION = 0.30


def _raw_ink(doc_id: str) -> str:
    """All raw ink for a doc, minus page delimiters and student section headers."""
    pages = load_page_ground_truth(RAW_DIR / f"{doc_id}.md").pages
    kept = [
        "\n".join(l for l in p.text.splitlines() if not _HEADER_RE.match(l))
        for p in pages
    ]
    return normalize("\n".join(kept), strip_illegible=False)


def _context(hay: str, lo: int, hi: int, width: int = 40) -> str:
    return hay[max(0, lo - width):lo] + " ⟪" + hay[lo:hi] + "⟫ " + hay[hi:hi + width]


def check_doc(doc_id: str) -> list[tuple[str, str, str, str]]:
    """Return [(kind, key, text, context)] for every cross-corpus divergence."""
    raw = _raw_ink(doc_id)
    findings: list[tuple[str, str, str, str]] = []

    for answer in load_ground_truth(DRAFT_DIR / f"{doc_id}.md").answers:
        body = normalize(answer.answer_text, strip_illegible=False)
        if not body:
            continue
        key = f"Q{answer.question_number}" + (
            f".{answer.sub_question_id}" if answer.sub_question_id else ""
        )
        # Align this answer against ALL raw ink: answers may span pages and appear
        # out of page order (omer_gelber), so the whole-document haystack is the
        # only sound comparison.
        sm = difflib.SequenceMatcher(None, raw, body, autojunk=False)
        opcodes = sm.get_opcodes()

        # The answer's footprint in the raw ink — everything between its first and
        # last matched run. Raw text outside this window is an intentional exclusion.
        matches = [b for b in sm.get_matching_blocks() if b.size >= _MIN_RUN]
        if not matches:
            continue
        interior_lo = matches[0].a
        interior_hi = matches[-1].a + matches[-1].size

        for tag, i1, i2, j1, j2 in opcodes:
            if tag in ("insert", "replace") and (j2 - j1) >= _MIN_RUN:
                findings.append(("ADDED", key, body[j1:j2], _context(body, j1, j2)))
            if tag in ("delete", "replace") and (i2 - i1) >= _MIN_RUN:
                interior = interior_lo < i1 and i2 < interior_hi
                plausible = (i2 - i1) <= _MAX_INTERIOR_FRACTION * len(body)
                if interior and plausible:
                    findings.append(("DROPPED", key, raw[i1:i2], _context(raw, i1, i2)))
    return findings


def main(argv: list[str]) -> int:
    doc_ids = argv[1:] or sorted(p.stem for p in DRAFT_DIR.glob("*.md"))
    total = 0

    for doc_id in doc_ids:
        findings = check_doc(doc_id)
        total += len(findings)
        if not findings:
            print(f"✓ {doc_id}: the two corpora agree on all shared ink")
            continue
        print(f"✗ {doc_id}: {len(findings)} divergence(s)")
        for kind, key, text, ctx in findings:
            arrow = "draft has, raw lacks" if kind == "ADDED" else "raw has, draft lacks"
            print(f"    [{kind:7}] {key}: {text!r}  ({arrow})")
            print(f"        {ctx}")

    if total:
        print(
            f"\n{total} divergence(s). Each is a defect in ONE of the two corpora — "
            "adjudicate against pdfs/<doc_id>.pdf.\nGT edits are the author's call "
            "(CLAUDE.md §17.7): surface with evidence, never silently fix."
        )
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
