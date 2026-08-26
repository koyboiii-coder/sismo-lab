"""Injects one synthetic earthquake through the real intensity -> alerts ->
ntfy chain, to verify end-to-end that a qualifying event actually reaches a
phone -- without ever touching Postgres.

Deliberately bypasses db.Writer entirely: no `events`/`event_reports` row is
created, so there is nothing to clean up afterwards and no risk of a
synthetic point being clustered against a real event by dedup.py. This means
it does not exercise dedup/clustering, NOTIFY, or the API/SSE path -- only
the part CLAUDE.md's "Motor de reglas" actually computes:

    intensity.estimate() -> alerts.alert_level() -> alerts.send() -> ntfy

which is the same sequence db.Writer._create_event runs for a brand-new
event (see db.py) minus the DB write itself.

The default scenario (M8.8, 350 km epicentral, 35 km deep -- the type-Maule
case documented in validate_intensity.py) is chosen specifically because it
crosses MMI >= V there, so a bare `--send` should always produce ALERT_FULL
against the deployed HOME_LAT/HOME_LON. The synthetic hypocenter is placed
due south of home at the requested distance (same trick as
validate_intensity.py: a pure north-south offset makes the haversine
distance exact, no need to solve for a bearing).

Every notification sent this way is marked unmistakably as a test --
alerts.format_message's `test_marker`, a "[PRUEBA]" title prefix plus a loud
first body line -- so it can never be confused with a real earthquake on the
phone that receives it.

Usage:
    python simulate_alert.py                     # compute + print only
    python simulate_alert.py --send               # also POST to ntfy for real
    python simulate_alert.py --send --magnitude 4.2 --distance-km 15 --depth-km 8
    python simulate_alert.py --list-presets
"""

from __future__ import annotations

import argparse
import asyncio
import math
from dataclasses import dataclass

import alerts
import intensity
import tsunami
from config import load_config
from dedup import EARTH_RADIUS_KM

_KM_PER_DEG_LAT = math.pi * EARTH_RADIUS_KM / 180  # ~111.19, see validate_intensity.py


@dataclass(frozen=True)
class Preset:
    name: str
    description: str
    magnitude: float
    distance_km: float
    depth_km: float


# Same scenarios validate_intensity.py already validated numerically --
# reused here as ready-made `--preset` choices instead of requiring
# `--magnitude/--distance-km/--depth-km` to be worked out by hand.
PRESETS = {
    "full": Preset(
        "full", "MMI >= V (ALERTA COMPLETA) -- tipo Maule 2010",
        magnitude=8.8, distance_km=350.0, depth_km=35.0,
    ),
    "silent": Preset(
        "silent", "MMI III-IV (notificacion silenciosa)",
        magnitude=4.5, distance_km=20.0, depth_km=10.0,
    ),
    "none": Preset(
        "none", "MMI < III (no deberia notificar)",
        magnitude=4.0, distance_km=100.0, depth_km=40.0,
    ),
}


