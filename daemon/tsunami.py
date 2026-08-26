"""Rough "could this be tsunamigenic" flag: shallow + near the Chilean
coast. This is a coarse heuristic for what to put in a notification, NOT a
tsunami determination -- that's SHOA/SNAM's job (see shoa.py), and any
notification that sets this flag must say so. Getting this wrong in either
direction has real cost (a false negative undersells real risk, a false
positive causes alert fatigue) but the only two things it drives are (a)
whether a notification says "revisa el boletin SHOA" more prominently and
(b) sorting/highlighting in a future dashboard -- it never gates or
replaces the actual SHOA check.

Two independent criteria, both simplifications documented where they're
defined:

- Shallow: depth_km <= _SHALLOW_DEPTH_KM. Deeper ruptures couple much less
  efficiently with the water column.
- Coastal: within _COASTAL_MARGIN_KM of a coarse reference coastline,
  itself a hand-picked lookup table of longitude-by-latitude, continental
  Chile only (~-17.5 to -46.0). This is not a real coastline dataset --
  there isn't one already in this repo (geocoding.py's gazetteer is named
  localities, not a boundary) and pulling one in would be exactly the kind
  of heavy dependency rule 5 warns against for a single boolean flag. South
  of -46 (Aysen/Magallanes) the coast fragments into fjords and islands
  where a 1D longitude-vs-latitude table stops meaning anything, so this
  returns False there rather than guess -- same "fail closed to no
  coordinate" philosophy as geocoding.py, applied to a boolean instead of a
  location.
"""

from __future__ import annotations

from typing import Optional

from dedup import haversine_km

_SHALLOW_DEPTH_KM = 60.0

# Below this, even a shallow coastal event has essentially no tsunamigenic
# potential by seismological consensus -- this flag isn't meant to fire for
# routine small coastal earthquakes.
_MIN_MAGNITUDE = 6.0

_COASTAL_MARGIN_KM = 60.0

# (latitude, coastline_longitude) reference points, continental Chile,
# roughly Arica to Chiloe -- south of -46 the coast fragments into fjords
# and this table intentionally doesn't extend there (see module docstring).
# Approximate, by eye, from public geography; not survey-grade, which is
# fine for a "how far offshore/inland, roughly" margin check.
_COASTLINE_LAT_LON = [
    (-17.5, -70.3), (-18.5, -70.3), (-20.0, -70.15), (-21.0, -70.2),
    (-22.0, -70.4), (-23.5, -70.45), (-25.0, -70.5), (-27.0, -70.8),
    (-29.0, -71.3), (-31.0, -71.5), (-33.0, -71.6), (-33.6, -71.6),
    (-35.0, -72.4), (-36.5, -73.1), (-38.0, -73.6), (-39.5, -73.4),
    (-41.5, -72.9), (-43.5, -73.7), (-46.0, -73.7),
]


def _reference_coastline_lon(latitude: float) -> float:
    """Linear interpolation of _COASTLINE_LAT_LON at `latitude`. Table is
    ordered north (less negative) to south (more negative)."""
    points = _COASTLINE_LAT_LON
    if latitude >= points[0][0]:
        return points[0][1]
    if latitude <= points[-1][0]:
        return points[-1][1]
    for (lat_a, lon_a), (lat_b, lon_b) in zip(points, points[1:]):
        if lat_b <= latitude <= lat_a:
            frac = (lat_a - latitude) / (lat_a - lat_b)
            return lon_a + frac * (lon_b - lon_a)
    return points[-1][1]  # unreachable given the bounds checks above


def is_coastal(latitude: float, longitude: float) -> bool:
    lat_min, lat_max = _COASTLINE_LAT_LON[-1][0], _COASTLINE_LAT_LON[0][0]
    if not (lat_min <= latitude <= lat_max):
        return False
    reference_lon = _reference_coastline_lon(latitude)
    # 1 degree of longitude != a fixed km distance -- haversine against a
    # same-latitude point handles the cos(lat) scaling properly rather than
    # eyeballing a degree-based margin.
    distance_km = haversine_km(latitude, longitude, latitude, reference_lon)
    return distance_km <= _COASTAL_MARGIN_KM


def possible_tsunami_source(
    latitude: Optional[float], longitude: Optional[float],
    depth_km: Optional[float], magnitude: Optional[float],
) -> bool:
    """True when an event is shallow, near the Chilean coast, and large
    enough to plausibly matter -- the "flag this prominently" signal for
    alerts.py, never a substitute for an actual SHOA/SNAM determination."""
    if latitude is None or longitude is None or depth_km is None or magnitude is None:
        return False
    if magnitude < _MIN_MAGNITUDE or depth_km > _SHALLOW_DEPTH_KM:
        return False
    return is_coastal(latitude, longitude)
