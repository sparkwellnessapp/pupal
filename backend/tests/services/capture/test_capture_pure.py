"""
In-house scanning — the pure pieces, zero mocks (PR_in_house_scanning.md §10):
the link token (OD-4), corner validation (§6.5), and the Asia/Jerusalem exam-day
window (R5) across midnight and both DST transitions.
"""
import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from app.services.capture import geometry, tokens
from app.services.capture.links import link_state, today_il

LINK = uuid.UUID("11111111-2222-3333-4444-555555555555")


# ---------------------------------------------------------------------------
# OD-4 — the derived token
# ---------------------------------------------------------------------------

def test_the_link_token_is_derived_so_the_qr_can_be_reshown():
    a = tokens.link_token("secret", LINK, 1)
    assert a == tokens.link_token("secret", LINK, 1)            # recomputed, never stored
    assert len(a) == 22 and "=" not in a                      # 16 bytes, base64url


def test_rotation_and_another_secret_give_a_different_token():
    a = tokens.link_token("secret", LINK, 1)
    assert tokens.link_token("secret", LINK, 2) != a           # rotate-token
    assert tokens.link_token("other", LINK, 1) != a            # secret rotation: every link
    assert tokens.link_token("secret", uuid.uuid4(), 1) != a


def test_no_secret_no_token():
    with pytest.raises(tokens.CaptureNotConfigured):
        tokens.link_token("", LINK, 1)


def test_random_tokens_are_long_and_distinct():
    a, b = tokens.random_token(), tokens.random_token()
    assert a != b and len(a) == 43
    assert tokens.same_hash(tokens.sha256(a), tokens.sha256(a))
    assert not tokens.same_hash(tokens.sha256(a), tokens.sha256(b))


# ---------------------------------------------------------------------------
# §6.5 — corner validation
# ---------------------------------------------------------------------------

def test_a_reasonable_quad_is_accepted_as_floats():
    q = [[0.1, 0.1], [0.9, 0.12], [0.88, 0.9], [0.12, 0.88]]
    assert geometry.validate_corners(q) == q


@pytest.mark.parametrize("bad,why", [
    ([[0.1, 0.1], [0.9, 0.9], [0.9, 0.1], [0.1, 0.9]], "self-intersecting (bow tie)"),
    ([[0.1, 0.1], [0.9, 0.1], [0.5, 0.3], [0.1, 0.9]], "concave"),
    ([[0.4, 0.4], [0.5, 0.4], [0.5, 0.5], [0.4, 0.5]], "1% of the frame"),
    ([[0.1, 0.1], [1.2, 0.1], [0.9, 0.9], [0.1, 0.9]], "outside the image"),
    ([[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]], "three points"),
    ([[0.1, 0.1], [0.5, 0.5], [0.9, 0.9], [0.1, 0.9]], "collinear"),
], ids=lambda v: v if isinstance(v, str) else "")
def test_an_impossible_page_is_refused(bad, why):
    with pytest.raises(geometry.InvalidCorners):
        geometry.validate_corners(bad)


def test_the_full_frame_is_valid():
    assert geometry.validate_corners(geometry.FULL_FRAME) == geometry.FULL_FRAME


# ---------------------------------------------------------------------------
# R5 — the exam day is the Asia/Jerusalem calendar day
# ---------------------------------------------------------------------------

def _utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


@pytest.mark.parametrize("instant,day", [
    (_utc(2026, 11, 3, 21, 59), date(2026, 11, 3)),     # 23:59 Israel (UTC+2, winter)
    (_utc(2026, 11, 3, 22, 1), date(2026, 11, 4)),      # 00:01 Israel — UTC is still the 3rd
    (_utc(2026, 7, 1, 20, 59), date(2026, 7, 1)),       # 23:59 Israel (UTC+3, summer)
    (_utc(2026, 7, 1, 21, 1), date(2026, 7, 2)),
    # DST begins Fri 27 Mar 2026 02:00 → 03:00; ends Sun 25 Oct 2026 02:00 → 01:00
    (_utc(2026, 3, 26, 22, 30), date(2026, 3, 27)),     # 00:30 Israel on the change day
    (_utc(2026, 3, 27, 21, 30), date(2026, 3, 28)),     # 00:30 the next day (now UTC+3)
    (_utc(2026, 10, 24, 21, 30), date(2026, 10, 25)),   # 00:30 Israel on the fall-back day
    (_utc(2026, 10, 25, 21, 59), date(2026, 10, 25)),   # 23:59 that day (UTC+2 again)
])
def test_today_is_the_israel_calendar_day(instant, day):
    assert today_il(instant) == day


def _link(exam_date, closed=False):
    return SimpleNamespace(exam_date=exam_date, closed_at=_utc(2026, 1, 1) if closed else None)


def test_the_window_is_exactly_the_exam_date():
    d = date(2026, 11, 4)
    assert link_state(_link(d), date(2026, 11, 3)) == "not_yet_open"
    assert link_state(_link(d), d) == "open"
    assert link_state(_link(d), date(2026, 11, 5)) == "closed"
    assert link_state(_link(d, closed=True), d) == "closed"          # closed early
