"""$0 estimate of the v6 feedback call's cost per test (owner rulings 2026-10-17 §8).

1. Tokens per character, calibrated on RECORDED Claude calls in this domain: the v6
   planner recordings (Opus 5.5, planner-v6.2) carry each scope call's usage; the
   per-scope VARIABLE part (uncached input) is the user message alone, so the slope
   of uncached tokens on user-message characters is the tokenizer's rate on this
   Hebrew + code mix, free of the cached system prompt and schema.
2. Feedback input per test: the exact message the runner would send for each of the
   36 recorded run-10 v6 drafts (system prompt + build_feedback_message over
   render_scope_v6 of every llm-graded scope).
3. Feedback output per test: the recorded Sonnet 5 feedback texts (Aug 30 run, the
   only recorded feedback outputs), characters → tokens at the same rate.
4. Priced on the feedback model's card (claude-sonnet-5), no caching.

The planner calibration (Opus 5.5) is kept for the record; the verifier fit replaces it,
because the planner's uncached part carries a large fixed block and gives an
implausible rate. No provider is called; run from backend/:
    python -m tests.grading_eval_suite.tools.v6_feedback_cost
"""
import glob
import hashlib
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]        # .../backend
sys.path.insert(0, str(ROOT))

from app.agents.feedback.prompt import FEEDBACK_SYSTEM_PROMPT, build_feedback_message, render_scope_v6  # noqa
from app.agents.plan_compiler.models import MODEL_CARDS  # noqa
from app.agents.plan_compiler.stage1_v6 import compile_stage1_v6  # noqa
from app.agents.planner.stage1_input import scope_planner_input  # noqa
from app.agents.planner.prompt import render_scope_input  # noqa
from app.schemas.graded_test_draft import GradedTestDraft  # noqa
from app.schemas.graded_test_draft_v6 import v6_content  # noqa
from app.services.pricing_v6 import price  # noqa
from tests.grading_eval_suite.fixtures import load_bundle  # noqa

SUITE = ROOT / "tests" / "grading_eval_suite"
EXAMS = {"hobby_tvshow": "din_ezra", "bagrut_899371": "bagrut_899371.din_ezra"}

# 1. calibration
xs, ys = [], []
for exam, fixture in EXAMS.items():
    contract = load_bundle(fixture, require_gt=False).rubric_contract
    sha = hashlib.sha256(contract.model_dump_json().encode("utf-8")).hexdigest()
    s1 = compile_stage1_v6(contract, exam_id=exam, rubric_contract_sha256=sha)
    rec = json.loads((SUITE / "plans" / "v6" / f"{exam}.claude-opus-5.5.recorded.json").read_text(encoding="utf-8"))
    for scope in s1.scopes:
        r = rec["scopes"].get(scope.scope)
        if not r or not r.get("usage"):
            continue
        u = r["usage"][0]
        user = render_scope_input(scope_planner_input(scope))
        xs.append(len(user))
        ys.append(u["input_tokens"] - (u.get("cached_input_tokens") or 0) - (u.get("cache_write_input_tokens") or 0))
planner_pts = list(zip(xs, ys))

# 1b. calibration on the run-10 VERIFIER calls (Sonnet 5.5): per scope, uncached input
#     tokens against the user message's characters (the system prompt is the cached prefix)
from app.agents.grader.plan_schemas import GradingPlanV6  # noqa
from app.agents.grader.verifier_prompt_v6 import build_verifier_v6_parts, verifier_aliases  # noqa
from app.agents.grader.grader import _get_terminal_map  # noqa
vx, vy = [], []
plans = {e: GradingPlanV6.model_validate_json((SUITE / "plans" / "v6" / f"{e}.plan.json").read_text(encoding="utf-8"))
         for e in EXAMS}
