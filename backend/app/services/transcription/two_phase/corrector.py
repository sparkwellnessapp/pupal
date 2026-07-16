"""
corrector.py — the deterministic post-pass that repairs transcription
ARTIFACTS without overwriting faithful student errors.

It is a PURE function over text. It runs AFTER the spec-blind Phase-1 model and
after Phase-2 segmentation; the LLM never sees correction logic. The scorer
reads the spec to correct; the Phase-1 model never does. This is what keeps the
anti-contamination property intact while still letting the prod-realistic
(post-repair) numbers appear in scores and reports.

THE SAFETY MODEL (the load-bearing distinction):
  The risk is overwriting a gradeable student error. Safety is decided by the
  CORRECTION TARGET class, not by surface similarity:

  - tier "impossible": correct a token only toward a KEYWORD. Keywords are a
    closed, language-defined vocabulary — never answer content. A token that is
    not (case-insensitively) a keyword but is within edit distance <=2 of a
    UNIQUE keyword is a misspelled keyword (`privaze`->`private`,
    `doble`->`double`): an artifact, safe to repair.
  - tier "spec": ALSO correct a token toward a SPEC IDENTIFIER (`Mobby`->`Hobby`,
    `GetArrShow`->`GetArrShows`). Spec identifiers ARE answer-adjacent content,
    so this tier can overwrite a real student error. It is OFF by default and
    its false-fix rate against faithful GT is the kill criterion (measured in
    the scorer, requires n>=10 with included student-spec-errors).

EXPLICIT NON-GOALS (conservative by design — these FLAG, never auto-correct):
  - Keyword CASING is never corrected: `While`/`Public`/`For` match a keyword
    case-INSENSITIVELY, so they are "known" and left untouched. (We logged
    casing edits as unauthorized last run; reversing that needs its own
    decision.)
  - Severe corruptions (mid-word whitespace splits like `count Sport`, illegal
    mid-identifier chars like `durot:on`) are NOT merged/repaired: the
    tokenizer splits them and no single piece lands within distance 2 of a
    unique target, so they remain and surface as flags. Repairing them safely
    would require ink we do not have.
  - Protected abbreviations (`CW`, `CR`) are treated as known: never corrected.

Uniqueness rule: a token corrects ONLY if exactly one target sits within
EDIT_MAX of it. Ties or nothing-within-EDIT_MAX -> left as written (flagged by
absence of correction). No guessing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

EDIT_MAX = 2  # confirmed threshold; catches 1-2 char artifacts, flags severe ones

# C# language keywords + primitive types. Closed set, NOT answer content.
CSHARP_KEYWORDS: frozenset[str] = frozenset({
    "abstract", "as", "base", "bool", "break", "byte", "case", "catch", "char",
    "checked", "class", "const", "continue", "decimal", "default", "delegate",
    "do", "double", "else", "enum", "event", "explicit", "extern", "false",
    "finally", "fixed", "float", "for", "foreach", "goto", "if", "implicit",
    "in", "int", "interface", "internal", "is", "lock", "long", "namespace",
    "new", "null", "object", "operator", "out", "override", "params", "private",
    "protected", "public", "readonly", "ref", "return", "sbyte", "sealed",
    "short", "sizeof", "stackalloc", "static", "string", "struct", "switch",
    "this", "throw", "true", "try", "typeof", "uint", "ulong", "unchecked",
    "unsafe", "ushort", "using", "var", "virtual", "void", "volatile", "while",
})

# Student abbreviations that must NEVER be corrected (they are the student's ink).
PROTECTED_TOKENS: frozenset[str] = frozenset({"CW", "CR"})

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True)
class Correction:
    original: str
    corrected: str
    tier: str          # "impossible" | "spec"
    target_kind: str   # "keyword" | "spec_identifier"


@dataclass(frozen=True)
class CorrectionResult:
    text: str
    corrections: tuple[Correction, ...]


def _bounded_levenshtein(a: str, b: str, max_d: int) -> int:
    """Levenshtein with early exit; returns max_d + 1 if distance exceeds max_d."""
    if abs(len(a) - len(b)) > max_d:
        return max_d + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        row_min = i
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            cur.append(v)
            row_min = min(row_min, v)
        if row_min > max_d:
            return max_d + 1
        prev = cur
    return prev[-1]


def _unique_target(token: str, candidates: frozenset[str], *, min_len: int = 3) -> str | None:
    """The single candidate within the length-guarded edit budget, or None.

    Distance budget: 1 for len in [min_len,4], 2 for len >= 5. Plus a hard
    floor of `min_len` on the token. Keyword targets pass min_len=5 (see
    correct_text) because short keywords (`for`,`var`,`int`,`new`) collide at
    distance 1 with deliberate short identifiers (`foo`,`bar`); the misspelled
    keywords actually worth repairing (`privaze`,`doble`,`while`-class) are all
    length >= 5. Spec-identifier targets keep min_len=3 (they're rarely that
    short, and `Hoby`->`Hobby` at len4 is wanted)."""
    if len(token) < min_len:
        return None
    max_allowed = 2 if len(token) >= 5 else 1
    best: list[str] = []
    best_d = max_allowed + 1
    for cand in candidates:
        d = _bounded_levenshtein(token, cand, max_allowed)
        if d == 0:
            return None  # exact match: token IS this candidate; not a correction
        if d <= max_allowed:
            if d < best_d:
                best_d, best = d, [cand]
            elif d == best_d:
                best.append(cand)
    if len(best) == 1:
        return best[0]
    return None  # zero candidates, or a tie -> no unique target -> flag (no fix)


def correct_text(
    text: str,
    *,
    policy: str,                       # "off" | "impossible" | "spec"
    spec_identifiers: frozenset[str] = frozenset(),
    keywords: frozenset[str] = CSHARP_KEYWORDS,
    protected: frozenset[str] = PROTECTED_TOKENS,
) -> CorrectionResult:
    """Repair artifact tokens per policy. Pure; deterministic; returns the
    corrected text plus the list of corrections applied (for evidence/scoring).
    """
    if policy == "off" or not text:
        return CorrectionResult(text=text, corrections=())

    kw_lower = {k.lower() for k in keywords}
    corrections: list[Correction] = []

    def repl(m: re.Match) -> str:
        tok = m.group(0)
        if tok in protected:
            return tok
        if tok.lower() in kw_lower:
            return tok            # known keyword (any casing) -> never touched
        if tok in spec_identifiers:
            return tok            # exact spec identifier -> already correct

        # tier "impossible": correct only toward a unique keyword (len>=5 guard).
        target = _unique_target(tok, keywords, min_len=5)
        if target is not None:
            corrections.append(Correction(tok, target, "impossible", "keyword"))
            return target

        # tier "spec": additionally correct toward a unique spec identifier.
        if policy == "spec" and spec_identifiers:
            target = _unique_target(tok, spec_identifiers, min_len=3)
            if target is not None:
                corrections.append(
                    Correction(tok, target, "spec", "spec_identifier")
                )
                return target
        return tok

    out = _IDENT_RE.sub(repl, text)
    return CorrectionResult(text=out, corrections=tuple(corrections))
