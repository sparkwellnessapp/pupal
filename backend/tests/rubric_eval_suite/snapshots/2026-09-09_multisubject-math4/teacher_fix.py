"""Zero-cost half of the Phase 2.t snapshot: take the REAL draft off disk and play the
teacher's move at the rubric gate — resolve each node the post-pass flagged — then compile.

This is what the gate claim rests on: the extraction + post-pass put the exam on 100 with every
number on the grid, and the ONLY thing standing between the draft and a Contract is the teacher's
own arithmetic, which she resolves in the editor. No provider is called here."""
import io, json, sys
from decimal import Decimal

sys.path.insert(0, ".")
from app.schemas.ontology_types import (
    Criterion, ExtractRubricResponse, NumericPolicy,
)
from app.services.contract_compiler import ContractCompiler
from app.services.docx_v3 import rescale_to_exam as rx

OUT = sys.argv[1]
draft = ExtractRubricResponse.model_validate_json(io.open(f"{OUT}/draft.json", encoding="utf-8").read())
unresolved = list(draft.extraction_metadata["rescale_to_exam"]["unresolved"])
report = {"unresolved": unresolved, "fixes": []}


def leaves(node, path):
    """Every scoring leaf under a node, with its path."""
    kids = getattr(node, "sub_questions", None) or []
    if kids:
        for k in kids:
            yield from leaves(k, f"{path}.{k.sub_question_id}")
    else:
        yield path, node


def fix(node, path, total: Decimal):
    """Her decision, played mechanically: split `total` over the children in the proportions she
    wrote (equally where she wrote nothing), on the grid, and give a bare leaf one criterion."""
    kids = getattr(node, "sub_questions", None) or []
    if kids:
        w = [c.points if c.points > 0 else Decimal(1) for c in kids]
        for c, p in zip(kids, rx.largest_remainder(w, total)):
            fix(c, f"{path}.{c.sub_question_id}", p)
        node_total_set(node, total)
        return
    if node.criteria:
        w = [c.points if c.points > 0 else Decimal(1) for c in node.criteria]
        pts = rx.largest_remainder(w, total)
        node.criteria = [c.model_copy(update={"points": p}) for c, p in zip(node.criteria, pts)]
    else:
        node.criteria = [Criterion(criterion_id=f"{path}.c0", index=0,
                                   description="פתרון מלא (הניקוד נקבע על ידי המורה)", points=total)]
    node_total_set(node, total)


def node_total_set(node, total: Decimal):
    if hasattr(node, "total_points"):
        node.total_points = total
    else:
        node.points = total


for path in unresolved:
    qid = path.split(".")[0]
    q = next(x for x in draft.questions if x.question_id == qid)
    if path == qid:
        node, total = q, q.total_points
    else:
        node = q
        for seg in path.split(".")[1:]:
            node = next(s for s in node.sub_questions if s.sub_question_id == seg)
        total = node.points
    fix(node, path, Decimal(str(total)))
    report["fixes"].append({"node": path, "held_at": str(total)})

draft.annotations = [a for a in draft.annotations if a.target_id not in unresolved]
io.open(f"{OUT}/draft_after_teacher_fix.json", "w", encoding="utf-8").write(draft.model_dump_json(indent=1))
try:
    c = ContractCompiler().compile(draft, policy=NumericPolicy(),
                                   acknowledged_warnings=[a.id for a in draft.annotations])
    io.open(f"{OUT}/contract.json", "w", encoding="utf-8").write(c.model_dump_json(indent=1))
    report["compile"] = f"OK total={c.total_points}"
    report["question_totals"] = {q.question_id: str(q.total_points) for q in c.questions}
    report["selection_groups"] = [g.model_dump(mode="json") for g in c.selection_groups]
except Exception as e:
    report["compile"] = f"FAILED: {type(e).__name__}: {str(e)[:900]}"
json.dump(report, io.open(f"{OUT}/teacher_fix_report.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(json.dumps(report, ensure_ascii=False, indent=1)[:1500])
