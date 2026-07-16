"""
two_phase_engine — the production entry to the two-phase pipeline + trust layer.

Selected by settings.transcription_engine == "two_phase" (transcribe_one).
Produces the SAME TranscriptionDraft shape as the legacy engine, so the
endpoint, persistence, and review UI are unchanged. What's new inside the
draft: per-answer page_numbers (deterministic provenance), and annotations of
type reader_disagreement / code_lint (the trust layer).

MODEL SET (mirrors the eval suite's validated v1_trust config; the suite's
models_registry stays eval-side — prices here are only for cost logging):
    baseline P1  gemini-3.1-pro-preview
    readers      claude-haiku-4.5 + gpt-4o-mini + gemini-3.1-flash-lite
    P2           gpt-5.4-nano
Measured on the golden set (2026-07-09 calibration): union critical-error
flag recall 0.93-0.95 with readers at 1400px; ~20 warning-tier flags/doc
(tier V3 in flagging.FlagSpan.severity); cost ~$0.085/doc (envelope $0.10).
"""
from __future__ import annotations

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
    "gemini-3.1-pro-preview": _Model(
        "gemini-3.1-pro-preview", "gemini", "gemini-3.1-pro-preview",
        PriceCard(in_per_mtok=2.00, out_per_mtok=12.00, cached_in_per_mtok=0.20)),
    "gemini-3.1-flash-lite": _Model(
        "gemini-3.1-flash-lite", "gemini", "gemini-3.1-flash-lite",
        PriceCard(in_per_mtok=0.25, out_per_mtok=1.50, cached_in_per_mtok=0.025)),
    "claude-haiku-4.5": _Model(
        "claude-haiku-4.5", "anthropic", "claude-haiku-4-5",
        PriceCard(in_per_mtok=1.00, out_per_mtok=5.00, cached_in_per_mtok=0.10)),
    "chatgpt-4o-mini": _Model(
        "chatgpt-4o-mini", "openai", "gpt-4o-mini",
        PriceCard(in_per_mtok=0.15, out_per_mtok=0.60, cached_in_per_mtok=0.075)),
    "gpt-5.4-nano-2026-03-17": _Model(
        "gpt-5.4-nano-2026-03-17", "openai", "gpt-5.4-nano-2026-03-17",
        PriceCard(in_per_mtok=0.20, out_per_mtok=1.25)),
}

# The production config — a mirror of the suite's configs/v1_trust.json
# (validated there; change THERE first, then here).
TRUST_CONFIG = PipelineConfig(
    p1_model_key="gemini-3.1-pro-preview",
    p1_pages_per_call=3,
    p1_image_packing="multi_image",
    dpi=200,
    image_max_px=2000,
    p1_max_tokens=5000,
    reader_model_keys=("claude-haiku-4.5", "chatgpt-4o-mini",
                       "gemini-3.1-flash-lite"),
    reader_image_max_px=1400,
    reader_max_tokens=5400,
    p2_model_key="gpt-5.4-nano-2026-03-17",
    correction_policy="off",
    p2_max_tokens=24000,
    temperature=0.0,
    use_json_schema=True,
    timeout_s=240.0,
)

TWO_PHASE_ENGINE_VERSION = "two_phase/v1_trust"


async def transcribe_two_phase(
    pdf_bytes: bytes,
    doc_id: str,
    rubric_draft_json: dict,
) -> TrustRun:
    """PDF + rubric draft json -> TrustRun (two-phase draft + flags)."""
    spec = spec_from_rubric_draft_data(rubric_draft_json, name="rubric")
    pipeline = _build_pipeline_multi(TRUST_CONFIG)
    return await run_with_trust(pipeline, pdf_bytes, doc_id, spec)


def _make_provider(m: _Model):
    if m.provider == "openai":
        return OpenAIProvider(m.model_id)
    if m.provider == "anthropic":
        return AnthropicProvider(m.model_id)
    if m.provider == "gemini":
        return GeminiProvider(m.model_id)
    raise ValueError(m.provider)


def _build_pipeline_multi(cfg: PipelineConfig) -> Pipeline:
    """Adapter instance per MODEL KEY (aliased) — see pipeline.AliasedModel."""
    keys = {k for k in (cfg.p1_model_key, cfg.p2_model_key,
                        *cfg.reader_model_keys) if k}
    providers = {}
    aliased = {}
    for key in keys:
        m = _MODELS[key]
        providers[key] = _make_provider(m)
        aliased[key] = alias(m)
    scheduler = ProviderScheduler({k: ProviderLimit() for k in keys})
    return Pipeline(cfg, providers, scheduler,
                    resolve_model=lambda k: aliased[k])


def build_draft_from_trust_run(
    tr: TrustRun,
    page_count: int,
    duration_ms: int,
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

    # Trust flags -> annotations. Severity mapping (measured vote ladder):
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
        student_name_suggestion=None,  # identity is excluded by the P1 prompt
        page_count=page_count,
        answers=answers,
        annotations=annotations,
        model_version=TWO_PHASE_ENGINE_VERSION,
        transcription_duration_ms=duration_ms,
    )
