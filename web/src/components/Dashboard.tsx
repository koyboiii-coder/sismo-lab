"use client";

import { useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { AlertErrorBoundary } from "@/components/alert/AlertErrorBoundary";
import { AlertLayout } from "@/components/alert/AlertLayout";
import { AvisoPopup } from "@/components/alert/AvisoPopup";
import { BuildBadge } from "@/components/BuildBadge";
import { ErrorState } from "@/components/error/ErrorState";
import { NormalLayout } from "@/components/layout/NormalLayout";
import { EVENTO_ALERTA_FIXTURE, REPORTES_ALERTA_FIXTURE } from "@/fixtures/events";
import { construirEscenario, esNombreEscenario } from "@/fixtures/scenarios";
import { useAvisoMachine } from "@/state/useAvisoMachine";
import { useClock } from "@/state/useClock";
import { useEventDetail } from "@/state/useEventDetail";
import { useExploreMode } from "@/state/useExploreMode";
import { useLiveEvents, type LiveEventsState } from "@/state/useLiveEvents";
import { useNightMode } from "@/state/useNightMode";
import type { RawEventReport } from "@/lib/types";
import styles from "./Dashboard.module.css";

/** Cuánto tiempo sin ningún paquete (REST inicial ni SSE) antes de tratar
 * la conexión como realmente caída -- handoff §6/§7: nunca mostrar datos
 * viejos como si fueran actuales. */
const UMBRAL_SIN_DATO_MS = 90_000;

export function Dashboard() {
  const searchParams = useSearchParams();
  const nombreEscenario = searchParams.get("escenario");
  // useMemo, no una expresión directa: construirEscenario arma arrays nuevos
  // en cada llamada (p. ej. `[evento, ...EVENTOS_BASE]`). Sin memoizar, cada
  // render de Dashboard le pasa a useAvisoMachine una referencia `eventos`
  // distinta aunque el contenido sea igual; su patrón de "ajustar estado
  // durante el render" (ver useAvisoMachine.ts) nunca ve `eventos ===
  // eventosProcesados` y dispara un re-render en cada intento, sin converger
  // -- React lo corta con "Too many re-renders" (bug real que rompía
  // ?escenario=alerta con pantalla en blanco).
  const escenario = useMemo(
    () => (esNombreEscenario(nombreEscenario) ? construirEscenario(nombreEscenario) : null),
    [nombreEscenario],
  );

  const live = useLiveEvents(!escenario);
  const ahora = useClock();
  // ?noche=false fuerza brillo pleno (y ?noche=true fuerza la atenuación) sin
  // tener que cambiar la hora del sistema -- para revisar el diseño en
  // desarrollo. Sin el parámetro, useNightMode decide por el reloj real.
  const nocheParam = searchParams.get("noche");
  const forzarNoche = nocheParam === "false" ? false : nocheParam === "true" ? true : null;
  const silencioNocturno = useNightMode(forzarNoche);

  const datos: LiveEventsState = escenario
    ? {
        eventos48h: escenario.events,
        eventosSignificativos90d: escenario.events.filter((e) => e.is_significant),
        health: escenario.health,
        config: escenario.config,
        connEstado: escenario.connEstado,
        ultimoPaqueteEn: escenario.ultimoPaqueteEn,
        cargandoInicial: false,
        errorInicial: null,
      }
    : live;

  const aviso = useAvisoMachine(datos.eventos48h, silencioNocturno);
  // Modo exploración deshabilitado mientras nivel 3 está activo (popup o
  // ya en alerta 1b): un toque ahí es para esa pantalla, no para entrar a
  // explorar -- ver useExploreMode.ts.
  const exploracion = useExploreMode(aviso.nivel === 3);

  const clusterKeyDetalle = !escenario && aviso.nivel === 3 ? aviso.evento?.cluster_key ?? null : null;
  const reportesLive = useEventDetail(clusterKeyDetalle);
  const reportesFixture: RawEventReport[] | null =
    escenario && aviso.evento?.cluster_key === EVENTO_ALERTA_FIXTURE.cluster_key ? REPORTES_ALERTA_FIXTURE : null;
  const reportes = escenario ? reportesFixture : reportesLive;

  // No hay fallback numérico: mientras /api/config no llega (o falló),
  // `home` es null en vez de una coordenada de relleno que parezca un dato
  // real -- ver CLAUDE.md "Sin default de ubicación en silencio". Los
  // escenarios forzados siempre traen CONFIG_FIXTURE, así que esto solo
  // puede ser null en modo en vivo.
  const home = datos.config?.home ?? null;

  const sinDatoMs = datos.ultimoPaqueteEn != null ? ahora.getTime() - datos.ultimoPaqueteEn : Infinity;
  const conexionCaida = datos.connEstado === "caido" && sinDatoMs > UMBRAL_SIN_DATO_MS;
  const errorCargaInicial = !datos.cargandoInicial && datos.errorInicial != null && datos.eventos48h.length === 0;

  if (conexionCaida || errorCargaInicial) {
    return (
      <div className={styles.pantalla}>
        <BuildBadge />
        <ErrorState
          ahora={ahora}
          ultimoPaqueteEn={datos.ultimoPaqueteEn}
          health={datos.health}
          sourceCadenceS={datos.config?.source_cadence_s ?? null}
          homeLat={home?.lat ?? null}
          homeLon={home?.lon ?? null}
          homeLabel={home?.label ?? "Ubicación"}
        />
      </div>
    );
  }

  if (!home) {
    // Carga inicial en curso, todavía sin error: pantalla de espera
    // genuina en vez de renderizar el dashboard con una ubicación
    // fabricada mientras se espera el primer /api/config.
    return (
      <div className={styles.pantalla}>
        <BuildBadge />
        <span className={styles.cargando}>CONECTANDO…</span>
      </div>
    );
  }

  return (
    <div className={styles.pantalla}>
      <BuildBadge />
      {aviso.nivel === 3 && !aviso.enAlerta && aviso.evento ? (
        <>
          <NormalLayout
            datos={datos}
            aviso={aviso}
            ahora={ahora}
            homeLat={home.lat}
            homeLon={home.lon}
            homeLabel={home.label}
            exploracion={exploracion}
          />
          <AvisoPopup
            evento={aviso.evento}
            eventosRelacionados={datos.eventos48h}
            reportes={reportes}
            cierraEnMs={aviso.cierraEnMs!}
            ahoraMs={ahora.getTime()}
            silencioNocturno={silencioNocturno}
            onCerrar={aviso.cerrarPopupAhora}
          />
        </>
      ) : aviso.enAlerta && aviso.evento ? (
        <AlertErrorBoundary evento={aviso.evento}>
          <AlertLayout evento={aviso.evento} reportes={reportes} homeLat={home.lat} homeLon={home.lon} ahora={ahora} />
        </AlertErrorBoundary>
      ) : (
        <NormalLayout
          datos={datos}
          aviso={aviso}
          ahora={ahora}
          homeLat={home.lat}
          homeLon={home.lon}
          homeLabel={home.label}
          exploracion={exploracion}
        />
      )}
    </div>
  );
}
