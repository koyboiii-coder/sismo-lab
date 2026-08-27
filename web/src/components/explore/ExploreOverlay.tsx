"use client";

import { NotesScreen } from "@/components/notes/NotesScreen";
import { cuentaRegresiva } from "@/lib/derive";
import type { RawEvent } from "@/lib/types";
import type { EstadoExploracion } from "@/state/useExploreMode";
import { EventDetailOverlay } from "./EventDetailOverlay";
import styles from "./ExploreOverlay.module.css";

export type VistaExploracion = "detalle" | "notas" | null;

/**
 * Capa táctil del modo exploración (puntos 4/5 del feedback post-tablet
 * -- CLAUDE.md). Solo el botón NOTAS es visible siempre (a pedido
 * explícito, tras el feedback de que la presión larga para encontrarlo
 * no era confiable en la tablet real) -- el resto (aviso de modo
 * exploración, detalle de evento) sigue oculto fuera de
 * `exploracion.activo`.
 */
export function ExploreOverlay({
  exploracion,
  vista,
  onCambiarVista,
  clusterKeySeleccionado,
  eventos,
  homeLat,
  homeLon,
}: {
  exploracion: EstadoExploracion;
  vista: VistaExploracion;
  onCambiarVista: (v: VistaExploracion) => void;
  clusterKeySeleccionado: string | null;
  eventos: RawEvent[];
  homeLat: number;
  homeLon: number;
}) {
  const eventoSeleccionado = eventos.find((e) => e.cluster_key === clusterKeySeleccionado) ?? null;

  function abrirNotas() {
    // Entra directo al modo exploración (sin pasar por la presión larga)
    // para que la pizarra tenga su reloj de inactividad/salida normal en
    // marcha -- ver useExploreMode.ts:activar.
    exploracion.activar();
    onCambiarVista("notas");
  }

  return (
    <div className={styles.capa}>
      {vista === null && (
        // El contador va a la izquierda y la pestaña NOTAS a ras de la
        // esquina: NOTAS es el ancla permanente, el aviso se le acopla
        // cuando el modo exploración está activo.
        <div className={styles.controlesInferiores}>
          {exploracion.activo && (
            <span className={exploracion.avisoDescarte ? styles.avisoDescarte : styles.aviso}>
              MODO EXPLORACIÓN
              {exploracion.segundosRestantes != null
                ? ` · SE CIERRA EN ${cuentaRegresiva(exploracion.segundosRestantes)}`
                : ""}
            </span>
          )}
          <button className={styles.pestanaNotas} onClick={abrirNotas}>
            NOTAS
          </button>
        </div>
      )}

      {vista === "detalle" && exploracion.activo && eventoSeleccionado && (
        <div className={styles.velo}>
          <EventDetailOverlay
            evento={eventoSeleccionado}
            homeLat={homeLat}
            homeLon={homeLon}
            onVolver={() => onCambiarVista(null)}
          />
        </div>
      )}

      {vista === "notas" && (
        <div className={styles.velo}>
          <NotesScreen onVolver={() => onCambiarVista(null)} onTrazosSinGuardar={exploracion.marcarTrazosSinGuardar} />
        </div>
      )}
    </div>
  );
}
