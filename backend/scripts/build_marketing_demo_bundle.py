"""Build the marketing-demo data bundle (the website's «נסו בעצמך» demo).

    python scripts/build_marketing_demo_bundle.py --out <website>/public/demo/v1 [--check]
                                                  [--review-dir <dir>]

WHAT IT IS. Two real `hobby_tvshow` exams, made safe and made exact, for a
fully simulated walkthrough on the public website: no API, no spend, no
backend. Brief: `docs/marketing-demo/BUNDLE_BUILDER_BRIEF.md`.

WHY IT LIVES HERE AND NOT IN THE WEBSITE. Only this repo can PROVE the data:
the grades are re-priced by `services/pricing.py`, approved by the real gate
(`compile_graded_test`) and drawn by the real renderer (`returned_exam.py`).
The website never computes a grade; it displays what this script verified.

THREE RULES IT REFUSES TO BREAK
  * Faithful: the transcription is the teacher-checked ground truth byte for
    byte, student errors included. Grades come from VERDICTS re-priced by the
    one pricer, never from a typed number, and must equal the teacher-validated
    GT on every terminal or the build fails.
  * Private (owner ruling 2026-10-23): pseudonyms only. Pages are rebuilt from
    the scan raster alone (dropping the CamScanner footer image and every byte
    of metadata) with the school logo, the name line and a personal note
    painted out. A privacy grep over every output byte gates the build.
  * Nothing generated is written into this repo: `--out` points at the
    website, and the bundle never enters the public remotes.
"""
from __future__ import annotations

import argparse
import copy
import filecmp
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Tuple

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageStat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.agents.feedback.staleness import basis_hash, flatten_checks  # noqa: E402
from app.agents.grader.validator import quote_match_status  # noqa: E402
from app.schemas.graded_test_draft import (  # noqa: E402
    GradedTestDraft, GradedTestOverrides, TeacherOverride)
from app.schemas.ontology_types import GradingRubricContract  # noqa: E402
from app.services import returned_exam as rx  # noqa: E402
from app.services.graded_test_contract_compiler import (  # noqa: E402
    _build_terminal_index, compile_graded_test)
from app.services.pricing import price_scope_checks_detailed  # noqa: E402

CONFIG = ROOT / "scripts" / "marketing_demo"
TESTS = ROOT / "tests"
RUBRIC = TESTS / "grading_eval_suite/benchmarks/contracts/hobby_tvshow_corrected.contract.json"
GT_DIR = TESTS / "grading_eval_suite/benchmarks/gt"
TRANSCRIPTIONS = TESTS / "grading_eval_suite/benchmarks/transcriptions"
PAGE_GT = TESTS / "transcription_eval_suit/raw_benchmarks"
SCANS = TESTS / "transcription_eval_suit/pdfs"
DRAFTS = TESTS / "fixtures/grade_review"

STUDENTS = ("dan_basiuk", "yonatan_basiuk")
BUNDLE_VERSION = "v1"
# The product default (`grading_batches.appendix_include_criteria` is False).
INCLUDE_CRITERIA = False

SCAN_LONG_EDGE, THUMB_LONG_EDGE, SIGNED_LONG_EDGE, PDF_LONG_EDGE = 1600, 320, 1600, 1800
WEBP_QUALITY = 80
BUDGET = {"scan": 350_000, "thumb": 40_000, "signed": 400_000, "bundle": 14_000_000}

# A teacher never sees a plan (W-3): no rule code, no English verdict name.
PLAN_CODE = re.compile(r"\[(PL|A|R|AUDIT)-[^\]]*\]|R-α|R-β|\bPL-\d|AUDIT-\d"
                       r"|\bpartially_met\b|\bnot_met\b|\bmet\b|\btariff\b")
HEB = "֐-׿"
FORBIDDEN = [re.compile(p, re.IGNORECASE) for p in (
    r"basiuk", "בסיוק", "מוסינזון", r"mosinzon", r"camscanner", r"intsig",
    rf"(?<![{HEB}])דן(?![{HEB}])", rf"(?<![{HEB}])יונתן(?![{HEB}])")]

_MARK = {"met": "✓", "partially_met": "◐", "not_met": "✗"}


