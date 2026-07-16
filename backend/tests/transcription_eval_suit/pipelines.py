"""
SHIM — the pipeline core moved to production
(app/services/transcription/two_phase/pipeline.py); the suite exercises the
same code production runs (one definition). This module preserves the suite's
import surface and injects the suite's model registry as the resolver, so
existing suite code/tests/configs are unchanged.
"""
from __future__ import annotations

from app.services.transcription.scheduler import ProviderScheduler
from app.services.transcription.two_phase.pipeline import (  # noqa: F401 — re-exports
    Pipeline,
    PipelineConfig,
    PipelineRun,
    PdfRenderer,
    ResolvedModel,
    SpecMismatch,
    _default_renderer,
)
from app.services.transcription.vlm_provider import VLMProvider

from .models_registry import spec as model_spec


def build_pipeline(
    cfg: PipelineConfig,
    providers: dict[str, VLMProvider],
    scheduler: ProviderScheduler,
    *,
    pdf_renderer: PdfRenderer = _default_renderer,
) -> Pipeline:
    """Suite-side factory: the registry is the model resolver."""
    return Pipeline(cfg, providers, scheduler,
                    resolve_model=model_spec, pdf_renderer=pdf_renderer)
