"""
two_phase_engine — the production entry to the two-phase pipeline.

Selected by settings.transcription_engine == "two_phase" (transcribe_one).
Produces the SAME TranscriptionDraft shape as the legacy engine, so the
endpoint, persistence, and review UI are unchanged. What's new inside the
draft: per-answer page_numbers (deterministic provenance) and code_lint
annotations (brace balance — measured zero-noise on the golden set).

MODEL SET (the suite's models_registry stays eval-side — prices here are only
for cost logging):
    baseline P1  gemini-3.1-pro-preview
    P2           gpt-5.6-luna (owner decision 2026-08-07 — the fired §17.8
                 escalation trigger's follow-through; nano's successor cost
                 tier, UNDER EVALUATION against the nano baseline. Revert =
                 flip p2_model_key back to gpt-5.4-nano-2026-03-17.)

READERS RETIRED IN PRODUCTION (2026-08-07, owner-ruled). The v1_trust
cross-reader flag layer (haiku-4.5 + 4o-mini + flash-lite) was calibrated for
RECALL on golden fixtures where the baseline had real errors; on production
docs where the baseline reads correctly (the common case) its flags were
~100% false — cheap readers omit brace lines, misread identifiers, and
NORMALIZE faithfully-captured student errors toward valid code (i+2 -> i+=2,
= -> == …), so multi-reader "consensus" concentrated on exactly the content
the product must never cast doubt on (FC). Evidence: transcription
bf610c19… (75/75 false flags). The flag→annotation adapter below is kept
(pre-retirement drafts still render; the eval suite still measures the layer
via configs/v1_trust.json), and re-enabling is config-only — but any future
verifier must first beat the falsification record in flagging.py's docstring.

STRIKE-CHECK PASS ENABLED (2026-08-23). PROD_CONFIG now names a
`p1_strike_check_model_key` (gemini-3.5-flash): after P1, one cheap call per
page asks which already-transcribed lines are struck through, and a pure
post-pass deletes exactly those lines. It returns LINE NUMBERS, never text, so
P1's verbatim contract holds by construction, and any failure leaves the page
as P1 produced it. Note this is NOT the retired reader layer: it does not
compare transcriptions or emit flags, and its output is a deletion, not a vote.
Two wiring facts worth keeping in view, both of which bit on the way in:
`_shared_infra` must include the strike key (it is resolved outside the pass's
per-page try/except, so a missing provider kills the DOCUMENT), and perception
lives in `Pipeline.perceive` because production enters through
`trust.run_with_trust`, NOT `run_phase1` — a hook installed only in the latter
runs in the eval suite and silently never runs in production.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from ...config import settings
from ...schemas.ontology_types import AnnotationSeverity
from ...schemas.transcription import (
    TranscriptionAnnotation,
    TranscriptionDraft,
    TranscriptionDraftAnswer,
)
from .providers.anthropic_provider import AnthropicProvider
from .providers.gemini_provider import GeminiProvider
from .providers.openai_provider import OpenAIProvider
from .scheduler import ProviderLimit, ProviderScheduler
from .two_phase.instrument import PriceCard
from .two_phase.parsing import spec_from_rubric_draft_data
from .two_phase.pipeline import Pipeline, PipelineConfig, alias
from .two_phase.trust import TrustRun, run_with_trust

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Model:
    key: str
    provider: str
    model_id: str
    price: PriceCard
    supports_json_schema: bool = True


_MODELS: dict[str, _Model] = {
    # Retired reader set (haiku-4.5 / 4o-mini / flash-lite) lives on in the
    # eval suite (configs/v1_trust.json + models_registry) — not here.
    "gemini-3.1-pro-preview": _Model(
        "gemini-3.1-pro-preview", "gemini", "gemini-3.1-pro-preview",
        PriceCard(in_per_mtok=2.00, out_per_mtok=12.00, cached_in_per_mtok=0.20)),
    # Previous P2 pin — kept as the one-line revert target while luna is
    # under evaluation.
    "gpt-5.4-nano-2026-03-17": _Model(
        "gpt-5.4-nano-2026-03-17", "openai", "gpt-5.4-nano-2026-03-17",
        PriceCard(in_per_mtok=0.20, out_per_mtok=1.25)),
    "gpt-5.6-luna": _Model(
        "gpt-5.6-luna", "openai", "gpt-5.6-luna",
        PriceCard(in_per_mtok=0.20, out_per_mtok=1.20)),
    # Post-P1 strike-check judge (2026-08-23). NOT a transcriber: it never
    # emits text, only line numbers (strike_check.py). gemini-3.5-flash was
    # chosen over flash-lite on evidence — flash-lite deleted 3 REAL lines on
    # moran p2 in 2/2 reps even behind the min-block guard, while flash
    # produced zero false positives across 15 paired records.
    # Prices are the ILS-corrected card (model page lists 6.00/36.00 ILS).
    "gemini-3.5-flash": _Model(
        "gemini-3.5-flash", "gemini", "gemini-3.5-flash",
        PriceCard(in_per_mtok=1.98, out_per_mtok=11.88,
                  cached_in_per_mtok=0.15)),
}

# The production config — v1_trust MINUS the reader fan-out (owner-ruled,
# see module docstring) and with P2 switched to gpt-5.6-luna (owner decision
# 2026-08-07, mirroring the suite's v0.json; nano remains the revert target).
# reader_model_keys=() is the pipeline's first-class "trust layer disabled"
# state: run_readers short-circuits, compute_flags emits nothing, lint +
# provenance still run.
PROD_CONFIG = PipelineConfig(
    p1_model_key="gemini-3.1-pro-preview",
    p1_pages_per_call=3,
    p1_image_packing="multi_image",
    dpi=200,
    image_max_px=2000,
    p1_max_tokens=5000,
    # --- Post-P1 crossed-out-ink verification (ENABLED 2026-08-23) ---
    # P1 (gemini-3.1-pro) stably transcribes large struck-through blocks that
    # the ground truth correctly excludes; the P1 prompt surface for this is
    # EXHAUSTED (t1.3/t1.3b both fired their kill criteria — see prompts.py).
    # This pass asks a second model ONE question per page — "which of these
    # already-transcribed lines are struck?" — and deletes exactly those lines.
    # It returns LINE NUMBERS, never text, so the verbatim contract holds by
    # construction; any failure (transport/parse/invalid range) leaves the page
    # exactly as P1 produced it.
    #
    # Evidence (paired k=3, 5 fixtures, 15 records — results/
    # strike_check_2026-08-19/): din_ezra 0.9025->0.9807 (+0.0780 mean, the
    # crossed-out block removed 3/3) with operator/structural/method-call
    # recall delta EXACTLY 0.000000; the other 12/12 records byte-identical,
    # zero deletions, moran's full-gate PASS preserved 3/3.
    # Cost +~$0.021/doc, +~7.8s median (pages checked concurrently).
    # REVERT = set this key to "" (one line); everything else stays.
    p1_strike_check_model_key="gemini-3.5-flash",
    p1_strike_check_max_tokens=4000,
    # Discard ranges shorter than 2 lines: the observed false-positive class is
    # a KEPT line containing an inline scribbled-out word (flash-lite deleted
    # `return true;` on moran p2 that way), while the real leak class is a
    # multi-line block. Deliberately NOT stated in the prompt — a model told
    # single lines are discarded learns to inflate its ranges.
    p1_strike_check_min_block_lines=2,
    p1_strike_check_votes=1,
    p2_model_key="gpt-5.6-luna",
    correction_policy="off",
    p2_max_tokens=24000,
    # Ratified by the 2026-08-11 proof run (results/20260811_174036_v0):
    # p2_only k=5, 25/25 records pass the conjunctive gate. effort=low showed
    # accuracy identical to medium with truncations 1->0 and half the latency.
    p2_reasoning_effort="low",
    # The span contract (spans.py): P2 emits line references against a closed
    # target enum; the harness slices text verbatim + validates the partition.
    # Revert path: "text" (the legacy generative contract).
    p2_output_contract="spans",
    temperature=0.0,
    use_json_schema=True,
    # 240s, DELIBERATELY above the eval suite's 120s (reverted 2026-08-12
    # after field evidence): P1 pushes multi-MB image uploads, and on weak
    # links (hotel/school WiFi) a SLOWLY-SUCCEEDING upload legitimately needs
    # 120-200s — a 120s cap killed calls mid-progress and re-paid the whole
    # upload (observed: first attempts cut at 120s, retries succeeding at
    # 45-90s). Patience beats fail-fast when retry means re-uploading
    # megabytes; the eval's 120s was earned on small-payload calls and a
    # healthy network. Hung-DEAD connections cost up to 240s before the
    # scheduler's retry — that trade is correct for the production reality,
    # and the doc-level re-run in batch_grading is the final net.
    timeout_s=240.0,
)

TWO_PHASE_ENGINE_VERSION = "two_phase/v4_p2-spans"


async def transcribe_two_phase(
    pdf_bytes: bytes,
    doc_id: str,
    rubric_draft_json: dict,
    *,
    doc_priority: int = 0,
    subject: str = "computer_science",
) -> tuple[TrustRun, str | None]:
    """PDF + rubric draft json -> (TrustRun, student-name suggestion).

    doc_priority feeds the provider scheduler's depth-first dispatch (lower =
    sooner): in a batch, document i gets priority i so the first upload's
    chunks win the per-model concurrency slots and finish first.

    The identity pass (identity.py) runs CONCURRENTLY with the pipeline —
    P1's prompt deliberately excludes the student identity block, so the name
    travels this separate channel. It never raises and never delays the doc
    (own timeout; pipeline is the long pole). doc_id is the original filename,
    which doubles as the identity pass's fallback source."""
    from dataclasses import replace as _replace

    from app.subjects import get_profile

    from .identity import extract_student_name

    # Subject seam (2026-09-08): the profile selects P1's ink rules (modality
    # only — the spec stays out of P1) and the P2 identifier keyword set (F-5).
    # CS reproduces PROD_CONFIG and the pre-seam spec byte-for-byte.
    profile = get_profile(subject)
    spec = spec_from_rubric_draft_data(rubric_draft_json, name="rubric",
                                       keywords=profile.p2_keywords)
    providers, _, scheduler = _shared_infra()
    pipeline = _build_pipeline_multi(_replace(PROD_CONFIG, subject_key=profile.key))
    # Identity rides the SAME shared provider + scheduler slot pool as P1
    # (same eyes — the proven Hebrew-handwriting reader; the crop makes its
    # cost negligible), at its document's priority: submitted before the P1
    # chunks finish encoding, it takes an early slot, and the scheduler owns
    # its transport retry (one concept, one place).
    trust_run, suggestion = await asyncio.gather(
        run_with_trust(pipeline, pdf_bytes, doc_id, spec,
                       doc_priority=doc_priority),
        extract_student_name(
            pdf_bytes, doc_id, providers[PROD_CONFIG.p1_model_key],
            scheduler=scheduler, provider_key=PROD_CONFIG.p1_model_key,
            doc_priority=doc_priority,
        ),
    )
    return trust_run, suggestion


