import { colorPorProfundidad } from "@/lib/constants";
import {
  enChile,
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

/** Heurística documentada: sin señal de "sentido en la zona" reportada por
 * usuarios, se usa M>=4.0 como umbral de percepción típica cerca del
 * epicentro (no depende de la distancia a HOME). Sí se restringe a eventos
 * en Chile: la lista mezcla actividad nacional con sismos mundiales M6.5+
 * (CLAUDE.md, "sin alerta local"), y "zona" nunca se pensó para esos --
 * un M6.7 en Japón no dice nada sobre si algo se sintió en Coihueco. Sin
 * este filtro la etiqueta aparecía en cualquier evento mundial grande
 * (ej. Afganistán a 16.700 km, MMI I aquí) como si fuera relevante. */
function sentidoEnLaZona(e: RawEvent): boolean {
  return enChile(e) && (e.magnitude ?? 0) >= 4.0;
}

export function EventRow({
  evento,
  magnitudMaxVisible,
  homeLat,
  homeLon,
}: {
  evento: RawEvent;
  magnitudMaxVisible: number;
  homeLat: number;
  homeLon: number;
}) {
  const sentido = esSentido(evento);
  const peso = pesoSeveridad(evento, magnitudMaxVisible);
  const sinUbicacion = sinUbicar(evento);

  const rumbo = !sinUbicacion ? rumboDesdeHome(homeLat, homeLon, evento.latitude!, evento.longitude!) : null;
  const mmiTexto = mmiRomano(evento.estimated_mmi);

  return (
    <div className={`${styles.fila} ${sentido ? styles.filaDestacada : ""}`}>
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
          {sentidoEnLaZona(evento) && <span className={styles.etiquetaZona}>SENTIDO EN LA ZONA</span>}
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
