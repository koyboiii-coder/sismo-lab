"""Post-event notifications via a self-hosted ntfy server.

Design stance -- informing fast, not warning early: EMSC/USGS/CSN all
publish 2-5 minutes after origin time (CLAUDE.md's own source notes: CSN
via gael.cloud updates ~every 5 min, USGS/EMSC are faster but still not
real-time). There is no useful anticipation window with these sources, so
this never tries to be an early-warning system -- see recompute.py/
db.Writer for the actual latency floor. The only lever available is
minimizing latency on the *notification*, which is why this fires from
whichever source reports an event crossing a threshold first, without
waiting for the other two to corroborate (see db.Writer._create_event /
_recanonicalize): a slightly-off first estimate that self-corrects in the
next NOTIFY is better than a precise one that's minutes later. CLAUDE.md's
existing revision/dedup machinery is what makes that acceptable -- the
dashboard's `updated`/`revision` fields already show a report is live and
subject to correction.

Levels follow CLAUDE.md's "Motor de reglas" table directly:

    MMI < III        -> no notification (still stored/listed)
    MMI III-IV       -> ALERT_SILENT  -- "notificacion silenciosa"
    MMI >= V         -> ALERT_FULL    -- "alerta completa"
    M >= 6.5 (global) -> no notification -- CLAUDE.md is explicit that this
                         tier is "sin alerta local", global-panel only

Never resend for a bare revision (rule 3: "Nunca reenviar alerta por una
revision salvo que la magnitud suba y cruce un umbral que no habia
cruzado antes") -- see should_notify().
"""

from __future__ import annotations

import logging
from typing import Optional

import aiohttp

import intensity

logger = logging.getLogger(__name__)

ALERT_SILENT = "silent"
ALERT_FULL = "full"

_LEVEL_RANK = {None: 0, ALERT_SILENT: 1, ALERT_FULL: 2}

# ntfy priority, 1 (min) - 5 (urgent) per its JSON publish API. "low" (2)
# is the closest fit to CLAUDE.md's "notificacion silenciosa" (no sound/
# vibration by default in ntfy clients); "high" (4) is what was explicitly
# asked for the full-alert tier, one step below ntfy's "urgent" (5, reserved
# for something this daemon has no basis to claim, like a confirmed
# evacuation order).
_NTFY_PRIORITY = {ALERT_SILENT: 2, ALERT_FULL: 4}

# Where to point someone when tsunami_flag is set. No consultable real-time
# API/feed exists for SHOA/SNAM bulletins (checked: shoa.cl and
# snamchile.cl are both JS-rendered pages meant for humans, not machines,
# and the only per-event PDFs found are general monthly digests, not live
# tsunami bulletins -- see the conversation that led to this being a link,
# not a scraper). snamchile.cl is SNAM's own site -- the official Chilean
# tsunami-alarm authority this notification is telling someone to go check.
_SHOA_SNAM_URL = "https://www.snamchile.cl"


def alert_level(mmi: Optional[float]) -> Optional[str]:
    """None (no notification), ALERT_SILENT, or ALERT_FULL. Deliberately
    takes only `mmi` -- CLAUDE.md's global M>=6.5 tier sets is_significant
    without a local MMI, and is explicitly "sin alerta local", so it must
    never reach this function as a reason to notify."""
    if mmi is None:
        return None
    if mmi >= intensity.FULL_ALERT_MMI:
        return ALERT_FULL
    if mmi >= intensity.LOCAL_SIGNIFICANT_MMI:
        return ALERT_SILENT
    return None


def should_notify(new_level: Optional[str], already_sent_level: Optional[str]) -> bool:
    """True only when `new_level` is a real tier strictly higher than
    whatever was already sent for this event -- covers both "never sent
    anything yet" (already_sent_level=None) and "escalated from silent to
    full" (CLAUDE.md's "cruce un umbral que no habia cruzado antes"). A
    revision that stays at the same tier, or drops to a lower one, must not
    re-notify."""
    if new_level is None:
        return False
    return _LEVEL_RANK[new_level] > _LEVEL_RANK.get(already_sent_level, 0)


