"""
grader-v6 — the Math / English STRUCTURAL smoke (owner rulings 2026-10-17 §6a). $0: no model.

    python -m tests.grading_eval_suite.tools.v6_smoke_structural [--out docs/plans/v6_smoke_structural.md]

For math3 and the English writing rubric (`smoke/known_answers.json`):
  1. Stage 1 compiles with no error. English: every criterion a `levels` shape from the
     C8-lite band ladder. Math: the components and point splits as compiled.
  2. The deterministic FALLBACK plan of every scope passes V12–V20; V21 is reported.
  3. For every pre-registered answer, the VERIFIER payload of every answered scope builds,
     addresses checks and options by AM-G17 aliases only (no real id), and is byte-identical
     when every option value moves — so no value reaches the verifier (§6.1).
  4. The answer is graded by the real `OptionsVerifyGrader` on a scripted fake model, so the
     draft is the real one. Then every check is set BY HAND to the option matching the
     intended class of its criterion: full → the full option, zero → the zero option,
     partial → a middle level, a ladder partial, or a mix of full/zero parts. A criterion
     whose plan cannot express a partial is listed. THE pricer prices it; the explainer
     payload builds from it, aliases only.
  5. Renders: her criterion rows, and the expanded checks, per answer.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Tuple

BACKEND = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND))

from app.agents.grader import plan_values as pv                                      # noqa: E402
from app.agents.grader.plan_schemas import (CheckVerdictV6, GradingPlanV6, PackRef,  # noqa: E402
                                            ScopeVerdictsV6)
from app.agents.grader.plan_validator_v6 import v21_group_enumeration_warnings      # noqa: E402
from app.agents.grader.verifier_prompt_v6 import build_verifier_v6_parts, verifier_aliases  # noqa: E402
from app.agents.plan_compiler.stage1_v6 import compile_stage1_v6                     # noqa: E402
from app.agents.planner.assemble import fallback_scope, validate_scope               # noqa: E402
from app.subjects import get_profile                                                 # noqa: E402
from tests.grading_eval_suite.tools.v6_smoke import (DOCS, SUBJECTS, _sha, load_subject,  # noqa: E402
                                                     transcription)

_REAL_ID = re.compile(r"\bq\d+(?:\.[^\s.]+)*\.(?:c\d+|f\d+|n\d+)\b")


# ── 1–2 · stage 1 and the fallback plan ───────────────────────────────────────

def fallback_plan(subject: str, contract):
    s1 = compile_stage1_v6(contract, exam_id=f"smoke_{subject}", rubric_contract_sha256=_sha(contract))
    profile = get_profile(contract.subject)
    terminals, checks, errors, v21 = [], [], {}, []
    for scope in s1.scopes:
        t, c, d = fallback_scope(scope, s1.precision)
        errs = validate_scope(scope, t, c, d, s1.precision)
        if errs:
            errors[scope.scope] = errs
        v21 += v21_group_enumeration_warnings(c, {t.terminal_id: scope.scope for t in scope.terminals})
        terminals += t
        checks += c
    plan = GradingPlanV6(plan_schema="plan/v6", plan_hash=pv.plan_hash(terminals, checks),
                         config_hash="smoke-structural", rubric_contract_version=str(contract.contract_version),
                         subject_pack=PackRef(pack_id=profile.pack_id, pack_version=profile.pack_version),
                         terminals=terminals, checks=checks)
    return s1, plan, errors, v21


# ── 3 · the verifier payload ───────────────────────────────────────────────────

def _shifted(checks):
    return [c.model_copy(update={"options": [o.model_copy(update={"value": o.value + Decimal("0.25")
                                                                   if o.value >= 0 else o.value - Decimal("0.25")})
                                             for o in c.options]}) for c in checks]


def verifier_payload_checks(plan, gradable) -> List[str]:
    """Problems with the verifier payload of every answered scope; [] when clean."""
    problems = []
    for scope in gradable.scopes:
        if not (scope.student_answer_text or "").strip():
            continue
        wanted = {c.criterion_id for c in scope.criteria} | {
            sc.sub_criterion_id for c in scope.criteria for sc in (c.sub_criteria or [])}
        checks = [c for c in plan.checks if c.priced_terminal_id in wanted]
        if not checks:
            problems.append(f"{scope.question_id}.{scope.sub_question_id}: no checks")
            continue
        rubric, student = build_verifier_v6_parts(scope, checks, verifier_aliases(checks))
        moved, _ = build_verifier_v6_parts(scope, _shifted(checks), verifier_aliases(_shifted(checks)))
        if moved != rubric:
            problems.append(f"{scope.question_id}.{scope.sub_question_id}: the payload moves with option values")
        leaked = [c.check_id for c in checks if c.check_id in rubric + student]
        if leaked:
            problems.append(f"{scope.question_id}.{scope.sub_question_id}: real check ids in the payload {leaked}")
        if not re.search(r"\bc1\b", rubric):
            problems.append(f"{scope.question_id}.{scope.sub_question_id}: no c1 alias")
    return problems


# ── 4 · grade (fake model), then the hand selection ───────────────────────────

class _Scripted:
    """The verifier's structured-output surface, answering every check with its default
    option (the zero option for a credit, `none` for a fault). The real grader post-
    validates it; the hand selection then replaces every choice."""

    def with_structured_output(self, schema, include_raw=True):
        assert schema is ScopeVerdictsV6 and include_raw
        return self

    async def ainvoke(self, messages):
        from langchain_core.messages import AIMessage
        user = messages[-1].content if isinstance(messages[-1].content, str) else \
            "".join(b.get("text", "") for b in messages[-1].content)
        verdicts = []
        for m in re.finditer(r"^(c\d+) \[([A-Z]+)\]", user, flags=re.M):
            cid, role = m.group(1), m.group(2)
            opts = re.findall(rf"^   (o\d+): ", user.split(m.group(0), 1)[1].split("\nc", 1)[0], flags=re.M)
            pick = opts[-1] if role.startswith("CRED") or role.startswith("ז") else opts[0]
            verdicts.append(CheckVerdictV6(check_id=cid, evidence_quote="", absence_pointer_he="", option_id=pick))
        raw = AIMessage(content="", usage_metadata={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                        response_metadata={"model": "scripted"})
        return {"raw": raw, "parsed": ScopeVerdictsV6(verdicts=verdicts), "parsing_error": None}


def _partial_choice(checks) -> Tuple[Dict[str, str], bool]:
    """Option ids for a PARTIAL award on one terminal's credits, and whether one exists."""
    credits = [c for c in checks if c.role == "credit"]
    for c in credits:                       # a middle level / a ladder partial
        mids = [o for o in c.options if Decimal(0) < o.value < c.options[0].value]
        if mids and c.shape in ("levels", "ladder", "count"):
            return {c.check_id: mids[0].option_id}, True
    if len(credits) >= 2:                   # some parts full, the rest zero
        return ({credits[0].check_id: credits[0].options[0].option_id}
                | {c.check_id: c.default_option.option_id for c in credits[1:]}), True
    return {}, False