run10 = SUITE / "results" / "20261017-162850_v6-cs-sonnet55-amg19" / "drafts"
for f in sorted(glob.glob(str(run10 / "*_r[0-9].json"))):
    stem = Path(f).name.rsplit("_r", 1)[0]
    exam = "bagrut_899371" if stem.startswith("bagrut") else "hobby_tvshow"
    plan = plans[exam]
    bundle = load_bundle(stem, require_gt=False)
    draft = GradedTestDraft.model_validate_json(Path(f).read_text(encoding="utf-8"))
    recs = {(r.question_id, r.sub_question_id): r for r in v6_content(draft).scopes}
    for scope in bundle.gradable_test.scopes:
        r = recs.get((scope.question_id, scope.sub_question_id))
        if r is None or r.usage is None or r.usage.calls != 1 or r.retry_count:
            continue
        tids = set(_get_terminal_map(scope))
        checks = [c for c in plan.checks if c.priced_terminal_id in tids]
        if not checks:
            continue
        a, b = build_verifier_v6_parts(scope, checks, verifier_aliases(checks))
        u = r.usage
        vx.append(len(a) + len(b))
        vy.append(u.input_tokens)                     # total: cached + written + fresh
xs, ys = vx, vy
n = len(xs)
mx, my = sum(xs) / n, sum(ys) / n
slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
icpt = my - slope * mx
ratio = sum(ys) / sum(xs)
print(f"calibration: {n} verifier scope calls (Sonnet 5.5) · tokens/char slope {slope:.4f} (intercept {icpt:.0f}) · plain ratio {ratio:.4f}")

# 2. feedback input per test, from the run-10 drafts
run = SUITE / "results" / "20261017-162850_v6-cs-sonnet55-amg19" / "drafts"
inputs, nscopes = [], []
for f in sorted(glob.glob(str(run / "*_r[0-9].json"))):
    draft = GradedTestDraft.model_validate_json(Path(f).read_text(encoding="utf-8"))
    content = v6_content(draft)
    priced = price(content.to_view())
    scopes = [(so.question_id if so.sub_question_id is None else f"{so.question_id}.{so.sub_question_id}", so)
              for so in draft.scope_outcomes if so.graded_by == "llm"]
    msg = build_feedback_message([(sid, render_scope_v6(content, priced, (so.question_id, so.sub_question_id)))
                                  for sid, so in scopes])
    inputs.append(len(FEEDBACK_SYSTEM_PROMPT) + len(msg))
    nscopes.append(len(scopes))
print(f"feedback input: {len(inputs)} drafts · chars mean {statistics.mean(inputs):.0f} "
      f"(min {min(inputs)}, max {max(inputs)})")

# 3. feedback output per test, from the recorded Sonnet 5 feedback
outs, per_scope, summaries = [], [], []
for f in sorted(glob.glob(str(SUITE / "results" / "20260830-205954_sonnet5-v5" / "feedback" / "*.json"))):
    d = json.loads(Path(f).read_text(encoding="utf-8"))
    outs.append(len(json.dumps({"scopes": d["scopes"], "summary": d["summary"]}, ensure_ascii=False)))
    per_scope.append(len(json.dumps(d["scopes"], ensure_ascii=False)) / max(1, len(d["scopes"])))
    summaries.append(len(json.dumps(d["summary"], ensure_ascii=False)))
print(f"feedback output: {len(outs)} recorded tests · chars mean {statistics.mean(outs):.0f} "
      f"(min {min(outs)}, max {max(outs)})")

# 4. price on the feedback model's card
icpt_fb = 300                                    # the feedback schema + framing, a guess
card = MODEL_CARDS["claude-sonnet-5"].price
for label, rate in (("slope", slope), ("plain ratio", ratio)):
    tin = statistics.mean(inputs) * rate
    tout = statistics.mean(outs) * rate
    cost = tin * card.in_per_mtok / 1e6 + tout * card.out_per_mtok / 1e6
    print(f"[{label}] ≈ {tin:.0f} input + {tout:.0f} output tokens → ${cost:.4f} per test "
          f"(card ${card.in_per_mtok}/${card.out_per_mtok} per Mtok)")

# 5. output scaled to each draft's own scope count (the recorded outputs are hobby only)
for label, rate in (("slope", slope),):
    costs = []
    for chars_in, k in zip(inputs, nscopes):
        tin = icpt_fb + chars_in * rate
        tout = (statistics.mean(per_scope) * k + statistics.mean(summaries)) * rate
        costs.append(tin * card.in_per_mtok / 1e6 + tout * card.out_per_mtok / 1e6)
    print(f"[{label}, scaled per scope, +{icpt_fb} schema/framing tokens] mean ${statistics.mean(costs):.4f} "
          f"(min ${min(costs):.4f}, max ${max(costs):.4f}) · llm scopes per test {min(nscopes)}..{max(nscopes)}")
