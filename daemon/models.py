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
