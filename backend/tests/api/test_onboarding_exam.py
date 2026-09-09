"""PATCH /api/v0/users/me/onboarding-exam — the 028 §5 contract.

Real users, real Bearer tokens (tests/api/conftest.py). The auth dependency is
NEVER faked here: a `dependency_overrides` stand-in would bypass exactly the
code §9 exists to protect, which is how the users.py query-parameter auth bug
survived a month.
"""
from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest

from tests.api.auth_helpers import signup_verified

ENDPOINT = "/api/v0/users/me/onboarding-exam"


@pytest.fixture
def fresh_headers(client):
    """A brand-new signed-in teacher PER TEST.

    Function-scoped on purpose: nearly every assertion here is about a
    transition from a known starting state («she had no phone», «she had never
    answered»), and the session-scoped user_a/user_b would carry whichever
    test ran first into all the others. Signup is cheap; a false green is not.
    """
    def _make() -> dict:
        user = signup_verified(
            client,
            email=f"exam_{uuid4().hex[:10]}@s2test.com",
            full_name="מורה מבחן",
        )
        return {"Authorization": f"Bearer {user['access_token']}"}

    return _make


def _iso(days_ahead: int) -> str:
    return (date.today() + timedelta(days=days_ahead)).isoformat()


# ---------------------------------------------------------------------------
# Auth & ownership (§9)
# ---------------------------------------------------------------------------

def test_requires_a_token(client):
    resp = client.patch(ENDPOINT, json={"next_exam_date": _iso(30)})
    assert resp.status_code in (401, 403), resp.text


