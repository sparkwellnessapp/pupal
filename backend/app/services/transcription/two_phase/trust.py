"""
trust.py — the trust-layer orchestrator: one PDF through the two-phase
pipeline PLUS the cross-reader disagreement flag layer.

    render once
      ├─ P1 (baseline model)      ┐ concurrent
      └─ readers (diverse models) ┘
      → P2 (segmentation, baseline pages only — readers NEVER feed the draft)
      → flags   = token-diff(baseline, each reader) → severity by vote count
      → anchor  = flag → the draft answer holding its line (else page-level)
      → provenance = answer → source page(s) + confidence
      → lint    = brace balance per answer

Readers influence NOTHING but flags: the draft text is the baseline's verbatim
output (teacher-authority + verbatim contract). Empirical basis and severity
calibration: see flagging.py module docstring.

Shared by the eval suite (trust metrics vs golden set) and production
(TranscriptionDraft annotations).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from ..flagging import FlagSpan, LintFinding, anchor_flags, brace_lint, compute_flags
from ..page_provenance import PageAttribution, align_answer_to_pages
from .instrument import Trace
from .parsing import ExamSpec
from .pipeline import Pipeline, PipelineRun


def answer_target(question_number: int, sub_question_id: str | None) -> str:
    """The one target-id convention ("q1" / "q1.א") — matches the draft
    annotation convention used by the transcription adapter."""
    base = f"q{question_number}"
    return f"{base}.{sub_question_id}" if sub_question_id else base


@dataclass
class TrustRun:
    run: PipelineRun                       # the two-phase result (baseline draft)
    reader_pages: dict[str, dict[int, str]] = field(default_factory=dict)
    flags: tuple[FlagSpan, ...] = ()       # anchored where possible
    attributions: dict[str, PageAttribution] = field(default_factory=dict)
    lint: tuple[LintFinding, ...] = ()

    @property
    def trace(self) -> Trace:
        return self.run.trace


async def run_with_trust(
    pipeline: Pipeline,
    pdf_bytes: bytes,
    doc_id: str,
    exam_spec: ExamSpec,
    *,
    doc_priority: int = 0,
) -> TrustRun:
    """Full two-phase run + trust layer. The reader stage is skipped entirely
    when the config names no readers (plain two-phase behavior)."""
    trace = Trace(doc_id=doc_id)
    images = await pipeline.render(pdf_bytes, trace)

    # Baseline P1 and all readers read the SAME rendered images, concurrently.
    base_task = pipeline._transcribe_pages(  # noqa: SLF001 — package-internal
        images, doc_id, doc_priority, trace)
    readers_task = pipeline.run_readers(
        images, doc_id, doc_priority=doc_priority, trace=trace)
    pages, (reader_pages, _) = await asyncio.gather(base_task, readers_task)

    run = await pipeline.run_phase2(
        pages, exam_spec, doc_id, doc_priority=doc_priority, trace=trace)

    answers_by_target = {
        answer_target(q, sub): text for (q, sub), text in run.answers.items()
    }

    flags = compute_flags(pages, list(reader_pages.values()))
    flags = anchor_flags(flags, answers_by_target)

    attributions = {
        target: align_answer_to_pages(text, pages)
        for target, text in answers_by_target.items()
    }

    return TrustRun(
        run=run,
        reader_pages=reader_pages,
        flags=tuple(flags),
        attributions=attributions,
        lint=tuple(brace_lint(answers_by_target)),
    )
