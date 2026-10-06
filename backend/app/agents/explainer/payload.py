"""
The explainer's input, built from a PRICED test (PR_grader_v6_options.md §7.3). Pure.

    build_scope_inputs(content, priced, materials) -> [ScopeExplainerInput]

One input per scope the explainer is CALLED for: a scope the verifier actually graded
(`ScopeRecordV6.graded_by == "llm"`) that counts toward the grade (`PricedScope.counted`;
D-6 — skipped, failed and excluded-by-selection scopes get no call), holding every CREDIT
terminal of that scope (≥ 1 credit check priced on it) that SHE did not decide. A terminal
she decided — a terminal override, or a typed amount on any of its checks (AM-G3) — is
explained by nobody: it is not in the input, and its line is «הציון נקבע ידנית».

What the input carries (§7.3), per scope: the question, the example solution, the
observed notes (Q-10); per credit terminal: its alias, her criterion text verbatim, the
interpretation notes, `awarded` / `points_possible`, every credit check (description, the
RESOLVED option's label and value, and the evidence for that option — a verified quote,
or the verifier's absence pointer at the zero option), and every fault check priced on it
(description, the resolved label, the amount, what was charged, the status; for
`superseded`, her text of the criterion where the group WAS charged; for `moved_by_pin`,
her text of the criterion whose grade she set by hand).

Never input: the full transcription, ground truth, other students, other scopes' terminals,
any check id or option id. Evidence is shown only for the option it was produced for: a
quote the validator could not verify (or one written for an option she replaced) is never
passed, so the explainer cannot describe something the grade does not stand on.

The input also records, never rendered: the real ids (to map the model's aliases back),
and `fallback_he` — the deterministic line `compose_reasoning_he` gives this terminal — so
a recorded payload (`payload_to_dict`) replays on another model (§13.4 arm B) with no
pricer and still knows its fallback. E-4's allowed numbers are a pure function of the
input (`validators.allowed_numbers`), so they travel with the payload by construction.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Literal, Mapping, Optional, Tuple

from pydantic import BaseModel, Field, field_serializer, model_validator

from app.agents.explainer.fallback import compose_reasoning_he
from app.agents.grader.payload_aliases import AliasTable
from app.schemas.graded_test_draft_v6 import CheckRecordV6, DraftV6Content
from app.services.pricing_v6 import FaultStatus, PricedCharge, PricedTerminal, PricedTest

__all__ = ["PAYLOAD_SCHEMA", "ScopeKey", "ScopeMaterials", "CreditCheckInput",
           "FaultCheckInput", "TerminalExplainerInput", "ScopeExplainerInput",
           "ExplainerInputError", "build_scope_inputs", "build_scope_input", "called_scopes",
           "credit_terminal_ids", "teacher_decided", "alias_table",
           "payload_to_dict", "payload_from_dict"]

PAYLOAD_SCHEMA = "explainer-payload/v1"
ScopeKey = Tuple[str, Optional[str]]                 # (question_id, sub_question_id)

_VERIFIED = ("exact", "fuzzy")
# a fault the pricer charged — wholly or in part — for its charge group
_CHARGED = ("applied", "capped", "floored")


class ExplainerInputError(ValueError):
    """The materials do not cover what the priced test needs (a missing scope or
    teacher text). A wrong INPUT, never a model failure: the caller degrades the
    scope to its fallback lines and logs it (§3.5a — a display path)."""


class ScopeMaterials(BaseModel):
    """The scope's rubric text, from the contract: the per-batch-identical part."""
    model_config = {"frozen": True}
    question_text: str
    example_solution: str = ""
    teacher_texts: Dict[str, str]                    # terminal_id → her criterion text, verbatim


def _sd(v: Optional[Decimal]) -> Optional[str]:
    return None if v is None else str(v)


class CreditCheckInput(BaseModel):
    model_config = {"frozen": True}
    description_he: str
    selected_label_he: str
    selected_value: Decimal
    evidence_quote: str = ""                         # verified span for the selected option
    absence_pointer_he: str = ""                     # at the zero option: what is there instead

    @field_serializer("selected_value")
    def _s(self, v: Decimal) -> str:
        return str(v)


class FaultCheckInput(BaseModel):
    model_config = {"frozen": True}
    description_he: str
    selected_label_he: str
    amount: Decimal                                  # the resolved option's value (≤ 0)
    charged: Decimal                                 # what was actually deducted (≤ 0)
    status: FaultStatus
    moved_by_pin: bool = False
    charged_elsewhere_he: Optional[str] = None       # superseded: where the group was charged
    pinned_criterion_he: Optional[str] = None        # moved_by_pin: the criterion she pinned

    @field_serializer("amount", "charged")
    def _s(self, v: Decimal) -> str:
        return str(v)


