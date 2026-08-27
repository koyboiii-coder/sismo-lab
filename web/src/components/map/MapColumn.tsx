import { PanelHeader } from "@/components/layout/PanelHeader";
import { enChile } from "@/lib/derive";
import type { RawEvent } from "@/lib/types";
import { NationalMap } from "./NationalMap";
import styles from "./MapColumn.module.css";

export function MapColumn({
  eventos,
  homeLat,
  homeLon,
  explorando = false,
  onSeleccionarEvento,
}: {
  eventos: RawEvent[];
  homeLat: number;
  homeLon: number;
  /** Modo exploración (ver state/useExploreMode.ts) -- fuera de él el
   * mapa no reacciona al toque, consistente con "sin interacción como
   * requisito" (handoff §1). */
  explorando?: boolean;
  /** Tocar el mapa abre el detalle del evento más cercano al punto
   * tocado -- ver NationalMap.tsx:alTocarMapa. */
  onSeleccionarEvento?: (clusterKey: string) => void;
}) {
  const nacionales = eventos.filter(enChile);
  return (
    <div className={styles.columna}>
      <PanelHeader titulo="Actividad nacional · 48 h" dato={`${nacionales.length} EVENTOS`} />
      <div className={styles.mapaContenedor}>
        <NationalMap
          eventos={eventos}
          homeLat={homeLat}
          homeLon={homeLon}
          explorando={explorando}
          onSeleccionarEvento={onSeleccionarEvento}
        />
      </div>
    </div>
  );
}
