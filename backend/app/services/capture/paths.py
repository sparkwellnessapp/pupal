"""
Where a capture submission's objects live — the ONE place that spells the
layout (the capture service writes it, the runner's step 0 reads it, the
purge lists it).

Every object of a submission sits DIRECTLY under one prefix:

    captures/{submission_id}/raw-{page_id}            the photo, as uploaded
    captures/{submission_id}/preview-{page_id}.jpg    display only (SCN-11)
    captures/{submission_id}/name-{page_id}.jpg       the name-suggest render
    captures/{submission_id}/{version_id}.pdf         the compiled PDF (SCN-4)

Flat, and keyed by ids only, because the purge's allow-list (PRV-11,
`erasure/targets.py`) admits exactly one path segment under an allowed prefix
and nothing that could be a name. The bucket is the service's one bucket
(`settings.gcs_bucket_name`): the transcription runner downloads and records
its source from that bucket alone, so a capture PDF anywhere else would be a
job the runner cannot read.
"""
from __future__ import annotations

import uuid


def _id(value) -> str:
    """A real UUID in canonical form, or a refusal — so a None can never
    format itself into `captures/None/`."""
    return str(value if isinstance(value, uuid.UUID) else uuid.UUID(str(value)))


def submission_prefix(submission_id) -> str:
    return f"captures/{_id(submission_id)}/"


def raw_path(submission_id, page_id) -> str:
    return f"{submission_prefix(submission_id)}raw-{_id(page_id)}"


def preview_path(submission_id, page_id) -> str:
    return f"{submission_prefix(submission_id)}preview-{_id(page_id)}.jpg"


def name_render_path(submission_id, page_id) -> str:
    return f"{submission_prefix(submission_id)}name-{_id(page_id)}.jpg"


def pdf_path(submission_id, version_id) -> str:
    """Deterministic in the version id: compiling a version twice writes the
    same object (SCN-4)."""
    return f"{submission_prefix(submission_id)}{_id(version_id)}.pdf"


def gs_uri(bucket: str, object_path: str) -> str:
    return f"gs://{bucket}/{object_path}"


def split_gs_uri(uri: str) -> tuple[str, str]:
    """`gs://bucket/path` → (bucket, path). Raises on anything else."""
    if not isinstance(uri, str) or not uri.startswith("gs://"):
        raise ValueError(f"not a gs:// uri: {uri!r}")
    bucket, _, path = uri[len("gs://"):].partition("/")
    if not bucket or not path:
        raise ValueError(f"not a gs:// object uri: {uri!r}")
    return bucket, path
