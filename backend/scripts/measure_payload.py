"""
C1 payload measurement (closeout) — READ-ONLY.

Measures what `GET /batches/{id}` actually costs at N2 scale (30–40 tests),
using REAL transcription drafts from the database rather than synthetic
guesses: the whole risk is that real student answers are bigger than fixtures,
so fixtures cannot answer the question.

Discipline (owner ruling): record SERIALIZED bytes first, then WIRE bytes with
gzip, and apply the threshold to the wire — but keep BOTH numbers on the
record. Compression is a mitigation, not an absolution: the serialized size
still costs server CPU per poll and client parse time on every tick, and it
still grows as `approved_answers` accumulate with approvals.

PRE-REGISTERED THRESHOLDS (declared before measuring):
    single payload  > 250KB on the wire  ⇒ defect
    20-min session  >  50MB on the wire  ⇒ defect

    python scripts/measure_payload.py
"""
from __future__ import annotations

import asyncio
import gzip
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402

TARGET_ITEMS = 40
POLL_SECONDS = 3          # the dashboard's cadence while work is in flight
SESSION_MINUTES = 20
SINGLE_THRESHOLD = 250 * 1024
SESSION_THRESHOLD = 50 * 1024 * 1024


def _kb(n: float) -> str:
    return f"{n / 1024:,.1f} KB"


def _mb(n: float) -> str:
    return f"{n / (1024 * 1024):,.1f} MB"


