"""
Fixture assembly + ground-truth guards [§4/§5 of the mission].

A fixture is the triple (rubric contract, transcription contract, teacher GT),
paired by a PER-FIXTURE manifest `fixtures/<name>.json` [F3 — the B-30f lesson
pre-applied: grading is inherently multi-exam, so pairing is a manifest fact,
never basename magic across directories].

The terminal universe comes from the REAL `gradable_compiler.compile` — one
definition of what a terminal is [§3]. GT validation is loud and total [§5]:
totality, bounds, precision grid, contract-hash pinning [D5], blind flag [R1].

R1 blind sequencing is mechanical here: `assert_blind_sequencing` refuses to
score a fixture whose GT was authored AFTER any cached grader draft for it
existed — authoring-after-seeing is the violation R1 exists to prevent.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.gradable import GradableTest
from app.schemas.ontology_types import GradingRubricContract
from app.schemas.transcription import TranscriptionContract
from app.services.gradable_compiler import compile as compile_gradable

from .exam_resolution import (
    ExamResolutionError,
    assert_gt_exam_id_agrees,
    manifest_exam_id,
)
from .schemas import FixtureGT

logger = logging.getLogger(__name__)

SUITE_DIR = Path(__file__).resolve().parent

ScopeKey = Tuple[str, Optional[str]]


class GTValidationError(Exception):
    """A ground-truth artifact failed a loader guard [§5]. Always fatal."""


class BlindSequencingError(Exception):
    """[R1] GT authored after a cached grader draft existed for the fixture."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Terminal universe — from the real compiler, one definition [§3]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TerminalInfo:
    terminal_id: str
    question_id: str
    sub_question_id: Optional[str]      # full path within the question, or None
    points: Decimal

    @property
    def scope_key(self) -> ScopeKey:
        return (self.question_id, self.sub_question_id)


def terminal_universe(gradable_test: GradableTest) -> Dict[str, TerminalInfo]:
    """Every leaf grading unit, keyed by terminal id. Mirrors the grader's own
    terminal semantics (sub-criteria are the terminals when present)."""
    infos: Dict[str, TerminalInfo] = {}
    for scope in gradable_test.scopes:
        for criterion in scope.criteria:
            if criterion.sub_criteria:
                for sc in criterion.sub_criteria:
                    infos[sc.sub_criterion_id] = TerminalInfo(
                        sc.sub_criterion_id, scope.question_id,
                        scope.sub_question_id, sc.points)
            else:
                infos[criterion.criterion_id] = TerminalInfo(
                    criterion.criterion_id, scope.question_id,
                    scope.sub_question_id, criterion.points)
    return infos


# ---------------------------------------------------------------------------
# Bundle
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FixtureBundle:
    name: str
    rubric_contract: GradingRubricContract
    transcription_contract: TranscriptionContract
    gradable_test: GradableTest
    terminal_infos: Dict[str, TerminalInfo]
    gt: Optional[FixtureGT]
    rubric_contract_hash: Optional[str] = None
    transcription_contract_hash: Optional[str] = None
    manifest: Dict[str, Any] = field(default_factory=dict)
    # [two-exam harness] Which exam this fixture answers, from its manifest.
    # THE routing fact — the runner resolves this fixture's plan by it. None on
    # a legacy manifest that predates the key, which resolves via the run-level
    # `config["plan"]` exactly as before.
    exam_id: Optional[str] = None

    @property
    def scope_keys(self) -> List[ScopeKey]:
        return [(s.question_id, s.sub_question_id) for s in self.gradable_test.scopes]