class BuildError(SystemExit):
    def __init__(self, message: str):
        super().__init__(f"REFUSED: {message}")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
                    encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# 1. scans: rebuilt from the raster alone, then painted
# ---------------------------------------------------------------------------

def _paper_color(im: Image.Image) -> Tuple[int, int, int]:
    small = im.resize((96, 96))
    mask = small.convert("L").point(lambda v: 255 if v > 175 else 0)
    stat = ImageStat.Stat(small, mask=mask)
    return tuple(int(round(c)) for c in stat.mean[:3]) if stat.count[0] else (245, 245, 240)


def redacted_scan(slug: str, rects: Dict[str, list]) -> Tuple[bytes, List[Image.Image], List[Image.Image]]:
    """(redacted PDF bytes, redacted page rasters, untouched page rasters for review)."""
    src = fitz.open(SCANS / f"hobby_tvshow.{slug}.pdf")
    out = fitz.open()
    pages, originals = [], []
    for number, page in enumerate(src, start=1):
        images = page.get_images(full=True)
        xref = max(images, key=lambda x: x[2] * x[3])[0]          # the scan, not the footer
        placement = page.get_image_rects(xref)[0]
        pix = fitz.Pixmap(src, xref)
        if pix.alpha or pix.n - pix.alpha != 3:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        im = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        originals.append(im.copy())
        paper = _paper_color(im)
        draw = ImageDraw.Draw(im)
        w, h = im.size
        for x0, y0, x1, y1 in rects.get(str(number), []):
            draw.rectangle([x0 * w, y0 * h, x1 * w, y1 * h], fill=paper)
        pages.append(im)

        # The PDF carries the page at print-legible resolution, not the phone's
        # full 3,000 px: a returned exam is read and printed, never zoomed 4x.
        embed = im
        if max(im.size) > PDF_LONG_EDGE:
            k = PDF_LONG_EDGE / max(im.size)
            embed = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
        jpeg = io.BytesIO()
        embed.save(jpeg, "JPEG", quality=75, optimize=True)
        new = out.new_page(width=page.rect.width, height=page.rect.height)
        new.insert_image(placement, stream=jpeg.getvalue())
    return _clean_pdf(out), pages, originals


def _clean_pdf(doc: fitz.Document) -> bytes:
    """No metadata, no XMP, no trailer /ID: byte-stable and anonymous."""
    doc.set_metadata({})
    doc.del_xml_metadata()
    buf = io.BytesIO()
    doc.save(buf, garbage=4, deflate=True, no_new_id=True)
    doc.close()
    reopened = fitz.open(stream=buf.getvalue(), filetype="pdf")
    if reopened.xref_get_key(-1, "ID")[0] != "null":
        reopened.xref_set_key(-1, "ID", "null")
    buf = io.BytesIO()
    reopened.save(buf, garbage=4, deflate=True, no_new_id=True)
    return buf.getvalue()


def _webp(im: Image.Image, long_edge: int) -> bytes:
    w, h = im.size
    scale = long_edge / max(w, h)
    if scale < 1:
        im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=WEBP_QUALITY, method=6)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 2. transcription draft: the GT, byte for byte
# ---------------------------------------------------------------------------

def _page_sections(slug: str) -> Dict[int, set]:
    text = (PAGE_GT / f"hobby_tvshow.{slug}.md").read_text(encoding="utf-8")
    sections: Dict[int, set] = {}
    for match in re.finditer(r"=== PAGE (\d+) ===\n(.*?)(?=\n=== PAGE |\Z)", text, re.S):
        sections[int(match.group(1))] = {" ".join(l.split()) for l in match.group(2).splitlines()
                                         if l.strip()}
    return sections


