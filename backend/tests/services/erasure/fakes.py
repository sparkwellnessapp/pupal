"""
An in-memory object store that records every call.

It is the purge's storage client in tests, and the witness for three
invariants that are about CALLS, not results:

  PRV-6  PlanEqualsExecution  — `deleted` equals the plan's object set
  PRV-11 PrefixSafety         — a refused target leaves `calls` empty
  PRV-3  ObjectsNeverSilentlyKept — `fail_on` makes one delete raise

It speaks the storage protocol the erasure core is written against
(`list_prefix`, `list_soft_deleted`, `delete_object`), synchronous like the
GCS client it stands in for. A deleted object moves to `soft_deleted` with a
restorable-until time, as the real bucket's 7-day policy does (OD-B3).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

SOFT_DELETE_WINDOW = timedelta(days=7)


class FakeStorage:
    def __init__(self, objects: Iterable[tuple[str, str]] = ()) -> None:
        self.live: set[tuple[str, str]] = set(objects)
        self.soft_deleted: dict[tuple[str, str], datetime] = {}
        self.calls: list[tuple[str, str, str]] = []
        self.deleted: list[tuple[str, str]] = []
        self.fail_on: set[tuple[str, str]] = set()

    def list_prefix(self, bucket: str, prefix: str) -> list[str]:
        self.calls.append(("list", bucket, prefix))
        return sorted(n for (b, n) in self.live if b == bucket and n.startswith(prefix))

    def list_soft_deleted(self, bucket: str, prefix: str) -> list[tuple[str, datetime]]:
        self.calls.append(("list_soft_deleted", bucket, prefix))
        return sorted((n, t) for (b, n), t in self.soft_deleted.items()
                      if b == bucket and n.startswith(prefix))

    def delete_object(self, bucket: str, name: str) -> None:
        self.calls.append(("delete", bucket, name))
        if (bucket, name) in self.fail_on:
            raise PermissionError(f"403 Forbidden: {bucket}/{name}")
        self.live.discard((bucket, name))
        self.deleted.append((bucket, name))
        self.soft_deleted[(bucket, name)] = datetime.now(timezone.utc) + SOFT_DELETE_WINDOW

    def delete_calls(self) -> list[tuple[str, str]]:
        return [(b, n) for (op, b, n) in self.calls if op == "delete"]
