"""
The PII registry — census row 2 as code (docs/PURGE_CENSUS.md §2, addition G).

Every column in `public` that the census patterns catch (%name%,
%student_name%, %filename%, %gcs%, %object_path%, %_key, and every jsonb
column) is classified here, and `tests/services/erasure/test_pii_registry.py`
set-compares this map with the live schema in BOTH directions. A new column
matching a pattern fails that test until someone decides what the purge does
with it; that decision is the point of the registry. Production and Vivi-Test
catch the same 50 columns (read 2026-09-23).
"""
from __future__ import annotations

from enum import Enum


class Disposition(str, Enum):
    DELETED_WITH_ROW = "deleted_with_row"            # her row goes; the value goes with it
    OBJECT_POINTER = "object_pointer"                # row goes; the object it names goes too
    SCRUBBED_IN_PLACE = "scrubbed_in_place"          # the row is the teacher's and survives
    LEGACY_ASSERTED_EMPTY = "legacy_asserted_empty"  # a dead table: never purged, verify asserts empty
    OUT_OF_SCOPE = "out_of_scope"                    # the teacher's own data, or an institution's
    NO_STUDENT_DATA = "no_student_data"


# The tables the plan DELETES from — dependency order is the executor's
# business (children first, the student row last).
PURGED_TABLES: tuple[str, ...] = (
    "class_memberships", "graded_tests", "transcription_jobs", "transcriptions", "students",
)

# Dead tables: empty, and nothing writes to them. The purge never deletes from
# them; `verify_purged` asserts they stay EMPTY; they go in the OD-B1 drop.
# `graded_test_pdfs` joined on 2026-09-23 — and, being the only one with an FK
# into the student graph, a row of it under her grades makes the plan refuse.
DEAD_TABLES: tuple[str, ...] = ("graded_test_pdfs", "grading_sessions", "raw_graded_tests")

D = Disposition
PII_REGISTRY: dict[tuple[str, str], Disposition] = {
    # --- her rows ---------------------------------------------------------
    ("students", "full_name"): D.DELETED_WITH_ROW,              # literally her name (G)
    ("graded_tests", "student_name"): D.DELETED_WITH_ROW,
    ("graded_tests", "filename"): D.DELETED_WITH_ROW,
    ("graded_tests", "draft_json"): D.DELETED_WITH_ROW,
    ("graded_tests", "contract_json"): D.DELETED_WITH_ROW,
    ("graded_tests", "returned_exam_key"): D.OBJECT_POINTER,    # the prefix is listed, not the key
    ("transcriptions", "student_name"): D.DELETED_WITH_ROW,
    ("transcriptions", "filename"): D.DELETED_WITH_ROW,
    ("transcriptions", "draft_json"): D.DELETED_WITH_ROW,
    ("transcriptions", "contract_json"): D.DELETED_WITH_ROW,
    ("transcriptions", "review_json"): D.DELETED_WITH_ROW,
    ("transcriptions", "gcs_uri"): D.OBJECT_POINTER,
    ("transcriptions", "gcs_bucket"): D.OBJECT_POINTER,
    ("transcriptions", "gcs_object_path"): D.OBJECT_POINTER,
    ("transcription_jobs", "source_filename"): D.DELETED_WITH_ROW,   # deleted, never NULLed
    ("transcription_jobs", "source_gcs_object_path"): D.OBJECT_POINTER,
    # --- the teacher's batch survives; its dormant 015 ledger is scrubbed ---
    ("grading_batches", "transcription_failures"): D.SCRUBBED_IN_PLACE,
    ("grading_batches", "stamp_position_default"): D.NO_STUDENT_DATA,
    ("grading_batches", "name"): D.OUT_OF_SCOPE,
    # --- dead tables ------------------------------------------------------
    ("graded_test_pdfs", "filename"): D.LEGACY_ASSERTED_EMPTY,
    ("graded_test_pdfs", "gcs_uri"): D.LEGACY_ASSERTED_EMPTY,
    ("graded_test_pdfs", "gcs_bucket"): D.LEGACY_ASSERTED_EMPTY,
    ("graded_test_pdfs", "gcs_object_path"): D.LEGACY_ASSERTED_EMPTY,
    ("grading_sessions", "student_name"): D.LEGACY_ASSERTED_EMPTY,
    ("grading_sessions", "filename"): D.LEGACY_ASSERTED_EMPTY,
    ("raw_graded_tests", "student_name"): D.LEGACY_ASSERTED_EMPTY,
    ("raw_graded_tests", "filename"): D.LEGACY_ASSERTED_EMPTY,
    # --- the teacher's own documents and account --------------------------
    ("classes", "name"): D.OUT_OF_SCOPE,
    ("rubrics", "name"): D.OUT_OF_SCOPE,
    ("rubrics", "draft_json"): D.OUT_OF_SCOPE,
    ("rubrics", "contract_json"): D.OUT_OF_SCOPE,
    ("rubrics", "acknowledged_warnings"): D.OUT_OF_SCOPE,
    ("rubrics", "legacy_rubric_json_backup"): D.OUT_OF_SCOPE,
    ("raw_rubrics", "name"): D.OUT_OF_SCOPE,
    ("raw_rubrics", "source_filename"): D.OUT_OF_SCOPE,
    ("raw_rubrics", "rubric_json"): D.OUT_OF_SCOPE,
    ("rubric_extraction_jobs", "source_filename"): D.OUT_OF_SCOPE,
    ("rubric_extraction_jobs", "source_gcs_uri"): D.OUT_OF_SCOPE,
    ("rubric_extraction_jobs", "request_params"): D.OUT_OF_SCOPE,
    ("rubric_extraction_jobs", "llm_config"): D.OUT_OF_SCOPE,
    ("rubric_extraction_jobs", "result_json"): D.OUT_OF_SCOPE,
    ("rubric_extraction_jobs", "errors"): D.OUT_OF_SCOPE,
    ("rubric_extraction_jobs", "warnings"): D.OUT_OF_SCOPE,
    ("rubric_share_tokens", "generated_pdf_gcs_path"): D.OUT_OF_SCOPE,
    ("users", "full_name"): D.OUT_OF_SCOPE,
    ("schools", "name"): D.OUT_OF_SCOPE,
    # --- no student data --------------------------------------------------
    ("grading_plans", "plan_json"): D.NO_STUDENT_DATA,           # rubric algebra only
    ("grading_plans", "skeleton_json"): D.NO_STUDENT_DATA,
    ("subject_matters", "name_en"): D.NO_STUDENT_DATA,
    ("subject_matters", "name_he"): D.NO_STUDENT_DATA,
}
del D
