/**
 * Escenarios forzables vía ?escenario=<nombre> (ver web/README.md). Cada
 * uno arma un snapshot estático -- events/health/config -- que reemplaza
 * por completo la carga en vivo (REST + SSE) para poder revisar las 5
 * pantallas del handoff sin esperar un sismo real ni tener el backend
 * levantado.
 */
import type { RawConfig, RawEvent, RawHealth } from "@/lib/types";
import { SseEstado } from "@/lib/sse";
import {
  CONFIG_FIXTURE,
  EVENTO_ALERTA_FIXTURE,
  EVENTO_AVISO2_FIXTURE,
  EVENTOS_BASE,
  HEALTH_FIXTURE_DEGRADADO,
  HEALTH_FIXTURE_OK,
} from "./events";

export const NOMBRES_ESCENARIO = ["normal", "aviso2", "aviso3", "alerta", "error"] as const;
export type NombreEscenario = (typeof NOMBRES_ESCENARIO)[number];

export interface SnapshotEscenario {
  events: RawEvent[];
  health: RawHealth;
  config: RawConfig;
  connEstado: SseEstado;
  ultimoPaqueteEn: number | null;
}

export function esNombreEscenario(valor: string | null): valor is NombreEscenario {
  return !!valor && (NOMBRES_ESCENARIO as readonly string[]).includes(valor);
}

export function construirEscenario(nombre: NombreEscenario): SnapshotEscenario {
  const base: Omit<SnapshotEscenario, "events"> = {
    health: HEALTH_FIXTURE_OK,
    config: CONFIG_FIXTURE,
    connEstado: "conectado",
    ultimoPaqueteEn: Date.now(),
  };

  switch (nombre) {
    case "normal":
      return { ...base, events: EVENTOS_BASE };

    case "aviso2":
      return { ...base, events: [EVENTO_AVISO2_FIXTURE, ...EVENTOS_BASE] };

    case "aviso3":
      return { ...base, events: [EVENTO_ALERTA_FIXTURE, ...EVENTOS_BASE] };

    case "alerta": {
      // Mismo evento que aviso3 pero "hace 6 minutos": ya pasó la ventana
      // de 45s del popup (handoff §5) pero sigue dentro del estado de
      // alerta (§4, hasta 20 min tras la última réplica M>=3.5).
      const haceSeisMin = new Date(Date.now() - 6 * 60_000).toISOString();
      const evento = { ...EVENTO_ALERTA_FIXTURE, origin_time: haceSeisMin, alert_sent_at: haceSeisMin };
      return { ...base, events: [evento, ...EVENTOS_BASE] };
    }

    case "error":
      return {
        ...base,
        events: EVENTOS_BASE,
        health: {
          ...HEALTH_FIXTURE_DEGRADADO,
          USGS: { status: "unknown", last_success_at: null, last_error_at: null, last_error: null, consecutive_failures: 0 },
          EMSC: { status: "unknown", last_success_at: null, last_error_at: null, last_error: null, consecutive_failures: 0 },
        },
        connEstado: "caido",
        ultimoPaqueteEn: Date.now() - 12 * 60_000,
      };
  }
}