def _validate_gt(gt: FixtureGT, bundle_name: str,
                 infos: Dict[str, TerminalInfo],
                 scope_keys: List[ScopeKey],
                 precision: Decimal,
                 rubric_hash: Optional[str],
                 transcription_hash: Optional[str]) -> None:
    """The loader guards [§5]. Every failure names the fixture and the rule."""
    # [D5] contract-hash pinning: a recompiled rubric cannot silently invalidate
    # the GT authored against it. Enforced whenever expected hashes are known
    # (file-loaded bundles always know them; object-level tests may not).
    if rubric_hash is not None and gt.rubric_contract_hash != rubric_hash:
        raise GTValidationError(
            f"{bundle_name}: GT hash pin failed — gt.rubric_contract_hash does not "
            f"match the snapshot file (D5). Re-authoring against a changed contract "
            f"is an OWNER decision, never silent.")
    if transcription_hash is not None and gt.transcription_contract_hash != transcription_hash:
        raise GTValidationError(
            f"{bundle_name}: GT hash pin failed for the transcription contract (D5).")

    # [R1] blind flag required for teacher_manual GT
    if gt.gt_source == "teacher_manual" and not gt.blind:
        raise GTValidationError(
            f"{bundle_name}: gt_source=teacher_manual requires blind: true (R1).")

    # [M1, owner-ratified 2026-08-25] teacher_validated: agent-proposed,
    # owner-validated — honestly non-blind, with both parties on record.
    # v0 gates on this class per owner ruling.
    if gt.gt_source == "teacher_validated":
        if gt.blind:
            raise GTValidationError(
                f"{bundle_name}: gt_source=teacher_validated requires blind: false "
                f"(M1) — a validated GT must not claim blindness.")
        if not gt.proposed_by or not gt.validated_by:
            raise GTValidationError(
                f"{bundle_name}: gt_source=teacher_validated requires proposed_by "
                f"AND validated_by (M1 attribution).")

    # duplicates
    seen: set = set()
    for t in gt.terminals:
        if t.terminal_id in seen:
            raise GTValidationError(
                f"{bundle_name}: duplicate terminal {t.terminal_id!r} in GT.")
        seen.add(t.terminal_id)

    # totality — every contract terminal exactly once, nothing extra (D3-analog)
    universe = set(infos)
    missing = universe - seen
    extra = seen - universe
    if missing or extra:
        raise GTValidationError(
            f"{bundle_name}: GT totality violated — missing={sorted(missing)} "
            f"extra={sorted(extra)}.")

    # bounds + precision grid
    for t in gt.terminals:
        possible = infos[t.terminal_id].points
        if not (Decimal("0") <= t.awarded <= possible):
            raise GTValidationError(
                f"{bundle_name}: GT bounds violated at {t.terminal_id}: "
                f"awarded={t.awarded} possible={possible}.")
        if (t.awarded % precision) != 0:
            raise GTValidationError(
                f"{bundle_name}: GT precision-grid violated at {t.terminal_id}: "
                f"awarded={t.awarded} is not a multiple of {precision}.")

    # ungradable scopes must reference real scopes [C-2]
    valid_keys = set(scope_keys)
    for u in gt.ungradable_scopes:
        if (u.question_id, u.sub_question_id) not in valid_keys:
            raise GTValidationError(
                f"{bundle_name}: ungradable scope ({u.question_id}, "
                f"{u.sub_question_id}) names no contract scope.")


def assemble_bundle(name: str,
                    rubric_contract: GradingRubricContract,
                    transcription_contract: TranscriptionContract,
                    gt: Optional[FixtureGT] = None,
                    *,
                    rubric_hash: Optional[str] = None,
                    transcription_hash: Optional[str] = None,
                    manifest: Optional[Dict[str, Any]] = None,
                    exam_id: Optional[str] = None) -> FixtureBundle:
    """Object-level assembly (tests + tools). Compiles the REAL GradableTest and
    validates the GT against it when present."""
    gradable = compile_gradable(rubric_contract, transcription_contract)
    infos = terminal_universe(gradable)
    scope_keys = [(s.question_id, s.sub_question_id) for s in gradable.scopes]
    if gt is not None:
        # The manifest routes; a GT that names its own exam must AGREE (§0.4 —
        # two sources of one fact are only safe when a disagreement is loud).
        assert_gt_exam_id_agrees(name, exam_id, getattr(gt, "exam_id", None))
        _validate_gt(gt, name, infos, scope_keys,
                     rubric_contract.numeric_policy.precision,
                     rubric_hash, transcription_hash)
    return FixtureBundle(
        name=name, rubric_contract=rubric_contract,
        transcription_contract=transcription_contract,
        gradable_test=gradable, terminal_infos=infos, gt=gt,
        rubric_contract_hash=rubric_hash,
        transcription_contract_hash=transcription_hash,
        manifest=manifest or {},
        exam_id=exam_id)


_MANIFEST_REQUIRED = ("rubric_contract", "transcription_contract", "gt")


def _authoring_progress(gt_path: Path) -> Optional[str]:
    """How far along a half-authored GT is, if that is why it failed to parse."""
    try:
        raw = json.loads(gt_path.read_text(encoding="utf-8"))
        terminals = raw.get("terminals") or []
    except (OSError, json.JSONDecodeError, AttributeError):
        return None
    if not terminals:
        return None
    unfilled = [t.get("terminal_id") for t in terminals
                if isinstance(t, dict) and t.get("awarded") is None]
    if not unfilled:
        return None
    placeholder = str(raw.get("authored_at") or "").startswith("FILL")
    return (f"GT is still being authored — {len(terminals) - len(unfilled)}"
            f"/{len(terminals)} terminals have an award; "
            f"{len(unfilled)} still null (first: {unfilled[0]})"
            + ("; authored_at is still the placeholder" if placeholder else ""))


