"""
Per-scope context the spend stages read from a contract: the V9 corpus, the
example solution, the question text. One derivation, shared by the production
builder and the eval tools.
"""
from __future__ import annotations

from typing import Dict, Tuple

from app.agents.plan_gen.prompt import scope_corpus

from .stage0 import contract_scopes, scope_label


def scope_maps(contract) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    """(corpora, solutions, questions) keyed by scope label (`q1.א`, `q6`)."""
    corpora: Dict[str, str] = {}
    solutions: Dict[str, str] = {}
    questions: Dict[str, str] = {}
    for key, q, sub in contract_scopes(contract):
        lbl = scope_label(key)
        corpora[lbl] = scope_corpus(q, sub)
        node = sub or q
        sol = next((getattr(n, "example_solution", None) for n in (node, q)
                    if (getattr(n, "example_solution", None) or "").strip()), None)
        if sol:
            solutions[lbl] = sol
        parts = [getattr(q, "question_text", None), getattr(sub, "text", None) if sub else None]
        questions[lbl] = " ".join(p for p in parts if isinstance(p, str) and p.strip())
    return corpora, solutions, questions
