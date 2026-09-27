"""
D-5 (GRADER_V6_CENSUS Appendix E; owner ruling Track B 1, 2026-09-27) — every
artifact a fixture manifest names is COMMITTED, BYTE-STABLE, and PINNED.

The bagrut exam could not run from a clean checkout of `main`: its rubric
contract and seven transcription contracts sat at the suite root, where
`backend/.gitignore`'s blanket `*.json` swallowed them, so they existed only in
one shared working tree. Every harness test that loads exam 2 therefore failed
on a fresh clone with a FileNotFoundError, and nothing said why.

Three properties, one per way that can come back:

  1. the file exists and its sha256 equals the pin its GT records (D5);
  2. git will not ignore it (a new artifact dropped outside the negations is
     silently left out of the next commit — the original defect);
  3. git will never EOL-convert it (`core.autocrlf` rewrites CRLF on the way
     in, so the committed bytes — and every GT hash pin with them — would differ
     from the bytes the pin was taken over; invisible on the machine that
     committed, fatal on every other one).

Committing students' work to the public repositories is ruled: OD-B10
(docs/PURGE_CENSUS.md) — "Closed, no action (2026-09-23)".
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

import pytest

from .fixtures import SUITE_DIR, sha256_file

_ARTIFACT_KEYS = ("rubric_contract", "transcription_contract", "gt")
_PIN_KEYS = (("rubric_contract", "rubric_contract_hash"),
             ("transcription_contract", "transcription_contract_hash"))


def _manifests() -> List[Tuple[str, dict]]:
    return [(p.stem, json.loads(p.read_text(encoding="utf-8")))
            for p in sorted((SUITE_DIR / "fixtures").glob("*.json"))]


def _artifact_relpaths() -> List[str]:
    """Every manifest-referenced artifact, suite-relative — existing or not
    (git's pattern rules answer for a path whether or not it is on disk)."""
    out = set()
    for _name, manifest in _manifests():
        for key in _ARTIFACT_KEYS:
            out.add(manifest[key])
    return sorted(out)


def _git(*args: str) -> subprocess.CompletedProcess:
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not available")
    probe = subprocess.run([git, "rev-parse", "--is-inside-work-tree"], cwd=SUITE_DIR,
                           capture_output=True, text=True)
    if probe.returncode != 0:
        pytest.skip("not a git checkout")
    return subprocess.run([git, *args], cwd=SUITE_DIR, capture_output=True, text=True,
                          encoding="utf-8")


def test_every_manifest_contract_exists_and_matches_its_gt_pin():
    for name, manifest in _manifests():
        raw_gt = json.loads((SUITE_DIR / manifest["gt"]).read_text(encoding="utf-8"))
        for key, pin in _PIN_KEYS:
            path = SUITE_DIR / manifest[key]
            assert path.is_file(), (
                f"{name}: {key} is not in the tree at {manifest[key]} — a fixture "
                f"that cannot load from a clean checkout is not a benchmark (D-5)")
            assert sha256_file(path) == raw_gt[pin], (
                f"{name}: {manifest[key]} does not hash to the GT's {pin} (D5)")


def test_manifest_artifacts_are_not_gitignored():
    """`--no-index` asks the RULES, not the index: the property that matters is
    that the next `git add` of a manifest-referenced file is not silently a
    no-op."""
    paths = _artifact_relpaths()
    result = _git("check-ignore", "--no-index", "--", *paths)
    ignored = [line for line in result.stdout.splitlines() if line.strip()]
    assert not ignored, f"gitignored manifest artifacts (D-5): {ignored}"


def test_manifest_artifacts_are_never_eol_converted():
    paths = _artifact_relpaths()
    result = _git("check-attr", "text", "--", *paths)
    assert result.returncode == 0, result.stderr
    attrs: Dict[str, str] = {}
    for line in result.stdout.splitlines():
        path, _attr, value = (part.strip() for part in line.rsplit(":", 2))
        attrs[Path(path).as_posix()] = value
    convertible = sorted(p for p in paths if attrs.get(p) != "unset")
    assert not convertible, (
        f"hash-pinned artifacts git may EOL-convert (need `-text` in "
        f".gitattributes): {convertible}")
