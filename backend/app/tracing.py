from typing import Callable

from langsmith import traceable

from . import config


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

