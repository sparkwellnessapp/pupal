"""The standing credit canary: one call per model a run will use, on the route the run spends on.

    python -m tests.eval_common.eval_key tests.eval_common.canary claude-sonnet-5-5 claude-opus-5-5

Since 2026-10-17 (§4) that route is Claude on Vertex (GCP credits, local ADC): the logical id
is mapped through `llm_factory.VERTEX_MODEL_IDS`. Refuses (exit 2) on the first failure —
quota, enablement or credit — and nothing else in the run starts. Never prints a credential.
"""
from __future__ import annotations

import sys

from tests.eval_common.eval_key import require_eval_key


def canary(model_id: str) -> str:
    """One `max_tokens=1` call to `model_id` (a LOGICAL id) on the Vertex route; returns the
    served model id. Raises SystemExit(2) on any provider error."""
    require_eval_key()
    import anthropic
    from anthropic import AnthropicVertex

    from app.agents.grader.llm_factory import vertex_model_id
    from app.config import settings
    client = AnthropicVertex(region=settings.claude_vertex_region,
                             project_id=settings.claude_vertex_project or settings.google_cloud_project,
                             max_retries=0, timeout=60)
    try:
        r = client.messages.create(model=vertex_model_id(model_id), max_tokens=1,
                                   messages=[{"role": "user", "content": "ok"}])
    except anthropic.APIStatusError as e:
        reason = "quota" if e.status_code == 429 else ("not served here" if e.status_code == 404
                                                      else type(e).__name__)
        print(f"canary FAILED {model_id} on vertex:{settings.claude_vertex_region}: {e.status_code} {reason}")
        raise SystemExit(2)
    print(f"canary OK {model_id} on vertex:{settings.claude_vertex_region} (served {r.model})")
    return r.model


def main(models) -> None:
    for m in models:
        canary(m)


if __name__ == "__main__":
    main(sys.argv[1:] or ["claude-sonnet-5-5"])
