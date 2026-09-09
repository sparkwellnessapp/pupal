"""The onboarding school path, driven with the REAL Ministry export.

`test_onboarding.py` pins the RULES with synthetic rows it fully controls. This
file asks a different question: does the rule survive the actual 2,194-row
dataset a teacher will pick from — its quote marks, its hyphens, and the 15
groups of schools that share a name WITHIN one city?

The export is read in place from the frontend data module (see
`israeli_schools_fixture`), so this cannot drift into testing a stale copy.

Sampling is DETERMINISTIC (a fixed stride, plus the named collision rows), not
random: a test that picks different rows every run reports a different fact every
run, and a failure nobody can reproduce is not a signal.
"""
from uuid import uuid4

from tests.api.auth_helpers import signup_verified

import pytest
from pydantic import ValidationError

from app.api.v0.users import SchoolInput
from app.services.override_attribution import normalize_school_name
from tests.api.israeli_schools_fixture import load_schools


def _fresh_user(client) -> dict:
    """A usable, signed-in user.

    [024] Delegates to the ONE shared helper: signup no longer returns a
    session, and four copies of "make a user" is what would have made that
    change expensive.
    """
    return signup_verified(client, "onbds")


def _headers(user: dict) -> dict:
    return {"Authorization": f"Bearer {user['access_token']}"}


def _pick(row) -> dict:
    """Exactly what the browser sends for a list pick."""
    return {"name": row.name, "city": row.city, "ministry_symbol": row.symbol}


# --- the dataset itself ------------------------------------------------------

def test_fixture_parses_the_whole_export():
    """Guards the parser, not the product: if the generator's shape changes and
    this drops to a subset, every test below would still 'pass' while covering
    a fraction of the data."""
    rows = load_schools()
    assert len(rows) == 2194, f"expected the full export, parsed {len(rows)}"
    assert len({r.symbol for r in rows}) == len(rows), "symbols must be unique"


def test_every_real_symbol_survives_the_endpoint_validation():
    """Every school that actually exists must be submittable. A single rejected
    row here is a teacher who cannot finish onboarding.

    Validated through the REAL request model rather than against a copy of its
    regex: a copied rule is a mirror, and a mirror that drifts reports the old
    rule while the endpoint enforces a new one (the AnnotationSchema lesson)."""
    bad = []
    for r in load_schools():
        try:
            SchoolInput(name=r.name, city=r.city, ministry_symbol=r.symbol)
        except ValidationError:
            bad.append(r)
    assert bad == [], f"{len(bad)} real schools would be refused, e.g. {bad[:3]}"


def test_the_validation_still_refuses_junk():
    """The other half: the rule above is only meaningful if it rejects
    something. Guards against a future widening that accepts anything."""
    for junk in ["abc", "12", "540151; DROP", "١٢٣٤٥٦"]:
        with pytest.raises(ValidationError):
            SchoolInput(name="בית ספר", ministry_symbol=junk)


def test_the_export_really_does_collide_on_names():
    """The premise of migration 023, asserted against the data rather than
    remembered from a note. If this ever stops being true, the symbol column is
    still correct but its justification changed and should be re-read."""
    rows = load_schools()
    groups: dict[str, list] = {}
    for r in rows:
        groups.setdefault(normalize_school_name(r.name), []).append(r)
    collisions = {k: v for k, v in groups.items() if len(v) > 1}
    assert collisions, "no name collisions — 023's premise would be void"

    same_city = [
        v for v in collisions.values()
        if len({r.city for r in v}) < len(v)
    ]
    assert same_city, "no same-name-same-city pair — the strongest case for 023"


# --- the real rows, through the real endpoint --------------------------------

def test_same_named_schools_in_one_town_stay_distinct(client):
    """The case that name identity — even name+city — cannot express, driven
    with the actual rows. The export has 15 such groups (13 pairs and 2 triples);
    this drives the largest, three «ישיבת חזון נחום» in בני ברק. The group is
    FOUND, not hardcoded, so a refreshed export re-derives it."""
    rows = load_schools()
    groups: dict[str, list] = {}
    for r in rows:
        groups.setdefault((normalize_school_name(r.name), r.city), []).append(r)
    clash = max(groups.values(), key=len)
    assert len(clash) > 1, "expected at least one same-name-same-city group"

    user = _fresh_user(client)
    resp = client.put("/api/v0/users/me/schools", headers=_headers(user),
                      json={"schools": [_pick(r) for r in clash]})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert len(body) == len(clash), "the town's same-named schools collapsed"
    assert len({s["id"] for s in body}) == len(clash)
    assert {s["ministry_symbol"] for s in body} == {r.symbol for r in clash}


@pytest.mark.parametrize("offset", [0, 977])
def test_a_real_sample_round_trips(client, offset):
    """A deterministic slice of the real export, committed and read back."""
    rows = load_schools()
    sample = [rows[(offset + i * 173) % len(rows)] for i in range(8)]

    user = _fresh_user(client)
    h = _headers(user)
    resp = client.put("/api/v0/users/me/schools", headers=h,
                      json={"schools": [_pick(r) for r in sample]})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Order is the PR-G6 key and must survive verbatim.
    assert [s["ministry_symbol"] for s in body] == [r.symbol for r in sample]
    # Names go in as written — quote marks and all (407 rows carry one).
    assert [s["name"] for s in body] == [r.name for r in sample]

    me = client.get("/api/v0/auth/me", headers=h).json()
    assert [s["ministry_symbol"] for s in me["schools"]] == [r.symbol for r in sample]
    assert me["primary_school_id"] == body[0]["id"]


def test_resubmitting_the_same_real_list_is_stable(client):
    """Re-saving an unchanged list must not create a second generation of rows —
    the round-trip of `ministry_symbol` through the profile is what prevents it."""
    rows = load_schools()
    sample = [rows[i * 401 % len(rows)] for i in range(5)]

    user = _fresh_user(client)
    h = _headers(user)
    first = client.put("/api/v0/users/me/schools", headers=h,
                       json={"schools": [_pick(r) for r in sample]}).json()

    # Re-submit from what the PROFILE returned, exactly as the client does.
    me = client.get("/api/v0/auth/me", headers=h).json()
    again = client.put("/api/v0/users/me/schools", headers=h, json={"schools": [
        {"name": s["name"], "city": s["city"], "ministry_symbol": s["ministry_symbol"]}
        for s in me["schools"]
    ]}).json()

    assert [s["id"] for s in again] == [s["id"] for s in first], "rows churned"


def test_two_teachers_picking_the_same_real_school_meet_on_one_row(client):
    """The convergence property, on a real institution with a quoted name."""
    quoted = next(r for r in load_schools() if '"' in r.name)

    a, b = _fresh_user(client), _fresh_user(client)
    one = client.put("/api/v0/users/me/schools", headers=_headers(a),
                     json={"schools": [_pick(quoted)]}).json()
    two = client.put("/api/v0/users/me/schools", headers=_headers(b),
                     json={"schools": [_pick(quoted)]}).json()

    assert one[0]["id"] == two[0]["id"]
    assert one[0]["ministry_symbol"] == quoted.symbol
    assert one[0]["name"] == quoted.name          # stored verbatim, quote included
