"use client";

import { useState } from "react";
import { EventList } from "@/components/events/EventList";
import { ExploreOverlay, type VistaExploracion } from "@/components/explore/ExploreOverlay";
import { MapColumn } from "@/components/map/MapColumn";
import { StatusColumn } from "@/components/status/StatusColumn";
import { TopBar } from "@/components/TopBar/TopBar";
import type { EstadoAviso } from "@/state/useAvisoMachine";
import type { EstadoExploracion } from "@/state/useExploreMode";
import type { LiveEventsState } from "@/state/useLiveEvents";
import styles from "./NormalLayout.module.css";

export function NormalLayout({
  datos,
  aviso,
  ahora,
  homeLat,
  homeLon,
  homeLabel,
  exploracion,
}: {
  datos: LiveEventsState;
  aviso: EstadoAviso;
  ahora: Date;
  homeLat: number;
  homeLon: number;
  homeLabel: string;
  exploracion: EstadoExploracion;
}) {
  const [vista, setVista] = useState<VistaExploracion>(null);
  const [clusterKeySeleccionado, setClusterKeySeleccionado] = useState<string | null>(null);

  // "Ajustar estado durante el render" (mismo patrón que
  // useAvisoMachine.ts, con la misma razón: evita el setState-en-efecto
  // que el lint de React 19 marca como error) -- el modo exploración se
  // apaga solo por inactividad (useExploreMode), y cuando eso pasa
  // cualquier sub-vista abierta (mapa/detalle/notas) debe cerrarse con
  // él, no quedar huérfana la próxima vez que se entre.
  const [activoProcesado, setActivoProcesado] = useState(exploracion.activo);
  if (exploracion.activo !== activoProcesado) {
    setActivoProcesado(exploracion.activo);
    if (!exploracion.activo) setVista(null);
  }

  const avisoNivel2 =
    aviso.nivel === 2 && aviso.evento && aviso.cierraEnMs
      ? { evento: aviso.evento, cierraEnMs: aviso.cierraEnMs }
      : null;

  const sourceCadenceS = datos.config?.source_cadence_s ?? null;

  function abrirDetalle(clusterKey: string) {
    setClusterKeySeleccionado(clusterKey);
    setVista("detalle");
  }

  return (
    <>
      <TopBar
        ahora={ahora}
        ubicacionLabel={homeLabel}
        homeLat={homeLat}
        homeLon={homeLon}
        health={datos.health}
        sourceCadenceS={sourceCadenceS}
      />
      <div className={styles.cuerpo}>
        <div className={styles.col}>
          <MapColumn
            eventos={datos.eventos48h}
            homeLat={homeLat}
            homeLon={homeLon}
            explorando={exploracion.activo}
            onSeleccionarEvento={abrirDetalle}
          />
        </div>
        <div className={styles.colB}>
          <EventList
            eventos={datos.eventos48h}
            ahora={ahora}
            homeLat={homeLat}
            homeLon={homeLon}
            avisoNivel2={avisoNivel2}
            explorando={exploracion.activo}
            onAbrirDetalle={abrirDetalle}
          />
        </div>
        <div className={styles.colSinBorde}>
          <StatusColumn
            eventos48h={datos.eventos48h}
            eventosSignificativos90d={datos.eventosSignificativos90d}
            health={datos.health}
            sourceCadenceS={sourceCadenceS}
            connEstado={datos.connEstado}
            ultimoPaqueteEn={datos.ultimoPaqueteEn}
            pollIntervalS={datos.config?.poll_interval_s ?? 30}
            ahora={ahora}
          />
        </div>
      </div>
      <ExploreOverlay
        exploracion={exploracion}
        vista={vista}
        onCambiarVista={setVista}
        clusterKeySeleccionado={clusterKeySeleccionado}
        eventos={datos.eventos48h}
        homeLat={homeLat}
        homeLon={homeLon}
        homeLabel={homeLabel}
      />
    </>
  );
}
