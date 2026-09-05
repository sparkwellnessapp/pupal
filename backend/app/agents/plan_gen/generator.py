"""
Generate a GradingPlan from a compiled rubric contract (Phase 0).

The shape is generate → verify → bounded repair, per SCOPE:

  * the terminal set is DERIVED from the contract, never proposed (V6);
  * `plan_validator` is the gate, and its tagged errors go back verbatim;
  * repair is per scope, so one bad scope never re-rolls the other five;
  * `check_id`s are minted deterministically here — the model never sees them,
    so it cannot collide them or encode meaning in them.

RULING 1: the model's output type has no `source` field, so every check this
module produces is `generated`. Only `plan_compiler` may set `ruling`.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from app.agents.grader.plan_schemas import GradingPlan, PlanCheck, TerminalPlan
from app.agents.grader.plan_validator import validate_plan
from app.agents.plan_gen.constitution import CONSTITUTION_VERSION, clauses_for
from app.agents.plan_gen.dispositions import (
    escape_hatch_count, validate_dispositions)
from app.agents.plan_gen.prompt import (
    PLAN_GEN_PROMPT_VERSION, SYSTEM_PROMPT, build_generation_message,
    detect_deductions, repair_message, scope_corpus,
)
from app.agents.plan_gen.schemas import ScopeDecomposition

logger = logging.getLogger(__name__)

MAX_REPAIRS = 2          # bounded: a third attempt has never been the fix
_KIND_TAG = {"required": "k", "tariff": "t", "note_only": "n"}


ScopeKey = Tuple[str, Optional[str]]


def _scope_of(question, sub_question, path: Optional[List[str]] = None) -> ScopeKey:
    """(question_id, FULL PATH to the leaf) — the PR-3 convention.

    ⚠ THIS USED TO CARRY THE LEAF'S OWN ID, AND IT COLLIDED. `bagrut_899371`'s
    q1 has two sub-questions (א, ב) whose children are BOTH named `1` and `2`,
    so four distinct leaves produced two labels: `q1.1` and `q1.2`, each twice.

    The damage was silent and landed on VALIDATION, not generation. `gen_plan`
    builds `corpora[label]`, so the second write won and q1.א's checks were
    grounded against q1.ב's text — 11 spurious V9 failures on a plan whose
    quotes were verbatim. Generation itself was unaffected (it validates each
    scope against a fresh single-entry dict), which is exactly why the defect
    presented as "the model fabricated quotes".

    INV-2's `target_id`, `gradable_compiler`'s scope ids and the terminal ids
    themselves all use the full path (`q1.א.2`); this was the one place that did
    not. Depth-1 exams cannot expose it, which is why hobby never did.
    """
    if sub_question is None:
        return (question.question_id, None)
    full = ".".join((path or []) + [sub_question.sub_question_id])
    return (question.question_id, full)


def _scope_label(key: ScopeKey) -> str:
    qid, sqid = key
    return f"{qid}.{sqid}" if sqid else qid


def contract_scopes(contract) -> List[Tuple[ScopeKey, object, object]]:
    """(key, question, sub_question|None) for every LEAF scope.

    Mirrors the gradable compiler: a sub-question WITH children contributes no
    scope of its own (PR-3, scopes are leaves at any depth).
    """
    out: List[Tuple[ScopeKey, object, object]] = []

    def walk_sub(question, sub, path: List[str]) -> None:
        if getattr(sub, "sub_questions", None):
            for child in sub.sub_questions:
                walk_sub(question, child, path + [sub.sub_question_id])
        else:
            out.append((_scope_of(question, sub, path), question, sub))

    for question in contract.questions:
        if question.sub_questions:
            for sub in question.sub_questions:
                walk_sub(question, sub, [])
        else:
            out.append((_scope_of(question, None), question, None))
    return out


def terminals_of(node) -> List[Tuple[str, Decimal]]:
    """The DERIVED terminal set for one scope: a criterion with sub-criteria
    contributes its sub-criteria, otherwise itself."""
    out: List[Tuple[str, Decimal]] = []
    for criterion in getattr(node, "criteria", []) or []:
        subs = getattr(criterion, "sub_criteria", None)
        if subs:
            out.extend((sc.sub_criterion_id, sc.points) for sc in subs)
        else:
            out.append((criterion.criterion_id, criterion.points))
    return out


def _to_plan_checks(terminal_id: str, generated) -> List[PlanCheck]:
    """Mint ids and stamp `source="generated"` — RULING 1, structurally."""
    counters: Dict[str, int] = {}
    checks: List[PlanCheck] = []
    for raw in generated.checks:
        tag = _KIND_TAG.get(raw.kind, "k")
        counters[tag] = counters.get(tag, 0) + 1
        checks.append(PlanCheck(
            check_id=f"{terminal_id}.{tag}{counters[tag]}",
            description_he=raw.description_he,
            kind=raw.kind,
            points=raw.points,
            tariff_amount=raw.tariff_amount,
            partial_fraction=raw.partial_fraction,
            equivalence_note=raw.equivalence_note,
            charge_group=raw.charge_group,
            rubric_quote=raw.rubric_quote,
            source="generated",
        ))
    return checks


class PlanGenerator:
    """One generation run over one contract.

    `llm` is a structured-output runnable over `ScopeDecomposition`; injected so
    tests never call a provider.
    """

    def __init__(self, llm, *, include_constitution: bool = True,
                 include_solution: bool = True,
                 plan_version: str = "generated/v1"):
        self._llm = llm
        self._include_constitution = include_constitution
        self._include_solution = include_solution
        self._plan_version = plan_version
        self.usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
        self.repairs: Dict[str, int] = {}
        self.markers: Dict[str, int] = {}
        self.escape_hatch: Dict[str, int] = {}

    async def _propose(self, messages) -> ScopeDecomposition:
        from langchain_core.messages import HumanMessage, SystemMessage

        result = await self._llm.ainvoke(
            [SystemMessage(content=SYSTEM_PROMPT)]
            + [HumanMessage(content=m) for m in messages])
        self.usage["calls"] += 1
        parsed = result
        if isinstance(result, dict):          # include_raw=True
            if result.get("parsing_error"):
                raise ValueError(f"plan-gen parse failure: {result['parsing_error']}")
            raw = result.get("raw")
            usage = (getattr(raw, "usage_metadata", None) or {}) if raw else {}
            self.usage["input_tokens"] += usage.get("input_tokens", 0)
            self.usage["output_tokens"] += usage.get("output_tokens", 0)
            parsed = result["parsed"]
        return parsed

    async def _scope(self, contract, key: ScopeKey, question, sub) -> List[TerminalPlan]:
        node = sub or question
        derived = terminals_of(node)
        if not derived:
            return []

        corpus = scope_corpus(question, sub,
                              include_solution=self._include_solution)
        # DETERMINISTIC: the model disposes of this list, it never has to find it
        markers = detect_deductions(question, sub,
                                    include_solution=self._include_solution)
        self.markers[_scope_label(key)] = len(markers)
        message = build_generation_message(
            key, corpus, [(t, str(p)) for t, p in derived],
            precision=str(contract.numeric_policy.precision),
            clauses=clauses_for(contract.subject,
                                include_constitution=self._include_constitution),
            subject=contract.subject,
            programming_language=contract.programming_language,
            deductions=markers)

        history = [message]
        points = {t: p for t, p in derived}
        scopes = {t: _scope_label(key) for t, _ in derived}

        for attempt in range(MAX_REPAIRS + 1):
            decomposition = await self._propose(history)
            terminals = [
                TerminalPlan(terminal_id=g.terminal_id,
                             points_possible=points.get(g.terminal_id, g.points_possible),
                             checks=_to_plan_checks(g.terminal_id, g))
                for g in decomposition.terminals
                if g.terminal_id in points          # V6 is assembly's job, not the model's
            ]
            # validate THIS scope in isolation — a sibling scope's problem must
            # not be fed back as if it were this one's
            errors = validate_plan(
                GradingPlan(plan_version=self._plan_version, exam_id="gen",
                            rubric_contract_sha256="", terminals=terminals),
                contract_terminal_points=points, terminal_scopes=scopes,
                precision=contract.numeric_policy.precision,
                scope_corpora={_scope_label(key): corpus})
            # V11 rides the same loop: its errors are tagged strings like the
            # rest, so a dropped marker or a substituted amount comes back to
            # the model in the same breath as an arithmetic failure.
            errors += validate_dispositions(
                markers, getattr(decomposition, "dispositions", []), terminals)
            self.escape_hatch[_scope_label(key)] = escape_hatch_count(
                getattr(decomposition, "dispositions", []))
            if not errors:
                return terminals
            self.repairs[_scope_label(key)] = attempt + 1
            logger.info("plan_gen_repair", extra={"scope": _scope_label(key),
                                                  "attempt": attempt + 1,
                                                  "errors": len(errors)})
            history = [message, repair_message(errors)]

        # Exhausted: return the last attempt and let the FULL validation report
        # it. Returning nothing would silently drop a scope, which V6 would then
        # report as a missing terminal — the wrong cause, far from the failure.
        logger.warning("plan_gen_unrepaired", extra={"scope": _scope_label(key)})
        return terminals

    async def generate(self, contract, *, exam_id: str,
                       resume: Optional[Dict[str, List[TerminalPlan]]] = None,
                       on_scope=None) -> Tuple[GradingPlan, Dict]:
        """`resume` / `on_scope` make a long run RESUMABLE, and they exist
        because a run died and took its own spend with it.

        The scope loop is sequential and the plan is only assembled at the end,
        so a transport failure on scope 11 of 13 discards eleven scopes that
        were already generated and paid for. `on_scope(label, terminals)` is
        called as each scope lands, and `resume` supplies scopes a previous
        attempt already produced — so a retry pays only for what is missing.

        Both default to off: with neither, this is the original loop exactly.
        """
        resume = resume or {}
        terminals: List[TerminalPlan] = []
        corpora: Dict[str, str] = {}
        for key, question, sub in contract_scopes(contract):
            label = _scope_label(key)
            done = resume.get(label)
            if done is not None:
                logger.info("plan_gen_resumed", extra={"scope": label})
                terminals.extend(done)
            else:
                produced = await self._scope(contract, key, question, sub)
                terminals.extend(produced)
                if on_scope is not None:
                    on_scope(label, produced)
            corpora[label] = scope_corpus(
                question, sub, include_solution=self._include_solution)

        plan = GradingPlan(
            plan_version=self._plan_version,
            exam_id=exam_id,
            rubric_contract_sha256="",
            terminals=terminals)
        return plan, {
            "usage": dict(self.usage),
            "repairs": dict(self.repairs),
            "markers_detected": dict(self.markers),
            "not_a_deduction": dict(self.escape_hatch),
            "scope_corpora": corpora,
            "constitution_version": (CONSTITUTION_VERSION
                                     if self._include_constitution else None),
            "prompt_version": PLAN_GEN_PROMPT_VERSION,
        }
