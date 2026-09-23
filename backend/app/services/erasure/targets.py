"""
PRV-11 PrefixSafety — the allow-list every storage target passes BEFORE any
storage call (ruling 2026-09-22; docs/PURGE_CENSUS.md §19).

Three families, and nothing else:

    ^thumbs/[0-9a-f-]{36}/$                               a scan's rendered pages
    ^returned_exams/[0-9a-f-]{36}/$                       a graded test's signed exams
    ^transcriptions/[0-9a-f-]{36}/[0-9a-f-]{36}\\.pdf$     one scan

and the bucket must be in the known set. A prefix that is empty, `None`-shaped,
missing its trailing slash, or in a foreign bucket raises here — so a bad id can
never widen a delete to a whole family or to someone else's bucket. There is
deliberately no fourth pattern (ruled 2026-09-23): `graded_test_pdfs` is a dead
table, and a row there makes the plan refuse rather than reach for its object.
"""
from __future__ import annotations

import re
import uuid

from app.config import settings

_PREFIX_FAMILIES = (
    re.compile(r"^thumbs/[0-9a-f-]{36}/$"),
    re.compile(r"^returned_exams/[0-9a-f-]{36}/$"),
)
_SCAN = re.compile(r"^transcriptions/[0-9a-f-]{36}/[0-9a-f-]{36}\.pdf$")
# An object inside a listed prefix: one path segment, never "." or "..".
_BASENAME = re.compile(r"^[^/]+$")


class UnsafeStorageTarget(ValueError):
    """A storage target outside the PRV-11 allow-list. Raised before any call."""


def known_buckets() -> frozenset[str]:
    """The buckets the purge may touch: the one the service writes to
    (`grader-vision-pdfs-0438328890` in production, census §4)."""
    return frozenset({settings.gcs_bucket_name})


def _check_bucket(bucket, known: frozenset[str]) -> None:
    if not isinstance(bucket, str) or bucket not in known:
        raise UnsafeStorageTarget(f"bucket outside the known set: {bucket!r}")


def validate_target(bucket, target, *, known_buckets: frozenset[str]) -> None:
    """A prefix to list, or one scan object. Anything else raises."""
    _check_bucket(bucket, known_buckets)
    if not isinstance(target, str) or not (
            any(p.fullmatch(target) for p in _PREFIX_FAMILIES) or _SCAN.fullmatch(target)):
        raise UnsafeStorageTarget(f"not an allowed storage target: {target!r}")


def validate_object(bucket, name, *, known_buckets: frozenset[str]) -> None:
    """An object to delete: a scan, or one object directly inside an allowed
    prefix family."""
    _check_bucket(bucket, known_buckets)
    if isinstance(name, str) and _SCAN.fullmatch(name):
        return
    if isinstance(name, str) and "/" in name:
        prefix, base = name.rsplit("/", 1)
        prefix += "/"
        if (any(p.fullmatch(prefix) for p in _PREFIX_FAMILIES)
                and _BASENAME.fullmatch(base) and base not in (".", "..")):
            return
    raise UnsafeStorageTarget(f"not an allowed object to delete: {name!r}")


def _canonical(value) -> str:
    """A real UUID in its canonical lowercase form, or a refusal — so a None
    can never format itself into `thumbs/None/`."""
    try:
        return str(value if isinstance(value, uuid.UUID) else uuid.UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise UnsafeStorageTarget(f"not an id: {value!r}") from None


def thumbs_prefix(transcription_id) -> str:
    return f"thumbs/{_canonical(transcription_id)}/"


def returned_exams_prefix(graded_test_id) -> str:
    return f"returned_exams/{_canonical(graded_test_id)}/"
