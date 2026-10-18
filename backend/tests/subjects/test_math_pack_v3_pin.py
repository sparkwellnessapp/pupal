"""[owner rulings 2026-10-18 16:15 §3] the Math pack ships with the EXACT bytes that were evaluated.

Pack v3 passed the §6b smoke (after the §2a phantom exclusion and the §2b re-assembly) and the
sealed held-out set (70/72, K1 0) — plans `d2d838a9` / `a79166be`, RUNLOG 2026-10-18. A change to
either fragment is a NEW pack: bump `PACK_VERSION` (which moves every Math plan's config hash),
re-run the smoke and the held-out set, and only then update these pins.
"""
from __future__ import annotations

import hashlib

from app.subjects.profiles.mathematics import PACK_VERSION, PLANNER_FRAGMENT, VERIFIER_FRAGMENT

EVALUATED = {
    "pack_version": "v3",
    "planner_fragment_sha256": "5bf1367e35d661c07009b6333faef11514c09492531ced027770dea36e75287c",
    "verifier_fragment_sha256": "fa064a2a33d2d397189e6b09daf5919a1f9e83f713e3a8c774e5f3a6a93271be",
}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_the_shipped_math_pack_is_the_evaluated_one():
    assert PACK_VERSION == EVALUATED["pack_version"]
    assert _sha(PLANNER_FRAGMENT) == EVALUATED["planner_fragment_sha256"], (
        "the Math planner fragment differs from the evaluated pack v3 — a new pack needs a new "
        "PACK_VERSION and a new smoke + held-out run before these pins move")
    assert _sha(VERIFIER_FRAGMENT) == EVALUATED["verifier_fragment_sha256"], (
        "the Math verifier fragment differs from the evaluated pack v3")


def test_the_v12_label_cap_is_the_ruled_200():
    from app.agents.grader import plan_validator_v6
    assert plan_validator_v6._LABEL_MAX == 200        # owner 2026-10-18 16:15 §2b
