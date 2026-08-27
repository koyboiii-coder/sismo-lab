import { colorPorProfundidad } from "@/lib/constants";
import {
  esSentido,
  haceTiempo,
  horaCortaCLT,
  km,
  magnitud,
  mmiRomano,
  pesoSeveridad,
  rumboDesdeHome,
  sinUbicar,
} from "@/lib/derive";
import type { RawEvent } from "@/lib/types";
import styles from "./EventList.module.css";

const BARRA_COLOR: Record<1 | 2 | 3 | 4, string> = {
  1: "var(--barra-1)",
  2: "var(--barra-2)",
  3: "var(--barra-3)",
  4: "var(--barra-4)",
};

export function EventRow({
  evento,
  magnitudMaxVisible,
  homeLat,
  homeLon,
  explorando = false,
  onAbrir,
}: {
  evento: RawEvent;
  magnitudMaxVisible: number;
  homeLat: number;
  homeLon: number;
  explorando?: boolean;
  onAbrir?: (clusterKey: string) => void;
}) {
  const sentido = esSentido(evento);
  const peso = pesoSeveridad(evento, magnitudMaxVisible);
  const sinUbicacion = sinUbicar(evento);

  const rumbo = !sinUbicacion ? rumboDesdeHome(homeLat, homeLon, evento.latitude!, evento.longitude!) : null;
  const mmiTexto = mmiRomano(evento.estimated_mmi);

  return (
    <div
      className={`${styles.fila} ${sentido ? styles.filaDestacada : ""}`}
      style={explorando ? { cursor: "pointer" } : undefined}
      onClick={explorando ? () => onAbrir?.(evento.cluster_key) : undefined}
      role={explorando ? "button" : undefined}
      aria-label={explorando ? `Ver detalle de ${evento.region ?? "evento"}` : undefined}
    >
      <div
        className={styles.barraSeveridad}
        style={{ background: sentido ? "var(--tinta)" : BARRA_COLOR[peso] }}
      />
      <div className={styles.colHora}>
        <span className={styles.horaCorta}>{horaCortaCLT(evento.origin_time)}</span>
        <span className={styles.metadato}>{haceTiempo(evento.origin_time)}</span>
      </div>
      <div className={styles.colMagnitud}>
        <span className={styles.mLabel}>M</span>
        <span className={sentido ? styles.magnitudGrandeSentido : styles.magnitudGrande}>
          {magnitud(evento.magnitude)}
        </span>
      </div>
      <div className={styles.colLugar}>
        <div className={styles.lugarLinea}>
          <span className={styles.lugar}>{sinUbicacion ? "SIN UBICAR" : evento.region ?? "REGIÓN DESCONOCIDA"}</span>
          {/* Antes: "M >= 4.0 en cualquier parte de Chile" (sin relación
              con la distancia a HOME) -- un M4+ en Melipilla, a cientos de
              km de Coihueco, se marcaba igual que un sismo realmente
              sentido acá. `sentido` (MMI en HOME, el mismo criterio que ya
              resalta la fila) es lo único que debería encender esta
              etiqueta. */}
          {sentido && <span className={styles.etiquetaZona}>SENTIDO AQUÍ</span>}
        </div>
        <span className={styles.metadato}>
          {(evento.region ?? "SIN REGIÓN").toUpperCase()} · {evento.preferred_source} ·{" "}
          {mmiTexto ? `MERCALLI ${mmiTexto}` : "MERCALLI —"}
        </span>
      </div>
      <div className={styles.colProfundidad}>
        <span className={styles.cuadradoProfundidad} style={{ background: colorPorProfundidad(evento.depth_km) }} />
        <span className={styles.profundidadValor}>{km(evento.depth_km).toUpperCase()}</span>
      </div>
      <div className={styles.colDistancia}>
        {sinUbicacion ? (
          <span className={styles.distanciaSinUbicar}>SIN UBICAR</span>
        ) : (
          <>
            <span className={sentido ? styles.distanciaSentida : styles.distancia}>{km(evento.distance_km)}</span>
            <span className={styles.metadato}>
              {rumbo} · {mmiTexto ? `MMI ${mmiTexto} AQUÍ` : "NO SENTIDO"}
            </span>
          </>
        )}
      </div>
    </div>
  );
}
