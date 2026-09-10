"""
pipeline.py — the two-phase pipeline, as a config-parameterized factory.
v0 is a config; every later layer is a config diff, never a code branch.

Phase 1: pages are chunked per `p1_pages_per_call` (lean default: 3) and packed
either as separate images in one call (`multi_image`, resolution-preserving) or
vertically stitched into one tall PNG (`stitched`, fewer images, downscale
risk). Chunks run concurrently through the shared scheduler under the
document's priority. Output is per-page text regardless of packing.

Phase 2: ONE text-only call per document — all pages + the exam spec.

Parse policy (D2): each call's text goes through the one defensive parser; on
failure, ONE re-request of the same call; on second failure, a degraded empty
result is returned and recorded (parse_ok=False) — per-unit failure isolation,
never a thrown document.

Model resolution is injected: callers supply `resolve_model(key) -> ResolvedModel`
(the eval suite passes its registry's `spec`; production passes a settings-owned
map). The pipeline never knows about prices/tiers beyond the returned card.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import base64
import io
import logging
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Protocol

from PIL import Image

from ..budget import Budget
from ..scheduler import ProviderScheduler
from ..vlm_provider import VLMProvider, VLMResponse

from .corrector import Correction, correct_text
from .instrument import CallRecord, PriceCard, StageTimer, Trace, cost_usd
from .keys import Key, normalize_key
from .parsing import ExamSpec, parse_model_json
from .prompts import (
    P1_SCHEMA,
    P2_SCHEMA,
    P2_SPAN_SYSTEM,
    TRANSCRIPTION_PROMPT_VERSION,
    P1_SYSTEM,
    p1_system,
    p1_user_prompt,
    p2_span_system,
    p2_span_user_prompt,
    p2_system_prompt,
    p2_user_prompt,
)
from app.subjects import get_profile as _get_subject_profile
from app.subjects import prompt_version as _stamp_prompt_version

log = logging.getLogger("transcription.two_phase")

# Finish reasons that mean "output was truncated at the token cap" — provider-
# agnostic (Gemini "MAX_TOKENS", OpenAI "length", Anthropic "max_tokens").
# A truncation is DETERMINISTIC: re-requesting the identical call truncates
# again, so the parse re-request is skipped for these (raise max_tokens instead).
_TRUNCATION_FINISH_REASONS = {"MAX_TOKENS", "LENGTH"}


class ResolvedModel(Protocol):
    """What the pipeline needs to know about a model key. Structural — the eval
    suite's ModelSpec satisfies it as-is."""
    key: str
    provider: str          # scheduler/adapter name: openai | anthropic | gemini
    model_id: str
    price: PriceCard
    supports_json_schema: bool


ResolveModel = Callable[[str], ResolvedModel]


@dataclass(frozen=True)
class AliasedModel:
    """A ResolvedModel whose provider name is the model KEY itself.

    Provider adapters pin their model_id at construction, so when a config
    names TWO models of the same vendor (e.g. gemini-pro baseline + flash-lite
    reader) they need two adapter instances. Registering each instance under
    its model key — and resolving through `alias()` — keeps the pipeline's
    one-lookup semantics while guaranteeing every call reaches the adapter
    built for exactly that model (a vendor-keyed dict silently last-write-wins)."""
    key: str
    provider: str
    model_id: str
    price: PriceCard
    supports_json_schema: bool = True


def alias(spec: ResolvedModel) -> AliasedModel:
    return AliasedModel(
        key=spec.key, provider=spec.key, model_id=spec.model_id,
        price=spec.price, supports_json_schema=spec.supports_json_schema,
    )


