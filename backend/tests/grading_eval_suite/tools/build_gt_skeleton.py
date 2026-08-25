"""
F4 — GT skeleton builder: reads the compiled contracts and emits a GT file
with EVERY terminal id pre-populated and the judgment fields empty. The owner
fills judgments only [F4]; the loader refuses the file until every judgment
is filled (nulls fail FixtureGT validation — that is the completion check).

`points_possible` and `description` per terminal are authoring aids only —
NOT FixtureGT fields; strip-on-load is automatic (pydantic ignores extras is
NOT relied on — the loader validates the typed subset via FixtureGT).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..fixtures import SUITE_DIR, FixtureBundle, load_bundle


def build_skeleton(bundle: FixtureBundle) -> dict:
    terminals = []
    # scope order = the contract's own order (the compiler's scope walk), so the
    # owner grades in document order
    for scope in bundle.gradable_test.scopes:
        for criterion in scope.criteria:
            if criterion.sub_criteria:
                for sc in criterion.sub_criteria:
                    terminals.append({
                        "terminal_id": sc.sub_criterion_id,
                        "points_possible": str(sc.points),        # authoring aid
                        "description": sc.description,            # authoring aid
                        "awarded": None,                          # OWNER FILLS
                        "evidence_exists": None,                  # OWNER FILLS [C-5]
                        "note": "",
                    })
            else:
                terminals.append({
                    "terminal_id": criterion.criterion_id,
                    "points_possible": str(criterion.points),
                    "description": criterion.description,
                    "awarded": None,
                    "evidence_exists": None,
                    "note": "",
                })
    return {
        "fixture": bundle.name,
        "rubric_contract_hash": bundle.rubric_contract_hash or "",
        "transcription_contract_hash": bundle.transcription_contract_hash or "",
        # [M1, 2026-08-25] the ruled v0 GT class: agent-proposed judgments,
        # owner-validated, both parties on record — honestly non-blind.
        "gt_source": "teacher_validated",
        "proposed_by": "claude-fable-5 (design-partner session)",
        "validated_by": "Noam",
        "authored_by": "Noam",
        "authored_at": "",                # OWNER stamps at completion
        "blind": False,                   # [M1] validated, not blind
        "terminals": terminals,
        "ungradable_scopes": [],          # [C-2] fill per GRADING_GT_CONVENTIONS
        "_instructions": ("Fill awarded (Decimal string on the precision grid), "
                          "evidence_exists (bool), optional note, per terminal; add "
                          "ungradable_scopes per C-2; stamp authored_at (ISO-8601) "
                          "when done; delete this key. The loader refuses partial "
                          "files — that is the completion check."),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Emit a GT skeleton for one fixture [F4]")
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    bundle = load_bundle(args.fixture, require_gt=False)
    sk = build_skeleton(bundle)
    out = Path(args.out) if args.out else (
        SUITE_DIR / "benchmarks" / "gt" / f"{args.fixture}.gt.skeleton.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(sk, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[F4] skeleton with {len(sk['terminals'])} terminals -> {out}")


if __name__ == "__main__":
    main()
