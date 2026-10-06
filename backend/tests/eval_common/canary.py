"""The standing credit canary: one token per model a run will use, on the EVAL key.

    python -m tests.eval_common.eval_key tests.eval_common.canary claude-sonnet-5-5 claude-haiku-4-5

Refuses (exit 2) on the first failure; nothing else in the run starts. Never prints the key.
"""
from __future__ import annotations

import sys

from tests.eval_common.eval_key import require_eval_key


def main(models) -> None:
    require_eval_key()
    import anthropic
    from app.config import settings
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key.get_secret_value())
    for m in models:
        try:
            r = client.messages.create(model=m, max_tokens=1, messages=[{"role": "user", "content": "ok"}])
        except anthropic.APIStatusError as e:
            print(f"canary FAILED {m}: {e.status_code} {'credit' if 'credit balance' in str(e) else type(e).__name__}")
            sys.exit(2)
        print(f"canary OK {m} (served {r.model})")


if __name__ == "__main__":
    main(sys.argv[1:] or ["claude-sonnet-5-5"])
