"""
OD-B2 — every LangSmith run carrying a student's work is stamped with the ids
an erasure request starts from (`graded_test_id`, `transcription_id`) and the
`student-data` tag.

Three layers, none of which touches the network:

  1. the context itself carries both ids and the tag, and nothing leaks out
     of the block;
  2. a REAL LangChain call made inside the block reaches the LangSmith tracer
     with that metadata, and the tag reaches every callback — the exact path
     `langchain_core` uses when tracing is on in production;
  3. STRUCTURALLY, the three places that send a student's work to a model —
     the grader and the feedback writer in `grading_runner._do_grade`, and
     `/feedback/regenerate` — make those calls INSIDE the block, and plan
     resolution (rubric-only work) does not.

The live half — that LangSmith stores the metadata and that
`POST /api/v1/runs/delete` by that metadata erases the run — was proven once
against a dedicated dev project and is recorded in docs/PURGE_CENSUS.md.
"""
from __future__ import annotations

import ast
import pathlib
from uuid import uuid4

from langsmith.run_helpers import get_tracing_context

from app.tracing import STUDENT_DATA_TAG, student_data_run

APP = pathlib.Path(__file__).resolve().parents[2] / "app"


def test_the_context_carries_both_ids_and_the_tag_and_nothing_leaks_out():
    g, t = uuid4(), uuid4()
    with student_data_run(graded_test_id=g, transcription_id=t):
        ctx = get_tracing_context()
        assert ctx["metadata"] == {"graded_test_id": str(g), "transcription_id": str(t)}
        assert STUDENT_DATA_TAG in ctx["tags"]
    after = get_tracing_context()
    assert not (after["metadata"] or {}).get("graded_test_id")
    assert STUDENT_DATA_TAG not in (after["tags"] or [])


def test_a_langchain_call_inside_the_block_reaches_the_tracer_with_the_ids(monkeypatch):
    """Tracing ON, as in production, with the LangSmith tracer replaced by a
    recorder: the metadata `langchain_core` hands the tracer is the metadata
    LangSmith stores."""
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    import langchain_core.tracers.langchain as lc_tracers

    seen_by_tracer: list[dict] = []

    class RecordingTracer(BaseCallbackHandler):
        """Stands in for LangSmith's tracer: records what it was built with
        and sends nothing."""
        def __init__(self, *args, metadata=None, tags=None, **kwargs):
            self.metadata = dict(metadata or {})
            self.tags = list(tags or [])
            seen_by_tracer.append({"metadata": self.metadata, "tags": self.tags})

        def copy_with_metadata_defaults(self, *, metadata=None, tags=None, **kwargs):
            # `langchain_core` derives a per-call tracer from the configured
            # one; whatever defaults it merges in are recorded too.
            merged = {**(metadata or {}), **self.metadata}
            seen_by_tracer.append({"metadata": merged, "tags": self.tags + list(tags or [])})
            return self

    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key-never-sent")
    monkeypatch.setattr(lc_tracers, "LangChainTracer", RecordingTracer)

    tags_on_start: list[list[str]] = []

    class Tags(BaseCallbackHandler):
        def on_chat_model_start(self, serialized, messages, *, tags=None, **kwargs):
            tags_on_start.append(list(tags or []))

    g, t = uuid4(), uuid4()
    model = FakeListChatModel(responses=["ok"])
    with student_data_run(graded_test_id=g, transcription_id=t):
        assert model.invoke("the student's answer", config={"callbacks": [Tags()]}).content == "ok"

    assert seen_by_tracer, "tracing was on, yet no LangSmith tracer was configured"
    # The ids are PRESENT; `langchain_core` adds its own model-description
    # defaults beside them, which LangSmith stores too.
    stamped = seen_by_tracer[-1]["metadata"]
    assert stamped["graded_test_id"] == str(g) and stamped["transcription_id"] == str(t)
    assert STUDENT_DATA_TAG in seen_by_tracer[-1]["tags"]
    assert tags_on_start and STUDENT_DATA_TAG in tags_on_start[-1]


def _calls_inside_student_block(path: pathlib.Path, callee: str) -> list[bool]:
    """For every call to `<something>.<callee>(` or `<callee>(` in the file:
    is it lexically inside `with student_data_run(...)`?"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    def inside(node):
        while node in parents:
            node = parents[node]
            if isinstance(node, (ast.With, ast.AsyncWith)) and any(
                    isinstance(i.context_expr, ast.Call)
                    and getattr(i.context_expr.func, "id", getattr(i.context_expr.func, "attr", ""))
                    == "student_data_run"
                    for i in node.items):
                return True
        return False

    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if name == callee:
                out.append(inside(node))
    return out


def test_every_call_that_sends_a_students_work_to_a_model_is_inside_the_block():
    runner = APP / "services" / "grading_runner.py"
    grading = APP / "api" / "v0" / "grading.py"
    for path, callee in ((runner, "grade"), (runner, "attach_feedback"), (grading, "generate")):
        found = _calls_inside_student_block(path, callee)
        assert found, f"no call to {callee}( in {path.name} — the pin names nothing"
        assert all(found), f"a call to {callee}( in {path.name} is outside student_data_run"


def test_rubric_only_work_is_not_tagged_as_student_data():
    """Plan resolution sees only the rubric; tagging it would bury the runs an
    erasure request is looking for among runs that hold no student at all."""
    runner = APP / "services" / "grading_runner.py"
    found = _calls_inside_student_block(runner, "resolve_plan_for_grade")
    assert found and not any(found)
