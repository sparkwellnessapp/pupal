"""
Stable result schema for the rubric eval suite.

`results.json` is the regression-gate input; its shape must stay stable across
runs so a later thread (or CI) can diff two runs mechanically. Provenance
(fixtures, config, prompt_version, model_versions) is stamped on every run —
a result is a function of (fixtures, config, prompt_version, model_versions),
all four recorded, mirroring the transcription suite's provenance principle.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class CriterionMatchRecord:
    """One criterion (or sub-criterion) alignment outcome."""
    status: str                      # 'matched' | 'missed' | 'spurious'
    gt_description: Optional[str] = None
    pred_description: Optional[str] = None
    gt_points: Optional[str] = None  # Decimal serialized as str
    pred_points: Optional[str] = None
    text_ratio: Optional[float] = None
    points_exact: Optional[bool] = None
    attribution: Optional[str] = None   # for 'missed': 'render_loss' | 'extraction_loss'
    merge_suspected: bool = False


@dataclass
class ScopeScore:
    """Per-scope (question / sub-question / sub-sub-question) detail for the report."""
    scope_id: str
    kind: str                        # 'question' | 'sub_question' | 'sub_sub_question'
    structure_status: str            # 'ok' | 'leaf_vs_branch' | 'missing' | 'extra'
    # text fidelity: None <=> GT has no text at this node (not-comparable);
    # 0.0 <=> GT has text and the prediction has none (a real miss)
    text_ratio: Optional[float] = None
    text_line_recall: Optional[float] = None
    points_gt: Optional[str] = None
    points_pred: Optional[str] = None
    points_exact: Optional[bool] = None
    solution_status: Optional[str] = None   # 'ok'|'missing'|'spurious'|'na'
    solution_ratio: Optional[float] = None
    criterion_matches: List[CriterionMatchRecord] = field(default_factory=list)
    subcriterion_matches: List[CriterionMatchRecord] = field(default_factory=list)


@dataclass
class AnnotationCheck:
    annotation_type: str
    target_id: Optional[str]


@dataclass
class StageTiming:
    """One pipeline progress event (from the docx_v3 `on_progress` seam), captured
    by the runner. `elapsed_s` = cumulative pipeline wall-clock at emission;
    `dt_s` = duration of the step that just ended (delta from the previous event).

    PURELY ADDITIVE latency instrument (Phase 0). Never read by the scorer or the
    gate — it exists only so `results.json` carries the per-step latency
    decomposition the mission's latency model needs. A `score_only` re-score leaves
    it empty (no pipeline timing), which is exactly what keeps score_only outputs
    byte-identical to a pre-instrument run on the gated fields.
    """
    stage: str
    attempt: Optional[int] = None
    elapsed_s: Optional[float] = None
    dt_s: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


@dataclass(slots=True)
class RubricScore:
    # slots=True: this record has ~40 declared fields and is the results.json row.
    # Slots make a typo'd `rs.pedagigical_match = ...` an AttributeError at write time
    # instead of a silently-dropped attribute that never reaches asdict() — the exact
    # class of drift that hid the pedagogical fields from a prior run's artifacts.
    rubric_name: str
    valid: bool
    invalid_reason: Optional[str] = None

    # structural
    question_recall: float = 0.0
    question_precision: float = 0.0
    subquestion_structure_match: float = 0.0
    criterion_recall: float = 0.0
    criterion_precision: float = 0.0
    subcriterion_recall: float = 0.0
    subcriterion_precision: float = 0.0

    # points
    point_exactness: float = 0.0
    total_points_correct: bool = False
    rubric_total_gt: Optional[str] = None
    rubric_total_pred: Optional[str] = None

    # selection (FP1)
    selection_match: bool = False
    achievable_points_gt: Optional[str] = None
    achievable_points_pred: Optional[str] = None
    achievable_points_correct: bool = False

    # example solution (gate-blocking per lock)
    example_solution_fidelity: float = 0.0

    # question/sub-question text fidelity (UNGATED DIAGNOSTIC — deliberately NOT
    # a gate_pass criterion; the gate threshold, if one is ever added, is to be
    # pre-registered from the measured distribution, never guessed).
    # Worst-node aggregation over nodes WITH GT text; None when no such nodes.
    question_text_fidelity_min: Optional[float] = None
    subquestion_text_fidelity_min: Optional[float] = None
    text_line_recall_min: Optional[float] = None

    # annotations (faithful-teacher-error)
    annotation_match: bool = False
    expected_annotations: List[AnnotationCheck] = field(default_factory=list)
    missing_annotations: List[AnnotationCheck] = field(default_factory=list)
    spurious_annotations: List[AnnotationCheck] = field(default_factory=list)

    # pedagogical mistakes (Step 2c) — same set-comparison shape as annotations.
    # Reuses AnnotationCheck(annotation_type=kind, target_id) rather than a parallel
    # type. Zero-mistake GTs make this the false-positive guard for the detector.
    pedagogical_match: bool = False
    expected_pedagogical: List[AnnotationCheck] = field(default_factory=list)
    missing_pedagogical: List[AnnotationCheck] = field(default_factory=list)
    spurious_pedagogical: List[AnnotationCheck] = field(default_factory=list)

    # health (NOT gated — the rubric may be legitimately inconsistent)
    point_sum_consistency: bool = True
    consistency_violations: List[str] = field(default_factory=list)

    # attribution (render vs extraction)
    render_loss_count: int = 0
    extraction_loss_count: int = 0

    # cost / provenance per record
    cost_usd: Optional[float] = None
    llm_seconds: Optional[float] = None
    retry_count: Optional[int] = None
    finish_reason: Optional[str] = None
    model_version: Optional[str] = None
    prompt_version: Optional[str] = None
    repeat_index: int = 0

    # ---- latency instrument (Phase 0 — ADDITIVE, UNGATED, WATCHED) -------------
    # t_doc = total_seconds (pipeline entry → returned ExtractRubricResponse).
    # Populated by the RUNNER after scoring — the scorer (immutable) never sets
    # these. All Optional/None-defaulted so a score_only re-score (no pipeline)
    # produces the same gated-field values as a pre-instrument run.
    total_seconds: Optional[float] = None     # t_doc (pipeline internal, time.time)
    render_seconds: Optional[float] = None    # t_render_local
    wall_seconds: Optional[float] = None       # runner-side monotonic wrap (incl.
                                               # thread dispatch) — instrument cross-check
    input_tokens: Optional[int] = None         # cumulative across chain steps + retries
    output_tokens: Optional[int] = None        # cumulative decode (incl. reasoning tokens)
    stage_timings: List[StageTiming] = field(default_factory=list)

    # infra warnings/errors (B4) — pipeline warnings, render-annotation-loss audit,
    # Tier-B transport failures. A gate-flipping infrastructure failure must
    # self-announce in the artifacts, not live only in stdout (the Tier B 400 was
    # invisible in results.json/reports for the detector's entire life).
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    # gate
    gate_pass: bool = False
    gate_failures: List[str] = field(default_factory=list)

    # detail (for report_<rubric>.md)
    scopes: List[ScopeScore] = field(default_factory=list)
    missed_criteria: List[CriterionMatchRecord] = field(default_factory=list)
    spurious_criteria: List[CriterionMatchRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SuiteResult:
    provenance: Dict[str, Any]
    per_rubric: List[RubricScore]
    aggregates: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provenance": self.provenance,
            "aggregates": self.aggregates,
            "per_rubric": [r.to_dict() for r in self.per_rubric],
        }