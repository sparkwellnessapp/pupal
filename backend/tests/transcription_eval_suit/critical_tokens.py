"""
Critical-token signature — the V1 metric that catches what difflib is blind to.

WHY THIS EXISTS
A normalized difflib ratio rewards bulk character overlap. It cannot see the
single-character, grading-critical errors that flip correctness or hide a Bagrut
deduction:
    - "=" transcribed where the student wrote "==" (or vice-versa)
    - a dropped ";" or a call written without "()"  (Bagrut: deductions)
    - a method-call name misread ("GetRate" -> "GetRates")
    - an abbreviation EXPANDED by the model ("CW" -> "Console.WriteLine"),
      which both corrupts the transcription and erases a 5%-once deduction.

This metric extracts, per answer, a "signature" of grading-relevant tokens and
scores prediction-vs-ground-truth precision/recall over it. It runs on the RAW
text (whitespace-preserving) — the opposite of the difflib normalizer — because
the exact form IS the signal here. It is case-sensitive EXCEPT for three narrow,
grade-irrelevant case folds (see extract_signature): abbreviation matching folds
case unconditionally (Change A); method-call keywords fold under the scorer's
case_insensitive_keywords policy (Change B); and ALL method-call identifiers fold
under the case_insensitive_method_calls policy (Change C — method-name case is not
a Bagrut deduction). Each folds ONLY letter case; none collapses an expansion or
an identifier-content change (a letter add/drop stays a miss).

SUBJECT BOUNDARY (CLAUDE.md §3.3)
The scoring engine (scoring.py) is subject-agnostic. The token *patterns* live
here as a swappable `CriticalProfile`. JAVA_BAGRUT is the CS profile; a new
subject is a new profile, no engine change.

DELIBERATE SCOPE
Derived from the Bagrut deduction rules, MINUS two that require semantics, not
transcription fidelity, and therefore belong to the downstream GraderAgent:
    - "incorrect use of an interface action" (needs the interface's contract)
    - "using an undeclared variable"          (needs a symbol table)
The transcription eval only asks: did we capture the call name / identifier as
written? Whether that call is *correct* or that variable is *declared* is grading.

V1 SIMPLIFICATIONS (documented, not hidden)
    - Comments (// and /* */) and string/char literal CONTENTS are stripped before
      tokenizing, so punctuation inside them is not counted. The strip is
      sequential (block, line, string, char) — it does not model comments nested
      inside strings or vice-versa. Adequate for handwritten exam code; revisit if
      a fixture breaks it.
    - A "//" line comment is stripped ONLY when newline-terminated, so that a
      prediction flattened onto one physical line (the model dropping newlines the
      schema asked it to keep) cannot have its code devoured by a single "//".
      Critical-token extraction is thereby layout-invariant, matching the difflib
      metric which already strips all whitespace. (See _LINE_COMMENT_RE.)
    - Bare binary arithmetic (+, -, *, /, %) is intentionally EXCLUDED from the
      operator set: it is formatting-noisy and not in the Bagrut deduction list.
      Compound assignment (+=, ...) and increment (++/--) ARE included.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class CriticalProfile:
    """A subject's grading-critical token vocabulary."""
    name: str
    operators: tuple[str, ...]      # compared as a multiset; order here is irrelevant
    structural: tuple[str, ...]     # single-char structural tokens; multiset
    abbreviations: tuple[str, ...]  # whole-word shorthands whose expansion is a deduction
    keywords: tuple[str, ...] = ()  # subject keywords whose CASE is not grade-relevant
    #   (Change B). Only meaningful where a keyword can appear as a comparable
    #   *token* — in this signature model that is method_calls (e.g. `for(`,
    #   `while(`, captured by _METHOD_CALL_RE). Folded to lower-case at extraction
    #   ONLY when the scorer's case_insensitive_keywords policy is on. A keyword
    #   that never precedes '(' (public/void) simply never enters any counter, so
    #   listing it here is harmless. Subject-specific by design (CLAUDE.md §3.3):
    #   the engine reads this tuple, it does not know the language.


