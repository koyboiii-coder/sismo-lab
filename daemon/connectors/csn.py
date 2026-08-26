"""CSN Chile connector (unofficial, via api.gael.cloud).

Polls a single endpoint that returns the full current list of recent
events, refreshed by the upstream source roughly every 5 minutes. This
is the most fragile source in the system: all fields arrive as strings,
there is no stable event id, and no coordinates are provided at all
(only a free-text `RefGeografica`). The raw payload is always stored
as-is in `event_reports`; only best-effort parsed fields go into
`events`.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp

import geocoding
from config import Config
from db import Writer
from models import ParsedEvent

logger = logging.getLogger(__name__)

SOURCE = "CSN"
CHILE_TZ = ZoneInfo("America/Santiago")
UTC_TZ = ZoneInfo("UTC")


def _source_event_id(item: dict) -> str:
    # CSN has no id field. Derive a stable-ish identifier from the
    # values that describe the report, so repeated polls of the same
    # (still unrevised) event at least carry a consistent id — this is
    # not deduplication, just a usable key for event_reports.
    raw = f"{item.get('Fecha')}|{item.get('RefGeografica')}|{item.get('Magnitud')}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _parse_float(value) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def parse(item: dict) -> ParsedEvent:
    # Fecha has no timezone indicator; it's local Chile time.
    local_dt = datetime.strptime(item["Fecha"], "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=CHILE_TZ
    )
    origin_time = local_dt.astimezone(UTC_TZ)
    region = item.get("RefGeografica")
    # CSN never gives coordinates directly -- geocode_ref_geografica derives
    # them from RefGeografica's "<dist> km al <rumbo> de <localidad>" shape.
    # Returns None (never an approximate/invented point) if parsing,
    # locality lookup, or disambiguation fails -- see geocoding.py.
    geocoded = geocoding.geocode_ref_geografica(region)
    return ParsedEvent(
        origin_time=origin_time,
        latitude=geocoded.latitude if geocoded else None,
        longitude=geocoded.longitude if geocoded else None,
        depth_km=_parse_float(item.get("Profundidad")),
        magnitude=_parse_float(item.get("Magnitud")),
        magnitude_type=None,
        region=region,
        preferred_source=SOURCE,
    )


async def run(config: Config, writer: Writer, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            logger.info("[%s] polling...", SOURCE)
            logger.debug("[%s] sending GET %s", SOURCE, config.csn_url)
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    config.csn_url, timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    logger.debug(
                        "[%s] got response, status=%s", SOURCE, resp.status
                    )
                    resp.raise_for_status()
                    items = await resp.json(content_type=None)
            logger.debug("[%s] parsed response body: %d item(s)", SOURCE, len(items))

            written = 0
            for item in items:
                try:
                    source_event_id = _source_event_id(item)
                    parsed = parse(item)
                    logger.debug(
                        "[%s] writing report %s before DB write",
                        SOURCE,
                        source_event_id,
                    )
                    await writer.write_report(SOURCE, source_event_id, item, parsed)
                    logger.debug(
                        "[%s] wrote report %s after DB write",
                        SOURCE,
                        source_event_id,
                    )
                    written += 1
                except Exception:
                    logger.exception("[%s] failed to parse item: %s", SOURCE, item)

            logger.info("[%s] wrote %d new event(s) this cycle", SOURCE, written)
            await writer.mark_source_ok(SOURCE)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("[%s] poll error: %s", SOURCE, exc)
            await writer.mark_source_error(SOURCE, str(exc))

        logger.debug(
            "[%s] sleeping %ss before next poll", SOURCE, config.csn_poll_interval_s
        )
        await asyncio.sleep(config.csn_poll_interval_s)
