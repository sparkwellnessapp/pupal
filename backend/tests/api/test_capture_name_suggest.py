"""
The teacher page's name suggestion through its endpoint (§6.9, SCN-10/12).
"""
from __future__ import annotations

import io
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PIL import Image

from tests.api.test_capture_api import (                       # noqa: F401  (fixtures)
    S, _create, _link, _page, _students, _uniq, env,
)

pytestmark = pytest.mark.integration


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1131, 1600), "white").save(buf, "JPEG")
    return buf.getvalue()


class _Provider:
    def __init__(self, text):
        self.text = text

    async def complete(self, **kw):
        return SimpleNamespace(text=self.text)


@pytest.fixture
def render(env):
    async def fake_render(*a, **kw):
        return None
    env["scan"].render = fake_render
    gcs = SimpleNamespace(download_bytes=lambda path: _jpeg())
    with patch("app.services.gcs_service.get_gcs_service", return_value=gcs):
        yield


def _suggest(client, headers, env, answer):
    base = f"/api/v0/capture/teacher/{env['batch']}"
    sub = client.post(f"{base}/submissions", headers=headers).json()["submission_id"]
    _page(client, base, sub, headers, env)
    with patch("app.services.capture.name_suggest._provider",
               return_value=(_Provider(answer), None, "")):
        return client.post(f"{base}/submissions/{sub}/name-suggest", headers=headers)


def test_a_roster_match_comes_back_as_her_student(client, headers_a, env, render):
    _link(client, headers_a, env)
    name = _uniq("הדר")
    (sid,) = _students(env, name)
    r = _suggest(client, headers_a, env,
                 f'{{"read_name": "{name}", "roster_match_id": "s1", "confidence": "high"}}')
    assert r.status_code == 200, r.text
    assert r.json() == {"read_name": name, "confidence": "high",
                        "match": {"student_id": str(sid), "display_name": name}}


def test_an_id_outside_the_roster_is_discarded_scn12(client, headers_a, env, render):
    _link(client, headers_a, env)
    _students(env, _uniq("עמית"))
    r = _suggest(client, headers_a, env,
                 '{"read_name": "x", "roster_match_id": "s99", "confidence": "high"}')
    assert r.json()["match"] is None and r.json()["read_name"] == "x"


def test_a_provider_failure_is_a_200_with_nothing(client, headers_a, env, render):
    _link(client, headers_a, env)
    base = f"/api/v0/capture/teacher/{env['batch']}"
    sub = client.post(f"{base}/submissions", headers=headers_a).json()["submission_id"]
    _page(client, base, sub, headers_a, env)
    with patch("app.services.capture.name_suggest._provider", side_effect=RuntimeError("down")):
        r = client.post(f"{base}/submissions/{sub}/name-suggest", headers=headers_a)
    assert r.status_code == 200
    assert r.json() == {"read_name": None, "match": None, "confidence": "low"}


def test_it_never_runs_on_a_student_link_submission_scn10(client, headers_a, env, render):
    """A student-link submission cannot even be addressed through the
    teacher's path for a name — and is refused if it is."""
    token = _link(client, headers_a, env)
    sub, dev = _create(client, token, "שם", confirm=False)
    _page(client, f"{S}/{token}", sub, dev, env)
    r = client.post(f"/api/v0/capture/teacher/{env['batch']}/submissions/{sub}/name-suggest",
                    headers=headers_a)
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "not_teacher_source")
    assert client.post(f"{S}/{token}/submissions/{sub}/name-suggest", headers=dev).status_code in (404, 405)


def test_it_waits_for_page_one_to_be_analyzed(client, headers_a, env, render):
    _link(client, headers_a, env)
    base = f"/api/v0/capture/teacher/{env['batch']}"
    sub = client.post(f"{base}/submissions", headers=headers_a).json()["submission_id"]
    _page(client, base, sub, headers_a, env, upload=False)
    r = client.post(f"{base}/submissions/{sub}/name-suggest", headers=headers_a)
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "page1_not_analyzed")
