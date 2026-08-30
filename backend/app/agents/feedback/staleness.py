"""
Is this feedback still describing the grade it was written for? (PR-G4)

Staleness is DERIVED, never a flag someone must remember to set: the text
carries the hash of the verdict vector it was generated from, and anything that
changes that vector makes it stale by construction.

OD-G4.1 — the basis is the ORDERED EFFECTIVE VERDICT VECTOR and nothing else.
Points are derived from verdicts, so hashing them too would make the text stale
when nothing it depends on moved. Quotes likewise: the feedback says what was
credited and what was missing, not which span was cited.
"""
from __future__ import annotations

import hashlib
from typing import Iterable, Sequence


def basis_hash(checks: Sequence) -> str:
    """sha256 over `check_id=verdict` pairs, in order. Order is part of the
    basis: the same verdicts in a different sequence describe a different
    answer, and the prose follows the sequence."""
    joined = "|".join(f"{c.check_id}={c.verdict}" for c in checks)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def is_stale(text, checks: Sequence) -> bool:
    """True when the verdicts have moved since this text was written."""
    if text is None or not getattr(text, "basis_hash", None):
        return False          # nothing was claimed; nothing can be stale
    return text.basis_hash != basis_hash(checks)


def flatten_checks(scope_outcome) -> Iterable:
    """The scope's checks in document order — the vector the hash is taken over."""
    for criterion in scope_outcome.criterion_outcomes:
        for leaf in (criterion.sub_criterion_outcomes or [criterion]):
            for check in (leaf.checks or []):
                yield check
