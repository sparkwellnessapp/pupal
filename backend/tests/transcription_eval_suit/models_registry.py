"""
SHIM — moved to the shared eval home: tests/eval_common/models_registry.py
(ONE registry serving both eval suites — transcription + rubric — so a model's
identity, price and tier are a single fact across their results artifacts).
This re-export preserves the suite's historical import surface: configs,
runner, pipelines and CallRecords are unchanged.
"""
from tests.eval_common.models_registry import (  # noqa: F401
    AS_OF,
    MODELS,
    ModelSpec,
    spec,
)
