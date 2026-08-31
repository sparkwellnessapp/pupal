"""
Batch ETA — two stages, and never a constant (PR-G8, §1.5).

The teacher plans her evening around this number, so it may only be as
confident as its inputs:

  * **unknown** — no latency profile for this model. The client says «עוד רגע»
    rather than a figure. Inventing one here would be a confident guess about
    the single thing she is waiting on.
  * **first_landing** — nothing has landed yet, so the estimate comes from the
    model's measured p50 scaled by WAVE COUNT. The profile was measured on
    6-scope fixtures, so it is normalised by however many waves THAT is at
    the current concurrency: a 15-scope test is more waves than a 6-scope one
    and must not be quoted the same number.

    [PR-G3] Both halves read the concurrency dial at CALL time. This assumes
    the profile was measured at the dial's current value — so **re-measure
    the profile whenever the dial moves**, which is exactly what G3(b) does.
    A profile measured 5-wide and divided 16-wide would quote a number
    describing a system that no longer exists.
  * **remaining** — once tests start landing, THIS batch's observed durations
    beat any profile: same provider, same evening, same queue depth. p90, not
    the mean, because the number should cover the slow tail she actually waits
    through.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

from app.agents.grader.grader import effective_scope_concurrency

# The fixture cohort the latency profile is measured on.
_PROFILE_SCOPES = 6


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

    scopes = max(scope_count, 1)
    waves = math.ceil(scopes / effective_scope_concurrency(scopes))
    profile_waves = math.ceil(
        _PROFILE_SCOPES / effective_scope_concurrency(_PROFILE_SCOPES))
    return {"kind": "first_landing",
            "seconds": int(round(profile_p50 * waves / profile_waves))}
