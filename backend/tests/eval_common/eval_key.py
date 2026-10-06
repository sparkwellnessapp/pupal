"""The eval-only Anthropic key (Oct 6 rulings §2) — the ONE key eval and plan runs spend on.

    python -m tests.eval_common.eval_key <module> [args...]
    e.g.  python -m tests.eval_common.eval_key tests.grading_eval_suite.runner --config X -k 2

The launcher reads `backend/vivi-eval.env` (gitignored; override the path with
VIVI_EVAL_ENV) and puts its ANTHROPIC_API_KEY into the process environment BEFORE
any app module is imported — the environment outranks `.env`, so Settings resolves
the eval key — then runs the module. Every spend path calls `require_eval_key()`,
which refuses unless the key Settings resolved IS the one loaded here (compared by
hash; the key is never printed, logged or written anywhere).
"""
from __future__ import annotations

import hashlib
import os
import runpy
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
_MARK = "VIVI_EVAL_KEY_SHA256"


def _env_path() -> Path:
    return Path(os.environ.get("VIVI_EVAL_ENV") or BACKEND / "vivi-eval.env")


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_eval_key() -> None:
    path = _env_path()
    if not path.exists():
        raise SystemExit(f"STOP: {path} not found — eval and plan runs spend ONLY on the "
                         f"eval key (Oct 6 rulings §2). Nothing was spent.")
    key = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("ANTHROPIC_API_KEY="):
            key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        raise SystemExit(f"STOP: {path} has no ANTHROPIC_API_KEY — nothing was spent.")
    os.environ["ANTHROPIC_API_KEY"] = key
    os.environ[_MARK] = _sha(key)


def require_eval_key() -> None:
    """Refuse a spend unless Settings resolved the key the launcher loaded."""
    from app.config import settings
    want = os.environ.get(_MARK)
    have = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else ""
    if not want or _sha(have) != want:
        raise SystemExit("STOP: this run would spend on a key other than the eval key. Launch it "
                         "through `python -m tests.eval_common.eval_key <module> …`.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    load_eval_key()
    module, sys.argv = sys.argv[1], sys.argv[1:]
    runpy.run_module(module, run_name="__main__", alter_sys=True)
