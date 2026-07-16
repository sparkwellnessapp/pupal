"""
The transcription trust layer — cross-reader disagreement flags.

WHY THIS EXISTS
The primary transcriber's residual errors are SYSTEMATIC NORMALIZATIONS (its
language prior overrides its vision: `!=`→`==`, `School Hobbies`→`SchoolHobbies`,
adding `()` a student omitted). Signals derived from the model itself —
logprobs, self-consistency resampling, self-audit — are downstream of the same
prior and measurably blind to this class (resampling flagged 12.7% of critical
errors; self-audit 33% with worse precision). Independent DIVERSE readers are
not: on the golden set, the union of disagreements between the baseline and
2-3 cheap cross-family readers covered 92% of critical errors, including every
named stable ship-gate blocker.

WHAT IT IS
Pure functions (no I/O, no LLM) that turn N transcriptions of the same pages
into severity-tiered FLAG SPANS for the teacher:
    baseline pages + reader pages -> token-aligned disagreement spans
        -> classify (code / hebrew / marker) -> severity by reader-vote count
        -> anchor into draft answers -> plus a brace-balance lint.

Severity is driven by the measured vote ladder: P(span is a real error |
k readers disagree) ≈ 5% (k=1), 30% (k=2), 67% (k=3). Flags are ADVISORY —
they are never used to auto-correct text (verbatim contract; the teacher is
the authority), and no signal may SUPPRESS a disagreement (an LLM judge was
measured confirming the wrong baseline on 55/99 real errors — suppression
trades away exactly the recall this layer exists for).

SHARED between production (draft annotations) and the eval harness (trust-gate
metrics). One definition, like normalize.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from difflib import SequenceMatcher

from .page_provenance import best_line_match, norm_line

# ---------------------------------------------------------------------------
# Tokenization (subject-tolerant: code tokens + Hebrew word runs + symbols)
# ---------------------------------------------------------------------------

TOKEN_RE = re.compile(
    r"[A-Za-z_]\w*"                                   # identifiers / keywords
    r"|[֐-׿]+"                              # Hebrew word runs
    r"|\d+(?:\.\d+)?"                                 # numbers
    r"|==|!=|<=|>=|&&|\|\||\+=|-=|\*=|/=|%=|\+\+|--"  # multi-char operators
    r"|\[\?\]"                                        # illegible marker
    r"|[^\sA-Za-z_0-9֐-׿]"                  # any other symbol
)

_HEBREW_RE = re.compile(r"[֐-׿]")
_IDENT_RE = re.compile(r"[A-Za-z_]\w*")
# Section-marker forms P1 is instructed to emit: "שאלה 3" / "א ." token streams.
_MARKER_TOKENS_RE = re.compile(r"^(?:שאלה(?: \d+)?|[֐-׿] ?\.?|\d+|\.)$")

_CRIT_CHARS = frozenset(";{}()[]")
_CRIT_OPS = frozenset({
    "==", "!=", "<=", ">=", "&&", "||", "+=", "-=", "*=", "/=", "%=",
    "++", "--", "=", "<", ">", "!",
})


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text)


def tokenize_with_pos(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(0), m.start(), m.end()) for m in TOKEN_RE.finditer(text)]


def _norm_tok(t: str) -> str:
    # Case is folded: identifier CASE is not a Bagrut deduction (scorer Change C),
    # so case-only reader disagreements would be pure flag noise.
    return t.lower()


def _is_hebrew(tok: str) -> bool:
    return bool(_HEBREW_RE.search(tok))


# ---------------------------------------------------------------------------
# Span extraction
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FlagSpan:
    """One disagreement region, expressed on the BASELINE page text."""
    page: int
    i1: int                      # token range on the baseline page [i1, i2)
    i2: int
    char_start: int              # char offsets on the baseline page text
    char_end: int
    base_text: str               # what the baseline transcribed ("" = insertion)
    alternatives: tuple[str, ...]  # distinct reader readings of the same region
    n_readers: int               # how many readers disagreed here (severity driver)
    kind: str                    # "code" | "hebrew" | "marker"
    context_line: str            # the baseline line containing the span
    has_consensus: bool = False  # >=2 readers proposed the SAME reading
    anchor_key: str | None = None      # "q{n}" / "q{n}.{sub}" once anchored
    anchor_similarity: float = 0.0

    @property
    def severity(self) -> str:
        """The teacher-attention tier (display-only — the full span set is
        unchanged; any-tier coverage never depends on this).

        Calibrated on the labeled golden set (policy lab, two independent
        baselines): P(real error | k readers disagree) ≈ 0.11/0.36/0.68 for
        k=1/2/3, consensus (same alternative from >=2 readers) ≈ 0.57,
        punct-only spans ≈ 0.15. WARNING requires the disagreement to be
        ABOUT grade-critical content — the operator or identifier MULTISET
        actually differs between the baseline and a reader's alternative
        (a span merely near an operator is not an operator dispute):
          - operator disputes warn at ANY vote count (the grade-flipping
            class — 100% warn-tier coverage held on both lab baselines);
          - identifier disputes warn on STRONG evidence only: reader
            consensus on the same alternative, or all readers disagreeing.
        Everything else stays reviewable in the collapsed tier. Measured
        effect (tier "V3", reader set haiku+4o-mini@1400px+flash): warnings
        ~20/doc at unchanged any-tier coverage 0.93-0.95 (vs 31-37/doc under
        the pre-calibration rule)."""
        if self.kind != "code":
            return "info"
        base_toks = tokenize(self.base_text)
        base_ops = sorted(t for t in base_toks if t in _STRONG_OPS)
        base_ids = sorted(t.lower() for t in base_toks
                          if _ASCII_IDENT_RE.fullmatch(t))
        op_dispute = ident_dispute = False
        for a in self.alternatives:
            a_toks = tokenize(a)
            if sorted(t for t in a_toks if t in _STRONG_OPS) != base_ops:
                op_dispute = True
            if sorted(t.lower() for t in a_toks
                      if _ASCII_IDENT_RE.fullmatch(t)) != base_ids:
                ident_dispute = True
        if op_dispute:
            return "high"
        if ident_dispute and (self.has_consensus or self.n_readers >= 3):
            return "high"
        return "medium"


_STRONG_OPS = frozenset({
    "==", "!=", "<=", ">=", "&&", "||", "+=", "-=", "*=", "/=", "%=", "++", "--",
})
_ASCII_IDENT_RE = re.compile(r"[A-Za-z_]\w+")  # len >= 2


def _span_kind(base_toks: list[str], alt_toks: list[str]) -> str:
    all_toks = base_toks + alt_toks
    if all_toks and all(_is_hebrew(t) or t == "[?]" for t in all_toks):
        return "hebrew"
    # Marker spans must carry an actual marker signal (שאלה / Hebrew letter),
    # not merely digits/dots — a numeric literal diff is code, not chrome.
    if (all_toks and all(_MARKER_TOKENS_RE.fullmatch(t) for t in all_toks)
            and any(_is_hebrew(t) for t in all_toks)):
        return "marker"
    # COMMENT CONTENT: a span carrying Hebrew prose is comment/margin text
    # (Hebrew never appears in this domain's code) — the scorer itself strips
    # comments before critical-token extraction, so such spans are never
    # gate-critical. It stays "code" only if it ALSO carries a real code
    # signal: a multi-char operator or an ASCII identifier (e.g. a merged
    # span like `minn ב .` -> `min1 שאלה 2 ג`, or a margin note quoting CW/CR).
    if any(_is_hebrew(t) for t in all_toks):
        has_code_signal = any(
            t in _STRONG_OPS or _ASCII_IDENT_RE.fullmatch(t) for t in all_toks)
        if not has_code_signal:
            return "hebrew"
    for t in all_toks:
        if t in _CRIT_OPS or t in _CRIT_CHARS:
            return "code"
    if [t for t in base_toks if _IDENT_RE.fullmatch(t)] != \
       [t for t in alt_toks if _IDENT_RE.fullmatch(t)]:
        return "code"
    return "code" if any(not _is_hebrew(t) for t in all_toks) else "hebrew"


def diff_spans(base_toks: list[str], other_toks: list[str]) -> list[dict]:
    """Non-equal opcodes of SequenceMatcher(base, other), base-side ranges."""
    a = [_norm_tok(t) for t in base_toks]
    b = [_norm_tok(t) for t in other_toks]
    sm = SequenceMatcher(a=a, b=b, autojunk=False)
    return [
        {"i1": i1, "i2": i2,
         "base": base_toks[i1:i2], "other": other_toks[j1:j2]}
        for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal"
    ]


def merge_adjacent(spans: list[dict], gap: int = 1) -> list[dict]:
    """Spans within `gap` tokens merge into one review stop."""
    if not spans:
        return []
    spans = sorted(spans, key=lambda s: (s["i1"], s["i2"]))
    merged = [dict(spans[0])]
    for s in spans[1:]:
        last = merged[-1]
        if s["i1"] <= last["i2"] + gap:
            last["i2"] = max(last["i2"], s["i2"])
            last["base"] = last["base"] + s["base"]
            last["other"] = last["other"] + s["other"]
        else:
            merged.append(dict(s))
    return merged


def spans_overlap(a_i1: int, a_i2: int, b_i1: int, b_i2: int,
                  slack: int = 1) -> bool:
    return not (b_i2 + slack <= a_i1 or a_i2 + slack <= b_i1)


def _line_of(text: str, char_start: int, char_end: int) -> str:
    ls = text.rfind("\n", 0, char_start) + 1
    le = text.find("\n", char_end)
    return text[ls: len(text) if le == -1 else le]


# ---------------------------------------------------------------------------
# The flag computation (baseline vs N readers, one page)
# ---------------------------------------------------------------------------

def compute_page_flags(
    page_number: int,
    base_text: str,
    reader_texts: list[str],
) -> list[FlagSpan]:
    """Merge every reader's disagreement spans into per-region FlagSpans."""
    base_pos = tokenize_with_pos(base_text)
    base_toks = [t for t, _, _ in base_pos]

    merged: list[dict] = []
    for rtext in reader_texts:
        for f in merge_adjacent(diff_spans(base_toks, tokenize(rtext))):
            hit = next((m for m in merged
                        if spans_overlap(m["i1"], m["i2"], f["i1"], f["i2"])),
                       None)
            reading = " ".join(f["other"])
            if hit:
                hit["i1"] = min(hit["i1"], f["i1"])
                hit["i2"] = max(hit["i2"], f["i2"])
                hit["alts"].append(reading)
                hit["n"] += 1
            else:
                merged.append({"i1": f["i1"], "i2": f["i2"],
                               "alts": [reading], "n": 1})

    flags: list[FlagSpan] = []
    for m in merged:
        base_span_toks = base_toks[m["i1"]:m["i2"]]
        alt_toks = [t for a in m["alts"] for t in tokenize(a)]
        kind = _span_kind(base_span_toks, alt_toks)
        if m["i2"] > m["i1"] and m["i1"] < len(base_pos):
            cs = base_pos[m["i1"]][1]
            ce = base_pos[min(m["i2"], len(base_pos)) - 1][2]
        elif m["i1"] < len(base_pos):        # insertion before token i1
            cs, ce = base_pos[m["i1"]][1], base_pos[m["i1"]][2]
        else:                                # insertion at end of page
            cs = ce = len(base_text)
        # distinct alternatives, longest first (most informative for the teacher)
        seen: dict[str, None] = {}
        norm_counts: dict[tuple[str, ...], int] = {}
        for a in sorted(m["alts"], key=len, reverse=True):
            seen.setdefault(a, None)
            key = tuple(_norm_tok(t) for t in tokenize(a))
            norm_counts[key] = norm_counts.get(key, 0) + 1
        flags.append(FlagSpan(
            page=page_number, i1=m["i1"], i2=m["i2"],
            char_start=cs, char_end=ce,
            base_text=" ".join(base_span_toks),
            alternatives=tuple(seen),
            n_readers=m["n"], kind=kind,
            context_line=_line_of(base_text, cs, ce),
            has_consensus=max(norm_counts.values(), default=0) >= 2,
        ))
    return flags


