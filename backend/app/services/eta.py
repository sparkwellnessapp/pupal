"""
Batch ETA — two stages, and never a constant (PR-G8, §1.5).

The teacher plans her evening around this number, so it may only be as
confident as its inputs:

  * **unknown** — no latency profile for this model. The client says «עוד רגע»
    rather than a figure. Inventing one here would be a confident guess about
    the single thing she is waiting on.
  * **first_landing** — nothing has landed yet, so the estimate comes from the
    model's measured p50 scaled by WAVE COUNT. The profile was measured on
    6-scope fixtures, which is two waves at MAX_CONCURRENT_SCOPES=5, so it is
    normalised by that: a 15-scope test is three waves and must not be quoted
    the same number as a 6-scope one.
  * **remaining** — once tests start landing, THIS batch's observed durations
    beat any profile: same provider, same evening, same queue depth. p90, not
    the mean, because the number should cover the slow tail she actually waits
    through.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

from app.agents.grader.grader import MAX_CONCURRENT_SCOPES

# The fixture cohort the latency profile is measured on: 6 scopes = 2 waves.
_PROFILE_WAVES = math.ceil(6 / MAX_CONCURRENT_SCOPES)


def _p90(values: List[float]) -> float:
    ordered = sorted(values)
    idx = math.ceil(0.9 * len(ordered)) - 1
    return ordered[max(0, min(idx, len(ordered) - 1))]


def estimate_eta(profile_p50: Optional[float],
                 scope_count: int,
                 landed_durations: List[float]) -> Dict[str, object]:
    """-> {"kind": "first_landing"|"remaining"|"unknown", "seconds": int|None}."""
    if landed_durations:
        return {"kind": "remaining", "seconds": int(round(_p90(landed_durations)))}

    if not profile_p50:
        return {"kind": "unknown", "seconds": None}

    waves = math.ceil(max(scope_count, 1) / MAX_CONCURRENT_SCOPES)
    return {"kind": "first_landing",
            "seconds": int(round(profile_p50 * waves / _PROFILE_WAVES))}
