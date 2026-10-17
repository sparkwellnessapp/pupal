"""Capture a REAL v6 review fixture for the frontend tests (no provider, no DB).

Grades the hobby bundle with the v6 grader on the scripted fake model the backend's
own tests use (`tests/services/test_v6_review_mvc.py::_grade`), then builds the exact
`GradedTestV6Response` the endpoints return (`grading.py::_v6_response`) for:

  base        no decision of hers
  flip        a ladder check moved to its middle option            (a PATCH response)
  pin         q1.ג.c6 set by hand to 2 — the group charge moves to q1.ג.c7 (AM-G15)
  undecided   a second grade in which the model answered NO ladder check: the same
              content with `model_option_id` null on `missing_check_ids` (asserted
              here), and the server's `undecided_check_ids` for it

`content` is stored ONCE (it is Vivi's record and never changes between responses);
each variant stores only the fields that move. Written compact.

Run from backend/ (no provider, no DB is touched):
    python scripts/gen_v6_review_fixture.py            # write
    python scripts/gen_v6_review_fixture.py --check    # fail on any diff
Deterministic: the one wall-clock field (`grading_duration_ms`) is pinned to 0, so a
re-run is byte-identical; `tests/fixtures/test_v6_review_fixture.py` regenerates it and
compares, so the frontend's fixture cannot drift from what the server returns.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from decimal import Decimal as D
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/x")
os.environ.setdefault("EMAIL_PROVIDER", "console")
BACKEND = Path(__file__).resolve().parents[1]
OUT = BACKEND.parent / "frontend" / "src" / "mocks" / "grade_review" / "v6_review_hobby.json"
sys.path.insert(0, str(BACKEND))

from tests.services.test_v6_review_mvc import _grade  # noqa: E402
from app.schemas.graded_test_responses import GradedTestV6Response, V6ReasoningLine  # noqa: E402
from app.services.v6_review import (CheckPatchV6, OverlayPatchV6, merge_overlay,  # noqa: E402
                                    overlay_doc, overlay_of, review, undecided_checks)

GID = uuid.UUID("6a6a6a6a-0000-4000-8000-000000000001")
MOVING = ("status", "overrides", "overlay", "priced", "ai_total_score", "lines",
          "undecided_check_ids")


def pick(role, opts):
    # credit: the top option; fault: charged; note: observed — so every state the
    # review renders (applied / capped / superseded group / observed note) exists
    if role == "CREDIT":
        return opts[0]
    return opts[1] if len(opts) > 1 else opts[0]


def pick_no_ladders(role, opts):
    if role == "CREDIT" and len(opts) >= 3:
        return "o999"                       # not an option: the model answered nothing
    return pick(role, opts)


def response(draft) -> dict:
    r = review(draft, draft.teacher_overrides)
    out = GradedTestV6Response(
        id=GID, status="draft", content=r.content, overrides=draft.teacher_overrides,
        overlay=r.overlay, priced=r.final, ai_total_score=r.ai.total_score,
        lines=[V6ReasoningLine(terminal_id=t, text_he=x, source=s) for t, (x, s) in r.lines.items()],
        undecided_check_ids=undecided_checks(r.content, r.ai, r.overlay))
    doc = json.loads(out.model_dump_json())
    doc["content"]["explainer_payloads"] = []
    return doc


def moving(doc: dict) -> dict:
    return {k: doc[k] for k in MOVING}


def with_patch(draft, patch):
    merged = merge_overlay(overlay_of(draft.teacher_overrides), patch)
    o = draft.teacher_overrides.model_copy(update={"v6": overlay_doc(merged)})
    return draft.model_copy(update={"teacher_overrides": o})


def build() -> str:
    """The fixture, serialized exactly as committed."""
    draft, _bundle = _grade(pick=pick)
    base = response(draft)
    content = base["content"]

    ladder = next(c["plan"] for c in content["checks"] if c["plan"]["check_id"] == "q2.א.c1.c2")
    mid = ladder["options"][1]["option_id"]
    flipped = with_patch(draft, OverlayPatchV6(checks={ladder["check_id"]: CheckPatchV6(option_id=mid)}))
    pinned = with_patch(draft, OverlayPatchV6(terminal_points={"q1.ג.c6": D("2")}))

    # the undecided variant: same plan, the model answered no ladder
    draft_u, _b = _grade(pick=pick_no_ladders)
    resp_u = response(draft_u)
    missing = [c["plan"]["check_id"] for c in resp_u["content"]["checks"] if c["model_option_id"] is None]
    # the reconstruction the frontend test performs must be EXACT for pricing
    for a, b in zip(content["checks"], resp_u["content"]["checks"]):
        assert a["plan"] == b["plan"] and a["plan_index"] == b["plan_index"]
        if a["plan"]["check_id"] in missing:
            assert b["model_option_id"] is None
        else:
            assert a["model_option_id"] == b["model_option_id"] and a["quote_status"] == b["quote_status"]
    for key in ("view_terminals", "selection", "precision", "terminals", "scopes"):
        assert content[key] == resp_u["content"][key], key

    env = draft.model_dump(mode="json")
    env["v6"] = None                         # re-attached from `base.content` by the reader
    env["grading_duration_ms"] = 0           # the one wall-clock field: pinned for determinism
    doc = {
        "_note": ("Captured from the v6 grader on the scripted fake model "
                  "(backend tests/services/test_v6_review_mvc.py::_grade, hobby bundle). "
                  "graded_test.draft.v6 is null HERE ONLY: the reader re-attaches base.content, "
                  "which is the same object. Regenerate with backend/scripts/gen_v6_review_fixture.py; never hand-edit."),
        "graded_test": {
            "id": str(GID), "status": "draft", "student_name": "נועה לוי",
            "transcription_id": "6a6a6a6a-0000-4000-8000-0000000000aa",
            "total_possible": content["selection"]["total_points"],
            "numeric_policy": {"precision": content["precision"], "rounding_mode": "half_up",
                               "sum_tolerance": "0.01"},
            "rubric_contract_stale": False, "regraded_from_id": None,
            "draft": env,
        },
        "base": base,
        "flip": {"check_id": ladder["check_id"], "option_id": mid, "response": moving(response(flipped))},
        "pin": {"terminal_id": "q1.ג.c6", "amount": "2", "response": moving(response(pinned))},
        "undecided": {"missing_check_ids": missing, "response": moving(resp_u)},
    }
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n"


def main(argv) -> int:
    text = build()
    if "--check" in argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else None
        if current != text:
            print(f"{OUT.name} is stale — run scripts/gen_v6_review_fixture.py")
            return 1
        print(f"{OUT.name}: clean")
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    doc = json.loads(text)
    moved = [c["check_id"] for t in doc["pin"]["response"]["priced"]["terminals"]
             for c in t["charges"] if c["moved_by_pin"]]
    print("wrote", OUT.name, "· base", doc["base"]["priced"]["total_score"],
          "flip", doc["flip"]["response"]["priced"]["total_score"],
          "pin", doc["pin"]["response"]["priced"]["total_score"], "moved", moved,
          "undecided", len(doc["undecided"]["response"]["undecided_check_ids"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
