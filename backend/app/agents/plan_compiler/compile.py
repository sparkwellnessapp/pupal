"""
PLAN COMPILER v2 — Stage 1, the pure compiler (PR_plan_compiler_v2.md §3, C1–C7).

Input: a frozen `GradingRubricContract`. Output: a `PlanSkeleton` — every
terminal's slots with kind, points, tariff amounts, unit counts, charge groups
and the verbatim clause each slot was read from. Zero I/O, zero spend, and
byte-identical across runs: the algebra of a plan is a function of the text.

Rule by rule (each is a section below, in the order they run per terminal):

  C3  counted      «17 תאים 0.7 כל תא» → ONE counted slot, unit_count=N,
                   points=P. The teacher's per-unit figure is her rounding.
  C1  deductions   the calibrated v2 patterns (`plan_gen.prompt`), re-scanned
                   POSITIONALLY so the clause boundary is «אם … להוריד N», not a
                   sentence. Amount copied verbatim. Case 4 «N (או M?)» → the
                   lenient end, flagged. «פעם אחת» → charge-once group.
                   Parent-level phrase over sub-criteria → first child + sibling
                   group (OD-10). Amountless «לקנוס»/«להוריד רק פעם אחת» → the
                   value of the component the phrase modifies (OD-15), flagged.
                   Two dispositions the hand plan taught and the PR did not name
                   (both surfaced as OD-20/OD-21):
                     · a «- N נק'» that closes a component clause with no
                       deduction verb is that component's VALUE, not a tariff;
                     · a deduction whose amount equals the value of the very
                       component it follows, on a negated «אם לא …» condition,
                       is that component's own failure — no tariff slot, or the
                       pricer would charge the same miss twice.
  C2  notes        «לא להוריד …» → note_only slot, the clause as source_span.
  C4  components   explicit values «(1)», «(2 נקודות)», «2 נק'», «נק' 1» →
                   valued components; bare numbers ONLY when ≥2 of them sum
                   exactly to P; else explicit separators (« + », «וגם», numbered
                   items, bullets, a «(a, b, c)» identifier list); else monolith.
                   C# tails after the prose are never split and never yield a
                   number (F-6).
  C5  points       Case 2 Σ<P → unvalued components take the remainder, else a
                   remainder slot; Case 3 Σ>P → strict whole-point absorption +
                   minimal residual break (verified against both references);
                   no values → even split with the OD-9 residual rule.
  C6  groups       «פעם אחת» / «רק פעם 1» spanning siblings → charge_group.
  C7  routing      one component ∧ P ≥ 4 ∧ scope example_solution → routed.

V1 (Σ earn-side points == points_possible) holds by construction and is
ASSERTED; a failure raises `CompilerBug`.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Dict, List, Optional, Sequence, Tuple

from .stage0 import contract_scopes, terminals_of
from app.agents.plan_gen.prompt import (_DEDUCT_AMOUNTLESS_PATTERNS, _DEDUCT_PATTERNS,
                                        _NO_DEDUCT_PATTERNS)

from .skeleton import CompilerBug, Flag, PlanSkeleton, Slot, TerminalSkeleton

COMPILER_VERSION = "plan-compiler/v2.0"
ROUTE_MIN_POINTS = Decimal("4")        # OD-11, ratified: monoliths at P ≥ 4 with a solution route

FLAG_CODES = (
    "routed",                          # C7
    "counted_per_unit_rounding",       # C3: N × stated per-unit ≠ P
    "counted_terminal_extra_slots",    # C3: deductions/notes on a counted terminal dropped (V12)
    "case2_remainder_slot",            # C5: all components valued, Σ < P
    "case2_unvalued_fill",             # C5: unvalued components took the remainder
    "case3_over_allocation",           # C5: Σ > P reconciled
    "case4_lenient",                   # C1: «N (או M?)»
    "even_split_residual",             # C5/OD-9
    "bare_values",                     # C4: values read from bare numbers (Σ == P)
    "tariff_folded_into_component",    # C1/OD-21
    "tariff_amount_inferred",          # C1/OD-15
    "tariff_reclassified_as_value",    # C1/OD-20
    "parent_tariff_first_child_group", # C1/OD-10
    "scope_tariff_first_terminal_group",
    "charge_once_group",               # C6
    "text_total_disagrees",            # «סה"כ N» ≠ P
    "unvalued_component_dropped",      # C5: Σ valued == P and a valueless segment remained
    "code_tail_ignored",               # C4/F-6
    "identifier_list_split",           # C4
    "deduction_verb_only",             # C1: a deduction phrase with no number and no component
    "split_below_partial_grid",        # C5/OD-22: P over N cannot keep every 50% on the grid → not split
    "partial_off_grid",                # C5: a value whose 50% is off the grid (V4 will refuse — loudly)
    "band_ladder_kept_whole",          # C8-lite: alternative bands are not components (multisubject 4b)
)

_NUM = r"\d+(?:[.,]\d+)?"
_UNIT = r"(?:נק['׳]?|נקודות|נקודה|כ[\"״]א)"
_HEB = r"[֐-׿]"


def _dec(raw: str) -> Decimal:
    return _canon(Decimal(raw.replace(",", ".")))


def _canon(d) -> Decimal:
    """`4.00` → `4`, `0.50` → `0.5`, `10.0` → `10` — the plan's numbers print the
    way the hand plan writes them, and two equal values are one string."""
    d = Decimal(str(d))
    if d == d.to_integral_value():
        return Decimal(int(d))
    return d.normalize()


def _snap(x: Decimal, grid: Decimal) -> Decimal:
    return (x / grid).to_integral_value(rounding=ROUND_HALF_UP) * grid


def _floor_grid(x: Decimal, grid: Decimal) -> Decimal:
    return (x / grid).to_integral_value(rounding=ROUND_DOWN) * grid


# ═══════════════════════════════════════════════════════════════════════════
# Text partition: prose | code tail (F-6)
# ═══════════════════════════════════════════════════════════════════════════

_CODE_SIGNAL = re.compile(r"[;{]")
_HEB_LETTER = re.compile(_HEB)


def _split_code_tail(text: str) -> Tuple[str, int]:
    """(prose, code_start). The tail begins at the first C#-ish statement:
    the earliest `;`/`{`, walked back to just after the last Hebrew letter
    (skipping the digits / brackets of a value marker that may sit between).
    A text with no `;`/`{` has no tail."""
    m = _CODE_SIGNAL.search(text)
    if not m:
        return text, len(text)
    last_heb = None
    for hm in _HEB_LETTER.finditer(text, 0, m.start()):
        last_heb = hm.end()
    if last_heb is None:
        return "", 0
    i = last_heb
    # skip over a value marker's tail: digits, spaces, closing parens, quotes
    while i < m.start() and text[i] in " \t\r\n0123456789.,)'\"״׳":
        i += 1
    return text[:i], i


# ═══════════════════════════════════════════════════════════════════════════
# C1/C2 — deductions and notes, positional
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Deduction:
    start: int                 # clause span in the terminal text
    end: int
    phrase_start: int          # the matched verb phrase
    phrase_end: int
    polarity: str              # "deduct" | "no_deduct"
    amount: Optional[Decimal]  # verbatim; None when amountless
    alt_amount: Optional[Decimal]   # Case 4 «(או M?)»
    once: bool                 # «פעם אחת» / «רק פעם 1»
    clause: str

    @property
    def condition(self) -> str:
        """The clause minus the verb phrase — what the deduction is FOR."""
        return (self.clause[: self.phrase_start - self.start]
                + " " + self.clause[self.phrase_end - self.start:]).strip(" ,;:-–()")


_ONCE = re.compile(r"\s*\(?\s*(?:רק\s+)?פעם\s+(?:אחת|1)\s*\)?")
_CASE4 = re.compile(rf"\s*\(\s*או\s+({_NUM})\s*\?\s*\)")
_DEDUCT_VERB = re.compile(r"להוריד|מורידים|הורדה|מינוס|לקנוס|קנס|deduct|minus", re.I)
# clause-start candidates, scanned backwards from the phrase
# «אם» opens a clause when it follows a space, a paren, a LATIN token or two
# Hebrew letters — the DOCX flattening glues words («תשובהאם», «nullאם») and
# «האם» (whether) must not qualify: its «אם» follows a lone «ה» after a space.
_START_WORDS = re.compile(
    r"(?:(?<=\s)|(?<=\()|(?<=[A-Za-z0-9\])])|(?<=[֐-׿]{2})|(?<=\s[וש])|^)(?:אם|כל\s+טעות)\s")
_BOUNDARY = re.compile(r"[.\n;()]|(?<=\s)[-–]\s|,\s")


def _clause_start(text: str, phrase_start: int, floor: int) -> int:
    """Nearest of: an «אם»/«כל טעות» opener, or a hard boundary — whichever
    sits closest before the phrase, never before `floor` (the previous
    clause's end)."""
    best = floor
    for m in _BOUNDARY.finditer(text, floor, phrase_start):
        best = max(best, m.end())
    for m in _START_WORDS.finditer(text, floor, phrase_start):
        best = max(best, m.start())
    return best


def _clause_end(text: str, phrase_end: int, polarity: str, opened: bool = False
                ) -> Tuple[int, bool, Optional[Decimal]]:
    """(end, once, alt_amount). A deduct clause ends at its number, extended over
    a «(רק פעם אחת)» / «(או M?)» tail; a clause that OPENED with a paren runs to
    its closing paren («(לקנוס פעם אחת אם לא בדקו …, הערה למטה)» — the
    condition follows the verb there); a no_deduct clause runs to the next
    hard boundary."""
    i = phrase_end
    once = False
    alt = None
    if polarity == "no_deduct":
        m = re.compile(r"[.\n;]|(?<=\s)[-–]\s").search(text, i)
        end = m.start() if m else len(text)
        tail = text[i:end]
        return i + len(tail.rstrip()), False, None
    while True:
        m1 = _ONCE.match(text, i)
        if m1 and m1.end() > i:
            i, once = m1.end(), True
            continue
        m2 = _CASE4.match(text, i)
        if m2:
            i, alt = m2.end(), _dec(m2.group(1))
            continue
        break
    if opened:
        close = text.find(")", i)
        nxt = re.compile(r"[.\n;]").search(text, i)
        if close != -1 and (nxt is None or close < nxt.start()):
            return close + 1, once, alt
    # a closing paren that closes the clause's own opener is taken too
    m3 = re.compile(r"\s*\)").match(text, i)
    if m3 and text.count("(", 0, i) > text.count(")", 0, i):
        i = m3.end()
    return i, once, alt


def scan_deductions(text: str) -> List[Deduction]:
    """Every deduction / no-deduction phrase in `text`, as positioned CLAUSES.

    Reuses the calibrated v2 pattern tuples; unlike `prompt._scan` it keeps
    positions (so a clause can be masked out of the component text), never
    dedups two identical phrases in one terminal, and reads a «- N נק'» with no
    deduction verb in its clause as a VALUE marker (OD-20)."""
    hits: List[Tuple[int, int, str, Optional[Decimal]]] = []
    claimed: List[Tuple[int, int]] = []

    def free(a: int, b: int) -> bool:
        return not any(not (b <= s or a >= e) for s, e in claimed)

    for pat in _NO_DEDUCT_PATTERNS:
        for m in re.finditer(pat, text):
            if free(*m.span()):
                claimed.append(m.span())
                hits.append((m.start(), m.end(), "no_deduct", None))
    for pat in _DEDUCT_PATTERNS:
        for m in re.finditer(pat, text):
            if not free(*m.span()):
                continue
            claimed.append(m.span())
            hits.append((m.start(), m.end(), "deduct", _dec(m.group(1))))
    for pat in _DEDUCT_AMOUNTLESS_PATTERNS:
        for m in re.finditer(pat, text):
            if free(*m.span()):
                claimed.append(m.span())
                hits.append((m.start(), m.end(), "deduct", None))
    hits.sort()

    out: List[Deduction] = []
    floor = 0
    for ps, pe, polarity, amount in hits:
        start = _clause_start(text, ps, floor)
        clause_text = text[start:pe]
        # OD-20: the dash form «- N נק'» is a VALUE when no deduction verb is in
        # its clause. Kept in the list as polarity="value" so the compiler can
        # flag it; never masked, so C4 still reads the marker.
        if polarity == "deduct" and re.match(r"[-–]", text[ps:pe]) and not _DEDUCT_VERB.search(clause_text):
            out.append(Deduction(start=start, end=pe, phrase_start=ps, phrase_end=pe,
                                 polarity="value", amount=amount, alt_amount=None,
                                 once=False, clause=text[start:pe].strip()))
            continue
        opened = start > 0 and text[start - 1] == "("
        end, once, alt = _clause_end(text, pe, polarity, opened)
        out.append(Deduction(start=start, end=end, phrase_start=ps, phrase_end=pe,
                             polarity=polarity, amount=amount, alt_amount=alt,
                             once=once, clause=text[start:end].strip()))
        floor = end
    return out


# ═══════════════════════════════════════════════════════════════════════════
# C3 — counted
# ═══════════════════════════════════════════════════════════════════════════

_COUNT_UNITS = re.compile(rf"(\d+)\s*(?:תאים|תא|יחידות|שורות|רכיבים)")
_PER_UNIT = re.compile(rf"({_NUM})\s*(?:נק['׳]?|נקודות|נקודה)?\s*(?:כל|לכל)\s*(?:תא|יחידה|שורה|אחד|רכיב)")
_TIMES = re.compile(rf"(\d+)\s*[×x*]\s*({_NUM})")


def _counted(prose: str) -> Optional[Tuple[int, Optional[Decimal], str]]:
    """(N, stated per-unit, span) when the criterion prices N uniform units."""
    cu, pu = _COUNT_UNITS.search(prose), _PER_UNIT.search(prose)
    if cu and pu:
        n = int(cu.group(1))
        if n >= 2:
            a, b = min(cu.start(), pu.start()), max(cu.end(), pu.end())
            return n, _dec(pu.group(1)), prose[a:b]
    t = _TIMES.search(prose)
    if t and int(t.group(1)) >= 2:
        return int(t.group(1)), _dec(t.group(2)), t.group(0)
    return None


# ═══════════════════════════════════════════════════════════════════════════
# C4 — components
# ═══════════════════════════════════════════════════════════════════════════

_TOTAL_CLAIM = re.compile(
    rf"\(?\s*סה[\"״']?כ\s+(?:[֐-׿\"״']+\s+){{0,3}}({_NUM})\s*(?:נקודות|נק['׳]?)?\s*\)?\s*:?")
_DETAIL_CLAIM = re.compile(rf"פירוט\s*ל-?\s*{_NUM}\s*:?")
_PAREN_BARE = re.compile(rf"\(\s*({_NUM})\s*({_UNIT})?\s*\)")
_PAREN_WORDED = re.compile(rf"\(\s*[^()\d]*?{_HEB}[^()\d]*?\s({_NUM})\s*({_UNIT})\s*\)")
_INLINE = re.compile(rf"(?<![\w.,/*%=<>!+\-–])[-–~]?\s*ב?\s?({_NUM})\s{{0,2}}({_UNIT})(?![\w])")
_INLINE_REV = re.compile(rf"({_UNIT})\s*({_NUM})(?![\w.])")
_BARE = re.compile(rf"(?<![\w.,\-–/*%=<>!+\[(])({_NUM})(?![\w.,\-–%*/=<>!+\])])")
_BARE_CONTEXT_WORDS = ("עד", "בגודל", "בין", "מאינדקס", "לפחות", "בעוד", "מ", "ל")
_SEPARATORS = re.compile(r"\s\+\s|\s\+(?=[֐-׿A-Za-z(])|\)\+\s?|\sוגם\s|[•·]|\n\s*[-–]\s")
_NUMBERED = re.compile(r"(?:(?<=\s)|^)(\d)[.)]\s")
_IDENT_LIST = re.compile(r"\(\s*([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)+)\s*\)")


@dataclass
class Component:
    start: int
    end: int
    text: str
    value: Optional[Decimal] = None
    each: bool = False          # the marker said כ"א
    stated: Optional[Decimal] = None   # the teacher's own figure, before any reconciliation

    def __post_init__(self) -> None:
        if self.value is not None and self.stated is None:
            self.stated = self.value

    @property
    def own_value(self) -> Optional[Decimal]:
        """What the teacher priced this component at: her stated figure, or the
        split she implied. The fold and OD-15 rules read THIS, never a Case-3
        reconciled number."""
        return self.stated if self.stated is not None else self.value


def _mask(text: str, spans: Sequence[Tuple[int, int]]) -> str:
    chars = list(text)
    for a, b in spans:
        for i in range(a, min(b, len(chars))):
            chars[i] = " "
    return "".join(chars)


def _clean(s: str) -> str:
    s = re.sub(r"\s+", " ", s)
    return s.strip(" \t\r\n,;:+-–")


def _markers(masked: str) -> List[Tuple[int, int, Decimal, bool]]:
    """(start, end, value, each) for every explicit value marker."""
    found: List[Tuple[int, int, Decimal, bool]] = []
    taken: List[Tuple[int, int]] = []
    work = masked

    def claim(m: re.Match, num: str, unit: Optional[str]) -> None:
        found.append((m.start(), m.end(), _dec(num), bool(unit and "א" in unit and "כ" in unit)))
        taken.append(m.span())

    for m in _PAREN_BARE.finditer(work):
        claim(m, m.group(1), m.group(2))
    work = _mask(work, taken)
    for m in _PAREN_WORDED.finditer(work):
        claim(m, m.group(1), m.group(2))
    work = _mask(work, taken)
    for m in _INLINE.finditer(work):
        claim(m, m.group(1), m.group(2))
    work = _mask(work, taken)
    for m in _INLINE_REV.finditer(work):
        claim(m, m.group(2), m.group(1))
    found.sort()
    return found


def _bare_values(masked: str, points: Decimal) -> List[Tuple[int, int, Decimal, bool]]:
    """Bare numbers, accepted ONLY when ≥ 2 of them sum exactly to P."""
    cands: List[Tuple[int, int, Decimal, bool]] = []
    for m in _BARE.finditer(masked):
        v = _dec(m.group(1))
        if v <= 0:
            continue
        before = masked[max(0, m.start() - 12): m.start()].rstrip()
        prev_word = before.split()[-1] if before.split() else ""
        if prev_word.rstrip("-–") in _BARE_CONTEXT_WORDS or prev_word.endswith(("-", "–")):
            continue
        after = masked[m.end(): m.end() + 3]
        if after.startswith(("-", "–")) and after[1:2].isdigit():
            continue
        cands.append((m.start(), m.end(), v, False))
    if len(cands) >= 2 and sum(c[2] for c in cands) == points:
        return cands
    return []


def _segments_by_markers(masked: str, marks: List[Tuple[int, int, Decimal, bool]]) -> List[Component]:
    """One component per value marker: the text since the previous marker
    carries the value. A segment that itself holds explicit separators
    («הגדרת משתנה + אתחול (1 נקודות)») is split — the LAST piece carries the
    marker's value, the earlier pieces are unvalued (Case 2 fills them)."""
    comps: List[Component] = []
    prev = 0
    for s, e, v, each in marks:
        pieces: List[Tuple[int, int]] = []
        cut = prev
        for sep in _SEPARATORS.finditer(masked, prev, s):
            pieces.append((cut, sep.start()))
            cut = sep.end()
        pieces.append((cut, s))
        pieces = [(a, b) for a, b in pieces if re.search(r"[֐-׿A-Za-z]", masked[a:b])]
        if not pieces:
            pieces = [(prev, s)]
        for a, b in pieces[:-1]:
            comps.append(Component(a, b, _clean(masked[a:b]), None, False))
        a, _b = pieces[-1]
        comps.append(Component(a, e, _clean(masked[a:s]), v, each))
        prev = e
    tail = masked[prev:]
    if len(_HEB_LETTER.findall(tail)) >= 3 and not tail.lstrip().startswith(")"):
        comps.append(Component(prev, len(masked), _clean(tail), None, False))
    return comps


def _split_separators(masked: str) -> List[Component]:
    nums = list(_NUMBERED.finditer(masked))
    if len(nums) >= 2 and [int(m.group(1)) for m in nums] == list(range(1, len(nums) + 1)):
        cuts = [m.start() for m in nums] + [len(masked)]
        return [Component(cuts[i], cuts[i + 1], _clean(masked[cuts[i]:cuts[i + 1]]))
                for i in range(len(nums)) if _clean(masked[cuts[i]:cuts[i + 1]])]
    parts: List[Component] = []
    prev = 0
    for m in _SEPARATORS.finditer(masked):
        parts.append(Component(prev, m.start(), _clean(masked[prev:m.start()])))
        prev = m.end()
    parts.append(Component(prev, len(masked), _clean(masked[prev:])))
    # a placeholder like «_» or an empty segment is not a component
    return [p for p in parts if re.search(r"[֐-׿A-Za-z]", p.text)]


# ═══════════════════════════════════════════════════════════════════════════
# C5 — points
# ═══════════════════════════════════════════════════════════════════════════

def even_split(points: Decimal, n: int, grid: Decimal
               ) -> Optional[Tuple[List[Decimal], bool]]:
    """P over n; the residual goes +1 unit to each of the first k components in
    textual order (OD-9 ratified (a)).

    [OD-22, surfaced] The UNIT is 2×grid, not the grid: validator V4 requires
    every `points × partial_fraction` (default ½) to sit on the grid, and a
    component of 1.75 on a 0.25 grid halves to 0.875. The PR's worked example
    (5 over 3 → 1.75/1.75/1.5) is exactly such a plan; on this lattice it is
    2/1.5/1.5. When even one unit per component is more than P allows
    (0.5 over 2), the split is refused — None — and the caller keeps ONE
    component, flagged. Returns (values, had_residual)."""
    unit = grid * 2
    base = _floor_grid(points / n, unit)
    if base <= 0:
        return None
    residual = points - base * n
    k = int((residual / unit).to_integral_value(rounding=ROUND_DOWN))
    leftover = residual - unit * k
    vals = [base + (unit if i < k else Decimal("0")) for i in range(n)]
    vals[0] += leftover                 # only when P itself is off the ½-lattice
    return vals, k > 0 or leftover > 0


def case3_reconcile(values: Sequence[Decimal], points: Decimal, grid: Decimal
                    ) -> Tuple[List[Decimal], bool]:
    """R-E Case 3, the STRICT reading (impl record §3.4, verified against both
    references: (1,3,1,1)→(1,2,1,1) and (1,1,3,1,1)→(0.5,0.5,2,1,1)).

    1. Whole-point absorption: classes descending, members in textual order; a
       member drops by 1 only while it stays STRICTLY above the next lower
       class; repeat while over ≥ 1.
    2. Residual (< 1): the largest class that can take it; within it the FEWEST
       members in textual order, evenly, each staying on-grid, > 0 and strictly
       above the next class. Flagged by the caller.
    Returns (values, residual_was_broken)."""
    vals = [Decimal(v) for v in values]
    over = sum(vals) - points
    if over <= 0:
        return vals, False
    while over >= 1:
        moved = False
        for cls in sorted(set(vals), reverse=True):
            lower = [v for v in set(vals) if v < cls]
            nxt = max(lower) if lower else Decimal("0")
            for i, v in enumerate(vals):
                if over >= 1 and vals[i] == cls and v - 1 > nxt:
                    vals[i] = v - 1
                    over -= 1
                    moved = True
        if not moved:
            break
    if over <= 0:
        return vals, False
    for cls in sorted(set(vals), reverse=True):
        members = [i for i, v in enumerate(vals) if v == cls]
        lower = [v for v in set(vals) if v < cls]
        nxt = max(lower) if lower else Decimal("0")
        for m in range(1, len(members) + 1):
            share = over / m
            if share != _snap(share, grid):
                continue
            new = cls - share
            if new > 0 and new > nxt:
                for i in members[:m]:
                    vals[i] = new
                return vals, True
    raise CompilerBug(f"Case 3 residual {over} on {values} cannot be placed on grid {grid}")


# ═══════════════════════════════════════════════════════════════════════════
# The per-terminal compiler
# ═══════════════════════════════════════════════════════════════════════════

_STOP = {"את", "של", "אם", "לא", "עם", "על", "או", "גם", "כל", "רק", "בין", "אחת", "פעם"}


def _tokens(s: str) -> set:
    out = set()
    for w in re.findall(r"[A-Za-z_][A-Za-z_0-9]{2,}|[֐-׿]{4,}", s):
        if w not in _STOP:
            out.add(w)
    return out


def _attach(ded: Deduction, comps: List[Component]) -> int:
    """Index of the component a deduction modifies: the one whose segment ended
    last before the clause; when amountless, a component that shares a
    distinctive token with the condition wins (OD-15)."""
    if not comps:
        return -1
    if ded.amount is None:
        cond = _tokens(ded.condition)
        if cond:
            scores = [len(cond & _tokens(c.text)) for c in comps]
            best = max(scores)
            if best > 0 and scores.count(best) == 1:
                return scores.index(best)
    prev = [i for i, c in enumerate(comps) if c.end <= ded.start]
    return prev[-1] if prev else 0


def _group_key(scope: str, comp_text: str, amount: Decimal) -> str:
    h = hashlib.sha1(f"{_clean(comp_text)}|{amount}".encode("utf-8")).hexdigest()[:8]
    return f"{scope}:once:{h}"


# C8-lite (multisubject 4b). A band ladder is a row of ALTERNATIVES with descending points,
# written by the extractor as one labelled line per band:
#     MECHANICS
#     CORRECT (6): …
#     PARTIALLY CORRECT (4): …
#     MINIMALLY CORRECT (2): …
#     INCORRECT (0): …
# The shape is deliberately narrow, because a false positive would silently collapse a real
# component list into one slot: at least three labelled bands, values STRICTLY DESCENDING, the
# top band equal to the terminal's own points, and the bottom band 0. No CS criterion in the
# corpus has that shape — the A0 guard is the standing check that it stays that way.
_BAND_LINE = re.compile(r"^[ \t]*(?P<label>[^\n()]{2,60}?)[ \t]*\((?P<pts>\d+(?:[.,]\d+)?)\)[ \t]*:",
                        re.MULTILINE)
_MIN_BANDS = 3


def _band_ladder(prose: str, points: Decimal) -> Optional[List[Tuple[str, Decimal]]]:
    """The ladder as (label, points), or None when the text is not one."""
    bands = [(m.group("label").strip(), _dec(m.group("pts")))
             for m in _BAND_LINE.finditer(prose or "")]
    if len(bands) < _MIN_BANDS:
        return None
    values = [v for _, v in bands]
    if values[0] != points or values[-1] != Decimal("0"):
        return None
    if any(a <= b for a, b in zip(values, values[1:])):
        return None
    return bands


def compile_terminal(*, terminal_id: str, scope: str, text: str, points: Decimal,
                     grid: Decimal, has_solution: bool,
                     inherited: Sequence[Slot] = (),
                     route_min_points: Decimal = ROUTE_MIN_POINTS) -> TerminalSkeleton:
    """Compile ONE terminal. `inherited` are tariff slots anchored here by a
    parent- or scope-level phrase (OD-10). `route_min_points` is OD-11's
    threshold; anything but the default is a COUNTERFACTUAL for a report,
    never a production setting."""
    flags: List[Flag] = []
    slots: List[Slot] = []
    text = text or ""
    points = _canon(points)
    grid = _canon(grid)

    def flag(code: str, detail: str = "") -> None:
        assert code in FLAG_CODES, code
        flags.append(Flag(code, terminal_id, detail))

    prose, code_start = _split_code_tail(text)
    if code_start < len(text):
        flag("code_tail_ignored", text[code_start:code_start + 40])

    deds = scan_deductions(text)
    claims = [m.span() for m in _TOTAL_CLAIM.finditer(prose)] + \
             [m.span() for m in _DETAIL_CLAIM.finditer(prose)]
    for m in _TOTAL_CLAIM.finditer(prose):
        if _dec(m.group(1)) != points:
            flag("text_total_disagrees", f"text says {m.group(1)}, points_possible {points}")

    # ── C8-lite: a BAND LADDER is one criterion, never a sum ─────────────────
    # ALPHA-GAP A-1 (D-3): beta keeps the ladder WHOLE at the top band. Alpha models discrete
    # levels — a `level_select` check whose bands are selectable, priced and overridable — and
    # this early return retires with it.
    #
    # Evidence that made this necessary (multisubject Phase 4b, the ruled 10-minute probe): the
    # Ministry F/G writing rubric compiled to THREE `required` slots per criterion, because C5
    # read the band values as components, saw 8+5+2+0 = 15 > 8, and reconciled them down to
    # 5/2/1. A student would then have had to satisfy CORRECT *and* PARTIALLY CORRECT *and*
    # MINIMALLY CORRECT to earn full marks on an essay — bands are ALTERNATIVES, not parts, and
    # the bottom band ("INCORRECT", 0) was being named as something to earn.
    ladder = _band_ladder(prose, points)
    if ladder:
        flag("band_ladder_kept_whole",
             " > ".join(f"{lab}={val}" for lab, val in ladder))
        slots.append(Slot(f"{terminal_id}.k1", "required", points=points,
                          source_span=prose.strip(), summary=_clean(prose)))
        if inherited:
            flag("counted_terminal_extra_slots", f"{len(inherited)} inherited dropped on a ladder")
        return TerminalSkeleton(terminal_id, scope, points, text, tuple(slots),
                                routed=False, case="band_ladder", flags=tuple(flags))

    # ── C3 ──────────────────────────────────────────────────────────────────
    counted = _counted(_mask(prose, claims))
    if counted:
        n, per, span = counted
        sflags = ()
        if per is not None and per * n != points:
            flag("counted_per_unit_rounding", f"{n} × {per} = {per * n} ≠ {points}")
            sflags = ("per_unit_is_rounding",)
        slots.append(Slot(f"{terminal_id}.k1", "counted", points=points, unit_count=n,
                          source_span=span.strip(), summary=_clean(prose), flags=sflags))
        real = [d for d in deds if d.polarity != "value"]
        if real or inherited:
            flag("counted_terminal_extra_slots", f"{len(real) + len(inherited)} dropped (V12)")
        return TerminalSkeleton(terminal_id, scope, points, text, tuple(slots),
                                routed=False, case="counted", flags=tuple(flags))

    # ── C4: components on the masked prose ──────────────────────────────────
    masked = _mask(prose, [(d.start, min(d.end, len(prose))) for d in deds
                           if d.start < len(prose) and d.polarity != "value"]
                   + claims)
    for d in deds:
        if d.polarity == "value":
            flag("tariff_reclassified_as_value", f"«{d.clause[-40:]}» closes a component, no verb")
    marks = _markers(masked)
    case = "single"
    if marks:
        if len(marks) == 1 and marks[0][3]:
            comps = _split_separators(_mask(masked, [marks[0][:2]]))
            for c in comps:
                c.value, c.each = marks[0][2], True
            case = "each"
        else:
            comps = _segments_by_markers(masked, marks)
            case = "valued"
    else:
        bare = _bare_values(masked, points)
        if bare:
            comps = _segments_by_markers(masked, bare)
            case = "bare"
            flag("bare_values", ", ".join(str(b[2]) for b in bare))
        else:
            comps = _split_separators(masked)
            if len(comps) <= 1:
                il = _IDENT_LIST.search(masked)
                if il:
                    names = [n.strip() for n in il.group(1).split(",")]
                    comps = [Component(0, len(masked), f"{_clean(masked)} — {nm}") for nm in names]
                    case = "identifier_list"
                    flag("identifier_list_split", ", ".join(names))
                else:
                    comps = [Component(0, len(masked), _clean(masked))]
                    case = "single"
            else:
                case = "separators"
    if not comps:
        comps = [Component(0, len(masked), _clean(masked) or _clean(text))]
        case = "single"

    # ── C5: points ──────────────────────────────────────────────────────────
    valued = [c for c in comps if c.value is not None]
    unvalued = [c for c in comps if c.value is None]
    remainder_slot: Optional[Decimal] = None
    if not valued:
        split = even_split(points, len(comps), grid) if len(comps) > 1 else ([points], False)
        if split is None:
            flag("split_below_partial_grid",
                 f"{points} over {len(comps)} components cannot keep each 50% on the {grid} grid")
            comps = [Component(comps[0].start, comps[-1].end,
                               " + ".join(c.text for c in comps))]
            split = ([points], False)
        vals, resid = split
        for c, v in zip(comps, vals):
            c.value = v
        if resid:
            flag("even_split_residual", f"{points} over {len(comps)}: {[str(v) for v in vals]}")
        if len(comps) > 1:
            case = case if case != "single" else "even"
    else:
        total = sum(c.value for c in valued)
        if total < points:
            split = (even_split(points - total, len(unvalued), grid)
                     if len(unvalued) > 1 else ([points - total], False)) if unvalued else None
            if unvalued and split is None:
                # the remainder cannot be shared on the lattice: one merged component
                flag("split_below_partial_grid",
                     f"remainder {points - total} over {len(unvalued)} unvalued components")
                merged = Component(unvalued[0].start, unvalued[-1].end,
                                   " + ".join(c.text for c in unvalued))
                comps = [c for c in comps if c.value is not None] + [merged]
                unvalued = [merged]
                split = ([points - total], False)
            if unvalued:
                vals, resid = split
                for c, v in zip(unvalued, vals):
                    c.value = v
                flag("case2_unvalued_fill", f"{points - total} over {len(unvalued)} unvalued")
                if resid:
                    flag("even_split_residual", f"{points - total} over {len(unvalued)}")
            else:
                remainder_slot = points - total
                flag("case2_remainder_slot", f"stated {total} < {points}; remainder {remainder_slot}")
            case = "case2"
        elif total > points:
            if unvalued:
                flag("unvalued_component_dropped", f"{len(unvalued)} valueless segment(s)")
                comps = valued
            new, broke = case3_reconcile([c.value for c in comps], points, grid)
            flag("case3_over_allocation",
                 f"stated {[str(c.value) for c in comps]} = {total} > {points} → {[str(v) for v in new]}"
                 + (" (residual broken)" if broke else ""))
            for c, v in zip(comps, new):
                c.value = v
            case = "case3"
        else:
            if unvalued:
                flag("unvalued_component_dropped", f"{len(unvalued)} valueless segment(s)")
                comps = valued
    comps = [c for c in comps if c.value and c.value > 0]
    if not comps:
        comps = [Component(0, len(masked), _clean(masked) or _clean(text), points)]

    # ── C1 tariffs / C2 notes, attached to components ──────────────────────
    tariffs: List[Slot] = []
    notes: List[Slot] = []
    for d in deds:
        if d.polarity == "value":
            continue
        if d.polarity == "no_deduct":
            notes.append(Slot(f"{terminal_id}.n{len(notes) + 1}", "note_only",
                              source_span=d.clause, summary=_clean(d.clause)))
            continue
        idx = _attach(d, comps)
        host = comps[idx] if idx >= 0 else None
        amount = d.amount
        sflags: List[str] = []
        if d.alt_amount is not None and amount is not None:
            lenient = min(amount, d.alt_amount)
            flag("case4_lenient", f"«{amount} (או {d.alt_amount}?)» → {lenient}")
            amount = lenient
            sflags.append("case4_lenient")
        if amount is None:
            if host is None or host.own_value is None:
                flag("deduction_verb_only", d.clause)
                continue
            amount = host.own_value
            flag("tariff_amount_inferred", f"{d.clause!r} → {amount} from «{host.text[:40]}»")
            sflags.append("amount_inferred")
        # OD-21: a deduction worth exactly the component it modifies IS that
        # component's failure — a required check already loses its whole value
        # when not met; a tariff of the same size would charge the miss twice.
        # A charge-once deduction is never folded: its group is the point.
        if host is not None and not d.once and amount == host.own_value:
            flag("tariff_folded_into_component",
                 f"«{d.clause[:60]}» = the {amount}-point component's own failure")
            continue
        group = None
        if d.once and host is not None:
            group = _group_key(scope, host.text, amount)
            flag("charge_once_group", f"{group} ← «{d.clause[:50]}»")
        tariffs.append(Slot(f"{terminal_id}.t{len(tariffs) + 1}", "tariff",
                            tariff_amount=_canon(amount), charge_group=group,
                            source_span=d.clause, summary=_clean(d.condition),
                            anchor_span=host.text if host else "", flags=tuple(sflags)))
    for s in inherited:
        tariffs.append(Slot(f"{terminal_id}.t{len(tariffs) + 1}", "tariff",
                            tariff_amount=s.tariff_amount, charge_group=s.charge_group,
                            source_span=s.source_span, flags=s.flags))

    # ── assemble, C7 ────────────────────────────────────────────────────────
    for i, c in enumerate(comps):
        slots.append(Slot(f"{terminal_id}.k{i + 1}", "required", points=_canon(c.value),
                          source_span=prose[c.start:c.end].strip(), summary=c.text))
    if remainder_slot is not None:
        # no clause of its own: it is "the rest of" the whole criterion
        slots.append(Slot(f"{terminal_id}.k{len(comps) + 1}", "required",
                          points=_canon(remainder_slot), source_span=prose.strip(), summary="",
                          flags=("case2_remainder",)))
    slots.extend(tariffs)
    slots.extend(notes)
    routed = (len(comps) == 1 and remainder_slot is None
              and points >= route_min_points and has_solution)
    if routed:
        flag("routed", f"monolith, P={points}, solution present")

    earned = sum(s.points for s in slots if s.kind in ("required", "counted"))
    if earned != points:
        raise CompilerBug(f"{terminal_id}: Σ earn-side {earned} ≠ points_possible {points} "
                          f"(case {case}; {[str(s.points) for s in slots]})")
    for s in slots:
        if s.points != _snap(s.points, grid) or (s.tariff_amount is not None
                                                 and s.tariff_amount != _snap(s.tariff_amount, grid)):
            raise CompilerBug(f"{terminal_id}: {s.slot_id} off the {grid} grid")
    return TerminalSkeleton(terminal_id, scope, points, text, tuple(slots),
                            routed=routed, case=case, flags=tuple(flags))


# ═══════════════════════════════════════════════════════════════════════════
# C6 — charge-once groups across a scope
# ═══════════════════════════════════════════════════════════════════════════

def _merge_once_groups(terminals: List[TerminalSkeleton]) -> List[TerminalSkeleton]:
    """Two charge-once tariffs in one SCOPE, of one amount, anchored on the same
    requirement, are ONE group — «פעם אחת» is a promise across the scope.

    "The same requirement" is a token-Jaccard ≥ 0.5 between the anchoring
    component texts: bagrut q4.ב's null check reads «סעיף ב:בתוך הלולאה (A) :
    בדיקה אם המערך במקום ה- i שונה מ- null» on c4 and «בדיקה אם המערך במקום ה- i
    שונה מ- null» on c7 — a label prefix apart. The merged id is a function of
    the union of the members' tokens, so it is stable across runs."""
    from dataclasses import replace
    items: List[Tuple[int, int, str, Decimal, set]] = []
    for ti, t in enumerate(terminals):
        for si, s in enumerate(t.slots):
            if s.kind == "tariff" and s.charge_group and ":once:" in s.charge_group:
                items.append((ti, si, t.scope, s.tariff_amount, _tokens(s.anchor_span)))
    parent = list(range(len(items)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a in range(len(items)):
        for b in range(a + 1, len(items)):
            _, _, sa, aa, ta = items[a]
            _, _, sb, ab, tb = items[b]
            if sa != sb or aa != ab or not ta or not tb:
                continue
            if len(ta & tb) / len(ta | tb) >= 0.5:
                parent[find(a)] = find(b)
    groups: Dict[int, List[int]] = {}
    for i in range(len(items)):
        groups.setdefault(find(i), []).append(i)
    new_slots: Dict[Tuple[int, int], str] = {}
    for members in groups.values():
        if len(members) < 2:
            continue
        scope, amount = items[members[0]][2], items[members[0]][3]
        union: set = set()
        for m in members:
            union |= items[m][4]
        gid = f"{scope}:once:" + hashlib.sha1(
            ("|".join(sorted(union)) + f"|{amount}").encode("utf-8")).hexdigest()[:8]
        for m in members:
            new_slots[(items[m][0], items[m][1])] = gid
    if not new_slots:
        return terminals
    out = list(terminals)
    for (ti, si), gid in new_slots.items():
        t = out[ti]
        slots = list(t.slots)
        slots[si] = replace(slots[si], charge_group=gid)
        out[ti] = replace(t, slots=tuple(slots))
    return out


# ═══════════════════════════════════════════════════════════════════════════
# Stage 0 + the whole contract
# ═══════════════════════════════════════════════════════════════════════════

_TEXT_ATTRS = ("description", "evaluation_guidance", "notes")


def _node_text(node) -> str:
    parts = []
    for a in _TEXT_ATTRS:
        v = getattr(node, a, None)
        if isinstance(v, str) and v.strip():
            parts.append(v.strip())
    return "\n".join(parts)


def _scope_label(key) -> str:
    q, sub = key
    return q if sub is None else f"{q}.{sub}"


def compile_contract(contract, *, exam_id: str, rubric_contract_sha256: str,
                     route_min_points: Decimal = ROUTE_MIN_POINTS) -> PlanSkeleton:
    grid = Decimal(str(contract.numeric_policy.precision))
    terminals: List[TerminalSkeleton] = []
    scope_flags: List[Flag] = []
    for key, question, sub in contract_scopes(contract):
        scope = _scope_label(key)
        node = sub or question
        has_solution = any((getattr(n, "example_solution", None) or "").strip()
                           for n in (node, question))
        scope_terms = [t for t, _ in terminals_of(node)]

        # scope-level numbered deductions → first terminal that can carry it + group
        inherited: Dict[str, List[Slot]] = {}
        scope_points = {t: Decimal(str(p)) for t, p in terminals_of(node)}

        def carrier(candidates: List[str], amount: Decimal) -> str:
            """[OD-23, surfaced] «first child» as ratified in OD-10 collides with
            validator V3 (a tariff never exceeds its terminal's points): hobby
            q2.ב.c4's 3-point tariff cannot sit on s0 (1 point). The first
            candidate that can CARRY the amount wins — s3, which is where the
            ratified hand plan put it; failing that, the largest."""
            for c in candidates:
                if scope_points.get(c, Decimal("0")) >= amount:
                    return c
            return max(candidates, key=lambda c: scope_points.get(c, Decimal("0")))
        scope_text = "\n".join(s for s in (getattr(node, "text", None), getattr(node, "notes", None),
                                           getattr(node, "evaluation_guidance", None))
                               if isinstance(s, str) and s.strip())
        for i, d in enumerate(scan_deductions(scope_text)):
            if d.polarity != "deduct" or d.amount is None or not scope_terms:
                continue
            amount = min(d.amount, d.alt_amount) if d.alt_amount is not None else d.amount
            group = f"{scope}:scope:d{i + 1}"
            host = carrier(scope_terms, amount)
            inherited.setdefault(host, []).append(
                Slot("", "tariff", tariff_amount=_canon(amount), charge_group=group,
                     source_span=d.clause, summary=_clean(d.condition), flags=("scope_level",)))
            scope_flags.append(Flag("scope_tariff_first_terminal_group", host,
                                    f"{group} over {scope_terms} ← «{d.clause[:50]}»"))

        for criterion in getattr(node, "criteria", []) or []:
            subs = getattr(criterion, "sub_criteria", None) or []
            if subs:
                # OD-10: parent-level phrase → first child + sibling charge_group
                kids = [s.sub_criterion_id for s in subs]
                for i, d in enumerate(scan_deductions(_node_text(criterion))):
                    if d.polarity != "deduct" or d.amount is None:
                        continue
                    amount = d.amount
                    if d.alt_amount is not None:
                        amount = min(amount, d.alt_amount)
                    group = f"{scope}:{criterion.criterion_id}:d{i + 1}"
                    host = carrier(kids, amount)
                    inherited.setdefault(host, []).append(
                        Slot("", "tariff", tariff_amount=_canon(amount), charge_group=group,
                             source_span=d.clause, summary=_clean(d.condition),
                             flags=("parent_level",)))
                    scope_flags.append(Flag("parent_tariff_first_child_group", host,
                                            f"{group} over {kids} ← «{d.clause[:50]}» "
                                            f"(anchored on the first child that can carry {amount})"))
                for s in subs:
                    terminals.append(compile_terminal(
                        terminal_id=s.sub_criterion_id, scope=scope, text=_node_text(s),
                        points=Decimal(str(s.points)), grid=grid, has_solution=has_solution,
                        inherited=tuple(inherited.get(s.sub_criterion_id, ())),
                        route_min_points=route_min_points))
            else:
                terminals.append(compile_terminal(
                    terminal_id=criterion.criterion_id, scope=scope, text=_node_text(criterion),
                    points=Decimal(str(criterion.points)), grid=grid, has_solution=has_solution,
                    inherited=tuple(inherited.get(criterion.criterion_id, ())),
                    route_min_points=route_min_points))
    terminals = _merge_once_groups(terminals)
    return PlanSkeleton(exam_id=exam_id, rubric_contract_sha256=rubric_contract_sha256,
                        precision=grid, compiler_version=COMPILER_VERSION,
                        terminals=tuple(terminals), flags=tuple(scope_flags))
