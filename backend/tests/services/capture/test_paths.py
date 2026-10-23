"""
The capture storage layout (`app/services/capture/paths.py`) against the
purge's allow-list (PRV-11, `erasure/targets.py`). The allow-list restates the
layout on purpose instead of importing it; this is what keeps the two equal.
Pure — no DB, no storage.
"""
import uuid

import pytest

from app.services.capture import paths
from app.services.erasure.targets import (
    UnsafeStorageTarget, captures_prefix, validate_object, validate_target,
)

BUCKET = "b"
KNOWN = frozenset({BUCKET})
SUB, PAGE, VERSION = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def test_the_submission_prefix_is_an_allowed_listing_target_and_matches_the_purge():
    validate_target(BUCKET, paths.submission_prefix(SUB), known_buckets=KNOWN)
    assert paths.submission_prefix(SUB) == captures_prefix(SUB)


@pytest.mark.parametrize("build", [
    lambda: paths.raw_path(SUB, PAGE),
    lambda: paths.preview_path(SUB, PAGE),
    lambda: paths.name_render_path(SUB, PAGE),
    lambda: paths.pdf_path(SUB, VERSION),
], ids=["raw", "preview", "name_render", "pdf"])
def test_every_object_the_layout_writes_is_deletable_by_the_purge(build):
    name = build()
    assert name.startswith(paths.submission_prefix(SUB))
    validate_object(BUCKET, name, known_buckets=KNOWN)


def test_the_compiled_pdf_is_also_a_scan_target():
    """A job and its transcription name the PDF directly (the purge's
    per-scan checks: bucket, allow-list, shared object)."""
    validate_target(BUCKET, paths.pdf_path(SUB, VERSION), known_buckets=KNOWN)


def test_the_pdf_path_is_deterministic_in_the_version():
    assert paths.pdf_path(SUB, VERSION) == paths.pdf_path(str(SUB), str(VERSION))


def test_a_non_id_never_formats_into_a_path():
    with pytest.raises(ValueError):
        paths.raw_path(None, PAGE)
    with pytest.raises(UnsafeStorageTarget):
        captures_prefix(None)


def test_split_gs_uri_round_trips_and_refuses_junk():
    path = paths.raw_path(SUB, PAGE)
    assert paths.split_gs_uri(paths.gs_uri(BUCKET, path)) == (BUCKET, path)
    for junk in ("", "b/x", "gs://", "gs://bucket", "gs://bucket/"):
        with pytest.raises(ValueError):
            paths.split_gs_uri(junk)
