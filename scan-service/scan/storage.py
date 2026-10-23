"""
Object storage by gs:// URI — the scan-service's only I/O. It holds no
database connection: the backend owns all state and hands over URIs.
"""
from __future__ import annotations

from typing import Optional, Protocol


class ObjectMissing(LookupError):
    """The raw object is not there. Compile refuses on it (SCN-11) — a partial
    PDF presented as complete would be a silent repair."""


class Storage(Protocol):
    def read(self, uri: str) -> bytes: ...
    def write(self, uri: str, data: bytes, content_type: str) -> None: ...


def split_gs_uri(uri: str) -> tuple[str, str]:
    if not isinstance(uri, str) or not uri.startswith("gs://"):
        raise ValueError("not a gs:// uri")
    bucket, _, path = uri[len("gs://"):].partition("/")
    if not bucket or not path:
        raise ValueError("not a gs:// object uri")
    return bucket, path


class GcsStorage:
    def __init__(self, client=None) -> None:
        self._client = client

    @property
    def client(self):
        if self._client is None:
            from google.cloud import storage
            self._client = storage.Client()
        return self._client

    def read(self, uri: str) -> bytes:
        from google.api_core.exceptions import NotFound

        bucket, path = split_gs_uri(uri)
        try:
            return self.client.bucket(bucket).blob(path).download_as_bytes()
        except NotFound:
            raise ObjectMissing(path) from None

    def write(self, uri: str, data: bytes, content_type: str) -> None:
        bucket, path = split_gs_uri(uri)
        self.client.bucket(bucket).blob(path).upload_from_string(data, content_type=content_type)


_storage: Optional[Storage] = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = GcsStorage()
    return _storage


def set_storage(storage: Optional[Storage]) -> None:
    """Tests inject a fake; production never calls this."""
    global _storage
    _storage = storage