def hand_select(content, intended: Dict[str, str]):
    from app.services.pricing_v6 import price
    by_t: Dict[str, list] = {}
    for rec in content.checks:
        by_t.setdefault(rec.plan.priced_terminal_id, []).append(rec.plan)
    choice: Dict[str, str] = {}
    inexpressible = []
    for tid, checks in by_t.items():
        want = intended.get(tid)
        if want is None:
            continue
        for c in checks:                    # faults and notes: `none`
            if c.role != "credit":
                choice[c.check_id] = c.options[0].option_id
        if want == "full":
            choice |= {c.check_id: c.options[0].option_id for c in checks if c.role == "credit"}
        elif want == "zero":
            choice |= {c.check_id: c.default_option.option_id for c in checks if c.role == "credit"}
        else:
            ids, ok = _partial_choice(checks)
            if not ok:
                inexpressible.append(tid)
                ids = {c.check_id: c.default_option.option_id for c in checks if c.role == "credit"}
            choice |= ids
    records = []
    for rec in content.checks:
        oid = choice.get(rec.plan.check_id, rec.model_option_id)
        default = rec.plan.default_option.option_id
        records.append(rec.model_copy(update={
            "model_option_id": oid, "quote_status": None if oid == default else "exact",
            "evidence_quote": "" if oid == default else "(hand-selected)"}))
    hand = content.model_copy(update={"checks": records})
    return hand, price(hand.to_view()), inexpressible


def _cls(awarded: Decimal, possible: Decimal) -> str:
    return "zero" if awarded == 0 else ("full" if awarded == possible else "partial")