def transcription_draft(slug: str, display_name: str, page_count: int) -> dict:
    answers = load(TRANSCRIPTIONS / f"{slug}.contract.json")["answers"]
    sections = _page_sections(slug)
    out = []
    for a in answers:
        if "תודה" in a["answer_text"]:
            raise BuildError(f"{slug}: a personal note reached a graded answer")
        lines = [" ".join(l.split()) for l in a["answer_text"].splitlines() if len(l.strip()) >= 4]
        hits = {p: sum(1 for l in lines if l in s) for p, s in sections.items()}
        need = 1 if len(lines) < 3 else 2
        pages = sorted(p for p, n in hits.items() if n >= need)
        if not pages:
            raise BuildError(f"{slug} q{a['question_number']}.{a['sub_question_id']}: "
                             f"cannot locate the answer on any page")
        out.append({"question_number": a["question_number"],
                    "sub_question_id": a.get("sub_question_id"),
                    "answer_text": a["answer_text"],
                    "confidence": 1.0,
                    "page_numbers": pages})
    return {"schema_version": "1.0", "student_name_suggestion": display_name,
            "page_count": page_count, "answers": out, "annotations": [],
            "model_version": "demo", "transcription_duration_ms": None}


# ---------------------------------------------------------------------------
# 3. the perfect graded draft
# ---------------------------------------------------------------------------

def _leaves(raw: dict):
    """(scope, leaf) in document order; a leaf is a terminal criterion or sub-criterion."""
    for scope in raw["scope_outcomes"]:
        for crit in scope["criterion_outcomes"]:
            for leaf in (crit.get("sub_criterion_outcomes") or [crit]):
                yield scope, crit, leaf


def _leaf_id(leaf: dict) -> str:
    return leaf.get("sub_criterion_id") or leaf["criterion_id"]


def _scope_key(scope: dict) -> str:
    return f"{scope['question_id']}.{scope['sub_question_id']}" if scope["sub_question_id"] \
        else scope["question_id"]


def _reasoning(checks: List[dict]) -> str:
    """The grader's own line format (agents/grader/pricer.py), from clean texts."""
    lines = []
    for c in checks:
        v, text, basis = c["verdict"], c["text"], c.get("basis_he") or ""
        if c.get("charge_group"):
            raise BuildError(f"{c['check_id']}: charge groups are not handled by this builder")
        if c["kind"] == "required":
            lines.append(f"{_MARK[v]} {text}" + (f" — {basis}" if v != "met" and basis else ""))
        elif c["kind"] == "tariff":
            fired = v in ("not_met", "partially_met")
            lines.append(f"✗ {text} — ניכוי {Decimal(str(c['tariff'])).normalize()}"
                         + (f" — {basis}" if basis else "") if fired else f"✓ {text}")
        elif c["kind"] == "note_only":
            fired = v in ("not_met", "partially_met")
            lines.append(f"◦ {text} — צוין, ללא ניכוי" if fired else f"✓ {text}")
        else:
            raise BuildError(f"{c['check_id']}: unexpected check kind {c['kind']}")
    return "\n".join(lines)


