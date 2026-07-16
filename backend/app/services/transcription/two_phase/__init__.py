"""
The two-phase transcription pipeline core — production home.

Phase 1 (perception): page images -> verbatim per-page text.
Phase 2 (interpretation): flat page text + exam spec -> per-(question, sub) answers.
Plus the deterministic corrector and the shared instrumentation.

HISTORY: this code was developed and validated inside the transcription eval
suite (tests/transcription_eval_suit/), which now imports it back from here via
thin shims — one definition of the pipeline, exercised by both production and
the golden-set harness (CLAUDE.md "one concept, one place"). The eval-only
pieces (ground truths, scoring, gate, model registry/prices, runner) stay in
the suite.

Model resolution is INJECTED (`ResolveModel`): the suite resolves registry keys
via its models_registry; production resolves via its own settings-owned map.
"""