def explainer_payload_checks(hand, priced, gradable) -> Tuple[int, List[str]]:
    from app.agents.explainer.payload import ScopeMaterials, build_scope_inputs, payload_to_dict
    from app.agents.explainer.prompt import render_scope_message
    materials = {}
    for sc in gradable.scopes:
        texts = {}
        for c in sc.criteria:
            for leaf in (c.sub_criteria or [c]):
                texts[getattr(leaf, "sub_criterion_id", None) or leaf.criterion_id] = leaf.description
        materials[(sc.question_id, sc.sub_question_id)] = ScopeMaterials(
            question_text="\n".join(t for t in (sc.question_text, sc.sub_question_text) if t),
            example_solution=sc.example_solution or "", teacher_texts=texts)
    inputs = build_scope_inputs(hand, priced, materials)
    problems = []
    for inp in inputs:
        json.dumps(payload_to_dict(inp), ensure_ascii=False)        # the recorded form builds
        # AM-G17 binds what the MODEL reads: the rendered message (the recorded input keeps
        # the real ids on purpose — to map the model's aliases back — and never renders them)
        leaked = sorted(set(_REAL_ID.findall(render_scope_message(inp))))
        if leaked:
            problems.append(f"real ids in a rendered explainer message: {leaked[:4]}")
    return len(inputs), problems


async def run_subject(subject: str) -> dict:
    from app.agents.grader.grader_v6 import OptionsVerifyGrader
    from app.services import gradable_compiler
    entry, contract = load_subject(subject)
    s1, plan, errors, v21 = fallback_plan(subject, contract)
    levels = [t for sc in s1.scopes for t in sc.terminals if t.shape == "levels"]
    out = {"subject": subject, "scopes": len(s1.scopes), "terminals": len(plan.terminals),
           "checks": len(plan.checks), "stage1_flags": [str(f) for f in s1.flags][:8],
           "fallback_validator_errors": errors, "v21": v21,
           "levels": [(t.terminal_id, [(lab, str(v)) for lab, v in t.bands]) for t in levels],
           "components": [(t.terminal_id, str(t.points_possible), [str(c.points) for c in t.components])
                          for sc in s1.scopes for t in sc.terminals if t.shape == "components"],
           "answers": {}}
    possible = {t.terminal_id: t.points_possible for t in plan.terminals}
    for name, answers in entry["answers"].items():
        gradable = gradable_compiler.compile(contract, transcription(answers))
        vproblems = verifier_payload_checks(plan, gradable)
        agent = OptionsVerifyGrader(plan, contract, llm=_Scripted(), model_version="scripted",
                                    profile=get_profile(plan.subject_pack.pack_id))
        draft = await agent.grade(gradable)
        from app.schemas.graded_test_draft_v6 import v6_content
        hand, priced, inexpressible = hand_select(v6_content(draft), entry["intended"][name])
        n_inputs, eproblems = explainer_payload_checks(hand, priced, gradable)
        awarded = {t.terminal_id: t.awarded for t in priced.terminals}
        rows = [{"terminal_id": tid, "intended": want, "awarded": str(awarded[tid]),
                 "possible": str(possible[tid]), "got": _cls(awarded[tid], possible[tid])}
                for tid, want in entry["intended"][name].items()]
        out["answers"][name] = {
            "verifier_payload_problems": vproblems, "explainer_inputs": n_inputs,
            "explainer_payload_problems": eproblems, "inexpressible_partials": inexpressible,
            "rows": rows, "hand": hand,
            "zero_for_wrong": all(r["got"] == "zero" for r in rows if r["intended"] == "zero"),
            "full_for_full": all(r["got"] == "full" for r in rows if r["intended"] == "full"),
            "partial_where_expressible": all(r["got"] == "partial" for r in rows
                                             if r["intended"] == "partial"
                                             and r["terminal_id"] not in inexpressible)}
    return out


# ── 5 · render ─────────────────────────────────────────────────────────────────

