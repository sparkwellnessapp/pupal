"""Phase 4a evidence: the PUBLIC-MINISTRY F/G writing rubric through the real pipeline with the
english profile. The claim under test (P-12 / D-3 beta path): a four-band ladder comes back as
ONE criterion at the TOP band's points, so the four criteria read 8 / 10 / 16 / 6 = 40."""
import asyncio, io, json, os, sys, time, logging
from dotenv import load_dotenv; load_dotenv(".env")
os.environ.setdefault("EXTRACTION_LLM_PROVIDER", "openai")
os.environ.setdefault("EXTRACTION_LLM_MODEL", "gpt-5.6-terra")
os.environ.setdefault("EXTRACTION_LLM_REASONING_EFFORT", "high")
os.environ.setdefault("EXTRACTION_LLM_MAX_TOKENS", "32000")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
from app.services.docx_v3 import pipeline as pl
from app.services.contract_compiler import ContractCompiler
from app.schemas.ontology_types import NumericPolicy

SRC = "tests/rubric_eval_suite/fixtures/English_rubircs-solutions/public/ministry_FG_writing_rubric_2020.docx"


async def main():
    data = open(SRC, "rb").read()
    t0 = time.time()
    result = await pl.extract_rubric_from_docx(
        data, pl.ExtractionConfig(subject="english"),
        name="Ministry F/G writing rubric (Winter 2020)", source_filename=os.path.basename(SRC))
    wall = time.time() - t0
    resp, m = result.response, result.metrics
    io.open(f"{OUT}/draft.json", "w", encoding="utf-8").write(resp.model_dump_json(indent=1))
    crits = [(c.criterion_id, str(c.points), c.description[:90], len(c.sub_criteria or []))
             for q in resp.questions for c in q.all_criteria]
    summary = {
        "wall_s": round(wall, 1), "model": m.llm_model, "retry_count": m.retry_count,
        "input_tokens": m.input_tokens, "output_tokens": m.output_tokens,
        "prompt_version": result.metadata.get("prompt_version"),
        "render": result.metadata.get("render"),
        "total_points": str(resp.total_points),
        "question_types": [q.question_type.value for q in resp.questions],
        "question_totals": [(q.question_id, str(q.total_points)) for q in resp.questions],
        "n_criteria": len(crits), "criteria": crits,
        "criterion_points": [str(c.points) for q in resp.questions for c in q.all_criteria],
        "warnings": result.warnings,
        "annotations": [(a.severity.value, a.annotation_type, a.target_id, a.message[:120])
                        for a in resp.annotations],
        "rescale_ran": "rescale_to_exam" in resp.extraction_metadata,
    }
    try:
        c = ContractCompiler().compile(resp, policy=NumericPolicy(),
                                       acknowledged_warnings=[a.id for a in resp.annotations])
        io.open(f"{OUT}/contract.json", "w", encoding="utf-8").write(c.model_dump_json(indent=1))
        summary["compile"] = f"OK total={c.total_points}"
    except Exception as e:
        summary["compile"] = f"BLOCKED: {type(e).__name__}: {str(e)[:700]}"
    json.dump(summary, io.open(f"{OUT}/summary.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)
    print(json.dumps(summary, ensure_ascii=False, indent=1, default=str)[:2500])

asyncio.run(main())
