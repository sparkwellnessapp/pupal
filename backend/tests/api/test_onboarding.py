"""Onboarding endpoints (migration 022) — schools, profile, completion stamp.

Real DB, real signup, real Bearer tokens (tests/api/conftest.py). The auth
dependency is NEVER faked here: a `dependency_overrides` fake would bypass
exactly the code §9 exists to protect, which is how the users.py auth hole
survived a month.

Each test signs up its OWN user where it mutates profile state, because the
session-scoped user_a is shared with the rest of the API suite and onboarding
writes are destructive (full replacement, a one-way completion stamp).
"""
from uuid import uuid4

from tests.api.auth_helpers import signup_verified

import pytest

from app.services.override_attribution import normalize_school_name


# --- helpers -----------------------------------------------------------------

def _fresh_user(client) -> dict:
    """A usable, signed-in user.

    [024] Delegates to the ONE shared helper: signup no longer returns a
    session, and four copies of "make a user" is what would have made that
    change expensive.
    """
    return signup_verified(client, "onb")


def _headers(user: dict) -> dict:
    return {"Authorization": f"Bearer {user['access_token']}"}


def _uniq(prefix: str) -> str:
    """A school name no other test (or run) shares — the schools table is
    global and its unique index is normalized, so a fixed literal would make
    these tests order-dependent across runs."""
    return f"{prefix} {uuid4().hex[:8]}"


# --- auth (§9) ---------------------------------------------------------------

@pytest.mark.parametrize(
    "method,path,body",
    [
        ("put", "/api/v0/users/me/schools", {"schools": []}),
        ("patch", "/api/v0/users/me/profile", {"full_name": "x"}),
        ("post", "/api/v0/users/me/onboarding/complete", None),
    ],
)
def test_onboarding_routes_require_auth(client, method, path, body):
    resp = getattr(client, method)(path, **({"json": body} if body is not None else {}))
    assert resp.status_code == 401, f"{method.upper()} {path} → {resp.status_code}"


def test_onboarding_routes_reject_a_user_id_parameter(client, headers_a):
    """A caller-supplied user_id must never select the owner (§9). It is ignored,
    never honored — the response describes the TOKEN's user."""
    victim = uuid4()
    resp = client.patch(
        f"/api/v0/users/me/profile?user_id={victim}",
        json={"gender": "unspecified"},
        headers=headers_a,
    )
    assert resp.status_code == 200
    assert resp.json()["id"] != str(victim)


# --- profile -----------------------------------------------------------------

