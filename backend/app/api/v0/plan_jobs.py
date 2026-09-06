"""
The Cloud Tasks target for plan builds (PLAN_production_wiring.md §8).

One internal route, no public surface: the teacher never learns that plans
exist (ruling W-3). Same discipline as the other /internal targets — the build
runs INSIDE this request (CPU guaranteed), the runner's first statement is the
queued→building CAS so a redelivery is a no-op, and the handler answers 200 on
every authorised call because a non-2xx would redeliver work the row already
accounts for.
"""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from ...services.cloud_tasks_service import verify_task_request

logger = logging.getLogger(__name__)

internal_router = APIRouter(prefix="/internal/plan-jobs", tags=["internal"])


@internal_router.post("/{job_id}/run", include_in_schema=False)
async def run_plan_build_task(job_id: UUID, request: Request) -> dict:
    reason = verify_task_request(request)
    if reason is not None:
        logger.warning("internal_plan_build_rejected job_id=%s reason=%s", job_id, reason)
        raise HTTPException(status_code=403, detail="Forbidden")

    from ...services.plan_build_runner import run_plan_build

    ran = await run_plan_build(job_id)
    return {"job_id": str(job_id), "ran": ran}
