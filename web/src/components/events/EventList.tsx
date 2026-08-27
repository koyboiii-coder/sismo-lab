import { AvisoStrip } from "@/components/alert/AvisoStrip";
import { PanelHeader } from "@/components/layout/PanelHeader";
import { enChile, ultimoSentido } from "@/lib/derive";
import type { RawEvent } from "@/lib/types";
import { EventRow } from "./EventRow";
import styles from "./EventList.module.css";
import { LastFeltBlock } from "./LastFeltBlock";

// 6, no 8: la fila subió de 90 a 132px (tokens.css) para que el texto se
// lea a 3-4m en la Tab M11 real -- ver CLAUDE.md. Menos densidad, pero
// legible sin acercarse es lo que se pidió tras la prueba en la tablet.
const FILAS_VISIBLES = 6;

export function EventList({
  eventos,
  ahora,
  homeLat,
  homeLon,
  avisoNivel2,
  explorando = false,
  onAbrirDetalle,
}: {
  eventos: RawEvent[];
  ahora: Date;
  homeLat: number;
  homeLon: number;
  avisoNivel2?: { evento: RawEvent; cierraEnMs: number } | null;
  /** Modo exploración (ver state/useExploreMode.ts): muestra las 48h
   * completas con scroll (en vez de las FILAS_VISIBLES recortadas) y
   * hace tocables las filas. */
  explorando?: boolean;
  onAbrirDetalle?: (clusterKey: string) => void;
}) {
  // enChile: esta lista es "actividad nacional" (mismo criterio que
  // MapColumn/NationalMap) -- eventos48h es el log GLOBAL (EMSC/USGS no
  // filtran por Chile, ver CLAUDE.md fuentes de datos), y un M1.6 en
  // Turquía no le dice nada a alguien monitoreando Coihueco. La
  // sismicidad mundial relevante (M6.5+) ya tiene su propio panel
  // ("SISMICIDAD MUNDIAL", columna C, WorldQuakes.tsx) -- no se duplica
  // acá, simplemente no aparece en esta lista si no es de Chile.
  const nacionales = eventos.filter(enChile);
  const visibles = explorando ? nacionales : nacionales.slice(0, FILAS_VISIBLES);
  const magnitudMaxVisible = Math.max(1, ...visibles.map((e) => e.magnitude ?? 0));
  const ultimo = ultimoSentido(nacionales);

  return (
    <div className={styles.columna}>
      <PanelHeader
        titulo="Últimos eventos · agregado CSN + USGS + EMSC"
        dato={explorando ? "Toca un evento para su detalle" : "Orden cronológico inverso"}
      />
      {avisoNivel2 ? (
        <AvisoStrip evento={avisoNivel2.evento} cierraEnMs={avisoNivel2.cierraEnMs} ahoraMs={ahora.getTime()} />
      ) : (
        <LastFeltBlock evento={ultimo} ahora={ahora} />
      )}
      <div className={styles.encabezadoTabla}>
        <span />
        <span>HORA</span>
        <span>MAGNITUD</span>
        <span>LUGAR</span>
        <span className={styles.celdaProfundidad}>PROF.</span>
        <span className={styles.encabezadoDerecha}>DISTANCIA</span>
      </div>
      <div className={explorando ? `${styles.filas} ${styles.filasScrolleables}` : styles.filas}>
        {visibles.map((e) => (
          <EventRow
            key={e.cluster_key}
            evento={e}
            magnitudMaxVisible={magnitudMaxVisible}
            homeLat={homeLat}
            homeLon={homeLon}
            explorando={explorando}
            onAbrir={onAbrirDetalle}
          />
        ))}
        {visibles.length === 0 && (
          <div className={styles.sinEventos}>SIN EVENTOS EN LAS ÚLTIMAS 48 HORAS</div>
        )}
      </div>
    </div>
  );
}