def test_profile_updates_name_and_gender(client):
    user = _fresh_user(client)
    h = _headers(user)

    resp = client.patch(
        "/api/v0/users/me/profile",
        json={"full_name": "  מיכל כהן  ", "gender": "female"},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["full_name"] == "מיכל כהן"       # stripped
    assert body["gender"] == "female"

    # It is the PERSISTED profile, not an echo.
    me = client.get("/api/v0/auth/me", headers=h).json()
    assert me["full_name"] == "מיכל כהן"
    assert me["gender"] == "female"


def test_profile_empty_body_is_a_noop_not_an_error(client):
    user = _fresh_user(client)
    h = _headers(user)
    before = client.get("/api/v0/auth/me", headers=h).json()

    resp = client.patch("/api/v0/users/me/profile", json={}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["full_name"] == before["full_name"]
    assert resp.json()["gender"] is None


def test_profile_rejects_whitespace_only_name(client):
    """full_name is NOT NULL: a name that strips to nothing is a validation
    failure, never an erasure."""
    user = _fresh_user(client)
    h = _headers(user)

    resp = client.patch("/api/v0/users/me/profile", json={"full_name": "   "}, headers=h)
    assert resp.status_code == 422

    assert client.get("/api/v0/auth/me", headers=h).json()["full_name"] == "מורה לבדיקה"


def test_profile_rejects_unknown_gender(client):
    user = _fresh_user(client)
    resp = client.patch(
        "/api/v0/users/me/profile",
        json={"gender": "banana"},
        headers=_headers(user),
    )
    assert resp.status_code == 422


def test_unspecified_gender_is_a_stored_answer_not_a_null(client):
    """'prefer not to say' must be distinguishable from 'never asked'."""
    user = _fresh_user(client)
    h = _headers(user)
    client.patch("/api/v0/users/me/profile", json={"gender": "unspecified"}, headers=h)
    assert client.get("/api/v0/auth/me", headers=h).json()["gender"] == "unspecified"


# --- schools -----------------------------------------------------------------

def test_schools_first_is_the_attribution_key(client):
    """THE D3 GUARD. users.school_id stays PR-G6's single attribution key and
    holds the FIRST school; the junction holds them all. If this test fails,
    override attribution has silently changed meaning."""
    user = _fresh_user(client)
    h = _headers(user)
    first, second = _uniq("עירוני א"), _uniq("בליך")

    resp = client.put(
        "/api/v0/users/me/schools",
        json={"schools": [
            {"name": first, "city": "תל אביב"},
            {"name": second, "city": "רמת גן"},
        ]},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [s["name"] for s in body] == [first, second]

    me = client.get("/api/v0/auth/me", headers=h).json()
    assert [s["name"] for s in me["schools"]] == [first, second]
    assert me["primary_school_id"] == body[0]["id"]


def test_reordering_moves_the_attribution_key(client):
    user = _fresh_user(client)
    h = _headers(user)
    a, b = _uniq("אלון"), _uniq("רבין")

    one = client.put("/api/v0/users/me/schools",
                     json={"schools": [{"name": a}, {"name": b}]}, headers=h).json()
    two = client.put("/api/v0/users/me/schools",
                     json={"schools": [{"name": b}, {"name": a}]}, headers=h).json()

    assert one[0]["id"] == two[1]["id"]
    assert client.get("/api/v0/auth/me", headers=h).json()["primary_school_id"] == two[0]["id"]


def test_schools_is_full_replacement(client):
    """PUT, like its `/me/subject-matters` sibling. No merge semantics."""
    user = _fresh_user(client)
    h = _headers(user)
    a, b, c = _uniq("א"), _uniq("ב"), _uniq("ג")

    client.put("/api/v0/users/me/schools",
               json={"schools": [{"name": a}, {"name": b}, {"name": c}]}, headers=h)
    resp = client.put("/api/v0/users/me/schools", json={"schools": [{"name": b}]}, headers=h)

    assert [s["name"] for s in resp.json()] == [b]
    me = client.get("/api/v0/auth/me", headers=h).json()
    assert [s["name"] for s in me["schools"]] == [b]


def test_empty_list_clears_both_surfaces(client):
    """The schools step is the skippable one; clearing must not leave a stale
    attribution key pointing at a school she removed."""
    user = _fresh_user(client)
    h = _headers(user)
    client.put("/api/v0/users/me/schools",
               json={"schools": [{"name": _uniq("זמני")}]}, headers=h)

    resp = client.put("/api/v0/users/me/schools", json={"schools": []}, headers=h)
    assert resp.status_code == 200
    assert resp.json() == []

    me = client.get("/api/v0/auth/me", headers=h).json()
    assert me["schools"] == []
    assert me["primary_school_id"] is None


def test_same_school_from_two_teachers_is_one_row(client):
    """Normalized-exact create-or-pick: the frontend list ships no real ids, so
    convergence on one row is what makes name-commit safe."""
    name = _uniq("בליך")
    a, b = _fresh_user(client), _fresh_user(client)

    one = client.put("/api/v0/users/me/schools",
                     json={"schools": [{"name": name, "city": "רמת גן"}]},
                     headers=_headers(a)).json()
    two = client.put("/api/v0/users/me/schools",
                     json={"schools": [{"name": f"  {name.upper()}  "}]},
                     headers=_headers(b)).json()

    assert one[0]["id"] == two[0]["id"]
    # The existing row is never rewritten to match the second teacher's spelling.
    assert two[0]["name"] == one[0]["name"]
    assert two[0]["city"] == "רמת גן"


def test_duplicates_within_one_request_collapse_keeping_first_position(client):
    user = _fresh_user(client)
    h = _headers(user)
    dup, other = _uniq("כפול"), _uniq("אחר")

    resp = client.put(
        "/api/v0/users/me/schools",
        json={"schools": [{"name": dup}, {"name": other}, {"name": f"  {dup}  "}]},
        headers=h,
    )
    assert resp.status_code == 200
    assert [s["name"] for s in resp.json()] == [dup, other]


def test_whitespace_only_school_name_is_rejected(client):
    user = _fresh_user(client)
    resp = client.put(
        "/api/v0/users/me/schools",
        json={"schools": [{"name": "   "}]},
        headers=_headers(user),
    )
    assert resp.status_code == 422


def test_patch_me_school_keeps_the_junction_in_agreement(client):
    """The PR-G6 single-school endpoint predates the junction. It must not leave
    the two surfaces disagreeing — the condition 022's backfill exists to
    prevent."""
    user = _fresh_user(client)
    h = _headers(user)
    name = _uniq("ישן")

    resp = client.patch("/api/v0/users/me/school", json={"school_name": name}, headers=h)
    assert resp.status_code == 200, resp.text

    me = client.get("/api/v0/auth/me", headers=h).json()
    assert [s["name"] for s in me["schools"]] == [name]
    assert me["primary_school_id"] == resp.json()["school_id"]


def test_school_resolution_matches_the_normalization_rule(client):
    """The app's key and the DB's unique index must agree. Pinning the Python
    half here keeps a future edit to one from silently diverging."""
    assert normalize_school_name("  Blich   High School ") == "blich high school"
    assert normalize_school_name("BLICH HIGH SCHOOL") == "blich high school"
    assert normalize_school_name("Blich  High  School") == normalize_school_name("Blich High School")


# --- completion --------------------------------------------------------------

def test_complete_is_idempotent(client):
    user = _fresh_user(client)
    h = _headers(user)

    assert client.get("/api/v0/auth/me", headers=h).json()["onboarding_completed_at"] is None

    first = client.post("/api/v0/users/me/onboarding/complete", headers=h)
    assert first.status_code == 200
    stamp = first.json()["onboarding_completed_at"]
    assert stamp is not None

    second = client.post("/api/v0/users/me/onboarding/complete", headers=h)
    assert second.status_code == 200
    assert second.json()["onboarding_completed_at"] == stamp     # never re-stamped


def test_signup_starts_un_onboarded_and_answers_the_new_shape(client):
    """Signup builds its response from a freshly created User; the new
    collection must be loaded there or it is a MissingGreenlet 500."""
    user = _fresh_user(client)
    profile = user["user"]
    assert profile["onboarding_completed_at"] is None
    assert profile["schools"] == []
    assert profile["gender"] is None
    assert profile["primary_school_id"] is None


def test_login_answers_the_new_shape(client):
    """The login path uses a DIFFERENT loader than get_current_user; both must
    eager-load schools."""
    email = f"onb_login_{uuid4().hex[:10]}@s2test.com"
    # [024] Must be VERIFIED, not merely signed up: an unverified account has no
    # password session to test with, which is the point of A4.
    signup_verified(client, email=email, full_name="מורה")
    resp = client.post("/api/v0/auth/login", json={"email": email, "password": "testpass123"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["schools"] == []
    assert resp.json()["user"]["onboarding_completed_at"] is None


# --- ministry symbol: exact institution identity (023) -----------------------
#
# The rule under test, in one line: WHEN A SYMBOL IS PRESENT IT IS THE IDENTITY,
# and it never falls back to (nor adopts) a name match. The motivating fact from
# the real Ministry export: 82 normalized names are shared by 213 institutions,
# two of them — 320440 and 338384 — in the SAME city.

def _sym() -> str:
    """A symbol no other test or run shares (the schools table is global)."""
    return str(uuid4().int % 900000 + 100000)


def test_same_symbol_from_two_teachers_is_one_row(client):
    """The convergence guarantee, now on the symbol rather than the spelling."""
    symbol = _sym()
    a, b = _fresh_user(client), _fresh_user(client)

    one = client.put("/api/v0/users/me/schools", headers=_headers(a), json={
        "schools": [{"name": _uniq("תיכון"), "city": "חיפה", "ministry_symbol": symbol}],
    }).json()
    # DIFFERENT spelling, DIFFERENT city, same institution.
    two = client.put("/api/v0/users/me/schools", headers=_headers(b), json={
        "schools": [{"name": _uniq("אחר לגמרי"), "city": "תל אביב", "ministry_symbol": symbol}],
    }).json()

    assert one[0]["id"] == two[0]["id"], "same symbol must be the same row"
    assert two[0]["ministry_symbol"] == symbol
    # The first spelling stands: an existing row is never rewritten to match a
    # later caller's text.
    assert two[0]["name"] == one[0]["name"]


def test_two_schools_sharing_a_name_stay_two_schools(client):
    """THE case name identity cannot express — and 018's whole-table index
    actively forbade, which is why 023 had to narrow it."""
    shared = _uniq("בית אקשטיין")
    sym_a, sym_b = _sym(), _sym()
    user = _fresh_user(client)

    resp = client.put("/api/v0/users/me/schools", headers=_headers(user), json={
        "schools": [
            {"name": shared, "city": "פרדס חנה-כרכור", "ministry_symbol": sym_a},
            {"name": shared, "city": "פרדס חנה-כרכור", "ministry_symbol": sym_b},
        ],
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 2, "same name + same city + different symbols = two institutions"
    assert body[0]["id"] != body[1]["id"]
    assert {s["ministry_symbol"] for s in body} == {sym_a, sym_b}


def test_a_symbol_never_adopts_a_name_match(client):
    """A symbol-bearing pick must NOT absorb an existing symbol-less row that
    happens to share its name: a name match is not evidence of identity, and
    adopting on it would invent exactly what the symbol exists to establish."""
    name = _uniq("בית ספר עמום")
    typed_by_hand = client.put(
        "/api/v0/users/me/schools", headers=_headers(_fresh_user(client)),
        json={"schools": [{"name": name}]},                    # no symbol
    ).json()
    assert typed_by_hand[0]["ministry_symbol"] is None

    picked = client.put(
        "/api/v0/users/me/schools", headers=_headers(_fresh_user(client)),
        json={"schools": [{"name": name, "ministry_symbol": _sym()}]},
    ).json()

    assert picked[0]["id"] != typed_by_hand[0]["id"], "must not merge on a name match"


def test_free_text_still_converges_on_the_name(client):
    """The pre-023 rule survives for the rows it can still honestly govern."""
    name = _uniq("בית ספר שאין ברשימה")
    one = client.put("/api/v0/users/me/schools", headers=_headers(_fresh_user(client)),
                     json={"schools": [{"name": name}]}).json()
    two = client.put("/api/v0/users/me/schools", headers=_headers(_fresh_user(client)),
                     json={"schools": [{"name": f"  {name.upper()}  "}]}).json()

    assert one[0]["id"] == two[0]["id"]
    assert two[0]["ministry_symbol"] is None


def test_symbol_round_trips_through_the_profile(client):
    """Without this the client cannot re-submit an unchanged list: every picked
    school would silently demote to free text on the next save."""
    symbol = _sym()
    user = _fresh_user(client)
    h = _headers(user)
    client.put("/api/v0/users/me/schools", headers=h, json={
        "schools": [{"name": _uniq("תיכון"), "city": "חיפה", "ministry_symbol": symbol}],
    })

    me = client.get("/api/v0/auth/me", headers=h).json()
    assert me["schools"][0]["ministry_symbol"] == symbol


def test_junk_symbol_is_refused(client):
    """This value becomes an IDENTITY; it is not a free-text field."""
    user = _fresh_user(client)
    # «١٢٣٤٥٦» is Arabic-Indic 123456: it LOOKS like a symbol to a human and
    # slipped through the first `\d` pattern, which is Unicode-aware. A symbol
    # that renders identically to another but is a different string is the
    # confusable identity this column exists to remove.
    for junk in ["abc", "12", "12345678901234", "540151; DROP", "", "١٢٣٤٥٦"]:
        resp = client.put("/api/v0/users/me/schools", headers=_headers(user), json={
            "schools": [{"name": "בית ספר", "ministry_symbol": junk}],
        })
        assert resp.status_code == 422, f"accepted junk symbol {junk!r}"


def test_symbol_and_free_text_schools_coexist_on_one_teacher(client):
    """A real list: some picked, some typed. Order (the PR-G6 key) is unaffected."""
    user = _fresh_user(client)
    h = _headers(user)
    picked, typed = _uniq("נבחר"), _uniq("הוקלד")
    symbol = _sym()

    body = client.put("/api/v0/users/me/schools", headers=h, json={
        "schools": [
            {"name": picked, "city": "חיפה", "ministry_symbol": symbol},
            {"name": typed},
        ],
    }).json()

    assert [s["name"] for s in body] == [picked, typed]
    assert body[0]["ministry_symbol"] == symbol
    assert body[1]["ministry_symbol"] is None
    me = client.get("/api/v0/auth/me", headers=h).json()
    assert me["primary_school_id"] == body[0]["id"]
