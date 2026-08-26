from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ParsedEvent:
    """Minimal fields extracted from a raw connector report.

    Passed to `db.Writer`, which clusters it against existing `events`
    rows (see `dedup.py`) rather than always creating a new one.
    """

    origin_time: datetime  # UTC, tz-aware
    latitude: Optional[float]
    longitude: Optional[float]
    depth_km: Optional[float]
    magnitude: Optional[float]
    magnitude_type: Optional[str]
    region: Optional[str]
    preferred_source: str
    # A source's own MMI estimate, verbatim, when it provides one (only
    # USGS does, via GeoJSON properties.mmi -- its ShakeMap-derived,
    # near-epicenter/max intensity). Stored so it can be compared against
    # our own GMPE at a matching distance -- NOT directly against
    # estimated_mmi, which is intensity at HOME_LAT/HOME_LON and will
    # differ for any event that isn't right on top of the house.
    source_mmi: Optional[float] = None
    # Real rupture-surface geometry, when a source publishes one: a list of
    # (lat, lon, depth_km) vertices. Only USGS ever sets this (see
    # connectors/usgs.fetch_rupture_geometry), only for M >= 7 events with a
    # real published rupture model. Feeds intensity.estimate()'s
    # finite_fault_rupture_distance_km path in place of the Wells &
    # Coppersmith worst-case approximation -- see intensity.py.
    rupture_geometry: Optional[list[tuple[float, float, float]]] = None
