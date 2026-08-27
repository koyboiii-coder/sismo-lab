from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import asyncpg

import alerts
import dedup
import intensity
import tsunami
from models import ParsedEvent

logger = logging.getLogger(__name__)


NOTIFY_CHANNEL = "seismic_events"


class IngestResult(str, Enum):
    """What `Writer.ingest` actually did with a report -- so connectors can
    log "wrote N" honestly instead of counting every item they handed over.
    A polled feed (CSN, USGS) re-sends its whole current list every cycle,
    so the vast majority of reports are UNCHANGED re-deliveries that never
    touch the DB."""

    CREATED = "created"      # opened a brand-new events cluster
    UPDATED = "updated"      # inserted a report into an existing cluster
    UNCHANGED = "unchanged"  # duplicate re-delivery, nothing written


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

    def __init__(
        self,
        dsn: str,
        dry_run: bool,
        home_lat: float = 0.0,
        home_lon: float = 0.0,
        command_timeout_s: float = 30.0,
        ntfy_url: str = "",
        ntfy_topic: str = "",
        ntfy_token: str = "",
        alerts_enabled: bool = True,
    ):
        self.dsn = dsn
        self.dry_run = dry_run
        self.home_lat = home_lat
        self.home_lon = home_lon
        self.command_timeout_s = command_timeout_s
        self.ntfy_url = ntfy_url
        self.ntfy_topic = ntfy_topic
        self.ntfy_token = ntfy_token
        # False for reprocess.py's replay Writer: it rebuilds `events` from
        # historical event_reports through this same create/recanonicalize
        # path, and without this it would re-fire a live ntfy notification
        # for every significant earthquake in the whole replayed history.
        # recompute.py never goes through Writer at all, so it needs no
        # equivalent guard.
        self.alerts_enabled = alerts_enabled
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
    ) -> IngestResult:
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
                            "source_mmi": parsed.source_mmi,
                        },
                        "payload": payload,
                    },
                    ensure_ascii=False,
                    default=str,
                )
            )
            return IngestResult.CREATED

        return await self.ingest(
            source, source_event_id, payload, parsed, datetime.now(timezone.utc)
        )

    async def ingest(
        self,
        source: str,
        source_event_id: str,
        payload: dict,
        parsed: ParsedEvent,
        received_at: datetime,
    ) -> IngestResult:
        """Core dedup/clustering path, shared by live ingestion
        (`write_report`, `received_at=now()`) and `reprocess.py` (replays
        history with each report's original `received_at`)."""
        assert self._pool is not None
        pending_notification: Optional[dict] = None
        result = IngestResult.UNCHANGED
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
                            return IngestResult.UNCHANGED
                        event_id = existing["event_id"]
                    else:
                        event_id = await self._find_cluster_match(conn, parsed)

                    if event_id is None:
                        pending_notification = await self._create_event(
                            conn, source, source_event_id, payload, parsed, received_at
                        )
                        result = IngestResult.CREATED
                    else:
                        previous = await conn.fetchrow(
                            "SELECT alert_level_sent, alert_sent_at FROM events "
                            "WHERE id = $1 FOR UPDATE",
                            event_id,
                        )
                        await self._insert_report(
                            conn, event_id, source, source_event_id, payload, parsed, received_at
                        )
                        pending_notification = await self._recanonicalize(
                            conn, event_id, source,
                            previous["alert_level_sent"], previous["alert_sent_at"],
                        )
                        result = IngestResult.UPDATED
        # Sent only after the transaction above has committed -- an ntfy
        # POST isn't transactional/revocable like the pg_notify() inside it
        # is, so it must never fire for a write that could still roll back.
        # See _send_alert and Writer.alerts_enabled.
        if pending_notification is not None:
            await self._send_alert(pending_notification)
        return result

    async def _create_event(
        self,
        conn: asyncpg.Connection,
        source: str,
        source_event_id: str,
        payload: dict,
        parsed: ParsedEvent,
        received_at: datetime,
    ) -> Optional[dict]:
        cluster_key = uuid.uuid4()
        est = intensity.estimate(
            latitude=parsed.latitude,
            longitude=parsed.longitude,
            depth_km=parsed.depth_km,
            magnitude=parsed.magnitude,
            home_lat=self.home_lat,
            home_lon=self.home_lon,
            rupture_vertices=parsed.rupture_geometry,
        )
        usgs_mmi = parsed.source_mmi if source == "USGS" else None

        # Brand-new event: nothing could have been notified for it yet, so
        # this only ever decides whether to send the *first* notification.
        new_level = alerts.alert_level(est.estimated_mmi)
        notify = alerts.should_notify(new_level, None)
        alert_level_sent = new_level if notify else None
        alert_sent_at = datetime.now(timezone.utc) if notify else None
        tsunami_flag = tsunami.possible_tsunami_source(
            parsed.latitude, parsed.longitude, parsed.depth_km, parsed.magnitude
        )

        event_id = await conn.fetchval(
            """
            INSERT INTO events (
                cluster_key, origin_time, latitude, longitude, depth_km,
                magnitude, magnitude_type, region, preferred_source,
                distance_km, estimated_pga, estimated_mmi, is_significant,
                usgs_reported_mmi, intensity_geometry_source,
                intensity_distance_saturated, alert_level_sent, alert_sent_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
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
            est.distance_km,
            est.estimated_pga,
            est.estimated_mmi,
            est.is_significant,
            usgs_mmi,
            est.geometry_source,
            est.distance_saturated,
            alert_level_sent,
            alert_sent_at,
        )
        await self._insert_report(
            conn, event_id, source, source_event_id, payload, parsed, received_at
        )
        await _notify(conn, "insert", cluster_key)
        logger.info(
            "[%s] new cluster %s: mag=%s depth=%s region=%s mmi=%s significant=%s "
            "geometry=%s saturated=%s alert=%s tsunami_flag=%s",
            source,
            cluster_key,
            parsed.magnitude,
            parsed.depth_km,
            parsed.region,
            est.estimated_mmi,
            est.is_significant,
            est.geometry_source,
            est.distance_saturated,
            new_level,
            tsunami_flag,
        )

        if not notify:
            return None
        return {
            "level": new_level,
            "magnitude": parsed.magnitude,
            "distance_km": est.distance_km,
            "mmi": est.estimated_mmi,
            "depth_km": parsed.depth_km,
            "region": parsed.region,
            "tsunami_flag": tsunami_flag,
        }

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
                magnitude, magnitude_type, region, source_mmi, rupture_geometry
            ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14::jsonb)
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
            parsed.source_mmi,
            json.dumps(parsed.rupture_geometry) if parsed.rupture_geometry is not None else None,
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
        self,
        conn: asyncpg.Connection,
        event_id: int,
        merged_source: str,
        previous_alert_level: Optional[str],
        previous_alert_sent_at: Optional[datetime],
    ) -> Optional[dict]:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (source)
                source, origin_time, latitude, longitude, depth_km,
                magnitude, magnitude_type, region, source_mmi, rupture_geometry
            FROM event_reports
            WHERE event_id = $1
            ORDER BY source, received_at DESC
            """,
            event_id,
        )
        snapshots = [dict(row) for row in rows]
        canonical = dedup.recompute_canonical(snapshots)
        usgs_mmi = next(
            (s["source_mmi"] for s in snapshots if s["source"] == "USGS" and s["source_mmi"] is not None),
            None,
        )
        # rupture_geometry is JSONB with no type codec registered on this
        # pool (unlike api/db.py), so asyncpg hands it back as raw JSON
        # text -- same reason usgs_mmi's sibling columns don't need this but
        # this one does.
        rupture_geometry_json = next(
            (
                s["rupture_geometry"]
                for s in snapshots
                if s["source"] == "USGS" and s["rupture_geometry"] is not None
            ),
            None,
        )
        rupture_vertices = (
            json.loads(rupture_geometry_json) if rupture_geometry_json is not None else None
        )
        est = intensity.estimate(
            latitude=canonical["latitude"],
            longitude=canonical["longitude"],
            depth_km=canonical["depth_km"],
            magnitude=canonical["magnitude"],
            home_lat=self.home_lat,
            home_lon=self.home_lon,
            rupture_vertices=rupture_vertices,
        )

        # CLAUDE.md rule 3: only resend when this revision crosses a tier
        # `previous_alert_level` hadn't already reached -- see
        # alerts.should_notify. A revision that stays at the same tier (or
        # drops, e.g. a magnitude downgrade) keeps the previously-sent
        # level/timestamp as-is rather than losing the record of what was
        # already sent.
        new_level = alerts.alert_level(est.estimated_mmi)
        notify = alerts.should_notify(new_level, previous_alert_level)
        alert_level_sent = new_level if notify else previous_alert_level
        alert_sent_at = datetime.now(timezone.utc) if notify else previous_alert_sent_at
        tsunami_flag = tsunami.possible_tsunami_source(
            canonical["latitude"], canonical["longitude"],
            canonical["depth_km"], canonical["magnitude"],
        )

        row = await conn.fetchrow(
            """
            UPDATE events SET
                origin_time = $2, latitude = $3, longitude = $4, depth_km = $5,
                magnitude = $6, magnitude_type = $7, region = $8, preferred_source = $9,
                distance_km = $10, estimated_pga = $11, estimated_mmi = $12,
                is_significant = $13, usgs_reported_mmi = $14,
                intensity_geometry_source = $15, intensity_distance_saturated = $16,
                alert_level_sent = $17, alert_sent_at = $18,
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
            est.distance_km,
            est.estimated_pga,
            est.estimated_mmi,
            est.is_significant,
            usgs_mmi,
            est.geometry_source,
            est.distance_saturated,
            alert_level_sent,
            alert_sent_at,
        )
        await _notify(conn, "update", row["cluster_key"])
        logger.info(
            "[%s] merged into cluster %s (sources=%s, rev=%s): "
            "mag=%s depth=%s lat=%s lon=%s region=%s preferred=%s mmi=%s significant=%s "
            "geometry=%s saturated=%s alert=%s (already_sent=%s) tsunami_flag=%s",
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
            est.estimated_mmi,
            est.is_significant,
            est.geometry_source,
            est.distance_saturated,
            new_level,
            previous_alert_level,
            tsunami_flag,
        )

        if not notify:
            return None
        return {
            "level": new_level,
            "magnitude": canonical["magnitude"],
            "distance_km": est.distance_km,
            "mmi": est.estimated_mmi,
            "depth_km": canonical["depth_km"],
            "region": canonical["region"],
            "tsunami_flag": tsunami_flag,
        }

    async def _send_alert(self, notification: dict) -> None:
        if not self.alerts_enabled:
            logger.debug(
                "[alerts] suppressed (alerts_enabled=False, e.g. reprocess.py "
                "replay): %s notification for mag=%s",
                notification["level"], notification["magnitude"],
            )
            return
        await alerts.send(
            ntfy_url=self.ntfy_url,
            ntfy_topic=self.ntfy_topic,
            ntfy_token=self.ntfy_token,
            **notification,
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