def _make_provider(m: _Model):
    if m.provider == "openai":
        return OpenAIProvider(m.model_id)
    if m.provider == "anthropic":
        return AnthropicProvider(m.model_id)
    if m.provider == "gemini":
        return GeminiProvider(m.model_id)
    raise ValueError(m.provider)


# Global per-model concurrency across ALL documents in this process. 5 keeps
# a single doc's chunks fully parallel and bounds a batch's simultaneous
# multi-MB image uploads (the 2026-08-12 root cause: per-doc schedulers made
# the cap a no-op, so N parallel docs launched up to 3×N+N Gemini uploads at
# once, saturating the uplink and cascading ReadTimeouts in weak windows).
PROD_MAX_CONCURRENT_PER_MODEL = 5

# ONE provider set + ONE scheduler per (process, event loop) — never per
# document. This is the eval runner's proven batch architecture: a shared
# scheduler is what makes the per-model cap real and doc_priority meaningful
# across documents (depth-first: doc 0's calls win slots batch-wide). Shared
# adapters also reuse HTTP connections across calls. Keyed by the running
# loop so tests (fresh loop per TestClient/asyncio.run) get fresh state.
_shared_infra_cache: tuple[object, dict, dict, ProviderScheduler] | None = None


def _shared_infra() -> tuple[dict, dict, ProviderScheduler]:
    global _shared_infra_cache
    loop = asyncio.get_running_loop()
    if _shared_infra_cache is not None and _shared_infra_cache[0] is loop:
        _, providers, aliased, scheduler = _shared_infra_cache
        return providers, aliased, scheduler
    # EVERY model key the config can dispatch to must get a provider, an alias
    # and a scheduler slot. The strike-check key is resolved OUTSIDE the
    # pass's per-page try/except, so omitting it here turns a config flip into
    # a KeyError that kills the whole document rather than degrading the
    # checker — pinned by test_two_phase_engine::test_shared_infra_covers_
    # every_prod_config_model_key.
    keys = {k for k in (PROD_CONFIG.p1_model_key, PROD_CONFIG.p2_model_key,
                        PROD_CONFIG.p1_strike_check_model_key,
                        *PROD_CONFIG.reader_model_keys) if k}
    providers = {k: _make_provider(_MODELS[k]) for k in keys}
    aliased = {k: alias(_MODELS[k]) for k in keys}
    scheduler = ProviderScheduler({
        k: ProviderLimit(max_concurrent=PROD_MAX_CONCURRENT_PER_MODEL)
        for k in keys
    })
    _shared_infra_cache = (loop, providers, aliased, scheduler)
    return providers, aliased, scheduler


