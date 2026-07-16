"""
Page provenance — deterministically map answer text back to the source page(s)
it was transcribed from, with a confidence score.

SHARED between production (TranscriptionDraftAnswer.page_numbers) and the eval
harness (provenance validation). One definition (CLAUDE.md "one concept, one
place"), like normalize.py.

Algorithm (pure, no LLM): split the answer into lines; for each line find the
best-matching line on each page (difflib ratio over a casefolded,
whitespace-stripped form); pages win weighted line votes. Validated on the
5-fixture golden set: 30/30 correct attributions on clean AND noisy pages,
including answers assembled across non-adjacent pages.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

# A line must match at least this well somewhere to cast a page vote.
LINE_VOTE_THRESHOLD = 0.75
# Pages below this share of an answer's line votes are dropped from its page set.
MIN_PAGE_WEIGHT = 0.15
# Lines shorter than this (normalized) are too generic to vote (e.g. "}").
MIN_VOTING_LINE_LEN = 4


def norm_line(s: str) -> str:
    """NFC + casefold + strip ALL whitespace — the line-match form."""
    s = unicodedata.normalize("NFC", s).lower()
    return "".join(s.split())


def best_line_match(target_norm: str, lines_norm: list[str]) -> float:
    """Highest difflib ratio of target against any candidate line."""
    best = 0.0
    for ln in lines_norm:
        if not ln:
            continue
        r = SequenceMatcher(a=target_norm, b=ln, autojunk=False).ratio()
        if r > best:
            best = r
    return best


@dataclass(frozen=True)
class PageAttribution:
    """Where one answer's text lives, with confidence."""
    page_weights: dict[int, float] = field(default_factory=dict)  # page -> share of votes
    confidence: float = 0.0   # mean best-line ratio over voting lines
    n_lines: int = 0          # voting lines considered

    @property
    def pages(self) -> list[int]:
        """Attributed pages, strongest first."""
        return [p for p, _ in sorted(self.page_weights.items(),
                                     key=lambda kv: -kv[1])]


def align_answer_to_pages(
    answer_text: str,
    pages: dict[int, str],
) -> PageAttribution:
    """Attribute one answer's text to source pages by line voting. Pure."""
    ans_lines = [norm_line(l) for l in answer_text.splitlines()]
    ans_lines = [l for l in ans_lines if len(l) >= MIN_VOTING_LINE_LEN]
    if not ans_lines:
        return PageAttribution()

    page_lines = {
        p: [norm_line(l) for l in text.splitlines() if norm_line(l)]
        for p, text in pages.items()
    }

    votes: dict[int, float] = {}
    ratios: list[float] = []
    for al in ans_lines:
        best_page, best_r = None, 0.0
        for p, plines in page_lines.items():
            r = best_line_match(al, plines)
            if r > best_r:
                best_page, best_r = p, r
        ratios.append(best_r)
        if best_page is not None and best_r >= LINE_VOTE_THRESHOLD:
            votes[best_page] = votes.get(best_page, 0.0) + 1.0

    total = sum(votes.values())
    weights = (
        {p: v / total for p, v in votes.items() if v / total >= MIN_PAGE_WEIGHT}
        if total else {}
    )
    return PageAttribution(
        page_weights=weights,
        confidence=sum(ratios) / len(ratios),
        n_lines=len(ans_lines),
    )