@dataclass(frozen=True)
class PipelineConfig:
    # Phase 1 (perception)
    p1_model_key: str
    p1_pages_per_call: int = 3            # lean default per design note
    p1_image_packing: str = "multi_image"  # multi_image | stitched
    dpi: int = 200
    image_max_px: int = 2000              # longest-edge resize, no enhancement in v0
    p1_max_tokens: int = 4000             # scaled by pages-per-call at call time
    # Post-P1 crossed-out-ink verification pass (strike_check.py); empty =
    # disabled. One cheap single-image call per nonempty page asks which
    # already-transcribed lines are struck through; a deterministic post-pass
    # DELETES flagged lines (never edits). Fail-safe: checker failure keeps
    # the page unchanged. P1 itself is untouched (its strike-prompt surface is
    # exhausted — t1.3/t1.3b kill, prompts.py note).
    p1_strike_check_model_key: str = ""
    p1_strike_check_max_tokens: int = 4000
    # Discard checker ranges spanning fewer lines than this (sc1.2 guard):
    # the observed false-positive class is single kept lines with an inline
    # scribbled-out word; the leak class is multi-line blocks. 1 disables.
    p1_strike_check_min_block_lines: int = 2
    # Concurrent checker calls per page; deletions are the UNION of the votes'
    # (guard-filtered) ranges. Single-call block recall measured ~0.8-0.9
    # (sc1.1: 4/4, sc1.0: 1/2) — union-of-2 squares the miss rate for
    # +~$0.003/doc and no added wall time. False-union risk is bounded: no
    # false >=2-line range has fired in any live run; the guard applies per
    # range regardless of vote count.
    p1_strike_check_votes: int = 1
    # Longest-edge resize for the CHECKER's image only; 0 = reuse image_max_px.
    # Strike marks are coarse, page-scale features (long diagonals across a
    # block), so the checker does not need P1's character-level resolution —
    # and the checker's cost is almost entirely image input tokens. Halving
    # the edge quarters those tokens.
    p1_strike_check_image_max_px: int = 0
    # Trust layer (cross-reader disagreement flags); empty = disabled
    reader_model_keys: tuple[str, ...] = ()
    reader_image_max_px: int = 2000       # readers may run cheaper/smaller images
    reader_max_tokens: int = 0            # per-page reader output cap; 0 = p1_max_tokens
    #   (haiku/4o-mini emit more tokens per page than gemini and were observed
    #   truncating on dense 3-page chunks; a truncated reader casts no votes)
    # Phase 2 (interpretation)
    p2_model_key: str = ""                # empty => Phase 2 disabled (p1_only runs)
    correction_policy: str = "off"        # off | impossible | spec  (deterministic post-pass)
    p2_max_tokens: int = 8000
    # OpenAI reasoning-effort for the P2 call ("minimal"|"low"|"medium"|"high");
    # empty = provider default. Caps hidden reasoning tokens, which spend the
    # max_completion_tokens budget BEFORE the visible answer (the P2 'length'
    # truncation mode). Non-OpenAI P2 providers accept and ignore it.
    p2_reasoning_effort: str = ""
    # P2 output contract: "text" (legacy generative — model re-emits answer
    # text) | "spans" (2026-08-11 redesign — model references numbered input
    # lines; the harness slices text verbatim; see spans.py). "text" is the
    # revert path while spans is under evaluation.
    p2_output_contract: str = "text"
    # Wire encoding for page images. "png" (default, historical) | "jpeg".
    # Providers sniff the mime from the bytes, so this needs no adapter change.
    image_format: str = "png"
    image_jpeg_quality: int = 90
    # Shared
    temperature: float = 0.0
    use_json_schema: bool = True          # the L3 experiment is this single flip
    # THE ESSENTIAL-CALL timeout (P1, P2). 240s in PROD_CONFIG, and that number
    # was earned by measurement on real congested uplinks: P1 pushes multi-MB
    # image payloads and a SLOWLY-SUCCEEDING upload must not be killed.
    timeout_s: float = 90.0
    # THE OPTIONAL-PASS timeout (strike check, readers) -- owner-ruled 40s,
    # 2026-09-10. These passes are NOT what `timeout_s` was calibrated for: the
    # strike check sends one page image to a cheap fast model and answers in
    # ~7.8s median, so inheriting P1's 240s gave it a ceiling ~30x its median
    # and, with the scheduler's one transport retry, a worst case of ~481s --
    # which is exactly what it spent on the incident that produced this field.
    # Retry policy is unchanged (the scheduler already retries exactly once), so
    # the worst case here is ~40 + backoff + 40 = ~82s.
    optional_pass_timeout_s: float = 40.0
    # THE OPTIONAL-PASS PHASE BELT (owner-ruled 120s). `_call_and_parse`'s parse
    # re-request still wraps the scheduler's transport retry, so ONE page's true
    # worst case is 2 x ~82s = ~164s. This belt is what bounds that residual
    # multiplication rather than leaving it to argument -- and it generalises the
    # policy `identity.py` already had (CALL_TIMEOUT_S + TOTAL_TIMEOUT_S, its
    # «belt over everything»), which is the only one of the three optional passes
    # that got it right. Expiry degrades to the pass's OWN defined failure
    # behaviour: keep the text / cast no votes.
    optional_pass_budget_s: float = 120.0
    # Subject seam (2026-09-08): the SUBJECT PROFILE key. Selects the P1 fragment
    # (modality only — P1 stays spec-blind) and the D-16 prompt stamp. The default
    # is the baseline, so every existing config/fixture is byte-identical.
    subject_key: str = "computer_science"


@dataclass(frozen=True)
class SpecMismatch:
    key: Key
    original: str
    suggested: str
    reason: str


@dataclass
class PipelineRun:
    pages: dict[int, str]                       # raw Phase-1 output (verbatim)
    answers: dict[Key, str]                     # raw Phase-2 segmentation (verbatim)
    spec_mismatches: tuple[SpecMismatch, ...]   # retained shape; populated from corrections
    routing_notes: tuple[str, ...]
    trace: Trace
    corrected_pages: dict[int, str] = field(default_factory=dict)
    corrected_answers: dict[Key, str] = field(default_factory=dict)
    corrections: tuple[Correction, ...] = ()
    prompt_version: str = TRANSCRIPTION_PROMPT_VERSION


# --- image preparation (pure-ish; PIL only) --------------------------------------

def _resize(img: Image.Image, max_px: int) -> Image.Image:
    w, h = img.size
    longest = max(w, h)
    if longest <= max_px:
        return img
    scale = max_px / longest
    return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)


def _to_b64_png(img: Image.Image) -> str:
    """PNG encode. Retained as the name several call sites/tests know."""
    return _to_b64_image(img, "png")


def _to_b64_image(img: Image.Image, fmt: str = "png", jpeg_quality: int = 90) -> str:
    """Encode a page image for the wire.

    PNG is the worst available choice for the photographic scans this pipeline
    actually receives: measured on a 6-page doc it costs 1269ms to encode and
    12.65MB of upload, against 92ms / 3.08MB for JPEG q90 — and since the
    strike-check pass every page is uploaded TWICE. Providers derive the mime
    type from these bytes (vlm_provider.image_mime_for), so the format is a
    pipeline decision no adapter has to be told about."""
    buf = io.BytesIO()
    rgb = img.convert("RGB")
    if fmt.lower() in ("jpeg", "jpg"):
        rgb.save(buf, format="JPEG", quality=jpeg_quality)
    else:
        rgb.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


