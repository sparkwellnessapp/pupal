"""The eval spend guard — since the owner rulings of 2026-10-17 (§4): eval and plan runs
spend ONLY on Claude-on-Vertex (GCP credits), and NEVER on the Anthropic direct API.

    python -m tests.eval_common.eval_key <module> [args...]
    e.g.  python -m tests.eval_common.eval_key tests.grading_eval_suite.runner --config X -k 2

The launcher, BEFORE any app module is imported (the environment outranks `.env`):
  * sets CLAUDE_ROUTE=vertex, so every Claude call the factory builds goes to Vertex
    (`llm_factory.claude_route`), on local ADC;
  * BLANKS ANTHROPIC_API_KEY, which shadows the key in `backend/.env` — so a call that
    somehow bypassed the route could not even authenticate on the direct API;
  * marks the process as launched.
Every spend path calls `require_eval_key()` (the historical name, kept so every call site
and RUNLOG reference stays valid), which refuses unless all three hold. Nothing is printed.

History: Oct 6 §2 ran eval spend on a dedicated Anthropic key in `backend/vivi-eval.env`;
Oct 17 §4 set Anthropic direct eval spend to ZERO, so that file is no longer read.
"""
from __future__ import annotations

import os
import runpy
import sys

_MARK = "VIVI_EVAL_ROUTE"


def load_eval_route() -> None:
    os.environ["CLAUDE_ROUTE"] = "vertex"
    os.environ["ANTHROPIC_API_KEY"] = ""          # shadows backend/.env: no direct call can authenticate
    os.environ[_MARK] = "vertex"


def require_eval_key() -> None:
    """Refuse a spend unless this process was launched on the Vertex route with no Anthropic key."""
    from app.agents.grader.llm_factory import claude_route
    from app.config import settings
    if os.environ.get(_MARK) != "vertex":
        raise SystemExit("STOP: eval spend runs ONLY on Vertex (Oct 17 §4). Launch it through "
                         "`python -m tests.eval_common.eval_key <module> …`. Nothing was spent.")
    if claude_route() != "vertex":
        raise SystemExit("STOP: CLAUDE_ROUTE is not vertex — Anthropic direct eval spend is ZERO "
                         "(Oct 17 §4). Nothing was spent.")
    if settings.anthropic_api_key and settings.anthropic_api_key.get_secret_value():
        raise SystemExit("STOP: an Anthropic API key is visible to this eval run — it must be blank "
                         "(Oct 17 §4). Nothing was spent.")


require_eval_route = require_eval_key


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    load_eval_route()
    module, sys.argv = sys.argv[1], sys.argv[1:]
    runpy.run_module(module, run_name="__main__", alter_sys=True)
