"""
E-1..E-5 — the deterministic checks on a reasoning line (PR_grader_v6_options.md §7.5). Pure.

A line that fails any rule is replaced, for THAT terminal only, by the fallback line; the
failed rule ids are recorded. Nothing here is retried and nothing here repairs a line.

E-1 Coverage   exactly one line per credit terminal of the call. A line addressed to an
               alias the call did not issue is dropped through the one closed-world
               function, `grader.validator.strip_out_of_world`, WITHOUT `rekey` (AM-G17: an
               alias has nothing to romanise, so no CWV-6). Duplicates: the first wins. A
               terminal left without a line fails E-1.
E-2 Length     1..200 characters after trimming (internal whitespace runs collapse to one
               space first; that normalised text is the line that is kept).
E-3 Vocabulary no internal term (`copy.MACHINE_VOCABULARY`) and no rule id
               (`(PL|PB|PRC|OD|INV|CW|V|P|X|E)-?\\d+`). Latin terms and rule ids match on
               ASCII token boundaries — stricter than `\\b`, which in Python treats a Hebrew
               letter as a word character and so misses «בPL-10». Hebrew terms match as
               substrings after apostrophe/whitespace normalisation.
               SUBJECT-MATTER EXEMPTION: a hit that also occurs in the teacher's text, the
               question, the example solution or a quoted span of the answer is the subject,
               not the machinery — a variable `P1`, a velocity `V2`, a method `Check`, an
               essay «על בינה מלאכותית». Planner-written labels and the verifier's absence
               pointers do NOT exempt (they are machine-written).
E-4 Numbers    every number in the line is in `allowed_numbers(scope, terminal)`, compared
               numerically (Decimal: «1.5» == «1.50»; «½ ¼ ¾» parse; signs ignored, since
               amounts are compared by absolute value). Digits only — a number written as a
               Hebrew word is not parsed (the prompt asks for digits).
E-5 Voice      no word from `copy.VOICE_MARKERS`, on HEBREW WORD BOUNDARIES with the
               proclitics: a token matches a marker M when it is P+M, P being up to three
               of «ו ה ש ב כ ל מ» («ואני», «שבדקתי», «משלי»); a marker that starts with the
               article «ה» also matches with the article absorbed after «ב/כ/ל»
               («לתלמיד», «בתלמידה»). A marker never matches inside a longer word
               («שלישי», «מאניה» pass). Niqqud is stripped first.

The allowed numbers (E-4) are a pure function of the recorded input, so a replay on
another model (§13.4) validates identically with no pricer:
  awarded · points_possible · every credit's selected value · |amount| and |charged| of
  every fault · and every number written in: her criterion text, the interpretation notes,
  the question, the example solution, the checks' descriptions and selected labels (a
  count label «5 מתוך 8 נכונים» is plan data), the verified quotes, and the teacher text
  of a charged-elsewhere / pinned criterion. NOT the verifier's absence pointers: they are
  its summary of the answer, not the answer.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple

from app.agents.explainer.copy import MACHINE_VOCABULARY, MAX_LINE, VOICE_MARKERS
from app.agents.explainer.payload import (
    ScopeExplainerInput,
    TerminalExplainerInput,
    alias_table,
)
from app.agents.grader.validator import strip_out_of_world

__all__ = ["RULES", "LineVerdict", "ScopeValidation", "validate_scope", "validate_line",
           "normalize_line", "e2_length_ok", "e3_vocabulary_ok", "e4_numbers_ok",
           "e5_voice_ok", "allowed_numbers", "numbers_in", "RULE_ID"]

RULES = ("E-1", "E-2", "E-3", "E-4", "E-5")

# ── E-3 ─────────────────────────────────────────────────────────────────────
_ASCII_WORD = "A-Za-z0-9_"
RULE_ID = re.compile(rf"(?<![{_ASCII_WORD}])(?:PL|PB|PRC|OD|INV|CW|V|P|X|E)-?[0-9]+(?![{_ASCII_WORD}])")
_LATIN_TERM = re.compile(r"^[A-Za-z]+$")
_APOSTROPHES = str.maketrans({"׳": "'", "’": "'", "‘": "'", "`": "'", "´": "'"})

# ── E-4 ─────────────────────────────────────────────────────────────────────
_NUMBER = re.compile(r"(?<![0-9])(?:[0-9]+(?:[.,][0-9]+)?|[.,][0-9]+)|[½¼¾]")
_FRACTION = {"½": Decimal("0.5"), "¼": Decimal("0.25"), "¾": Decimal("0.75")}

# ── E-5 ─────────────────────────────────────────────────────────────────────
_PROCLITICS = "והשבכלמ"
_ARTICLE_ABSORBERS = "בכל"
_HEBREW_WORD = re.compile(r"[א-ת]+")


@dataclass(frozen=True)
class LineVerdict:
    """One credit terminal's outcome: the model's (normalised) line when it passed every
    rule, else None and the rules it failed (E-1 alone when there was no line)."""
    terminal_id: str                                  # the REAL id
    text_he: Optional[str]
    failed_rules: Tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.text_he is not None


@dataclass
class ScopeValidation:
    verdicts: Dict[str, LineVerdict]                  # real terminal id → verdict
    telemetry: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# the scope
# ═══════════════════════════════════════════════════════════════════════════

def validate_scope(lines: Sequence[Tuple[str, str]], inp: ScopeExplainerInput) -> ScopeValidation:
    """`lines` = the model's (alias, text) pairs, in its order. Every terminal of the
    input gets a verdict."""
    table = alias_table(inp)
    tel: List[str] = []
    kept, flags, _annotations = strip_out_of_world(
        list(lines), key=lambda x: x[0], known=table.issued("t"), scope_id=inp.scope_id,
        describe=lambda x: f"{len(x[1] or '')} chars")
    # the explainer has no teacher surface for a machine's addressing: the INFO
    # annotation's place is the telemetry (as the planner's, assemble._unalias)
    tel.extend(f"scope={inp.scope_id} alias_dropped terminal: {f.message}" for f in flags)

    first: Dict[str, str] = {}
    for alias, text in kept:
        if alias in first:
            tel.append(f"scope={inp.scope_id} duplicate_line {alias}: first kept")
            continue
        first[alias] = text

    verdicts: Dict[str, LineVerdict] = {}
    for t in inp.terminals:
        text = first.get(t.alias)
        if text is None:
            verdicts[t.terminal_id] = LineVerdict(t.terminal_id, None, ("E-1",))
            continue
        line = normalize_line(text)
        failed = validate_line(line, inp, t)
        verdicts[t.terminal_id] = LineVerdict(t.terminal_id, None if failed else line,
                                              tuple(failed))
    return ScopeValidation(verdicts=verdicts, telemetry=tel)


def validate_line(line: str, inp: ScopeExplainerInput, t: TerminalExplainerInput) -> List[str]:
    """E-2..E-5 on one normalised line; the failed rule ids, in rule order."""
    failed: List[str] = []
    if not e2_length_ok(line):
        failed.append("E-2")
    if not e3_vocabulary_ok(line, _exempting_corpus(inp, t)):
        failed.append("E-3")
    if not e4_numbers_ok(line, allowed_numbers(inp, t)):
        failed.append("E-4")
    if not e5_voice_ok(line):
        failed.append("E-5")
    return failed


def normalize_line(text: Optional[str]) -> str:
    return " ".join((text or "").split())


# ═══════════════════════════════════════════════════════════════════════════
# E-2
# ═══════════════════════════════════════════════════════════════════════════

def e2_length_ok(line: str) -> bool:
    return 1 <= len(line.strip()) <= MAX_LINE


# ═══════════════════════════════════════════════════════════════════════════
# E-3
# ═══════════════════════════════════════════════════════════════════════════

def _norm3(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).translate(_APOSTROPHES).split())


def _latin_hits(term: str, text: str) -> List[str]:
    pattern = re.compile(rf"(?<![{_ASCII_WORD}]){re.escape(term)}s?(?![{_ASCII_WORD}])",
                         re.IGNORECASE)
    return [m.group(0) for m in pattern.finditer(text)]


def e3_vocabulary_ok(line: str, exempting_corpus: str = "") -> bool:
    """No internal term and no rule id — unless the very token is the subject matter
    (it occurs in `exempting_corpus`: her text, the question, the solution, the quotes)."""
    text, corpus = _norm3(line), _norm3(exempting_corpus)
    for term in MACHINE_VOCABULARY:
        if _LATIN_TERM.match(term):
            corpus_words = {w.lower() for w in _latin_hits(term, corpus)}
            if any(h.lower() not in corpus_words for h in _latin_hits(term, text)):
                return False
        else:
            needle = _norm3(term)
            if needle in text and needle not in corpus:
                return False
    corpus_ids = set(RULE_ID.findall(corpus))
    return all(hit in corpus_ids for hit in RULE_ID.findall(text))


def _exempting_corpus(inp: ScopeExplainerInput, t: TerminalExplainerInput) -> str:
    """Teacher- and student-written text only (see the module docstring)."""
    parts = [t.teacher_text, inp.question_text, inp.example_solution]
    parts += [c.evidence_quote for c in t.credit_checks]
    parts += [f.charged_elsewhere_he or "" for f in t.fault_checks]
    parts += [f.pinned_criterion_he or "" for f in t.fault_checks]
    return "\n".join(p for p in parts if p)


# ═══════════════════════════════════════════════════════════════════════════
# E-4
# ═══════════════════════════════════════════════════════════════════════════

def numbers_in(text: str) -> List[Decimal]:
    """Every number written in `text`, as an absolute Decimal («2,5» is 2.5)."""
    out: List[Decimal] = []
    for tok in _NUMBER.findall(text or ""):
        if tok in _FRACTION:
            out.append(_FRACTION[tok])
            continue
        try:
            out.append(abs(Decimal(tok.replace(",", "."))))
        except InvalidOperation:                     # pragma: no cover — the regex admits none
            continue
    return out


def allowed_numbers(inp: ScopeExplainerInput, t: TerminalExplainerInput) -> FrozenSet[Decimal]:
    values: List[Decimal] = [t.awarded, t.points_possible]
    values += [c.selected_value for c in t.credit_checks]
    for f in t.fault_checks:
        values += [f.amount, f.charged]
    texts: List[str] = [t.teacher_text, inp.question_text, inp.example_solution,
                        *t.interpretation_notes_he]
    for c in t.credit_checks:
        texts += [c.description_he, c.selected_label_he, c.evidence_quote]
    for f in t.fault_checks:
        texts += [f.description_he, f.selected_label_he,
                  f.charged_elsewhere_he or "", f.pinned_criterion_he or ""]
    found = [abs(v) for v in values]
    for text in texts:
        found += numbers_in(text)
    return frozenset(found)


def e4_numbers_ok(line: str, allowed: Iterable[Decimal]) -> bool:
    allowed_set = set(allowed)
    return all(n in allowed_set for n in numbers_in(line))


# ═══════════════════════════════════════════════════════════════════════════
# E-5
# ═══════════════════════════════════════════════════════════════════════════

def _strip_niqqud(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", text)
                   if not ("֑" <= ch <= "ׇ" and unicodedata.category(ch) == "Mn"))


def _is_proclitics(prefix: str) -> bool:
    return len(prefix) <= 3 and all(ch in _PROCLITICS for ch in prefix)


def _token_is_marker(token: str, marker: str) -> bool:
    if token.endswith(marker) and _is_proclitics(token[: len(token) - len(marker)]):
        return True
    if marker.startswith("ה") and len(marker) > 1:       # the article, absorbed: ל+ה → ל
        stem = marker[1:]
        if token.endswith(stem):
            prefix = token[: len(token) - len(stem)]
            return (len(prefix) >= 1 and prefix[-1] in _ARTICLE_ABSORBERS
                    and _is_proclitics(prefix))
    return False


def e5_voice_ok(line: str) -> bool:
    tokens = _HEBREW_WORD.findall(_strip_niqqud(line))
    return not any(_token_is_marker(tok, m) for tok in tokens for m in VOICE_MARKERS)