#: [Stage C1] A DEDICATED pool for page encoding — never the default executor.
#:
#: `run_in_executor(None, …)` uses the process-wide default pool, which is
#: `min(32, os.cpu_count() + 4)` — **5 threads at cpu=1000m**. `asyncio.to_thread`
#: resolves to that same pool, and this codebase pushes genuinely long blocking
#: work through it: `docx_v3/pipeline.py` runs a `.invoke` bounded at
#: EXTRACTION_LLM_TIMEOUT_S (default 360s, twice), and `rubric_service` several
#: more. An instance serving containerConcurrency=4 can therefore have every
#: default-pool thread parked in a multi-minute LLM call while a transcription's
#: page encodes sit in an unbounded, untimed FIFO behind them — a latency
#: regression in exactly the dimension C1 exists to improve, and one that would
#: read as slow model calls in the stage timings rather than as queueing.
#:
#: TWO, not more, and the smaller number is the deliberate one:
#:   * `Pipeline._encode_lock` already bounds each DOCUMENT to one encode at a
#:     time, so this only bounds how many documents encode at once.
#:   * Encoding is not the bottleneck — a 3-page chunk encodes in ~1s against
#:     model calls of 20–60s — so more threads buy nothing measurable.
#:   * Memory is the binding constraint on this box. `--concurrency` was cut
#:     5→4 on 2026-08-23 from a measurement (≈260 MB/doc + ≈480 MB fixed,
#:     C=4 = 74% of 2Gi) taken when the event loop serialized every encode in
#:     the PROCESS. Concurrent encodes are new transient (~25 MB of resized
#:     pages plus a buffer and its 1.33× base64, per thread), so the headroom
#:     that fixed C=4 is stale. Two threads keeps that addition small; raising
#:     it is a decision for the C2 memory re-measure, not a default.
_ENCODE_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="page-encode")


def _encode_pages_sync(
    images: list[Image.Image], max_px: int, fmt: str, jpeg_quality: int,
    stitch: bool = False,
) -> list[str]:
    # NOTE: `stitch` is deliberately POSITIONAL, not keyword-only.
    # `loop.run_in_executor` can only forward positional arguments, and a
    # keyword-only parameter here raises TypeError on every single call — at
    # runtime, inside the executor, on a path no unit test of the pure encoder
    # would ever exercise. Do not "tidy" it behind a `*`.
    """Resize + encode + base64 a chunk of pages. PURE and SYNCHRONOUS.

    [Stage C1, UPLOAD_LATENCY_PLAN.md] Extracted so the callers can hand it to a
    thread. It is byte-for-byte what the inline code did — same functions, same
    order, same arguments — because the whole point is that NOTHING the model
    receives changes (ruling R1). Pinned by a byte-identity test.

    WHY IT MATTERS: this is real CPU on the request thread. PNG measured 1269ms
    for a 6-page document, and since the strike-check pass every page is encoded
    TWICE. Cloud Run runs this service at cpu=1000m with containerConcurrency=4,
    so four concurrent transcription requests were spending that time on the
    event loop — starving the interactive uploads sharing the same instance
    (measured: appends 0.43s -> 5.3, 5.9, 15.6s when they overlapped a
    transcription on the same instanceId). Pillow releases the GIL inside its
    resize and encode loops, so moving this to a thread is real relief even on
    one core.
    """
    resized = [_resize(img, max_px) for img in images]
    if stitch and len(resized) > 1:
        return [_to_b64_image(_stitch(resized), fmt, jpeg_quality)]
    return [_to_b64_image(img, fmt, jpeg_quality) for img in resized]


def _stitch(images: list[Image.Image], gap_px: int = 24) -> Image.Image:
    width = max(i.width for i in images)
    height = sum(i.height for i in images) + gap_px * (len(images) - 1)
    canvas = Image.new("RGB", (width, height), "white")
    y = 0
    for img in images:
        canvas.paste(img.convert("RGB"), (0, y))
        y += img.height + gap_px
    return canvas


def _chunk(seq: list[int], size: int) -> list[list[int]]:
    return [seq[i:i + size] for i in range(0, len(seq), size)]


# --- the pipeline -----------------------------------------------------------------

PdfRenderer = Callable[[bytes, int], list[Image.Image]]

#: Runway an ESSENTIAL phase (P1, P2) needs before it is worth beginning.
#:
#: A MARGIN, not a worst case — and the difference matters. Demanding a full
#: `timeout_s` (240s) of runway would refuse to start a P1 that had 239s left
#: and needed 40, killing documents that were going to succeed. PR-2 already
#: settled this shape for extraction: it gates its phases on T+10 / T+60
#: margins and lets the remaining budget become the call's own timeout, so the
#: deadline stops work that CANNOT finish rather than work that MIGHT not.
#: The clamp does the rest — a phase starting with 30s left gets a 30s call.
_ESSENTIAL_MIN_RUNWAY_S = 30.0


def _default_renderer(pdf_bytes: bytes, dpi: int) -> list[Image.Image]:
    # Lazy import: reuse the production renderer; the pipeline stays decoupled
    # from document_parser until actually running on a PDF.
    from ...document_parser import pdf_to_images  # type: ignore
    return pdf_to_images(pdf_bytes, dpi)