def _build_pipeline_multi(cfg: PipelineConfig) -> Pipeline:
    """Per-document Pipeline over the SHARED providers/scheduler (adapter
    instance per MODEL KEY, aliased — see pipeline.AliasedModel)."""
    providers, aliased, scheduler = _shared_infra()
    return Pipeline(cfg, providers, scheduler,
                    resolve_model=lambda k: aliased[k])


def build_draft_from_trust_run(
    tr: TrustRun,
    page_count: int,
    duration_ms: int,
    student_name_suggestion: str | None = None,
) -> TranscriptionDraft:
    """TrustRun -> TranscriptionDraft (the v2 adapter).

    Draft text is the BASELINE's verbatim output. The trust layer contributes
    ONLY page provenance, confidence, and annotations — flags are advisory and
    never modify text (verbatim contract; teacher authority)."""
    answers: list[TranscriptionDraftAnswer] = []
    annotations: list[TranscriptionAnnotation] = []

    from .two_phase.trust import answer_target

    for (q, sub), text in sorted(tr.run.answers.items(),
                                 key=lambda kv: (kv[0][0], str(kv[0][1]))):
        target = answer_target(q, sub)
        att = tr.attributions.get(target)
        answers.append(TranscriptionDraftAnswer(
            question_number=q,
            sub_question_id=sub,
            answer_text=text,
            confidence=round(att.confidence, 3) if att else 0.0,
            page_numbers=att.pages if att else [],
        ))
        if "[?]" in text:
            annotations.append(TranscriptionAnnotation(
                severity=AnnotationSeverity.WARNING,
                target_id=target,
                annotation_type="vlm_unparseable",
                message="חלקים מהתשובה לא היו קריאים בתמלול",
            ))

    # Trust flags -> annotations. DORMANT under PROD_CONFIG (readers retired,
    # 2026-08-07 — tr.flags is empty); kept for pre-retirement drafts and any
    # future eval-gated re-enable. Severity mapping (measured vote ladder):
    #   high (≥2 readers)  -> WARNING — the teacher should look
    #   medium (1 reader)  -> INFO    — glance-worthy
    #   info (hebrew/marker chrome) -> dropped from teacher surface (metadata
    #   noise; comments/markers are not graded content)
    for f in tr.flags:
        if f.severity == "info":
            continue
        target = f.anchor_key or "transcription"
        alts = " / ".join(a for a in f.alternatives if a) or "(השמטה)"
        base_disp = f.base_text or "(ריק)"
        annotations.append(TranscriptionAnnotation(
            severity=(AnnotationSeverity.WARNING if f.severity == "high"
                      else AnnotationSeverity.INFO),
            target_id=target,
            annotation_type="reader_disagreement",
            message=(f"עמוד {f.page}: קריאה חוזרת של קטע זה זיהתה נוסח שונה — "
                     f"תומלל „{base_disp}”, קריאה חלופית: „{alts}”. "
                     f"מומלץ להשוות מול הסריקה."),
            metadata={
                "page": f.page,
                "line_quote": f.context_line,
                "transcribed": f.base_text,
                "alternatives": list(f.alternatives),
                "n_readers": f.n_readers,
                "char_start": f.char_start,
                "char_end": f.char_end,
                "anchor_similarity": round(f.anchor_similarity, 3),
            },
        ))

    # Marker↔key mismatch (2026-08-07): the student's own leading section
    # marker contradicts the P2-assigned key — the known nano skip-collapse
    # renumbering. The key is the GRADING route, so this is a WARNING with a
    # proposed swap target; the teacher confirms via the review surface (the
    # frontend recomputes the same detection LIVE in segmentation-check.ts —
    # this static annotation is the triage signal + the permanent record).
    from .segmentation_check import detect_mismatches
    triples = [(a.question_number, a.sub_question_id, a.answer_text)
               for a in answers]
    for mm in detect_mismatches(triples):
        target = answer_target(mm.question_number, mm.sub_question_id)
        assigned_label = (
            f"שאלה {mm.question_number}"
            + (f" סעיף {mm.sub_question_id}" if mm.sub_question_id else "")
        )
        annotations.append(TranscriptionAnnotation(
            severity=AnnotationSeverity.WARNING,
            target_id=target,
            annotation_type="segmentation_mismatch",
            message=(f"בכתב היד הקטע מסומן כשאלה {mm.declared_question}, "
                     f"אך שויך ל{assigned_label} — מומלץ לוודא את השיוך."),
            metadata={
                "declared_question": mm.declared_question,
                "proposed_target": (
                    answer_target(*mm.proposed_target)
                    if mm.proposed_target else None
                ),
            },
        ))

    for lf in tr.lint:
        annotations.append(TranscriptionAnnotation(
            severity=AnnotationSeverity.INFO,
            target_id=lf.answer_key,
            annotation_type="code_lint",
            message=("סוגריים מסולסלים לא מאוזנים בתשובה זו "
                     f"({'+' if lf.balance > 0 else ''}{lf.balance}) — "
                     "ייתכן שהושמט סוגר בתמלול או שהתלמיד השמיט אותו."),
            metadata={"balance": lf.balance},
        ))

    return TranscriptionDraft(
        # From the SEPARATE identity pass (identity.py) — P1's verbatim output
        # still excludes the identity block by design. None = no legible name
        # and no plausible filename (teacher picks manually, as before).
        student_name_suggestion=student_name_suggestion,
        page_count=page_count,
        answers=answers,
        annotations=annotations,
        model_version=TWO_PHASE_ENGINE_VERSION,
        prompt_version=getattr(tr.run, "prompt_version", None),
        transcription_duration_ms=duration_ms,
    )
