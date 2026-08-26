"""Backfills `events`/`event_reports` with data derived from logic added
after those rows were first ingested: CSN geocoding (geocoding.py) and the
local-intensity pipeline (intensity.py). Never re-fetches from any source
and never touches `event_reports.payload` -- see reprocess.py instead if
the *clustering* algorithm itself changes and history needs replaying from
scratch.

Two passes:

1. Re-parse every CSN `event_reports` row whose stored `latitude` is still
   NULL, through the now-geocoding-aware `csn.parse()`. Only the report's
   own latitude/longitude columns are patched in place -- it is never
   moved to a different event, since that's a clustering decision and
   this script doesn't re-run clustering.
2. For every `events` row, recompute its canonical fields from its latest
   per-source report snapshots (the same logic
   `db.Writer._recanonicalize` runs on every live update -- this picks up
   any coordinates pass 1 just added, which can also change which source
   wins canonical priority) and its intensity fields (distance_km,
   estimated_pga, estimated_mmi, is_significant, usgs_reported_mmi). Only
   events whose stored values actually differ from the recomputed ones are
   written, so `revision`/`updated_at`/NOTIFY stay meaningful across
   repeated runs of this script instead of bumping on every no-op re-run.

Both passes always run inside one transaction; `--dry-run` rolls it back
at the end instead of skipping the writes. Pass 2 depends on pass 1's
output (an event only gets local intensity once its CSN report has
coordinates), so a dry-run that merely skipped writing would under-report:
it needs to see what pass 1 *would* have written to accurately preview
what pass 2 would then do.

Usage:
    python recompute.py --dry-run     # report what would change
    python recompute.py               # prompts for confirmation
    python recompute.py --yes         # skip the confirmation prompt
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

import asyncpg

import dedup
import intensity
from config import load_config
from connectors import csn

logger = logging.getLogger(__name__)

NOTIFY_CHANNEL = "seismic_events"

_CANONICAL_UPDATE_FIELDS = (
    "origin_time", "latitude", "longitude", "depth_km", "magnitude",
    "magnitude_type", "region", "preferred_source",
)
_INTENSITY_UPDATE_FIELDS = (
    "distance_km", "estimated_pga", "estimated_mmi", "is_significant",
    "usgs_reported_mmi", "intensity_geometry_source", "intensity_distance_saturated",
)


async def _regeocode_csn_reports(conn: asyncpg.Connection) -> None:
    rows = await conn.fetch(
        "SELECT id, payload FROM event_reports WHERE source = 'CSN' AND latitude IS NULL"
    )
    logger.info("found %d CSN report(s) without coordinates", len(rows))

    geocoded = 0
    for row in rows:
        payload = json.loads(row["payload"])
        try:
            parsed = csn.parse(payload)
        except Exception:
            logger.exception("failed to re-parse CSN report %s", row["id"])
            continue
        if parsed.latitude is None or parsed.longitude is None:
            continue  # still not geocodable, nothing to change

        geocoded += 1
        logger.info(
            "report %s: geocoded to (%.5f, %.5f)", row["id"], parsed.latitude, parsed.longitude
        )
        await conn.execute(
            "UPDATE event_reports SET latitude = $2, longitude = $3 WHERE id = $1",
            row["id"],
            parsed.latitude,
            parsed.longitude,
        )

    logger.info("geocoded %d/%d previously-unlocated CSN report(s)", geocoded, len(rows))


async def _recompute_events(conn: asyncpg.Connection, config) -> None:
    event_ids = [r["id"] for r in await conn.fetch("SELECT id FROM events ORDER BY id")]
    logger.info("recomputing canonical + intensity fields for %d event(s)", len(event_ids))

    updated = 0
    for event_id in event_ids:
        async with conn.transaction():
            old = await conn.fetchrow(
                f"""
                SELECT cluster_key, {", ".join(_CANONICAL_UPDATE_FIELDS)},
                       {", ".join(_INTENSITY_UPDATE_FIELDS)}
                FROM events WHERE id = $1 FOR UPDATE
                """,
                event_id,
            )

            snapshot_rows = await conn.fetch(
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
            snapshots = [dict(r) for r in snapshot_rows]
            canonical = dedup.recompute_canonical(snapshots)
            usgs_mmi = next(
                (s["source_mmi"] for s in snapshots if s["source"] == "USGS" and s["source_mmi"] is not None),
                None,
            )
            # No jsonb type codec on this connection (plain asyncpg.connect,
            # same as _regeocode_csn_reports' manual json.loads on payload
            # above) -- rupture_geometry comes back as raw JSON text.
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
                home_lat=config.home_lat,
                home_lon=config.home_lon,
                rupture_vertices=rupture_vertices,
            )

            new_values = {
                **canonical,
                "distance_km": est.distance_km,
                "estimated_pga": est.estimated_pga,
                "estimated_mmi": est.estimated_mmi,
                "is_significant": est.is_significant,
                "usgs_reported_mmi": usgs_mmi,
                "intensity_geometry_source": est.geometry_source,
                "intensity_distance_saturated": est.distance_saturated,
            }
            fields = _CANONICAL_UPDATE_FIELDS + _INTENSITY_UPDATE_FIELDS
            if all(old[field] == new_values[field] for field in fields):
                continue

            updated += 1
            logger.info(
                "event %s changed: mmi %s -> %s, significant %s -> %s, distance_km %s -> %s",
                old["cluster_key"],
                old["estimated_mmi"], new_values["estimated_mmi"],
                old["is_significant"], new_values["is_significant"],
                old["distance_km"], new_values["distance_km"],
            )
            await conn.execute(
                f"""
                UPDATE events SET
                    {", ".join(f"{f} = ${i + 2}" for i, f in enumerate(fields))},
                    revision = revision + 1, updated_at = NOW()
                WHERE id = $1
                """,
                event_id,
                *[new_values[f] for f in fields],
            )
            await conn.execute(
                "SELECT pg_notify($1, $2)",
                NOTIFY_CHANNEL,
                json.dumps({"type": "update", "cluster_key": str(old["cluster_key"])}),
            )

    logger.info("updated %d/%d event(s)", updated, len(event_ids))


class _DryRunRollback(Exception):
    """Raised to unwind the transaction below after a dry-run has done all
    its (uncommitted) work -- see the module docstring on why dry-run runs
    the real writes and rolls back, rather than skipping them."""


async def main(dry_run: bool, assume_yes: bool) -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    config = load_config()
    conn = await asyncpg.connect(config.database_url)
    try:
        if not dry_run and not assume_yes:
            answer = input(
                "This will UPDATE event_reports (CSN geocoding) and events "
                "(canonical + intensity fields), bumping revision/NOTIFY "
                "for every event whose values actually change. "
                "Type 'yes' to continue: "
            )
            if answer.strip().lower() != "yes":
                logger.info("aborted")
                return

        try:
            async with conn.transaction():
                await _regeocode_csn_reports(conn)
                await _recompute_events(conn, config)
                if dry_run:
                    logger.info("dry-run: rolling back, nothing persisted")
                    raise _DryRunRollback()
        except _DryRunRollback:
            pass
    finally:
        await conn.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Only report what would change"
    )
    parser.add_argument(
        "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(main(args.dry_run, args.yes))