def perfect_draft(slug: str, ids: dict, review: list) -> Tuple[dict, Dict[str, Decimal]]:
    raw = load(DRAFTS / f"draft_{slug}.json")
    cleanup = load(CONFIG / "copy_cleanup.json")["replace"]
    corrections = load(CONFIG / "corrections" / f"{slug}.json")["checks"]
    feedback = load(CONFIG / "feedback" / f"{slug}.json")
    answers = {(a["question_number"], a.get("sub_question_id")): a["answer_text"]
               for a in load(TRANSCRIPTIONS / f"{slug}.contract.json")["answers"]}

    # (a) the answer each scope was graded against (EVD-1)
    for scope in raw["scope_outcomes"]:
        n = int(re.sub(r"\D", "", scope["question_id"]))
        text = answers.get((n, scope["sub_question_id"]))
        if text is None:
            raise BuildError(f"{slug} {_scope_key(scope)}: no transcription answer")
        scope["student_answer"] = {"text": text, "source": "own", "inherited_from": None}

    # (b) plain check texts; (c) the verdict corrections
    seen = set()
    for scope, crit, leaf in _leaves(raw):
        answer = scope["student_answer"]["text"]
        for c in leaf.get("checks") or []:
            for field in ("text", "basis_he"):
                if c.get(field) in cleanup:
                    c[field] = cleanup[c[field]]
            fix = corrections.get(c["check_id"])
            if fix:
                seen.add(c["check_id"])
                review.append({"student": slug, "check": c["check_id"],
                               "verdict": f"{c['verdict']} → {fix['verdict']}",
                               "basis_before": c.get("basis_he") or "",
                               "basis_after": fix["basis_he"]})
                c["verdict"] = fix["verdict"]
                c["basis_he"] = fix["basis_he"]
                if "quote" in fix:
                    c["quote"] = fix["quote"]
            if c.get("quote"):
                status = quote_match_status(c["quote"], answer)
                c["quote_status"] = status.value if status is not None else "not_found"
            credited = c["kind"] in ("required", "counted") and c["verdict"] != "not_met"
            if credited and c.get("quote_status") != "exact":
                raise BuildError(f"{slug} {c['check_id']}: credited without an exact quote "
                                 f"({c.get('quote_status')})")
        quotes = []
        for c in leaf.get("checks") or []:
            if c.get("quote") and c["quote"] not in [q["quote_text"] for q in quotes]:
                quotes.append({"position_hint": None, "quote_text": c["quote"],
                               "span_pointer": None, "validation_status": c["quote_status"]})
        leaf["evidence_quotes"] = quotes
        leaf["evidence_quote"] = quotes[0] if quotes else None
        leaf["reasoning"] = _reasoning(leaf.get("checks") or [])
    missing = set(corrections) - seen
    if missing:
        raise BuildError(f"{slug}: corrections name unknown checks {sorted(missing)}")

    # (d) re-price through the ONE pricer, scope-wide (charge groups are scope-wide)
    policy = load(RUBRIC)["numeric_policy"]
    precision = Decimal(str(policy["precision"]))
    model = GradedTestDraft.model_validate(raw)
    index, _ = _build_terminal_index(model)
    by_scope: Dict[tuple, list] = {}
    for info in index.values():
        by_scope.setdefault(info.scope_key, []).append(info)
    prices = {}
    for infos in by_scope.values():
        prices.update(price_scope_checks_detailed(
            [(i.terminal_id, i.points_possible, i.checks) for i in infos], precision))

    for scope in raw["scope_outcomes"]:
        scope_total = Decimal("0")
        for crit in scope["criterion_outcomes"]:
            subs = crit.get("sub_criterion_outcomes")
            for leaf in (subs or [crit]):
                price = prices[_leaf_id(leaf)]
                leaf["points_awarded"] = str(price.awarded)
                flags = [f for f in leaf.get("flags") or []
                         if f["reason"] not in ("evidence_unverified", "bounds_clamped")]
                if price.raw != price.awarded:
                    flags.append({"criterion_id": _leaf_id(leaf), "reason": "bounds_clamped",
                                  "message": f"pricer clamped/snapped: {price.raw} → {price.awarded}"})
                leaf["flags"] = flags
            if subs:
                crit["points_awarded"] = str(sum(Decimal(s["points_awarded"]) for s in subs))
            scope_total += Decimal(crit["points_awarded"])
        scope["points_awarded"] = str(scope_total)

    # (e) diagnostics that the corrected grade no longer earns
    credited_ok = {c["check_id"] for _, _, leaf in _leaves(raw) for c in leaf.get("checks") or []
                   if c.get("quote_status") == "exact"}
    raw["annotations"] = [a for a in raw["annotations"]
                          if not (a["annotation_type"] in ("evidence_unverified", "bounds_clamped")
                                  and (a.get("metadata") or {}).get("check_id") in credited_ok)]
    if any(a["severity"] == "error" for a in raw["annotations"]):
        raise BuildError(f"{slug}: an error annotation would block approval")

    # (f) feedback that agrees with the grade; basis hashes over the final verdicts
    block = raw["feedback"]
    for scope_id, text in feedback["scopes"].items():
        review.append({"student": slug, "feedback": scope_id,
                       "before": block["scopes"][scope_id]["text"], "after": text})
        block["scopes"][scope_id]["text"] = text
    review.append({"student": slug, "feedback": "summary",
                   "before": block["summary"]["text"], "after": feedback["summary"]})
    block["summary"]["text"] = feedback["summary"]
    model = GradedTestDraft.model_validate(raw)
    for scope in model.scope_outcomes:
        sid = rx.scope_id_of(scope)
        block["scopes"][sid]["basis_hash"] = basis_hash(list(flatten_checks(scope)))

    # (g) the ids the website joins on
    raw["teacher_overrides"] = {}
    raw["transcription_contract_version"] = f"demo-{ids['id']}"
    return raw, {tid: p.awarded for tid, p in prices.items()}


