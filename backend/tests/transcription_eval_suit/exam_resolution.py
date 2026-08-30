"""
exam_resolution.py — which EXAM does a fixture answer, and which PROFILE scores it.

The suite used to answer both questions once per RUN: one `--exam-spec` handed
to every fixture, one hardcoded `JAVA_BAGRUT`. That was true while the corpus
was one exam and false the moment a second one existed. The exam is a property
of the FIXTURE — a fact about the paper, not about the run.

RESOLUTION, per doc_id, in order:

  1. `fixtures/<doc_id>.json` — the per-fixture manifest. Names a shared exam
     artifact by relative path, plus an optional profile:

         {"exam_spec": "exams/hobby_tvshow.json",
          "profile": "java_bagrut",          # optional; default java_bagrut
          "provenance": {...}}               # free-form, never routed on

  2. the run-level `--exam-spec` — TODAY'S BEHAVIOUR, unchanged. With no
     manifests on disk every existing invocation (check_goal.sh, the whole
     RUNLOG history, the eval gate) resolves byte-identically and needs zero
     new files.

  3. nothing — legal only for `p1_only`, which transcribes pages and has no
     question skeleton to route into.

WHY A MANIFEST AND NOT A SPEC COPY PER DOC (amends BACKLOG B-30f): the tree
already states doc_id -> {pdf, raw GT, draft GT} by basename, and this module
does not restate any of that. It carries only the one fact the tree is silent
about. A full spec copy per doc would put N byte-identical copies of one exam
in the tree — the same two-copies-drift shape that produced GT findings F-1..F-3
(GT_ARTIFACTS_REPORT.md §8), and invisible in results.json. The sibling grading
suite ruled the same way first, for the same reason
(grading_eval_suite/fixtures.py: "pairing is a manifest fact, never basename
magic across directories").

Every failure here is LOUD. A manifest that names a missing spec, an unknown
profile, or omits `exam_spec` raises — a fixture scored against the wrong
question skeleton is a silently wrong benchmark, which is worse than a crash.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .critical_tokens import CriticalProfile
from .parsing import ExamSpec, load_exam_spec, spec_from_rubric_draft
from .profiles import DEFAULT_PROFILE, profile as resolve_profile

SUITE_DIR = Path(__file__).parent
MANIFEST_DIR_NAME = "fixtures"
EXAMS_DIR_NAME = "exams"


@dataclass(frozen=True)
class ResolvedExam:
    """What scored a fixture, and the provenance to prove it in results.json."""
    spec: ExamSpec
    ref: str                      # path as written (relative to the suite dir when possible)
    sha256: str                   # content pin — two fixtures on one exam must agree
    profile_name: str
    profile: CriticalProfile
    meta: dict = field(default_factory=dict)   # rubric_name, selection_groups

    def as_provenance(self) -> dict:
        out = {
            "exam_spec": self.ref,
            "exam_spec_sha256": self.sha256,
            "profile": self.profile_name,
        }
        out.update(self.meta)
        return out


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative_ref(path: Path, root: Path) -> str:
    """Suite-relative when the artifact lives in the tree; absolute otherwise.

    Anchored on the root actually in use, not the module-level SUITE_DIR — the
    ref is what results.json records, and a run against another tree must record
    that tree's paths, not paths that only look right by coincidence."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def load_spec_file(path: Path) -> ExamSpec:
    """Canonical harness spec, or a rubric draft_json drop-in.

    The tolerance is deliberate and unchanged from the runner's historical
    `load_spec`: production builds its ExamSpec from a rubric draft_json
    (`two_phase_engine::spec_from_rubric_draft_data`), so a verbatim export of
    the teacher's rubric is the production-faithful artifact to score against.
    KeyError: a rubric draft lacks the canonical "number" key, so the strict
    loader trips before the fallback could run. Both shapes drop in."""
    try:
        return load_exam_spec(path)
    except (ValueError, KeyError):
        return spec_from_rubric_draft(path)


