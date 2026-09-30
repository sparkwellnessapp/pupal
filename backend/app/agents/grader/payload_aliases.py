"""[AM-G17] Opaque aliases: the only ids a v6 model ever reads or writes.

Every v6 LLM payload (the planner, the verifier and the explainer) names things by
CALL-SCOPED ASCII aliases, `t1…` (terminals), `k1…` (compiler components), `m1…`
(deduction markers), `c1…` (checks). Code maps them back. The real ids carry Hebrew
labels (`q1.א.c0`), and a model that echoes one can return it altered. In G2 a
planner returned the Bengali letter `ব` in place of `א` (2026-09-28): a homoglyph,
which the romanisation recovery (CWV-6) cannot see, and a guess could not repair it
without inventing an id. An alias holds nothing to mis-copy, and it means nothing
outside the call that issued it.

An alias the table did not issue is OUTSIDE THE CLOSED WORLD: the caller drops that
item through `validator.strip_out_of_world` (the one closed-world function), with
no `rekey`, so there is no CWV-6 recovery. There is nothing to romanise. CWV-6
stays for v5, whose payloads carry real ids.

The table is a PURE function of what the call shows, in order, so the renderer and
the mapper each build it and get the same table, and a repair call reuses it.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

__all__ = ["ALIAS_PATTERN", "AliasTable"]

ALIAS_PATTERN = re.compile(r"^[a-z]\d+$")


class AliasTable:
    """Real id ↔ alias, for ONE call. `groups` is ((prefix, real ids in payload order), …):
    `(("t", terminal ids), ("k", component ids), ("m", marker ids))` gives t1…, k1…, m1….
    A real id appears once across all groups."""

    def __init__(self, groups: Iterable[Tuple[str, Sequence[str]]],
                 named: Optional[Mapping[str, str]] = None):
        """`named`: real ids the call never shows (the scope's own id), redacted to a
        fixed word in our messages and never issued as an alias."""
        self._alias: Dict[str, str] = {}
        self._real: Dict[str, str] = {}
        self._by_prefix: Dict[str, Tuple[str, ...]] = {}
        for prefix, ids in groups:
            if not re.fullmatch(r"[a-z]", prefix) or prefix in self._by_prefix:
                raise ValueError(f"alias prefix {prefix!r}: one lowercase letter, used once")
            issued = []
            for n, real in enumerate(ids, start=1):
                if real in self._alias:
                    raise ValueError(f"real id {real!r} aliased twice")
                a = f"{prefix}{n}"
                self._alias[real], self._real[a] = a, real
                issued.append(a)
            self._by_prefix[prefix] = tuple(issued)
        self._redact = {**{k: v for k, v in (named or {}).items() if k not in self._alias},
                        **self._alias}
        # longest first, so `q1.c10` is never read as `q1.c1` followed by «0»
        ids = sorted(self._redact, key=len, reverse=True)
        self._pattern = (re.compile(r"(?<![\w.])(" + "|".join(map(re.escape, ids)) + r")(?!\w)")
                         if ids else None)

    def alias(self, real: str) -> str:
        return self._alias[real]

    def real(self, alias: Optional[str]) -> Optional[str]:
        """The real id, or None for anything this table did not issue."""
        return self._real.get(alias) if alias is not None else None

    def issued(self, prefix: str) -> Tuple[str, ...]:
        return self._by_prefix.get(prefix, ())

    def redact(self, text: str) -> str:
        """`text` with every real id replaced by its alias: for OUR messages that go
        back to the model (the repair call's validator messages). The teacher's text
        and the model's output are never rewritten."""
        if self._pattern is None:
            return text
        return self._pattern.sub(lambda m: self._redact[m.group(1)], text)