def _synthetic_hypocenter(home_lat: float, home_lon: float, distance_km: float) -> tuple[float, float]:
    """A point exactly `distance_km` due south of home. Longitude held equal
    to home_lon: on a meridian, great-circle distance is exactly
    R * delta_latitude_radians, no cos(lat) correction to get wrong."""
    return home_lat - distance_km / _KM_PER_DEG_LAT, home_lon


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inject a synthetic earthquake through intensity.py -> alerts.py "
            "-> ntfy, without writing to Postgres, to verify the alert chain "
            "reaches a phone."
        )
    )
    parser.add_argument(
        "--preset", choices=sorted(PRESETS), default=None,
        help="Named scenario from PRESETS (overridden by --magnitude/--distance-km/"
        "--depth-km if any of those are also given). Default: 'full' if no "
        "override is given.",
    )
    parser.add_argument("--magnitude", type=float, default=None)
    parser.add_argument("--distance-km", type=float, default=None, help="epicentral distance from HOME, due south")
    parser.add_argument("--depth-km", type=float, default=None)
    parser.add_argument(
        "--send", action="store_true",
        help="Actually POST to ntfy (real push to whatever subscribes to "
        "NTFY_TOPIC). Without this flag, only computes and prints -- no network call.",
    )
    parser.add_argument(
        "--list-presets", action="store_true", help="Print PRESETS and exit"
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if args.list_presets:
        for preset in PRESETS.values():
            print(f"{preset.name:8} {preset.description}")
            print(
                f"         M{preset.magnitude}, {preset.distance_km:.0f} km epicentral, "
                f"{preset.depth_km:.0f} km depth"
            )
        return

    override_given = any(
        v is not None for v in (args.magnitude, args.distance_km, args.depth_km)
    )
    preset = PRESETS[args.preset] if args.preset else (None if override_given else PRESETS["full"])

    magnitude = args.magnitude if args.magnitude is not None else (preset.magnitude if preset else None)
    distance_km = args.distance_km if args.distance_km is not None else (preset.distance_km if preset else None)
    depth_km = args.depth_km if args.depth_km is not None else (preset.depth_km if preset else None)
    if magnitude is None or distance_km is None or depth_km is None:
        raise SystemExit(
            "need magnitude, distance-km and depth-km -- pass all three "
            "explicitly, or use --preset (see --list-presets)"
        )

    config = load_config()
    lat, lon = _synthetic_hypocenter(config.home_lat, config.home_lon, distance_km)

    est = intensity.estimate(
        latitude=lat, longitude=lon, depth_km=depth_km, magnitude=magnitude,
        home_lat=config.home_lat, home_lon=config.home_lon,
    )
    level = alerts.alert_level(est.estimated_mmi)
    tsunami_flag = tsunami.possible_tsunami_source(lat, lon, depth_km, magnitude)
    region = f"[SINTETICO] {distance_km:.0f} km al S de HOME_LAT/HOME_LON"

    print(f"HOME:          ({config.home_lat}, {config.home_lon})")
    print(f"hipocentro:    ({lat:.4f}, {lon:.4f})")
    print(f"magnitud:      M{magnitude}")
    print(f"profundidad:   {depth_km:.1f} km")
    print(f"dist. hipoc.:  {est.distance_km:.1f} km")
    print(f"Rrup usado:    {est.rrup_km:.1f} km ({est.geometry_source}, saturado={est.distance_saturated})")
    print(f"PGA estimado:  {est.estimated_pga:.5f} g")
    print(f"MMI estimada:  {est.estimated_mmi:.2f} ({intensity.mmi_roman(est.estimated_mmi)})")
    print(f"nivel alerta:  {level!r}")
    print(f"tsunami_flag:  {tsunami_flag}")

    if level is None:
        print(
            "\nEsta combinacion no cruza ningun umbral de notificacion "
            "(MMI < III) -- nada que enviar. Usa --preset full/silent, o "
            "sube --magnitude / baja --distance-km, para probar el envio."
        )
        return

    if not args.send:
        print(
            "\n(no se envio nada -- pasa --send para hacer el POST real a "
            f"ntfy en {config.ntfy_url}, topic '{config.ntfy_topic}')"
        )
        return

    print(f"\nenviando a {config.ntfy_url} (topic '{config.ntfy_topic}')...")
    asyncio.run(
        alerts.send(
            ntfy_url=config.ntfy_url,
            ntfy_topic=config.ntfy_topic,
            ntfy_token=config.ntfy_token,
            level=level,
            magnitude=magnitude,
            distance_km=est.distance_km,
            mmi=est.estimated_mmi,
            depth_km=depth_km,
            region=region,
            tsunami_flag=tsunami_flag,
            test_marker=True,
        )
    )
    print("hecho -- revisa el celular/dashboard suscrito al topic de ntfy.")


if __name__ == "__main__":
    main()
