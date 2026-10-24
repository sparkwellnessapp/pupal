"""
In-house scanning — the scan eval (PR_in_house_scanning.md §11). NOT a merge
gate and NOT a test: it makes REAL model calls (P1 only).

    python -m tests.scan_eval.run --photos <dir> [--gt <raw_benchmarks dir>]
                                  [--arms raw,ours,external] [--config v0]
                                  [--out <dir>] [--dry-run]

Input layout:   <photos>/<doc_id>/page_01.jpg, page_02.jpg, …
                <photos>/<doc_id>/external.pdf      (optional: CamScanner / copier)
Ground truth:   <gt>/<doc_id>.md — the transcription suite's raw_benchmarks
                (default: tests/transcription_eval_suit/raw_benchmarks). Read only.

Arms
  raw       the photos wrapped into a PDF unprocessed (EXIF orientation only)
  ours      the scan-service pipeline with AUTOMATIC corners, no manual edit —
            exactly what a page gets before anyone touches it
  external  the provided PDF, as given

Each arm's PDF goes through the suite's OWN `p1_only` path — `run_phase1` +
`score_page_document` against the raw GT, the same scorer, policy and profile
`runner.py` uses — so the three arms are measured by one ruler. Reported per
doc: doc_ratio_strict, coverage, critical recalls, and the WORST doc per arm
(the suite's worst-doc discipline, transcription eval §0.5). Also reported,
per page: the detection outcome (auto_contour / full_frame), confidence and
quality reasons — the data that calibrates the contour gate and T_BLUR.

DECISION RULE (in the report header): ours ≥ external on worst-doc strict
ratio AND on every critical recall = scanning is at parity.

Needs scan-service's dependencies (OpenCV, img2pdf, pillow-heif) importable:
    pip install -r ../scan-service/requirements.txt
`--dry-run` builds the arms and the detection report and makes NO model call.
"""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
SCAN_SERVICE = BACKEND.parent / "scan-service"
SUITE = BACKEND / "tests" / "transcription_eval_suit"
DEFAULT_GT = SUITE / "raw_benchmarks"

DECISION_RULE = ("ours ≥ external on worst-doc doc_ratio_strict AND on every "
                 "critical recall ⇒ scanning is at parity")


def _import_scan():
    if str(SCAN_SERVICE) not in sys.path:
        sys.path.insert(0, str(SCAN_SERVICE))
    try:
        from scan import SCAN_PIPELINE_VERSION
        from scan import pipeline as P
        from scan.assemble import assemble_pdf
    except ImportError as exc:                                  # pragma: no cover
        raise SystemExit(f"scan-service is not importable ({exc}). "
                         f"pip install -r {SCAN_SERVICE / 'requirements.txt'}")
    return SCAN_PIPELINE_VERSION, P, assemble_pdf


# ---------------------------------------------------------------------------
# building the arms
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class PageDetection:
    page: str
    corners_source: str
    confidence: float
    verdict: str
    reasons: list


ARMS = ("raw", "ours", "external")


def _page_order(path: Path) -> tuple:
    """page_2 before page_10: the number in the name, not its spelling."""
    digits = "".join(ch for ch in path.stem if ch.isdigit())
    return (int(digits) if digits else 0, path.name)


