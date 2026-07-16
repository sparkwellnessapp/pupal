"""
SHIM — moved to production: app/services/transcription/two_phase/parsing.py
(the suite exercises the exact code production runs; one definition).
This re-export preserves the suite's historical import surface.
"""
from app.services.transcription.two_phase.parsing import *  # noqa: F401,F403
from app.services.transcription.two_phase.parsing import _FENCE_RE  # noqa: F401
