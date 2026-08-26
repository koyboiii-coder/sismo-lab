"""Validates the local-intensity pipeline (intensity.py) against synthetic
scenarios spanning the range the daemon actually has to get right: close-in
moderate events and the M8+ subduction megathrust case, not just the distant
M2.5-3.6 events that make up the real event history so far (all of which
land at MMI ~1, the floor of the scale -- see the docstring on why that's
not evidence the GMPE works anywhere else on the curve).

Pure computation against intensity.py's public functions. Never touches the
database and never imports db.py/asyncpg -- this is meant to run on a
laptop without a Postgres connection, not just on the Pi. No network access
either: the finite-fault demonstration scenarios below use hand-built
synthetic rupture geometry, not a real USGS payload (see their docstring).

Usage:
    python validate_intensity.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import intensity
from dedup import EARTH_RADIUS_KM

# Wald et al. (1999) MMI ranges, abbreviated -- used here only to label each
# computed MMI with what it's supposed to mean, so a number like "4.37"
# reads as something checkable against real-world expectation instead of an
# opaque float.
_MMI_LABELS = {
    1: ("I", "No sentido"),
    2: ("II-III", "Debil -- sentido por pocas personas en reposo, objetos colgantes oscilan"),
    4: ("IV", "Sentido por muchos en interiores, vajilla y ventanas vibran"),
    5: ("V", "Sentido por casi todos, algunos objetos vuelcan, ventanas pueden romperse"),
    6: ("VI", "Sentido por todos, muebles se mueven, dano leve"),
    7: ("VII", "Dificil mantenerse de pie, dano leve-moderado en construccion normal"),
    8: ("VIII", "Dano moderado-severo en construccion normal, chimeneas caen"),
    9: ("IX", "Dano severo, edificios desplazados de su cimiento"),
    10: ("X+", "Destruccion generalizada"),
}


def _mmi_label(mmi: float) -> tuple[str, str]:
    # _MMI_LABELS keys are the floor of the ranges above; II and III are
    # merged in Wald et al.'s own bilinear fit (no distinct breakpoint
    # between them), hence no separate "3" entry.
    key = 1
    for k in sorted(_MMI_LABELS):
        if mmi >= k:
            key = k
    return _MMI_LABELS[key]


# Synthetic global coordinate frame for this script only -- HOME is fixed at
# (0, 0) and every scenario's hypocenter is placed due south of it, at
# longitude 0, so epicentral distance is pure north-south and exactly
# `epicentral_km` (haversine along a meridian has no cos(lat) term to
# approximate away). Deliberately decoupled from config.py's real
# HOME_LAT/HOME_LON -- this is a validation fixture, not a deployment.
_KM_PER_DEG_LAT = math.pi * EARTH_RADIUS_KM / 180  # ~111.19
_HOME_LAT, _HOME_LON = 0.0, 0.0


def _hypocenter_south_of_home(epicentral_km: float) -> float:
    return -epicentral_km / _KM_PER_DEG_LAT


def _synthetic_rupture_vertices(
    hypocenter_lat: float, rupture_length_km: float, top_depth_km: float, bottom_depth_km: float
) -> list[tuple[float, float, float]]:
    """A hand-built rupture surface for the finite-fault demonstration
    scenarios below -- NOT a real USGS rupture.json. Strikes due north from
    the hypocenter (toward HOME) for `rupture_length_km`, with an updip row
    at `top_depth_km` and a downdip row at `bottom_depth_km`, six segments.
    Longitude held at 0 throughout (no dip-direction offset) since only the
    along-strike distance matters for what this is demonstrating: that real
    geometry, unlike the Wells & Coppersmith worst-case floor, can place the
    *end* of a rupture short of a site and report a genuinely larger,
    non-saturated Rrup.
    """
    vertices = []
    for i in range(7):
        lat = hypocenter_lat + (i / 6) * (rupture_length_km / _KM_PER_DEG_LAT)
        vertices.append((lat, 0.0, top_depth_km))
        vertices.append((lat, 0.0, bottom_depth_km))
    return vertices


@dataclass(frozen=True)
class Scenario:
    name: str
    magnitude: float
    epicentral_km: float
    depth_km: float
    historical_note: str
    # Only set for the finite-fault demonstration scenarios at the end.
    synthetic_rupture_length_km: Optional[float] = None
    synthetic_rupture_top_km: float = 15.0
    synthetic_rupture_bottom_km: float = 45.0


SCENARIOS = [
    Scenario(
        "M8.8 interplaca (tipo Maule 2010)", 8.8, 350.0, 35.0,
        "27-F 2010: epicentro frente a Cauquenes. Santiago, a ~325-340 km "
        "epicentrales, registro MMI VII-VIII y PGA observado del orden de "
        "0.2-0.3 g (varias estaciones RENADIC/CSN). Concepcion, mucho mas "
        "cerca de la zona de ruptura (~100 km), llego a MMI IX.",
    ),
    Scenario(
        "M7.6 interplaca", 7.6, 100.0, 30.0,
        "Sin anclaje a un evento historico puntual -- referencia es la "
        "expectativa general para M7+ a 100 km: MMI VI-VII en la zona "
        "epicentral segun USGS ShakeMap para eventos comparables.",
    ),
    Scenario(
        "M6.5 interplaca", 6.5, 50.0, 20.0,
        "Sin anclaje historico especifico. Expectativa general: MMI VI-VII "
        "cerca del epicentro para M6.5 somero.",
    ),
    Scenario(
        "M5.5 cortical somero", 5.5, 30.0, 15.0,
        "Sin anclaje historico especifico. Expectativa general: MMI IV-V, "
        "sentido ampliamente, dano leve poco probable a esta magnitud.",
    ),
    Scenario(
        "M4.5 cortical somero", 4.5, 20.0, 10.0,
        "Sin anclaje historico especifico. Expectativa general: MMI III-IV, "
        "sentido localmente, sin dano.",
    ),
    Scenario(
        "M4.0 lejano", 4.0, 100.0, 40.0,
        "Expectativa general: MMI I-II, tipicamente imperceptible a esta "
        "distancia.",
    ),
    Scenario(
        "M6.0 intraplaca profundo", 6.0, 200.0, 100.0,
        "Sin anclaje historico especifico. Eventos intraplaca profundos "
        "chilenos comparables (p.ej. 100+ km) suelen sentirse en un area "
        "amplia pero con intensidad moderada: MMI III-IV esperable a esta "
        "distancia.",
    ),
    Scenario(
        "M8.8 interplaca, extremo cercano", 8.8, 100.0, 35.0,
        "Mismo evento tipo-Maule, epicentro mucho mas cerca (comparable a la "
        "distancia Concepcion-epicentro real del 27-F, donde se observo "
        "MMI IX). Incluido para ver el otro extremo de la curva "
        "distancia-intensidad del mismo escenario magnitud-profundidad.",
    ),
]

# Finite-fault demonstration: same M8.8 @ 350 km and M8.8 @ 100 km pair as
# above, but now each gets a synthetic (not real-USGS) 250 km rupture
# extending from its own hypocenter toward HOME. 250 km is deliberately
# shorter than Wells & Coppersmith's ~483 km estimate for M8.8 -- real
# ruptures vary around that regression, and a shorter one makes a clearer
# demonstration: at 350 km the rupture's near end falls ~100 km short of
# HOME (a genuine, non-floor Rrup), while at 100 km HOME sits astride the
# rupture (Rrup collapses to the shallow updip depth). See
# _synthetic_rupture_vertices's docstring.
FINITE_FAULT_SCENARIOS = [
    Scenario(
        "M8.8 finite-fault @ 350 km", 8.8, 350.0, 35.0,
        "DEMOSTRACION SINTETICA (no es un payload real de USGS) -- mismo "
        "evento y distancia que el escenario tipo-Maule arriba, pero con "
        "geometria de ruptura real disponible en vez del fallback de "
        "Wells & Coppersmith.",
        synthetic_rupture_length_km=250.0,
    ),
    Scenario(
        "M8.8 finite-fault @ 100 km", 8.8, 100.0, 35.0,
        "DEMOSTRACION SINTETICA (no es un payload real de USGS) -- mismo "
        "evento y distancia que el escenario 'extremo cercano' arriba, con "
        "geometria de ruptura real.",
        synthetic_rupture_length_km=250.0,
    ),
]


def _run_scenario(s: Scenario) -> tuple[intensity.IntensityEstimate, float]:
    hypocenter_lat = _hypocenter_south_of_home(s.epicentral_km)
    rupture_vertices = None
    if s.synthetic_rupture_length_km is not None:
        rupture_vertices = _synthetic_rupture_vertices(
            hypocenter_lat,
            s.synthetic_rupture_length_km,
            s.synthetic_rupture_top_km,
            s.synthetic_rupture_bottom_km,
        )
    est = intensity.estimate(
        latitude=hypocenter_lat,
        longitude=0.0,
        depth_km=s.depth_km,
        magnitude=s.magnitude,
        home_lat=_HOME_LAT,
        home_lon=_HOME_LON,
        rupture_vertices=rupture_vertices,
    )
    return est, hypocenter_lat


def _print_table(scenarios: list[Scenario]) -> None:
    header = (
        f"{'Escenario':<34} {'M':>4} {'Repi':>6} {'H':>5} {'Rhipo':>7} {'Rrup':>7} "
        f"{'PGA(g)':>10} {'PGA(gal)':>9} {'MMI':>6} {'Mercalli':>10} "
        f"{'Geometria':>17} {'Sat.':>5} {'Umbral':>18}"
    )
    print(header)
    print("-" * len(header))

    for s in scenarios:
        est, _ = _run_scenario(s)
        pga_gal = est.estimated_pga * intensity._G_TO_GAL
        roman, _desc = _mmi_label(est.estimated_mmi)

        if est.estimated_mmi >= 5.0 or s.magnitude >= intensity.GLOBAL_SIGNIFICANT_MAGNITUDE:
            threshold = "ALERTA (>=V)" if est.estimated_mmi >= 5.0 else "global (M>=6.5)"
        elif est.estimated_mmi >= intensity.LOCAL_SIGNIFICANT_MMI:
            threshold = "notif. silenciosa"
        else:
            threshold = "solo listado"

        print(
            f"{s.name:<34} {s.magnitude:>4.1f} {s.epicentral_km:>6.0f} {s.depth_km:>5.0f} "
            f"{est.distance_km:>7.1f} {est.rrup_km:>7.1f} {est.estimated_pga:>10.5f} "
            f"{pga_gal:>9.1f} {est.estimated_mmi:>6.2f} {roman:>10} "
            f"{est.geometry_source:>17} {str(est.distance_saturated):>5} {threshold:>18}"
        )


def main() -> None:
    _print_table(SCENARIOS)

    print()
    print("Notas historicas / contraste con la escala Mercalli:")
    for s in SCENARIOS:
        print(f"\n- {s.name}: {s.historical_note}")

    print()
    print("=" * 78)
    print("INVESTIGACION: M7.6@100km y M6.5@50km con el mismo PGA a 4 decimales")
    print("=" * 78)
    print(
        "No hay clamp ni techo -- se revisaron los valores con mas precision:\n"
        "  M7.6 @ 100 km, H=30 km: PGA = 0.0709673592 g\n"
        "  M6.5 @  50 km, H=20 km: PGA = 0.0710153899 g\n"
        "Difieren al quinto decimal (~0.07%); coincidian en la tabla original\n"
        "solo porque esta se imprimia a 4 decimales. La cercania es real, no un\n"
        "bug, y viene del termino de saturacion cercana de Youngs et al. (1997),\n"
        "A4*exp(A5*M) en el denominador logaritmico: ese termino crece con M\n"
        "(120.1 km de 'radio' efectivo para M7.6, 65.3 km para M6.5) para evitar\n"
        "PGA infinito en R=0 en eventos grandes. Para estos dos escenarios en\n"
        "particular, el termino de magnitud directa (A2*M) y el de distancia\n"
        "(C3*ln(R+termino de saturacion)) casi se cancelan entre si, y la\n"
        "diferencia de profundidad (30 vs 20 km, termino A6*H) casi cierra el\n"
        "resto de la brecha -- una coincidencia de los R elegidos para el\n"
        "escenario, no una propiedad rota del modelo. La tabla ahora imprime\n"
        "PGA(g) a 5 decimales para que esto no vuelva a parecer un techo.\n"
    )

    print("=" * 78)
    print("CORRECCION APLICADA: distancia a la ruptura via Wells & Coppersmith")
    print("=" * 78)
    print(
        "intensity.py ahora calcula una distancia de ruptura (Rrup) antes de\n"
        "llamar a youngs_1997_pga_g(), en vez de pasarle la distancia\n"
        "hipocentral directamente -- ver rupture_distance_km() en intensity.py\n"
        "para el detalle completo. Resumen: Wells & Coppersmith (1994, reverse)\n"
        "da una longitud de ruptura L a partir de M; Rrup = max(Rhipo - L,\n"
        "depth_km), el limite geometrico de peor caso (la ruptura se extiende\n"
        "su largo completo hacia el sitio), acotado por abajo por la\n"
        "profundidad -- un sitio no puede estar mas cerca de la falla, en 3D,\n"
        "que su distancia vertical a ella.\n"
        "\n"
        "Efecto en el escenario tipo-Maule (M8.8 @ 350 km, H=35 km):\n"
        "  L(M8.8) = 483 km  =>  Rrup = max(351.7 - 483, 35) = 35 km (piso)\n"
        "  MMI: 4.37 (IV, sin la correccion) -> 7.10 (VII, con ella) -- ver tabla\n"
        "Con Rrup en el piso de profundidad, el modelo llega a MMI ~VII, en el\n"
        "rango de lo observado en Santiago en 2010 (VII-VIII), y ahora SI cruza\n"
        "el umbral de alerta completa (MMI >= V) de CLAUDE.md.\n"
        "\n"
        "El escenario '@ 100 km' cae en el MISMO piso de profundidad (35 km) y\n"
        "por lo tanto en la misma MMI que el de 350 km -- no es un bug: L=483 km\n"
        "ya excede ambas distancias hipocentrales (351.7 y 106.0 km), asi que el\n"
        "limite de peor caso satura en ambos casos. Es el precio explicito de no\n"
        "tener geometria de falla real: para magnitudes cuyo largo de ruptura\n"
        "alcanza o supera la distancia al hipocentro, el modelo deja de\n"
        "distinguir '350 km' de '100 km' porque, en el peor caso, la falla\n"
        "podria pasar bajo el sitio en cualquiera de los dos. Los escenarios\n"
        "M4.0-M6.5 (rupturas de <20 km) practicamente no se ven afectados --\n"
        "Rrup ~ Rhipo sigue siendo valido ahi. Este es exactamente el caso que\n"
        "intensity_distance_saturated marca como True (ver tabla, columna 'Sat.').\n"
    )

    print("=" * 78)
    print("INCERTIDUMBRE: intensity_geometry_source / intensity_distance_saturated")
    print("=" * 78)
    print(
        "Cada IntensityEstimate ahora expone de donde salio su Rrup:\n"
        "'wells_coppersmith' (aproximacion por magnitud, la unica disponible\n"
        "hasta ahora) o 'finite_fault' (geometria real de ruptura de USGS, ver\n"
        "connectors/usgs.fetch_rupture_geometry -- solo M>=7, y solo cuando USGS\n"
        "publico un modelo real, no un placeholder de tipo punto). Persistido en\n"
        "events.intensity_geometry_source / events.intensity_distance_saturated,\n"
        "expuesto por la API (api/notifier.py) para que el dashboard pueda\n"
        "mostrar 'MMI VII estimado -- geometria de falla desconocida' en vez de\n"
        "un numero que aparenta mas precision de la que tiene, exactamente\n"
        "cuando distance_saturated=True.\n"
    )

    print("=" * 78)
    print("FINITE-FAULT: recuperando discriminacion de distancia (demostracion)")
    print("=" * 78)
    print(
        "Los dos escenarios abajo son sinteticos (construidos por este script,\n"
        "no un payload real de USGS -- ver _synthetic_rupture_vertices), pero\n"
        "ejercitan el mismo camino de codigo que un M8.8 real con ShakeMap\n"
        "rupture.json disponible: mismo M8.8/350km y M8.8/100km de arriba, con\n"
        "una ruptura de 250 km (mas corta que el largo Wells & Coppersmith de\n"
        "483 km -- las rupturas reales varian en torno a esa regresion)\n"
        "extendiendose desde cada hipocentro hacia HOME.\n"
    )
    _print_table(FINITE_FAULT_SCENARIOS)
    print(
        "\n"
        "A 350 km, el extremo de la ruptura sintetica queda ~100 km corto de\n"
        "HOME: Rrup real (~101 km) es MAYOR que el piso de Wells & Coppersmith\n"
        "(35 km) -- la geometria real muestra que el peor caso de W&C era, en\n"
        "efecto, pesimista para este caso, y el MMI baja de vuelta a un rango\n"
        "mas moderado (con geometry_source='finite_fault' y saturated=False,\n"
        "asi que el dashboard puede mostrarlo con confianza, no como cota).\n"
        "\n"
        "A 100 km, HOME cae dentro del tramo de la ruptura sintetica: Rrup real\n"
        "(~22 km -- el vertice de la malla mas cercano no cae exactamente sobre\n"
        "HOME, asi que queda algo por encima de los 15 km del borde superior/\n"
        "updip) es igual MENOR que el piso de W&C (35 km) -- aqui la geometria\n"
        "real confirma que el sitio esta cerca de la falla, mas de lo que W&C\n"
        "asumia, aunque no literalmente encima.\n"
        "\n"
        "El punto central: los dos escenarios ahora dan MMI DISTINTA entre si\n"
        "(a diferencia del par equivalente con el fallback de W&C, que colapsaba\n"
        "ambos a la misma MMI 7.10 saturada) -- geometria real recupera la\n"
        "discriminacion por distancia que el fallback, por diseno, no puede dar.\n"
    )


if __name__ == "__main__":
    main()
