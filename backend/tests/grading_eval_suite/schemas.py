"""
Stable schemas for the grading eval suite.

Two families:
  1. Ground-truth types (pydantic) — the on-disk GT artifact [D1][R3][§5 of the
     mission]. Typed so the loader guards are validation, not convention.
  2. Result rows (dataclasses, slots=True) — the results.json shape. slots makes
     a typo'd attribute an AttributeError at write time instead of a silently
     dropped key (the rubric suite's RubricScore precedent).

Decimal policy: all points arithmetic in Decimal; Decimals serialize to JSON as
strings (the app-schema convention). Floats appear only for rates/confidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_serializer


# =============================================================================
# Ground truth [D1] — schema per mission §5
# =============================================================================

class TerminalGT(BaseModel):
    """One owner judgment for one terminal (leaf criterion or sub-criterion)."""
    terminal_id: str
    awarded: Decimal                      # Decimal-string on disk [§5]
    evidence_exists: bool                 # [C-5] credit without quotable evidence is legal, but recorded
    note: Optional[str] = None

    @field_serializer("awarded")
    def _sd(self, v: Decimal) -> str:
        return str(v)


class ScopeUngradable(BaseModel):
    """[C-2] A scope the owner could not grade — the encoding for 'correct model
    behavior is a low-confidence flag, not a guess'. Keyed like selection_scoring's
    ScopeKey: (question_id, sub_question_id-full-path | None)."""
    question_id: str
    sub_question_id: Optional[str] = None
    reason: str


class FixtureGT(BaseModel):
    """The blind-authored teacher grade for one fixture [R1][R3]."""
    fixture: str
    # [two-exam harness] Which exam this GT was authored against. OPTIONAL, and
    # deliberately NOT the routing fact — the fixture manifest routes, and this
    # is CROSS-CHECKED against it (exam_resolution.assert_gt_exam_id_agrees).
    # It earns its place by making a GT file self-describing when read alone;
    # the cross-check is what stops the two copies drifting (§0.4).
    exam_id: Optional[str] = None
    rubric_contract_hash: str             # sha256 of the snapshot file bytes [D5]
    transcription_contract_hash: str      # sha256 of the snapshot file bytes [D5]
    # [M1, owner-ratified 2026-08-25] three provenance classes. v0 GATES on the
    # teacher_validated class per owner ruling; production_approval stays
    # non-gating ([D10] flywheel hook — importer NOT v0).
    gt_source: Literal["teacher_manual", "teacher_validated", "production_approval"]
    authored_by: str
    authored_at: str                      # ISO-8601; the R1 blind-sequencing anchor
    blind: bool                           # [R1] true for teacher_manual; FALSE for teacher_validated [M1]
    proposed_by: Optional[str] = None     # [M1] required for teacher_validated
    validated_by: Optional[str] = None    # [M1] required for teacher_validated
    terminals: List[TerminalGT]
    ungradable_scopes: List[ScopeUngradable] = Field(default_factory=list)


# =============================================================================
# Result rows — results.json shape [§9]
# =============================================================================

@dataclass(slots=True)
class TerminalScore:
    """One terminal's agreement record. Decimals carried as str for JSON stability."""
    terminal_id: str
    question_id: str
    sub_question_id: Optional[str]
    gt_awarded: str
    ai_awarded: str
    delta: str                            # signed: ai - gt [Tier-2]
    abs_delta: str
    within_precision: bool                # |Δ| <= numeric_policy.precision [R4']
    exact: bool                           # Δ == 0
    quote_status: Optional[str]           # exact|fuzzy|not_found | None (no quote emitted)
    ai_confidence: float
    gt_evidence_exists: bool
    ai_flags: List[str] = field(default_factory=list)
    # burden decomposition [Tier-2 edit_burden]
    burden_precision: bool = False        # |Δ| > precision
    burden_evidence: bool = False         # awarded>0 with unverified evidence (None or not_found)
    # [DL-2 SPLIT, owner ruling 2026-08-27] both gate Tier-1, distinct labels:
    #   fabricated = cited ink ABSENT from the answer (trust catastrophe)
    #   stitched   = real ink, non-contiguous, misrepresented as one span
    #                (citation defect: breaks span-highlighting in the review UI)
    fabricated_evidence: bool = False     # [T1-FABRICATED] awarded>0, quote not_found, fragment(s) ABSENT
    evidence_stitched: bool = False       # [T1-STITCHED]   awarded>0, quote not_found, ALL fragments present
    excluded_by_selection: bool = False   # excluded under the GT-side derivation; not in agreement metrics
    # [C-2, ratified 2026-08-24] terminal sits on a GT-ungradable scope: the
    # owner's best-guess award participates in TOTALS only; excluded from all
    # Tier-2 agreement metrics. Row kept + marked for the read-by-hand ritual.
    ungradable_scope: bool = False
    gt_note: Optional[str] = None         # [item 6] owner note incl. [C1-TABLE] markers


