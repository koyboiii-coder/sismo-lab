"""USGS FDSN Event Web Service connector.

Polls two queries every `usgs_poll_interval_s`: a global feed above
`usgs_min_magnitude_global`, and a Chile bounding-box feed above the
lower `usgs_min_magnitude_chile` threshold. Both use a rolling window of
`usgs_window_minutes`.

The same earthquake will be re-fetched on every poll while it stays
inside the moving window; `db.Writer` recognizes the repeat by
`source_event_id` and updates the existing event instead of creating a
new one. Only exact duplicates *within the same poll* (an event matched
by both queries) are collapsed here.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import aiohttp

from config import Config
from db import Writer
from dedup import CHILE_BBOX as _CHILE_BBOX
from models import ParsedEvent

logger = logging.getLogger(__name__)

SOURCE = "USGS"

CHILE_BBOX = dict(
    minlatitude=_CHILE_BBOX["min_lat"],
    maxlatitude=_CHILE_BBOX["max_lat"],
    minlongitude=_CHILE_BBOX["min_lon"],
    maxlongitude=_CHILE_BBOX["max_lon"],
)


def parse(feature: dict) -> ParsedEvent:
    properties = feature["properties"]
    coordinates = feature["geometry"]["coordinates"]
    origin_time = datetime.fromtimestamp(properties["time"] / 1000, tz=timezone.utc)
    return ParsedEvent(
        origin_time=origin_time,
        latitude=coordinates[1],
        longitude=coordinates[0],
        depth_km=coordinates[2],
        magnitude=properties.get("mag"),
        magnitude_type=properties.get("magType"),
        region=properties.get("place"),
        preferred_source=SOURCE,
    )


async def _fetch(
    session: aiohttp.ClientSession, config: Config, starttime: str, extra_params: dict
) -> list:
    params = {"format": "geojson", "starttime": starttime, **extra_params}
    async with session.get(
        config.usgs_base_url, params=params, timeout=aiohttp.ClientTimeout(total=30)
    ) as resp:
        resp.raise_for_status()
        body = await resp.json()
        return body.get("features", [])


async def run(config: Config, writer: Writer, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            logger.info("[%s] polling...", SOURCE)
            starttime = (
                datetime.now(timezone.utc) - timedelta(minutes=config.usgs_window_minutes)
            ).strftime("%Y-%m-%dT%H:%M:%S")

            async with aiohttp.ClientSession() as session:
                global_features, chile_features = await asyncio.gather(
                    _fetch(
                        session,
                        config,
                        starttime,
                        {"minmagnitude": config.usgs_min_magnitude_global},
                    ),
                    _fetch(
                        session,
                        config,
                        starttime,
                        {"minmagnitude": config.usgs_min_magnitude_chile, **CHILE_BBOX},
                    ),
                )

            seen_ids = set()
            written = 0
            for feature in global_features + chile_features:
                source_event_id = feature.get("id")
                if not source_event_id or source_event_id in seen_ids:
                    continue
                seen_ids.add(source_event_id)
                try:
                    parsed = parse(feature)
                    await writer.write_report(SOURCE, source_event_id, feature, parsed)
                    written += 1
                except Exception:
                    logger.exception(
                        "[%s] failed to parse feature %s", SOURCE, source_event_id
                    )

            logger.info("[%s] wrote %d new event(s) this cycle", SOURCE, written)
            await writer.mark_source_ok(SOURCE)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("[%s] poll error: %s", SOURCE, exc)
            await writer.mark_source_error(SOURCE, str(exc))

        await asyncio.sleep(config.usgs_poll_interval_s)
