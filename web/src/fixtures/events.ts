/**
 * Datos de ejemplo para desarrollar sin el backend levantado (handoff §8,
 * punto 6). Forma idéntica a RawEvent/RawHealth/RawConfig -- la de la API
 * real, no la de handoff.md §7 -- para que el resto de la app no sepa si
 * está mirando fixtures o el backend real. Ver web/README.md para cómo
 * forzar cada escenario.
 */
import type { RawConfig, RawEvent, RawEventDetail, RawHealth } from "@/lib/types";

export const HOME_FIXTURE = { lat: -33.457, lon: -70.601, label: "Ñuñoa · Santiago" };

const AHORA = Date.now();
const horas = (n: number) => new Date(AHORA - n * 3_600_000).toISOString();
const dias = (n: number) => new Date(AHORA - n * 86_400_000).toISOString();

function evento(parcial: Partial<RawEvent> & Pick<RawEvent, "cluster_key" | "origin_time">): RawEvent {
  return {
    latitude: null,
    longitude: null,
    depth_km: null,
    magnitude: null,
    magnitude_type: "ML",
    region: null,
    distance_km: null,
    estimated_pga: null,
    estimated_mmi: null,
    intensity_geometry_source: null,
    intensity_distance_saturated: false,
    preferred_source: "CSN",
    is_significant: false,
    alert_sent_at: null,
    alert_level_sent: null,
    first_seen_at: parcial.origin_time,
    updated_at: parcial.origin_time,
    revision: 1,
    ...parcial,
  };
}

/** Actividad de fondo: eventos chicos repartidos por Chile, sin nada sentible. */
export const EVENTOS_BASE: RawEvent[] = [
  evento({
    cluster_key: "fx-001",
    origin_time: horas(0.5),
    latitude: -20.21, longitude: -68.9, depth_km: 108, magnitude: 3.2,
    region: "Calama, Antofagasta", preferred_source: "CSN",
    distance_km: 1180, estimated_mmi: 0.4, estimated_pga: 0.0003,
  }),
  evento({
    cluster_key: "fx-002",
    origin_time: horas(2),
    latitude: -33.02, longitude: -71.55, depth_km: 35, magnitude: 3.8,
    region: "Valparaíso", preferred_source: "USGS", magnitude_type: "Mw",
    distance_km: 92, estimated_mmi: 1.6, estimated_pga: 0.002,
  }),
  evento({
    cluster_key: "fx-003",
    origin_time: horas(5),
    latitude: -36.9, longitude: -73.05, depth_km: 22, magnitude: 4.1,
    region: "Talcahuano, Biobío", preferred_source: "CSN",
    distance_km: 410, estimated_mmi: 0.9, estimated_pga: 0.0008,
  }),
  evento({
    cluster_key: "fx-004",
    origin_time: horas(9),
    latitude: null, longitude: null, depth_km: 65, magnitude: 2.9,
    region: "49 km al SE de Socaire", preferred_source: "CSN",
    magnitude_type: "ML",
  }),
  evento({
    cluster_key: "fx-005",
    origin_time: horas(14),
    latitude: -30.6, longitude: -71.2, depth_km: 48, magnitude: 4.6,
    region: "Coquimbo", preferred_source: "USGS", magnitude_type: "Mw",
    distance_km: 540, estimated_mmi: 1.1, estimated_pga: 0.001,
  }),
  evento({
    cluster_key: "fx-006",
    origin_time: horas(22),
    latitude: -34.1, longitude: -70.7, depth_km: 112, magnitude: 3.5,
    region: "San José de Maipo, RM", preferred_source: "CSN",
    distance_km: 76, estimated_mmi: 0.7, estimated_pga: 0.0005,
  }),
  evento({
    cluster_key: "fx-007",
    origin_time: horas(30),
    latitude: -18.4, longitude: -69.4, depth_km: 115, magnitude: 4.3,
    region: "Arica y Parinacota", preferred_source: "EMSC", magnitude_type: "md",
    distance_km: 1720, estimated_mmi: 0.2, estimated_pga: 0.0001,
  }),
  // "Último sismo sentible" del handoff §3.2: M4.4, 22km NO de Valparaíso, MMI III, hace 3 días.
  evento({
    cluster_key: "fx-felt-1",
    origin_time: dias(3),
    latitude: -32.86, longitude: -71.85, depth_km: 28, magnitude: 4.4,
    region: "22 km NO de Valparaíso", preferred_source: "CSN",
    distance_km: 118, estimated_mmi: 3.2, estimated_pga: 0.004,
    is_significant: true, alert_level_sent: "silent",
    alert_sent_at: dias(3),
  }),
  // Mundial M6.5+, sin alerta local (CLAUDE.md: "sin alerta local").
  evento({
    cluster_key: "fx-world-1",
    origin_time: horas(38),
    latitude: 38.3, longitude: 142.4, depth_km: 32, magnitude: 6.7,
    region: "Costa este de Honshu, Japón", preferred_source: "USGS",
    magnitude_type: "Mw", distance_km: 17400, estimated_mmi: 0.0,
    is_significant: true,
  }),
  evento({
    cluster_key: "fx-world-2",
    origin_time: dias(2),
    latitude: -6.2, longitude: 130.1, depth_km: 140, magnitude: 6.5,
    region: "Islas Banda, Indonesia", preferred_source: "EMSC",
    magnitude_type: "mww", distance_km: 15200, estimated_mmi: 0.0,
    is_significant: true,
  }),
];

