"""
Supersede and rebuild the live `ready` grading plans through the plan store.

    python -m app.scripts.rebuild_plans                     # dry run: list them, spend nothing
    python -m app.scripts.rebuild_plans --apply --max-usd 2

WHY THIS EXISTS (D-13, owner-authorized 2026-09-30). Until the D-13 fix the router
lost every monolith whose tool call carried `components` as a JSON STRING (Sonnet 5
does this), so plans built before it degraded those terminals' wording to the
compiler's own spans. The fix makes new builds route them; this rebuilds the plans
that were already `ready`.

WHAT IT DOES, per ready row, in plan order of `built_at`:
  * `plan_store.requeue_for_rebuild`: ONE transaction, ready → superseded (plan_json
    untouched) and a new queued row;
  * `plan_build_runner.run_plan_build(new_id)`: the ordinary build path (CAS claim,
    heartbeat, mark_ready | mark_failed) in THIS process.
Existing drafts keep the plans they were graded with: a draft carries its own copy.
A grade arriving mid-build waits on the live builder (OD-W3).

SPEND. A row is never STARTED once the spend so far plus the most expensive build
seen so far (a first build assumes $0.50) would pass `--max-usd`; the rows left are
listed, not dropped silently. A credit canary runs first (the standing rule).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from decimal import Decimal

from sqlalchemy import select

from app.database import engine, get_db_context
from app.models.grading_plan import GradingPlanRecord
from app.services import plan_store
from app.services.plan_build_runner import run_plan_build

logger = logging.getLogger("rebuild_plans")
FIRST_BUILD_ESTIMATE = Decimal("0.50")


def _canary() -> None:
    import anthropic
    from app.agents.plan_compiler.models import MODEL_CARDS, ROUTER_MODEL_KEY
    from app.config import settings
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key.get_secret_value())
    model = MODEL_CARDS[ROUTER_MODEL_KEY].model_id
    try:
        client.messages.create(model=model, max_tokens=1, messages=[{"role": "user", "content": "ok"}])
    except anthropic.APIStatusError as e:
        raise SystemExit(f"credit canary FAILED ({e.status_code}) — nothing rebuilt")
    print(f"credit canary: {model} OK")


async def _ready_rows():
    async with get_db_context() as db:
        rows = (await db.execute(select(GradingPlanRecord)
                                 .where(GradingPlanRecord.status == "ready")
                                 .order_by(GradingPlanRecord.built_at))).scalars().all()
        return [(r.id, r.rubric_id, r.contract_sha256, r.contract_version, r.wording_source,
                 r.router_model, r.cost_usd, r.built_at) for r in rows]


async def main(apply: bool, max_usd: Decimal) -> None:
    rows = await _ready_rows()
    print(f"{len(rows)} ready plan(s):")
    for rid, rubric, sha, _v, wording, router, cost, built in rows:
        print(f"  {rid} rubric={rubric} sha={sha[:12]} wording={wording} router={router} "
              f"cost=${cost} built={built:%Y-%m-%d %H:%M}")
    if not apply:
        print("dry run: nothing rebuilt (pass --apply)")
        return
    _canary()
    spent, seen_max, skipped = Decimal("0"), None, []
    for rid, rubric, sha, version, *_ in rows:
        estimate = FIRST_BUILD_ESTIMATE if seen_max is None else seen_max
        if spent + estimate > max_usd:
            skipped.append(rid)
            continue
        async with get_db_context() as db:
            new = await plan_store.requeue_for_rebuild(db, sha, rubric_id=rubric, contract_version=version)
        await run_plan_build(new.id)
        async with get_db_context() as db:
            built = await db.get(GradingPlanRecord, new.id)
            status, wording, cost = built.status, built.wording_source, built.cost_usd or Decimal("0")
            err = (built.error_message or "")[:200]
        spent += cost
        seen_max = cost if seen_max is None else max(seen_max, cost)
        print(f"  rebuilt {rid} → {new.id}: {status} · wording={wording} · ${cost}"
              + (f" · {err}" if err else ""))
    print(f"spent ${spent} of ${max_usd}" + (f" · NOT started (cap): {skipped}" if skipped else ""))
    await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max-usd", type=Decimal, default=Decimal("2"))
    args = ap.parse_args()
    asyncio.run(main(args.apply, args.max_usd))