def build_arms(doc_dir: Path, arms: list[str]) -> tuple[dict[str, bytes], list[PageDetection]]:
    version, P, assemble_pdf = _import_scan()
    photos = sorted((p for p in doc_dir.iterdir()
                     if p.is_file() and p.name.lower().startswith("page_")
                     and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".heic", ".heif")),
                    key=_page_order)
    pdfs: dict[str, bytes] = {}
    detections: list[PageDetection] = []
    raw_pages, ours_pages = [], []
    for photo in photos:
        data = photo.read_bytes()
        decoded = P.decode_bounded(data)                         # what production analyzes
        rgb = decoded.rgb
        if "raw" in arms:
            # Unprocessed: no flatten, no cleanup; sized like the arm's other pages.
            raw_pages.append(P.encode_jpeg(P.resize_long_side(rgb, P.COMPILE_LONG_SIDE),
                                           P.COMPILE_QUALITY))
        det = P.detect(rgb)
        q = P.assess(rgb, det, scale=decoded.scale)
        detections.append(PageDetection(photo.name, det.source, det.confidence, q.verdict,
                                        list(q.reasons)))
        if "ours" in arms:
            ours_pages.append(P.encode_jpeg(
                P.render_page(data, det.corners, 0, P.COMPILE_LONG_SIDE, enhance=True),
                P.COMPILE_QUALITY))
    if raw_pages:
        pdfs["raw"] = assemble_pdf(raw_pages)
    if ours_pages:
        pdfs["ours"] = assemble_pdf(ours_pages)
    external = doc_dir / "external.pdf"
    if "external" in arms and external.exists():
        pdfs["external"] = external.read_bytes()
    return pdfs, detections


# ---------------------------------------------------------------------------
# scoring — the suite's p1_only path, unchanged
# ---------------------------------------------------------------------------

async def score_arm(pipeline, doc_id: str, pdf: bytes, gt_path: Path) -> dict:
    from tests.transcription_eval_suit.exam_resolution import resolve_exam
    from tests.transcription_eval_suit.ground_truth import load_page_ground_truth
    from tests.transcription_eval_suit.profiles import DEFAULT_PROFILE, profile as resolve_profile
    from tests.transcription_eval_suit.runner import SCORING_POLICY, _ser_p1
    from tests.transcription_eval_suit.scoring import score_page_document

    gold = load_page_ground_truth(gt_path)
    exam = resolve_exam(doc_id, fallback_spec_path=None)
    profile = exam.profile if exam else resolve_profile(DEFAULT_PROFILE)
    pages, _trace = await pipeline.run_phase1(pdf, doc_id, doc_priority=0)
    return _ser_p1(score_page_document(pages, gold, profile=profile, policy=SCORING_POLICY))


def _critical_recalls(p1: dict) -> dict:
    c = p1.get("critical") or {}
    return {k: v for k, v in c.items() if "recall" in k}


def _worst(rows: list[dict], arm: str, arms: list[str]) -> dict | None:
    # Over the docs EVERY requested arm scored: `external` exists only where an
    # external.pdf does, and a worst-doc taken over different sets would let
    # the decision rule compare one arm's hardest doc with another's easier set.
    scored = [r for r in rows if all(r["arms"].get(a) for a in arms)]
    if not scored:
        return None
    w = min(scored, key=lambda r: r["arms"][arm]["doc_ratio_strict"])
    return {"doc_id": w["doc_id"], **{k: w["arms"][arm][k] for k in ("doc_ratio_strict", "coverage")},
            "critical": _critical_recalls(w["arms"][arm])}