def load_bundle(name: str, *, suite_dir: Path = SUITE_DIR,
                require_gt: bool = True) -> FixtureBundle:
    """File-level assembly from `fixtures/<name>.json` [F3].

    `require_gt=False` means STRUCTURE ONLY: a GT that is absent, or present but
    not yet finished, yields `gt=None` rather than an exception. That is what
    lets a tool or a structural test work on a fixture while its GT is being
    authored — the state exam 2 is in for as long as the authoring takes."""
    manifest_path = suite_dir / "fixtures" / f"{name}.json"
    if not manifest_path.exists():
        raise GTValidationError(f"{name}: no fixture manifest at {manifest_path}.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key in _MANIFEST_REQUIRED:
        if key not in manifest:
            raise GTValidationError(f"{name}: manifest missing {key!r}.")

    rc_path = suite_dir / manifest["rubric_contract"]
    tc_path = suite_dir / manifest["transcription_contract"]
    gt_path = suite_dir / manifest["gt"]
    rubric_contract = GradingRubricContract.model_validate_json(
        rc_path.read_text(encoding="utf-8"))
    transcription_contract = TranscriptionContract.model_validate_json(
        tc_path.read_text(encoding="utf-8"))

    gt: Optional[FixtureGT] = None
    if gt_path.exists():
        try:
            gt = FixtureGT.model_validate_json(gt_path.read_text(encoding="utf-8"))
        except Exception as exc:                              # noqa: BLE001
            # A GT skeleton is filled in over a long authoring session, so
            # "present but not finished" is a NORMAL state, not a corrupt file.
            # Pydantic answers it with one error per unfilled field — 30+ lines
            # that bury the one fact the author needs, which is how many
            # terminals are left. The skeleton's own _instructions promise "the
            # loader refuses partial files — that is the completion check", so
            # this is that check finally saying something useful.
            detail = _authoring_progress(gt_path) or str(exc)[:200]
            if require_gt:
                raise GTValidationError(f"{name}: {detail}") from None
            logger.warning("gt_not_ready", extra={"fixture": name, "detail": detail})
    elif require_gt:
        # [R1] no grade-mode run on a fixture until its GT file is committed.
        raise GTValidationError(
            f"{name}: R1 — no GT at {gt_path}; grade mode is refused until the "
            f"owner's blind GT is committed.")

    return assemble_bundle(
        name, rubric_contract, transcription_contract, gt,
        rubric_hash=sha256_file(rc_path),
        transcription_hash=sha256_file(tc_path),
        manifest=manifest,
        exam_id=manifest_exam_id(name, suite_dir=suite_dir))


# ---------------------------------------------------------------------------
# [R1] blind sequencing
# ---------------------------------------------------------------------------

_RUN_DIR_TS_RE = re.compile(r"^(\d{8}-\d{6})_")


def _run_dir_timestamp(dirname: str) -> Optional[datetime]:
    m = _RUN_DIR_TS_RE.match(dirname)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d-%H%M%S")
    except ValueError:
        return None


def assert_blind_sequencing(fixture: str, gt: FixtureGT, results_dir: Path) -> None:
    """[R1] Refuse to score when the GT was authored AFTER any cached grader
    draft for this fixture already existed — the owner could have seen output.
    The draft's run timestamp comes from its results-dir name (runner-stamped)."""
    try:
        authored = datetime.fromisoformat(gt.authored_at)
    except ValueError as e:
        raise GTValidationError(
            f"{fixture}: GT authored_at {gt.authored_at!r} is not ISO-8601: {e}")
    if not results_dir.exists():
        return
    for run_dir in results_dir.iterdir():
        ts = _run_dir_timestamp(run_dir.name)
        if ts is None:
            continue
        drafts = run_dir / "drafts"
        if not drafts.exists():
            continue
        if any(drafts.glob(f"{fixture}_r*.json")) and ts < authored:
            raise BlindSequencingError(
                f"{fixture}: R1 blind-sequencing violation — GT authored_at "
                f"{gt.authored_at} POSTDATES cached grader drafts in "
                f"{run_dir.name}. A GT authored after grader output existed is "
                f"not blind; surface to the owner, do not score.")
