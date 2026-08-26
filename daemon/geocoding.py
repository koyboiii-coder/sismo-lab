"""Geocodes CSN's `RefGeografica` free-text field ("49 km al SE de
Socaire") into coordinates, since CSN never provides latitude/longitude
directly (see CLAUDE.md's "Fuentes de datos" / CSN section).

Pipeline: parse "<distancia> km al <rumbo> de <localidad>" -> look up
<localidad> in an offline gazetteer of Chilean localities -> project a
point <distancia> km along <rumbo> from that locality's coordinates.

If any step fails -- the text doesn't match the expected shape, the
compass code is unrecognized, or the locality isn't found -- this returns
None. It never falls back to a nearest-match guess: an approximate
coordinate presented as real would be worse than no coordinate, since
nothing downstream would know to distrust it (see CLAUDE.md: "si no se
logra ubicar, el evento se guarda sin coordenadas").

This also means a reference to a place outside Chile (e.g. "110 km al NE
de San Antonio de los Cobres", which is in Argentina) fails safely: the
embedded gazetteer (see build_gazetteer.py) only covers Chile, so a
non-Chilean locality simply isn't found. This is a deliberate side effect
of scoping the dataset to Chile, not a separate check.
"""

from __future__ import annotations

import gzip
import logging
import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dedup import EARTH_RADIUS_KM, haversine_km

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).parent / "data" / "cl_gazetteer.tsv.gz"
# Hand-curated overlay (major mines and similar CSN-cited places GeoNames'
# whitelist excludes or doesn't carry at all) -- see that file's header for
# why it's kept separate from build_gazetteer.py's output. Plain, uncompressed
# TSV since it's meant to be hand-edited, with '#'-prefixed comment lines.
_MANUAL_DATA_PATH = Path(__file__).parent / "data" / "manual_places.tsv"

# 16-point compass, Spanish notation (O for Oeste, not W -- CSN's actual
# output only ever uses the 8 primary/secondary points in the examples
# CLAUDE.md documents, but the 16-point set costs nothing extra to support
# and some CSN reports do use them).
_COMPASS_DEGREES = {
    "N": 0.0, "NNE": 22.5, "NE": 45.0, "ENE": 67.5,
    "E": 90.0, "ESE": 112.5, "SE": 135.0, "SSE": 157.5,
    "S": 180.0, "SSO": 202.5, "SO": 225.0, "OSO": 247.5,
    "O": 270.0, "ONO": 292.5, "NO": 315.0, "NNO": 337.5,
}

_REF_RE = re.compile(
    r"^\s*(?P<distance>\d+(?:[.,]\d+)?)\s*km\s+al\s+(?P<dir>[A-Za-zÑñ]{1,3})\s+de\s+(?P<locality>.+?)\s*$",
    re.IGNORECASE,
)

# Spanish geographic generic terms. Gazetteer entries are frequently
# "<generic> <name>" ("Caleta Patache", "Punta Patache", "Puerto Patache")
# while CSN cites just "<name>" ("... de Patache"). Stripped iteratively so
# multi-word generics like "Guaneros Punta X" still resolve. This is exact
# normalized matching after stripping known prefixes, not fuzzy/nearest
# matching -- see module docstring on why that distinction matters.
_GENERIC_PREFIXES = frozenset({
    "caleta", "punta", "puerto", "cerro", "volcan", "salar", "quebrada",
    "isla", "islote", "bahia", "faro", "cuesta", "portezuelo", "paso",
    "rio", "estero", "laguna", "cordon", "villa", "aldea", "fundo",
    "hacienda", "sector", "localidad", "poblado", "caserio", "cuchilla",
    "loma", "guaneros", "campamento", "mina", "estacion", "playa",
})

# Feature-class priority when several gazetteer rows share a matched name
# (see `_resolve_candidates`): a populated place is stronger evidence of
# "the town called X" than a terrain feature that happens to share the name.
_CLASS_RANK = {"P": 0, "L": 1, "H": 2, "T": 3}

# If every candidate for a name sits within this radius of the top-ranked
# one, they're treated as the same real-world place (e.g. duplicate
# registrations across admin-boundary revisions) and the top-ranked one's
# coordinates are used. Beyond this radius, two different Chilean places
# happen to share a name (there are dozens of "Cerro Negro") and there's no
# reliable way to tell which one CSN meant -- so the lookup fails rather
# than guessing.
_AMBIGUITY_CLUSTER_KM = 15.0


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped.lower().strip())


