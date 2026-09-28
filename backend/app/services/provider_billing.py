"""
Provider billing exhaustion — owner ruling A-8 (Billing visibility).

«A provider error meaning "out of credits" (e.g. Anthropic's "credit balance is
too low") is logged at CRITICAL with the structured tag
PROVIDER_BILLING_EXHAUSTED, in the grading runner, the plan builder and the
feedback call. The teacher-facing failure copy is unchanged. The owner's GCP
log-based alert on the tag is already live.»

WHY THIS EXISTS. On 2026-09-27 an Anthropic call failed with a 400 whose body
said «Your credit balance is too low». Every one of the three paths that talk to
a model is built to SURVIVE a provider failure — the grader turns it into a
flagged zero-outcome per scope (§3.6), the plan builder degrades the wording to
the compiler's placeholder (W-2), the feedback call lands the draft with
`feedback=None` — and that resilience is exactly what makes an empty account
invisible: nothing crashes, the logs carry a WARNING/ERROR among many, and the
product quietly stops grading. An empty account is not a blip; it is the one
failure that fails every call for everyone until a human pays.

WHAT THIS MODULE DOES — AND DOES NOT. It recognises the fact and says it out
loud, once. It changes NO behaviour: flags, statuses, degradation, retries,
return values and the teacher's copy stay exactly as they were. Callers add a
log line, nothing else.

THE TAG IS AT THE START OF THE MESSAGE STRING. `logger.*(..., extra={...})`
fields are never rendered in this service (CLAUDE.md §8 — the formatter is the
bare `%(message)s`), so the alert can only key on text in the message. The line
carries ids only, never a student name or a filename (OD-B4), and never the
provider's error body — the class name is enough to find the row, and the body
can echo request content.

PRECISION. A plain 429 rate limit, a timeout, a 5xx or a parse failure is NOT
billing — a false positive here pages a human at night for traffic that heals
itself. Each provider names the condition its own way, so each is matched by the
provider's own vocabulary:

  * Anthropic — «credit balance is too low» (a 400 `invalid_request_error`: the
    type alone cannot tell it from any other bad request), and the documented
    402 `billing_error` type.
  * OpenAI — the `insufficient_quota` code (a 429 that is NOT rate pressure; the
    SDKs cannot discriminate it), `billing_not_active`,
    `billing_hard_limit_reached`, and the «exceeded your current quota» wording
    ONLY on an `openai.*` exception — Gemini's AI-Studio per-minute 429 uses the
    identical sentence for plain quota pressure.
  * Google / Gemini — the `BILLING_DISABLED` reason, or «billing» together with
    «not enabled» / «disabled» / «to be enabled» wording.
"""
from __future__ import annotations

import logging
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)

PROVIDER_BILLING_EXHAUSTED = "PROVIDER_BILLING_EXHAUSTED"

# A chain longer than this is a loop or a pathology, not an error to read.
_MAX_LINKS = 16
# Bounded per text source: provider bodies can be long, the phrases are early.
_MAX_TEXT = 4000

_ANTHROPIC_MARKERS = ("credit balance is too low", "billing_error")
_OPENAI_MARKERS = ("insufficient_quota", "billing_not_active",
                   "billing_hard_limit_reached")
_OPENAI_ONLY_MARKER = "exceeded your current quota"
_GOOGLE_REASON = "billing_disabled"
_GOOGLE_BILLING_WORDING = ("not enabled", "disabled", "to be enabled")


def _chain(exc: BaseException) -> Iterator[BaseException]:
    """Every exception reachable from `exc`, outermost first.

    Follows `__cause__` / `__context__` (an SDK error re-raised under a
    LangChain or application exception), exception groups' `.exceptions`, and a
    tenacity `RetryError`'s last attempt (LangChain's `with_retry` substrate).
    Cycle-safe and bounded."""
    queue = [exc]
    seen: set = set()
    while queue and len(seen) < _MAX_LINKS:
        link = queue.pop(0)
        if not isinstance(link, BaseException) or id(link) in seen:
            continue
        seen.add(id(link))
        yield link
        queue.extend((link.__cause__, link.__context__))
        group = getattr(link, "exceptions", None)
        if isinstance(group, (list, tuple)):
            queue.extend(group)
        last = getattr(link, "last_attempt", None)
        if last is not None and callable(getattr(last, "exception", None)):
            try:
                queue.append(last.exception())
            except BaseException:                  # noqa: BLE001 — a Future's own state
                pass


