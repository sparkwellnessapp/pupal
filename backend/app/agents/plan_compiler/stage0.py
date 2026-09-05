"""
PLAN COMPILER v2 — Stage 0: DERIVE the scope and terminal sets from a contract.

Moved verbatim from `plan_gen.generator` when the Opus decomposer was retired
(R-4); the derivation predates the compiler and its collision fix is ratified
(R-1). Pure; mirrors `gradable_compiler` — scopes are LEAVES at any depth
(PR-3) and the terminal set is never proposed, only derived (validator V6).
"""
from __future__ import annotations

from decimal import Decimal
from typing import List, Optional, Tuple

ScopeKey = Tuple[str, Optional[str]]


def _scope_of(question, sub_question, path: Optional[List[str]] = None) -> ScopeKey:
    """(question_id, FULL PATH to the leaf) — the PR-3 convention.

    ⚠ THIS USED TO CARRY THE LEAF'S OWN ID, AND IT COLLIDED. `bagrut_899371`'s
    q1 has two sub-questions (א, ב) whose children are BOTH named `1` and `2`,
    so four distinct leaves produced two labels: `q1.1` and `q1.2`, each twice.

    The damage was silent and landed on VALIDATION, not generation. `gen_plan`
    built `corpora[label]`, so the second write won and q1.א's checks were
    grounded against q1.ב's text — 11 spurious V9 failures on a plan whose
    quotes were verbatim. Generation itself was unaffected (it validated each
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


def scope_label(key: ScopeKey) -> str:
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
