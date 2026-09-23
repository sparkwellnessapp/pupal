"""
The purge's view of object storage: a three-call protocol, and a guard in
front of it that validates every target first (PRV-11).

The protocol is synchronous, like the GCS client it wraps; callers push it
through a thread. Tests hand in a recording fake — the witness for "zero
storage calls" and for "the deleted set IS the plan" (PRV-6).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol

from .targets import known_buckets as _configured_buckets
from .targets import validate_object, validate_target


class StorageClient(Protocol):
    def list_prefix(self, bucket: str, prefix: str) -> list[str]: ...
    def list_soft_deleted(self, bucket: str, prefix: str) -> list[tuple[str, datetime]]: ...
    def delete_object(self, bucket: str, name: str) -> None: ...


class GuardedStorage:
    """Every call validated against PRV-11 before the client sees it; a refusal
    raises `UnsafeStorageTarget` having made no call at all."""

    def __init__(self, inner: StorageClient, *, known_buckets: Optional[frozenset[str]] = None):
        self._inner = inner
        self.known_buckets = frozenset(known_buckets) if known_buckets is not None \
            else _configured_buckets()

    def list_prefix(self, bucket: str, prefix: str) -> list[str]:
        validate_target(bucket, prefix, known_buckets=self.known_buckets)
        return list(self._inner.list_prefix(bucket, prefix))

    def list_soft_deleted(self, bucket: str, prefix: str) -> list[tuple[str, datetime]]:
        validate_target(bucket, prefix, known_buckets=self.known_buckets)
        return list(self._inner.list_soft_deleted(bucket, prefix))

    def delete_object(self, bucket: str, name: str) -> None:
        validate_object(bucket, name, known_buckets=self.known_buckets)
        self._inner.delete_object(bucket, name)


class GcsStorage:
    """The real bucket, through the service's one GCS client (same credentials
    as every other storage call)."""

    def __init__(self, client=None):
        if client is None:
            from app.services.gcs_service import get_gcs_service
            client = get_gcs_service().client
        self._client = client

    def list_prefix(self, bucket: str, prefix: str) -> list[str]:
        return [b.name for b in self._client.list_blobs(bucket, prefix=prefix)]

    def list_soft_deleted(self, bucket: str, prefix: str) -> list[tuple[str, datetime]]:
        # A soft-deleted object stays restorable until its hard-delete time
        # (7 days on the student-data bucket, OD-B3); `ls` never shows it.
        return [(b.name, b.hard_delete_time)
                for b in self._client.list_blobs(bucket, prefix=prefix, soft_deleted=True)]

    def delete_object(self, bucket: str, name: str) -> None:
        from google.api_core.exceptions import NotFound

        try:
            self._client.bucket(bucket).blob(name).delete()
        except NotFound:
            pass                     # already gone: a retry of a delete is a no-op


def get_purge_storage() -> GuardedStorage:
    """FastAPI dependency: the guarded real bucket. Tests override it with a
    guarded fake; nothing else about the request is faked (CLAUDE.md §9)."""
    return GuardedStorage(GcsStorage())
