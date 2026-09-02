"""
Page thumbnails — the small WebP representation, and the variant token that
names it. (PR-G8 · PLAN_page1_image_route §4.1/§4.3)

WHY A SECOND REPRESENTATION AT ALL. The JSON page proxy renders a review-grade
image and hands it over as base64 PNG. Measured on the six real bagrut scans
(p50 of 3 runs each): **1168 KB and 1227 ms per page**. §1.5 puts a page-1
thumbnail on every batch card, so a thirty-card dashboard on that path is ~34 MB
over the wire and ~37 s of render — and it would have been discovered during the
pilot, on a school connection. This variant is **33.6 KB and 259 ms**: ~35x
fewer bytes, ~4.7x less render. It is not the same resource wearing a different
URL; it is a different resource, and it is keyed separately so the review pane
can never be served a 600 px thumb nor a card a 1.1 MB PNG.

WHY `render_dpi` EXCEEDS THE OUTPUT WIDTH. It is SUPERSAMPLING, not resolution:
rendering at 110 dpi and LANCZOS-ing down to 600 px is visibly sharper than
rendering at 72 dpi directly, and the measurement says it costs ~2 KB and ~36 ms
(72→600: 31.7 KB/223 ms · 110→600: 33.6 KB/259 ms · 150→600: 34.5 KB/421 ms).
150 buys nothing but time.

WHY THE VARIANT IS IN THE URL — and this is the part that is easy to delete and
expensive to lose. The route answers with `Cache-Control: ... immutable` and a
one-year lifetime, while the three render settings are config tunables. Without
the variant in the URL, changing `page_thumb_width_px` 600→800 leaves every
browser that already cached a thumb holding the OLD bytes for a year, with
`immutable` telling it not even to revalidate — and there is no bust short of
changing the URL. So the URL carries `?v=600x72@110`, minted server-side, and
the route resolves both the render settings AND the cache key from it. URL,
cache key and bytes are then one fact in three places instead of three that can
drift.

THE TOKEN IS NOT A FREE PARAMETER. It must be in the allow-set (current settings
∪ `page_thumb_legacy_variants`). A token the route parsed into render settings
without that check would be a client-controlled rasterizer: `?v=20000x100@600`
is a render-bomb, not a cache key.
"""
from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from typing import Optional, Tuple

from PIL import Image

from ..config import settings
from .pdf_render import render_page

logger = logging.getLogger(__name__)

#: `{width}x{quality}@{dpi}`. Bounded digit runs so a hostile token cannot even
#: reach int() with something pathological; the allow-set is the real gate.
#:
#: NO LEADING ZEROS, deliberately. `600x072@110` parses to the same three numbers
#: as `600x72@110` and would therefore be *allowed*, mapping to the same
#: canonical cache key — harmless on the server, but it lets a caller mint
#: unbounded distinct URLs for identical bytes, which defeats the BROWSER cache
#: that is the entire reason the variant is in the URL. One spelling per
#: resource keeps ⟨C1⟩'s "the URL and the cache key cannot disagree" literally
#: true rather than nearly true.
_TOKEN_RE = re.compile(r"^([1-9]\d{0,4})x([1-9]\d{0,2})@([1-9]\d{0,3})$")

MEDIA_TYPE = "image/webp"

#: A year. Sent ONLY with `immutable`, and only when the URL pins the bytes.
IMMUTABLE_MAX_AGE = 31_536_000
#: What an un-pinned URL (no `?v=`) gets: short, and never `immutable`, because
#: that URL makes no promise about which variant it returns.
UNPINNED_MAX_AGE = 60


@dataclass(frozen=True)
class ThumbVariant:
    """The three numbers that decide the bytes, as one value."""
    width_px: int
    quality: int
    render_dpi: int

    @property
    def token(self) -> str:
        return f"{self.width_px}x{self.quality}@{self.render_dpi}"

    @property
    def cache_variant(self) -> str:
        """Cache namespace. Distinct from the review path's `png-b64@<dpi>` —
        sharing a namespace is how a card gets a review PNG or the review pane
        gets a 600 px thumb."""
        return f"webp@{self.token}"

    @classmethod
    def parse(cls, token: str) -> Optional["ThumbVariant"]:
        """Grammar only — says nothing about whether the variant is ALLOWED."""
        match = _TOKEN_RE.match((token or "").strip())
        if not match:
            return None
        width, quality, dpi = (int(g) for g in match.groups())
        if width < 1 or dpi < 1 or not (1 <= quality <= 100):
            return None
        return cls(width_px=width, quality=quality, render_dpi=dpi)


def current_variant() -> ThumbVariant:
    """What the feed mints today. Read at CALL time, never frozen at import, so
    a settings change takes effect on the next request rather than the next
    deploy — the same discipline as `grader_max_concurrent_scopes`."""
    return ThumbVariant(
        width_px=int(settings.page_thumb_width_px),
        quality=int(settings.page_thumb_quality),
        render_dpi=int(settings.page_thumb_render_dpi),
    )


def allowed_variants() -> Tuple[ThumbVariant, ...]:
    """Current ∪ the deliberately-retained legacy tokens.

    A malformed entry in `page_thumb_legacy_variants` is DROPPED with a warning
    rather than raising: an unparseable config string must not take the route
    down, and the failure is visible in the logs. The current variant is always
    first and can never be excluded by config.
    """
    out = [current_variant()]
    for token in (settings.page_thumb_legacy_variants or []):
        variant = ThumbVariant.parse(token)
        if variant is None:
            logger.warning("page_thumb_legacy_variant_unparseable",
                           extra={"token": str(token)[:32]})
            continue
        if variant not in out:
            out.append(variant)
    return tuple(out)


