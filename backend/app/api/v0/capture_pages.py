"""
The page and save endpoints, defined ONCE and mounted on both capture routers
(§6.5, §6.6). Each router hands in its own actor dependency — the teacher's
(her session or a batch-scoped capture session) or the student's (link token
+ device secret, link OPEN). The service enforces scope with that actor, so
the same function serves both modes and neither can reach the other's rows.

Each router also hands in its own submission VIEW: the student's is narrower
(no student state — she is never told her submission is a conflict, D1).
"""
from __future__ import annotations

from typing import Awaitable, Callable, Type
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...schemas.capture import (
    PageCreateRequest, PageCreateResponse, PageOrderRequest, PagePatchRequest, PageView,
    ResetCornersRequest, SaveResponse,
)
from ...services.batch_ingest import enqueue_transcription_or_mark_failed
from ...services.capture import submissions as svc


def add_page_routes(router: APIRouter, actor_dep: Callable, *, view_model: Type[BaseModel],
                    view: Callable[..., Awaitable[BaseModel]]) -> None:

    @router.get("/submissions/{submission_id}", response_model=view_model)
    async def get_submission(submission_id: UUID, actor=Depends(actor_dep),
                             db: AsyncSession = Depends(get_db)):
        return await view(db, await svc.load_submission(db, actor, submission_id))

    @router.post("/submissions/{submission_id}/pages", response_model=PageCreateResponse,
                 status_code=201)
    async def create_page(submission_id: UUID, body: PageCreateRequest, actor=Depends(actor_dep),
                          db: AsyncSession = Depends(get_db)):
        new = await svc.create_page(db, actor, submission_id, body.content_type)
        await db.commit()
        return PageCreateResponse(page_id=new.page.id, position=new.page.position,
                                  upload_url=new.upload_url, required_headers=new.required_headers)

    @router.post("/submissions/{submission_id}/pages/{page_id}/uploaded", response_model=PageView)
    async def page_uploaded(submission_id: UUID, page_id: UUID, actor=Depends(actor_dep),
                            db: AsyncSession = Depends(get_db)):
        page = await svc.confirm_upload(db, actor, submission_id, page_id)
        await db.commit()
        return await svc.page_view(page)

    @router.patch("/submissions/{submission_id}/pages/{page_id}", response_model=PageView)
    async def patch_page(submission_id: UUID, page_id: UUID, body: PagePatchRequest,
                         actor=Depends(actor_dep), db: AsyncSession = Depends(get_db)):
        page = await svc.patch_page(db, actor, submission_id, page_id,
                                    corners=body.corners, rotation=body.rotation)
        await db.commit()
        return await svc.page_view(page)

    @router.post("/submissions/{submission_id}/pages/{page_id}/reset-corners",
                 response_model=PageView)
    async def reset_corners(submission_id: UUID, page_id: UUID, body: ResetCornersRequest,
                            actor=Depends(actor_dep), db: AsyncSession = Depends(get_db)):
        page = await svc.reset_corners(db, actor, submission_id, page_id, body.to)
        await db.commit()
        return await svc.page_view(page)

    @router.delete("/submissions/{submission_id}/pages/{page_id}", status_code=204)
    async def delete_page(submission_id: UUID, page_id: UUID, actor=Depends(actor_dep),
                          db: AsyncSession = Depends(get_db)):
        await svc.delete_page(db, actor, submission_id, page_id)
        await db.commit()
        return Response(status_code=204)

    @router.put("/submissions/{submission_id}/order", status_code=204)
    async def reorder(submission_id: UUID, body: PageOrderRequest, actor=Depends(actor_dep),
                      db: AsyncSession = Depends(get_db)):
        await svc.reorder(db, actor, submission_id, body.page_ids)
        await db.commit()
        return Response(status_code=204)

    @router.post("/submissions/{submission_id}/save", response_model=SaveResponse)
    async def save(submission_id: UUID, actor=Depends(actor_dep),
                   db: AsyncSession = Depends(get_db)):
        """SCN-6: once this answers 200 every later failure is recoverable by
        a retry, without the student — the version and its job are durable."""
        saved = await svc.save(db, actor, submission_id)
        await db.commit()
        await db.close()                    # pooler discipline before the enqueue
        await enqueue_transcription_or_mark_failed(saved.job_id)
        return SaveResponse(submission_id=saved.submission_id,
                            version_no=saved.version.version_no,
                            saved_at=saved.version.created_at.isoformat(),
                            page_count=saved.page_count)
