"""A-7 TEST HYGIENE (owner ruling, 2026-09-27) — the pinned pre-existing failures,
and what a GATE run must prove.

Two rules, both mechanical so no session can argue with them:

1. **Known failures are pinned BY NAME** in `tests/KNOWN_FAILURES.txt`. Each
   listed test is marked `xfail(strict=True)`: it may keep failing, and it cannot
   hide a NEW failure, because only the exact node id is excused. The day it
   passes it is an XPASS, which strict turns into a failure — so a name leaves the
   list exactly when its test passes, and never before.

2. **A gate run must reach the test DB.** With `VIVI_TEST_GATE=1`, the session
   probes the database before anything runs and stops (exit 3) if it cannot
   connect. Without it, an unreachable DB turns into hundreds of setup errors
   that read as "environment" and get waved through — which is how a real
   failure hides. A gate run also refuses a list entry that names no collected
   test (a renamed test must not leave an excuse behind).

Anything that fails and is not listed fails the run, as pytest always does.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pytest

KNOWN_FAILURES_PATH = Path(__file__).resolve().parent / "KNOWN_FAILURES.txt"
GATE_ENV = "VIVI_TEST_GATE"
GATE_DB_UNREACHABLE_EXIT = 3


def load_known_failures(path: Path = KNOWN_FAILURES_PATH) -> Dict[str, str]:
    """node id → its reason (the text after `#` on its line)."""
    known: Dict[str, str] = {}
    if not path.exists():
        return known
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        node, _, reason = line.partition("#")
        known[node.strip()] = reason.strip() or "pinned in KNOWN_FAILURES.txt"
    return known


def is_gate_run() -> bool:
    return os.environ.get(GATE_ENV, "").strip() not in ("", "0", "false", "False")


def mark_known_failures(items: Iterable, known: Dict[str, str]) -> List[str]:
    """Mark every listed item strict-xfail. Returns the node ids it marked."""
    marked: List[str] = []
    for item in items:
        reason = known.get(item.nodeid)
        if reason is not None:
            item.add_marker(pytest.mark.xfail(strict=True, reason=f"KNOWN_FAILURES.txt: {reason}"))
            marked.append(item.nodeid)
    return marked


def stale_entries(known: Dict[str, str], collected: Iterable[str],
                  narrowed_files: Iterable[str] = ()) -> List[str]:
    """Listed ids whose FILE was collected but which name no collected test.

    A file the command line narrowed to a single node (`file.py::test`) is not
    judged — its other tests were never meant to be collected.
    """
    collected = set(collected)
    files = {nid.split("::", 1)[0] for nid in collected}
    narrowed = set(narrowed_files)
    return sorted(nid for nid in known
                  if nid.split("::", 1)[0] in files
                  and nid.split("::", 1)[0] not in narrowed
                  and nid not in collected)


def probe_database(url: Optional[str], timeout_s: float = 20.0) -> Optional[str]:
    """None when `SELECT 1` succeeds on `url`; otherwise why it did not."""
    if not url:
        return "no DATABASE_URL"
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)

    async def _probe() -> None:
        import asyncpg
        conn = await asyncpg.connect(dsn, timeout=timeout_s, statement_cache_size=0)
        try:
            await conn.fetchval("SELECT 1")
        finally:
            await conn.close()

    try:
        asyncio.run(_probe())
    except Exception as exc:                      # the reason is the whole point
        return f"{type(exc).__name__}: {exc}"
    return None
