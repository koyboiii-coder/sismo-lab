"""Local shaking-intensity pipeline, per CLAUDE.md's "Motor de reglas"
section: hypocentral distance -> a rupture-distance (Rrup) estimate -> a
subduction-zone GMPE for PGA -> a PGA-to-MMI conversion. Pure functions --
`db.Writer` calls `estimate()` after every insert/recanonicalization of an
`events` row and writes the result alongside the canonical fields in the
same statement, so distance_km/estimated_pga/estimated_mmi/is_significant/
intensity_geometry_source/intensity_distance_saturated are always in sync
with whatever the current canonical origin/magnitude/depth are.

Rrup (distance to the rupture, not the hypocenter) comes from one of two
places, in priority order:

1. Real USGS-published rupture geometry (`rupture_vertices` -- see
   connectors/usgs.fetch_rupture_geometry), when it exists.
2. Otherwise, a Wells & Coppersmith (1994) magnitude-only worst-case
   approximation (`rupture_distance_km`) -- see its docstring for why this
   matters and what "worst case" means here.

Which one was used, and whether (2) hit its saturation floor, is recorded
on `IntensityEstimate` so callers -- ultimately the dashboard -- can
qualify estimated_mmi instead of presenting it as more precise than it is.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from dedup import haversine_km

# Youngs, Chiou, Silva & Humphrey (1997), "Strong Ground Motion Attenuation
# Relationships for Subduction Zone Earthquakes", Seismological Research
# Letters 68(1), pp. 58-73, Table 2. Rock-site coefficients -- this daemon
# has no Vs30/site-class data, so rock is the only condition implemented.
# Verified against the OpenQuake hazardlib reference implementation
# (openquake.hazardlib.gsim.youngs_1997: CONSTS rock = A1..A7 below;
# COEFFS_ROCK's PGA-period row gives C1=C2=0, C3=-2.552).
_YOUNGS_A1 = 0.2418
_YOUNGS_A2 = 1.414
_YOUNGS_A4 = 1.7818
_YOUNGS_A5 = 0.554
_YOUNGS_A6 = 0.00607
_YOUNGS_A7 = 0.3846  # interface/intraslab (Zt) step
_YOUNGS_C3_ROCK = -2.552

# The model isn't calibrated for depths this large; deep-focus events
# elsewhere in the world (600+ km, seen via the global EMSC/USGS feeds)
# would otherwise extrapolate the depth term into nonsense.
_MAX_MODELED_DEPTH_KM = 100.0

# Wells & Coppersmith (1994), "New Empirical Relationships among Magnitude,
# Rupture Length, Rupture Width, Rupture Area, and Surface Displacement",
# BSSA 84(4), pp. 974-1002, Table 2A: subsurface rupture length (SRL, km)
# regressed on moment magnitude, reverse-mechanism events --
#   log10(SRL) = a + b*Mw
# WC94 predates a distinct "subduction interface" category; reverse is the
# standard stand-in used in practice for thrust earthquakes, which is what
# both interface and intraslab subduction events are. Known to underpredict
# for M >= 8.5 (its catalog had few events that large), which only makes
# the conservative floor below more conservative, not less.
_WC94_REVERSE_A = -2.86
_WC94_REVERSE_B = 0.63

# CLAUDE.md asks to distinguish interface (interplaca) from intraslab
# (intraplaca) "por profundidad si es posible" -- this threshold is that
# simplification, not a real trench-geometry classification.
_INTERFACE_MAX_DEPTH_KM = 50.0

# Wald, Quitoriano, Heaton & Kanamori (1999), "Relationships between Peak
# Ground Acceleration, Peak Ground Velocity, and Modified Mercalli
# Intensity in California", Earthquake Spectra 15(3), pp. 557-564. Bilinear
# fit of MMI against log10(PGA in cm/s^2). Verified against USGS's own
# production GMICE implementation (esi_shakelib.gmice.wald99.Wald99):
# Imm = C2 + C1*log10(PGA_gal) for log10(PGA_gal) >= 1.82 (Imm >= ~V)
# Imm = C4 + C3*log10(PGA_gal) otherwise
_WALD_C1 = 3.66
_WALD_C2 = -1.66
_WALD_C3 = 2.20
_WALD_C4 = 1.00
_WALD_BREAKPOINT_LOG10_GAL = 1.82
_G_TO_GAL = 981.0  # matches the constant used in USGS's own implementation

GLOBAL_SIGNIFICANT_MAGNITUDE = 6.5
LOCAL_SIGNIFICANT_MMI = 3.0  # MMI III
FULL_ALERT_MMI = 5.0  # MMI V -- CLAUDE.md's "alerta completa" threshold

# Roman-numeral MMI labels per Wald et al. (1999)'s own ranges (bilinear fit
# has no distinct breakpoint between II and III, hence no separate "3" key
# here -- same reasoning as validate_intensity.py's table). Shared by
# alerts.py (notification text) and validate_intensity.py (its table).
MMI_ROMAN = {
    1: "I", 2: "II-III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII", 9: "IX", 10: "X+",
}


def mmi_roman(mmi: float) -> str:
    key = 1
    for k in sorted(MMI_ROMAN):
        if mmi >= k:
            key = k
    return MMI_ROMAN[key]

# `IntensityEstimate.geometry_source` values -- what the Rrup fed into the
# GMPE was actually based on. Surfaced all the way to the API/dashboard (see
# events.intensity_geometry_source) so a number like "MMI VII" can be shown
# next to how much to trust it: real modeled rupture geometry, or a
# magnitude-only worst-case guess.
GEOMETRY_SOURCE_FINITE_FAULT = "finite_fault"
GEOMETRY_SOURCE_WELLS_COPPERSMITH = "wells_coppersmith"


def hypocentral_distance_km(epicentral_km: float, depth_km: float) -> float:
    return math.sqrt(epicentral_km ** 2 + depth_km ** 2)


def wells_coppersmith_rupture_length_km(magnitude: float) -> float:
    return 10 ** (_WC94_REVERSE_A + _WC94_REVERSE_B * magnitude)


def rupture_distance_km(
    hypocentral_km: float, magnitude: float, depth_km: float
) -> tuple[float, bool]:
    """Reduces a point-source hypocentral distance toward a rupture-distance
    (Rrup) proxy, per Wells & Coppersmith (1994) -- see validate_intensity.py
    for why this matters: without it, great earthquakes come out far too
    weak at any distance beyond their rupture's own near-field. This is the
    fallback used when no real rupture geometry is available -- see
    `finite_fault_rupture_distance_km` for when USGS has actually published
    one (M >= 7, and only for events with a modeled fault, not every event
    -- see connectors/usgs.fetch_rupture_geometry).

    youngs_1997_pga_g() takes distance from a single hypocenter point as a
    stand-in for Rrup (distance to the closest point of the rupture plane),
    which is a fine approximation when the rupture is small relative to how
    far away the site is -- but it breaks down for great earthquakes. A
    M8.8 interface rupture is ~500 km long (see
    wells_coppersmith_rupture_length_km); a site 350 km from the
    *hypocenter* can be far closer to the *rupture* if it happens to extend
    that way. Maule 2010 nucleated off Cauquenes and propagated ~300 km
    north, bringing Santiago (~330 km from the hypocenter) much closer to
    the fault than hypocentral distance alone suggests.

    Without real geometry we can't know which way a given rupture actually
    extended, so this takes the worst case: the rupture extends its full
    modeled length toward the site. That's a hard geometric bound, not a
    guess -- for a rupture of length L that contains the hypocenter, no
    point on it is farther from the site than the hypocenter is, and the
    closest point can be no closer than (hypocentral_distance - L).
    Deliberately conservative (biases toward *overestimating* shaking for
    large, distant-but-within-reach ruptures) -- the correct failure mode
    for a local alerting system per CLAUDE.md rule 3: a missed alert is
    worse than an occasional early one.

    Floored at depth_km: even in the worst case a site can't be closer to
    the rupture, in 3D, than the vertical distance to it (Rrup can't go
    below Rjb=0, directly above the fault) -- the same degeneracy
    hypocentral_distance_km itself has as epicentral distance -> 0.

    Returns (distance_km, saturated). `saturated` is True exactly when the
    depth floor was the binding constraint -- i.e. the event's own
    approximated rupture length already reaches (or exceeds) the
    hypocentral distance, so this worst-case bound can no longer
    distinguish this event from one genuinely closer in. That's not a bug:
    it's this function honestly reporting that, absent real geometry, it
    has hit the limit of what a point hypocenter + a length estimate can
    tell you. Callers surface this (events.intensity_distance_saturated)
    so the estimated MMI can be shown as an uncertain worst-case bound
    rather than a precise figure -- e.g. a M8.8 event at both 350 km and
    100 km hits the same floor at depth_km=35 and reports the same
    saturated MMI for both.
    """
    rupture_length_km = wells_coppersmith_rupture_length_km(magnitude)
    floor_bound = hypocentral_km - rupture_length_km
    if floor_bound <= depth_km:
        return depth_km, True
    return floor_bound, False


def finite_fault_rupture_distance_km(
    home_lat: float, home_lon: float, rupture_vertices: list[tuple[float, float, float]]
) -> float:
    """Rrup from real USGS rupture geometry: the minimum 3D distance from
    home to any vertex of the modeled rupture surface (see
    connectors/usgs.fetch_rupture_geometry for where `rupture_vertices`
    comes from -- ShakeMap's rupture.json, (lat, lon, depth_km) triples).

    This is an approximation in its own right: the true Rrup is the
    distance to the closest *point on the rupture surface*, which can fall
    strictly between two vertices (e.g. the middle of a fault-patch edge
    facing the site), not just at a corner. Using only vertices
    underestimates the true minimum slightly less often than it
    overestimates it in practice, since ShakeMap's rupture.json patches are
    typically dense enough (tens of km between corners at most) that a
    site meaningfully far from every vertex is also far from every patch --
    but for a site very close to the rupture, this can be a few km off
    either way. Good enough to recover real distance discrimination
    between events, which is the whole point of using this over the
    Wells & Coppersmith worst-case floor.
    """
    if not rupture_vertices:
        raise ValueError("rupture_vertices must be non-empty")
    return min(
        hypocentral_distance_km(haversine_km(home_lat, home_lon, vlat, vlon), vdepth)
        for vlat, vlon, vdepth in rupture_vertices
    )


def youngs_1997_pga_g(magnitude: float, rupture_distance_km: float, depth_km: float) -> float:
    """PGA in g, on rock, per Youngs et al. (1997). `rupture_distance_km`
    (Rrup) is computed by the caller -- either from real USGS rupture
    geometry or, when that isn't available, the Wells & Coppersmith
    worst-case approximation. See estimate()."""
    depth_for_model = min(max(depth_km, 0.0), _MAX_MODELED_DEPTH_KM)
    zt = 0.0 if depth_km < _INTERFACE_MAX_DEPTH_KM else 1.0
    # Avoid ln(<=0) for a hypothetical zero-distance source; harmless at
    # any real distance.
    r = max(rupture_distance_km, 1.0)

    ln_pga = (
        _YOUNGS_A1
        + _YOUNGS_A2 * magnitude
        + _YOUNGS_C3_ROCK * math.log(r + _YOUNGS_A4 * math.exp(_YOUNGS_A5 * magnitude))
        + _YOUNGS_A6 * depth_for_model
        + _YOUNGS_A7 * zt
    )
    return math.exp(ln_pga)


def wald_1999_mmi(pga_g: float) -> float:
    pga_gal = pga_g * _G_TO_GAL
    if pga_gal <= 0:
        return 1.0
    log_pga_gal = math.log10(pga_gal)
    if log_pga_gal >= _WALD_BREAKPOINT_LOG10_GAL:
        mmi = _WALD_C2 + _WALD_C1 * log_pga_gal
    else:
        mmi = _WALD_C4 + _WALD_C3 * log_pga_gal
    return min(max(mmi, 1.0), 10.0)


@dataclass(frozen=True)
class IntensityEstimate:
    distance_km: Optional[float]
    estimated_pga: Optional[float]
    estimated_mmi: Optional[float]
    is_significant: bool
    # None when no intensity was computed at all (no location/magnitude).
    # Otherwise GEOMETRY_SOURCE_FINITE_FAULT or GEOMETRY_SOURCE_WELLS_COPPERSMITH
    # -- what estimated_mmi's Rrup was actually based on. See
    # rupture_distance_km/finite_fault_rupture_distance_km.
    geometry_source: Optional[str]
    # True only when geometry_source is GEOMETRY_SOURCE_WELLS_COPPERSMITH and
    # its depth floor was the binding constraint -- see rupture_distance_km's
    # docstring. The dashboard should render estimated_mmi as an uncertain
    # worst-case bound ("MMI VII estimado, geometria de falla desconocida")
    # rather than a precise figure whenever this is True.
    distance_saturated: bool
    # The actual Rrup fed into youngs_1997_pga_g() -- not persisted on
    # `events` (distance_km, the hypocentral figure, is what's stored and
    # displayed per CLAUDE.md's schema), but exposed here for logging and
    # for validate_intensity.py, since it's the number that actually
    # explains estimated_pga/estimated_mmi.
    rrup_km: Optional[float]


def estimate(
    *,
    latitude: Optional[float],
    longitude: Optional[float],
    depth_km: Optional[float],
    magnitude: Optional[float],
    home_lat: float,
    home_lon: float,
    rupture_vertices: Optional[list[tuple[float, float, float]]] = None,
) -> IntensityEstimate:
    """Rule 3 in CLAUDE.md: never alert on magnitude alone. A magnitude >=
    6.5 event is still flagged significant (for the global-events panel)
    even without a local-intensity estimate, but that's the one exception
    -- everything else needs a real MMI computed from a real location.

    `rupture_vertices`, when given, is real USGS-published rupture geometry
    (see connectors/usgs.fetch_rupture_geometry) and takes priority over the
    Wells & Coppersmith worst-case fallback -- it's strictly better
    information when it exists, since it's an actual modeled fault rather
    than a magnitude-only length guess. Only ever populated for M >= 7
    USGS-sourced events that have a real (non-point) rupture model
    published, which in practice means it's absent far more often than
    present -- most events, including most M >= 7 ones, still go through
    the fallback.
    """
    globally_significant = magnitude is not None and magnitude >= GLOBAL_SIGNIFICANT_MAGNITUDE

    if latitude is None or longitude is None or depth_km is None or magnitude is None:
        return IntensityEstimate(None, None, None, globally_significant, None, False, None)

    epicentral_km = haversine_km(home_lat, home_lon, latitude, longitude)
    distance_km = hypocentral_distance_km(epicentral_km, depth_km)
    # distance_km (hypocentral, from the point hypocenter) is what's stored
    # and displayed -- CLAUDE.md's schema documents it as such. Only the
    # GMPE call gets the rupture-aware Rrup below.
    if rupture_vertices:
        rrup_km = finite_fault_rupture_distance_km(home_lat, home_lon, rupture_vertices)
        geometry_source = GEOMETRY_SOURCE_FINITE_FAULT
        distance_saturated = False
    else:
        rrup_km, distance_saturated = rupture_distance_km(distance_km, magnitude, depth_km)
        geometry_source = GEOMETRY_SOURCE_WELLS_COPPERSMITH

    pga_g = youngs_1997_pga_g(magnitude, rrup_km, depth_km)
    mmi = wald_1999_mmi(pga_g)

    is_significant = globally_significant or mmi >= LOCAL_SIGNIFICANT_MMI
    return IntensityEstimate(
        distance_km, pga_g, mmi, is_significant, geometry_source, distance_saturated, rrup_km
    )
