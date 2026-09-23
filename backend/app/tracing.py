from contextlib import contextmanager
from typing import Callable, Iterator
from uuid import UUID

from langsmith import traceable, tracing_context

from . import config

#: The tag every run carrying a student's work wears, so a person reading the
#: LangSmith project can tell those runs apart from rubric-only work.
STUDENT_DATA_TAG = "student-data"


@contextmanager
def student_data_run(*, graded_test_id: UUID | str,
                     transcription_id: UUID | str) -> Iterator[None]:
    """[OD-B2] Every LangSmith run that carries a STUDENT'S WORK is stamped
    with the two ids an erasure request starts from.

    A grading trace holds the student's transcribed answers verbatim (the
    grader's and the feedback writer's prompts), and tracing is ON in
    production. LangSmith cannot find "Dana's traces" by name — only by
    metadata — so without these ids an erasure request has no way in. With
    them it is one call (the runbook in docs/PURGE_CENSUS.md, row 8):

        POST /api/v1/runs/delete
        {"session_id": <project id>, "metadata": {"graded_test_id": "<id>"}}

    Everything invoked inside the block inherits the metadata and the tag —
    LangChain runnables through `langchain_core`'s callback configuration,
    `@traceable` functions directly, and child asyncio tasks (the grader's
    per-scope `gather`) because the context rides contextvars. Work that sees
    only the RUBRIC (plan compilation, extraction) stays outside the block.
    """
    with tracing_context(
        metadata={"graded_test_id": str(graded_test_id),
                  "transcription_id": str(transcription_id)},
        tags=[STUDENT_DATA_TAG],
    ):
        yield


def trace_if_enabled(
    flag_attr: str,
    *,
    name: str,
    run_type: str = "chain",
) -> Callable:
    """
    Conditionally wrap a function with langsmith.traceable based on app.config.

    Behavior:
    - If config.langsmith_interface_trace is False → always returns the original function.
    - If master flag is True and config.<flag_attr> is True → wraps with traceable(name, run_type).
    - If master flag is True and config.<flag_attr> is False → returns the original function.

    This allows fine-grained control over which LLM nodes are traced while keeping
    the default behavior simple and safe.
    """

    def decorator(fn: Callable) -> Callable:
        master_enabled = getattr(config, "langsmith_interface_trace", False)
        node_enabled = getattr(config, flag_attr, False)

        if not (master_enabled and node_enabled):
            # Tracing disabled for this node – no-op decorator.
            return fn

        return traceable(name=name, run_type=run_type)(fn)

    return decorator