def resolve_variant(token: Optional[str]) -> Tuple[Optional[ThumbVariant], bool]:
    """`?v=` → (variant, pinned).

    * absent/empty  → (current, False). Renders, but the answer must NOT claim
      `immutable`: the URL named no variant, so it promises nothing.
    * allowed token → (that variant, True). The URL pins the bytes, so a
      one-year `immutable` is honest.
    * anything else → (None, False). The caller answers 404 — the same
      vocabulary the route already uses for "no such resource", and what stops
      the token being a client-controlled rasterizer.
    """
    if not token:
        return current_variant(), False
    variant = ThumbVariant.parse(token)
    if variant is None or variant not in allowed_variants():
        return None, False
    return variant, True


def webp_available() -> bool:
    """Can this interpreter actually encode WebP?

    NOT a formality. Pillow's WebP support is a COMPILE-TIME option: the wheel
    on a developer's laptop can have it while the one installed into the image
    does not, and the failure mode is silent until a teacher loads a dashboard
    and every card 502s. The vendored-Hebrew-font lesson exactly (PR-G9: perfect
    on a laptop, tofu on Cloud Run), so it is checked where it matters — in the
    running process — rather than trusted from a local check.
    """
    try:
        from PIL import features
        return bool(features.check("webp"))
    except Exception:                                  # pragma: no cover
        return False


def log_capability_on_boot() -> bool:
    """Say so, loudly, at startup. Follows `verify_schema_head`'s discipline: it
    LOGS and never crashes, because a degraded thumbnail is not a reason to
    refuse to serve grading."""
    ok = webp_available()
    if ok:
        logger.info("THUMBNAIL OK: WebP encoder available (%s)",
                    current_variant().token)
    else:
        logger.error(
            "THUMBNAIL UNAVAILABLE: this Pillow build cannot encode WebP, so "
            "every page-1 card thumbnail will fail. Check the Pillow wheel in "
            "the image (PIL.features.check('webp'))."
        )
    return ok


def render_page_thumbnail(
    pdf_bytes: bytes,
    page_number: int,
    *,
    width_px: int,
    quality: int,
    render_dpi: int,
) -> bytes:
    """One page → WebP bytes. Pure: no I/O, no settings read, no session.

    Goes through `pdf_render.render_page`, the ONE rasterizer — a fourth copy is
    exactly the drift that module's docstring exists to prevent. Raises
    `ValueError` for an out-of-range page, unchanged from `render_page`, so the
    route's 404 guard is the same guard the JSON proxy already has.
    """
    image = render_page(pdf_bytes, page_number, render_dpi)
    if image.mode != "RGB":
        # WebP has no palette mode and RGBA would carry an alpha channel a scan
        # never has; both cost bytes for nothing.
        image = image.convert("RGB")
    if image.width > width_px:
        height = max(1, round(image.height * width_px / image.width))
        image = image.resize((width_px, height), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    # method=4 is Pillow's default speed/size trade; measured at the pinned
    # settings it is the 259 ms in the table above.
    image.save(buffer, format="WEBP", quality=quality, method=4)
    return buffer.getvalue()


def render_variant(pdf_bytes: bytes, page_number: int, variant: ThumbVariant) -> bytes:
    """`render_page_thumbnail` addressed by variant — the shape the route wants,
    so the three numbers travel together and cannot be paired up wrongly."""
    return render_page_thumbnail(
        pdf_bytes, page_number,
        width_px=variant.width_px,
        quality=variant.quality,
        render_dpi=variant.render_dpi,
    )


def gcs_object_path(transcription_id, page_number: int, variant: ThumbVariant) -> str:
    """Where a rendered thumbnail is kept (phase 2).

    ⚠ THE VARIANT IS IN THE OBJECT PATH, and it has to be. The PR-G8 spec line
    named `thumbs/{transcription_id}/p1.webp`, from before the variant existed;
    keeping that would rebuild the exact bug ⟨C1⟩ fixed for the browser, one
    layer down — change `page_thumb_width_px` and every teacher is served the
    old bytes from GCS forever, with no expiry to age them out and no request
    that can ever miss. A variant-keyed path makes a settings change a new
    object, and the old one is garbage rather than a lie.
    """
    return (f"thumbs/{transcription_id}/p{int(page_number)}"
            f"_{variant.token.replace('@', '-')}.webp")


def page_image_path(transcription_id, page_number: int = 1,
                    variant: Optional[ThumbVariant] = None) -> str:
    """The value that goes on the wire as `BatchGradedItem.page1_image_url`.

    RELATIVE on purpose: `apiFetchRaw` prefixes `NEXT_PUBLIC_API_URL`, and an
    absolute URL here would bake the environment into a stored payload.

    ⚠ Usable ONLY through the client seam. Dropped into a bare `<img src>` this
    resolves against the FRONTEND origin and 404s from Next — not a 401 from the
    API — which sends whoever is debugging it to the wrong service.
    """
    variant = variant or current_variant()
    return (f"/api/v0/transcriptions/{transcription_id}"
            f"/pages/{page_number}/image?v={variant.token}")