def render(results: List[dict]) -> str:
    from tests.grading_eval_suite.tools.v6_smoke import load_subject as _ls
    ok = {True: "✅", False: "❌"}
    L = ["# grader-v6 — Math / English structural smoke (§6a, $0, no model)", "",
         "The deterministic FALLBACK plan, the real v6 grader on a scripted model, every check set by "
         "hand to the option matching the pre-registered class, priced by THE pricer.", ""]
    for r in results:
        _entry, contract = _ls(r["subject"])
        texts = {}

        def walk(node):
            for c in getattr(node, "criteria", None) or []:
                texts[c.criterion_id] = " ".join((c.description or "").split())[:100]
            for s in getattr(node, "sub_questions", None) or []:
                walk(s)
        for q in contract.questions:
            walk(q)
        L += [f"## {r['subject']}", "",
              f"- Stage 1: {r['scopes']} scopes · {r['terminals']} criteria · fallback plan {r['checks']} checks.",
              f"- Fallback plan through V12–V20: "
              f"{'clean ✅' if not r['fallback_validator_errors'] else '❌ ' + json.dumps(r['fallback_validator_errors'], ensure_ascii=False)}"
              f" · V21 warnings: {len(r['v21'])}."]
        if r["levels"]:
            L.append(f"- `levels` from the C8-lite band ladder: " + "; ".join(
                f"`{tid}` " + " / ".join(f"{lab.split()[0]} {v}" for lab, v in bands) for tid, bands in r["levels"]))
        else:
            comps = [f"`{tid}` {p}" + (f" = {'+'.join(cs)}" if len(cs) > 1 else "") for tid, p, cs in r["components"]]
            L.append(f"- Components as compiled ({len(comps)}): " + ", ".join(comps))
        for name, a in r["answers"].items():
            L += ["", f"### {name}", "",
                  f"- verifier payload: {'aliases only, value-invariant ✅' if not a['verifier_payload_problems'] else '❌ ' + '; '.join(a['verifier_payload_problems'])}",
                  f"- explainer payload: {a['explainer_inputs']} scope input(s) built, "
                  f"{'aliases only ✅' if not a['explainer_payload_problems'] else '❌ ' + '; '.join(a['explainer_payload_problems'])}",
                  f"- pricing: zero for wrong/blank {ok[a['zero_for_wrong']]} · full for full {ok[a['full_for_full']]}"
                  f" · partial where expressible {ok[a['partial_where_expressible']]}"
                  + (f" · **partial NOT expressible on the fallback plan:** {', '.join(f'`{t}`' for t in a['inexpressible_partials'])}"
                     if a["inexpressible_partials"] else ""), "",
                  "| criterion | her text | intended | priced | |", "|---|---|---|---|---|"]
            hand = a["hand"]
            by_t: Dict[str, list] = {}
            for rec in hand.checks:
                by_t.setdefault(rec.plan.priced_terminal_id, []).append(rec)
            for row in a["rows"]:
                tid = row["terminal_id"]
                good = row["got"] == row["intended"] or (row["intended"] == "partial" and tid in a["inexpressible_partials"])
                L.append(f"| `{tid}` | {texts.get(tid, '')} | {row['intended']} | {row['awarded']}/{row['possible']} "
                         f"{row['got']} | {ok[good]} |")
            if name.startswith("A2"):
                L += ["", "Expanded checks (the partial answer):", ""]
                for row in a["rows"]:
                    for rec in by_t.get(row["terminal_id"], []):
                        o = rec.plan.option(rec.model_option_id) or rec.plan.default_option
                        L.append(f"- `{row['terminal_id']}` {rec.plan.role}/{rec.plan.shape} · {rec.plan.description_he} "
                                 f"→ **{o.label_he}** ({pv.canonical_decimal(o.value)})")
        L.append("")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DOCS / "v6_smoke_structural.md"))
    a = ap.parse_args()
    results = [asyncio.run(run_subject(s)) for s in SUBJECTS]
    text = render(results)
    Path(a.out).write_text(text, encoding="utf-8")
    for r in results:
        print(r["subject"], "fallback errors:", len(r["fallback_validator_errors"]), "· V21:", len(r["v21"]))
        for name, x in r["answers"].items():
            print("  ", name, "verifier", "ok" if not x["verifier_payload_problems"] else x["verifier_payload_problems"][:2],
                  "· explainer", x["explainer_inputs"], "ok" if not x["explainer_payload_problems"] else x["explainer_payload_problems"][:2],
                  "· zero", x["zero_for_wrong"], "full", x["full_for_full"], "partial", x["partial_where_expressible"],
                  "· inexpressible", x["inexpressible_partials"])


if __name__ == "__main__":
    main()
