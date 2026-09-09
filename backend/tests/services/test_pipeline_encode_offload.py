"""
Stage C1 (UPLOAD_LATENCY_PLAN.md) — page encoding moved OFF the event loop.

THE DEFECT. `pdf_render` was already in an executor, but the resize + PNG +
base64 that follows it ran inline on the request thread — twice per page since
the strike-check pass shipped. Cloud Run runs this service at cpu=1000m with
containerConcurrency=4, so four concurrent transcription requests spent that
CPU on the loop and starved the teacher's interactive uploads on the same
instance (measured: appends 0.43s → 5.3, 5.9, 15.6s exactly when they
overlapped a transcription with the same instanceId).

THE BAR (ruling R1 — the model's input is FROZEN). This change may not alter a
single byte the model receives; it moves the same work to a different thread.
That is not a claim to take on faith, so the first test below is the proof:
the executor path's base64 must equal the inline encoders' base64, byte for
byte. It is the C1 analogue of the page-proxy's byte-equality guarantee
(`tests/api/test_transcription_page_render.py`).

Zero mocks, zero network: pure Pillow images through the pure encoders.
"""
import asyncio

import pytest
from PIL import Image

from app.services.transcription.two_phase.pipeline import (
    _encode_pages_sync,
    _resize,
    _stitch,
    _to_b64_image,
)


def _page(seed: int, w: int = 1400, h: int = 1900) -> Image.Image:
    """A deterministic non-uniform page. Flat colour would encode identically
    under almost any bug, so this varies per pixel and per seed."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(0, h, 7):
        for x in range(0, w, 5):
            px[x, y] = ((x + seed) % 256, (y * 3 + seed) % 256, (x * y) % 256)
    return img


PAGES = [_page(11), _page(29), _page(47)]


# ---------------------------------------------------------------------------
# THE R1 PROOF: same bytes, different thread.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fmt,quality", [("png", 90), ("jpeg", 90), ("jpeg", 72)])
@pytest.mark.parametrize("max_px", [2000, 1000])
def test_offloaded_encode_is_byte_identical_to_the_inline_encoders(fmt, quality, max_px):
    inline = [_to_b64_image(_resize(img, max_px), fmt, quality) for img in PAGES]
    offloaded = _encode_pages_sync(PAGES, max_px, fmt, quality)
    assert offloaded == inline


def test_stitched_packing_is_byte_identical_too():
    """The `stitched` branch is the one a refactor is most likely to drop —
    it is off in PROD_CONFIG, so nothing else here would notice."""
    inline = [_to_b64_image(_stitch([_resize(i, 2000) for i in PAGES]), "png", 90)]
    assert _encode_pages_sync(PAGES, 2000, "png", 90, stitch=True) == inline


def test_a_single_page_never_stitches():
    """`stitch=True` with one page must behave exactly like the unstitched
    path — the old inline code guarded on `len(resized) > 1` and so does this."""
    one = [PAGES[0]]
    assert (_encode_pages_sync(one, 2000, "png", 90, stitch=True)
            == _encode_pages_sync(one, 2000, "png", 90, stitch=False))


def test_page_order_is_preserved():
    """Order IS meaning here: the encoded list is zipped against page numbers
    downstream, so a reordering would silently mislabel every page."""
    out = _encode_pages_sync(PAGES, 2000, "png", 90)
    assert out == [_to_b64_image(_resize(p, 2000), "png", 90) for p in PAGES]
    assert len(set(out)) == 3            # the fixtures really are distinct


def test_running_it_through_an_executor_changes_nothing():
    """The call shape the pipeline actually uses."""
    async def go():
        return await asyncio.get_running_loop().run_in_executor(
            None, _encode_pages_sync, PAGES, 2000, "png", 90, False)

    assert asyncio.run(go()) == _encode_pages_sync(PAGES, 2000, "png", 90)


# ---------------------------------------------------------------------------
# The point of the exercise: the loop stays responsive while encoding runs.
# ---------------------------------------------------------------------------

def test_the_event_loop_keeps_running_during_an_encode():
    """A regression here is invisible to every other test in this file — the
    bytes would still be right, and only the latency would come back.

    So: start a real encode in the executor and count how many times a 5ms
    heartbeat gets to run while it is in flight. Inline, the loop is blocked
    and the heartbeat cannot tick at all.
    """
    heavy = [_page(i, 2200, 3000) for i in range(4)]

    async def go() -> int:
        ticks = 0
        done = asyncio.Event()

        async def heartbeat():
            nonlocal ticks
            while not done.is_set():
                await asyncio.sleep(0.005)
                ticks += 1

        beat = asyncio.create_task(heartbeat())
        await asyncio.get_running_loop().run_in_executor(
            None, _encode_pages_sync, heavy, 2000, "png", 90, False)
        done.set()
        await beat
        return ticks

    # A PNG encode of four 2200x3000 pages takes well over 100ms, so a
    # responsive loop ticks many times. `> 1` is the assertion because the
    # threshold that matters is "the loop ran AT ALL", and anything tighter
    # would be a timing test on shared CI hardware.
    assert asyncio.run(go()) > 1


# ---------------------------------------------------------------------------
# The regression the eval suite caught: offloading also made the encode AWAIT.
# ---------------------------------------------------------------------------

def test_chunks_dispatch_in_chunk_order_not_encode_completion_order():
    """Moving the encode into a thread also made it yield, and the P1 chunks run
    under one `asyncio.gather` — so whichever chunk finished ENCODING first
    dispatched first. That is not random: the smaller chunk finishes sooner, so
    a 5-page document at 3-per-call reliably issued its 2-page call before its
    3-page one (measured 8/8 before the fix).

    Nothing the model receives changes and the merge is by page number, so the
    transcription is identical either way. But Stage C1's bar is "same
    behaviour, different thread", and a dispatch order that flips is not that —
    so `Pipeline._encode_lock` reproduces the sequence the inline code had. It
    costs nothing, because inline encodes were already serial on the loop.

    This is a PURE simulation of that structure: no pipeline, no providers, no
    network — two gathered tasks that encode then "dispatch", with the same lock.
    """
    small = [_page(1, 900, 1200)]
    large = [_page(2, 2200, 3000), _page(3, 2200, 3000), _page(4, 2200, 3000)]

    async def go() -> list[str]:
        dispatched: list[str] = []
        lock = asyncio.Lock()
        loop = asyncio.get_running_loop()

        async def chunk(name: str, images):
            async with lock:
                await loop.run_in_executor(
                    None, _encode_pages_sync, images, 2000, "png", 90, False)
            dispatched.append(name)

        # `large` is created FIRST, exactly as chunk order would have it, and it
        # is the slower one to encode.
        await asyncio.gather(chunk("large", large), chunk("small", small))
        return dispatched

    assert asyncio.run(go()) == ["large", "small"]
