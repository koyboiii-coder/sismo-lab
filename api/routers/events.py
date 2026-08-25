from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from notifier import EVENT_FIELDS, serialize_event

router = APIRouter()


@router.get("/events")
async def list_events(
    request: Request,
    since: Optional[datetime] = Query(None, description="ISO8601, filters origin_time >="),
    limit: int = Query(50, ge=1, le=500),
):
    pool = request.app.state.db.pool
    if since is not None:
        rows = await pool.fetch(
            f"SELECT {EVENT_FIELDS} FROM events "
            "WHERE origin_time >= $1 ORDER BY origin_time DESC LIMIT $2",
            since,
            limit,
        )
    else:
        rows = await pool.fetch(
            f"SELECT {EVENT_FIELDS} FROM events ORDER BY origin_time DESC LIMIT $1",
            limit,
        )
    return [serialize_event(row) for row in rows]


@router.get("/events/{cluster_key}")
async def get_event(cluster_key: UUID, request: Request):
    pool = request.app.state.db.pool
    event_row = await pool.fetchrow(
        f"SELECT id, {EVENT_FIELDS} FROM events WHERE cluster_key = $1", cluster_key
    )
    if event_row is None:
        raise HTTPException(status_code=404, detail="event not found")

    report_rows = await pool.fetch(
        "SELECT source, source_event_id, payload, received_at "
        "FROM event_reports WHERE event_id = $1 ORDER BY received_at DESC",
        event_row["id"],
    )
    return {
        "event": serialize_event(event_row),
        "reports": [
            {
                "source": r["source"],
                "source_event_id": r["source_event_id"],
                "payload": r["payload"],
                "received_at": r["received_at"].isoformat(),
            }
            for r in report_rows
        ],
    }