def write_report(out: Path, rows: list[dict], arms: list[str], meta: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    worst = {arm: _worst(rows, arm, arms) for arm in arms}
    common = sum(1 for r in rows if all(r["arms"].get(a) for a in arms))
    (out / "results.json").write_text(json.dumps({"meta": meta, "rows": rows, "worst": worst},
                                                 ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [f"# Scan eval — {meta['scan_pipeline_version']}", "",
             f"**Decision rule:** {DECISION_RULE}", "",
             f"config `{meta['config']}` · arms {', '.join(arms)} · {meta['when']}", ""]
    if not meta["dry_run"]:
        lines += ["## Worst doc per arm", "",
                  f"over the {common} doc(s) every arm scored ({len(rows)} in the run)", "",
                  "| arm | doc | strict | coverage | critical recalls |", "|---|---|---|---|---|"]
        for arm, w in worst.items():
            if w:
                lines.append(f"| {arm} | {w['doc_id']} | {w['doc_ratio_strict']:.4f} | "
                             f"{w['coverage']:.4f} | {json.dumps(w['critical'], ensure_ascii=False)} |")
        lines += ["", "## Per doc", "", "| doc | " + " | ".join(f"{a} strict" for a in arms) + " |",
                  "|---|" + "---|" * len(arms)]
        for r in rows:
            cells = [f"{r['arms'][a]['doc_ratio_strict']:.4f}" if r["arms"].get(a) else "—" for a in arms]
            lines.append(f"| {r['doc_id']} | " + " | ".join(cells) + " |")
    lines += ["", "## Detection per page (the calibration data)", "",
              "| doc | page | corners_source | confidence | verdict | reasons |", "|---|---|---|---|---|---|"]
    for r in rows:
        for d in r["detections"]:
            lines.append(f"| {r['doc_id']} | {d['page']} | {d['corners_source']} | {d['confidence']:.2f} | "
                         f"{d['verdict']} | {', '.join(d['reasons']) or '—'} |")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run(args) -> Path:
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    unknown = sorted(set(arms) - set(ARMS))
    if unknown:
        raise SystemExit(f"unknown arm(s) {unknown}; known: {', '.join(ARMS)}")
    version, _P, _a = _import_scan()
    photos = Path(args.photos)
    gt_dir = Path(args.gt)
    out = Path(args.out)
    docs = sorted(p for p in photos.iterdir() if p.is_dir())
    pipeline = None
    if not args.dry_run:
        # Every ground truth BEFORE the first paid call: a missing one found
        # half-way used to abort the run and lose what was already paid for.
        missing = [d.name for d in docs if not (gt_dir / f"{d.name}.md").exists()]
        if missing:
            raise SystemExit(f"no ground truth for {missing} in {gt_dir}")
        from tests.transcription_eval_suit.runner import _load_config, make_default_pipeline
        pipeline = make_default_pipeline(_load_config(args.config))
    meta = {"scan_pipeline_version": version, "config": args.config,
            "dry_run": args.dry_run, "when": time.strftime("%Y-%m-%d %H:%M")}
    rows = []
    for doc_dir in docs:
        pdfs, detections = build_arms(doc_dir, arms)
        row = {"doc_id": doc_dir.name, "arms": {}, "detections": [dataclasses.asdict(d) for d in detections],
               "pdf_bytes": {a: len(b) for a, b in pdfs.items()}}
        gt = gt_dir / f"{doc_dir.name}.md"
        if pipeline is not None:
            if not gt.exists():
                raise SystemExit(f"{doc_dir.name}: no ground truth at {gt}")
            for arm, pdf in pdfs.items():
                row["arms"][arm] = await score_arm(pipeline, doc_dir.name, pdf, gt)
        rows.append(row)
        if args.keep_pdfs:
            for arm, pdf in pdfs.items():
                (out / "pdfs").mkdir(parents=True, exist_ok=True)
                (out / "pdfs" / f"{doc_dir.name}.{arm}.pdf").write_bytes(pdf)
        # After EVERY doc: a provider failure on doc N keeps docs 1..N-1.
        write_report(out, rows, arms, meta)
    write_report(out, rows, arms, meta)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--photos", required=True, help="<dir>/<doc_id>/page_NN.jpg …")
    ap.add_argument("--gt", default=str(DEFAULT_GT), help="raw_benchmarks directory (read only)")
    ap.add_argument("--arms", default="raw,ours,external")
    ap.add_argument("--config", default="v0", help="a transcription suite config (P1 is what runs)")
    ap.add_argument("--out", default=str(BACKEND / "tests" / "scan_eval" / "results" / time.strftime("%Y%m%d_%H%M%S")))
    ap.add_argument("--dry-run", action="store_true", help="build the arms; no model calls")
    ap.add_argument("--keep-pdfs", action="store_true", help="write each arm's PDF beside the report")
    args = ap.parse_args()
    out = asyncio.run(run(args))
    print(f"report: {out / 'report.md'}")


if __name__ == "__main__":
    main()
