"""Publish the APPROVED fixtures the returned-exam preview (F3) renders from.

WHY THIS SCRIPT EXISTS AND NOT A HAND-WRITTEN JSON. The §1.7 seam rule is that
a fixture is generated from real data or it refuses; a hand-written approved
contract would let F3 build a preview against a shape nobody agreed to, and the
disagreement would surface at integration. So this runs the REAL approval gate
(`compile_graded_test`) over the REAL published drafts and the REAL rubric
contract they were graded against — the same three inputs production uses. The
output is ground truth by construction, not by assertion.

The drafts carry `rubric_contract_version` 9a6c82dc-…, which is exactly the
version of `benchmarks/contracts/hobby_tvshow_corrected.contract.json`; the
script REFUSES if that ever stops being true, because compiling against a
different rubric would silently publish a contract whose points came from
somewhere else.

Overrides: the published drafts carry the teacher's own `teacher_overrides`
(empty for most — she approved as proposed). We pass exactly what the draft
carries, which is what `/approve` does when she signs without touching anything.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.graded_test_draft import GradedTestDraft, GradedTestOverrides
from app.schemas.ontology_types import GradingRubricContract
from app.services.graded_test_contract_compiler import compile_graded_test

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "grade_review"
RUBRIC = (ROOT / "tests" / "grading_eval_suite" / "benchmarks" / "contracts"
          / "hobby_tvshow_corrected.contract.json")

# The batch feed's OWN ids, verbatim — the fixtures join to
# `batch_feed_*.json` on these, so a placeholder here (the first version wrote
# the literal string "TEST_A") produces a payload the server could never emit
# and silently breaks any consumer that does not rewrite it.
#   slug -> (display name, graded_test_id, transcription_id)
STUDENTS = {
    "dan_basiuk": ("דן בסיוק",
                   "44444444-4444-4444-8444-000000000000",
                   "55555555-5555-4555-8555-000000000000"),
    "moran_aharon": ("מורן אהרון",
                     "44444444-4444-4444-8444-000000000002",
                     "55555555-5555-4555-8555-000000000002"),
    "omer_gelber": ("עומר גלבר",
                    "44444444-4444-4444-8444-000000000003",
                    "55555555-5555-4555-8555-000000000003"),
    "yonatan_basiuk": ("יונתן בסיוק",
                       "44444444-4444-4444-8444-000000000004",
                       "55555555-5555-4555-8555-000000000004"),
}

# `compile_graded_test` stamps `datetime.now(utc)`, so carrying the compiler's
# value would rewrite every fixture on every run — and the preview's header
# would show whatever day the fixtures were last regenerated. The signing
# instant is pinned to the batch feed's own evening instead, which is what
# makes this file byte-stable and its screenshots reproducible.
APPROVED_AT = "2026-08-31T20:31:00+00:00"

# `compile_graded_test` also mints a FRESH `contract_version` UUID per compile
# (CLAUDE.md §4 — correct in production, where each compile is a distinct
# freeze). In a fixture it is pure churn: the file changes on every run and any
# test that asserts on it is unstable. Pinned per student, deterministically.
CONTRACT_VERSIONS = {
    "dan_basiuk": "66666666-6666-4666-8666-000000000000",
    "moran_aharon": "66666666-6666-4666-8666-000000000002",
    "omer_gelber": "66666666-6666-4666-8666-000000000003",
    "yonatan_basiuk": "66666666-6666-4666-8666-000000000004",
}

# din_ezra is DELIBERATELY absent, and the omission is a finding rather than a
# gap: its draft carries an unresolved `llm_failure` ERROR annotation on q2.ב,
# so the real approval gate refuses it (§5 — an ERROR blocks approval). There
# is no honest approved contract for that test until the teacher resolves the
# failed scope, and manufacturing one would publish a returned exam for a
# student whose grade was never signed. It is also the test the dashboard's
# attention line already names as the worst — the two surfaces agree.
BLOCKED = {"din_ezra": "unresolved llm_failure ERROR on q2.ב — gate refuses"}


def main() -> None:
    rubric = GradingRubricContract.model_validate(
        json.loads(RUBRIC.read_text(encoding="utf-8")))

    written = []
    for slug, (name, test_id, transcription_id) in STUDENTS.items():
        src = FIX / f"draft_{slug}.json"
        raw = json.loads(src.read_text(encoding="utf-8"))
        draft = GradedTestDraft.model_validate(raw)

        if draft.rubric_contract_version != rubric.contract_version:
            raise SystemExit(
                f"{src.name}: rubric_contract_version {draft.rubric_contract_version} "
                f"!= contract {rubric.contract_version} — refusing to compile a "
                f"grade against a rubric it was not graded on.")

        overrides = draft.teacher_overrides or GradedTestOverrides()
        contract = compile_graded_test(draft, overrides, rubric)

        # The two fields the compiler stamps from the clock / a fresh UUID.
        # Overridden AFTER compilation, never before: the gate ran on the real
        # thing, and only the two values that cannot be reproduced are pinned.
        contract_json = contract.model_dump(mode="json")
        contract_json["approved_at"] = APPROVED_AT
        contract_json["contract_version"] = CONTRACT_VERSIONS[slug]

        payload = {
            "id": test_id,
            "status": "approved",
            "student_name": name,
            "filename": f"{slug}.pdf",
            "transcription_id": transcription_id,
            "regraded_from_id": None,
            "total_score": str(contract.total_score),
            "total_possible": str(contract.total_possible),
            "percentage": (str(contract.percentage)
                           if contract.percentage is not None else None),
            "approved_at": APPROVED_AT,
            "numeric_policy": rubric.numeric_policy.model_dump(mode="json"),
            "rubric_contract_stale": False,
            "total_cost_usd": None,
            "contract": contract_json,
            "draft": raw,
        }
        out = FIX / f"approved_{slug}.json"
        out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8")
        written.append((out.name, payload["total_score"], payload["total_possible"]))

    for n, s, p in written:
        print(f"  {n}  {s}/{p}")


if __name__ == "__main__":
    main()