def format_message(
    *,
    level: str,
    magnitude: Optional[float],
    distance_km: Optional[float],
    mmi: Optional[float],
    depth_km: Optional[float],
    region: Optional[str],
    tsunami_flag: bool,
    test_marker: bool = False,
) -> tuple[str, str, list[str]]:
    """Returns (title, body, ntfy_tags) in Chilean Spanish (CLAUDE.md rule
    6: UI-facing text, which this is, stays in Spanish even though the code
    around it doesn't).

    `test_marker` is set by simulate_alert.py for synthetic events injected
    to verify this chain end-to-end. It must make the notification
    unmistakable as a test on the receiving phone -- both in the title
    (visible in a lock-screen preview without opening anything) and as the
    very first line of the body -- since this is otherwise indistinguishable
    from a real MMI>=III/V notification."""
    mmi_label = intensity.mmi_roman(mmi) if mmi is not None else "?"
    mag_label = f"M{magnitude:.1f}" if magnitude is not None else "M?"
    title = f"Sismo {mag_label} -- MMI {mmi_label} estimada"
    if test_marker:
        title = f"[PRUEBA] {title}"

    lines = []
    if test_marker:
        lines.append(
            "*** ESTO ES UNA PRUEBA -- evento sintetico, no es un sismo real ***"
        )
    if tsunami_flag:
        lines.append(
            "⚠ Epicentro costero y superficial: potencial de tsunami. "
            f"Revisa el boletin oficial de SHOA/SNAM ({_SHOA_SNAM_URL}) y las "
            "alertas de SENAPRED antes de decidir evacuar -- este daemon no "
            "tiene forma de consultar el boletin real, solo estima la "
            "geometria del epicentro."
        )
    lines.append(f"Magnitud: {mag_label}")
    if distance_km is not None:
        lines.append(f"Distancia: {distance_km:.0f} km de tu ubicacion")
    lines.append(f"MMI estimada: {mmi_label}")
    if depth_km is not None:
        lines.append(f"Profundidad: {depth_km:.0f} km")
    if region:
        lines.append(f"Region: {region}")
    lines.append(
        "Aviso informativo posterior al evento (fuentes con 2-5 min de "
        "retraso) -- no es una alerta temprana."
    )

    tags = ["earthquake"]
    if tsunami_flag:
        tags += ["warning", "ocean"]
    if level == ALERT_FULL:
        tags.append("rotating_light")

    return title, "\n".join(lines), tags


async def send(
    *,
    ntfy_url: str,
    ntfy_topic: str,
    ntfy_token: str,
    level: str,
    magnitude: Optional[float],
    distance_km: Optional[float],
    mmi: Optional[float],
    depth_km: Optional[float],
    region: Optional[str],
    tsunami_flag: bool,
    test_marker: bool = False,
) -> None:
    """POSTs one ntfy notification, via ntfy's JSON publish API rather than
    its header-based shorthand -- the title/body here are Chilean Spanish
    with accents and an emoji, and plain HTTP headers are ASCII/Latin-1 by
    spec (ntfy's own docs note this), so putting them in a JSON body
    (UTF-8, like any JSON) avoids a header-mangling failure mode that would
    otherwise be silent (the POST still succeeds, the text just arrives
    garbled).

    Never raises -- rule 4 (graceful degradation): a notification-server
    hiccup must not be able to affect ingestion, which has already
    committed to Postgres by the time this is called (see
    db.Writer._send_alert)."""
    title, body, tags = format_message(
        level=level,
        magnitude=magnitude,
        distance_km=distance_km,
        mmi=mmi,
        depth_km=depth_km,
        region=region,
        tsunami_flag=tsunami_flag,
        test_marker=test_marker,
    )
    payload = {
        "topic": ntfy_topic,
        "title": title,
        "message": body,
        "priority": _NTFY_PRIORITY[level],
        "tags": tags,
    }
    if tsunami_flag:
        # One tap straight to SNAM instead of someone having to type the
        # URL out of the notification body during an actual emergency.
        payload["click"] = _SHOA_SNAM_URL
    # The server runs auth-default-access=deny-all (see
    # infra/docker-compose.yml + infra/ntfy-setup.sh) so publishing without
    # this token doesn't just skip a hardening step -- it gets rejected
    # outright. Logged as a warning below, not raised, per rule 4.
    headers = {"Authorization": f"Bearer {ntfy_token}"} if ntfy_token else {}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                ntfy_url, json=payload, headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
        logger.info("[alerts] sent %s notification: %s", level, title)
    except Exception:
        logger.warning(
            "[alerts] failed to send %s notification to %s (token configured: %s)",
            level, ntfy_url, bool(ntfy_token), exc_info=True,
        )
