"""
The page cache is bounded by BYTES, and its variants cannot answer for each other.

Both properties were established by measurement, not taste (PLAN §2):

* The cache used to cap at 256 ENTRIES, justified by a docstring claiming "a
  rendered page is tens of KB". A review page measures 1168 KB p50 / 1870 KB
  max, so that cap was ~300 MB — worst case ~480 MB — in a 2 GiB container whose
  concurrency had already been cut 5→4 on an OOM measurement.
* The card thumbnail (33.6 KB WebP) and the review image (1168 KB base64 PNG)
  are different resources at ~35x different sizes. A shared key would serve a
  600 px thumb to the review pane, or a 1.1 MB PNG to a batch card.
"""
from __future__ import annotations

import pytest

from app.config import settings
from app.services import page_cache


@pytest.fixture(autouse=True)
def _clean_cache():
    page_cache.clear()
    original = settings.page_cache_max_bytes
    yield
    settings.page_cache_max_bytes = original
    page_cache.clear()


def test_page_cache_is_bounded_by_bytes_not_entries():
    """300 large entries must not exceed the budget — the §2 memory fix.

    Under the old entry cap this stored 256 x 1 MB = 268 MB while reporting
    itself as "bounded".
    """
    settings.page_cache_max_bytes = 4 * 1024 * 1024          # 4 MiB
    one_mib = b"x" * (1024 * 1024)

    for i in range(300):
        page_cache.put("t", i, "webp@600x72@110", one_mib)

    assert page_cache.total_bytes() <= 4 * 1024 * 1024, (
        f"cache holds {page_cache.total_bytes()} bytes over a 4 MiB budget")
    assert page_cache.size() <= 4, (
        "a byte budget of 4 MiB cannot hold more than four 1 MiB entries")


def test_eviction_is_lru_not_arbitrary():
    settings.page_cache_max_bytes = 3 * 1024
    for i in range(3):
        page_cache.put("t", i, "v", b"y" * 1024)
    page_cache.get("t", 0, "v")                              # 0 becomes newest
    page_cache.put("t", 3, "v", b"y" * 1024)                 # evicts the oldest

    assert page_cache.get("t", 0, "v") is not None, "the touched entry was evicted"
    assert page_cache.get("t", 1, "v") is None, "the least-recently-used survived"


def test_an_item_larger_than_the_whole_budget_is_not_cached():
    """Admitting it would evict everything to store one entry the next put
    evicts again — a cache that holds nothing while doing a cache's work."""
    settings.page_cache_max_bytes = 1024
    page_cache.put("t", 1, "v", b"keep" * 8)
    page_cache.put("t", 2, "v", b"z" * 4096)

    assert page_cache.get("t", 2, "v") is None, "the oversized item was admitted"
    assert page_cache.get("t", 1, "v") is not None, "it evicted the rest on the way in"


def test_replacing_a_key_does_not_double_count_its_bytes():
    settings.page_cache_max_bytes = 1024 * 1024
    page_cache.put("t", 1, "v", b"a" * 100)
    page_cache.put("t", 1, "v", b"b" * 300)

    assert page_cache.size() == 1
    assert page_cache.total_bytes() == 300, (
        f"accounting drifted: {page_cache.total_bytes()} for a single 300-byte value")


def test_webp_variant_does_not_evict_or_answer_for_the_review_png():
    """Variant isolation — the review pane must never receive a 600 px thumb."""
    settings.page_cache_max_bytes = 1024 * 1024
    page_cache.put("t", 1, "png-b64@150", "BASE64-REVIEW-IMAGE")
    page_cache.put("t", 1, "webp@600x72@110", b"RIFF....WEBP")

    assert page_cache.get("t", 1, "png-b64@150") == "BASE64-REVIEW-IMAGE"
    assert page_cache.get("t", 1, "webp@600x72@110") == b"RIFF....WEBP"
    assert page_cache.get("t", 1, "webp@800x72@110") is None, (
        "a variant nobody stored answered from another variant's bytes")
    assert page_cache.size() == 2, "the two representations collapsed into one key"


def test_a_new_variant_token_misses_rather_than_serving_stale_bytes():
    """⟨C1⟩ the settings-change path: a new token is a new resource."""
    settings.page_cache_max_bytes = 1024 * 1024
    page_cache.put("t", 1, "webp@600x72@110", b"OLD")
    assert page_cache.get("t", 1, "webp@800x72@110") is None


def test_byte_accounting_does_not_drift_under_concurrent_use():
    """The running total is mutated from many threads; if it drifts the cache
    silently stops being bounded, which is the whole defect this module was
    just fixed for. FastAPI runs the render in a threadpool, so this is the
    real access pattern, not a hypothetical.
    """
    import random
    import threading

    import app.services.page_cache as pc

    settings.page_cache_max_bytes = 512 * 1024
    page_cache.clear()

    def churn(seed):
        rng = random.Random(seed)
        for _ in range(400):
            key = rng.randrange(40)
            if rng.random() < 0.6:
                page_cache.put("t", key, "v", b"x" * rng.randrange(1, 40_000))
            else:
                page_cache.get("t", key, "v")

    threads = [threading.Thread(target=churn, args=(s,)) for s in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with pc._lock:
        truth = sum(len(v) for v in pc._cache.values())
    assert page_cache.total_bytes() == truth, (
        f"accounting drifted: reported {page_cache.total_bytes()}, actual {truth}")
    assert page_cache.total_bytes() <= settings.page_cache_max_bytes