/** El sismo M6.1 usado en las pantallas de aviso/alerta (handoff §4/§5). */
export const EVENTO_ALERTA_FIXTURE: RawEvent = evento({
  cluster_key: "fx-alerta-m61",
  origin_time: new Date(AHORA - 42_000).toISOString(),
  latitude: -33.55, longitude: -70.62, depth_km: 47, magnitude: 6.1,
  magnitude_type: "Mw", region: "12 km al SO de Ñuñoa",
  preferred_source: "CSN", distance_km: 12, estimated_mmi: 6.3,
  estimated_pga: 0.09, intensity_geometry_source: "wells_coppersmith",
  intensity_distance_saturated: true, is_significant: true,
  alert_level_sent: "full", alert_sent_at: new Date(AHORA - 38_000).toISOString(),
  revision: 3,
});

/** El mismo evento en nivel de aviso 2 (silencioso), para probar esa franja. */
export const EVENTO_AVISO2_FIXTURE: RawEvent = evento({
  cluster_key: "fx-aviso2-m44",
  origin_time: new Date(AHORA - 40_000).toISOString(),
  latitude: -33.68, longitude: -71.22, depth_km: 61, magnitude: 4.4,
  magnitude_type: "Mw", region: "Melipilla · 58 km",
  preferred_source: "CSN", distance_km: 58, estimated_mmi: 3.6,
  estimated_pga: 0.006, is_significant: true, alert_level_sent: "silent",
  alert_sent_at: new Date(AHORA - 35_000).toISOString(),
});

export const REPORTES_ALERTA_FIXTURE: RawEventDetail["reports"] = [
  {
    source: "CSN", source_event_id: "csn-fx-1",
    received_at: new Date(AHORA - 38_000).toISOString(),
    payload: { magnitud: "5.8", ref: "AUTOMÁTICA" },
  },
  {
    source: "USGS", source_event_id: "usgs-fx-1",
    received_at: new Date(AHORA - 12_000).toISOString(),
    payload: { mag: 6.0, status: "AUTOMÁTICA" },
  },
  {
    source: "CSN", source_event_id: "csn-fx-2",
    received_at: new Date(AHORA - 1_000).toISOString(),
    payload: { magnitud: "6.1", ref: "VIGENTE" },
  },
];

export const HEALTH_FIXTURE_OK: RawHealth = {
  CSN: { status: "ok", last_success_at: horas(0.02), last_error_at: null, last_error: null, consecutive_failures: 0 },
  USGS: { status: "ok", last_success_at: horas(0.005), last_error_at: null, last_error: null, consecutive_failures: 0 },
  EMSC: { status: "ok", last_success_at: horas(0.001), last_error_at: null, last_error: null, consecutive_failures: 0 },
};

export const HEALTH_FIXTURE_DEGRADADO: RawHealth = {
  ...HEALTH_FIXTURE_OK,
  CSN: {
    status: "degraded", last_success_at: horas(1.4), last_error_at: horas(0.1),
    last_error: "timeout consultando api.gael.cloud", consecutive_failures: 6,
  },
};

export const CONFIG_FIXTURE: RawConfig = {
  home: HOME_FIXTURE,
  poll_interval_s: 30,
  source_cadence_s: { CSN: 300, USGS: 60, EMSC: null },
};
