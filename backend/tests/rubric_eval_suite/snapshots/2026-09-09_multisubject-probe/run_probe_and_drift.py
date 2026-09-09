"""Two unfinished plan items in one pass.

A) Phase 4a's second test — the OMML/bands probe through the english profile, so the band table
   10/6/4 becomes a PINNED benchmark instead of "today's coincidence".
B) P-11b — grid-snap drift on the REAL 4-unit document. `rescale_to_exam` is applied inside the
   pipeline, so the pre-rescale draft is normally never seen; here the post-pass is intercepted so
   both sides are captured and `max_criterion_drift` can be computed on real weights.

Render for (B) is replayed from the recorded run — already paid for.
"""
import asyncio, io, json, os, sys, time, logging
from dotenv import load_dotenv; load_dotenv(".env")
os.environ.setdefault("EXTRACTION_LLM_PROVIDER", "openai")
os.environ.setdefault("EXTRACTION_LLM_MODEL", "gpt-5.6-terra")
os.environ.setdefault("EXTRACTION_LLM_REASONING_EFFORT", "high")
os.environ.setdefault("EXTRACTION_LLM_MAX_TOKENS", "32000")
logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)

from app.services.docx_v3 import pipeline as pl
from app.services.docx_v3 import rescale_to_exam as rx
from app.services.docx_v3 import image_render as ir
from app.services.docx_v3.image_render import RenderReport
from app.services.contract_compiler import ContractCompiler
from app.schemas.ontology_types import NumericPolicy

PROBE = "tests/rubric_eval_suite/fixtures/probes/omml_bands_probe.docx"
MATH4 = "tests/rubric_eval_suite/fixtures/Math_rubrics/4 יחל מבחן ומחוון.docx"
CACHE = "tests/rubric_eval_suite/snapshots/2026-09-09_multisubject-math4"


async def probe():
    """(A) the band ladder, pinned."""
    t0 = time.time()
    res = await pl.extract_rubric_from_docx(
        open(PROBE, "rb").read(), pl.ExtractionConfig(subject="english"),
        name="OMML + bands probe", source_filename=os.path.basename(PROBE))
    r = res.response
    io.open(f"{OUT}/probe_draft.json", "w", encoding="utf-8").write(r.model_dump_json(indent=1))
    crits = [c for q in r.questions for c in q.all_criteria]
    out = {
        "wall_s": round(time.time() - t0, 1), "model": res.metrics.llm_model,
        "retry_count": res.metrics.retry_count,
        "input_tokens": res.metrics.input_tokens, "output_tokens": res.metrics.output_tokens,
        "prompt_version": res.metadata.get("prompt_version"),
        "render": res.metadata.get("render"),
        "total_points": str(r.total_points),
        "question_types": sorted({q.question_type.value for q in r.questions}),
        "criteria": [(c.criterion_id, str(c.points), c.description) for c in crits],
        "criterion_points": [str(c.points) for c in crits],
        "warnings": res.warnings,
    }
    try:
        c = ContractCompiler().compile(r, policy=NumericPolicy(),
                                       acknowledged_warnings=[a.id for a in r.annotations])
        out["compile"] = f"OK total={c.total_points}"
    except Exception as e:
        out["compile"] = f"BLOCKED: {type(e).__name__}: {str(e)[:400]}"
    json.dump(out, io.open(f"{OUT}/probe_summary.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)
    print("A) PROBE:", json.dumps({k: out[k] for k in
          ("criterion_points", "total_points", "question_types", "compile", "retry_count")},
          ensure_ascii=False))


async def drift():
    """(B) P-11b on the real 4-unit weights: capture both sides of the post-pass."""
    md = io.open(f"{CACHE}/render.md", encoding="utf-8").read()
    rep = json.load(io.open(f"{CACHE}/render_report.json", encoding="utf-8"))
    report = RenderReport(**{k: v for k, v in rep.items() if k not in ("wall_s", "chars")})

    async def replay(file_bytes, filename, deadline_s=None):
        return md, report
    ir.render_source = replay

    captured = {}
    real = rx.rescale_to_exam

    def spy(response, **kw):
        captured["before"] = response.model_copy(deep=True)
        after = real(response, **kw)
        captured["after"] = after
        return after
    # the pipeline imports the function INSIDE the branch, so the patch must land on the
    # defining module's attribute, not on the pipeline namespace
    rx.rescale_to_exam = spy

    t0 = time.time()
    res = await pl.extract_rubric_from_docx(
        open(MATH4, "rb").read(), pl.ExtractionConfig(subject="mathematics"),
        name="4-unit (P-11b drift capture)", source_filename=os.path.basename(MATH4))
    wall = round(time.time() - t0, 1)

    before, after = captured.get("before"), captured.get("after")
    if before is None:
        print("B) DRIFT: the post-pass was never called — nothing to measure"); return
    io.open(f"{OUT}/math4_before_rescale.json", "w", encoding="utf-8").write(before.model_dump_json(indent=1))
    io.open(f"{OUT}/math4_after_rescale.json", "w", encoding="utf-8").write(after.model_dump_json(indent=1))
    worst = rx.max_criterion_drift(before, after)
    stamp = after.extraction_metadata.get("rescale_to_exam", {})
    per_q = {}
    for q in after.questions:
        s = sum((c.points for c in q.all_criteria), type(q.total_points)(0)) if not q.sub_questions else None
        per_q[q.question_id] = str(q.total_points)
    out = {
        "wall_s": wall, "input_tokens": res.metrics.input_tokens,
        "output_tokens": res.metrics.output_tokens, "retry_count": res.metrics.retry_count,
        "max_criterion_drift": str(worst),
        "P_11b_bound": "0.25",
        "passes": worst <= type(worst)("0.25"),
        "exam_total": stamp.get("exam_total"), "exam_total_written": stamp.get("exam_total_written"),
        "shares": stamp.get("shares"), "unresolved": stamp.get("unresolved"),
        "question_totals": per_q,
    }
    json.dump(out, io.open(f"{OUT}/drift_summary.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)
    print("B) DRIFT:", json.dumps(out, ensure_ascii=False, default=str)[:700])


async def main():
    await probe()
    await drift()

asyncio.run(main())
