from __future__ import annotations

from fastapi import APIRouter, Request

from notifier import health_detail

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    pool = request.app.state.db.pool
    return await health_detail(pool)
