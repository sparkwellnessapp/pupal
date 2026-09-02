# -*- coding: utf-8 -*-
"""
Generate the four batch-dashboard fixtures (spec §1.7) FROM THE WIRE TYPES.

Not hand-written, and not a shape agreed in parallel with the backend: every
fixture is built by constructing the real `BatchDetailResponse` and dumping it.
If the model changes, these regenerate differently and
`tests/api/test_batch_feed_fixtures.py` fails — which is the point. A fixture
that can drift from the endpoint it describes is worse than no fixture, because
the frontend builds against it and the disagreement surfaces at integration.

The four states are the dashboard's real lifecycle:
  landing   — nothing graded yet; the ETA is all she has
  running   — some landed, some still grading; look_counts appear
  done      — everything landed, nothing approved
  complete  — everything approved

Usage:  python -m scripts.gen_batch_feed_fixtures
"""
from __future__ import annotations

import io
import json
import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.schemas.batch import (  # noqa: E402
    BatchDetailResponse, BatchEta, BatchGradedItem, BatchRollup,
)
from app.services.thumbnail import page_image_path  # noqa: E402

OUT = ROOT / "tests" / "fixtures" / "grade_review"

# Stable ids so a regeneration produces a clean diff rather than noise.
BATCH = UUID("11111111-1111-4111-8111-111111111111")
RUBRIC = UUID("22222222-2222-4222-8222-222222222222")
STUDENTS = [
    (UUID("33333333-3333-4333-8333-00000000000%d" % i), name)
    for i, name in enumerate(
        ["דן בסיוק", "דין עזרא", "מורן אהרון", "עומר גלבר", "יונתן בסיוק"])
]
# The transcription each graded test came from — what the page-1 thumbnail url
# addresses. Distinct from the graded_test_id: a regrade extends the chain with
# a NEW graded test over the SAME transcription, so conflating them would put
# the wrong id in the url the day the fixtures cover a revision.
TRANSCRIPTIONS = [UUID("55555555-5555-4555-8555-00000000000%d" % i)
                  for i in range(5)]


def _item(idx, status, *, awarded=None, looks=None, landed=None, opened=None,
          page1=True):
    sid, name = STUDENTS[idx]
    # [PR-G8] The url is MINTED, not spelled out, so the fixture carries the
    # live variant token and a settings change shows up here as a diff rather
    # than as a fixture quietly describing a url the backend stopped issuing.
    tid = TRANSCRIPTIONS[idx]
    return BatchGradedItem(
        graded_test_id=UUID("44444444-4444-4444-8444-00000000000%d" % idx),
        student_id=sid, student_name=name, status=status, version=1,
        landed_at=landed, opened_at=opened,
        total_awarded=None if awarded is None else Decimal(str(awarded)),
        look_count=looks,
        page1_image_url=page_image_path(tid, 1) if page1 else None)


def _detail(name, *, items, eta, status):
    return BatchDetailResponse(
        id=BATCH, name=name, rubric_id=RUBRIC, class_id=None,
        rubric_name="מתכונת 1 — שאלון 899371", class_name="יא'3",
        status=status,
        started_at="2026-08-31T18:00:00+00:00", completed_at=None,
        created_at="2026-08-31T17:58:00+00:00",
        rollup=BatchRollup(
            total=5, transcribing=0, transcribed=5, transcription_failed=0,
            needs_eyes=0, approved_transcription=5,
            grading=sum(1 for i in items if i.status == "grading"),
            draft=sum(1 for i in items if i.status == "draft"),
            approved=sum(1 for i in items if i.status == "approved"),
            failed=sum(1 for i in items if i.status == "failed")),
        transcriptions=[], active_jobs=[], graded_tests=items, eta=eta)


STATES = {
    # Nothing has landed. The ETA is the ONLY thing she has, and it comes from
    # the model's measured p50 — never a constant.
    "landing": _detail(
        "מבחן מחצית ב'",
        # The last item carries page1_image_url = null: the transcription has no
        # page 1, so the feed OMITS the url rather than offering one the route
        # would 404 (§3.5a). It is on a `grading` item on purpose — the omission
        # is INDEPENDENT of status, and putting it on the `failed` item would
        # teach the client a correlation that does not exist.
        items=[_item(i, "grading", page1=i < 4) for i in range(5)],
        eta=BatchEta(kind="first_landing", seconds=204),
        status="grading"),

    # Mid-flight. Two landed — one clean, one carrying markers that need her
    # eye. `look_count` is null on the third: its draft would not parse, and a
    # reassuring 0 there would be wrong in the dangerous direction.
    "running": _detail(
        "מבחן מחצית ב'",
        items=[
            _item(0, "draft", awarded="87.5", looks=0,
                  landed="2026-08-31T18:02:11+00:00"),
            _item(1, "draft", awarded="64.25", looks=3,
                  landed="2026-08-31T18:02:48+00:00"),
            _item(2, "draft", awarded="71.0", looks=None,
                  landed="2026-08-31T18:03:02+00:00"),
            _item(3, "grading"),
            _item(4, "failed"),
        ],
        eta=BatchEta(kind="remaining", seconds=68),
        status="grading"),

    # Everything landed, nothing approved. One was opened and not finished —
    # `opened_at` set with status still draft is the "you started this" state.
    "done": _detail(
        "מבחן מחצית ב'",
        items=[
            _item(0, "draft", awarded="87.5", looks=0,
                  landed="2026-08-31T18:02:11+00:00",
                  opened="2026-08-31T18:10:00+00:00"),
            _item(1, "draft", awarded="64.25", looks=3,
                  landed="2026-08-31T18:02:48+00:00"),
            _item(2, "draft", awarded="71.0", looks=1,
                  landed="2026-08-31T18:03:02+00:00"),
            _item(3, "draft", awarded="93.75", looks=0,
                  landed="2026-08-31T18:03:40+00:00"),
            _item(4, "failed"),
        ],
        eta=BatchEta(kind="unknown", seconds=None),
        status="draft"),

    # Done and approved. The failed one is STILL failed — a batch completes
    # with a hole in it and says so, rather than quietly reporting 4 of 4.
    "complete": _detail(
        "מבחן מחצית ב'",
        items=[
            _item(i, "approved", awarded=a, looks=0,
                  landed="2026-08-31T18:0%d:00+00:00" % (i + 2),
                  opened="2026-08-31T18:1%d:00+00:00" % i)
            for i, a in enumerate(["87.5", "64.25", "71.0", "93.75"])
        ] + [_item(4, "failed")],
        eta=BatchEta(kind="unknown", seconds=None),
        status="partially_completed"),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for state, payload in STATES.items():
        path = OUT / f"batch_feed_{state}.json"
        io.open(path, "w", encoding="utf-8", newline="\n").write(
            json.dumps(payload.model_dump(mode="json"),
                       ensure_ascii=False, indent=2) + "\n")
        print(f"  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
