/**
 * Cliente SSE con reconexión manual (no el retry nativo de EventSource,
 * que no permite backoff exponencial ni detectar un socket que sigue
 * "abierto" pero dejó de recibir datos). CLAUDE.md / handoff §7: el
 * frontend nunca debe mostrar datos viejos como si fueran actuales, así
 * que este módulo expone el estado de conexión explícitamente en vez de
 * asumir que "abierto" == "al día".
 *
 * api/routers/stream.py manda un evento "health" cada 15 s como
 * heartbeat -- si no llega nada (ni "seismic" ni "health") en
 * WATCHDOG_TIMEOUT_MS, se asume el socket muerto y se fuerza reconexión.
 */
import { SSE_BACKOFF_INICIAL_MS, SSE_BACKOFF_MAXIMO_MS } from "./constants";
import type { RawEvent, RawHealthCompact } from "./types";

export type SseEstado = "conectando" | "conectado" | "reconectando" | "caido";

export interface SseHandlers {
  onSeismic: (msg: { type: "insert" | "update"; event: RawEvent }) => void;
  onHealth: (health: RawHealthCompact) => void;
  onEstadoCambia: (estado: SseEstado, ultimoPaqueteEn: number | null) => void;
}

const WATCHDOG_INTERVAL_MS = 5_000;
const WATCHDOG_TIMEOUT_MS = 40_000; // > 2x el heartbeat de 15s del backend

export class SseConexion {
  private es: EventSource | null = null;
  private backoffMs = SSE_BACKOFF_INICIAL_MS;
  private cerrado = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private watchdogTimer: ReturnType<typeof setInterval> | null = null;
  private ultimoPaqueteEn: number | null = null;
  private intentos = 0;

  constructor(
    private readonly url: string,
    private readonly handlers: SseHandlers,
  ) {}

  conectar(): void {
    this.cerrado = false;
    this.abrir();
    this.watchdogTimer = setInterval(() => this.chequearVida(), WATCHDOG_INTERVAL_MS);
  }

  cerrar(): void {
    this.cerrado = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.watchdogTimer) clearInterval(this.watchdogTimer);
    this.es?.close();
    this.es = null;
  }

  private abrir(): void {
    this.handlers.onEstadoCambia(this.intentos === 0 ? "conectando" : "reconectando", this.ultimoPaqueteEn);
    const es = new EventSource(this.url);
    this.es = es;

    es.addEventListener("open", () => {
      this.intentos = 0;
      this.backoffMs = SSE_BACKOFF_INICIAL_MS;
    });

    es.addEventListener("seismic", (ev) => {
      this.marcarVivo();
      try {
        const data = JSON.parse((ev as MessageEvent).data) as {
          type: "insert" | "update";
          event: RawEvent;
        };
        this.handlers.onSeismic(data);
      } catch {
        // Payload mal formado: se ignora este mensaje puntual, no se
        // derriba la conexión por un solo evento corrupto.
      }
    });

    es.addEventListener("health", (ev) => {
      this.marcarVivo();
      try {
        const data = JSON.parse((ev as MessageEvent).data) as RawHealthCompact;
        this.handlers.onHealth(data);
      } catch {
        // idem
      }
    });

    es.addEventListener("error", () => {
      if (this.cerrado) return;
      es.close();
      this.es = null;
      this.programarReconexion();
    });
  }

  private marcarVivo(): void {
    this.ultimoPaqueteEn = Date.now();
    this.handlers.onEstadoCambia("conectado", this.ultimoPaqueteEn);
  }

  private chequearVida(): void {
    if (this.cerrado || this.ultimoPaqueteEn == null) return;
    if (Date.now() - this.ultimoPaqueteEn > WATCHDOG_TIMEOUT_MS) {
      this.es?.close();
      this.es = null;
      this.programarReconexion();
    }
  }

  private programarReconexion(): void {
    if (this.cerrado) return;
    this.intentos += 1;
    this.handlers.onEstadoCambia("caido", this.ultimoPaqueteEn);
    this.reconnectTimer = setTimeout(() => {
      if (this.cerrado) return;
      this.abrir();
    }, this.backoffMs);
    this.backoffMs = Math.min(this.backoffMs * 2, SSE_BACKOFF_MAXIMO_MS);
  }
}
