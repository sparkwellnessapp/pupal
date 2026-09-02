"""
Bounded per-page render cache for the page proxies (PR-G8).

The census finding this closes: every page request downloaded the ENTIRE PDF
from GCS and re-rendered it. §1.5 puts a page-1 thumbnail on every batch card,
so one dashboard load of thirty tests was thirty full-PDF downloads — and it
would have been discovered during the pilot, on a school connection.

BOUNDED BY BYTES, NOT BY ENTRIES — and that correction has a history worth
keeping. This cache used to cap at `MAX_ENTRIES = 256`, justified in this very
docstring with "a rendered page is tens of KB, so the cap is the memory bound".
MEASURED on the six real bagrut scans: a review page is **1168 KB p50, 1870 KB
max** — the claim was wrong by ~40x, so a full cache was **~300 MB (worst case
~480 MB)** in a container with a 2 GiB limit whose concurrency had already been
cut 5→4 on an OOM measurement (CLAUDE.md §12). The entry count was never the
memory bound. Bytes are, so bytes are what is counted. Do not reintroduce an
entry cap "as well" — two bounds means one of them is decorative and nobody
knows which.

KEYED BY (transcription_id, page_number, variant). The `variant` namespaces the
representation: `png-b64@150` is the review path's base64 PNG, `webp@600x72@110`
is a §1.5 card thumbnail. They are DIFFERENT RESOURCES at wildly different
sizes, and sharing a key would serve a 600 px thumb to the review pane or a
1.1 MB PNG to a card.

NOT keyed by user: ownership is proved by `get_owned_or_404` BEFORE the cache is
consulted, so the cache never becomes the thing that decides who may see a page.

Process-local by design. Cloud Run runs several instances, so this is a
per-instance hit-rate improvement, not a distributed cache — and it needs no
invalidation, because a transcription's page content is immutable once uploaded
and a settings change mints a new `variant` rather than mutating an old one.
"""
from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from typing import Optional, Tuple, Union

from ..config import settings

logger = logging.getLogger(__name__)

Value = Union[bytes, str]
Key = Tuple[str, int, str]

_lock = threading.Lock()
_cache: "OrderedDict[Key, Value]" = OrderedDict()
_total_bytes = 0


def _budget() -> int:
    """Read at CALL time so the cap can be changed without a restart — the same
    discipline as the other operational dials."""
    try:
        return max(0, int(settings.page_cache_max_bytes))
    except (TypeError, ValueError):            # pragma: no cover — config typo
        logger.warning("page_cache_max_bytes_invalid; caching disabled")
        return 0


def _charge(value: Value) -> int:
    """Bytes a value costs. `len()` of an ASCII base64 str is ~1 byte/char, so
    it is a faithful proxy; for bytes it is exact."""
    return len(value)


def _key(transcription_id, page_number: int, variant: str) -> Key:
    return (str(transcription_id), int(page_number), str(variant))


def get(transcription_id, page_number: int, variant: str) -> Optional[Value]:
    key = _key(transcription_id, page_number, variant)
    with _lock:
        value = _cache.get(key)
        if value is not None:
            _cache.move_to_end(key)          # LRU
        return value


def put(transcription_id, page_number: int, variant: str, value: Value) -> None:
    global _total_bytes
    key = _key(transcription_id, page_number, variant)
    cost = _charge(value)
    budget = _budget()

    # An item bigger than the whole budget is NOT cached. Admitting it would
    # evict everything else to store one entry that the next put evicts again —
    # a cache that holds nothing while doing all the work of a cache.
    if cost > budget:
        logger.info("page_cache_item_exceeds_budget",
                    extra={"bytes": cost, "budget": budget})
        with _lock:
            if key in _cache:                # a smaller earlier value may exist
                _total_bytes -= _charge(_cache.pop(key))
        return

    with _lock:
        if key in _cache:
            _total_bytes -= _charge(_cache.pop(key))
        _cache[key] = value
        _total_bytes += cost
        while _total_bytes > budget and _cache:
            _, evicted = _cache.popitem(last=False)
            _total_bytes -= _charge(evicted)


def clear() -> None:
    """Tests only — the cache has no invalidation in production because page
    content is immutable once uploaded."""
    global _total_bytes
    with _lock:
        _cache.clear()
        _total_bytes = 0


def size() -> int:
    """Entry count. Diagnostics only — the BOUND is `total_bytes()`."""
    with _lock:
        return len(_cache)


def total_bytes() -> int:
    with _lock:
        return _total_bytes
