from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/config")
async def get_config(request: Request):
    """Config de solo lectura para el frontend (web/): la ubicación HOME
    que el daemon ya usa para el GMPE (ver daemon/config.py) y el
    intervalo de sondeo esperado. No hay escritura ni cálculo nuevo acá,
    solo se expone lo que ya existe -- ver api/config.py."""
    config = request.app.state.config
    return {
        "home": {"lat": config.home_lat, "lon": config.home_lon, "label": config.home_label},
        "poll_interval_s": config.poll_interval_s,
        # Cadencia esperada por fuente, para que el dashboard pueda mostrar
        # salud verde/ámbar/gris relativa a lo normal de cada una, en vez de
        # un mismo umbral fijo para las tres. EMSC es push (WebSocket, sin
        # sondeo): null señala "sin cadencia que violar" -- su salud depende
        # solo de si la conexión está viva (source_health.consecutive_failures),
        # no de hace cuánto llegó el último mensaje (puede llevar horas sin
        # sismos y estar perfectamente sana).
        "source_cadence_s": {
            "CSN": config.csn_poll_interval_s,
            "USGS": config.usgs_poll_interval_s,
            "EMSC": None,
        },
    }
