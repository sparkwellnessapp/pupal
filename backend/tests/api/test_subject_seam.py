"""The subject seam at the API boundary (multisubject beta, Phase 1; D-10).

Three rules, each pinned:
  * extraction-job submit REQUIRES `subject` and refuses an unknown key (422) —
    the teacher picks it, the server never defaults it, the model never chooses it;
  * a saved rubric's subject is IMMUTABLE — an update whose draft names another
    subject is a 409, never a silent overwrite;
  * a draft with an unknown subject cannot be saved (400 validation error).

Real auth, real DB (the Vivi-Test database) — the harness signs up real users.
"""
from __future__ import annotations

import copy

from tests.api.conftest import MINIMAL_DRAFT

JOBS_URL = "/api/v0/rubrics/extraction-jobs"
DOCX_MAGIC = b"PK\x03\x04" + b"\x00" * 60


def test_submit_without_subject_is_422(client, headers_a):
    resp = client.post(
        f"{JOBS_URL}/", headers=headers_a,
        files={"file": ("rubric.docx", DOCX_MAGIC,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={},
    )
    assert resp.status_code == 422, resp.text


def test_submit_with_unknown_subject_is_422_before_any_upload(client, headers_a):
    resp = client.post(
        f"{JOBS_URL}/", headers=headers_a,
        files={"file": ("rubric.docx", DOCX_MAGIC,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"subject": "physics"},
    )
    assert resp.status_code == 422, resp.text
    assert "physics" in resp.text and "computer_science" in resp.text


def test_update_with_a_different_subject_is_409(client, headers_a, rubric_a):
    rubric_id = rubric_a["rubric_id"]
    draft = copy.deepcopy(MINIMAL_DRAFT)
    draft["subject"] = "english"
    resp = client.put(
        f"/api/v0/rubrics/{rubric_id}/draft", headers=headers_a,
        json={"draft": draft, "acknowledged_warning_ids": ["narrowness_issue:q1.c0"]},
    )
    assert resp.status_code == 409, resp.text
    body = resp.json()["detail"]
    assert body["error_type"] == "subject_conflict"
    assert body["message_he"]


def test_update_with_the_same_subject_still_saves(client, headers_a, rubric_a):
    rubric_id = rubric_a["rubric_id"]
    draft = copy.deepcopy(MINIMAL_DRAFT)
    draft["subject"] = "computer_science"  # explicit == the row's key
    resp = client.put(
        f"/api/v0/rubrics/{rubric_id}/draft", headers=headers_a,
        json={"draft": draft, "acknowledged_warning_ids": ["narrowness_issue:q1.c0"]},
    )
    assert resp.status_code == 200, resp.text


def test_save_with_unknown_subject_is_a_validation_error(client, headers_a):
    draft = copy.deepcopy(MINIMAL_DRAFT)
    draft["subject"] = "physics"
    resp = client.post(
        "/api/v0/rubrics/save_ontology_draft", headers=headers_a,
        json={"name": "physics attempt", "draft": draft,
              "acknowledged_warning_ids": ["narrowness_issue:q1.c0"]},
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"]["error_type"] == "validation_failed"


def test_saved_rubric_carries_its_subject_column_and_contract_agree(client, headers_a):
    """The column (migration 027) and the contract JSON name the same subject."""
    draft = copy.deepcopy(MINIMAL_DRAFT)
    draft["subject"] = "english"
    resp = client.post(
        "/api/v0/rubrics/save_ontology_draft", headers=headers_a,
        json={"name": "english rubric", "draft": draft,
              "acknowledged_warning_ids": ["narrowness_issue:q1.c0"]},
    )
    assert resp.status_code == 201, resp.text
    rubric_id = resp.json()["rubric_id"]
    detail = client.get(f"/api/v0/rubrics/{rubric_id}?include_contract=true&include_draft=true",
                        headers=headers_a)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    # the draft and the contract both carry the key the column was written from
    assert (body.get("draft_json") or {}).get("subject") == "english", body.keys()
    assert (body.get("contract_json") or {}).get("subject") == "english", body.keys()
