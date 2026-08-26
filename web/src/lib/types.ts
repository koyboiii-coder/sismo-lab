/**
 * Formas crudas tal como las entrega la API (api/notifier.py:serialize_event,
 * api/routers/health.py, api/routers/config.py). Deliberadamente NO es el
 * `Evento`/`Estado` de docs/design/handoff.md §7: ese contrato es de la
 * maqueta, no de la API real. Todo lo que el handoff da por hecho (lugar,
 * rumbo, fuentes confirmantes, resumen 48h, nivel de aviso) se deriva de
 * estos campos crudos en lib/derive.ts.
 */

export type FuenteId = "CSN" | "USGS" | "EMSC";

export type EstadoFuente = "ok" | "degraded" | "unknown";

export interface RawEvent {
  cluster_key: string;
  origin_time: string; // ISO 8601 UTC
  latitude: number | null; // null: CSN sin geocodificar (handoff §7, CLAUDE.md fuente CSN)
  longitude: number | null;
  depth_km: number | null;
  magnitude: number | null;
  magnitude_type: string | null;
  region: string | null; // texto crudo de la fuente, no normalizado
  distance_km: number | null; // hipocentral, desde HOME
  estimated_pga: number | null;
  estimated_mmi: number | null; // 1-12, null si no estimable (sin coords)
  intensity_geometry_source: "finite_fault" | "wells_coppersmith" | null;
  intensity_distance_saturated: boolean | null;
  preferred_source: FuenteId;
  is_significant: boolean;
  alert_sent_at: string | null;
  alert_level_sent: "silent" | "full" | null;
  first_seen_at: string;
  updated_at: string;
  revision: number;
}

export interface RawHealthDetail {
  status: EstadoFuente;
  last_success_at: string | null;
  last_error_at: string | null;
  last_error: string | null;
  consecutive_failures: number;
}

export type RawHealth = Record<FuenteId, RawHealthDetail>;

/** Payload compacto que llega en el evento SSE "health". */
export type RawHealthCompact = Record<FuenteId, EstadoFuente>;

export interface RawEventReport {
  source: FuenteId;
  source_event_id: string;
  payload: unknown;
  received_at: string;
}

export interface RawEventDetail {
  event: RawEvent;
  reports: RawEventReport[];
}

export interface RawConfig {
  home: { lat: number; lon: number; label: string };
  poll_interval_s: number;
}

export type SsePayload =
  | { kind: "seismic"; type: "insert" | "update"; event: RawEvent }
  | { kind: "health"; health: RawHealthCompact };