async def main() -> int:
    async with engine.connect() as conn:
        rows = (await conn.execute(text(
            "SELECT draft_json, review_json, status FROM public.transcriptions "
            "WHERE draft_json IS NOT NULL ORDER BY created_at DESC LIMIT 200"
        ))).all()

    drafts = [r[0] for r in rows]
    sizes = [len(json.dumps(d, ensure_ascii=False).encode("utf-8")) for d in drafts] or [0]
    answer_counts = [len((d or {}).get("answers") or []) for d in drafts] or [0]

    # CREDIBILITY GATE (closeout): a measurement is only as good as its input.
    # This database is pre-launch and its transcriptions are development stubs
    # (observed: p50 0 answers, p50 0.0 KB). Measuring those would produce a
    # confident PASS that means nothing — the failure mode is a green number
    # nobody questions. When the DB has no realistic drafts, fall back to the
    # eval suite's REAL student transcriptions (2.5–3.9 KB each) and SAY SO.
    median_size = statistics.median(sizes)
    source = "production drafts"
    if median_size < 1024 or statistics.median(answer_counts) < 1:
        bench_dir = Path(__file__).resolve().parents[1] / "tests" / "transcription_eval_suit" / "draft_benchmarks"
        bench = sorted(bench_dir.glob("*.md")) if bench_dir.is_dir() else []
        if not bench:
            print("DB drafts are stubs AND no eval benchmarks found — cannot measure credibly.")
            await engine.dispose()
            return 2
        texts = [p.read_text(encoding="utf-8", errors="replace") for p in bench]
        # Model each test as ~6 answers carved from a real transcription.
        drafts = []
        for t in texts:
            chunk = max(1, len(t) // 6)
            drafts.append({
                "schema_version": "1.0",
                "student_name_suggestion": "ישראל ישראלי",
                "page_count": 3,
                "answers": [
                    {"question_number": i + 1, "sub_question_id": None,
                     "answer_text": t[i * chunk:(i + 1) * chunk],
                     "confidence": 0.93, "page_numbers": [1, 2]}
                    for i in range(6)
                ],
                "annotations": [],
                "model_version": "two_phase/v3_p2-luna",
                "transcription_duration_ms": 61000,
            })
        sizes = [len(json.dumps(d, ensure_ascii=False).encode("utf-8")) for d in drafts]
        answer_counts = [len(d["answers"]) for d in drafts]
        source = (f"EVAL-SUITE REAL STUDENT TRANSCRIPTIONS ({len(bench)} benchmarks) — "
                  f"the production DB holds only development stubs")

    print("=" * 72)
    print(f"C1 PAYLOAD MEASUREMENT  ·  source: {source}")
    print("=" * 72)
    print(f"draft_json bytes   : p50 {_kb(statistics.median(sizes))} · "
          f"mean {_kb(statistics.mean(sizes))} · max {_kb(max(sizes))}")
    print(f"answers per draft  : p50 {statistics.median(answer_counts):.0f} · "
          f"max {max(answer_counts)}")

    # Build a realistic N-item payload by cycling the real drafts. Each item
    # carries what BatchTranscriptionItem actually ships: the draft, the
    # overlay when present, and approved_answers once approved (B6).
    items = []
    for i in range(TARGET_ITEMS):
        draft = drafts[i % len(drafts)]
        approved = i < TARGET_ITEMS // 2          # half-approved: the mid-session shape
        answers = (draft or {}).get("answers") or []
        items.append({
            "transcription_id": "00000000-0000-0000-0000-0000000000%02d" % i,
            "filename": f"scan_{i:03d}.pdf",
            "transcription_status": "approved" if approved else "transcribed",
            "created_at": "2026-08-20T10:00:00+00:00",
            "draft": draft,
            "review": None,
            "student_name_suggestion": "ישראל ישראלי",
            "matched_student_id": "00000000-0000-0000-0000-000000000001",
            "matched_student_name": "ישראל ישראלי",
            "flag_verdict": {"review_needed": not approved, "reasons": ["low_confidence"] if not approved else []},
            "approved_answers": ([
                {"question_number": a.get("question_number"),
                 "sub_question_id": a.get("sub_question_id"),
                 "answer_text": a.get("answer_text")}
                for a in answers
            ] if approved else None),
            "graded_test_id": None, "graded_test_status": None,
            "total_score": None, "total_possible": None,
        })

    payload = {
        "id": "00000000-0000-0000-0000-0000000000ff",
        "name": "מקבץ מדידה", "rubric_id": "r", "class_id": "c",
        "rubric_name": "מתכונת 1", "class_name": "יא׳3",
        "status": "in_progress", "started_at": None, "completed_at": None,
        "created_at": "2026-08-20T09:00:00+00:00",
        "rollup": {"transcribing": 0, "transcribed": 20, "approved_transcription": 20,
                   "grading": 0, "draft": 0, "approved": 20, "failed": 0,
                   "transcription_failed": 0, "total": 40},
        "transcriptions": items,
        "selection_groups": [], "transcription_failures": [], "active_jobs": [],
    }

    serialized = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    wire = gzip.compress(serialized, compresslevel=6)
    ratio = len(serialized) / max(1, len(wire))

    polls = (SESSION_MINUTES * 60) // POLL_SECONDS
    session_serialized = len(serialized) * polls
    session_wire = len(wire) * polls

    print()
    print(f"SINGLE PAYLOAD @ {TARGET_ITEMS} items (half approved):")
    print(f"  serialized : {_kb(len(serialized))}")
    print(f"  wire (gzip): {_kb(len(wire))}   (ratio {ratio:.1f}×)")
    print(f"  threshold  : {_kb(SINGLE_THRESHOLD)} on the WIRE — "
          f"{'PASS' if len(wire) <= SINGLE_THRESHOLD else 'DEFECT'}")
    print()
    print(f"SESSION @ {SESSION_MINUTES} min / {POLL_SECONDS}s poll = {polls} polls:")
    print(f"  serialized : {_mb(session_serialized)}")
    print(f"  wire (gzip): {_mb(session_wire)}")
    print(f"  threshold  : {_mb(SESSION_THRESHOLD)} on the WIRE — "
          f"{'PASS' if session_wire <= SESSION_THRESHOLD else 'DEFECT'}")
    print()
    print("NOTE: gzip is a mitigation, not an absolution — the serialized "
          "number above is what the server CPU serializes and the client "
          "parses on EVERY tick, and it grows as approved_answers accumulate.")

    await engine.dispose()
    failed = len(wire) > SINGLE_THRESHOLD or session_wire > SESSION_THRESHOLD
    print("=" * 72)
    print("MEASUREMENT: DEFECT — mitigation required" if failed else "MEASUREMENT: within pre-registered thresholds")
    print("=" * 72)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
