from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    database_url: str

    emsc_ws_url: str

    usgs_base_url: str
    usgs_poll_interval_s: int
    usgs_window_minutes: int
    usgs_min_magnitude_global: float
    usgs_min_magnitude_chile: float

    csn_url: str
    csn_poll_interval_s: int

    db_command_timeout_s: float

    log_level: str


def load_config() -> Config:
    return Config(
        database_url=os.environ.get(
            "DATABASE_URL", "postgresql://sismos:sismos@localhost:5432/sismos"
        ),
        emsc_ws_url=os.environ.get(
            "EMSC_WS_URL", "wss://www.seismicportal.eu/standing_order/websocket"
        ),
        usgs_base_url=os.environ.get(
            "USGS_BASE_URL", "https://earthquake.usgs.gov/fdsnws/event/1/query"
        ),
        usgs_poll_interval_s=int(os.environ.get("USGS_POLL_INTERVAL_S", "60")),
        usgs_window_minutes=int(os.environ.get("USGS_WINDOW_MINUTES", "30")),
        usgs_min_magnitude_global=float(
            os.environ.get("USGS_MIN_MAGNITUDE_GLOBAL", "4.0")
        ),
        usgs_min_magnitude_chile=float(
            os.environ.get("USGS_MIN_MAGNITUDE_CHILE", "2.5")
        ),
        csn_url=os.environ.get(
            "CSN_URL", "https://api.gael.cloud/general/public/sismos"
        ),
        csn_poll_interval_s=int(os.environ.get("CSN_POLL_INTERVAL_S", "300")),
        db_command_timeout_s=float(os.environ.get("DB_COMMAND_TIMEOUT_S", "30")),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
