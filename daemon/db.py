from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import asyncpg

import dedup
from models import ParsedEvent

logger = logging.getLogger(__name__)


NOTIFY_CHANNEL = "seismic_events"


async def _notify(conn: asyncpg.Connection, kind: str, cluster_key: uuid.UUID) -> None:
    """Tells api/ a cluster was created or revised, so its SSE stream can
    push it instead of polling. Payload is deliberately just the id, not the
    full event -- see api/notifier.py for why. Issued inside the caller's
    transaction, so Postgres only delivers it once that transaction commits
    and the row is actually visible to the listener's re-fetch."""
    await conn.execute(
        "SELECT pg_notify($1, $2)",
        NOTIFY_CHANNEL,
        json.dumps({"type": kind, "cluster_key": str(cluster_key)}),
    )


def _parsed_unchanged(existing_row: asyncpg.Record, parsed: ParsedEvent) -> bool:
    """Compares parsed fields, not the raw payload: sources re-send the
    same report with only a bookkeeping timestamp bumped (CSN's
    FechaUpdate is when gael.cloud last scraped sismologia.cl, USGS's
    `updated` and EMSC's `lastupdate` are similar agency-side bookkeeping)
    and none of that should look like a revision."""
    return all(
        existing_row[field] == getattr(parsed, field) for field in dedup.CANONICAL_FIELDS
    )