class Pipeline:
    def __init__(
        self,
        cfg: PipelineConfig,
        providers: dict[str, VLMProvider],   # provider name -> instance
        scheduler: ProviderScheduler,
        *,
        resolve_model: ResolveModel,
        pdf_renderer: PdfRenderer = _default_renderer,
        budget: Budget | None = None,
    ):
        self.cfg = cfg
        self._providers = providers
        self._sched = scheduler
        self._resolve = resolve_model
        self._render = pdf_renderer
        # The document's wall budget (budget.py). DEFAULT UNBOUNDED, and that
        # default IS the eval path: the suite measures model behaviour, not
        # Cloud Run's request timeout, so `check_goal.sh` is untouched by
        # construction (PR-2's seam, `deadline_seconds=None`). Production passes
        # a real one down from the job runner, clocked at the CAS claim.
        self._budget = budget or Budget(None)
        # [Stage C1] Serializes this DOCUMENT's page encodes.
        #
        # Moving the encode into a thread also made it AWAIT, and the chunks run
        # under one `asyncio.gather` — so without this the chunk whose encode
        # finished first dispatched first, and a 5-page/3-per-call document
        # reliably issued its 2-page call BEFORE its 3-page one (measured: 8/8
        # trials reversed). Nothing about the model's input changes, and the
        # merge is by page number, so the transcription is identical either
        # way — but the plan's bar is "same behaviour, different thread", and a
        # dispatch order that flips is not that.
        #
        # It costs nothing: before C1 the encodes were ALREADY serial, because
        # they ran inline on the event loop with no await between them. The lock
        # reproduces exactly that sequence while leaving the loop free to serve
        # other documents' requests — which is the entire point of C1.
        #
        # Per-INSTANCE, and a Pipeline is built per document
        # (`two_phase_engine._build_pipeline_multi`), so this never serializes
        # one teacher's batch against another's.
        self._encode_lock = asyncio.Lock()

    # -- internals --

    async def _call_parsed(
        self,
        *,
        phase: str,
        model_key: str,
        doc_priority: int,
        trace: Trace,
        required_keys: tuple[str, ...],
        make_call: Callable[[], Awaitable[VLMResponse]],
        label: str = "",
    ) -> tuple[bool, dict]:
        """Scheduler-submitted call + defensive parse + ONE parse re-request.

        The re-request recovers from a malformed/transient bad output, but is
        skipped on a token-cap truncation (deterministic — see
        ``_TRUNCATION_FINISH_REASONS``)."""
        ms = self._resolve(model_key)
        provider_name = ms.provider
        tag = label or phase
        ok, data = False, {}
        for attempt in (1, 2):
            log.info("[%s] %s: submitting to %s (parse-attempt %d/2)",
                     trace.doc_id, tag, provider_name, attempt)
            res = await self._sched.submit(
                provider_name, doc_priority, make_call, doc_id=trace.doc_id)
            log.info("[%s] %s: provider returned in %.0fms "
                     "(queue_wait=%.0fms, call-attempts=%d)",
                     trace.doc_id, tag, res.response.total_ms,
                     res.queue_wait_ms, res.attempts)
            ok, data = parse_model_json(res.response.text, required_keys=required_keys)
            log.info("[%s] %s: parse ok=%s%s", trace.doc_id, tag, ok,
                     "" if ok else f" (finish_reason={res.response.raw_finish_reason})")
            trace.calls.append(CallRecord(
                phase=phase,
                provider=provider_name,
                model_key=model_key,
                usage=res.response.usage,
                total_ms=res.response.total_ms,
                queue_wait_ms=res.queue_wait_ms,
                attempts=res.attempts,
                parse_ok=ok,
                cost_usd=cost_usd(res.response.usage, ms.price),
                finish_reason=res.response.raw_finish_reason,
            ))
            if ok:
                break
            finish = (res.response.raw_finish_reason or "").upper()
            if finish in _TRUNCATION_FINISH_REASONS and phase != "p2":
                # P1/reader truncation is DETERMINISTIC (verbatim output length
                # is fixed by the ink) — re-requesting reproduces it; raise
                # max_tokens instead. P2 (a reasoning model) is NOT: its hidden
                # reasoning tokens vary run-to-run, so one re-request has a real
                # chance of fitting (observed ~1/25 rep truncation rate, and a
                # truncated P2 means an EMPTY answer set — worth the retry).
                log.info("[%s] %s: output truncated (finish_reason=%s) — not "
                         "re-requesting; raise max_tokens / lower thinking_level",
                         trace.doc_id, tag, res.response.raw_finish_reason)
                break
        return ok, data

    async def _phase1_chunk(
        self,
        page_numbers: list[int],
        images: list[Image.Image],
        doc_priority: int,
        trace: Trace,
        *,
        phase: str = "p1",
        model_key: str | None = None,
        image_max_px: int | None = None,
        timeout_s: float | None = None,
    ) -> dict[int, str]:
        cfg = self.cfg
        key = model_key or cfg.p1_model_key
        max_px = image_max_px or cfg.image_max_px
        # An EXPLICIT parameter, not a `phase == "reader"` sniff. Readers share
        # this code path with P1 and need the optional-pass timeout, and the
        # caller is the only thing that knows which it is; branching on the
        # phase STRING here would put that knowledge in two places and make the
        # transport policy a stringly-typed transport (CLAUDE.md 3.2).
        base_timeout_s = timeout_s if timeout_s is not None else cfg.timeout_s
        ms = self._resolve(key)
        provider = self._providers[ms.provider]

        timer = StageTimer(trace)
        log.info("[%s] %s chunk pages=%s: encoding %d image(s)",
                 trace.doc_id, phase, page_numbers, len(images))
        with timer.span("image_encode"):
            # [Stage C1] In the executor, not on the event loop. Same function,
            # same arguments, same bytes — a different thread. The lock keeps
            # this document's chunks encoding in the order they always did (see
            # `_encode_lock`).
            async with self._encode_lock:
                images_b64 = await asyncio.get_running_loop().run_in_executor(
                    _ENCODE_POOL, _encode_pages_sync, images, max_px,
                    cfg.image_format, cfg.image_jpeg_quality,
                    cfg.p1_image_packing == "stitched",
                )

        user = p1_user_prompt(page_numbers, cfg.p1_image_packing)
        schema = P1_SCHEMA if (cfg.use_json_schema and ms.supports_json_schema) else None
        per_page = (cfg.reader_max_tokens
                    if phase == "reader" and cfg.reader_max_tokens
                    else cfg.p1_max_tokens)
        max_tokens = per_page * len(page_numbers)
        log.info("[%s] %s chunk pages=%s: %d image(s) encoded "
                 "(model=%s, max_tokens=%d, timeout=%.0fs)",
                 trace.doc_id, phase, page_numbers, len(images_b64),
                 ms.model_id, max_tokens, self._budget.clamp(base_timeout_s))

        # P1 per subject profile: CS is `P1_SYSTEM` byte-for-byte; a prose/math
        # profile swaps only the ink-rules block (prompts.p1_system). Spec-blind
        # either way — the profile carries modality, never rubric content.
        p1_system_text = p1_system(_get_subject_profile(cfg.subject_key))

        def make_call():
            # Clamped HERE, inside the closure, so the budget is read at
            # DISPATCH rather than at chunk entry. Between the two sits the page
            # encode and however long the scheduler holds this call behind the
            # per-model concurrency cap — which on a busy instance is the whole
            # reason a clamp is worth having. Every other phase already reads it
            # at dispatch; P1 reading it earlier would have been the one call
            # allowed to outlive the budget.
            return provider.complete(
                system=p1_system_text, user=user, images_b64=images_b64,
                max_tokens=max_tokens, temperature=cfg.temperature,
                json_schema=schema,
                timeout_s=self._budget.clamp(base_timeout_s),
            )

        ok, data = await self._call_parsed(
            phase=phase, model_key=key, doc_priority=doc_priority,
            trace=trace, required_keys=("pages",), make_call=make_call,
            label=f"{phase} pages={page_numbers}",
        )
        if not ok:
            return {n: "" for n in page_numbers}  # degraded; coverage will fail loudly

        out: dict[int, str] = {}
        for item in data.get("pages", []):
            try:
                n = int(item["page_number"])
                if n in page_numbers:
                    # Same page emitted twice -> concatenate, never drop.
                    out[n] = (out.get(n, "") + "\n" + str(item["text"])).strip("\n")
            except (KeyError, TypeError, ValueError):
                continue
        for n in page_numbers:
            out.setdefault(n, "")
        return out

    async def _transcribe_pages(
        self,
        images: list[Image.Image],
        doc_id: str,
        doc_priority: int,
        trace: Trace,
        *,
        phase: str = "p1",
        model_key: str | None = None,
        image_max_px: int | None = None,
        timeout_s: float | None = None,
    ) -> dict[int, str]:
        """Chunk + dispatch pre-rendered page images through one P1 model."""
        page_numbers = list(range(1, len(images) + 1))
        chunks = _chunk(page_numbers, max(1, self.cfg.p1_pages_per_call))
        log.info("[%s] %s: dispatching %d chunk(s) (<=%d pages each) concurrently",
                 doc_id, phase, len(chunks), max(1, self.cfg.p1_pages_per_call))
        results = await asyncio.gather(*[
            self._phase1_chunk(
                nums, [images[n - 1] for n in nums], doc_priority, trace,
                phase=phase, model_key=model_key, image_max_px=image_max_px,
                timeout_s=timeout_s,
            )
            for nums in chunks
        ])
        pages: dict[int, str] = {}
        for r in results:
            pages.update(r)
        return pages

    async def render(self, pdf_bytes: bytes, trace: Trace) -> list[Image.Image]:
        timer = StageTimer(trace)
        with timer.span("pdf_render"):
            images = await asyncio.get_running_loop().run_in_executor(
                None, self._render, pdf_bytes, self.cfg.dpi
            )
        return images

    async def run_phase1(
        self, pdf_bytes: bytes, doc_id: str, *, doc_priority: int = 0,
        trace: Trace | None = None,
    ) -> tuple[dict[int, str], Trace]:
        trace = trace or Trace(doc_id=doc_id)
        log.info("[%s] phase1 start: rendering PDF @ %d DPI (%.1f KB)",
                 doc_id, self.cfg.dpi, len(pdf_bytes) / 1024)
        images = await self.render(pdf_bytes, trace)
        log.info("[%s] pdf_render done: %d page(s)", doc_id, len(images))
        pages = await self.perceive(images, doc_id, doc_priority, trace)
        return pages, trace

    async def perceive(
        self,
        images: list[Image.Image],
        doc_id: str,
        doc_priority: int,
        trace: Trace,
    ) -> dict[int, str]:
        """THE perception entry point: P1 transcription + the post-P1
        strike-check pass.

        Both callers go through here — `run_phase1` (eval `p1_only`) and
        `trust.run_with_trust` (the PRODUCTION path, which calls
        `_transcribe_pages` directly and does NOT use run_phase1). The
        strike-check hook originally lived in run_phase1 alone, which meant
        enabling it in PROD_CONFIG changed nothing in production while working
        perfectly in the eval suite — a silent eval-vs-prod divergence. Keeping
        perception in one method is what stops that recurring; pinned by
        tests/transcription_eval_suit/test_strike_check.py::
        test_trust_path_runs_the_strike_check_too.
        """
        # P1 is ESSENTIAL: without it there is no transcription at all, so an
        # exhausted budget raises rather than degrading (budget.py).
        self._budget.require(_ESSENTIAL_MIN_RUNWAY_S, "phase 1 (perception)")
        pages = await self._transcribe_pages(images, doc_id, doc_priority, trace)
        log.info("[%s] phase1 done: %d page(s) transcribed", doc_id, len(pages))
        if self.cfg.p1_strike_check_model_key:
            pages = await self._strike_check_pages(
                images, pages, doc_id, doc_priority, trace)
        return pages

    async def _strike_check_pages(
        self,
        images: list[Image.Image],
        pages: dict[int, str],
        doc_id: str,
        doc_priority: int,
        trace: Trace,
    ) -> dict[int, str]:
        """Post-P1 verification: per nonempty page, ask the checker model which
        transcribed lines are crossed out in the ink, then delete exactly those
        lines (strike_check.py). Concurrent across pages; per-page fail-safe —
        any failure keeps that page's text unchanged (never a thrown doc)."""
        from .strike_check import (
            STRIKE_CHECK_SCHEMA,
            STRIKE_CHECK_SYSTEM,
            apply_struck_ranges,
            strike_check_user_prompt,
        )
        cfg = self.cfg
        key = cfg.p1_strike_check_model_key
        ms = self._resolve(key)
        provider = self._providers[ms.provider]
        schema = (STRIKE_CHECK_SCHEMA
                  if (cfg.use_json_schema and ms.supports_json_schema) else None)
        targets = [n for n in sorted(pages) if pages[n].strip()]
        if not targets:
            return pages
        # OPTIONAL PASS: when the document's wall budget cannot cover this
        # phase, SKIP it and keep P1's text -- which is precisely what this pass
        # already does on any failure. Degradation by omission, never by guess
        # (CLAUDE.md 3.5a); the teacher loses a crossed-out-ink correction, not
        # her document.
        if not self._budget.can_start(self.cfg.optional_pass_budget_s):
            log.warning(
                "[%s] strike_check skipped: %.0fs of the %.0fs document budget "
                "already spent — keeping P1 text for %d page(s)",
                doc_id, self._budget.elapsed_s(), self._budget.total_s or 0.0,
                len(targets))
            return pages
        log.info("[%s] strike_check: verifying %d page(s) with %s",
                 doc_id, len(targets), ms.model_id)

        votes = max(1, cfg.p1_strike_check_votes)

        async def one_vote(n: int, b64: str, user: str, vote: int) -> list:
            """One checker call; returns its reported ranges ([] on failure)."""
            try:
                def make_call():
                    return provider.complete(
                        system=STRIKE_CHECK_SYSTEM, user=user, images_b64=[b64],
                        max_tokens=cfg.p1_strike_check_max_tokens,
                        temperature=cfg.temperature,
                        json_schema=schema,
                        timeout_s=self._budget.clamp(cfg.optional_pass_timeout_s),
                    )

                label = (f"strike_check page={n}" if votes == 1
                         else f"strike_check page={n} vote={vote}")
                ok, data = await self._call_parsed(
                    phase="strike_check", model_key=key,
                    doc_priority=doc_priority, trace=trace,
                    required_keys=("struck_line_ranges",), make_call=make_call,
                    label=label,
                )
                ranges = data.get("struck_line_ranges", []) if ok else []
                return ranges if isinstance(ranges, list) else []
            except Exception:  # noqa: BLE001 — checker must never sink the doc
                log.warning("[%s] strike_check page %d vote %d failed; "
                            "casting no ranges", doc_id, n, vote, exc_info=True)
                return []

        async def one(n: int) -> tuple[int, str]:
            text = pages[n]
            try:
                timer = StageTimer(trace)
                with timer.span("strike_encode"):
                    max_px = (cfg.p1_strike_check_image_max_px
                              or cfg.image_max_px)
                    # [Stage C1] The SECOND encode of every page — the one that
                    # doubled this pipeline's CPU on the request thread. Same
                    # lock, same reason: one page per call here, so the order
                    # this preserves is the page order.
                    async with self._encode_lock:
                        b64 = (await asyncio.get_running_loop().run_in_executor(
                            _ENCODE_POOL, _encode_pages_sync, [images[n - 1]], max_px,
                            cfg.image_format, cfg.image_jpeg_quality, False,
                        ))[0]
                user = strike_check_user_prompt(n, text)
                vote_ranges = await asyncio.gather(
                    *(one_vote(n, b64, user, v) for v in range(1, votes + 1)))
                # UNION of the votes' reports; the min-block guard applies to
                # every range regardless of which vote cast it.
                combined = [r for ranges in vote_ranges for r in ranges]
                new_text, removed = apply_struck_ranges(
                    text, combined,
                    min_block_lines=cfg.p1_strike_check_min_block_lines)
                if removed:
                    log.info(
                        "[%s] strike_check page %d: removed %d struck line(s): %s",
                        doc_id, n, len(removed),
                        " | ".join(ln.strip()[:60] for ln in removed[:5]))
                elif combined:
                    log.info(
                        "[%s] strike_check page %d: %d range(s) reported, all "
                        "discarded by validation/min-block guard", doc_id, n,
                        len(combined))
                return n, new_text
            except Exception:  # noqa: BLE001 — checker must never sink the doc
                log.warning("[%s] strike_check page %d failed; keeping text",
                            doc_id, n, exc_info=True)
                return n, text

        # THE BELT (optional_pass_budget_s). The per-page `except` below already
        # guarantees this pass never RAISES; it does not — and cannot — bound how
        # long it DELAYS, because every layer under it (parse re-request x
        # scheduler transport retry x call timeout) multiplies. On 2026-09-10 one
        # page spent ~481s here and then discarded its own result exactly as
        # designed. Expiry lands on the same outcome the pass already defines:
        # keep every page's text unchanged.
        t_phase = time.monotonic()
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*(one(n) for n in targets)),
                timeout=self._budget.clamp(self.cfg.optional_pass_budget_s),
            )
        except asyncio.TimeoutError:
            log.warning(
                "[%s] strike_check exceeded its %.0fs budget after %.0fs — "
                "keeping P1 text for all %d page(s)",
                doc_id, self.cfg.optional_pass_budget_s,
                time.monotonic() - t_phase, len(targets))
            return pages
        out = dict(pages)
        out.update(dict(results))
        return out

    async def run_readers(
        self,
        images: list[Image.Image],
        doc_id: str,
        *,
        doc_priority: int = 0,
        trace: Trace | None = None,
    ) -> tuple[dict[str, dict[int, str]], Trace]:
        """Trust layer: run every configured reader model over the SAME page
        images, concurrently. Reader failures degrade to empty pages (which
        cast no disagreement votes) — per-unit isolation, never a thrown doc."""
        trace = trace or Trace(doc_id=doc_id)
        if not self.cfg.reader_model_keys:
            return {}, trace
        # OPTIONAL PASS, same policy as the strike check: an unaffordable budget
        # casts no votes rather than delaying the document. (Retired in prod --
        # PROD_CONFIG names no readers -- so this is the eval path today; it gets
        # the policy anyway because the difference between the two passes was
        # never a decision anyone made.)
        if not self._budget.can_start(self.cfg.optional_pass_budget_s):
            log.warning(
                "[%s] readers skipped: %.0fs of the %.0fs document budget "
                "already spent — casting no votes",
                doc_id, self._budget.elapsed_s(), self._budget.total_s or 0.0)
            return {}, trace

        async def one_reader(key: str) -> tuple[str, dict[int, str]]:
            try:
                pages = await self._transcribe_pages(
                    images, doc_id, doc_priority, trace,
                    phase="reader", model_key=key,
                    image_max_px=self.cfg.reader_image_max_px,
                    timeout_s=self.cfg.optional_pass_timeout_s,
                )
            except Exception:  # noqa: BLE001 — a reader must never sink the doc
                log.warning("[%s] reader %s failed; casting no votes",
                            doc_id, key, exc_info=True)
                pages = {}
            return key, pages

        t_phase = time.monotonic()
        try:
            results = await asyncio.wait_for(
                asyncio.gather(
                    *[one_reader(k) for k in self.cfg.reader_model_keys]),
                timeout=self._budget.clamp(self.cfg.optional_pass_budget_s),
            )
        except asyncio.TimeoutError:
            log.warning(
                "[%s] readers exceeded their %.0fs budget after %.0fs — "
                "casting no votes", doc_id, self.cfg.optional_pass_budget_s,
                time.monotonic() - t_phase)
            return {}, trace
        return dict(results), trace

    async def run_phase2(
        self, pages: dict[int, str], exam_spec: ExamSpec, doc_id: str,
        *, doc_priority: int = 0, trace: Trace | None = None,
    ) -> PipelineRun:
        cfg = self.cfg
        trace = trace or Trace(doc_id=doc_id)
        if not cfg.p2_model_key:
            raise ValueError("Phase 2 requested but p2_model_key is empty (p1_only config).")
        ms = self._resolve(cfg.p2_model_key)
        provider = self._providers[ms.provider]
        # P2 is ESSENTIAL -- P1 text without segmentation is not a transcription
        # anyone can grade, so exhaustion raises here rather than shipping a
        # partial draft (budget.py; CLAUDE.md 3.5a + FC).
        self._budget.require(_ESSENTIAL_MIN_RUNWAY_S, "phase 2 (segmentation)")
        log.info("[%s] phase2 start: %d page(s) -> %s (contract=%s, timeout=%.0fs)",
                 doc_id, len(pages), ms.model_id, cfg.p2_output_contract,
                 self._budget.clamp(cfg.timeout_s))

        if cfg.p2_output_contract == "spans":
            answers, notes = await self._phase2_spans(
                pages, exam_spec, doc_priority, trace, ms, provider)
            corrected_answers, corrections, mismatches = self._apply_corrections(
                answers, exam_spec, trace
            )
            return PipelineRun(
                pages=pages, answers=answers,
                spec_mismatches=tuple(mismatches), routing_notes=notes,
                trace=trace, corrected_answers=corrected_answers,
                corrections=tuple(corrections),
                prompt_version=_stamp_prompt_version(
                    TRANSCRIPTION_PROMPT_VERSION, _get_subject_profile(cfg.subject_key)),
            )

        # ALPHA-GAP A-8: P2 text is the CS base for every profile; alpha words segmentation per modality.
        system = p2_system_prompt(_get_subject_profile(cfg.subject_key))
        user = p2_user_prompt(pages, exam_spec.to_prompt_json())
        schema = P2_SCHEMA if (cfg.use_json_schema and ms.supports_json_schema) else None

        def make_call():
            return provider.complete(
                system=system, user=user, images_b64=None,
                max_tokens=cfg.p2_max_tokens, temperature=cfg.temperature,
                json_schema=schema, timeout_s=self._budget.clamp(cfg.timeout_s),
                reasoning_effort=cfg.p2_reasoning_effort or None,
            )

        ok, data = await self._call_parsed(
            phase="p2", model_key=cfg.p2_model_key, doc_priority=doc_priority,
            trace=trace, required_keys=("answers",), make_call=make_call,
            label="p2",
        )

        answers: dict[Key, str] = {}
        notes: tuple[str, ...] = ()
        if ok:
            with StageTimer(trace).span("merge"):
                for a in data.get("answers", []):
                    try:
                        k = normalize_key((int(a["question_number"]),
                                           a.get("sub_question_id")))
                    except (KeyError, TypeError, ValueError):
                        continue
                    text = str(a.get("answer_text", ""))
                    answers[k] = (answers[k] + "\n" + text) if k in answers else text
                notes = tuple(str(n) for n in data.get("routing_notes", []) or [])

        # Deterministic correction post-pass (spec-blind LLM stays verbatim).
        corrected_answers, corrections, mismatches = self._apply_corrections(
            answers, exam_spec, trace
        )

        return PipelineRun(
            pages=pages, answers=answers,
            spec_mismatches=tuple(mismatches), routing_notes=notes, trace=trace,
            corrected_answers=corrected_answers, corrections=tuple(corrections),
            prompt_version=_stamp_prompt_version(
                TRANSCRIPTION_PROMPT_VERSION, _get_subject_profile(cfg.subject_key)),
        )

    async def _phase2_spans(
        self,
        pages: dict[int, str],
        exam_spec: ExamSpec,
        doc_priority: int,
        trace: Trace,
        ms,
        provider,
    ) -> tuple[dict[Key, str], tuple[str, ...]]:
        """The span contract (spans.py): model emits line references; the
        harness slices text verbatim and VALIDATES the partition.

        A parseable-but-contract-invalid map gets ONE visible re-request (a
        separate call record — parse_ok stays honest, so the gate's
        parse_failure validity check is untouched); a second bad map degrades
        to the deterministic salvage slice with every resolution recorded in
        routing_notes. Never throws."""
        from .spans import (
            build_span_schema, numbered_pages_block, parse_and_slice,
            spec_targets,
        )
        cfg = self.cfg
        targets = spec_targets(exam_spec)
        numbered = numbered_pages_block(pages)
        # ALPHA-GAP A-8: span-mode P2 text is the CS base for every profile this cycle.
        system = p2_span_system(_get_subject_profile(cfg.subject_key))
        user = p2_span_user_prompt(numbered, exam_spec.to_prompt_json())
        schema = (build_span_schema(targets)
                  if (cfg.use_json_schema and ms.supports_json_schema) else None)

        def _mk(user_text: str):
            def make_call():
                return provider.complete(
                    system=system, user=user_text, images_b64=None,
                    max_tokens=cfg.p2_max_tokens, temperature=cfg.temperature,
                    json_schema=schema,
                    timeout_s=self._budget.clamp(cfg.timeout_s),
                    reasoning_effort=cfg.p2_reasoning_effort or None,
                )
            return make_call

        results = []
        attempt_user = user
        for attempt_label in ("p2", "p2-remap"):
            ok, data = await self._call_parsed(
                phase="p2", model_key=cfg.p2_model_key,
                doc_priority=doc_priority, trace=trace,
                required_keys=("assignments",), make_call=_mk(attempt_user),
                label=attempt_label,
            )
            if not ok:
                break                       # parse layer already retried once
            with StageTimer(trace).span("merge"):
                result = parse_and_slice(data, pages, targets)
            results.append(result)
            if result.ok:
                break
            log.info("[%s] %s: span map contract-invalid (%d problem(s): %s)",
                     trace.doc_id, attempt_label, len(result.problems),
                     "; ".join(result.problems[:4]))
            # Targeted repair: name the violations, demand a full corrected map.
            attempt_user = (
                f"{user}\n\nYOUR PREVIOUS ASSIGNMENT MAP VIOLATED THE CONTRACT:\n"
                + "\n".join(f"- {p}" for p in result.problems[:12])
                + "\nRe-emit the FULL corrected assignment map (every target "
                  "exactly once, spans disjoint and in range)."
            )

        if not results:
            # Unparseable twice — degraded empty map; coverage fails loudly.
            return ({t.key: "" for t in targets},
                    ("span_contract: no parseable assignment map",))

        best = min(results, key=lambda r: len(r.problems))
        notes = list(best.notes)
        for p in best.problems:
            notes.append(f"span_contract: {p} (salvaged deterministically)")
        return best.answers, tuple(notes)

    def _apply_corrections(self, answers, exam_spec, trace):
        """Run the deterministic corrector over each answer; collect evidence.
        Returns (corrected_answers, all_corrections, spec_mismatch_records)."""
        corrected: dict[Key, str] = {}
        all_corr: list[Correction] = []
        mismatches: list[SpecMismatch] = []
        if self.cfg.correction_policy == "off":
            return dict(answers), [], []
        with StageTimer(trace).span("correct"):
            for k, text in answers.items():
                res = correct_text(
                    text, policy=self.cfg.correction_policy,
                    spec_identifiers=exam_spec.identifiers,
                )
                corrected[k] = res.text
                for c in res.corrections:
                    all_corr.append(c)
                    mismatches.append(SpecMismatch(
                        key=k, original=c.original, suggested=c.corrected,
                        reason=f"{c.tier}->{c.target_kind}",
                    ))
        return corrected, all_corr, mismatches

    async def run(
        self, pdf_bytes: bytes, doc_id: str, exam_spec: ExamSpec,
        *, doc_priority: int = 0,
    ) -> PipelineRun:
        pages, trace = await self.run_phase1(
            pdf_bytes, doc_id, doc_priority=doc_priority
        )
        return await self.run_phase2(
            pages, exam_spec, doc_id, doc_priority=doc_priority, trace=trace
        )


def build_pipeline(
    cfg: PipelineConfig,
    providers: dict[str, VLMProvider],
    scheduler: ProviderScheduler,
    *,
    resolve_model: ResolveModel,
    pdf_renderer: PdfRenderer = _default_renderer,
) -> Pipeline:
    return Pipeline(cfg, providers, scheduler,
                    resolve_model=resolve_model, pdf_renderer=pdf_renderer)
