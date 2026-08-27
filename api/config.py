from __future__ import annotations

import os
from dataclasses import dataclass


def _require_float(name: str) -> float:
    """No default: see daemon/config.py's copy of this same guard. Both
    services must agree on the real HOME_LAT/HOME_LON (infra/.env) --
    silently falling back to a placeholder here would show the dashboard a
    location that doesn't match what the daemon actually scored events
    against."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        raise RuntimeError(
            f"{name} is required (no default) -- set it in infra/.env. "
            "See CLAUDE.md 'Motor de reglas'."
        )
    return float(raw)


@dataclass(frozen=True)
class Config:
    database_url: str
    cors_origins: list[str]
    log_level: str
    home_lat: float
    home_lon: float
    home_label: str
    poll_interval_s: int
    usgs_poll_interval_s: int
    csn_poll_interval_s: int


def load_config() -> Config:
    return Config(
        database_url=os.environ.get(
            "DATABASE_URL", "postgresql://sismos:sismos@localhost:5432/sismos"
        ),
        # Kiosk tablet + local network only for now; tighten once infra/Caddy
        # (fase 4) puts this behind a real origin.
        cors_origins=[
            o.strip()
            for o in os.environ.get("CORS_ORIGINS", "*").split(",")
            if o.strip()
        ],
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        # Mismos valores requeridos que daemon/config.py -- el dashboard
        # necesita esta ubicación para el mapa, el rumbo de cada evento y la
        # barra superior, y la API es de solo lectura (CLAUDE.md), así que
        # no calcula nada nuevo: solo expone la misma config que ya usa el
        # daemon para el GMPE. HOME_LAT/HOME_LON vienen de infra/.env (un
        # solo lugar) para los dos servicios vía docker-compose.yml, así que
        # no pueden desincronizarse entre sí.
        home_lat=_require_float("HOME_LAT"),
        home_lon=_require_float("HOME_LON"),
        home_label=os.environ.get("HOME_LABEL", "Casa"),
        poll_interval_s=int(os.environ.get("POLL_INTERVAL_S", "30")),
        # Mismos nombres/defaults que daemon/config.py -- ver GET /api/config
        # en routers/config.py. El dashboard los usa para juzgar la salud de
        # cada fuente por su propia cadencia (CSN cada 5 min, USGS cada 60s)
        # en vez de mostrar segundos crudos sin contexto (CLAUDE.md, Fase 5).
        usgs_poll_interval_s=int(os.environ.get("USGS_POLL_INTERVAL_S", "60")),
        csn_poll_interval_s=int(os.environ.get("CSN_POLL_INTERVAL_S", "300")),
    )