def test_a_body_supplied_user_id_is_ignored(client, fresh_headers):
    """The owning row is the PRINCIPAL's. A caller-supplied user id is a
    privilege-escalation bug, and the model simply has no such field."""
    headers_a, headers_b = fresh_headers(), fresh_headers()
    b_before = client.patch(
        ENDPOINT, headers=headers_b, json={"next_exam_date": _iso(40)},
    )
    assert b_before.status_code == 200, b_before.text

    resp = client.patch(
        ENDPOINT,
        headers=headers_a,
        json={"next_exam_date": _iso(10), "user_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["next_exam_date"] == _iso(10)

    # B is untouched — the write went to A's row and only A's row.
    b_after = client.patch(ENDPOINT, headers=headers_b, json={})
    assert b_after.json()["next_exam_date"] == _iso(40)


# ---------------------------------------------------------------------------
# Validation — ONB-1, minimal by design
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("days", [-8, -400])
def test_a_date_too_far_in_the_past_is_refused(client, headers_a, days):
    resp = client.patch(ENDPOINT, headers=headers_a, json={"next_exam_date": _iso(days)})
    assert resp.status_code == 422, resp.text


def test_a_date_beyond_eighteen_months_is_refused(client, headers_a):
    resp = client.patch(ENDPOINT, headers=headers_a, json={"next_exam_date": _iso(600)})
    assert resp.status_code == 422, resp.text


@pytest.mark.parametrize("days", [-7, 0, 1, 540])
def test_the_window_itself_is_accepted(client, headers_a, days):
    """Both edges are INSIDE. -7 exists because she may answer on Sunday about
    Thursday's exam; 0 because "today" is a real answer."""
    resp = client.patch(ENDPOINT, headers=headers_a, json={"next_exam_date": _iso(days)})
    assert resp.status_code == 200, resp.text


def test_consent_without_a_phone_is_refused(client, fresh_headers):
    headers_c = fresh_headers()
    resp = client.patch(ENDPOINT, headers=headers_c, json={"whatsapp_opt_in": True})
    assert resp.status_code == 422, resp.text
    # Hebrew, because she is the one reading it.
    assert "טלפון" in resp.json()["detail"]


def test_consent_is_allowed_against_a_PREVIOUSLY_stored_phone(client, fresh_headers):
    """The guard tests the phone AFTER this request, not the one in the body —
    she may be ticking the box on a number she gave last week."""
    headers_c = fresh_headers()
    first = client.patch(ENDPOINT, headers=headers_c, json={"phone": "052-1234567"})
    assert first.status_code == 200, first.text

    resp = client.patch(ENDPOINT, headers=headers_c, json={"whatsapp_opt_in": True})
    assert resp.status_code == 200, resp.text
    assert resp.json()["whatsapp_opt_in"] is True


def test_clearing_the_phone_while_consent_stands_is_refused(client, fresh_headers):
    """The refusal is the honest answer: a stored `true` with no number is a
    consent record attached to nothing."""
    headers_c = fresh_headers()
    client.patch(ENDPOINT, headers=headers_c, json={"phone": "052-1234567"})
    client.patch(ENDPOINT, headers=headers_c, json={"whatsapp_opt_in": True})
    resp = client.patch(ENDPOINT, headers=headers_c, json={"phone": ""})
    assert resp.status_code == 422, resp.text
    # …and nothing was written: the number and the consent both stand.
    after = client.patch(ENDPOINT, headers=headers_c, json={})
    assert after.json()["phone"] == "052-1234567"
    assert after.json()["whatsapp_opt_in"] is True


@pytest.mark.parametrize(
    "messy",
    ["052-123-4567", "+972 (52) 123 4567", "  0521234567  ", "052.123.4567 שלוחה 3"],
)
def test_a_messy_phone_is_accepted_and_stored_verbatim(client, fresh_headers, messy):
    """NO format validation (§5). Rejecting a teacher's phone format mid-
    onboarding is hostility disguised as rigour. Only outer whitespace is
    trimmed — that is not a format opinion."""
    headers_d = fresh_headers()
    resp = client.patch(ENDPOINT, headers=headers_d, json={"phone": messy})
    assert resp.status_code == 200, resp.text
    assert resp.json()["phone"] == messy.strip()


# ---------------------------------------------------------------------------
# ONB-2 — "I don't know yet" is an ANSWER
# ---------------------------------------------------------------------------

def test_a_null_date_is_an_answer_and_stamps_answered_at(client, fresh_headers):
    headers_e = fresh_headers()
    resp = client.patch(ENDPOINT, headers=headers_e, json={"next_exam_date": None})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["next_exam_date"] is None
    # The stamp is the ONLY thing separating "answered, unknown" from "never
    # asked" — there is deliberately no second `unknown` flag.
    assert body["next_exam_answered_at"] is not None


def test_answered_at_carries_a_utc_offset(client, fresh_headers):
    """The column is TIMESTAMPTZ and the model says so. A naive value would
    serialize without an offset on the write path and with one on every later
    read, and a browser parses the offset-less form as LOCAL time (the 022
    lesson, 3h off in Israel)."""
    headers_e = fresh_headers()
    resp = client.patch(ENDPOINT, headers=headers_e, json={"next_exam_date": None})
    stamped = resp.json()["next_exam_answered_at"]
    parsed = datetime.fromisoformat(stamped.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None, f"naive timestamp on the wire: {stamped!r}"


# ---------------------------------------------------------------------------
# Idempotency, re-callability, and the absent/null distinction
# ---------------------------------------------------------------------------

def test_re_calling_updates_the_date_and_the_stamp(client, fresh_headers):
    headers_f = fresh_headers()
    first = client.patch(ENDPOINT, headers=headers_f, json={"next_exam_date": _iso(20)})
    assert first.status_code == 200, first.text
    first_stamp = first.json()["next_exam_answered_at"]

    second = client.patch(ENDPOINT, headers=headers_f, json={"next_exam_date": _iso(45)})
    assert second.status_code == 200, second.text
    assert second.json()["next_exam_date"] == _iso(45)
    assert second.json()["next_exam_answered_at"] >= first_stamp


def test_an_ABSENT_date_leaves_the_date_and_the_stamp_alone(client, fresh_headers):
    """THE load-bearing distinction. The app shell's booking link posts
    `guided_session_requested` alone; if "absent" were read as "null" it would
    erase her date AND re-stamp `answered_at`, silently pushing her 14-day
    re-ask out by however long she took to click."""
    headers_g = fresh_headers()
    seeded = client.patch(ENDPOINT, headers=headers_g, json={"next_exam_date": _iso(30)})
    assert seeded.status_code == 200, seeded.text
    stamp = seeded.json()["next_exam_answered_at"]

    later = client.patch(
        ENDPOINT, headers=headers_g, json={"guided_session_requested": True},
    )
    assert later.status_code == 200, later.text
    assert later.json()["next_exam_date"] == _iso(30)
    assert later.json()["next_exam_answered_at"] == stamp


def test_guided_session_is_stamped_on_the_FIRST_occurrence_only(client, fresh_headers):
    """Re-stamping would turn "when she first asked for help" into "when she
    last clicked a link", and the first is the fact worth having."""
    headers_g = fresh_headers()
    first = client.patch(
        ENDPOINT, headers=headers_g, json={"guided_session_requested": True},
    )
    original = first.json()["guided_session_requested_at"]
    assert original is not None

    again = client.patch(
        ENDPOINT, headers=headers_g, json={"guided_session_requested": True},
    )
    assert again.json()["guided_session_requested_at"] == original


def test_an_empty_body_is_a_no_op_and_never_claims_she_answered(client, fresh_headers):
    headers_h = fresh_headers()
    resp = client.patch(ENDPOINT, headers=headers_h, json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["next_exam_date"] is None
    assert body["next_exam_answered_at"] is None
    assert body["whatsapp_opt_in"] is False


# ---------------------------------------------------------------------------
# The /internal Cloud Tasks target
# ---------------------------------------------------------------------------

def test_the_internal_sheet_target_refuses_an_unauthenticated_caller(client, user_a):
    """It takes a user id from its caller — legitimately, because its caller is
    Cloud Tasks. `verify_task_request` is the ONLY thing standing between that
    path and anyone who can guess a UUID."""
    resp = client.post(
        f"/internal/onboarding-sheet/{user_a['user']['id']}/upsert",
        headers={"X-Internal-Token": "wrong-secret"},
    )
    assert resp.status_code == 403, resp.text


def test_the_internal_sheet_target_is_not_in_the_public_schema(client):
    schema = client.get("/openapi.json").json()
    assert not [p for p in schema["paths"] if p.startswith("/internal/onboarding-sheet")]
