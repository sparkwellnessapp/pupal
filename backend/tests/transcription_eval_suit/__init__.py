"""Transcription eval suite.

Layer 1 (pure, offline, runs in `pytest -q`):
    ground_truth.py   — canonical GT format + parser
    critical_tokens.py — subject profile + grading-critical signature extractor
    scoring.py        — difflib accuracy, coverage/segmentation, critical-token metric

Later layers (API-touching, run opt-in only):
    instrument / vlm_provider adapters / pipelines / runner / report / gate.

benchmarks/ holds canonical ground-truth markdown; pdfs/ holds source PDFs.
Both contain real student data — see the integration notes; long-term they move
to a private bucket and are git-ignored.
"""