# ---------------------------------------------------------------------------
# 4-6. approval, the scripted variant, the signed exams
# ---------------------------------------------------------------------------

def approved_payload(raw: dict, overrides: GradedTestOverrides, rubric: GradingRubricContract,
                     ids: dict, contract_version: str, approved_at: str) -> Tuple[dict, object]:
    draft = GradedTestDraft.model_validate(raw)
    contract = compile_graded_test(draft, overrides, rubric)
    contract_json = contract.model_dump(mode="json")
    contract_json["approved_at"] = approved_at
    contract_json["contract_version"] = contract_version
    stored = copy.deepcopy(raw)
    stored["teacher_overrides"] = overrides.model_dump(mode="json")
    return {
        "id": ids["graded_test_id"], "status": "approved",
        "student_name": ids["display_name"], "filename": f"{ids['display_name']}.pdf",
        "transcription_id": ids["transcription_id"], "regraded_from_id": None,
        "total_score": str(contract.total_score), "total_possible": str(contract.total_possible),
        "percentage": str(contract.percentage) if contract.percentage is not None else None,
        "approved_at": approved_at,
        "numeric_policy": rubric.numeric_policy.model_dump(mode="json"),
        "rubric_contract_stale": False, "total_cost_usd": None,
        "contract": contract_json, "draft": stored,
    }, contract


def signed_pdf(scan_pdf: bytes, display_name: str, contract) -> bytes:
    pdf = rx.render_returned_exam(
        scan_pdf, display_name,
        rx.scopes_for_render(contract, INCLUDE_CRITERIA), rx.summary_for_render(contract),
        None, INCLUDE_CRITERIA,
        rx.format_points(contract.total_score), rx.format_points(contract.total_possible))
    return _clean_pdf(fitz.open(stream=pdf, filetype="pdf"))


