"""
Code shared by the eval suites (transcription + rubric).

One definition of a model's identity, price, capability and tier
(models_registry.py). Suite-specific things — ground truths, scorers, gates,
runners — stay in their suites; only facts that must not fork live here.
Production deliberately keeps its own narrow settings-owned model map
(app/services/transcription/two_phase/__init__.py's ruling: the registry
stays eval-side).
"""