@dataclass(slots=True)
class TrialScore:
    """One (fixture, trial) record — the results.json row."""
    fixture: str
    trial_index: int

    # Tier 0 — validity [§6/§7]
    valid: bool = True
    invalid_reason: Optional[str] = None

    # Stamps
    provisional: bool = False             # k=1 or subset — PROVISIONAL in every artifact [§3]
    diagnostic_subset: bool = False       # --scopes mode: Tier-2 totals suppressed
    rerun_count: int = 0                  # [D7] 0 or 1; reason in rerun_reason
    rerun_reason: Optional[str] = None

    # Tier 1 — tripwires (gate from run one) [§6]
    tier1_pass: bool = False
    tier1_failures: List[str] = field(default_factory=list)

    # Per-terminal detail
    terminals: List[TerminalScore] = field(default_factory=list)

    # Tier 2 — agreement (UNGATED-WATCHED) [§6][R4']; None in subset/invalid records
    mae: Optional[float] = None
    within_precision_rate: Optional[float] = None
    exact_rate: Optional[float] = None
    gt_total: Optional[str] = None        # via REAL score_with_selection [§5]
    ai_total: Optional[str] = None
    total_possible: Optional[str] = None  # contract.total_points — never re-derived
    total_delta: Optional[str] = None     # signed, ai - gt
    shippable: Optional[bool] = None      # |total_delta| <= 1.0 [R4']
    gt_pct: Optional[float] = None
    ai_pct: Optional[float] = None
    boundary_flips: List[int] = field(default_factory=list)   # [C-4] boundaries crossed in opposite directions
    edit_burden: Optional[int] = None
    compensating_error: Optional[bool] = None                 # [DL-1] small |total_Δ|, big Σ|Δ|
    exclusion_mismatch: bool = False      # GT-side vs AI-side best-k exclusion sets differ (Tier-3 note)

    # Tier 3 — diagnostics [§6]
    parse_failed_scopes: List[str] = field(default_factory=list)      # [R6] scored, rate escalates
    transport_failed_scopes: List[str] = field(default_factory=list)  # invalidates the trial
    skipped_scopes: List[str] = field(default_factory=list)
    fallback_scopes: List[str] = field(default_factory=list)          # parent_answer_fallback
    skip_agreement_violations: List[str] = field(default_factory=list)  # [T1-SKIP]
    quote_status_counts: Dict[str, int] = field(default_factory=dict)
    graded_by_counts: Dict[str, int] = field(default_factory=dict)

    # Cost / latency [Tier-1 ceiling / Tier-3]
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: Optional[int] = None   # [mission §1.3] provider cache reads
    cost_usd: Optional[float] = None
    latency_s: Optional[float] = None
    per_scope_cost_usd: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SuiteResult:
    provenance: Dict[str, Any]
    trials: List[TrialScore]
    aggregates: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provenance": self.provenance,
            "aggregates": self.aggregates,
            "trials": [t.to_dict() for t in self.trials],
        }
