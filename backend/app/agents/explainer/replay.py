"""
§13.4 arm B — the explainer on RECORDED payloads (PR_grader_v6_options.md §13.4).

    replay_payloads(payloads, *, llm, model_id, profile, timeout_s) -> ReplayResult

Re-runs the SAME scope payloads a grading run recorded (`explain_test(...,
record_payloads=True)` → `payload_to_dict`) on another model: same prompt, same
message, same E-1..E-5 — so arms differ only by the model. Zero verifier spend and no
pricer: each payload carries everything the call and the validators read (E-4's allowed
numbers are a pure function of it), and each terminal's deterministic fallback line
(`fallback_he`), recorded at grading time.

Teacher-decided terminals were never in a payload, so a replay covers exactly the
terminals the explainer is called for. The engine is `explainer.run_scopes` — one call
per payload, all bounded together by `timeout_s`, one transport retry — exactly the
grading-time behaviour.
"""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from app.agents.explainer.explainer import EXPLAINER_TIMEOUT_S, run_scopes
from app.agents.explainer.payload import payload_from_dict
from app.schemas.graded_test_draft_v6 import UsageV6

logger = logging.getLogger(__name__)

__all__ = ["ReplayLine", "ReplayResult", "replay_payloads"]


@dataclass(frozen=True)
class ReplayLine:
    question_id: str
    sub_question_id: Optional[str]
    terminal_id: str                                 # the real id
    text_he: str
    source: str                                      # "model" | "fallback"
    failed_rules: Tuple[str, ...] = ()


@dataclass
class ReplayResult:
    lines: List[ReplayLine]                          # payload order, then terminal order
    usage: UsageV6
    telemetry: List[str] = field(default_factory=list)


async def replay_payloads(payloads: Sequence[Mapping[str, Any]], *, llm, model_id: str,
                          profile, timeout_s: float = EXPLAINER_TIMEOUT_S) -> ReplayResult:
    inputs = [payload_from_dict(p) for p in payloads]
    run = await run_scopes(inputs, llm=llm, model_id=model_id, profile=profile,
                           timeout_s=timeout_s)
    lines: List[ReplayLine] = []
    for inp, scope_verdicts in zip(inputs, run.verdicts):
        for t in inp.terminals:
            v = (scope_verdicts or {}).get(t.terminal_id)
            if v is not None and v.passed:
                lines.append(ReplayLine(inp.question_id, inp.sub_question_id, t.terminal_id,
                                        v.text_he, "model"))
            else:
                lines.append(ReplayLine(inp.question_id, inp.sub_question_id, t.terminal_id,
                                        t.fallback_he, "fallback",
                                        v.failed_rules if v is not None else ()))
    rules = Counter(r for ln in lines for r in ln.failed_rules)
    logger.info(
        f"explainer_replay_done payloads={len(inputs)} lines={len(lines)} "
        f"model={sum(ln.source == 'model' for ln in lines)} "
        f"fallback={sum(ln.source == 'fallback' for ln in lines)} "
        f"failed_rules={','.join(f'{r}:{rules[r]}' for r in sorted(rules)) or 'none'} "
        f"calls={run.usage.calls} timeout={run.timed_out} model_id={model_id} "
        f"served={','.join(run.usage.served_models) or 'unreported'} "
        f"model_fallback={run.usage.model_fallback}")
    return ReplayResult(lines=lines, usage=run.usage, telemetry=list(run.telemetry))
