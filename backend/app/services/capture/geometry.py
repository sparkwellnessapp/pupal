"""
Corner validation for a manual adjustment (§6.5) — pure.

Corners travel normalized to [0, 1], in the order TL, TR, BR, BL (the order
the corner editor's four handles keep; scan-service orders DETECTED corners
itself). A manual quad is accepted only if it is a page someone could mean:
four points inside the frame, convex, not self-intersecting, and covering at
least 5% of the frame. Anything else is a 422 — the client snaps back.
"""
from __future__ import annotations

from typing import Sequence

FULL_FRAME: list[list[float]] = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
MIN_AREA_FRACTION = 0.05


class InvalidCorners(ValueError):
    pass


def _cross(o, a, b) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def area(points: Sequence[Sequence[float]]) -> float:
    s = 0.0
    for i in range(4):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % 4]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def validate_corners(corners) -> list[list[float]]:
    """The validated quad as plain floats, or InvalidCorners."""
    try:
        pts = [[float(x), float(y)] for x, y in corners]
    except (TypeError, ValueError):
        raise InvalidCorners("corners must be four [x, y] pairs") from None
    if len(pts) != 4:
        raise InvalidCorners("corners must be four [x, y] pairs")
    if any(not (0.0 <= c <= 1.0) for p in pts for c in p):
        raise InvalidCorners("corners must lie inside the image")
    # Convex, simple AND clockwise on screen (y grows down), i.e. really in the
    # order TL, TR, BR, BL: every turn strictly positive. A "bow tie" alternates
    # sign, a concave quad flips one, and an all-negative quad is the page
    # MIRRORED — scan-service would flatten it back to front. (The editor
    # cannot make one: moving one handle never changes the opposite turn.)
    turns = [_cross(pts[i], pts[(i + 1) % 4], pts[(i + 2) % 4]) for i in range(4)]
    if not all(t > 1e-9 for t in turns):
        raise InvalidCorners("corners must form a convex, non-crossing shape")
    if area(pts) < MIN_AREA_FRACTION:
        raise InvalidCorners("the page is too small")
    return pts
