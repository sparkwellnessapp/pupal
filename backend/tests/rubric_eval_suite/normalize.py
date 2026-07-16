"""
Normalization & similarity primitives for the rubric eval suite.

Ported disciplines from the transcription suite:
  - difflib with autojunk=False (the single most dangerous instrument bug there:
    autojunk silently dropped 'popular' characters on long strings and read a true
    0.88 ratio as 0.21). NEVER use difflib with default autojunk here.
  - NFC -> casefold -> collapse-whitespace normalizer, applied identically to both
    sides of every comparison.

This module is pure (no pipeline / no I/O). Everything it exposes is unit-testable
in isolation, because the scorer rides entirely on these primitives being correct.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Set

_WS = re.compile(r"\s+")

# Render-markup tokens emitted by parser_render: [[color:RRGGBB]], [[/color]],
# [[hl:name]], [[/hl]], and ~~strike~~ fences. They glue onto adjacent ink with no
# whitespace ("[[color:EE0000]]ניקוד:"), so a marker-blind tokenizer mangles the
# first/last token of every marked span — corrupting render-presence attribution
# (a GT criterion whose ink is marked scored as "absent from render" → false
# render_loss). Stripped for token comparisons; GT text never contains markup.
_RENDER_MARKUP = re.compile(r"\[\[color:[0-9A-Fa-f]{6}\]\]|\[\[/color\]\]"
                            r"|\[\[hl:[A-Za-z]+\]\]|\[\[/hl\]\]|~~")


def strip_render_markup(s: str) -> str:
    """Remove parser_render annotation markup, leaving the ink it wraps.

    Replacement is "" (not " "): markers WRAP ink flush against it, never displace
    it, so empty replacement is the exact inverse — substituting a space would
    inject phantom whitespace at span boundaries mid-token ("נקודות:" -> "נקודות :")."""
    return _RENDER_MARKUP.sub("", s)

# Hebrew alphabet in collation order — used to harmonize sub-question labels
# (א/ב/ג ...) with Latin (a/b/c ...) and numeric ((1)/(2) ...) labels onto a
# single index space so label-type drift between GT and prediction does not
# produce spurious structure mismatches.
_HEB = "אבגדהוזחטיכךלמםנןסעפףצץקרשת"
# Final-form letters share an index with their base form.
_HEB_FINAL = {"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"}
_HEB_ORDER = "אבגדהוזחטיכלמנסעפצקרשת"


def norm_text(s: str | None) -> str:
    """NFC -> strip format chars -> casefold -> collapse all whitespace -> strip.
    The comparison normal form.

    Format-char stripping (Unicode category Cf: LRM/RLM/bidi embeddings) is
    load-bearing: real Hebrew rubric ink embeds directionality marks around Latin
    identifiers (measured: 20 Cf chars in csharp_plane_combine), while GT is typed
    clean. Without stripping, a verbatim-correct extraction of marked ink scores a
    fake text mismatch against clean GT — the same instrument-error class as the
    din GT typos in the transcription suite.
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Cf")
    s = s.casefold()
    s = _WS.sub(" ", s).strip()
    return s


def ratio(a: str | None, b: str | None) -> float:
    """difflib similarity on the NORMALIZED strings, autojunk disabled. Range [0,1]."""
    na, nb = norm_text(a), norm_text(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb, autojunk=False).ratio()


def canon_subq_label(label: str | None) -> tuple[str, object]:
    """
    Harmonize a sub-question label to a comparable key.

    'א'/'a'/'1'/'(1)'/'1)'  -> ('idx', 0)
    'ב'/'b'/'2'             -> ('idx', 1)
    Unknown / multi-token   -> ('raw', normalized_string)

    Returning the same ('idx', n) for Hebrew/Latin/numeric lets the tree matcher
    pair nodes even when the model relabels (e.g. GT 'א' vs predicted '1'); the raw
    labels are still carried into the report so the drift remains visible.
    """
    if label is None:
        return ("raw", "")
    s = unicodedata.normalize("NFC", str(label)).strip()
    if not s:
        return ("raw", "")
    # single Hebrew letter (incl. final forms)
    base = _HEB_FINAL.get(s, s)
    if len(base) == 1 and base in _HEB_ORDER:
        return ("idx", _HEB_ORDER.index(base))
    # single Latin letter
    low = s.lower()
    if len(low) == 1 and "a" <= low <= "z":
        return ("idx", ord(low) - ord("a"))
    # numeric, possibly wrapped: '(1)', '1)', '1.', '1'
    digits = re.sub(r"\D", "", s)
    if digits:
        return ("idx", int(digits) - 1)  # 1-based label -> 0-based index
    return ("raw", norm_text(s))


def render_token_set(rendered_markdown: str) -> Set[str]:
    """Bag of normalized tokens (len >= 2) present anywhere in the rendered markdown.
    Render markup is stripped first — markers glue onto ink and mangle tokens."""
    return {t for t in norm_text(strip_render_markup(rendered_markdown)).split()
            if len(t) >= 2}


def present_in_render(text: str | None, render_tokens: Set[str], tau: float = 0.7) -> bool:
    """
    Is `text`'s content present in the render at all? (token-overlap, order-free).

    Used for ATTRIBUTION only: a GT criterion that is missing from the extraction is
    classified as a render_loss (its content never reached the LLM) vs an
    extraction_loss (content is in the render, the LLM dropped it). Token-overlap is
    the right tool here — 'is this content anywhere in the render' is a bag-of-words
    question, robust to the renderer splitting/reordering it (e.g. two-column criteria
    concatenated as 'col1: col2'). This is a heuristic; it is pinned by a regression
    test and reported transparently, never trusted blindly.
    """
    toks = [t for t in norm_text(text).split() if len(t) >= 2]
    if not toks:
        return True
    hits = sum(1 for t in toks if t in render_tokens)
    return (hits / len(toks)) >= tau


def canon_q(question_id: str | None) -> object:
    """
    Canonical question key for matching across pred/GT independent of the id string
    convention ('q1', 'question_1', '1' all -> 1). Falls back to the normalized
    string when no digits are present.
    """
    if question_id is None:
        return ""
    import re as _re
    digits = _re.sub(r"\D", "", str(question_id))
    return int(digits) if digits else norm_text(str(question_id))