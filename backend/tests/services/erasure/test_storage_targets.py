"""
PRV-11 PrefixSafety — every storage target is validated against a strict
allow-list BEFORE any storage call (ruling 2026-09-22):

    ^thumbs/[0-9a-f-]{36}/$
    ^returned_exams/[0-9a-f-]{36}/$
    ^transcriptions/[0-9a-f-]{36}/[0-9a-f-]{36}\\.pdf$

and the bucket must be in the known set. Anything else raises. The edge cases
— an empty or None id, a missing trailing slash, a foreign bucket — each raise
with ZERO storage calls. The census checked the allow-list against production:
all 39 scan paths and every id fit it (PURGE_CENSUS §19).

Pure: no database. The recording fake is the witness for "zero calls".
"""
from __future__ import annotations

import uuid

import pytest

from tests.services.erasure.fakes import FakeStorage

B = "known-bucket"
U, T, G = (str(uuid.uuid4()) for _ in range(3))

VALID_PREFIXES = [
    f"thumbs/{T}/",
    f"returned_exams/{G}/",
]
VALID_SCAN = f"transcriptions/{U}/{T}.pdf"

INVALID_TARGETS = [
    "",                                   # the whole bucket
    "thumbs/",                            # every student's thumbnails
    "returned_exams/",
    "transcriptions/",
    f"transcriptions/{U}/",               # one teacher's every scan
    "thumbs//",                           # an empty id
    "thumbs/None/",                       # a None id, formatted
    "returned_exams/None/",
    f"thumbs/{T}",                        # missing trailing slash: also matches thumbs/{T}X…
    f"returned_exams/{G}",
    f"thumbs/{T}/p1.webp/",               # deeper than the family
    f"thumbs/{T.upper()}/",               # not the canonical lowercase form
    f"thumbs/{T[:-1]}/",                  # 35 characters
    f"../thumbs/{T}/",
    f"thumbs/../{T}/",
    f"transcriptions/{U}/{T}.PDF",
    f"transcriptions/{U}/{T}.pdf.bak",
    f"transcriptions/{U}/{T}",
    f"rubric-sources/{U}/{'a' * 64}.pdf",  # the teacher's document
    "db-archive/",                        # the database archives (census §4a)
    f"/thumbs/{T}/",
]


def _guarded(store: FakeStorage):
    from app.services.erasure import GuardedStorage

    return GuardedStorage(store, known_buckets=frozenset({B}))


@pytest.mark.parametrize("prefix", VALID_PREFIXES)
def test_the_two_prefix_families_are_accepted(prefix):
    from app.services.erasure import validate_target

    validate_target(B, prefix, known_buckets=frozenset({B}))


def test_a_scan_object_is_accepted():
    from app.services.erasure import validate_target

    validate_target(B, VALID_SCAN, known_buckets=frozenset({B}))


@pytest.mark.parametrize("target", INVALID_TARGETS)
def test_anything_else_raises(target):
    from app.services.erasure import UnsafeStorageTarget, validate_target

    with pytest.raises(UnsafeStorageTarget):
        validate_target(B, target, known_buckets=frozenset({B}))


@pytest.mark.parametrize("bucket", ["other-bucket", "", None, f"{B} ", B.upper()])
def test_a_bucket_outside_the_known_set_raises(bucket):
    from app.services.erasure import UnsafeStorageTarget, validate_target

    with pytest.raises(UnsafeStorageTarget):
        validate_target(bucket, VALID_PREFIXES[0], known_buckets=frozenset({B}))


@pytest.mark.parametrize("bad_id", [None, "", "None", "not-a-uuid", " " * 36])
def test_the_prefix_builders_refuse_an_empty_or_none_id(bad_id):
    """The builders are the only way the purge spells a prefix, so a None id
    can never format itself into `thumbs/None/`."""
    from app.services.erasure import UnsafeStorageTarget, returned_exams_prefix, thumbs_prefix

    with pytest.raises(UnsafeStorageTarget):
        thumbs_prefix(bad_id)
    with pytest.raises(UnsafeStorageTarget):
        returned_exams_prefix(bad_id)


def test_the_prefix_builders_spell_the_allow_listed_form():
    from app.services.erasure import returned_exams_prefix, thumbs_prefix

    t, g = uuid.uuid4(), uuid.uuid4()
    assert thumbs_prefix(t) == f"thumbs/{t}/"
    assert returned_exams_prefix(g) == f"returned_exams/{g}/"


# ---- the guard sits IN FRONT of the client: a refusal makes no call ----------

@pytest.mark.parametrize("target", INVALID_TARGETS)
def test_a_refused_listing_makes_zero_storage_calls(target):
    from app.services.erasure import UnsafeStorageTarget

    store = FakeStorage({(B, f"thumbs/{T}/p1.webp")})
    with pytest.raises(UnsafeStorageTarget):
        _guarded(store).list_prefix(B, target)
    with pytest.raises(UnsafeStorageTarget):
        _guarded(store).list_soft_deleted(B, target)
    assert store.calls == []


def test_a_foreign_bucket_makes_zero_storage_calls():
    from app.services.erasure import UnsafeStorageTarget

    store = FakeStorage()
    for op in ("list_prefix", "list_soft_deleted"):
        with pytest.raises(UnsafeStorageTarget):
            getattr(_guarded(store), op)("other-bucket", VALID_PREFIXES[0])
    with pytest.raises(UnsafeStorageTarget):
        _guarded(store).delete_object("other-bucket", VALID_SCAN)
    assert store.calls == []


@pytest.mark.parametrize("name", [
    f"thumbs/{T}/",                       # the prefix itself is not an object
    f"thumbs/{T}/..",
    f"thumbs/{T}/.",
    f"thumbs/{T}/a/b.webp",               # nested below the family
    f"thumbs/{T}",
    f"rubric-sources/{U}/x.pdf",
    f"transcriptions/{U}/",
    "",
])
def test_a_refused_delete_makes_zero_storage_calls(name):
    from app.services.erasure import UnsafeStorageTarget

    store = FakeStorage({(B, name)})
    with pytest.raises(UnsafeStorageTarget):
        _guarded(store).delete_object(B, name)
    assert store.calls == []


@pytest.mark.parametrize("name", [
    f"thumbs/{T}/p1_1200x80-150.webp",
    f"returned_exams/{G}/k-current.pdf",
    VALID_SCAN,
])
def test_an_object_inside_an_allowed_family_is_deleted(name):
    store = FakeStorage({(B, name)})
    _guarded(store).delete_object(B, name)
    assert store.deleted == [(B, name)]


def test_the_known_bucket_set_defaults_to_the_configured_bucket():
    """Production's known set is the bucket the service writes to — today
    `grader-vision-pdfs-0438328890` (census §4, A)."""
    from app.config import settings
    from app.services.erasure import known_buckets

    assert known_buckets() == frozenset({settings.gcs_bucket_name})
