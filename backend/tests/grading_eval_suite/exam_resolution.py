"""
exam_resolution.py — which EXAM does a fixture answer, and which PLAN grades it.

The suite used to answer the second question once per RUN: one `config["plan"]`
handed to every fixture, and run-level provenance read off `bundles[0]`. That
was true while the corpus was one exam and false the moment a second one
existed. **The exam is a property of the FIXTURE** — a fact about the paper, not
about the run.

This is the sibling of `transcription_eval_suit/exam_resolution.py` and follows
it deliberately (owner steer 2026-09-03: that suite already solved this; its
registry/resolution design is the reference, not a thing to reinvent).

RESOLUTION, per fixture, in order:

  1. `fixtures/<name>.json` names an `exam_id`, and the config maps it:

         # fixtures/din_ezra.json
         {"exam_id": "hobby_tvshow", "rubric_contract": ..., ...}

         # configs/<name>.json
         {"plans": {"hobby_tvshow": "plans/hobby_tvshow.plan.json",
                    "bagrut_899371": "plans/bagrut_899371.plan.json"}}

  2. the run-level `config["plan"]` — TODAY'S BEHAVIOUR, unchanged. A one-exam
     corpus resolves byte-identically and every existing config needs zero edits.

  3. nothing — the caller refuses (v5 requires a plan; only it knows the mode).

WHY A SHARED ARTIFACT NAMED BY PATH, not a plan copy per fixture: five fixtures
answer one exam, so a copy each would put five byte-identical plans in the tree —
the two-copies-drift shape that produced GT findings F-1..F-3, and invisible in
results.json.

WHERE THIS DIFFERS FROM THE REFERENCE, deliberately: the transcription suite
sha-pins its exam spec so that "two fixtures on one exam must agree". Grading
does not need that, because it already has a STRONGER pin — `_load_plan` refuses
when `plan.rubric_contract_sha256` does not match the fixture's own contract
snapshot, per fixture. The sha here is recorded as provenance, not used to route.

Every failure is LOUD. A fixture graded under another exam's plan is a silently
wrong benchmark, which is worse than a crash.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

SUITE_DIR = Path(__file__).resolve().parent
MANIFEST_DIR_NAME = "fixtures"

#: The manifest key that routes. Free-form `provenance.exam` prose ("hobby_tvshow
#: (corrected, H1-ratified)") is NOT this and is never routed on.
EXAM_ID_KEY = "exam_id"


class ExamResolutionError(Exception):
    """A fixture could not be routed to a plan. Always fatal, always pre-spend."""


@dataclass(frozen=True)
class ResolvedPlan:
    """Which plan graded a fixture, and the provenance to prove it."""
    exam_id: Optional[str]        # None only on the legacy run-level path
    ref: str                      # suite-relative path as written
    sha256: str                   # content pin, recorded (see module docstring)
    path: Path

    def as_provenance(self) -> Dict[str, Any]:
        return {"exam_id": self.exam_id, "plan": self.ref, "plan_sha256": self.sha256}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative_ref(path: Path, root: Path) -> str:
    """Suite-relative when the artifact lives in the tree; absolute otherwise.

    Anchored on the root ACTUALLY IN USE, not the module-level SUITE_DIR — the
    ref is what results.json records, and a run against another tree (every
    tmp_path test) must record that tree's paths, not paths that only look right
    by coincidence."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def read_manifest(name: str, *, suite_dir: Optional[Path] = None) -> Optional[dict]:
    """The per-fixture manifest, or None when the fixture has none."""
    root = suite_dir or SUITE_DIR
    path = root / MANIFEST_DIR_NAME / f"{name}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExamResolutionError(
            f"{name}: fixture manifest {path} is not valid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise ExamResolutionError(
            f"{name}: fixture manifest {path} must be a JSON object.")
    return data


def manifest_exam_id(name: str, *, suite_dir: Optional[Path] = None) -> Optional[str]:
    """The exam a fixture declares, or None (legacy manifests predate the key)."""
    manifest = read_manifest(name, suite_dir=suite_dir)
    if manifest is None:
        return None
    value = manifest.get(EXAM_ID_KEY)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ExamResolutionError(
            f"{name}: manifest {EXAM_ID_KEY!r} must be a non-empty string.")
    return value.strip()


def resolve_plan(exam_id: Optional[str], config: dict, *,
                 fixture: str = "<fixture>",
                 suite_dir: Optional[Path] = None) -> Optional[ResolvedPlan]:
    """(exam_id, config) -> the plan that grades it. None when the config names
    no plan at all — the CALLER refuses, because only it knows whether the
    architecture requires one."""
    root = suite_dir or SUITE_DIR
    plans = config.get("plans")

    if plans is not None:
        if not isinstance(plans, dict):
            raise ExamResolutionError(
                "config 'plans' must be an object mapping exam_id -> plan path.")
        if exam_id is None:
            raise ExamResolutionError(
                f"{fixture}: the config maps plans by exam_id "
                f"({sorted(plans)}), but this fixture's manifest declares no "
                f"{EXAM_ID_KEY!r}. A fixture that cannot name its exam cannot be "
                f"routed to a plan — add the key rather than guessing.")
        ref = plans.get(exam_id)
        if not ref:
            raise ExamResolutionError(
                f"{fixture}: no plan for exam_id {exam_id!r} — the config maps "
                f"{sorted(plans)}. Grading it under another exam's plan is a "
                f"silently wrong benchmark, so this refuses instead.")
        path = root / ref
        if not path.exists():
            raise ExamResolutionError(
                f"{fixture}: config maps exam {exam_id!r} to {ref!r}, but "
                f"{path} does not exist.")
        return ResolvedPlan(exam_id=exam_id, ref=_relative_ref(path, root),
                            sha256=_sha256_file(path), path=path)

    # Legacy single-plan path — byte-identical to the pre-two-exam behaviour.
    ref = config.get("plan")
    if not ref:
        return None
    path = root / ref
    if not path.exists():
        raise ExamResolutionError(
            f"{fixture}: config names plan {ref!r}, but {path} does not exist.")
    return ResolvedPlan(exam_id=exam_id, ref=_relative_ref(path, root),
                        sha256=_sha256_file(path), path=path)


def assert_gt_exam_id_agrees(fixture: str, manifest_exam: Optional[str],
                            gt_exam: Optional[str]) -> None:
    """The manifest ROUTES; a GT's own `exam_id` is CROSS-CHECKED.

    Two sources of one fact is the drift shape §0.4 forbids, and the answer is
    not to delete one — a GT file that names its exam is self-describing when
    read alone, which is worth having. The answer is that they must AGREE, and
    that a disagreement is loud. Same discipline as the D5 contract-hash pin.
    """
    if gt_exam is None or manifest_exam is None:
        return
    if gt_exam != manifest_exam:
        raise ExamResolutionError(
            f"{fixture}: GT declares exam_id {gt_exam!r} but the fixture "
            f"manifest routes it to {manifest_exam!r}. One of the two is wrong "
            f"and scoring either way would benchmark the wrong pairing.")
