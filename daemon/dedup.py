"""Cross-source clustering rules, per CLAUDE.md's "Deduplicacion" section.

Pure functions only -- no DB access here. `db.Writer` uses these to decide
whether an incoming report belongs to an existing `events` cluster and,
if so, what the cluster's canonical fields should become.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

from models import ParsedEvent

logger = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0

TIME_WINDOW_S = 90
# Narrower window for the no-coordinates fallback (the CSN case) -- see
# `matches_cluster`. Kept tighter than TIME_WINDOW_S because this path has
# no spatial check to fall back on, only elapsed time + magnitude + bbox.
TIME_WINDOW_S_NO_COORDS = 30
SPATIAL_WINDOW_KM = 100.0
MAGNITUDE_WINDOW_NO_COORDS = 0.7

# Same rectangle USGS's connector queries for its Chile-specific feed.
CHILE_BBOX = dict(min_lat=-56.0, max_lat=-17.0, min_lon=-76.0, max_lon=-66.0)

SOURCE_PRIORITY_CHILE = ("CSN", "USGS", "EMSC")
SOURCE_PRIORITY_WORLD = ("USGS", "EMSC")

CANONICAL_FIELDS = (
    "origin_time",
    "latitude",
    "longitude",
    "depth_km",
    "magnitude",
    "magnitude_type",
    "region",
)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def in_chile_bbox(lat: Optional[float], lon: Optional[float]) -> bool:
    if lat is None or lon is None:
        return False
    return (
        CHILE_BBOX["min_lat"] <= lat <= CHILE_BBOX["max_lat"]
        and CHILE_BBOX["min_lon"] <= lon <= CHILE_BBOX["max_lon"]
    )


def matches_cluster(parsed: ParsedEvent, candidate: dict) -> bool:
    """`candidate` is a row from `events` (origin_time/latitude/longitude/
    magnitude/region -- its current canonical values). Assumes the caller
    has already restricted candidates to the +-90s origin_time window."""
    has_coords = (
        parsed.latitude is not None
        and parsed.longitude is not None
        and candidate["latitude"] is not None
        and candidate["longitude"] is not None
    )
    if has_coords:
        distance = haversine_km(
            parsed.latitude, parsed.longitude, candidate["latitude"], candidate["longitude"]
        )
        return distance < SPATIAL_WINDOW_KM

    # At least one side has no coordinates (the CSN case) -- fall back to
    # elapsed time + magnitude, since there's no spatial check available on
    # that side. This used to match globally on magnitude alone within the
    # +-90s window, which merged a CSN report (no coords) with an unrelated
    # EMSC event on the other side of the world (e.g. Alaska) purely because
    # their magnitudes happened to be close. The window is tighter here than
    # the coordinate case, since magnitude proximity alone is weak evidence.
    dt = abs((candidate["origin_time"] - parsed.origin_time).total_seconds())
    if dt > TIME_WINDOW_S_NO_COORDS:
        return False

    # CSN is the only source that can lack coordinates (when
    # geocoding.py fails to resolve RefGeografica -- see csn.py) and it's
    # exclusively Chilean. If the *other* side does have coordinates, they
    # must sit inside Chile -- otherwise this is two unrelated events that
    # merely share a magnitude and a moment (the Alaska/Argentina bug). If
    # neither side has coordinates, both reports must be CSN's (e.g. two of
    # its hash-derived ids for the same revised report), and there's no
    # location to cross-check.
    known_coords = [
        (lat, lon)
        for lat, lon in ((parsed.latitude, parsed.longitude), (candidate["latitude"], candidate["longitude"]))
        if lat is not None and lon is not None
    ]
    if known_coords and not any(in_chile_bbox(lat, lon) for lat, lon in known_coords):
        return False

    if parsed.magnitude is None or candidate["magnitude"] is None:
        return False
    if abs(parsed.magnitude - candidate["magnitude"]) >= MAGNITUDE_WINDOW_NO_COORDS:
        return False

    if known_coords:
        # Cross-source merge (no-coords report matched against a
        # coordinate-bearing one). Region strings come from different
        # agencies in free text ("43 km al O de Ollagüe" vs "ANTOFAGASTA,
        # CHILE" vs flynn_region) -- there's no reliable way to
        # auto-validate they refer to the same place without geocoding, and
        # a heuristic string match would either miss real mismatches or
        # block legitimate merges. Bbox + time + magnitude above do the
        # actual gatekeeping; this just flags the merge for a human to
        # eyeball, per CLAUDE.md's dedup rules.
        logger.warning(
            "no-coordinates merge accepted (dt=%.1fs, mag diff=%.2f): "
            "regions='%s' vs '%s' -- review for coherence",
            dt,
            abs(parsed.magnitude - candidate["magnitude"]),
            parsed.region,
            candidate.get("region"),
        )
    return True


def source_priority(is_chile: bool) -> tuple[str, ...]:
    return SOURCE_PRIORITY_CHILE if is_chile else SOURCE_PRIORITY_WORLD


def recompute_canonical(snapshots: list[dict]) -> dict:
    """`snapshots`: latest parsed report per source attached to a cluster,
    each a dict with a "source" key plus CANONICAL_FIELDS. Picks an overall
    preferred_source by priority, then fills each field from the
    highest-priority source that actually has it -- CSN outranks USGS/EMSC
    in Chile but never has coordinates, so those still need to come from
    whichever other source has them.
    """
    is_chile = any(s["source"] == "CSN" for s in snapshots) or any(
        in_chile_bbox(s["latitude"], s["longitude"]) for s in snapshots
    )
    priority = source_priority(is_chile)
    present = {s["source"] for s in snapshots}
    ordered = [s for s in priority if s in present]
    ordered += sorted(s for s in present if s not in ordered)

    by_source = {s["source"]: s for s in snapshots}
    canonical = {}
    for field in CANONICAL_FIELDS:
        value = None
        for source in ordered:
            candidate_value = by_source[source][field]
            if candidate_value is not None:
                value = candidate_value
                break
        canonical[field] = value
    canonical["preferred_source"] = ordered[0]
    return canonical
