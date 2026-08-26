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
    }
