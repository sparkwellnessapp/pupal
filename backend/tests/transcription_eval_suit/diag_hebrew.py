"""
diag_hebrew.py — the HEBREW diagnostic (MISSION §4.3). Additive: nothing in the
gate path reads it.

WHY A PROJECTION. The gated ratio compares everything at once, and on a page of
code the handful of Hebrew characters (a two-line comment, a one-sentence free
answer) is a rounding error inside it: a Hebrew line read badly barely moves
`doc_ratio_strict`. Projecting both sides onto Hebrew-script characters ONLY —
after the suite's own normalizer — isolates exactly those characters. It is blind
to code and punctuation by design; that blindness is the point.

Two numbers, because they fail differently:
  * projection ratio — difflib over the Hebrew character streams (`autojunk=False`,
    load-bearing for the same reason it is in scoring.py);
  * Hebrew WER — word-level Levenshtein over Hebrew-bearing words, each projected
    to its Hebrew letters, divided by the gold word count. A ratio forgives one
    wrong letter in a long answer; WER charges the whole word, which is what the
    teacher re-reads.

A page with no Hebrew in EITHER side contributes nothing (it is not a Hebrew
measurement). A page with none in gold but some in the prediction scores 0.0 —
invented Hebrew is an error.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass

from app.services.transcription.normalize import normalize

HEB_LO, HEB_HI = 0x0590, 0x05FF


# A WHOLE line that is only section markers: `שאלה 3`, `א.`, and the non-canonical
# forms the bagrut GT carries (`(1)`, `א) (1)`, `(ב) (1)`). These are Hebrew
# script but not Hebrew TEXT: on a code-heavy hobby page they can be ALL of the
# Hebrew there is (din_ezra: 30 characters, every one a marker), so one misread
# letter (`ב.` for `א.`) swings the all-Hebrew ratio while no comment was touched. The prose view drops them
# on BOTH sides; the all-Hebrew view keeps them. A marker followed by prose on the
# same line (`(2) לבדוק אם ...`) is prose and stays.
_MARK = r"(?:\([א-ת0-9]{1,2}\)|[א-ת0-9]{1,2}[.)]|\d{1,2})"
_MARKER_LINE = re.compile(rf"^\s*(?:שאלה\s*[\dא-ת]{{1,2}}[.)]?(?=\s|$))?(?:\s*{_MARK}(?=\s|$))*\s*$")


def strip_marker_lines(text: str) -> str:
    return "\n".join(ln for ln in (text or "").split("\n")
                     if not (ln.strip() and _MARKER_LINE.match(ln)))


def is_hebrew(ch: str) -> bool:
    return HEB_LO <= ord(ch) <= HEB_HI


def project(text: str) -> str:
    """Hebrew-script characters only, after the suite's normalizer."""
    return "".join(ch for ch in normalize(text or "", strip_illegible=False)
                   if is_hebrew(ch))


def hebrew_words(text: str) -> list[str]:
    """Hebrew-bearing words, each reduced to its Hebrew letters. Word boundaries
    need the whitespace the normalizer deletes, so this uses NFC + lowercase
    only — the same two folds, minus the deletion."""
    t = unicodedata.normalize("NFC", text or "").lower()
    out = []
    for tok in t.split():
        h = "".join(ch for ch in tok if is_hebrew(ch))
        if h:
            out.append(h)
    return out


def _ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def _levenshtein(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


@dataclass(frozen=True)
class HebrewScore:
    gold_chars: int
    pred_chars: int
    ratio: float | None          # None = no Hebrew on either side
    gold_words: int
    word_errors: int

    @property
    def wer(self) -> float | None:
        if self.gold_words == 0:
            return None if self.ratio is None else (0.0 if not self.word_errors else 1.0)
        return self.word_errors / self.gold_words

    def as_dict(self) -> dict:
        return {"gold_chars": self.gold_chars, "pred_chars": self.pred_chars,
                "ratio": self.ratio, "gold_words": self.gold_words,
                "word_errors": self.word_errors, "wer": self.wer}


def score_hebrew(gold: str, pred: str) -> HebrewScore:
    g, p = project(gold), project(pred)
    gw, pw = hebrew_words(gold), hebrew_words(pred)
    if not g and not p:
        return HebrewScore(0, 0, None, 0, 0)
    return HebrewScore(len(g), len(p), _ratio(g, p), len(gw), _levenshtein(gw, pw))


def score_units(gold: dict, pred: dict, *, markers: bool = True) -> dict:
    """Per-unit (page or answer key) scores plus the document aggregate, which is
    computed over the CONCATENATION in gold order — not a mean of ratios, so a
    long Hebrew answer weighs more than a one-word comment, as it should.
    `markers=False` is the PROSE view (see `strip_marker_lines`)."""
    if not markers:
        gold = {k: strip_marker_lines(v) for k, v in gold.items()}
        pred = {k: strip_marker_lines(v) for k, v in pred.items()}
    units = {}
    for k in gold:
        s = score_hebrew(gold[k], pred.get(k, ""))
        if s.ratio is not None:
            units[str(k)] = s.as_dict()
    extra = [k for k in pred if k not in gold]
    g_all = "\n".join(gold[k] for k in gold)
    p_all = "\n".join([pred.get(k, "") for k in gold] + [pred[k] for k in extra])
    doc = score_hebrew(g_all, p_all)
    return {"doc": doc.as_dict(), "units": units}
