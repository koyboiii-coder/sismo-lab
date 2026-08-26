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
    significant: Optional[bool] = Query(
        None,
        description=(
            "Filters is_significant = true. Used by web/ to pull the 90-day "
            "'felt near home' memory panel without paging through every "
            "small Chilean event in that window -- see "
            "web/src/lib/api.ts:fetchSignificantEvents."
        ),
    ),
):
    pool = request.app.state.db.pool
    conditions = []
    params: list = []
    if since is not None:
        params.append(since)
        conditions.append(f"origin_time >= ${len(params)}")
    if significant:
        conditions.append("is_significant = true")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)
    rows = await pool.fetch(
        f"SELECT {EVENT_FIELDS} FROM events {where} "
        f"ORDER BY origin_time DESC LIMIT ${len(params)}",
        *params,
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
