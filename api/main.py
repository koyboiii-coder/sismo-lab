from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import load_config
from db import Database
from notifier import SEISMIC_CHANNEL, Broadcaster, make_notify_callback
from routers import config as config_router
from routers import events, health, notes, stream, version

config = load_config()
logging.basicConfig(
    level=config.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = Database(config.database_url)
    await db.connect()

    broadcaster = Broadcaster()
    notify_callback = make_notify_callback(db.pool, broadcaster)
    await db.listener_conn.add_listener(SEISMIC_CHANNEL, notify_callback)
    logger.info("listening on Postgres channel '%s'", SEISMIC_CHANNEL)

    app.state.db = db
    app.state.broadcaster = broadcaster
    app.state.config = config
    try:
        yield
    finally:
        await db.listener_conn.remove_listener(SEISMIC_CHANNEL, notify_callback)
        await db.close()


app = FastAPI(title="Sismos API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    # POST/DELETE agregados solo para /api/notes -- único endpoint de
    # escritura de la API (ver routers/notes.py, CLAUDE.md "Arquitectura").
    # Todo lo demás sigue siendo GET.
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

app.include_router(events.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(stream.router, prefix="/api")
app.include_router(config_router.router, prefix="/api")
app.include_router(version.router, prefix="/api")
app.include_router(notes.router, prefix="/api")
