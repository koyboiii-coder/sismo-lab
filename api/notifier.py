"""Bridges Postgres LISTEN/NOTIFY (channel `seismic_events`, see
daemon/db.py) to the SSE stream in routers/stream.py.

The daemon's NOTIFY payload is deliberately small -- {"type", "cluster_key"}
-- not the full event, both to stay well under Postgres's ~8000 byte NOTIFY
payload limit and so there is exactly one place (here) that decides what an
event looks like on the wire. On notify we re-fetch the row: NOTIFY only
fires at COMMIT, so the row is guaranteed visible by the time we query it.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

import asyncpg

logger = logging.getLogger(__name__)

SEISMIC_CHANNEL = "seismic_events"

EVENT_FIELDS = """
    cluster_key, origin_time, latitude, longitude, depth_km, magnitude,
    magnitude_type, region, distance_km, estimated_pga, estimated_mmi,
    preferred_source, is_significant, alert_sent_at, alert_level_sent,
    first_seen_at, updated_at, revision, intensity_geometry_source,
    intensity_distance_saturated
"""

SOURCES = ("CSN", "USGS", "EMSC")
STATUS_UNKNOWN = "unknown"
STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"


class Broadcaster:
    """Fan-out from one Postgres listener to N SSE clients. Each subscriber
    gets its own queue so one slow/stuck client can't block delivery to the
    others."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def publish(self, event: str, data: Any) -> None:
        for queue in list(self._subscribers):
            queue.put_nowait((event, data))


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt is not None else None


def serialize_event(row: asyncpg.Record) -> dict:
    return {
        "cluster_key": str(row["cluster_key"]),
        "origin_time": _iso(row["origin_time"]),
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "depth_km": row["depth_km"],
        "magnitude": row["magnitude"],
        "magnitude_type": row["magnitude_type"],
        "region": row["region"],
        "distance_km": row["distance_km"],
        "estimated_pga": row["estimated_pga"],
        "estimated_mmi": row["estimated_mmi"],
        # What estimated_mmi's distance was actually based on ('finite_fault'
        # | 'wells_coppersmith' | None) and, for the latter, whether its
        # worst-case depth floor was hit -- see
        # daemon/intensity.py:rupture_distance_km. The dashboard should
        # qualify estimated_mmi (e.g. "MMI VII estimado -- geometria de
        # falla desconocida") whenever intensity_distance_saturated is true,
        # rather than showing it as a precise figure.
        "intensity_geometry_source": row["intensity_geometry_source"],
        "intensity_distance_saturated": row["intensity_distance_saturated"],
        "preferred_source": row["preferred_source"],
        "is_significant": row["is_significant"],
        "alert_sent_at": _iso(row["alert_sent_at"]),
        # 'silent' | 'full' | None -- which notification tier (daemon/
        # alerts.py) was actually sent for this event, if any. See
        # infra/postgres/init/005_alerts.sql.
        "alert_level_sent": row["alert_level_sent"],
        "first_seen_at": _iso(row["first_seen_at"]),
        "updated_at": _iso(row["updated_at"]),
        "revision": row["revision"],
    }


async def fetch_event_by_cluster_key(pool: asyncpg.Pool, cluster_key: str) -> Optional[dict]:
    row = await pool.fetchrow(
        f"SELECT {EVENT_FIELDS} FROM events WHERE cluster_key = $1", cluster_key
    )
    return serialize_event(row) if row is not None else None


async def fetch_health_rows(pool: asyncpg.Pool) -> dict[str, asyncpg.Record]:
    rows = await pool.fetch(
        "SELECT source, last_success_at, last_error_at, last_error, "
        "consecutive_failures FROM source_health"
    )
    return {row["source"]: row for row in rows}


def _status(row: Optional[asyncpg.Record]) -> str:
    if row is None:
        return STATUS_UNKNOWN
    return STATUS_DEGRADED if row["consecutive_failures"] > 0 else STATUS_OK


async def health_compact(pool: asyncpg.Pool) -> dict[str, str]:
    """Shape used on the SSE `health` event: {"CSN": "ok", ...}."""
    rows = await fetch_health_rows(pool)
    return {source: _status(rows.get(source)) for source in SOURCES}


async def health_detail(pool: asyncpg.Pool) -> dict[str, dict]:
    """Shape used by GET /api/health -- compact status plus the bookkeeping
    behind it."""
    rows = await fetch_health_rows(pool)
    detail = {}
    for source in SOURCES:
        row = rows.get(source)
        detail[source] = {
            "status": _status(row),
            "last_success_at": _iso(row["last_success_at"]) if row else None,
            "last_error_at": _iso(row["last_error_at"]) if row else None,
            "last_error": row["last_error"] if row else None,
            "consecutive_failures": row["consecutive_failures"] if row else 0,
        }
    return detail


def make_notify_callback(pool: asyncpg.Pool, broadcaster: Broadcaster):
    """asyncpg calls this synchronously on every NOTIFY, so it can't be a
    coroutine itself -- it just schedules the real handler."""

    async def _handle(payload: str) -> None:
        try:
            message = json.loads(payload)
            event = await fetch_event_by_cluster_key(pool, message["cluster_key"])
        except Exception:
            logger.exception("failed to handle NOTIFY payload: %s", payload)
            return
        if event is None:
            logger.warning(
                "NOTIFY for cluster_key with no matching event row: %s", payload
            )
            return
        broadcaster.publish("seismic", {"type": message["type"], "event": event})

    def _on_notify(connection, pid, channel, payload) -> None:
        asyncio.create_task(_handle(payload))

    return _on_notify
