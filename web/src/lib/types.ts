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
  // null para EMSC: push (WebSocket), sin cadencia de sondeo que violar.
  source_cadence_s: Record<FuenteId, number | null>;
}

/** Un punto de trazo, en coordenadas normalizadas 0-1 por eje (relativas
 * al ancho/alto del lienzo al momento de dibujar, no a px de pantalla) --
 * ver components/notes/NoteCanvas.tsx. Se renderiza siempre dentro de un
 * contenedor de la misma proporción, así que no hace falta forzar un
 * lienzo cuadrado para evitar distorsión. `p` es la
 * presión del lápiz (PointerEvent.pressure), casi siempre un valor fijo
 * en esta tablet sin lápiz con presión real; se guarda igual para no
 * cerrar la puerta si algún día hay uno. `t` es el tiempo relativo (ms)
 * desde el inicio del trazo -- sin uso hoy, deja abierta una futura
 * conversión trazo -> texto sin recapturar nada. */
export interface RawStrokePoint {
  x: number;
  y: number;
  p: number;
  t: number;
}

export interface RawStroke {
  points: RawStrokePoint[];
  /** Ancho de línea normalizado como fracción del ancho del lienzo donde
   * se dibujó (no px absolutos) -- multiplicar por el ancho de destino al
   * renderizar, igual que x/y. Ver lib/strokes.ts. */
  width: number;
}

export interface RawNote {
  id: number;
  created_at: string; // ISO 8601 UTC
  strokes: RawStroke[];
}

export type SsePayload =
  | { kind: "seismic"; type: "insert" | "update"; event: RawEvent }
  | { kind: "health"; health: RawHealthCompact };
