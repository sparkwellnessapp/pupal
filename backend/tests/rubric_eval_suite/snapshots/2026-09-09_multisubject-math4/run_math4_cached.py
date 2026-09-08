"""REAL-PROVIDER SNAPSHOT, attempt 2 (execution plan Phase 2.t): the 4-unit Math DOCX
through the product pipeline with the render stage REPLAYED from attempt 1's recorded
rubric-read/rr1.0 output (byte-identical text + report; $0.147 already paid), then
extraction (mathematics profile, real provider) -> rescale_to_exam -> compile.
Then a SIMULATED TEACHER FILL of every node the post-pass left unresolved, to prove the
arithmetic compiles at the exam's real 100 once she writes what the document lacks."""
import asyncio, json, os, sys, time, logging
from decimal import Decimal
from dotenv import load_dotenv; load_dotenv(".env")
# THE PRODUCTION PIN (CLAUDE.md D-2, flipped 2026-08-24). The pipeline resolves its model
# from os.environ and falls through to its own gpt-4o code default otherwise — attempt 2
# ran on that default and produced 1 question of 5 with mixed scales, which says nothing
# about the fragment. Cloud Run sets these as service env; a script must set them itself.
os.environ.setdefault("EXTRACTION_LLM_PROVIDER", "openai")
os.environ.setdefault("EXTRACTION_LLM_MODEL", "gpt-5.6-terra")
os.environ.setdefault("EXTRACTION_LLM_REASONING_EFFORT", "high")
os.environ.setdefault("EXTRACTION_LLM_MAX_TOKENS", "32000")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
from app.services.docx_v3 import pipeline as pl
from app.services.docx_v3.image_render import RenderReport
from app.services.docx_v3 import rescale_to_exam as rx
from app.services.contract_compiler import ContractCompiler
from app.schemas.ontology_types import NumericPolicy
SRC = "tests/rubric_eval_suite/fixtures/Math_rubrics/4 יחל מבחן ומחוון.docx"
CACHED_MD = open(os.path.join(OUT, "render.md"), encoding="utf-8").read()
_rep = json.load(open(os.path.join(OUT, "render_report.json"), encoding="utf-8"))
CACHED_REPORT = RenderReport(**{k: v for k, v in _rep.items() if k not in ("wall_s", "chars")})

async def _replay_render(file_bytes, filename, deadline_s=None):
    return CACHED_MD, CACHED_REPORT
# the pipeline imports render_source INSIDE the function, so the patch must land on the
# defining module, not on the pipeline's namespace
from app.services.docx_v3 import image_render as _ir
_ir.render_source = _replay_render

def _find(resp, path):
    qid, *rest = path.split(".")
    node = next(q for q in resp.questions if q.question_id == qid)
    cur = qid
    for part in rest:
        cur = f"{cur}.{part}"
        kids = node.sub_questions
        node = next(s for s in kids if s.sub_question_id in (part, cur))
    return node

def _fill(node, is_question):
    """Simulated teacher decision: the node's points, split onto its children."""
    total = node.total_points if is_question else node.points
    total = rx._snap_nearest(total, rx.GRID)
    if node.sub_questions:
        w = [c.points if c.points > 0 else Decimal(1) for c in node.sub_questions]
        pts = rx.largest_remainder(w, total)
        for c, p in zip(node.sub_questions, pts):
            c.points = p
            _fill(c, False)
    elif node.criteria:
        w = [c.points if c.points > 0 else Decimal(1) for c in node.criteria]
        pts = rx.largest_remainder(w, total)
        for c, p in zip(node.criteria, pts):
            c.points = p

async def main():
    data = open(SRC, "rb").read()
    t0 = time.time()
    result = await pl.extract_rubric_from_docx(data, pl.ExtractionConfig(subject="mathematics"),
                                               name="מתמטיקה 4 יחל מתכונת 2 (35472)", source_filename=os.path.basename(SRC))
    wall = time.time() - t0
    meta = result.metadata; m = result.metrics
    json.dump(meta, open(os.path.join(OUT, "metadata.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    resp = result.response
    open(os.path.join(OUT, "draft.json"), "w", encoding="utf-8").write(resp.model_dump_json(indent=1))
    summary = {"attempt": 3, "model_pin": os.environ["EXTRACTION_LLM_MODEL"], "render": "REPLAYED from attempt 1 (rubric-read/rr1.0, 16 pages, $0.1472)",
               "wall_s": round(wall,1), "input_tokens": m.input_tokens, "output_tokens": m.output_tokens,
               "finish_reason": m.finish_reason, "llm_model": m.llm_model, "retry_count": m.retry_count,
               "warnings": result.warnings, "errors": result.errors, "prompt_version": meta.get("prompt_version")}
    def walk(q):
        return {"id": q.question_id, "total": str(q.total_points), "criteria": [(c.criterion_id, str(c.points), c.description[:50]) for c in q.criteria],
                "subs": [{"id": s.sub_question_id, "points": str(s.points),
                          "criteria": [(c.criterion_id, str(c.points), c.description[:50]) for c in s.criteria],
                          "subs": [{"id": t.sub_question_id, "points": str(t.points),
                                    "criteria": [(c.criterion_id, str(c.points), c.description[:50]) for c in t.criteria]} for t in s.sub_questions]}
                         for s in q.sub_questions]}
    summary["questions"] = [walk(q) for q in resp.questions]
    summary["total_points"] = str(resp.total_points)
    summary["selection_groups"] = [g.model_dump() for g in resp.selection_groups]
    summary["annotations"] = [(a.severity.value, a.annotation_type, a.target_id, a.expected, a.actual, a.message[:160]) for a in resp.annotations]
    summary["rescale"] = resp.extraction_metadata.get("rescale_to_exam")
    try:
        c = ContractCompiler().compile(resp, policy=NumericPolicy(), acknowledged_warnings=[a.id for a in resp.annotations])
        open(os.path.join(OUT, "contract.json"), "w", encoding="utf-8").write(c.model_dump_json(indent=1))
        summary["compile"] = f"OK total={c.total_points}"
    except Exception as e:
        summary["compile"] = f"BLOCKED: {type(e).__name__}: {str(e)[:700]}"
        # SIMULATED TEACHER FILL of every unresolved node
        unresolved = list((resp.extraction_metadata.get("rescale_to_exam") or {}).get("unresolved", []))
        filled = resp.model_copy(deep=True)
        for path in unresolved:
            node = _find(filled, path)
            _fill(node, is_question=("." not in path))
        filled.annotations = [a for a in filled.annotations if a.target_id not in unresolved]
        open(os.path.join(OUT, "draft_after_teacher_fill.json"), "w", encoding="utf-8").write(filled.model_dump_json(indent=1))
        try:
            c2 = ContractCompiler().compile(filled, policy=NumericPolicy(), acknowledged_warnings=[a.id for a in filled.annotations])
            open(os.path.join(OUT, "contract_after_teacher_fill.json"), "w", encoding="utf-8").write(c2.model_dump_json(indent=1))
            summary["compile_after_teacher_fill"] = f"OK total={c2.total_points} filled={unresolved}"
        except Exception as e2:
            summary["compile_after_teacher_fill"] = f"FAILED: {type(e2).__name__}: {str(e2)[:700]}"
    json.dump(summary, open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(json.dumps(summary, ensure_ascii=False, indent=1, default=str))
asyncio.run(main())
