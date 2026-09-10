"""
The per-document transcription wall budget — one clock, one owner.

WHY THIS EXISTS (the 2026-09-10 incident, and it is the whole rationale).
Five documents were submitted together. Four landed in 47-78s. One took ~600s
and left exactly ONE line in the logs:

    [hobby_tvshow.dan_basiuk.pdf] strike_check page 2 vote 1 failed;
    casting no ranges

That line was written 521.8s after the job was claimed. Subtracting a normal
P1 (~40s) leaves ~481s = 240s call timeout + jittered backoff + 240s, i.e. the
scheduler's ONE transport retry on the global `timeout_s`. It was spent by the
STRIKE CHECK — an optional pass with a 7.8s median whose own failure handling
is "keep the page exactly as P1 produced it". It blocked a teacher's document
for eight minutes and then discarded its own result, exactly as designed.

  «checker must never sink the doc» was implemented as "never RAISE".
  It was not implemented as "never DELAY".

THE RULE, carried over from PR-2 (`docx_v3/pipeline.py`, where the same defect
family was killed for extraction): a retry budget is only meaningful when ONE
owner holds it and ONE deadline bounds it. Retry layers that cannot see each
other MULTIPLY — transcription had three (the scheduler's transport retry, the
parse re-request in `_call_and_parse`, and the doc-level re-run in
`transcription_job_runner`), and 2x2x2x240s = 1,920s against a 900s Cloud Run
request timeout. So the deadline lives HERE, and the phases ASK it instead of
each keeping a private clock.

THE ENFORCEMENT SHAPE IS DELIBERATE, and it is what makes a short budget safe.
A Budget NEVER cancels a call in flight. It does two things only:

    clamp(t)      -- a call may not be given a timeout that outlives the budget
    can_start(t)  -- a phase REFUSES TO BEGIN work it cannot finish

so a document dies at a PHASE BOUNDARY, never mid-upload. A weak-uplink P1
chunk that starts inside the budget keeps its full patience (the 240s that was
earned by measurement on real congested uplinks, 2026-08-12); the budget stops
the NEXT thing, not the one already paying for itself. This is PR-2's shape:
the deadline is checked at entry points, and the remaining budget is passed
down as a per-call timeout.

WHO REACTS HOW, and why the two differ:

  * OPTIONAL passes (strike check, readers) treat exhaustion as their own
    already-defined degradation -- skip, keep the text. Nothing is lost that
    they were not free to lose anyway.
  * ESSENTIAL phases (P1, P2) raise `BudgetExceeded`, which the job runner
    lands as a FAILED, retryable row. Transcription feeds grading, which is a
    CONSUMING path (CLAUDE.md 3.5a: consuming paths refuse loudly), and a
    partial transcription presented as complete would be a silent repair (FC).
    The source PDF is in GCS, so the retry costs the teacher nothing.

`Budget(None)` is UNBOUNDED and IS the eval path -- PR-2's own seam. The eval
suite measures model behaviour, not Cloud Run's request timeout, so
`check_goal.sh` is untouched by construction.
"""
from __future__ import annotations

import time
from typing import Callable, Optional


class BudgetExceeded(Exception):
    """An ESSENTIAL phase could not start inside the document's wall budget.

    Terminal for the run: the job runner lands it as a failed, retryable row
    (never a partial draft -- see this module's docstring)."""


class Budget:
    """A monotonic wall budget for one document. Cheap, stateless past `_t0`,
    and safe to share across the phases of a single run.

    `total_s=None` means unbounded: `remaining_s()` is None, `clamp` returns
    its argument untouched and `can_start`/`require` always pass.
    """

    __slots__ = ("_total_s", "_t0", "_time")

    def __init__(
        self,
        total_s: Optional[float],
        *,
        time_fn: Callable[[], float] = time.monotonic,
        started_at: Optional[float] = None,
    ):
        # `started_at` lets the CALLER anchor the clock before this object
        # exists -- the job runner starts counting at the CAS claim, so the
        # GCS download and the rubric read are inside the budget rather than
        # assumed away (PR-2: pre-work is MEASURED, never assumed).
        self._total_s = total_s
        self._time = time_fn
        self._t0 = started_at if started_at is not None else time_fn()

    @property
    def bounded(self) -> bool:
        return self._total_s is not None

    @property
    def total_s(self) -> Optional[float]:
        return self._total_s

    def elapsed_s(self) -> float:
        return self._time() - self._t0

    def remaining_s(self) -> Optional[float]:
        if self._total_s is None:
            return None
        return self._total_s - self.elapsed_s()

    def clamp(self, timeout_s: float) -> float:
        """The largest timeout this call may be given. Never returns <= 0: an
        essential phase has already called `require` by the time it gets here,
        and handing a provider a negative timeout would be a different bug than
        the one we are reporting."""
        remaining = self.remaining_s()
        if remaining is None:
            return timeout_s
        return max(1.0, min(timeout_s, remaining))

    def can_start(self, needs_s: float) -> bool:
        remaining = self.remaining_s()
        return remaining is None or remaining >= needs_s

    def require(self, needs_s: float, what: str) -> None:
        """Refuse to begin `what` when the budget cannot cover it."""
        if self.can_start(needs_s):
            return
        raise BudgetExceeded(
            f"transcription budget exhausted before {what}: "
            f"{self.elapsed_s():.0f}s elapsed of a {self._total_s:.0f}s budget "
            f"(needed {needs_s:.0f}s more)"
        )
