from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from notifier import health_compact

logger = logging.getLogger(__name__)
router = APIRouter()

# Also doubles as the client's disconnect-detection heartbeat: the tablet
# should never go longer than this without *something* arriving on the
# stream, per CLAUDE.md's API section.
HEARTBEAT_INTERVAL_S = 15.0


def _format_sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/stream")
async def stream(request: Request):
    db = request.app.state.db
    broadcaster = request.app.state.broadcaster

    async def event_generator():
        queue = broadcaster.subscribe()
        try:
            # Prime the client with current health immediately instead of
            # making it wait up to HEARTBEAT_INTERVAL_S for the first byte.
            yield _format_sse("health", await health_compact(db.pool))
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event, data = await asyncio.wait_for(
                        queue.get(), timeout=HEARTBEAT_INTERVAL_S
                    )
                    yield _format_sse(event, data)
                except asyncio.TimeoutError:
                    yield _format_sse("health", await health_compact(db.pool))
        finally:
            broadcaster.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Disables response buffering on Caddy/nginx-style reverse
            # proxies (infra fase 4) -- irrelevant today but harmless.
            "X-Accel-Buffering": "no",
        },
    )
