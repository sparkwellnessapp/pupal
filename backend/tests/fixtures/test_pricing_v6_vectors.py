"""grader-v6 Phase 1 — the parity vectors regenerate clean (A-2, PRC-7's seam).

`pricing_v6_vectors.json` is committed (explicitly un-ignored) and must be
byte-identical to what `scripts/gen_pricing_v6_vectors.py` produces from a
clean checkout: ≥ 30 hand-written cases (E1–E10, E3 dropped) + 500 generated
by a seeded PRNG through the one case builder. The TS mirror (Phase 5)
reproduces every vector."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
OUT = BACKEND / "tests" / "fixtures" / "grade_review" / "pricing_v6_vectors.json"


def _gen():
    sys.path.insert(0, str(BACKEND / "scripts"))
    import gen_pricing_v6_vectors as gen
    return gen


def test_pricing_vectors_regenerate_clean():
    gen = _gen()
    expected = gen.render(gen.all_vectors())
    assert OUT.exists(), "pricing_v6_vectors.json missing — run scripts/gen_pricing_v6_vectors.py"
    assert OUT.read_text(encoding="utf-8") == expected, (
        "pricing_v6_vectors.json is stale — run scripts/gen_pricing_v6_vectors.py")
    vectors = json.loads(expected)
    hand = [v for v in vectors if v["kind"] == "hand"]
    generated = [v for v in vectors if v["kind"] == "generated"]
    assert len(hand) >= 30 and len(generated) == 500
    names = {v["case"] for v in hand}
    for e in ("E1", "E2", "E4", "E5", "E6", "E7", "E8", "E9", "E10"):
        assert any(n.startswith(e + ":") for n in names), e


def test_vectors_file_is_tracked_not_ignored():
    """D-3: the typed vectors went missing on a clean checkout because
    `*.json` is ignored. This file must be explicitly un-ignored."""
    import subprocess
    r = subprocess.run(["git", "check-ignore", "-q", str(OUT)], cwd=BACKEND)
    assert r.returncode == 1, "pricing_v6_vectors.json is git-ignored — add a negation"
