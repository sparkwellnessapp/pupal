"""Shared transcription package.

Holds code imported by BOTH the production pipeline and the eval harness.
Layer 1 adds `normalize`. Later layers add the VLM provider interface and the
bounded-concurrency scheduler here.
"""