def _strip_generic_prefix(normalized_name: str) -> Optional[str]:
    """Strip leading generic terms, plus a connecting "de" if one follows a
    stripped term ("punta de choros" -> "choros", matching gazetteer's
    "Punta Choros"/"Choros" -- GeoNames entries never carry the "de", but
    CSN's own free text sometimes does, e.g. "... de Punta de Choros")."""
    tokens = normalized_name.split(" ")
    i = 0
    while i < len(tokens) - 1 and tokens[i] in _GENERIC_PREFIXES:
        i += 1
        if i < len(tokens) - 1 and tokens[i] == "de":
            i += 1
    if i == 0:
        return None
    return " ".join(tokens[i:])


@dataclass(frozen=True)
class _Locality:
    name: str
    latitude: float
    longitude: float
    fclass: str
    population: int


@dataclass(frozen=True)
class ParsedRef:
    distance_km: float
    bearing_deg: float
    locality: str


@dataclass(frozen=True)
class GeocodeResult:
    latitude: float
    longitude: float
    # Kept for logging/debugging -- which gazetteer entry was actually used.
    matched_locality: str
    matched_latitude: float
    matched_longitude: float


def parse_ref_geografica(ref: str) -> Optional[ParsedRef]:
    if not ref:
        return None
    match = _REF_RE.match(ref)
    if not match:
        return None
    bearing = _COMPASS_DEGREES.get(match.group("dir").upper())
    if bearing is None:
        return None
    try:
        distance_km = float(match.group("distance").replace(",", "."))
    except ValueError:
        return None
    locality = match.group("locality").strip()
    if not locality:
        return None
    return ParsedRef(distance_km=distance_km, bearing_deg=bearing, locality=locality)


def _project(lat: float, lon: float, distance_km: float, bearing_deg: float) -> tuple[float, float]:
    """Destination point given a start point, bearing and distance, via the
    standard spherical direct geodesic formula. Flat-earth/equirectangular
    approximations break down badly at the 100+ km distances CSN reports."""
    angular_distance = distance_km / EARTH_RADIUS_KM
    bearing = math.radians(bearing_deg)
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)

    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular_distance)
        + math.cos(lat1) * math.sin(angular_distance) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(angular_distance) * math.cos(lat1),
        math.cos(angular_distance) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), (math.degrees(lon2) + 540.0) % 360.0 - 180.0


class Gazetteer:
    def __init__(self, localities: list[_Locality]):
        self._primary: dict[str, list[_Locality]] = defaultdict(list)
        self._secondary: dict[str, list[_Locality]] = defaultdict(list)
        for loc in localities:
            key = _normalize(loc.name)
            self._primary[key].append(loc)
            stripped = _strip_generic_prefix(key)
            if stripped:
                self._secondary[stripped].append(loc)

    @classmethod
    def load(cls, path: Path = _DATA_PATH, manual_path: Path = _MANUAL_DATA_PATH) -> "Gazetteer":
        localities = []
        with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
            next(f)  # header
            for line in f:
                name, asciiname, lat, lon, fclass, fcode, admin1, population = line.rstrip("\n").split("\t")
                localities.append(_Locality(
                    name=name,
                    latitude=float(lat),
                    longitude=float(lon),
                    fclass=fclass,
                    population=int(population) if population else 0,
                ))
        base_count = len(localities)

        manual_count = 0
        try:
            manual_lines = manual_path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            logger.warning(
                "manual gazetteer overlay not found at %s -- proceeding with "
                "the generated dataset only", manual_path,
            )
        else:
            rows = (
                line for line in manual_lines
                if line.strip() and not line.lstrip().startswith("#")
            )
            next(rows)  # header
            for line in rows:
                name, asciiname, lat, lon, fclass, fcode, admin1, population = line.split("\t")
                localities.append(_Locality(
                    name=name,
                    latitude=float(lat),
                    longitude=float(lon),
                    fclass=fclass,
                    population=int(population) if population else 0,
                ))
                manual_count += 1

        logger.info(
            "loaded %d localities into offline gazetteer (%d generated + %d manual overlay)",
            len(localities), base_count, manual_count,
        )
        return cls(localities)

    def resolve(self, locality_name: str) -> tuple[Optional[_Locality], Optional[str]]:
        """Returns (locality, None) on success, or (None, reason) on failure,
        where reason is "not_found" or "ambiguous" -- see
        geocode_ref_geografica for how callers surface this."""
        key = _normalize(locality_name)
        candidates = self._primary.get(key) or self._secondary.get(key)
        if not candidates:
            # The query itself may carry a generic term CSN's text includes
            # but the gazetteer entry doesn't spell out on its own name (e.g.
            # a query of "Punta de Choros" against a gazetteer whose entry is
            # plain "Choros") -- so strip the query symmetrically to how
            # gazetteer entries are indexed above, not just the other way.
            stripped = _strip_generic_prefix(key)
            if stripped:
                candidates = self._primary.get(stripped) or self._secondary.get(stripped)
        if not candidates:
            return None, "not_found"
        result = _resolve_candidates(candidates, locality_name)
        if result is None:
            return None, "ambiguous"
        return result, None

    def size(self) -> int:
        return sum(len(v) for v in self._primary.values())


