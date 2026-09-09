"""Phase 5 smoke: one fixture, one subject, the whole product path — render (deterministic or
rubric-read) -> extraction -> the profile's post-pass -> compile. Records everything.

    python run_any.py <out_dir> <subject> <path/to/fixture>
"""
import asyncio, io, json, os, sys, time, logging
from dotenv import load_dotenv; load_dotenv(".env")
os.environ.setdefault("EXTRACTION_LLM_PROVIDER", "openai")
os.environ.setdefault("EXTRACTION_LLM_MODEL", "gpt-5.6-terra")
os.environ.setdefault("EXTRACTION_LLM_REASONING_EFFORT", "high")
os.environ.setdefault("EXTRACTION_LLM_MAX_TOKENS", "32000")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

OUT, SUBJECT, SRC = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)

from app.services.docx_v3 import pipeline as pl
from app.services.contract_compiler import ContractCompiler
from app.schemas.ontology_types import NumericPolicy


async def main():
    data = open(SRC, "rb").read()
    t0 = time.time()
    result = await pl.extract_rubric_from_docx(
        data, pl.ExtractionConfig(subject=SUBJECT),
        name=os.path.basename(SRC), source_filename=os.path.basename(SRC))
    wall = time.time() - t0
    resp, m = result.response, result.metrics
    io.open(f"{OUT}/draft.json", "w", encoding="utf-8").write(resp.model_dump_json(indent=1))
    rescale = resp.extraction_metadata.get("rescale_to_exam")
    summary = {
        "fixture": os.path.basename(SRC), "subject": SUBJECT,
        "wall_s": round(wall, 1), "model": m.llm_model, "retry_count": m.retry_count,
        "input_tokens": m.input_tokens, "output_tokens": m.output_tokens,
        "prompt_version": result.metadata.get("prompt_version"),
        "render": result.metadata.get("render"),
        "total_points": str(resp.total_points),
        "question_types": sorted({q.question_type.value for q in resp.questions}),
        "question_totals": [(q.question_id, str(q.total_points)) for q in resp.questions],
        "selection_groups": [g.model_dump(mode="json") for g in resp.selection_groups],
        "n_criteria": sum(len(q.all_criteria) for q in resp.questions),
        "rescale": rescale,
        "warnings": result.warnings[:12],
        "annotations": [(a.severity.value, a.annotation_type, a.target_id, (a.message or "")[:110])
                        for a in resp.annotations][:12],
    }
    try:
        c = ContractCompiler().compile(resp, policy=NumericPolicy(),
                                       acknowledged_warnings=[a.id for a in resp.annotations])
        io.open(f"{OUT}/contract.json", "w", encoding="utf-8").write(c.model_dump_json(indent=1))
        summary["compile"] = f"OK total={c.total_points}"
    except Exception as e:
        summary["compile"] = f"BLOCKED: {type(e).__name__}: {str(e)[:600]}"
    json.dump(summary, io.open(f"{OUT}/summary.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)
    print(json.dumps(summary, ensure_ascii=False, indent=1, default=str)[:2200])

asyncio.run(main())
