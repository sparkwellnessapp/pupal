"""
The explainer: one reasoning line per credit criterion, after pricing
(PR_grader_v6_options.md §7, S-2 as amended).

    explain_test(content, priced, materials, *, llm, model_id, profile,
                 timeout_s=EXPLAINER_TIMEOUT_S, record_payloads=False) -> ExplainResult

It EXPLAINS a grade; it never changes one. Its input is the priced test, so the text can
only describe a decision already made, and nothing it returns feeds the pricer.

  * ONE line per credit terminal of the WHOLE test, in plan order (`explanations`):
      a terminal SHE decided (override, or a typed amount — AM-G3)  → «הציון נקבע ידנית»,
                                                                       source teacher_override,
                                                                       and no call is made for it;
      a model line that passed E-1..E-5                              → source model;
      anything else (no call, a late or failed call, a failed rule)  → the deterministic
                                                                       fallback, source fallback,
                                                                       with the rules it failed.
  * One call per scope the verifier graded and that counts (D-6), all scopes in parallel,
    ALL bounded together by one `asyncio.wait_for(…, timeout_s)`. A scope finished before
    the wall keeps its lines; a late scope falls back — the test never fails (§7.2).
  * Exactly ONE app-level retry, on a transient TRANSPORT error only (the v5 vocabulary,
    `grader_v5.V5_TRANSIENT_EXCEPTIONS`, imported — and never on a permanent provider
    error: a billing 429 or a 4xx fails every call alike). Content and parse failures are
    NOT retried (CLAUDE.md §7): they fall back. Never stack a second retry layer: the
    caller's model comes from `build_chat_model`, whose SDK retries are already off.
  * Usage is summed over every request issued; the served model is the provider-reported
    one (`response_metadata["model"]`), and `model_fallback` flags a call served by
    another model ([AM-G18], `serves_requested`).

`replay.py` re-runs recorded payloads through the same engine (`run_scopes`).
Call infrastructure follows `agents/feedback/agent.py` (structured output with
include_raw, A-8 billing log) — prompts and outputs are NOT shared with it: student
feedback and her reasoning line have different readers (§7.8).
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.explainer.copy import MANUAL_HE
from app.agents.explainer.fallback import compose_reasoning_he
from app.agents.explainer.payload import (
    ExplainerInputError,
    ScopeExplainerInput,
    ScopeKey,
    ScopeMaterials,
    build_scope_input,
    called_scopes,
    credit_terminal_ids,
    payload_to_dict,
    teacher_decided,
)
from app.agents.explainer.prompt import (
    EXPLAINER_PROMPT_VERSION,
    ScopeExplanations,
    explainer_system_prompt,
    render_scope_message,
)
from app.agents.explainer.validators import LineVerdict, validate_scope
from app.agents.grader.prompt_cache import cache_write_tokens, supports_cache, system_message
from app.agents.grader.grader import (
    RETRY_BACKOFF_MAX,
    RETRY_BACKOFF_MIN,
    is_permanent_provider_error,
)
from app.agents.grader.grader_v5 import V5_TRANSIENT_EXCEPTIONS
from app.agents.grader.llm_factory import serves_requested
from app.schemas.graded_test_draft_v6 import DraftV6Content, ExplanationV6, UsageV6
from app.services.pricing_v6 import PricedTest
from app.services.provider_billing import log_billing_exhausted

logger = logging.getLogger(__name__)

__all__ = ["EXPLAINER_TIMEOUT_S", "EXPLAINER_PROMPT_VERSION", "ExplainResult",
           "ScopeRun", "explain_test", "run_scopes"]

# §7.2: all scopes of one test, bounded TOGETHER. No setting exists for it yet
# (config.py is not this module's to edit); the caller passes `timeout_s` to move it.
EXPLAINER_TIMEOUT_S = 30.0
EXPLAINER_TRANSPORT_ATTEMPTS = 2                 # one app-level retry, transient only


@dataclass
class ExplainResult:
    explanations: List[ExplanationV6]            # one per credit terminal, plan order
    usage: UsageV6
    payloads: List[Dict[str, Any]] = field(default_factory=list)   # record_payloads only
    telemetry: List[str] = field(default_factory=list)


@dataclass
class ScopeRun:
    """What the engine returns, ALIGNED with its inputs: `verdicts[i]` is input i's
    {real terminal id → verdict}, or None when that call produced nothing (late, failed
    in transport). Per input, never merged: a replay holds many students' copies of one
    scope, and their terminal ids coincide."""
    verdicts: List[Optional[Dict[str, LineVerdict]]]
    usage: UsageV6
    telemetry: List[str]
    timed_out: bool = False


# ═══════════════════════════════════════════════════════════════════════════
# the public entry point
# ═══════════════════════════════════════════════════════════════════════════

async def explain_test(content: DraftV6Content, priced: PricedTest,
                       materials: Mapping[ScopeKey, ScopeMaterials], *,
                       llm, model_id: str, profile,
                       timeout_s: float = EXPLAINER_TIMEOUT_S,
                       record_payloads: bool = False) -> ExplainResult:
    """Never raises on a model, transport, timeout or validation failure: those fall back
    per terminal. (A `priced` that does not belong to `content` is a caller bug and
    raises — the fallback composer could not price it either. A CancelledError from the
    caller propagates.)"""
    t0 = time.monotonic()
    telemetry: List[str] = []
    view = content.to_view()
    priced_terminals = {t.terminal_id: t for t in priced.terminals}

    inputs: List[ScopeExplainerInput] = []
    for key in called_scopes(content, priced):
        try:
            inp = build_scope_input(content, priced, materials, key)
        except ExplainerInputError as exc:
            # a wrong INPUT, not a model failure: this scope falls back, loudly (§3.5a)
            logger.error(f"explainer_input_error scope={_scope_name(key)}: {exc}")
            telemetry.append(f"scope={_scope_name(key)} input_error: {exc}")
            continue
        if inp is not None:
            inputs.append(inp)

    run = await run_scopes(inputs, llm=llm, model_id=model_id, profile=profile,
                           timeout_s=timeout_s)
    telemetry += run.telemetry
    by_terminal: Dict[str, LineVerdict] = {}
    for scope_verdicts in run.verdicts:          # one test: its scopes' terminals are distinct
        by_terminal.update(scope_verdicts or {})

    explanations: List[ExplanationV6] = []
    for tid in credit_terminal_ids(content):
        if teacher_decided(priced_terminals[tid]):
            explanations.append(ExplanationV6(terminal_id=tid, text_he=MANUAL_HE,
                                              source="teacher_override"))
            continue
        verdict = by_terminal.get(tid)
        if verdict is not None and verdict.passed:
            explanations.append(ExplanationV6(terminal_id=tid, text_he=verdict.text_he,
                                              source="model"))
            continue
        explanations.append(ExplanationV6(
            terminal_id=tid, text_he=compose_reasoning_he(priced, view, tid),
            source="fallback",
            failed_rules=list(verdict.failed_rules) if verdict is not None else []))

    _log_done(explanations, run, inputs, model_id, time.monotonic() - t0)
    return ExplainResult(
        explanations=explanations, usage=run.usage,
        payloads=[payload_to_dict(i) for i in inputs] if record_payloads else [],
        telemetry=telemetry)


# ═══════════════════════════════════════════════════════════════════════════
# the engine (shared with replay.py)
# ═══════════════════════════════════════════════════════════════════════════

async def run_scopes(inputs: Sequence[ScopeExplainerInput], *, llm, model_id: str, profile,
                     timeout_s: float) -> ScopeRun:
    """One call per input, all in parallel, all under ONE wall. A scope that does not
    finish (late, failed, unparseable) has no verdicts here — its terminals fall back."""
    usage = _UsageAcc(model_id)
    telemetry: List[str] = []
    verdicts: List[Optional[Dict[str, LineVerdict]]] = [None] * len(inputs)
    if not inputs:
        return ScopeRun(verdicts, usage.result(), telemetry)

    try:
        system = explainer_system_prompt(profile)
        cache = supports_cache(llm)                    # [CL-2] the system prompt is the cached prefix
        runner = llm.with_structured_output(ScopeExplanations, include_raw=True)
    except Exception as exc:                                       # noqa: BLE001
        logger.error(f"explainer_unavailable model={model_id} "
                     f"exc={type(exc).__name__}: {str(exc)[:200]}")
        telemetry.append(f"explainer_unavailable: {type(exc).__name__}")
        return ScopeRun(verdicts, usage.result(), telemetry)

    pending = set(range(len(inputs)))

    async def one(i: int, inp: ScopeExplainerInput) -> None:
        try:
            out = await _call_scope(inp, runner, system, model_id, usage, telemetry, cache)
        except Exception as exc:                                   # noqa: BLE001
            # per-scope isolation (§3.6): even a defect here costs one scope its lines
            logger.error(f"explainer_scope_error scope={inp.scope_id} "
                         f"exc={type(exc).__name__}: {str(exc)[:200]}")
            telemetry.append(f"scope={inp.scope_id} error: {type(exc).__name__}")
            out = None
        verdicts[i] = out
        pending.discard(i)

    timed_out = False
    try:
        await asyncio.wait_for(asyncio.gather(*(one(i, inp) for i, inp in enumerate(inputs))),
                               timeout=timeout_s)
    except asyncio.TimeoutError:
        timed_out = True
        late = sorted({inputs[i].scope_id for i in pending})
        logger.warning(f"explainer_timeout model={model_id} timeout_s={timeout_s} "
                       f"late_scopes={','.join(late)}")
        telemetry.append(f"timeout after {timeout_s}s: late scopes {', '.join(late)}")
    return ScopeRun(verdicts, usage.result(), telemetry, timed_out)


async def _call_scope(inp: ScopeExplainerInput, runner, system: str, model_id: str,
                      usage: "_UsageAcc", telemetry: List[str],
                      cache: bool = False) -> Optional[Dict[str, LineVerdict]]:
    """One scope: the call (one retry, transport only), then E-1..E-5. None when the call
    produced no lines at all for a transport reason; a parse failure is the model's
    content failure and is returned as E-1 on every terminal (no line came back)."""
    sid = inp.scope_id
    messages = [system_message(system, cache), HumanMessage(content=render_scope_message(inp))]
    res: Any = None
    for attempt in range(1, EXPLAINER_TRANSPORT_ATTEMPTS + 1):
        usage.calls += 1
        try:
            res = await runner.ainvoke(messages)
            break
        except Exception as exc:                                   # noqa: BLE001
            log_billing_exhausted(exc, site="explainer", model=model_id)
            transient = (isinstance(exc, V5_TRANSIENT_EXCEPTIONS)
                         and not is_permanent_provider_error(exc))
            if transient and attempt < EXPLAINER_TRANSPORT_ATTEMPTS:
                logger.warning(f"explainer_scope_retry scope={sid} kind=transient "
                               f"exc={type(exc).__name__}: {str(exc)[:200]}")
                await asyncio.sleep(_retry_backoff_s())
                continue
            kind = "transient" if transient else (
                "permanent" if is_permanent_provider_error(exc) else "content")
            logger.warning(f"explainer_scope_failed scope={sid} kind={kind} attempts={attempt} "
                           f"exc={type(exc).__name__}: {str(exc)[:200]}")
            telemetry.append(f"scope={sid} call_failed kind={kind}: {type(exc).__name__}")
            return None

    parsed, raw, parsing_error = _unpack(res)
    usage.add(raw)
    if parsed is None:
        # the provider answered, the output did not parse: a CONTENT failure — not retried
        logger.warning(f"explainer_parse_failed scope={sid} model={model_id}: "
                       f"{str(parsing_error)[:200]}")
        telemetry.append(f"scope={sid} parse_failed")
        return {t.terminal_id: LineVerdict(t.terminal_id, None, ("E-1",)) for t in inp.terminals}

    checked = validate_scope([(ln.terminal_id, ln.text_he) for ln in parsed.lines], inp)
    telemetry.extend(checked.telemetry)
    for v in checked.verdicts.values():
        if not v.passed:
            telemetry.append(f"scope={sid} terminal={v.terminal_id} "
                             f"failed={','.join(v.failed_rules)}")
    return checked.verdicts


def _unpack(res: Any) -> Tuple[Optional[ScopeExplanations], Any, Any]:
    """`with_structured_output(include_raw=True)` → {"raw", "parsed", "parsing_error"}."""
    if isinstance(res, ScopeExplanations):
        return res, None, None
    if not isinstance(res, dict):
        return None, None, f"unexpected result {type(res).__name__}"
    raw, parsed, err = res.get("raw"), res.get("parsed"), res.get("parsing_error")
    if err is not None:
        return None, raw, err
    if isinstance(parsed, dict):
        try:
            parsed = ScopeExplanations.model_validate(parsed)
        except Exception as exc:                                   # noqa: BLE001
            return None, raw, exc
    if not isinstance(parsed, ScopeExplanations):
        return None, raw, f"no parsed {ScopeExplanations.__name__}"
    return parsed, raw, None


def _retry_backoff_s() -> float:
    """Jitter before the one transport retry (the v5 window); a function, so a test
    can make it zero."""
    return random.uniform(RETRY_BACKOFF_MIN, RETRY_BACKOFF_MAX)


class _UsageAcc:
    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cached_input_tokens = 0
        self.cache_write_input_tokens = 0
        self.served: List[str] = []

    def add(self, raw: Any) -> None:
        if raw is None:
            return
        meta = dict(getattr(raw, "usage_metadata", None) or {})
        self.input_tokens += int(meta.get("input_tokens") or 0)
        self.output_tokens += int(meta.get("output_tokens") or 0)
        self.cached_input_tokens += int(
            (meta.get("input_token_details") or {}).get("cache_read") or 0)
        self.cache_write_input_tokens += cache_write_tokens(meta)
        rmeta = dict(getattr(raw, "response_metadata", None) or {})
        served = rmeta.get("model") or rmeta.get("model_name")
        if served and str(served) not in self.served:
            self.served.append(str(served))

    def result(self) -> UsageV6:
        return UsageV6(model=self.model_id, calls=self.calls, input_tokens=self.input_tokens,
                       output_tokens=self.output_tokens,
                       cached_input_tokens=self.cached_input_tokens,
                       cache_write_input_tokens=self.cache_write_input_tokens,
                       served_models=sorted(self.served),
                       model_fallback=any(not serves_requested(self.model_id, s)
                                          for s in self.served))


# ═══════════════════════════════════════════════════════════════════════════
# the one log line per test (§8: everything to query is IN the message string)
# ═══════════════════════════════════════════════════════════════════════════

def _log_done(explanations: List[ExplanationV6], run: ScopeRun,
              inputs: Sequence[ScopeExplainerInput], model_id: str, elapsed_s: float) -> None:
    sources = Counter(e.source for e in explanations)
    rules = Counter(r for e in explanations for r in e.failed_rules)
    failed = ",".join(f"{r}:{rules[r]}" for r in sorted(rules)) or "none"
    logger.info(
        f"explainer_done lines={len(explanations)} model={sources.get('model', 0)} "
        f"fallback={sources.get('fallback', 0)} teacher={sources.get('teacher_override', 0)} "
        f"failed_rules={failed} scopes={len(inputs)} calls={run.usage.calls} "
        f"timeout={run.timed_out} model_id={model_id} "
        f"served={','.join(run.usage.served_models) or 'unreported'} "
        f"model_fallback={run.usage.model_fallback} "
        f"in_tok={run.usage.input_tokens} out_tok={run.usage.output_tokens} "
        f"cached_tok={run.usage.cached_input_tokens} elapsed_ms={int(elapsed_s * 1000)}")


def _scope_name(key: ScopeKey) -> str:
    return key[0] if key[1] is None else f"{key[0]}.{key[1]}"
