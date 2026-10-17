"""The eval spend guard — since the owner rulings of 2026-10-17 (§4): eval and plan runs
spend on Claude-on-Vertex (GCP credits), and on the Anthropic direct API ONLY when the
owner rules a specific run onto it.

    python -m tests.eval_common.eval_key <module> [args...]            # Vertex (the default)
    python -m tests.eval_common.eval_key --direct <module> [args...]   # owner-ruled direct run
    e.g.  python -m tests.eval_common.eval_key tests.grading_eval_suite.runner --config X -k 2

The launcher, BEFORE any app module is imported (the environment outranks `.env`):
  * VERTEX (default): sets CLAUDE_ROUTE=vertex, so every Claude call the factory builds
    goes to Vertex on local ADC, and BLANKS ANTHROPIC_API_KEY, which shadows the key in
    `backend/.env` — a call that bypassed the route could not even authenticate.
  * DIRECT (`--direct`): sets CLAUDE_ROUTE=direct and loads ANTHROPIC_API_KEY from the
    dedicated EVAL key file (`backend/vivi-eval.env`, or `VIVI_EVAL_ENV_FILE`) — never
    from `backend/.env` and never the production key (Oct 6 §2). Refuses when the file or
    its key is missing. Used only for a run the owner ruled onto the direct API: the
    first is the §6b smoke (ruling "B, cap $3", 2026-10-17), after Google refused the
    Vertex quota.
  * marks the process with its route.
Every spend path calls `require_eval_key()` (the historical name, kept so every call site
and RUNLOG reference stays valid), which refuses unless the process was launched and the
route, the key and the mark agree. Nothing is printed.
"""
from __future__ import annotations

import os
import re
import runpy
import sys
from pathlib import Path

_MARK = "VIVI_EVAL_ROUTE"
EVAL_ENV_FILE = Path(__file__).resolve().parents[2] / "vivi-eval.env"


def load_eval_route() -> None:
    os.environ["CLAUDE_ROUTE"] = "vertex"
    os.environ["ANTHROPIC_API_KEY"] = ""          # shadows backend/.env: no direct call can authenticate
    os.environ[_MARK] = "vertex"


def _eval_key_from_file(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"STOP: the eval key file {path.name} is missing — a direct run never "
                         f"falls back to backend/.env. Nothing was spent.")
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*ANTHROPIC_API_KEY\s*=\s*(.+?)\s*$", line)
        if m:
            key = m.group(1).strip().strip('"').strip("'")
            if key:
                return key
    raise SystemExit(f"STOP: {path.name} carries no ANTHROPIC_API_KEY. Nothing was spent.")


def load_direct_route(path: Path | None = None) -> None:
    """[owner ruling B, 2026-10-17] the direct route, on the EVAL key only."""
    path = path or Path(os.environ.get("VIVI_EVAL_ENV_FILE") or EVAL_ENV_FILE)
    key = _eval_key_from_file(path)
    os.environ["CLAUDE_ROUTE"] = "direct"
    os.environ["ANTHROPIC_API_KEY"] = key         # the eval key, outranking backend/.env
    os.environ[_MARK] = "direct"


def require_eval_key() -> None:
    """Refuse a spend unless this process was launched, and its route, key and mark agree."""
    from app.agents.grader.llm_factory import claude_route
    from app.config import settings
    mark = os.environ.get(_MARK)
    key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else ""
    if mark == "direct":
        if claude_route() != "direct":
            raise SystemExit("STOP: launched for the direct route but CLAUDE_ROUTE is not direct. "
                             "Nothing was spent.")
        if not key or key != os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("STOP: the direct route must run on the eval key the launcher loaded. "
                             "Nothing was spent.")
        return
    if mark != "vertex":
        raise SystemExit("STOP: eval spend runs on Vertex unless the owner rules a run direct "
                         "(Oct 17 §4). Launch it through `python -m tests.eval_common.eval_key "
                         "<module> …`. Nothing was spent.")
    if claude_route() != "vertex":
        raise SystemExit("STOP: CLAUDE_ROUTE is not vertex — Anthropic direct eval spend is ZERO "
                         "(Oct 17 §4). Nothing was spent.")
    if key:
        raise SystemExit("STOP: an Anthropic API key is visible to this eval run — it must be blank "
                         "(Oct 17 §4). Nothing was spent.")


require_eval_route = require_eval_key


if __name__ == "__main__":
    args = sys.argv[1:]
    direct = bool(args) and args[0] == "--direct"
    if direct:
        args = args[1:]
    if not args:
        raise SystemExit(__doc__)
    load_direct_route() if direct else load_eval_route()
    module, sys.argv = args[0], args
    runpy.run_module(module, run_name="__main__", alter_sys=True)
