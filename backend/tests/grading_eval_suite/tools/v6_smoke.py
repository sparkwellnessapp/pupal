"""
grader-v6 — the Math / English KNOWN-ANSWER smoke (owner rulings Oct 6 §3 item 7c; Oct 6
evening §7.5: «the Math/English known-answer smoke as ruled (same planner choice)»).

    python -m tests.eval_common.eval_key tests.grading_eval_suite.tools.v6_smoke \\
        --subject mathematics --planner claude-sonnet-5.5 --confirm-spend [--max-usd 2.0]
    python -m tests.grading_eval_suite.tools.v6_smoke --subject mathematics \\
        --planner claude-sonnet-5.5 --replay --run-dir <dir>          # $0: re-score a run

Per subject, from `smoke/known_answers.json` (written, with every intended class, BEFORE any run):
  1. PLAN — Stage 1, then the v6 planner (the CS iteration's chosen model, effort high) one
     call per scope that needs language, ≤ 1 repair, rule 7 strict → lenient. Recorded to
     `smoke/<subject>.<planner>.recorded.json` (replayable, $0), rendered for REVIEW.
  2. GRADE — each known answer as an approved transcription contract (P1 out of scope),
     compiled to a GradableTest, graded by v6 k=1 on the PRODUCTION config (Oct 17 §6b, §7):
     verifier Sonnet 5.5 (adaptive, effort low), NO explainer — the renders show the
     fallback composer line. Order (§6b): the blank/wrong answers, then the partial ones,
     then the fully correct ones; a step whose estimate exceeds what is left of `--max-usd`
     does not start, and the report says what ran.
  3. SCORE — every criterion's class (full / partial / zero) from THE pricer, against the
     intended class, and the five pre-registered pass conditions:
       · 0 K1-class events (credit on a criterion intended zero — blank or wrong work);
       · the fully correct answer at full on every criterion;
       · ≥ 90% of criteria in their intended class;
       · no unrepaired validator error (a fallback, or a rule-7 downgrade, counts) —
         every fallback reported;
       · English: every criterion a compiled `levels` check on its C8-lite bands.
  4. RENDER — `docs/plans/v6_smoke_<subject>.md`: her criterion rows for every answer with
     the reasoning line; the expanded checks for the partial answer and for every miss.

The spend rules are the eval's: Vertex only (`require_eval_key`, Oct 17 §4), a one-token
canary per model before any call, a hard `--max-usd` (a scope never starts past it).
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BACKEND = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND))

from app.agents.grader import plan_values as pv                                      # noqa: E402
from app.agents.grader.plan_schemas import PackRef                                   # noqa: E402
from app.agents.plan_compiler.models import MODEL_CARDS                              # noqa: E402
from app.agents.plan_compiler.stage1_v6 import STAGE1_V6_VERSION, compile_stage1_v6  # noqa: E402
from app.agents.planner.planner import assemble_plan, plan_scope                     # noqa: E402
from app.agents.planner.prompt import (PLANNER_PROMPT_VERSION, am_g19_applies,      # noqa: E402
                                       planner_system_prompt, render_scope_input)
from app.agents.planner.render import render_plan_md                                 # noqa: E402
from app.agents.planner.schemas import ScopePlanOutput                               # noqa: E402
from app.agents.planner.stage1_input import scope_planner_input                      # noqa: E402
from app.schemas.ontology_types import GradingRubricContract                         # noqa: E402
from app.schemas.transcription import TranscriptionContract, TranscriptionContractAnswer  # noqa: E402
from app.subjects import get_profile                                                 # noqa: E402

SUITE = BACKEND / "tests" / "grading_eval_suite"
SMOKE = SUITE / "smoke"
DOCS = BACKEND.parent / "docs" / "plans"
VERIFIER_KEY = "claude-sonnet-5.5"
VERIFIER_PARAMS = {"reasoning_effort": "low", "thinking": "adaptive"}     # as registered (CS eval)
EXPLAINER_KEY = "claude-sonnet-5.5"                                     # OO-3 arm B (unused in §6b)
WITH_EXPLAINER = False                                                  # §6b: NO explainer
INTENDED_SHARE = Decimal("0.90")


# ── the fixture ───────────────────────────────────────────────────────────────

# [Oct 18 Item A] the answer set: the smoke's own, or the held-out set (`--answers`); `--tag`
# keeps the held-out renders and run dirs apart from the smoke's.
ANSWERS_FILE = "known_answers.json"
TAG = ""


def load_subject(subject: str) -> Tuple[dict, GradingRubricContract]:
    ka = json.loads((SMOKE / ANSWERS_FILE).read_text(encoding="utf-8"))
    entry = ka["subjects"][subject]
    contract = GradingRubricContract.model_validate_json(
        (SMOKE / entry["contract"]).read_text(encoding="utf-8"))
    src = entry.get("question_text_from")
    if src:                                   # the A-9 merge: the exam's own task, verbatim
        path, ref = src.split("#", 1)
        draft = json.loads((SMOKE / path).read_text(encoding="utf-8"))
        rubric = draft.get("rubric") or draft
        idx = int(ref.split("[", 1)[1].rstrip("]"))
        task = rubric["questions"][idx]["question_text"]
        q0 = contract.questions[0].model_copy(update={"question_text": task})
        contract = contract.model_copy(update={"questions": [q0] + list(contract.questions[1:])})
    return entry, contract


def transcription(answers: Dict[str, Dict[str, str]]) -> TranscriptionContract:
    return TranscriptionContract(answers=[
        TranscriptionContractAnswer(question_number=int(q), sub_question_id=(s or None), answer_text=text)
        for q, subs in answers.items() for s, text in subs.items()])


def _sha(contract) -> str:
    return hashlib.sha256(contract.model_dump_json().encode("utf-8")).hexdigest()


# ── 1 · plan ───────────────────────────────────────────────────────────────────

async def plan(subject: str, contract, planner_key: str, *, live: bool, max_usd: float):
    from app.agents.planner.planner import ScopePlanResult  # noqa: F401
    s1 = compile_stage1_v6(contract, exam_id=f"smoke_{subject}", rubric_contract_sha256=_sha(contract))
    profile = get_profile(contract.subject)
    system = planner_system_prompt(profile)
    card = MODEL_CARDS[planner_key]
    rec_path = SMOKE / f"{subject}.{planner_key}.recorded.json"
    if live:
        from app.agents.planner.planner_llm import build_planner_call
        call_live = build_planner_call(model_key=planner_key)
        am_g19 = True
    else:
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        am_g19 = am_g19_applies(rec["planner_prompt_version"])
    results, spent, skipped = [], 0.0, []
    t0 = time.monotonic()
    for scope in s1.scopes:
        if live and scope.needs_planner and spent >= max_usd:
            skipped.append(scope.scope)
            continue
        if live:
            call = call_live
        else:
            r = rec["scopes"].get(scope.scope, {})
            queue = [ScopePlanOutput.model_validate(o) for o in r.get("outputs", [])]
            usage = list(r.get("usage", []))

            async def call(system_, user_, q=queue, u=usage):
                if not q:
                    raise RuntimeError("replay exhausted")
                return q.pop(0), (u.pop(0) if u else {})
        r = await plan_scope(scope, precision=s1.precision, system_prompt=system,
                             user_message=render_scope_input(scope_planner_input(scope)),
                             call=call, am_g19=am_g19)
        cost = sum(u.get("cost_usd", 0.0) for u in r.usage)
        spent += cost
        results.append(r)
        print(f"  plan {scope.scope}: {r.origin} · {len(r.usage)} call(s) · ${cost:.4f}"
              + (f" · {len(r.errors)} validator msg(s)" if r.errors else ""), flush=True)
    if skipped:
        raise SystemExit(f"CAP ${max_usd} reached — scopes NOT planned: {skipped}; no grading")
    config = pv.config_hash(compiler_version=STAGE1_V6_VERSION, planner_model=card.model_id,
                            planner_prompt_version=(PLANNER_PROMPT_VERSION if live
                                                    else rec["planner_prompt_version"]),
                            pack_id=profile.pack_id, pack_version=profile.pack_version)
    the_plan = assemble_plan(results, config_hash=config, rubric_contract_version=str(contract.contract_version),
                             pack=PackRef(pack_id=profile.pack_id, pack_version=profile.pack_version))
    if live:
        rec_path.write_text(json.dumps({
            "subject": subject, "stage1_version": s1.version, "planner_prompt_version": PLANNER_PROMPT_VERSION,
            "model_key": planner_key, "model_id": card.model_id, "plan_hash": the_plan.plan_hash,
            "config_hash": config, "cost_usd": round(spent, 4), "wall_s": round(time.monotonic() - t0, 1),
            "scopes": {r.scope: {"origin": r.origin, "outputs": r.outputs, "usage": r.usage,
                                 "errors": r.errors, "telemetry": r.telemetry} for r in results},
        }, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / f"v6_smoke_{subject}_plan.md").write_text(
        render_plan_md(f"smoke · {subject}", the_plan, s1, results), encoding="utf-8")
    return s1, results, the_plan, spent


# ── 2 · grade ──────────────────────────────────────────────────────────────────

def _grader(the_plan, contract):
    from app.agents.explainer.prompt import EXPLAINER_PROMPT_VERSION
    from app.agents.grader.grader_v6 import OptionsVerifyGrader
    from app.agents.grader.llm_factory import build_chat_model
    from tests.eval_common.models_registry import spec
    from tests.grading_eval_suite.runner import _build_explain
    profile = get_profile(the_plan.subject_pack.pack_id)
    s = spec(VERIFIER_KEY)
    llm = build_chat_model(s.provider, s.model_id, reasoning_effort=VERIFIER_PARAMS["reasoning_effort"],
                           thinking=VERIFIER_PARAMS["thinking"])
    if not WITH_EXPLAINER:                                  # §6b: no explainer — fallback lines
        return OptionsVerifyGrader(the_plan, contract, llm=llm, model_version=s.model_id, profile=profile)
    explain = _build_explain({"explainer": {"model_key": EXPLAINER_KEY, "params": {}},
                              "record_explainer_payloads": False}, profile)
    return OptionsVerifyGrader(the_plan, contract, llm=llm, model_version=s.model_id, profile=profile,
                               explain=explain, explainer_prompt_version=EXPLAINER_PROMPT_VERSION)


# §6b: the blank/wrong answers first, then the partial ones, then the fully correct ones
GRADE_ORDER = ("A3", "A2", "A1")
# a step's estimate before it starts: run 10's measured verifier cost per call (Sonnet 5.5,
# effort low, cached) × the answered scopes, with headroom; actuals come from the drafts
VERIFIER_USD_PER_CALL = 0.0100


def _answered_scopes(answers) -> int:
    return sum(1 for subs in answers.values() for text in subs.values() if text.strip()) or 1


async def grade_one(contract, the_plan, name: str, answers, run_dir: Path) -> Path:
    from app.services import gradable_compiler
    gradable = gradable_compiler.compile(contract, transcription(answers))
    draft = await _grader(the_plan, contract).grade(gradable)
    p = run_dir / f"{name}.json"
    p.write_text(draft.model_dump_json(indent=1), encoding="utf-8")
    return p


def draft_cost(path: Path) -> float:
    from app.schemas.graded_test_draft import GradedTestDraft
    from app.schemas.graded_test_draft_v6 import v6_content
    from tests.grading_eval_suite.v6_cost import usage_cost
    c = v6_content(GradedTestDraft.model_validate_json(path.read_text(encoding="utf-8")))
    return (usage_cost(c.verifier_usage.model_dump() if c.verifier_usage else None)
            + usage_cost(c.explainer_usage.model_dump() if c.explainer_usage else None))


# ── 3 · score ──────────────────────────────────────────────────────────────────

def _cls(awarded: Decimal, possible: Decimal) -> str:
    return "zero" if awarded == 0 else ("full" if awarded == possible else "partial")


def score(entry, the_plan, results, drafts: Dict[str, Path]) -> dict:
    from app.schemas.graded_test_draft import GradedTestDraft
    from app.schemas.graded_test_draft_v6 import v6_content
    from app.services.pricing_v6 import price
    from tests.grading_eval_suite.v6_cost import usage_cost
    possible = {t.terminal_id: t.points_possible for t in the_plan.terminals}
    rows, cost, fallbacks = [], 0.0, 0
    contents = {}
    for name, path in drafts.items():
        content = v6_content(GradedTestDraft.model_validate_json(path.read_text(encoding="utf-8")))
        contents[name] = content
        priced = {t.terminal_id: t for t in price(content.to_view()).terminals}
        for tid, want in entry["intended"][name].items():
            got = _cls(priced[tid].awarded, possible[tid])
            rows.append({"answer": name, "terminal_id": tid, "intended": want, "got": got,
                         "awarded": priced[tid].awarded, "possible": possible[tid]})
        cost += usage_cost(content.verifier_usage.model_dump() if content.verifier_usage else None)
        cost += usage_cost(content.explainer_usage.model_dump() if content.explainer_usage else None)
        fallbacks += sum(1 for s in content.scopes if s.usage and s.usage.model_fallback)
    k1 = [r for r in rows if r["intended"] == "zero" and r["awarded"] > 0]
    full_name = next(n for n in entry["intended"] if n.startswith("A1"))
    a1_not_full = [r for r in rows if r["answer"] == full_name and r["got"] != "full"]
    hit = sum(r["got"] == r["intended"] for r in rows)
    share = Decimal(hit) / Decimal(len(rows)) if rows else Decimal(0)
    missing = [n for n in entry["intended"] if n not in drafts]
    plan_fallbacks = [r.scope for r in results if r.origin == "fallback"]
    downgraded = [r.scope for r in results if any(x.startswith("am_g19_downgraded") for x in r.telemetry)]
    levels_ok = None
    if the_plan.subject_pack.pack_id == "english":
        credits = [c for c in the_plan.checks if c.role == "credit"]
        levels_ok = bool(credits) and all(c.shape == "levels" and c.origin == "compiler" for c in credits)
    checks = {
        "k1_class_events": (not k1, f"{len(k1)}"),
        "full_answer_at_full": (not a1_not_full, f"{len(a1_not_full)} not full"),
        "intended_share": (share >= INTENDED_SHARE, f"{hit}/{len(rows)} = {float(share):.1%}"),
        "validator": (not plan_fallbacks and not downgraded,
                      f"fallback scopes {plan_fallbacks or 0} · rule-7 downgraded {downgraded or 0}"),
    }
    if levels_ok is not None:
        checks["english_levels"] = (levels_ok, "every credit a compiled `levels` check" if levels_ok
                                    else "NOT every credit is a compiled levels check")
    checks["all_answers_ran"] = (not missing, f"not run: {missing}" if missing else "3/3")
    return {"rows": rows, "checks": checks, "pass": all(ok for ok, _ in checks.values()),
            "grading_cost": cost, "model_fallback_scopes": fallbacks, "contents": contents}


# ── 4 · render ─────────────────────────────────────────────────────────────────

def render(subject: str, entry, contract, the_plan, results, scored, planner_key: str,
           plan_cost: float, run_dir: Path) -> str:
    texts = {}
    for q in contract.questions:
        def walk(node, prefix):
            for c in getattr(node, "criteria", None) or []:
                texts[c.criterion_id] = " ".join((c.description or "").split())[:110]
            for s in getattr(node, "sub_questions", None) or []:
                walk(s, prefix)
        walk(q, q.question_id)
    mark = {True: "✅", False: "❌"}
    L = [f"# grader-v6 known-answer smoke — {subject}", "",
         f"**Verdict: {'PASS' if scored['pass'] else 'FAIL'}** · planner `{planner_key}` "
         f"(planner-v6.2) · plan `{the_plan.plan_hash[:12]}…` · verifier Sonnet 5.5 (effort low) · "
         f"no explainer (the fallback composer's lines) · k=1 · route `{_route()}`", "",
         f"Cost: planner ${plan_cost:.4f} · grading ${scored['grading_cost']:.4f} "
         f"({len(entry['answers'])} answers) · run `{run_dir.name}`", "",
         "| pass condition | result | |", "|---|---|---|"]
    L += [f"| {k} | {detail} | {mark[ok]} |" for k, (ok, detail) in scored["checks"].items()]
    L += ["", f"Fixture: {entry['fixture_note']}", ""]
    origins = {o: sum(r.origin == o for r in results) for o in ("planner", "repaired", "fallback", "compiled")}
    L += [f"Plan: {len(the_plan.checks)} checks · scope origins {origins}", ""]
    for name, content in scored["contents"].items():
        rows = [r for r in scored["rows"] if r["answer"] == name]
        hits = sum(r["got"] == r["intended"] for r in rows)
        L += [f"## {name} — {hits}/{len(rows)} in the intended class", "",
              "| criterion | her text | intended | AI | |", "|---|---|---|---|---|"]
        expl = {x.terminal_id: x.text_he for x in content.explanations}
        by_t = {}
        for c in content.checks:
            by_t.setdefault(c.plan.priced_terminal_id, []).append(c)
        detail = []
        for r in rows:
            tid = r["terminal_id"]
            ok = r["got"] == r["intended"]
            L.append(f"| `{tid}` | {texts.get(tid, '')} | {r['intended']} | "
                     f"{pv.canonical_decimal(r['awarded'])}/{pv.canonical_decimal(r['possible'])} {r['got']} | "
                     f"{mark[ok]} |")
            if name.startswith("A2") or not ok:
                detail.append(f"- **`{tid}`** — {expl.get(tid, '(no line)')}")
                for c in by_t.get(tid, []):
                    o = c.plan.option(c.model_option_id) or c.plan.default_option
                    ev = c.evidence_quote or c.absence_pointer_he
                    detail.append(f"  - {c.plan.role} · {c.plan.description_he} → **{o.label_he}** "
                                  f"({pv.canonical_decimal(o.value)})" + (f" · «{ev[:90]}»" if ev else ""))
        if detail:
            L += ["", "Reasoning lines and the checks behind them:" if name.startswith("A2")
                  else "Misses, with their checks:", ""] + detail
        L.append("")
    return "\n".join(L) + "\n"


# ── main ───────────────────────────────────────────────────────────────────────

SUBJECTS = ("mathematics", "english")                  # §6b: plan Math, then English


def _route() -> str:
    from app.agents.grader.llm_factory import claude_route
    from app.config import settings
    return f"vertex:{settings.claude_vertex_region}" if claude_route() == "vertex" else "direct"


async def main_async(a) -> int:
    subjects = SUBJECTS if a.subject == "both" else (a.subject,)
    live = a.confirm_spend                         # grading spends
    plan_live = live and not a.replay              # [Item A] --replay grades on the recorded plan
    if live:
        from tests.eval_common.canary import canary
        from tests.eval_common.eval_key import require_eval_key
        from tests.eval_common.models_registry import spec
        require_eval_key()
        for mid in sorted({MODEL_CARDS[a.planner].model_id, spec(VERIFIER_KEY).model_id}):
            canary(mid)
    spent, ran, stopped = 0.0, [], None
    state = {}
    for subject in subjects:                           # 1 · plan every subject first
        entry, contract = load_subject(subject)
        s1, results, the_plan, plan_cost = await plan(subject, contract, a.planner, live=plan_live,
                                                      max_usd=max(a.max_usd - spent, 0.0))
        if not plan_live:
            plan_cost = 0.0                        # a replayed plan spends nothing now
        spent += plan_cost
        state[subject] = dict(entry=entry, contract=contract, results=results, plan=the_plan,
                              plan_cost=plan_cost, drafts={})
        print(f"== plan {subject} {the_plan.plan_hash[:12]} · ${plan_cost:.4f} · spent ${spent:.4f}", flush=True)
    if a.run_dir:                                      # re-score, or [Item A] resume: grade what is missing
        run_dir = Path(a.run_dir)
        for subject, st in state.items():
            st["drafts"] = {p.stem.split("__", 1)[1]: p for p in sorted(run_dir.glob(f"{subject}__A*.json"))}
    elif not live:
        raise SystemExit("grading spends money: pass --confirm-spend, or --run-dir to re-score")
    else:
        run_dir = SUITE / "results" / f"{datetime.now():%Y%m%d-%H%M%S}_v6-smoke{TAG}"
        run_dir.mkdir(parents=True)
    if live:
        for prefix in GRADE_ORDER:                     # 2 · wrong → partial → full, across subjects
            for subject, st in state.items():
                name = next(n for n in st["entry"]["answers"] if n.startswith(prefix))
                if name in st["drafts"]:               # already graded in this run (resume)
                    continue
                est = VERIFIER_USD_PER_CALL * _answered_scopes(st["entry"]["answers"][name])
                if spent + est > a.max_usd:
                    stopped = f"{subject} {name}: estimate ${est:.4f} > ${a.max_usd - spent:.4f} left"
                    break
                path = await grade_one(st["contract"], st["plan"], f"{subject}__{name}",
                                       st["entry"]["answers"][name], run_dir)
                st["drafts"][name] = path
                cost = draft_cost(path)
                spent += cost
                ran.append(f"{subject} {name} ${cost:.4f}")
                print(f"  graded {subject} {name} · ${cost:.4f} · spent ${spent:.4f}", flush=True)
            if stopped:
                print(f"STOPPED before {stopped}", flush=True)
                break
    verdicts = {}
    for subject, st in state.items():                  # 3 · score + render what ran
        scored = score(st["entry"], st["plan"], st["results"], st["drafts"])
        md = render(subject, st["entry"], st["contract"], st["plan"], st["results"], scored, a.planner,
                    st["plan_cost"], run_dir)
        (DOCS / f"v6_smoke{TAG}_{subject}.md").write_text(md, encoding="utf-8")
        verdicts[subject] = scored["pass"]
        (run_dir / f"smoke_{subject}.json").write_text(json.dumps({
            "subject": subject, "planner": a.planner, "plan_hash": st["plan"].plan_hash, "route": _route(),
            "pass": scored["pass"], "checks": {k: [ok, d] for k, (ok, d) in scored["checks"].items()},
            "planner_cost_usd": round(st["plan_cost"], 6), "grading_cost_usd": round(scored["grading_cost"], 6),
            "model_fallback_scopes": scored["model_fallback_scopes"],
            "rows": [{**r, "awarded": str(r["awarded"]), "possible": str(r["possible"])} for r in scored["rows"]],
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print(md)
    print(f"== smoke: {verdicts} · total ${spent:.4f} · ran {ran}" + (f" · stopped before {stopped}" if stopped else ""))
    return 0 if all(verdicts.values()) else 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", default="both", choices=("both",) + SUBJECTS)
    ap.add_argument("--planner", default="claude-opus-5.5", choices=sorted(MODEL_CARDS))   # §7 production
    ap.add_argument("--confirm-spend", action="store_true")
    ap.add_argument("--replay", action="store_true", help="plan from the recording ($0)")
    ap.add_argument("--run-dir", default=None, help="re-score the drafts of an earlier run ($0)")
    ap.add_argument("--max-usd", type=float, default=2.0)
    ap.add_argument("--answers", default="known_answers.json",
                    help="answer set under smoke/ (Item A: known_answers_heldout.json)")
    ap.add_argument("--tag", default="", help="suffix for renders and the run dir, e.g. _heldout")
    a = ap.parse_args()
    global ANSWERS_FILE, TAG
    ANSWERS_FILE, TAG = a.answers, a.tag
    # [Item A] --replay with --confirm-spend: the RECORDED plan ($0), graded live — the held-out
    # set and the resume of an attempt grade on a plan that was already paid for.
    sys.exit(asyncio.run(main_async(a)))


if __name__ == "__main__":
    main()