def exam_meta(path: Path) -> dict:
    """Provenance the runner RECORDS but never ROUTES on.

    `selection_groups` is the one that matters today: on a choose-k-of-N exam
    the student is *expected* to leave whole questions blank, so a reader of
    results.json must be able to tell an empty answer that is correct by design
    from one that is a segmentation failure. Recording it does not change any
    prompt or any score — making P2 selection-AWARE would, and that is a
    separate single-variable experiment (CLAUDE.md §17.3)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    meta: dict = {}
    name = data.get("rubric_name") or data.get("name")
    if isinstance(name, str) and name.strip():
        meta["exam_name"] = name.strip()
    groups = data.get("selection_groups")
    if isinstance(groups, list) and groups:
        meta["selection_groups"] = [
            {
                "group_id": g.get("group_id"),
                "choose_k": g.get("choose_k"),
                "of_question_ids": g.get("of_question_ids"),
            }
            for g in groups
            if isinstance(g, dict)
        ]
    return meta


def read_manifest(doc_id: str, *, suite_dir: Path | None = None) -> dict | None:
    """The per-fixture manifest, or None when the fixture has none."""
    root = suite_dir or SUITE_DIR
    path = root / MANIFEST_DIR_NAME / f"{doc_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{doc_id}: fixture manifest {path} is not valid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise ValueError(f"{doc_id}: fixture manifest {path} must be a JSON object.")
    return data


def resolve_exam(
    doc_id: str,
    *,
    fallback_spec_path: str | None = None,
    suite_dir: Path | None = None,
) -> ResolvedExam | None:
    """Resolve (exam spec, profile) for one fixture. Returns None when neither a
    manifest nor a run-level spec exists — legal for p1_only only; the caller
    enforces that, because only it knows the mode."""
    root = suite_dir or SUITE_DIR
    manifest = read_manifest(doc_id, suite_dir=root)

    if manifest is not None:
        ref = manifest.get("exam_spec")
        if not isinstance(ref, str) or not ref.strip():
            raise ValueError(
                f"{doc_id}: fixture manifest must name an 'exam_spec' "
                f"(a path relative to {root.name}/, e.g. "
                f"\"{EXAMS_DIR_NAME}/<exam>.json\")."
            )
        ref = ref.strip()
        path = root / ref
        if not path.exists():
            raise FileNotFoundError(
                f"{doc_id}: manifest names exam_spec {ref!r}, but {path} does not exist."
            )
        profile_name = manifest.get("profile") or DEFAULT_PROFILE
        if not isinstance(profile_name, str):
            raise ValueError(f"{doc_id}: manifest 'profile' must be a string.")
        return ResolvedExam(
            spec=load_spec_file(path),
            ref=_relative_ref(path, root),
            sha256=_sha256_file(path),
            profile_name=profile_name,
            profile=resolve_profile(profile_name),   # unknown key raises here
            meta=exam_meta(path),
        )

    if fallback_spec_path:
        path = Path(fallback_spec_path)
        if not path.is_absolute():
            path = root / path
        if not path.exists():
            raise FileNotFoundError(
                f"{doc_id}: no fixtures/{doc_id}.json manifest and the run-level "
                f"--exam-spec {fallback_spec_path!r} does not exist at {path}."
            )
        return ResolvedExam(
            spec=load_spec_file(path),
            ref=_relative_ref(path, root),
            sha256=_sha256_file(path),
            profile_name=DEFAULT_PROFILE,
            profile=resolve_profile(DEFAULT_PROFILE),
            meta=exam_meta(path),
        )

    return None


def spec_keys(spec: ExamSpec) -> list[tuple[int, str | None]]:
    """The answer keys an exam declares, in spec order — the same key set
    `spans.spec_targets` builds, so GT authored against it lines up with what
    P2 is asked to produce. A question with no sub-questions contributes one
    whole-question key `(n, None)`."""
    from .keys import normalize_key

    out: list[tuple[int, str | None]] = []
    for question in spec.questions:
        if question.sub_questions:
            out.extend(
                normalize_key((question.number, sq.id)) for sq in question.sub_questions
            )
        else:
            out.append(normalize_key((question.number, None)))
    return out
