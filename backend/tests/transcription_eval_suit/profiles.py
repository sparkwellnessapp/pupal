"""
profiles.py — the critical-token PROFILE REGISTRY: name -> CriticalProfile.

Same role `models_registry.py` plays for models: one place that rots, and a
loud failure on an unknown key. A fixture's exam spec names its profile; the
scoring engine never knows a subject (CLAUDE.md §3.3), it just scores whatever
profile it is handed.

WHY THIS IS A SEPARATE MODULE (and not a dict inside critical_tokens.py):
`critical_tokens.py` is on the §17.7 STOP list by name, alongside scoring.py
and normalize.py — it defines what the instrument measures. A registry that
merely *names* profiles is plumbing, not measurement, so it lives here and
`critical_tokens.py` keeps a zero-line diff. Adding a key here changes nothing
for any existing fixture; editing JAVA_BAGRUT's contents would, and that stays
an owner-gated change in the file it belongs to.
"""
from __future__ import annotations

from .critical_tokens import JAVA_BAGRUT, CriticalProfile

# The name a spec/manifest omits. Every fixture authored before per-fixture
# exams existed resolves to exactly this, which is why the lift is a no-op for
# the seed corpus.
DEFAULT_PROFILE = "java_bagrut"

PROFILES: dict[str, CriticalProfile] = {
    "java_bagrut": JAVA_BAGRUT,
}


def profile(name: str | None = None) -> CriticalProfile:
    """Resolve a profile name. Unknown names raise — never silently default,
    which would score a fixture under a vocabulary nobody chose."""
    key = name or DEFAULT_PROFILE
    try:
        return PROFILES[key]
    except KeyError:
        raise ValueError(
            f"unknown critical-token profile {key!r}; known profiles: "
            f"{sorted(PROFILES)}"
        ) from None
