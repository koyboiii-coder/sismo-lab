"use client";

import { ZoomMap } from "@/components/map/ZoomMap";
import {
  descripcionMmi,
  fuentesConfirmantes,
  haceTiempo,
  horaCLT,
  km,
  localizadorDesdeHome,
  magnitud,
  mmiRomano,
  regionAproxDeChile,
} from "@/lib/derive";
import type { RawEvent } from "@/lib/types";
import { useEventDetail } from "@/state/useEventDetail";
import styles from "./ExploreOverlay.module.css";

/** Detalle de un evento tocado en modo exploración -- reutiliza
 * useEventDetail (ya construido para "N de 3 fuentes confirman" y el
 * historial de soluciones de la pantalla de alerta) en vez de un fetch
 * nuevo. */
export function EventDetailOverlay({
  evento,
  homeLat,
  homeLon,
  homeLabel,
  onVolver,
}: {
  evento: RawEvent;
  homeLat: number;
  homeLon: number;
  homeLabel: string;
  onVolver: () => void;
}) {
  const reportes = useEventDetail(evento.cluster_key);
  const fuentes = reportes ? fuentesConfirmantes(reportes) : [];
  const mmiTexto = mmiRomano(evento.estimated_mmi);

  // Ancla geográfica que al `region` del CSN ("38 km al E de Antuco") le
  // falta: región administrativa aproximada (por latitud, ver
  // regionAproxDeChile) + posición epicentral relativa a HOME. Solo para
  // eventos ubicados -- sin coordenadas no hay ninguna de las dos.
  const ubicado = evento.latitude != null && evento.longitude != null;
  const regionAprox = ubicado ? regionAproxDeChile(evento.latitude!, evento.longitude!) : null;
  const relativoAHome = ubicado
    ? `${localizadorDesdeHome(homeLat, homeLon, evento.latitude!, evento.longitude!)} de ${homeLabel}`
    : null;

  return (
    <div className={styles.panelGrande}>
      <div className={styles.encabezadoPanel}>
        <span className={styles.tituloPanel}>{evento.region ?? "Región desconocida"}</span>
        <button className={styles.botonTexto} onClick={onVolver}>
          VOLVER
        </button>
      </div>
      <div className={styles.detalleCuerpo}>
        <div className={styles.detalleDatos}>
          {relativoAHome && (
            <span className={styles.metaDetalle}>
              {regionAprox ? `Región aprox.: ${regionAprox}` : "Fuera de Chile continental"} · {relativoAHome}
            </span>
          )}
          <div>
            <span className={styles.etiquetaDetalle}>MAGNITUD</span>
            <span className={styles.cifraDetalle}>M {magnitud(evento.magnitude)}</span>
          </div>
          <div>
            <span className={styles.etiquetaDetalle}>DISTANCIA</span>
            <span className={styles.cifraDetalle}>{km(evento.distance_km)}</span>
          </div>
          <div>
            <span className={styles.etiquetaDetalle}>PROFUNDIDAD</span>
            <span className={styles.cifraDetalle}>{km(evento.depth_km)}</span>
          </div>
          <div>
            <span className={styles.etiquetaDetalle}>MERCALLI AQUÍ</span>
            <span className={styles.cifraDetalle}>{mmiTexto ?? "—"}</span>
          </div>
          <p className={styles.descripcionMmi}>
            {descripcionMmi(evento.estimated_mmi) ?? "Sin estimación de intensidad -- evento sin coordenadas."}
          </p>
          <span className={styles.metaDetalle}>
            {horaCLT(evento.origin_time)} · {haceTiempo(evento.origin_time)} · revisión {evento.revision}
          </span>
          <span className={styles.metaDetalle}>
            {reportes == null
              ? "CARGANDO FUENTES…"
              : fuentes.length > 0
                ? `${fuentes.join(" + ")} · ${fuentes.length} DE 3 FUENTES CONFIRMAN`
                : "SIN CONFIRMACIÓN DE OTRA FUENTE TODAVÍA"}
          </span>
        </div>
        <div className={styles.detalleMapa}>
          <ZoomMap homeLat={homeLat} homeLon={homeLon} eventoLat={evento.latitude} eventoLon={evento.longitude} />
        </div>
      </div>
    </div>
  );
}
