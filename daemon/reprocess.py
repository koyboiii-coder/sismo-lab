"""Rebuilds `events` from scratch by replaying every historical row in
`event_reports`, in original arrival order, through the live dedup and
clustering algorithm in `db.Writer`.

Use this to clean up events created before the dedup fix (one `events`
row per raw report, no clustering) and to validate the algorithm against
data already accumulated in production.

DESTRUCTIVE: loads all of `event_reports` into memory, then TRUNCATEs
`events` (which cascades to `event_reports`), then reinserts every
report through `Writer.ingest`, preserving each report's original
`received_at` so the rebuilt history stays accurate. The raw payloads
are never modified or dropped -- only the derived `events` clusters and
the per-report parsed-field columns are recomputed.

Usage:
    python reprocess.py --dry-run     # just report how many rows exist
    python reprocess.py               # prompts for confirmation
    python reprocess.py --yes         # skips the confirmation prompt
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

import asyncpg

from config import load_config
from connectors import csn, emsc, usgs
from db import Writer
from models import ParsedEvent

logger = logging.getLogger(__name__)


def _reparse(source: str, payload: dict) -> ParsedEvent:
    """Re-derive parsed fields from a report's raw payload. Needed for
    rows written before the parsed-field columns existed on
    event_reports (see infra/postgres/init/002_dedup.sql)."""
    if source == "CSN":
        return csn.parse(payload)
    if source == "EMSC":
        properties = payload.get("data", {}).get("properties", {})
        return emsc.parse(properties)
    if source == "USGS":
        return usgs.parse(payload)
    raise ValueError(f"unknown source: {source}")


async def _load_reports(conn: asyncpg.Connection) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT source, source_event_id, payload, received_at,
               origin_time, latitude, longitude, depth_km,
               magnitude, magnitude_type, region, source_mmi, rupture_geometry
        FROM event_reports
        ORDER BY received_at ASC, id ASC
        """
    )
    return [dict(row) for row in rows]


async def main(dry_run: bool, assume_yes: bool) -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    config = load_config()
    conn = await asyncpg.connect(config.database_url)
    try:
        reports = await _load_reports(conn)
        logger.info("loaded %d historical report(s)", len(reports))
        if not reports:
            logger.info("nothing to reprocess")
            return

        if dry_run:
            logger.info("dry-run: not touching the database")
            return

        if not assume_yes:
            answer = input(
                f"This will TRUNCATE `events` (cascades to `event_reports`) "
                f"and rebuild {len(reports)} report(s) from scratch. "
                f"Type 'yes' to continue: "
            )
            if answer.strip().lower() != "yes":
                logger.info("aborted")
                return

        await conn.execute("TRUNCATE TABLE events RESTART IDENTITY CASCADE")
        logger.info("truncated events/event_reports, replaying history...")

        writer = Writer(
            config.database_url,
            dry_run=False,
            home_lat=config.home_lat,
            home_lon=config.home_lon,
            # This replays potentially months of history through the same
            # create/recanonicalize path live ingestion uses -- without
            # this, every significant historical earthquake would fire a
            # real ntfy notification again. See db.Writer.alerts_enabled.
            alerts_enabled=False,
        )
        await writer.connect()
        try:
            for report in reports:
                payload = json.loads(report["payload"])
                if report["origin_time"] is None:
                    # Pre-migration row: parsed-field columns were never
                    # backfilled, so re-derive them from the raw payload.
                    parsed = _reparse(report["source"], payload)
                else:
                    parsed = ParsedEvent(
                        origin_time=report["origin_time"],
                        latitude=report["latitude"],
                        longitude=report["longitude"],
                        depth_km=report["depth_km"],
                        magnitude=report["magnitude"],
                        magnitude_type=report["magnitude_type"],
                        region=report["region"],
                        preferred_source=report["source"],
                        source_mmi=report["source_mmi"],
                        # No jsonb codec on this plain asyncpg.connect(), same
                        # as payload above -- comes back as raw JSON text.
                        rupture_geometry=(
                            json.loads(report["rupture_geometry"])
                            if report["rupture_geometry"] is not None
                            else None
                        ),
                    )
                await writer.ingest(
                    source=report["source"],
                    source_event_id=report["source_event_id"],
                    payload=payload,
                    parsed=parsed,
                    received_at=report["received_at"],
                )
        finally:
            await writer.close()

        total_events = await conn.fetchval("SELECT COUNT(*) FROM events")
        total_reports = await conn.fetchval("SELECT COUNT(*) FROM event_reports")
        logger.info(
            "done: %d event(s), %d report(s) rebuilt from %d historical report(s)",
            total_events,
            total_reports,
            len(reports),
        )
    finally:
        await conn.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild `events` clusters from `event_reports` history"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report how many rows would be reprocessed",
    )
    parser.add_argument(
        "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(main(args.dry_run, args.yes))