@dataclass(frozen=True)
class Signature:
    """Extracted grading-critical features of one piece (or aggregate) of code."""
    operators: Counter      # token -> count
    structural: Counter     # token -> count
    method_calls: frozenset[str]  # identifier names immediately followed by '('
    abbreviations: Counter  # abbreviation -> count


# --- CS / Israeli-Bagrut profile -------------------------------------------------

JAVA_BAGRUT = CriticalProfile(
    name="java_bagrut",
    operators=(
        # comparison / logical / negation — flipping any changes control flow
        "==", "!=", "<=", ">=", "&&", "||", "!", "<", ">",
        # assignment + compound + increment
        "+=", "-=", "*=", "/=", "%=", "++", "--", "=",
    ),
    structural=(";", "{", "}", "(", ")", "[", "]"),
    # Seeded from real data (moran_aharon): Console.WriteLine / ReadLine shorthands.
    # Grow as fixtures reveal more standard Bagrut shorthands.
    abbreviations=("CW", "CR"),
    # C# reserved words. Their letter-case is not a Bagrut deduction (`For` vs
    # `for` grades identically), so under the case_insensitive_keywords policy a
    # method-call-position keyword folds to lower-case before comparison. These
    # are reserved words — a student identifier can never collide with one. No
    # case fold (keyword OR the broader identifier fold, Change C) collapses an
    # identifier-CONTENT error: a misread GetRate->GetRates (a letter add) stays a
    # miss; only letter-case is ever folded. Expanded beyond the spec's named
    # examples to the standard C# set so the fold is uniform, not ad hoc.
    keywords=(
        "if", "else", "for", "foreach", "while", "do", "switch", "case",
        "default", "return", "break", "continue", "public", "private",
        "protected", "internal", "static", "void", "class", "new", "using",
        "namespace", "try", "catch", "finally", "throw", "lock",
    ),
)


# --- extraction (pure) ----------------------------------------------------------

_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
# The trailing "\n" is LOAD-BEARING — a "//" comment is stripped ONLY when it is
# newline-terminated. Without it (the historical `//[^\n]*`), a prediction that the
# model flattened onto a single line — legal output the schema permits, and common
# when a cheap model is under token pressure — would let the FIRST "//" swallow the
# entire rest of the answer, deleting every operator / bracket / method call after
# it. That cratered critical-token RECALL on faithful transcriptions (observed:
# structural recall 0.457, method_call 0.406 with precision pinned at 1.0 — the
# signature of a decimated prediction signature, not a transcription error). With
# the terminator required, a flattened answer simply keeps its "//" runs inline;
# their natural-language prose contributes no critical tokens, so recall is honest.
# For normal multi-line code this is byte-identical to the old behavior. An
# unterminated trailing comment on the final line is left in place (harmless: prose,
# not code). See test_line_comment_strip_is_layout_invariant.
_LINE_COMMENT_RE = re.compile(r"//[^\n]*\n")
_STRING_RE = re.compile(r"\"(?:[^\"\\]|\\.)*\"")
_CHAR_RE = re.compile(r"'(?:[^'\\]|\\.)*'")
_METHOD_CALL_RE = re.compile(r"([A-Za-z_]\w*)\s*\(")


def _strip_comments_and_strings(code: str) -> str:
    """Remove comment and literal CONTENTS so their punctuation isn't counted.

    String/char literals collapse to empty quotes' worth of nothing; the
    surrounding code structure (including a call's parentheses) is preserved:
        CW("average is:")  ->  CW()
    """
    code = _BLOCK_COMMENT_RE.sub("", code)
    # Replace with the terminating newline (not "") so line structure is preserved
    # and the strip stays a no-op-equivalent to the historical behavior on
    # multi-line code (see _LINE_COMMENT_RE for why the terminator is required).
    code = _LINE_COMMENT_RE.sub("\n", code)
    code = _STRING_RE.sub("", code)
    code = _CHAR_RE.sub("", code)
    return code


