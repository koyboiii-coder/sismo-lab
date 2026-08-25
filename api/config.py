from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    database_url: str
    cors_origins: list[str]
    log_level: str


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
    )
