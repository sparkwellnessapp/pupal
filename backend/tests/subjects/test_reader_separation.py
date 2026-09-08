"""Two readers, two purposes (execution plan §4.6) — a structural guard.

`rubric-read/rr1.0` (app/services/docx_v3/image_render.py) reads RUBRIC pages and
may read everything on them: printed text, handwriting, weights. P1 reads STUDENT
pages and stays spec-blind. They share the provider and page machinery only.

This test makes the wrong wiring impossible to land quietly: no module on the
student-transcription path may import the rubric reader, and the rubric reader
may not import the student pipeline's prompts.
"""
from __future__ import annotations

from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
APP = BACKEND / "app"

STUDENT_PATH_FILES = [
    *sorted((APP / "services" / "transcription").rglob("*.py")),
    APP / "services" / "transcribe_one.py",
    APP / "services" / "transcription_job_runner.py",
    APP / "api" / "v0" / "transcription.py",
    APP / "api" / "v0" / "batch_grading.py",
]

FORBIDDEN_IN_STUDENT_PATH = ("image_render", "rubric_read", "RUBRIC_READ")


def test_student_transcription_path_never_imports_the_rubric_reader():
    offenders = []
    for path in STUDENT_PATH_FILES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_IN_STUDENT_PATH:
            if token in text:
                offenders.append(f"{path.relative_to(BACKEND)}: {token}")
    assert not offenders, "rubric reader reachable from the student path:\n" + "\n".join(offenders)


def test_rubric_reader_never_imports_the_student_prompts():
    text = (APP / "services" / "docx_v3" / "image_render.py").read_text(encoding="utf-8")
    for token in ("P1_SYSTEM", "p1_system", "two_phase.prompts", "P2_SPAN_SYSTEM", "p2_system_prompt"):
        assert token not in text, f"image_render.py must not import the student prompts: {token}"


def test_rubric_reader_prompt_is_short_and_never_solves():
    from app.services.docx_v3.image_render import RUBRIC_READ_PROMPT_VERSION, RUBRIC_READ_SYSTEM

    assert RUBRIC_READ_PROMPT_VERSION == "rubric-read/rr1.0"
    lines = [l for l in RUBRIC_READ_SYSTEM.splitlines() if l.strip()]
    assert len(lines) <= 12, f"rr1.0 has {len(lines)} lines (> 12, execution plan §4.1)"
    assert "=== PAGE" in RUBRIC_READ_SYSTEM
    assert "never solve" in RUBRIC_READ_SYSTEM.lower()
