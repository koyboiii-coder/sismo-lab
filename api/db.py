from __future__ import annotations

import json
import logging
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)


async def _init_connection(conn: asyncpg.Connection) -> None:
    # Without this, jsonb columns (event_reports.payload) come back as raw
    # JSON text instead of parsed Python objects.
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


class Database:
    """Read-only pool for request handlers, plus one dedicated connection
    held open for LISTEN. A pooled connection can't be used for that: it
    gets handed back and reused by other queries between notifications, so
    the listener needs a connection of its own for the app's lifetime.
    """

    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool: Optional[asyncpg.Pool] = None
        self.listener_conn: Optional[asyncpg.Connection] = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(
            self.dsn, min_size=1, max_size=10, init=_init_connection
        )
        self.listener_conn = await asyncpg.connect(self.dsn)
        await _init_connection(self.listener_conn)

    async def close(self) -> None:
        if self.listener_conn is not None:
            await self.listener_conn.close()
        if self.pool is not None:
            await self.pool.close()
