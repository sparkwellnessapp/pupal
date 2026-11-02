"""[owner rulings 2026-10-18 16:15 §3] the Math pack ships with the EXACT bytes that were evaluated.

v5 (2026-11-02, owner-requested + owner-approved direct-API eval, RUNLOG): ONE MISTAKE, ONE
CHARGE replaces R2 (planner + verifier) — held-out K1 0, 70/72; smoke 54/57, its one K1 (q5.ד,
credit for solving her own wrong equation) ACCEPTED by the owner as the ruled behaviour.

v4 (2026-10-29, owner-approved direct-API eval, RUNLOG): verifier only — held-out K1 0, 70/72
(v3 re-run 69/72); smoke 54/57 (v3 53/57), the one K1 the §2a phantom. Planner unchanged (v3).
The shipped bytes differ from the evaluated run by ONE line join (whitespace, the 12-line guard).

Pack v3 passed the §6b smoke (after the §2a phantom exclusion and the §2b re-assembly) and the
sealed held-out set (70/72, K1 0) — plans `d2d838a9` / `a79166be`, RUNLOG 2026-10-18. A change to
either fragment is a NEW pack: bump `PACK_VERSION` (which moves every Math plan's config hash),
re-run the smoke and the held-out set, and only then update these pins.
"""
from __future__ import annotations

import hashlib

from app.subjects.profiles.mathematics import PACK_VERSION, PLANNER_FRAGMENT, VERIFIER_FRAGMENT

EVALUATED = {
    "pack_version": "v5",
    "planner_fragment_sha256": "ed1a16773b0f79efa7c822d00e17f57493e0364d7d2c262ac9126e4ff5a42180",
    "verifier_fragment_sha256": "4431aca485a3ad74c7304b0360304130e4a78f739fdbba823fdce0f51047a7e5",
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