class TerminalExplainerInput(BaseModel):
    model_config = {"frozen": True}
    alias: str                                       # AM-G17: t1, t2 … in plan order
    terminal_id: str                                 # the real id — NEVER rendered
    teacher_text: str
    points_possible: Decimal
    interpretation_notes_he: Tuple[str, ...] = ()
    awarded: Decimal
    credit_checks: Tuple[CreditCheckInput, ...]
    fault_checks: Tuple[FaultCheckInput, ...] = ()
    fallback_he: str                                 # compose_reasoning_he — NEVER rendered

    @field_serializer("points_possible", "awarded")
    def _s(self, v: Decimal) -> str:
        return str(v)


class ScopeExplainerInput(BaseModel):
    model_config = {"frozen": True}
    payload_schema: Literal["explainer-payload/v1"] = PAYLOAD_SCHEMA
    question_id: str                                 # real ids — logs and mapping only
    sub_question_id: Optional[str] = None
    question_text: str
    example_solution: str = ""
    observed_notes_he: Tuple[str, ...] = ()
    terminals: Tuple[TerminalExplainerInput, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _aliases_are_the_table(self) -> "ScopeExplainerInput":
        """[AM-G17] the aliases ARE `alias_table(self)`: t1…tn in order, so the renderer
        and the mapper build the same table from the same input."""
        expected = [f"t{i}" for i in range(1, len(self.terminals) + 1)]
        if [t.alias for t in self.terminals] != expected:
            raise ValueError(f"terminal aliases must be {expected} in order (AM-G17)")
        ids = [t.terminal_id for t in self.terminals]
        if len(set(ids)) != len(ids):
            raise ValueError("a terminal appears twice in one scope input")
        return self

    @property
    def scope_id(self) -> str:
        return self.question_id if self.sub_question_id is None \
            else f"{self.question_id}.{self.sub_question_id}"


def alias_table(inp: ScopeExplainerInput) -> AliasTable:
    """[AM-G17] the call's table: a pure function of what the call shows, in order."""
    return AliasTable((("t", [t.terminal_id for t in inp.terminals]),))


# ═══════════════════════════════════════════════════════════════════════════
# who gets a line, and who decides it
# ═══════════════════════════════════════════════════════════════════════════

def credit_terminal_ids(content: DraftV6Content) -> List[str]:
    """Every CREDIT terminal of the test (≥ 1 credit check priced on it), in plan order."""
    with_credit = {c.plan.priced_terminal_id for c in content.checks if c.plan.role == "credit"}
    return [t.terminal_id for t in content.terminals if t.terminal_id in with_credit]


def teacher_decided(terminal: PricedTerminal) -> bool:
    """She set the number herself: a terminal override, or a typed amount on any of
    its checks (AM-G3, §7.6). Nobody explains a number she chose."""
    return bool(terminal.overridden or terminal.typed)


# ═══════════════════════════════════════════════════════════════════════════
# the builder
# ═══════════════════════════════════════════════════════════════════════════

def build_scope_inputs(content: DraftV6Content, priced: PricedTest,
                       materials: Mapping[ScopeKey, ScopeMaterials]) -> List[ScopeExplainerInput]:
    """One input per scope the explainer is called for, in plan order (see the module
    docstring for which scopes and terminals). Raises ExplainerInputError when the
    materials do not cover a scope that needs a call."""
    out: List[ScopeExplainerInput] = []
    for key in called_scopes(content, priced):
        inp = build_scope_input(content, priced, materials, key)
        if inp is not None:
            out.append(inp)
    return out


def called_scopes(content: DraftV6Content, priced: PricedTest) -> List[ScopeKey]:
    """The scopes that may get a call (D-6), in plan order: graded by the verifier and
    counted toward the grade."""
    graded = {(s.question_id, s.sub_question_id) for s in content.scopes if s.graded_by == "llm"}
    counted = {(s.question_id, s.sub_question_id) for s in priced.scopes if s.counted}
    seen: List[ScopeKey] = []
    for vt in content.view_terminals:
        key = (vt.question_id, vt.sub_question_id)
        if key not in seen and key in graded and key in counted:
            seen.append(key)
    return seen


def build_scope_input(content: DraftV6Content, priced: PricedTest,
                      materials: Mapping[ScopeKey, ScopeMaterials],
                      key: ScopeKey) -> Optional[ScopeExplainerInput]:
    """The input for ONE scope, or None when every credit terminal in it is hers."""
    view = content.to_view()
    priced_terminals = {t.terminal_id: t for t in priced.terminals}
    resolved = {r.check_id: r for r in priced.checks}
    records: Dict[str, CheckRecordV6] = {c.plan.check_id: c for c in content.checks}
    plans = {t.terminal_id: t for t in content.terminals}
    scope_tids = [vt.terminal_id for vt in content.view_terminals
                  if (vt.question_id, vt.sub_question_id) == key]
    in_scope = set(scope_tids)
    credit_tids = [tid for tid in credit_terminal_ids(content) if tid in in_scope]
    explained = [tid for tid in credit_tids if not teacher_decided(priced_terminals[tid])]
    if not explained:
        return None

    mat = materials.get(key)
    if mat is None:
        raise ExplainerInputError(f"no materials for scope {_scope_name(key)}")

    def teacher_text(tid: str) -> str:
        text = mat.teacher_texts.get(tid)
        if text is None or not text.strip():
            raise ExplainerInputError(
                f"no teacher text for terminal {tid} in scope {_scope_name(key)}")
        return text

    by_terminal: Dict[str, List[CheckRecordV6]] = {}
    for rec in sorted(content.checks, key=lambda c: c.plan_index):
        by_terminal.setdefault(rec.plan.priced_terminal_id, []).append(rec)

    # where each charge group was charged (V7: a group lies inside one scope)
    charged_at: Dict[str, str] = {}
    for tid in scope_tids:
        for ch in priced_terminals[tid].charges:
            group = records[ch.check_id].plan.charge_group
            if group is not None and ch.status in _CHARGED:
                charged_at.setdefault(group, tid)

    terminals: List[TerminalExplainerInput] = []
    for n, tid in enumerate(explained, start=1):
        pt = priced_terminals[tid]
        charges: Dict[str, PricedCharge] = {c.check_id: c for c in pt.charges}
        credits: List[CreditCheckInput] = []
        faults: List[FaultCheckInput] = []
        for rec in by_terminal.get(tid, []):
            plan = rec.plan
            r = resolved[plan.check_id]
            if plan.role == "credit":
                option = plan.option(r.option_id)
                if option is None:              # a typed amount: the terminal would be hers
                    raise ExplainerInputError(f"check on {tid} resolved to no option")
                credits.append(CreditCheckInput(
                    description_he=plan.description_he, selected_label_he=option.label_he,
                    selected_value=r.value, **_evidence(rec, r.option_id)))
            elif plan.role == "fault":
                ch = charges[plan.check_id]
                pointer = pinned = None
                if ch.status == "superseded" and plan.charge_group in charged_at:
                    pointer = teacher_text(charged_at[plan.charge_group])
                if ch.moved_by_pin and ch.moved_from_terminal_id is not None:
                    pinned = teacher_text(ch.moved_from_terminal_id)
                faults.append(FaultCheckInput(
                    description_he=plan.description_he,
                    selected_label_he=plan.option(ch.option_id).label_he,
                    amount=ch.amount, charged=ch.charged, status=ch.status,
                    moved_by_pin=ch.moved_by_pin, charged_elsewhere_he=pointer,
                    pinned_criterion_he=pinned))
        terminals.append(TerminalExplainerInput(
            alias=f"t{n}", terminal_id=tid, teacher_text=teacher_text(tid),
            points_possible=plans[tid].points_possible,
            interpretation_notes_he=tuple(plans[tid].interpretation_notes_he),
            awarded=pt.awarded, credit_checks=tuple(credits), fault_checks=tuple(faults),
            fallback_he=compose_reasoning_he(priced, view, tid)))

    notes: List[str] = []
    for tid in scope_tids:
        for cid in priced_terminals[tid].notes_observed:
            option = records[cid].plan.option("observed")
            if option is not None:
                notes.append(option.label_he)

    return ScopeExplainerInput(
        question_id=key[0], sub_question_id=key[1], question_text=mat.question_text,
        example_solution=mat.example_solution or "", observed_notes_he=tuple(notes),
        terminals=tuple(terminals))


def _evidence(rec: CheckRecordV6, resolved_option_id: Optional[str]) -> Dict[str, str]:
    """The evidence for the RESOLVED option, and only for it: the model's verified quote
    when the resolution IS the model's own non-default pick, or its absence pointer when
    the model itself chose the zero option. A gated pick (unverified quote) resolves to
    the zero option with neither — the explainer sees the grade, never the claim."""
    if resolved_option_id is None or resolved_option_id != rec.model_option_id:
        return {}
    if resolved_option_id == rec.plan.default_option.option_id:
        pointer = (rec.absence_pointer_he or "").strip()
        return {"absence_pointer_he": pointer} if pointer else {}
    quote = rec.evidence_quote or ""
    if rec.quote_status in _VERIFIED and quote.strip():
        return {"evidence_quote": quote}
    return {}


def _scope_name(key: ScopeKey) -> str:
    return key[0] if key[1] is None else f"{key[0]}.{key[1]}"


# ═══════════════════════════════════════════════════════════════════════════
# the recorded payload (§13.4 arm B)
# ═══════════════════════════════════════════════════════════════════════════

def payload_to_dict(inp: ScopeExplainerInput) -> Dict[str, Any]:
    """JSON-safe: Decimals as strings, tuples as lists."""
    return inp.model_dump(mode="json")


def payload_from_dict(d: Mapping[str, Any]) -> ScopeExplainerInput:
    return ScopeExplainerInput.model_validate(dict(d))
