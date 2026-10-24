"""The marketing-demo bundle's data half stays exact as the product moves.

`scripts/build_marketing_demo_bundle.py` publishes two real exams to the public
website, with grades that must equal the teacher-validated GT. The full build
(scans, PDFs, images) runs ~100 s and needs git-ignored scans, so it is checked
by `--check` by hand. What CAN silently break in CI is the data half — a schema
change, a pricer change, an approval-gate change — and that is what this pins,
with no scans and no images. Zero mocks: the real pricer and the real gate.
"""
from __future__ import annotations

import importlib.util
from decimal import Decimal
from pathlib import Path

import pytest

from app.schemas.graded_test_draft import GradedTestOverrides, TeacherOverride
from app.schemas.ontology_types import GradingRubricContract

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "build_marketing_demo_bundle", ROOT / "scripts" / "build_marketing_demo_bundle.py")
bundle = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bundle)

PSEUDO = bundle.load(bundle.CONFIG / "pseudonyms.json")
RUBRIC = GradingRubricContract.model_validate(bundle.load(bundle.RUBRIC))
TOTALS = {"dan_basiuk": Decimal("84"), "yonatan_basiuk": Decimal("92.5")}


def _gt(slug):
    return {t["terminal_id"]: Decimal(t["awarded"])
            for t in bundle.load(bundle.GT_DIR / f"{slug}.gt.json")["terminals"]}


@pytest.mark.parametrize("slug", bundle.STUDENTS)
def test_every_terminal_prices_to_the_teacher_gt(slug):
    raw, priced = bundle.perfect_draft(slug, PSEUDO["students"][slug], [])
    assert priced == _gt(slug)
    assert sum(priced.values()) == TOTALS[slug]


@pytest.mark.parametrize("slug", bundle.STUDENTS)
def test_the_real_gate_approves_it_at_the_gt_total(slug):
    ids = PSEUDO["students"][slug]
    raw, _ = bundle.perfect_draft(slug, ids, [])
    payload, contract = bundle.approved_payload(
        raw, GradedTestOverrides(), RUBRIC, ids, ids["contract_version"], PSEUDO["approved_at"])
    assert contract.total_score == TOTALS[slug]
    assert payload["student_name"] == ids["display_name"]


def test_the_scripted_override_lands_on_845():
    ids = PSEUDO["students"]["dan_basiuk"]
    raw, _ = bundle.perfect_draft("dan_basiuk", ids, [])
    overrides = GradedTestOverrides(terminals={"q1.א.c1": [
        TeacherOverride(check_id="q1.א.c1.k4", verdict="met")]})
    _, contract = bundle.approved_payload(
        raw, overrides, RUBRIC, ids, ids["variant_contract_version"], PSEUDO["approved_at"])
    assert contract.total_score == Decimal("84.5")


@pytest.mark.parametrize("slug", bundle.STUDENTS)
def test_no_plan_code_and_no_real_name_reaches_the_page(slug):
    ids = PSEUDO["students"][slug]
    raw, _ = bundle.perfect_draft(slug, ids, [])
    for text in bundle._visible(raw):
        assert not bundle.PLAN_CODE.search(text), text[:80]
    draft = bundle.transcription_draft(slug, ids["display_name"], 6)
    for text in list(bundle._strings(raw)) + list(bundle._strings(draft)):
        for rule in bundle.FORBIDDEN:
            assert not rule.search(text), (rule.pattern, text[:80])


@pytest.mark.parametrize("slug", bundle.STUDENTS)
def test_the_transcription_is_the_gt_byte_for_byte(slug):
    draft = bundle.transcription_draft(slug, "x", 6)
    gt = bundle.load(bundle.TRANSCRIPTIONS / f"{slug}.contract.json")["answers"]
    assert [a["answer_text"] for a in draft["answers"]] == [a["answer_text"] for a in gt]
    assert all(a["page_numbers"] for a in draft["answers"])


def test_the_rubric_document_copy_is_redacted_as_ruled():
    """Owner ruling 2026-10-23: logo gone, «ויויאנה» kept, «נעמה» blanked, no
    comments. The shipped pages are images nobody can grep, so this pins the
    redacted copy Word renders them from. No Word needed: it never renders."""
    import io
    import re
    import zipfile
    from PIL import Image

    cfg = bundle.load(bundle.CONFIG / "redactions.json")["rubric_docx"]
    _, redacted = bundle.redacted_rubric_docx(cfg)
    zf = zipfile.ZipFile(io.BytesIO(redacted))
    parts = {n: zf.read(n) for n in zf.namelist()}

    text = " ".join(bundle._visible_docx_text(parts))
    assert "ויויאנה" in text
    for rule in bundle.FORBIDDEN:
        assert not rule.search(text), rule.pattern
    assert not [n for n in parts if re.fullmatch(r"word/(comments\w*|people)\.xml", n)]
    assert "commentReference" not in parts["word/document.xml"].decode("utf-8")

    for rels in [n for n in parts if re.fullmatch(r"word/_rels/header\d+\.xml\.rels", n)]:
        for target in re.findall(r'Target="(media/[^"]+)"', parts[rels].decode("utf-8")):
            with Image.open(io.BytesIO(parts[f"word/{target}"])) as im:
                assert all(lo == hi == 255 for lo, hi in im.convert("RGB").getextrema()), target
