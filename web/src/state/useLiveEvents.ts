"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchConfig, fetchEvents, fetchHealth, fetchSignificantEvents } from "@/lib/api";
import { VENTANA_EVENTOS_HORAS } from "@/lib/constants";
import { SseConexion, type SseEstado } from "@/lib/sse";
import type { RawConfig, RawEvent, RawHealth, RawHealthCompact } from "@/lib/types";

const VENTANA_SENTIDOS_DIAS = 90;
const RESYNC_INTERVAL_MS = 5 * 60_000;

export interface LiveEventsState {
  eventos48h: RawEvent[];
  eventosSignificativos90d: RawEvent[];
  health: RawHealth | null;
  config: RawConfig | null;
  connEstado: SseEstado;
  ultimoPaqueteEn: number | null;
  cargandoInicial: boolean;
  errorInicial: string | null;
}

function upsertTodos(mapa: Map<string, RawEvent>, eventos: RawEvent[]): Map<string, RawEvent> {
  const siguiente = new Map(mapa);
  for (const e of eventos) siguiente.set(e.cluster_key, e);
  return siguiente;
}

/**
 * Fuente única de verdad de eventos vistos en esta sesión: REST inicial +
 * upserts por SSE (insert/update), indexados por cluster_key en estado de
 * React (no una ref -- las dos ventanas derivadas más abajo se calculan
 * en useMemo, y leer una ref durante el render rompe las reglas de
 * pureza de React). Las dos ventanas que la UI necesita (48h nacional, 90
 * días de sentidos) se derivan filtrando este mapa, así un mismo evento
 * nunca puede quedar desincronizado entre ambas listas.
 *
 * `enabled=false` (usado por Dashboard cuando hay ?escenario= forzado)
 * evita fetches/SSE de más contra un backend que puede ni estar
 * levantado en desarrollo -- las Rules of Hooks igual exigen llamar el
 * hook siempre, así que el corte es interno.
 */
export function useLiveEvents(enabled: boolean = true): LiveEventsState {
  const [eventos, setEventos] = useState<Map<string, RawEvent>>(new Map());
  const [health, setHealth] = useState<RawHealth | null>(null);
  const [config, setConfig] = useState<RawConfig | null>(null);
  const [connEstado, setConnEstado] = useState<SseEstado>("conectando");
  const [ultimoPaqueteEn, setUltimoPaqueteEn] = useState<number | null>(null);
  const [cargandoInicial, setCargandoInicial] = useState(true);
  const [errorInicial, setErrorInicial] = useState<string | null>(null);
  // "Ahora" como estado, no Date.now() leído directamente en el render:
  // los useMemo de más abajo dependen de este valor en vez de llamar a
  // una función impura durante el cálculo derivado.
  const [ahoraMs, setAhoraMs] = useState<number>(() => Date.now());

  useEffect(() => {
    if (!enabled) return;
    let cancelado = false;

    async function cargaInicial() {
      const desde48h = new Date(Date.now() - VENTANA_EVENTOS_HORAS * 3_600_000).toISOString();
      const desde90d = new Date(Date.now() - VENTANA_SENTIDOS_DIAS * 86_400_000).toISOString();
      try {
        const [eventosIniciales, significativos, cfg, salud] = await Promise.all([
          fetchEvents(desde48h),
          fetchSignificantEvents(desde90d),
          fetchConfig(),
          fetchHealth(),
        ]);
        if (cancelado) return;
        setEventos((prev) => upsertTodos(prev, [...significativos, ...eventosIniciales]));
        setConfig(cfg);
        setHealth(salud);
      } catch (err) {
        if (!cancelado) setErrorInicial(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelado) setCargandoInicial(false);
      }
    }
    cargaInicial();

    const resyncId = setInterval(() => {
      const desde48h = new Date(Date.now() - VENTANA_EVENTOS_HORAS * 3_600_000).toISOString();
      fetchEvents(desde48h)
        .then((nuevos) => {
          if (!cancelado) setEventos((prev) => upsertTodos(prev, nuevos));
        })
        .catch(() => {
          // El resync es una red de seguridad sobre el SSE, no la fuente
          // principal -- una falla acá no debe tratarse como caída (eso
          // ya lo refleja connEstado vía SseConexion).
        });
    }, RESYNC_INTERVAL_MS);

    const sse = new SseConexion("/api/stream", {
      onSeismic: (msg) => setEventos((prev) => upsertTodos(prev, [msg.event])),
      onHealth: (h) => setHealth((prev) => mapHealthCompact(h, prev)),
      onEstadoCambia: (estado, ultimo) => {
        if (cancelado) return;
        setConnEstado(estado);
        setUltimoPaqueteEn(ultimo);
      },
    });
    sse.conectar();

    return () => {
      cancelado = true;
      clearInterval(resyncId);
      sse.cerrar();
    };
  }, [enabled]);

  useEffect(() => {
    const id = setInterval(() => setAhoraMs(Date.now()), (config?.poll_interval_s ?? 30) * 1000);
    return () => clearInterval(id);
  }, [config?.poll_interval_s]);

  const eventos48h = useMemo(() => {
    const corte = ahoraMs - VENTANA_EVENTOS_HORAS * 3_600_000;
    return [...eventos.values()]
      .filter((e) => new Date(e.origin_time).getTime() >= corte)
      .sort((a, b) => new Date(b.origin_time).getTime() - new Date(a.origin_time).getTime());
  }, [eventos, ahoraMs]);

  const eventosSignificativos90d = useMemo(() => {
    const corte = ahoraMs - VENTANA_SENTIDOS_DIAS * 86_400_000;
    return [...eventos.values()]
      .filter((e) => e.is_significant && new Date(e.origin_time).getTime() >= corte)
      .sort((a, b) => new Date(b.origin_time).getTime() - new Date(a.origin_time).getTime());
  }, [eventos, ahoraMs]);

  return {
    eventos48h,
    eventosSignificativos90d,
    health,
    config,
    connEstado,
    ultimoPaqueteEn,
    cargandoInicial: enabled ? cargandoInicial : false,
    errorInicial,
  };
}

/**
 * El evento SSE "health" trae la forma compacta {"CSN":"ok",...} (ver
 * api/notifier.py:health_compact) -- solo status, sin las marcas de
 * tiempo del detalle. Se preserva lo demás de la última vez que se pidió
 * /api/health por REST.
 */
function mapHealthCompact(compact: RawHealthCompact, prev: RawHealth | null): RawHealth {
  const out = { ...(prev ?? ({} as RawHealth)) };
  for (const fuente of Object.keys(compact) as (keyof RawHealthCompact)[]) {
    const status = compact[fuente];
    const anterior = out[fuente];
    out[fuente] = {
      status,
      last_success_at: anterior?.last_success_at ?? null,
      last_error_at: anterior?.last_error_at ?? null,
      last_error: anterior?.last_error ?? null,
      consecutive_failures: anterior?.consecutive_failures ?? 0,
    };
  }
  return out;
}
