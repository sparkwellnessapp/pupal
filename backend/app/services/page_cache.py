"""
Bounded per-page render cache for the page proxy (PR-G8).

The census finding this closes: every page request downloaded the ENTIRE PDF
from GCS and re-rendered it. §1.5 puts a page-1 thumbnail on every batch card,
so one dashboard load of thirty tests was thirty full-PDF downloads — and it
would have been discovered during the pilot, on a school connection.

BOUNDED, because an unbounded cache in a Cloud Run container with a 2GiB limit
is a memory leak with a nicer name. LRU by insertion order, capped by entry
count; a rendered page is tens of KB, so the cap is the memory bound.

Keyed by (transcription_id, page_number, dpi). NOT by user: ownership is proved
by `get_owned_or_404` BEFORE the cache is consulted, so the cache never becomes
the thing that decides who may see a page.

Process-local by design. Cloud Run runs several instances, so this is a
per-instance hit-rate improvement, not a distributed cache — and it needs no
invalidation, because a transcription's page content is immutable once
uploaded.
"""
from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

MAX_ENTRIES = 256                       # ~tens of KB each

_lock = threading.Lock()
_cache: "OrderedDict[Tuple[str, int, int], str]" = OrderedDict()


def get(transcription_id, page_number: int, dpi: int) -> Optional[str]:
    key = (str(transcription_id), int(page_number), int(dpi))
    with _lock:
        value = _cache.get(key)
        if value is not None:
            _cache.move_to_end(key)      # LRU
        return value


def put(transcription_id, page_number: int, dpi: int, thumbnail_base64: str) -> None:
    key = (str(transcription_id), int(page_number), int(dpi))
    with _lock:
        _cache[key] = thumbnail_base64
        _cache.move_to_end(key)
        while len(_cache) > MAX_ENTRIES:
            _cache.popitem(last=False)


def clear() -> None:
    """Tests only — the cache has no invalidation in production because page
    content is immutable once uploaded."""
    with _lock:
        _cache.clear()


def size() -> int:
    with _lock:
        return len(_cache)