def _priority(loc: _Locality) -> tuple[int, int]:
    return (_CLASS_RANK.get(loc.fclass, 9), -loc.population)


def _resolve_candidates(candidates: list[_Locality], queried_name: str) -> Optional[_Locality]:
    best = min(candidates, key=_priority)
    if len(candidates) == 1:
        return best

    farthest = max(
        haversine_km(best.latitude, best.longitude, c.latitude, c.longitude)
        for c in candidates
    )
    if farthest > _AMBIGUITY_CLUSTER_KM:
        logger.info(
            "locality %r is ambiguous: %d candidates spanning %.0f km "
            "(max allowed %.0f km) -- refusing to guess",
            queried_name, len(candidates), farthest, _AMBIGUITY_CLUSTER_KM,
        )
        return None
    return best


_GAZETTEER: Optional[Gazetteer] = None

# The real embedded dataset has ~26k rows (see build_gazetteer.py). Anything
# far below that means the shipped file is missing, truncated, or an empty
# placeholder -- e.g. excluded from a Docker build context the same way it
# was once excluded from git (see the module/CLAUDE.md history on this).
# That must be loud at startup, not discovered later as a wall of unrelated
# "locality not found" misses during normal CSN polling.
_EXPECTED_MIN_LOCALITIES = 20000


def _get_gazetteer() -> Gazetteer:
    global _GAZETTEER
    if _GAZETTEER is None:
        _GAZETTEER = Gazetteer.load()
    return _GAZETTEER


def startup_check() -> bool:
    """Eagerly loads the gazetteer and logs its health once, loudly, at
    daemon startup. Never raises -- CSN events already degrade gracefully to
    coordinate-less when geocoding is unavailable (rule 4, CLAUDE.md), so a
    bad gazetteer must not crash the daemon. It must, however, be impossible
    to miss in the logs, since a silent failure here means CSN geocoding
    quietly stops working entirely and nothing else would say so."""
    try:
        gazetteer = _get_gazetteer()
    except Exception:
        logger.error(
            "failed to load offline gazetteer from %s -- CSN events will "
            "have no coordinates until this is fixed",
            _DATA_PATH,
            exc_info=True,
        )
        return False

    count = gazetteer.size()
    if count < _EXPECTED_MIN_LOCALITIES:
        logger.error(
            "offline gazetteer at %s loaded only %d localities (expected "
            "at least %d) -- looks truncated or missing from the build; "
            "CSN geocoding will fail for most localities until this is fixed",
            _DATA_PATH, count, _EXPECTED_MIN_LOCALITIES,
        )
        return False

    logger.info("offline gazetteer loaded %d localities from %s", count, _DATA_PATH)
    return True


def geocode_ref_geografica(ref: Optional[str]) -> Optional[GeocodeResult]:
    if not ref:
        return None

    parsed = parse_ref_geografica(ref)
    if parsed is None:
        logger.debug("geocoding failed for %r: reason=parse_failed", ref)
        return None

    match, reason = _get_gazetteer().resolve(parsed.locality)
    if match is None:
        logger.debug(
            "geocoding failed for %r: reason=%s locality=%r", ref, reason, parsed.locality
        )
        return None

    latitude, longitude = _project(
        match.latitude, match.longitude, parsed.distance_km, parsed.bearing_deg
    )
    return GeocodeResult(
        latitude=latitude,
        longitude=longitude,
        matched_locality=match.name,
        matched_latitude=match.latitude,
        matched_longitude=match.longitude,
    )
