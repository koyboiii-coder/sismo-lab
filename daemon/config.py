from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    database_url: str
    migrations_dir: Path

    emsc_ws_url: str

    usgs_base_url: str
    usgs_poll_interval_s: int
    usgs_window_minutes: int
    usgs_min_magnitude_global: float
    usgs_min_magnitude_chile: float

    csn_url: str
    csn_poll_interval_s: int

    home_lat: float
    home_lon: float
    # [recovery note: a comment likely stood here in the original file --
    # bytecode does not preserve comments, so this could not be recovered]
    ntfy_url: str
    ntfy_topic: str
    # [recovery note: same as above -- likely comment lost]
    ntfy_token: str

    db_command_timeout_s: float

    log_level: str


def load_config() -> Config:
    return Config(
        database_url=os.environ.get(
            "DATABASE_URL", "postgresql://sismos:sismos@localhost:5432/sismos"
        ),
        migrations_dir=Path(os.environ.get(
            "MIGRATIONS_DIR",
            str(Path(__file__).resolve().parent.parent / "infra" / "postgres" / "init"),
        )),
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
        home_lat=float(os.environ.get("HOME_LAT", "-36.8270")),
        home_lon=float(os.environ.get("HOME_LON", "-73.0498")),
        ntfy_url=os.environ.get("NTFY_URL", "http://ntfy:80"),
        ntfy_topic=os.environ.get("NTFY_TOPIC", "sismos"),
        ntfy_token=os.environ.get("NTFY_TOKEN", ""),
        db_command_timeout_s=float(os.environ.get("DB_COMMAND_TIMEOUT_S", "30")),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
