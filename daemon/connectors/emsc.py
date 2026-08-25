"""EMSC / SeismicPortal connector.

Persistent WebSocket, push-based, no polling. Reconnects with exponential
backoff (1s -> 60s cap) on any failure. `action` can be "insert" or
"update" and both must be processed; non-earthquake event types
(explosions, etc.) are filtered out via `evtype != "ke"`.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import websockets

from config import Config
from db import Writer
from models import ParsedEvent

logger = logging.getLogger(__name__)

SOURCE = "EMSC"


def parse(properties: dict) -> ParsedEvent:
    origin_time = datetime.fromisoformat(properties["time"].replace("Z", "+00:00"))
    return ParsedEvent(
        origin_time=origin_time.astimezone(timezone.utc),
        latitude=properties.get("lat"),
        longitude=properties.get("lon"),
        # properties.depth is positive km; geometry.coordinates has it
        # negative, so we deliberately read from properties here.
        depth_km=properties.get("depth"),
        magnitude=properties.get("mag"),
        magnitude_type=properties.get("magtype"),
        region=properties.get("flynn_region"),
        preferred_source=SOURCE,
    )


async def run(config: Config, writer: Writer, stop_event: asyncio.Event) -> None:
    backoff = 1
    while not stop_event.is_set():
        try:
            async with websockets.connect(
                config.emsc_ws_url, ping_interval=20, ping_timeout=20
            ) as ws:
                logger.info("[%s] connected", SOURCE)
                backoff = 1
                await writer.mark_source_ok(SOURCE)

                while not stop_event.is_set():
                    raw = await ws.recv()
                    try:
                        message = json.loads(raw)
                        action = message.get("action")
                        if action not in ("insert", "update"):
                            continue

                        feature = message.get("data", {})
                        properties = feature.get("properties", {})
                        if properties.get("evtype") != "ke":
                            continue

                        source_event_id = properties.get("unid")
                        if not source_event_id:
                            continue

                        parsed = parse(properties)
                        await writer.write_report(
                            SOURCE, source_event_id, message, parsed
                        )
                        await writer.mark_source_ok(SOURCE)
                    except Exception:
                        logger.exception("[%s] failed to process message", SOURCE)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("[%s] connection error: %s", SOURCE, exc)
            await writer.mark_source_error(SOURCE, str(exc))
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