def _texts(link: BaseException) -> str:
    """The lowercase haystack for one link: its message plus the structured
    fields the SDKs carry the provider's words in (`code`/`type` on OpenAI and
    Anthropic, `status`/`details` on google-genai, `body` on both SDKs, and an
    httpx response's text when the wrapper is a bare `HTTPStatusError`)."""
    parts = [type(link).__name__]
    try:
        parts.append(str(link)[:_MAX_TEXT])
    except Exception:                               # noqa: BLE001
        pass
    for attr in ("code", "type", "status", "message", "body", "details"):
        try:
            value = getattr(link, attr, None)
        except Exception:                           # noqa: BLE001 — a raising property
            continue
        if value is not None and not callable(value):
            parts.append(repr(value)[:_MAX_TEXT])
    try:
        import httpx
        response = getattr(link, "response", None)
        if isinstance(response, httpx.Response):
            parts.append(response.text[:_MAX_TEXT])
    except Exception:                               # noqa: BLE001 — an unread stream
        pass
    return " ".join(parts).lower()


def _is_openai_exception(link: BaseException) -> bool:
    return type(link).__module__.split(".")[0] == "openai"


def _link_is_billing(link: BaseException) -> bool:
    hay = _texts(link)
    if any(m in hay for m in _ANTHROPIC_MARKERS):
        return True
    if any(m in hay for m in _OPENAI_MARKERS):
        return True
    if _OPENAI_ONLY_MARKER in hay and _is_openai_exception(link):
        return True
    if _GOOGLE_REASON in hay:
        return True
    return "billing" in hay and any(w in hay for w in _GOOGLE_BILLING_WORDING)


def _billing_link(exc: Any) -> Optional[BaseException]:
    if not isinstance(exc, BaseException):
        return None
    for link in _chain(exc):
        if _link_is_billing(link):
            return link
    return None


def is_billing_exhausted(exc: Any) -> bool:
    """True when `exc` — or anything in its chain — is a provider saying the
    account is out of credit / has no billing. Anything that is not an
    exception (None, a test double) is simply False."""
    try:
        return _billing_link(exc) is not None
    except Exception:                               # noqa: BLE001 — never a new failure
        return False


def first_billing_exhausted(seen: Optional[BaseException],
                            exc: Any) -> Optional[BaseException]:
    """Keep the FIRST billing exception of a run. For fan-out callers (the
    grader's per-scope gather): every scope of a test fails the same way, and
    the alert must fire once per graded test, not once per scope."""
    if seen is not None:
        return seen
    return exc if is_billing_exhausted(exc) else None


def _provider_of(link: BaseException) -> str:
    root = type(link).__module__.split(".")[0]
    if root in ("anthropic", "langchain_anthropic"):
        return "anthropic"
    if root in ("openai", "langchain_openai"):
        return "openai"
    if root == "google":
        return "gemini"
    return "unknown"


def log_billing_exhausted(exc: Any, *, site: str, model: Optional[str] = None,
                          **ids: Any) -> bool:
    """If `exc` is a billing exhaustion, log ONE CRITICAL line and return True;
    otherwise log nothing and return False. Never raises — this is a log line
    riding on a failure path, and it must not become the failure.

        PROVIDER_BILLING_EXHAUSTED site=grading graded_test_id=… provider=anthropic model=claude-sonnet-5: BadRequestError

    `ids` are rendered in the order given, as `key=value`. Pass ids only
    (graded_test_id, plan_id, rubric_id, a stage name) — never a student's name
    or a filename (OD-B4)."""
    try:
        link = _billing_link(exc)
        if link is None:
            return False
        fields = " ".join(f"{k}={v}" for k, v in ids.items())
        logger.critical(
            f"{PROVIDER_BILLING_EXHAUSTED} site={site}"
            + (f" {fields}" if fields else "")
            + f" provider={_provider_of(link)} model={model or 'unknown'}: "
            f"{type(link).__name__}")
        return True
    except Exception:                               # noqa: BLE001
        return False