def pdf_pages_webp(pdf: bytes, long_edge: int) -> List[bytes]:
    doc = fitz.open(stream=pdf, filetype="pdf")
    out = []
    for page in doc:
        zoom = long_edge / max(page.rect.width, page.rect.height)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        out.append(_webp(Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB"), long_edge))
    return out


def write_zip(path: Path, entries: List[Tuple[str, bytes]]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 23, 20, 30, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.flag_bits |= 0x800                                  # UTF-8 names
            zf.writestr(info, data)


# ---------------------------------------------------------------------------
# the build
# ---------------------------------------------------------------------------

def build(out: Path, review_dir: Path) -> None:
    pseudo = load(CONFIG / "pseudonyms.json")
    redactions = load(CONFIG / "redactions.json")
    rubric_raw = load(RUBRIC)
    rubric = GradingRubricContract.model_validate(rubric_raw)
    approved_at, batch_name = pseudo["approved_at"], pseudo["batch_name"]
    review: list = []

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    review_dir.mkdir(parents=True, exist_ok=True)
    dump(out / "rubric.contract.json", rubric_raw)

    students_manifest = []
    zip_proposed, zip_variant = [], []
    for slug in STUDENTS:
        ids = pseudo["students"][slug]
        sdir = out / "students" / ids["id"]
        gt = {t["terminal_id"]: Decimal(t["awarded"]) for t in load(GT_DIR / f"{slug}.gt.json")["terminals"]}

        # 1. scans
        scan_pdf, pages, originals = redacted_scan(slug, redactions.get(slug, {}))
        for n, im in enumerate(pages, start=1):
            (sdir / "scan").mkdir(parents=True, exist_ok=True)
            (sdir / "scan" / f"page-{n}.webp").write_bytes(_webp(im, SCAN_LONG_EDGE))
            (sdir / "scan" / f"page-{n}.thumb.webp").write_bytes(_webp(im, THUMB_LONG_EDGE))
        _contact_sheet(review_dir / f"contact_sheet_{ids['id']}.png", originals, pages)

        # 2. transcription
        dump(sdir / "transcription.draft.json",
             transcription_draft(slug, ids["display_name"], len(pages)))

        # 3. the perfect draft — and the check that makes it perfect
        raw, priced = perfect_draft(slug, ids, review)
        if set(priced) != set(gt):
            raise BuildError(f"{slug}: terminal set differs from GT: {set(priced) ^ set(gt)}")
        wrong = {t: (str(priced[t]), str(gt[t])) for t in gt if priced[t] != gt[t]}
        if wrong:
            raise BuildError(f"{slug}: priced != teacher GT on {wrong}")
        total = sum(priced.values())

        # 4. approval through the real gate
        approved, contract = approved_payload(raw, GradedTestOverrides(), rubric, ids,
                                              ids["contract_version"], approved_at)
        if contract.total_score != total:
            raise BuildError(f"{slug}: contract total {contract.total_score} != priced {total}")
        dump(sdir / "graded.approved.json", approved)
        dump(sdir / "graded.draft.json", {
            "id": ids["graded_test_id"], "status": "draft", "student_name": ids["display_name"],
            "filename": f"{ids['display_name']}.pdf", "transcription_id": ids["transcription_id"],
            "numeric_policy": rubric.numeric_policy.model_dump(mode="json"),
            "total_score": str(total), "total_possible": str(contract.total_possible),
            "percentage": approved["percentage"], "draft": raw,
            "rubric_contract_stale": False, "regraded_from_id": None})

        # 6. signed exams
        name = rx.zip_entry_name(batch_name, ids["display_name"])
        signed = signed_pdf(scan_pdf, ids["display_name"], contract)
        (sdir / "signed").mkdir(parents=True, exist_ok=True)
        (sdir / "signed" / "exam.pdf").write_bytes(signed)
        signed_pages = pdf_pages_webp(signed, SIGNED_LONG_EDGE)
        for n, data in enumerate(signed_pages, start=1):
            (sdir / "signed" / f"page-{n}.webp").write_bytes(data)
        zip_proposed.append((name, signed))
        entry = {"id": ids["id"], "display_name": ids["display_name"],
                 "graded_test_id": ids["graded_test_id"], "transcription_id": ids["transcription_id"],
                 "filename": f"{ids['display_name']}.pdf", "pages": len(pages),
                 "total_score": str(total), "total_possible": str(contract.total_possible),
                 "signed_pdf": f"students/{ids['id']}/signed/exam.pdf",
                 "signed_pages": len(signed_pages), "zip_entry_name": name}

        # 5. the scripted control moment (a teacher override, never a proposal)
        variant = load(CONFIG / "corrections" / f"{slug}.json").get("variant_q1a")
        if variant:
            overrides = GradedTestOverrides(terminals={variant["terminal_id"]: [
                # `decided_at` defaults to now(); pinned (a minute before approval)
                # so the bundle is byte-stable, as `approved_at` already is.
                TeacherOverride(check_id=variant["check_id"], verdict=variant["verdict"],
                                decided_at=approved_at.replace("17:30:", "17:29:"))]})
            v_payload, v_contract = approved_payload(raw, overrides, rubric, ids,
                                                     ids["variant_contract_version"], approved_at)
            terminal = next(t for s in v_contract.scope_outcomes for t in s.terminal_outcomes
                            if t.terminal_id == variant["terminal_id"])
            if (terminal.final_points_awarded != Decimal(variant["expect_terminal"])
                    or v_contract.total_score != Decimal(variant["expect_total"])):
                raise BuildError(f"{slug}: variant priced {terminal.final_points_awarded} / "
                                 f"{v_contract.total_score}, expected {variant['expect_terminal']} / "
                                 f"{variant['expect_total']}")
            dump(sdir / "graded.approved.variant-q1a.json", v_payload)
            v_signed = signed_pdf(scan_pdf, ids["display_name"], v_contract)
            (sdir / "signed-variant-q1a").mkdir(parents=True, exist_ok=True)
            (sdir / "signed-variant-q1a" / "exam.pdf").write_bytes(v_signed)
            v_pages = pdf_pages_webp(v_signed, SIGNED_LONG_EDGE)
            for n, data in enumerate(v_pages, start=1):
                (sdir / "signed-variant-q1a" / f"page-{n}.webp").write_bytes(data)
            zip_variant.append((name, v_signed))
            entry["variant_q1a"] = {
                "terminal_id": variant["terminal_id"], "check_id": variant["check_id"],
                "terminal_awarded": variant["expect_terminal"], "total_score": variant["expect_total"],
                "approved": f"students/{ids['id']}/graded.approved.variant-q1a.json",
                "signed_pdf": f"students/{ids['id']}/signed-variant-q1a/exam.pdf",
                "signed_pages": len(v_pages)}
        else:
            zip_variant.append((name, signed))
        students_manifest.append(entry)

    write_zip(out / "signed-exams.zip", zip_proposed)
    write_zip(out / "signed-exams.variant-q1a.zip", zip_variant)
    _write_manifest(out, students_manifest, batch_name)
    _write_review(review_dir / "review.md", review,
                  {slug: pseudo["students"][slug]["display_name"] for slug in STUDENTS})
    verify(out)


def _contact_sheet(path: Path, before: List[Image.Image], after: List[Image.Image]) -> None:
    """Before | after, one row per page, for the owner's eye review. Never in the bundle."""
    rows = []
    for b, a in zip(before, after):
        bs, as_ = (im.resize((round(im.width * 520 / im.height), 520)) for im in (b, a))
        row = Image.new("RGB", (bs.width + as_.width + 20, 520), "white")
        row.paste(bs, (0, 0))
        row.paste(as_, (bs.width + 20, 0))
        rows.append(row)
    sheet = Image.new("RGB", (max(r.width for r in rows), sum(r.height + 20 for r in rows)), "#888")
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height + 20
    sheet.save(path)


def _write_review(path: Path, review: list, names: Dict[str, str]) -> None:
    lines = ["# Hebrew authored for the demo bundle — for the owner's review", ""]
    for item in review:
        item = {**item, "student": names[item["student"]]}
        if "check" in item:
            lines += [f"## {item['student']} · {item['check']} · {item['verdict']}",
                      f"- before: {item['basis_before'] or '—'}", f"- after: {item['basis_after'] or '—'}", ""]
        else:
            lines += [f"## {item['student']} · feedback {item['feedback']}",
                      f"- before: {item['before']}", f"- after: {item['after']}", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                                       text=True).strip()
    except Exception:                                                # noqa: BLE001
        return "unknown"


def _write_manifest(out: Path, students: list, batch_name: str) -> None:
    files = {}
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name not in ("manifest.json",):
            files[p.relative_to(out).as_posix()] = {
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
    dump(out / "manifest.json", {
        "bundle_version": BUNDLE_VERSION,
        "source": {"repo": "vivi-codebase", "commit": _git_commit(),
                   "script": "backend/scripts/build_marketing_demo_bundle.py"},
        "batch_name": batch_name,
        "appendix_include_criteria": INCLUDE_CRITERIA,
        "rubric": "rubric.contract.json",
        "zips": {"proposed": "signed-exams.zip", "variant_q1a": "signed-exams.variant-q1a.zip"},
        "students": students,
        "files": files,
    })
    dump(out / "bundle.schema.json", MANIFEST_SCHEMA)


MANIFEST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Vivi marketing-demo bundle manifest",
    "type": "object",
    "required": ["bundle_version", "source", "batch_name", "appendix_include_criteria",
                 "rubric", "zips", "students", "files"],
    "properties": {
        "bundle_version": {"const": BUNDLE_VERSION},
        "batch_name": {"type": "string"},
        "appendix_include_criteria": {"type": "boolean"},
        "rubric": {"type": "string"},
        "zips": {"type": "object", "required": ["proposed", "variant_q1a"]},
        "students": {"type": "array", "items": {
            "type": "object",
            "required": ["id", "display_name", "graded_test_id", "transcription_id", "filename",
                         "pages", "total_score", "total_possible", "signed_pdf", "signed_pages",
                         "zip_entry_name"],
            "properties": {"variant_q1a": {"type": "object", "required": [
                "terminal_id", "check_id", "terminal_awarded", "total_score", "approved",
                "signed_pdf", "signed_pages"]}}}},
        "files": {"type": "object", "additionalProperties": {
            "type": "object", "required": ["sha256", "bytes"]}},
    },
}


# ---------------------------------------------------------------------------
# verification — every build, no exceptions
# ---------------------------------------------------------------------------

def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from _strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)


def verify(out: Path) -> None:
    problems = []
    total = 0
    for p in sorted(out.rglob("*")):
        if not p.is_file():
            continue
        total += p.stat().st_size
        rel = p.relative_to(out).as_posix()
        texts: List[str] = [rel]
        if p.suffix == ".json":
            data = load(p)
            texts += list(_strings(data))
            if p.name.startswith("graded."):
                for s in _visible(data):
                    if PLAN_CODE.search(s):
                        problems.append(f"{rel}: plan code / verdict name in «{s[:80]}»")
        elif p.suffix == ".pdf":
            doc = fitz.open(p)
            if any(doc.metadata.get(k) for k in ("title", "author", "subject", "creator",
                                                  "producer", "keywords")):
                problems.append(f"{rel}: PDF metadata not empty: {doc.metadata}")
            texts += [page.get_text() for page in doc]
        elif p.suffix == ".zip":
            with zipfile.ZipFile(p) as zf:
                texts += zf.namelist()
                for name in zf.namelist():
                    doc = fitz.open(stream=zf.read(name), filetype="pdf")
                    texts += [page.get_text() for page in doc]
        for t in texts:
            for rule in FORBIDDEN:
                if rule.search(t):
                    problems.append(f"{rel}: forbidden identifier /{rule.pattern}/ in «{t[:80]}»")
        size = p.stat().st_size
        if p.suffix == ".webp":
            kind = "thumb" if ".thumb." in p.name else ("signed" if "signed" in rel else "scan")
            if size > BUDGET[kind]:
                problems.append(f"{rel}: {size} bytes > {kind} budget {BUDGET[kind]}")
    if total > BUDGET["bundle"]:
        problems.append(f"bundle is {total} bytes > {BUDGET['bundle']}")
    manifest = load(out / "manifest.json")
    for rel, meta in manifest["files"].items():
        if hashlib.sha256((out / rel).read_bytes()).hexdigest() != meta["sha256"]:
            problems.append(f"{rel}: sha256 differs from manifest")
    if problems:
        raise BuildError("verification failed:\n  - " + "\n  - ".join(dict.fromkeys(problems)))
    print(f"verified: {len(manifest['files'])} files, {total / 1e6:.2f} MB")


# Fields a person reads on the review surface, the signed exam or the feedback.
# Enum VALUES ("kind": "tariff", "verdict": "met") are data, not prose; and the
# student's own answer (`student_answer.text`) is evidence, never rewritten.
_VISIBLE_KEYS = {"basis_he", "reasoning", "message", "message_he", "description"}


def _visible(node, key: str = "", parent: str = ""):
    if isinstance(node, str):
        if key in _VISIBLE_KEYS or (key == "text" and parent not in ("student_answer",)):
            yield node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from _visible(v, k, key)
    elif isinstance(node, list):
        for v in node:
            yield from _visible(v, key, parent)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--review-dir", type=Path, default=None)
    parser.add_argument("--check", action="store_true",
                        help="rebuild into a temp dir and fail on any byte difference from --out")
    args = parser.parse_args()
    review = args.review_dir or Path(tempfile.mkdtemp(prefix="demo-bundle-review-"))

    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            fresh = Path(tmp) / "v1"
            build(fresh, review)
            diff = _diff(fresh, args.out)
            if diff:
                raise BuildError("--out differs from a fresh build:\n  - " + "\n  - ".join(diff))
        print(f"check: {args.out} is byte-identical to a fresh build")
        return
    build(args.out, review)
    print(f"bundle: {args.out}\nreview: {review}")


def _diff(a: Path, b: Path) -> List[str]:
    fa = {p.relative_to(a).as_posix() for p in a.rglob("*") if p.is_file()}
    fb = {p.relative_to(b).as_posix() for p in b.rglob("*") if p.is_file()} if b.exists() else set()
    out = [f"only in fresh: {x}" for x in sorted(fa - fb)] + [f"only in out: {x}" for x in sorted(fb - fa)]
    out += [f"differs: {x}" for x in sorted(fa & fb)
            if not filecmp.cmp(a / x, b / x, shallow=False)]
    return out


if __name__ == "__main__":
    main()