def compute_flags(
    base_pages: dict[int, str],
    reader_pages: list[dict[int, str]],
) -> list[FlagSpan]:
    """All pages, all readers. Readers missing a page simply cast no vote there
    (a wholly-missing reader page must not flag the entire page as disagreement)."""
    flags: list[FlagSpan] = []
    for pno, btext in sorted(base_pages.items()):
        rtexts = [rp[pno] for rp in reader_pages
                  if pno in rp and rp[pno].strip()]
        if not btext.strip() or not rtexts:
            continue
        flags.extend(compute_page_flags(pno, btext, rtexts))
    return flags


# ---------------------------------------------------------------------------
# Anchoring flags into draft answers (page text -> answer the teacher reviews)
# ---------------------------------------------------------------------------

ANCHOR_THRESHOLD = 0.75


def anchor_flags(
    flags: list[FlagSpan],
    answers: dict[str, str],
) -> list[FlagSpan]:
    """Attach each flag to the answer containing its context line (fuzzy line
    match). Unanchored flags keep anchor_key=None -> page-level display."""
    ans_lines = {
        key: [norm_line(l) for l in text.splitlines() if norm_line(l)]
        for key, text in answers.items()
    }
    out = []
    for f in flags:
        target = norm_line(f.context_line)
        best_key, best_r = None, 0.0
        if target:
            for key, lines in ans_lines.items():
                r = best_line_match(target, lines)
                if r > best_r:
                    best_key, best_r = key, r
        if best_key is not None and best_r >= ANCHOR_THRESHOLD:
            out.append(replace(f, anchor_key=best_key,
                               anchor_similarity=best_r))
        else:
            out.append(f)
    return out


# ---------------------------------------------------------------------------
# Deterministic code lint (brace balance) — catches a slice of the errors ALL
# readers agree on (correlated normalization), measured zero-noise on the
# golden set: 4/30 answers fired, 2 true transcription drops + 2 true
# student-authored imbalances (still a useful, true note).
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LintFinding:
    answer_key: str
    balance: int  # positive: unclosed '{'; negative: extra '}'


def brace_lint(answers: dict[str, str]) -> list[LintFinding]:
    out = []
    for key, text in answers.items():
        bal = text.count("{") - text.count("}")
        if bal != 0:
            out.append(LintFinding(answer_key=key, balance=bal))
    return out