class Writer:
    """Persists connector reports, deduplicating and clustering them into
    `events` rows as they arrive.

    Two kinds of duplicates are handled:

    - Same-source re-delivery: a connector reports the same
      (source, source_event_id) again, identical (by parsed fields,
      ignoring bookkeeping-only fields like a source's last-scraped/
      last-updated timestamp) or revised. See `_parsed_unchanged`.
    - Cross-source clustering: a brand-new (source, source_event_id) that
      describes a physical earthquake already tracked from another source
      (or the same source under a different id, e.g. CSN's hash-derived
      ids). See `dedup.matches_cluster`.

    All connector tasks share one Writer/one asyncio.Lock, so the
    read-decide-write sequence below never interleaves between them --
    without that, two reports for the same brand-new earthquake arriving
    around the same time could each fail to find the other and create two
    separate clusters.
    """

    def __init__(self, dsn: str, dry_run: bool, command_timeout_s: float = 30.0):
        self.dsn = dsn
        self.dry_run = dry_run
        self.command_timeout_s = command_timeout_s
        self._pool: Optional[asyncpg.Pool] = None
        self._write_lock = asyncio.Lock()

    async def connect(self) -> None:
        if self.dry_run:
            return
        # command_timeout bounds every query run through this pool. Without
        # it, a query blocked server-side on a Postgres lock (e.g. the
        # SELECT ... FOR UPDATE below) can await forever -- and since that
        # await happens while holding `_write_lock`, it would freeze every
        # other connector too, silently, with no exception and no more log
        # lines. Rule 4 (graceful degradation) requires every source to keep
        # making progress even if Postgres itself misbehaves.
        self._pool = await asyncpg.create_pool(
            self.dsn, min_size=1, max_size=5, command_timeout=self.command_timeout_s
        )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    async def write_report(
        self,
        source: str,
        source_event_id: str,
        payload: dict,
        parsed: ParsedEvent,
    ) -> None:
        if self.dry_run:
            print(
                json.dumps(
                    {
                        "source": source,
                        "source_event_id": source_event_id,
                        "parsed": {
                            "origin_time": parsed.origin_time.isoformat(),
                            "latitude": parsed.latitude,
                            "longitude": parsed.longitude,
                            "depth_km": parsed.depth_km,
                            "magnitude": parsed.magnitude,
                            "magnitude_type": parsed.magnitude_type,
                            "region": parsed.region,
                            "preferred_source": parsed.preferred_source,
                        },
                        "payload": payload,
                    },
                    ensure_ascii=False,
                    default=str,
                )
            )
            return

        await self.ingest(
            source, source_event_id, payload, parsed, datetime.now(timezone.utc)
        )

    async def ingest(
        self,
        source: str,
        source_event_id: str,
        payload: dict,
        parsed: ParsedEvent,
        received_at: datetime,
    ) -> None:
        """Core dedup/clustering path, shared by live ingestion
        (`write_report`, `received_at=now()`) and `reprocess.py` (replays
        history with each report's original `received_at`)."""
        assert self._pool is not None
        async with self._write_lock:
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    existing = await conn.fetchrow(
                        f"""
                        SELECT event_id, {", ".join(dedup.CANONICAL_FIELDS)}
                        FROM event_reports
                        WHERE source = $1 AND source_event_id = $2
                        ORDER BY received_at DESC
                        LIMIT 1
                        """,
                        source,
                        source_event_id,
                    )

                    if existing is not None:
                        if _parsed_unchanged(existing, parsed):
                            logger.debug(
                                "[%s] duplicate report %s (parsed fields unchanged "
                                "since last report, ignoring bookkeeping-only diffs "
                                "like FechaUpdate/lastupdate/updated)",
                                source,
                                source_event_id,
                            )
                            return
                        event_id = existing["event_id"]
                    else:
                        event_id = await self._find_cluster_match(conn, parsed)

                    if event_id is None:
                        await self._create_event(
                            conn, source, source_event_id, payload, parsed, received_at
                        )
                        return

                    await conn.fetchrow(
                        "SELECT id FROM events WHERE id = $1 FOR UPDATE", event_id
                    )
                    await self._insert_report(
                        conn, event_id, source, source_event_id, payload, parsed, received_at
                    )
                    await self._recanonicalize(conn, event_id, source)

    async def _create_event(
        self,
        conn: asyncpg.Connection,
        source: str,
        source_event_id: str,
        payload: dict,
        parsed: ParsedEvent,
        received_at: datetime,
    ) -> None:
        cluster_key = uuid.uuid4()
        event_id = await conn.fetchval(
            """
            INSERT INTO events (
                cluster_key, origin_time, latitude, longitude, depth_km,
                magnitude, magnitude_type, region, preferred_source
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id
            """,
            cluster_key,
            parsed.origin_time,
            parsed.latitude,
            parsed.longitude,
            parsed.depth_km,
            parsed.magnitude,
            parsed.magnitude_type,
            parsed.region,
            parsed.preferred_source,
        )
        await self._insert_report(
            conn, event_id, source, source_event_id, payload, parsed, received_at
        )
        await _notify(conn, "insert", cluster_key)
        logger.info(
            "[%s] new cluster %s: mag=%s depth=%s region=%s",
            source,
            cluster_key,
            parsed.magnitude,
            parsed.depth_km,
            parsed.region,
        )

    async def _insert_report(
        self,
        conn: asyncpg.Connection,
        event_id: int,
        source: str,
        source_event_id: str,
        payload: dict,
        parsed: ParsedEvent,
        received_at: datetime,
    ) -> None:
        await conn.execute(
            """
            INSERT INTO event_reports (
                event_id, source, source_event_id, payload, received_at,
                origin_time, latitude, longitude, depth_km,
                magnitude, magnitude_type, region
            ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9, $10, $11, $12)
            """,
            event_id,
            source,
            source_event_id,
            json.dumps(payload, ensure_ascii=False, default=str),
            received_at,
            parsed.origin_time,
            parsed.latitude,
            parsed.longitude,
            parsed.depth_km,
            parsed.magnitude,
            parsed.magnitude_type,
            parsed.region,
        )

    async def _find_cluster_match(
        self, conn: asyncpg.Connection, parsed: ParsedEvent
    ) -> Optional[int]:
        rows = await conn.fetch(
            """
            SELECT id, origin_time, latitude, longitude, magnitude, region
            FROM events
            WHERE origin_time BETWEEN $1 AND $2
            """,
            parsed.origin_time - timedelta(seconds=dedup.TIME_WINDOW_S),
            parsed.origin_time + timedelta(seconds=dedup.TIME_WINDOW_S),
        )
        best_id: Optional[int] = None
        best_dt: Optional[float] = None
        for row in rows:
            if not dedup.matches_cluster(parsed, row):
                continue
            dt = abs((row["origin_time"] - parsed.origin_time).total_seconds())
            if best_dt is None or dt < best_dt:
                best_id, best_dt = row["id"], dt
        return best_id

    async def _recanonicalize(
        self, conn: asyncpg.Connection, event_id: int, merged_source: str
    ) -> None:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (source)
                source, origin_time, latitude, longitude, depth_km,
                magnitude, magnitude_type, region
            FROM event_reports
            WHERE event_id = $1
            ORDER BY source, received_at DESC
            """,
            event_id,
        )
        snapshots = [dict(row) for row in rows]
        canonical = dedup.recompute_canonical(snapshots)

        row = await conn.fetchrow(
            """
            UPDATE events SET
                origin_time = $2, latitude = $3, longitude = $4, depth_km = $5,
                magnitude = $6, magnitude_type = $7, region = $8, preferred_source = $9,
                revision = revision + 1, updated_at = NOW()
            WHERE id = $1
            RETURNING cluster_key, revision
            """,
            event_id,
            canonical["origin_time"],
            canonical["latitude"],
            canonical["longitude"],
            canonical["depth_km"],
            canonical["magnitude"],
            canonical["magnitude_type"],
            canonical["region"],
            canonical["preferred_source"],
        )
        await _notify(conn, "update", row["cluster_key"])
        logger.info(
            "[%s] merged into cluster %s (sources=%s, rev=%s): "
            "mag=%s depth=%s lat=%s lon=%s region=%s preferred=%s",
            merged_source,
            row["cluster_key"],
            sorted(s["source"] for s in snapshots),
            row["revision"],
            canonical["magnitude"],
            canonical["depth_km"],
            canonical["latitude"],
            canonical["longitude"],
            canonical["region"],
            canonical["preferred_source"],
        )

    async def mark_source_ok(self, source: str) -> None:
        if self.dry_run:
            return
        assert self._pool is not None
        await self._pool.execute(
            """
            INSERT INTO source_health (source, last_success_at, consecutive_failures)
            VALUES ($1, NOW(), 0)
            ON CONFLICT (source) DO UPDATE SET
                last_success_at = NOW(),
                consecutive_failures = 0
            """,
            source,
        )

    async def mark_source_error(self, source: str, error: str) -> None:
        if self.dry_run:
            logger.warning("[%s] error: %s", source, error)
            return
        assert self._pool is not None
        await self._pool.execute(
            """
            INSERT INTO source_health (source, last_error_at, last_error, consecutive_failures)
            VALUES ($1, NOW(), $2, 1)
            ON CONFLICT (source) DO UPDATE SET
                last_error_at = NOW(),
                last_error = $2,
                consecutive_failures = source_health.consecutive_failures + 1
            """,
            source,
            error,
        )
