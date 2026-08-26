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
from typing import Optional

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

# Below this, don't bother fetching finite-fault geometry: intensity.py's
# Wells & Coppersmith fallback only starts materially reducing the
# hypocentral distance once the rupture length is a meaningful fraction of
# typical distances-of-interest, and every event this small is well
# rock-approximated as a point source anyway. Matches the magnitude where
# the fallback's docstring caveat (saturation) starts to matter.
FINITE_FAULT_MIN_MAGNITUDE = 7.0

# GeoJSON geometry types that represent an actual extended rupture. A bare
# "Point" means ShakeMap had no real fault model to draw from and just
# echoed the hypocenter back (metadata.reference == "Origin" in that case)
# -- using it as "real" geometry would silently reproduce the exact
# point-source approximation the Wells & Coppersmith fallback already makes,
# while wrongly labeling it intensity_geometry_source='finite_fault'.
# Confirmed against live USGS payloads (2023 Turkey M7.8, us6000jllz -- real
# MultiPolygon rupture; several other M7+ events with no finite-fault
# product -- single Point, reference "Origin").
_REAL_RUPTURE_GEOMETRY_TYPES = {
    "Polygon", "MultiPolygon", "LineString", "MultiLineString", "MultiPoint",
}


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
        # ShakeMap-derived MMI, when USGS has computed one. Passed through
        # verbatim to compare against our own estimated_mmi -- see
        # intensity.py and events.usgs_reported_mmi.
        source_mmi=properties.get("mmi"),
    )


def _extract_vertices(geometry: dict) -> list[tuple[float, float, float]]:
    """Flattens a GeoJSON geometry's coordinates (Point/LineString/Polygon/
    Multi* -- arbitrary nesting depth) into (lat, lon, depth_km) triples.
    GeoJSON coordinate order is [lon, lat, (optional) depth]; ShakeMap's
    rupture.json always includes depth, in km positive-down (confirmed
    against us6000jllz's rupture.json: 1.0-16.0 km for a shallow crustal
    M7.8), but this defaults a missing third element to 0.0 defensively."""
    vertices: list[tuple[float, float, float]] = []

    def walk(node) -> None:
        if not isinstance(node, list):
            return
        if node and isinstance(node[0], (int, float)):
            lon, lat = node[0], node[1]
            depth = node[2] if len(node) > 2 else 0.0
            vertices.append((lat, lon, depth))
            return
        for child in node:
            walk(child)

    walk(geometry.get("coordinates"))
    return vertices


async def fetch_rupture_geometry(
    session: aiohttp.ClientSession, feature: dict
) -> Optional[list[tuple[float, float, float]]]:
    """Fetches real rupture-surface geometry for a M >= 7 USGS event, from
    its ShakeMap product's rupture.json (properties.products.shakemap ->
    contents["download/rupture.json"]), if one exists and represents an
    actual modeled fault rather than a point-source placeholder.

    Requires a second network round-trip per qualifying event (the summary
    feed used elsewhere in this module has no rupture geometry; only the
    per-event "detail" feed -- linked from properties.detail on every
    feature -- carries properties.products). Called on every poll for every
    M >= 7 feature currently in the moving window, which is deliberately
    unoptimized: these events are rare, and a freshly-published or revised
    finite-fault model is exactly the kind of update this should pick up
    without extra bookkeeping. Reconsider (e.g. cache by product
    updateTime) only if this turns out to be a real cost in practice.

    Returns None -- never raises -- whenever real geometry isn't available:
    no `detail` link, no shakemap product, no rupture.json content, a
    point-only placeholder, or any network/parsing failure. Rule 4
    (graceful degradation): the caller falls back to the Wells & Coppersmith
    approximation in that case, which is the normal, expected outcome for
    most events, not an error.
    """
    detail_url = feature.get("properties", {}).get("detail")
    if not detail_url:
        return None

    try:
        async with session.get(
            detail_url, timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            resp.raise_for_status()
            detail = await resp.json()

        shakemap = detail.get("properties", {}).get("products", {}).get("shakemap")
        if not shakemap:
            return None
        contents = shakemap[0].get("contents", {})
        rupture_content = contents.get("download/rupture.json")
        if not rupture_content:
            return None

        async with session.get(
            rupture_content["url"], timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            resp.raise_for_status()
            rupture_geojson = await resp.json()

        features = rupture_geojson.get("features", [])
        if not any(
            f.get("geometry", {}).get("type") in _REAL_RUPTURE_GEOMETRY_TYPES
            for f in features
        ):
            logger.info(
                "[%s] %s: shakemap rupture.json has no real fault model "
                "(reference=%r) -- falling back to Wells & Coppersmith",
                SOURCE,
                feature.get("id"),
                rupture_geojson.get("metadata", {}).get("reference"),
            )
            return None

        vertices = [v for f in features for v in _extract_vertices(f["geometry"])]
        return vertices or None
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.warning(
            "[%s] %s: failed to fetch/parse finite-fault geometry, "
            "falling back to Wells & Coppersmith",
            SOURCE,
            feature.get("id"),
            exc_info=True,
        )
        return None


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
                        if parsed.magnitude is not None and parsed.magnitude >= FINITE_FAULT_MIN_MAGNITUDE:
                            parsed.rupture_geometry = await fetch_rupture_geometry(session, feature)
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
