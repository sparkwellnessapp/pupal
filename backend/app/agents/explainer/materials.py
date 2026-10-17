"""The explainer's inputs from a GradableTest, and the grader's `explain` hook — ONE place
for production and the eval runner (owner rulings 2026-10-17 §7: the runner writes the
explanation line into the draft at grading time, before the move to `draft`).

`scope_materials(gradable_test)` gives, per scope, what the explainer reads beside the
priced draft: the question (with the sub-question), the teacher's example solution and her
criterion texts by terminal id. `explain_hook(...)` binds a model to `explain_test` in the
shape `OptionsVerifyGrader(explain=…)` calls: `(content, priced, gradable_test)`.
"""
from __future__ import annotations

from typing import Dict

from .payload import ScopeKey, ScopeMaterials


def scope_materials(gradable_test) -> Dict[ScopeKey, ScopeMaterials]:
    out: Dict[ScopeKey, ScopeMaterials] = {}
    for sc in gradable_test.scopes:
        texts = {}
        for c in sc.criteria:
            for leaf in (c.sub_criteria or [c]):
                tid = getattr(leaf, "sub_criterion_id", None) or leaf.criterion_id
                texts[tid] = leaf.description
        question = "\n".join(t for t in (sc.question_text, sc.sub_question_text) if t)
        out[(sc.question_id, sc.sub_question_id)] = ScopeMaterials(
            question_text=question, example_solution=sc.example_solution or "", teacher_texts=texts)
    return out


def explain_hook(llm, *, model_id: str, profile, record_payloads: bool = False):
    from .explainer import explain_test

    async def explain(content, priced, gradable_test):
        return await explain_test(content, priced, scope_materials(gradable_test),
                                  llm=llm, model_id=model_id, profile=profile,
                                  record_payloads=record_payloads)
    return explain