def _build_operator_re(profile: CriticalProfile) -> re.Pattern[str]:
    # Longest-first so "==" wins over "=", "<=" over "<", "!=" over "!", etc.
    ordered = sorted(profile.operators, key=len, reverse=True)
    return re.compile("|".join(re.escape(op) for op in ordered))


def extract_signature(
    code: str,
    profile: CriticalProfile,
    *,
    fold_keyword_case: bool = False,
    fold_identifier_case: bool = False,
) -> Signature:
    """Extract the grading-critical signature from raw code. Pure.

    Operators and structural tokens are punctuation — they carry no case and are
    extracted exactly. Up to THREE NARROW case folds apply, each on a single axis;
    none collapses an EXPANSION or an identifier-CONTENT change (a letter add/drop):

      ABBREVIATIONS are matched case-insensitively (Change A): `\\bCW\\b` ignores
      letter case, so CW/cw/Cw/cW all count as the one abbreviation "CW". This
      folds ONLY case — it does NOT collapse an EXPANSION. "CW" -> "cw" keeps the
      count (not flagged altered); "CW" -> "Console.WriteLine" removes the
      \\bCW\\b token entirely, so the count drops and the expansion is STILL
      flagged. Case-folding and expansion-detection are different axes; only the
      former is folded. (This also strengthens detection: a lower-case `cw`
      expansion, previously invisible to the case-sensitive \\bCW\\b, is now
      caught.)

      METHOD-CALL keywords fold to lower-case ONLY when `fold_keyword_case` is set
      and the captured token is in `profile.keywords` (Change B). So For()/for(),
      While()/while() compare equal, while a real identifier (GetRate) — never a
      keyword — stays case-exact under this fold alone.

      METHOD-CALL identifiers fold to lower-case when `fold_identifier_case` is set
      (Change C — Noam's 2026-06-27 ruling that method-name CASE is not a Bagrut
      deduction, reversing the earlier identifier-case-sensitive lock). This folds
      ALL method-call tokens (`printAverages`/`PrintAverages`, `CW`/`cw`,
      `GetChl`/`Getchl` compare equal) and SUPERSEDES the keyword-only fold. It
      folds ONLY case: a CONTENT misread (a letter add/drop, `GetArrShows` ->
      `GetArrShow`) still misses, so genuine identifier misreads stay detected.
    """
    cleaned = _strip_comments_and_strings(code)

    operators = Counter(_build_operator_re(profile).findall(cleaned))

    structural = Counter(ch for ch in cleaned if ch in set(profile.structural))

    calls = _METHOD_CALL_RE.findall(cleaned)
    if fold_identifier_case:
        # Change C: method-name case is not graded -> fold every method-call token's
        # case. Supersedes the keyword-only fold. Case only: content (letter add/drop)
        # is untouched, so a real misread like GetArrShows->GetArrShow still misses.
        calls = [c.lower() for c in calls]
    elif fold_keyword_case and profile.keywords:
        kw = {k.lower() for k in profile.keywords}
        calls = [c.lower() if c.lower() in kw else c for c in calls]
    method_calls = frozenset(calls)

    abbreviations: Counter = Counter()
    for abbr in profile.abbreviations:
        # IGNORECASE folds letter-case ONLY (Change A). Word boundaries still
        # require the abbreviation to stand alone, so an EXPANSION to its full
        # form removes the token and is still counted as altered downstream.
        n = len(re.findall(rf"\b{re.escape(abbr)}\b", cleaned, re.IGNORECASE))
        if n:
            abbreviations[abbr] = n

    return Signature(
        operators=operators,
        structural=structural,
        method_calls=method_calls,
        abbreviations=abbreviations,
    )


def merge_signatures(sigs: list[Signature]) -> Signature:
    """Aggregate per-answer signatures into one document-level signature."""
    operators: Counter = Counter()
    structural: Counter = Counter()
    method_calls: set[str] = set()
    abbreviations: Counter = Counter()
    for s in sigs:
        operators.update(s.operators)
        structural.update(s.structural)
        method_calls |= s.method_calls
        abbreviations.update(s.abbreviations)
    return Signature(operators, structural, frozenset(method_calls), abbreviations)
