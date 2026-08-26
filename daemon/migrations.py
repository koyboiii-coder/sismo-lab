"""Tiny SQL migration runner -- no Alembic (rule 5, CLAUDE.md: no heavy
dependencies on the Pi). Applies infra/postgres/init/*.sql in filename
order, tracked in `schema_migrations`, once at daemon startup before any
connector starts.

Why this exists: docker-entrypoint-initdb.d only runs on an empty Postgres
volume. A file added after a volume's first boot -- like 003_intensity.sql
was -- never runs on its own; it just sits there until something hits the
missing column at runtime as an UndefinedColumnError. This makes "apply
whatever's new" part of every startup instead of a manual `psql -f` step.
"""

from __future__ import annotations

import logging
from pathlib import Path

import asyncpg

logger = logging.getLogger(__name__)

_CREATE_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename   TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


async def run_pending(conn: asyncpg.Connection, migrations_dir: Path) -> None:
    await conn.execute(_CREATE_TRACKING_TABLE)
    applied = {r["filename"] for r in await conn.fetch("SELECT filename FROM schema_migrations")}
    files = sorted(migrations_dir.glob("*.sql"))

    if not applied and files and await conn.fetchval(
        "SELECT to_regclass('public.events') IS NOT NULL"
    ):
        # Nothing tracked yet, but the schema already exists: this volume was
        # bootstrapped by docker-entrypoint-initdb.d (which runs every *.sql
        # here unconditionally on an empty volume) or predates this runner.
        # Record what's already applied instead of re-running its DDL.
        logger.info(
            "schema_migrations is empty but the schema already exists -- "
            "seeding baseline from %d file(s) on disk without re-running them",
            len(files),
        )
        await conn.executemany(
            "INSERT INTO schema_migrations (filename) VALUES ($1)",
            [(f.name,) for f in files],
        )
        return

    for path in files:
        if path.name in applied:
            continue
        logger.info("applying pending migration: %s", path.name)
        async with conn.transaction():
            await conn.execute(path.read_text(encoding="utf-8"))
            await conn.execute(
                "INSERT INTO schema_migrations (filename) VALUES ($1)", path.name
            )
