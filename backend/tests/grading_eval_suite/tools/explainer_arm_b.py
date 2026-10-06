"""
§13.4 explainer arm B (Oct 6 rulings §3.7a): the SAME recorded explainer payloads of a
v6 run, replayed on Sonnet 5.5 at its lowest setting — thinking `between_tools` (no
thinking without tools; `disabled` is a 400) and effort `low`. Zero verifier spend.

    python -m tests.eval_common.eval_key tests.grading_eval_suite.tools.explainer_arm_b <v6_run_dir>

One test at a time, each under the explainer's own timeout — the condition arm A ran
under. Writes `<run_dir>/arm_b.json`:
  {model, n_tests, cost_usd, cost_per_test, cache_hit, usage, e_pass: [model, total],
   lines: {"<fixture>|r<k>|<terminal_id>": {text_he, source, failed_rules}}}
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND))

ARM_B_MODEL_KEY = "claude-sonnet-5.5"
ARM_B_PARAMS = {"reasoning_effort": "low", "thinking": "between_tools"}


async def main(run_dir: Path) -> None:
    from tests.eval_common.eval_key import require_eval_key
    require_eval_key()                                   # [Oct 6 §2] spend only on the eval key
    from app.agents.explainer.replay import replay_payloads
    from app.agents.grader.llm_factory import build_chat_model
    from app.schemas.graded_test_draft import GradedTestDraft
    from app.schemas.graded_test_draft_v6 import v6_content
    from app.subjects import get_profile
    from app.services.transcription.two_phase.instrument import cost_usd
    from app.services.transcription.vlm_provider import Usage
    from tests.eval_common.models_registry import spec
    from tests.grading_eval_suite.tools.explainer_read_sheet import line_key

    s = spec(ARM_B_MODEL_KEY)
    llm = build_chat_model(s.provider, s.model_id, max_output_tokens=4000, **ARM_B_PARAMS)
    lines, totals = {}, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0}
    served, n_tests, e_model, e_total = set(), 0, 0, 0
    for p in sorted((run_dir / "drafts").glob("*_r*.json")):
        if p.name.endswith(".meta.json"):
            continue
        fixture, r = p.stem.rsplit("_r", 1)
        content = v6_content(GradedTestDraft.model_validate_json(p.read_text(encoding="utf-8")))
        if content is None or not content.explainer_payloads:
            continue
        n_tests += 1
        res = await replay_payloads(content.explainer_payloads, llm=llm, model_id=s.model_id,
                                    profile=get_profile(content.pack.pack_id))
        for ln in res.lines:
            lines[line_key(fixture, int(r), ln.terminal_id)] = {
                "text_he": ln.text_he, "source": ln.source, "failed_rules": list(ln.failed_rules)}
            e_total += 1
            e_model += ln.source == "model"
        u = res.usage
        for k in totals:
            totals[k] += getattr(u, k)
        served.update(u.served_models)
        print(f"  {fixture} r{r}: {len(res.lines)} lines · {u.calls} calls")
    cost = cost_usd(Usage(input_tokens=totals["input_tokens"], output_tokens=totals["output_tokens"],
                          cached_input_tokens=totals["cached_input_tokens"] or None), s.price)
    out = {"model": s.model_id, "params": ARM_B_PARAMS, "n_tests": n_tests, "cost_usd": round(cost, 6),
           "cost_per_test": round(cost / n_tests, 6) if n_tests else 0.0,
           "cache_hit": (totals["cached_input_tokens"] / totals["input_tokens"]) if totals["input_tokens"] else 0.0,
           "usage": totals, "served_models": sorted(served), "e_pass": [e_model, e_total], "lines": lines}
    (run_dir / "arm_b.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"arm B: {n_tests} tests · ${cost:.4f} (${out['cost_per_test']:.4f}/test) · "
          f"E-pass {e_model}/{e_total} · served {sorted(served)}")


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1])))
