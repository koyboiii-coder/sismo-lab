import { PanelHeader } from "@/components/layout/PanelHeader";
import { enChile } from "@/lib/derive";
import type { RawEvent } from "@/lib/types";
import { NationalMap } from "./NationalMap";
import styles from "./MapColumn.module.css";

export function MapColumn({ eventos, homeLat, homeLon }: { eventos: RawEvent[]; homeLat: number; homeLon: number }) {
  const nacionales = eventos.filter(enChile);
  return (
    <div className={styles.columna}>
      <PanelHeader titulo="Actividad nacional · 48 h" dato={`${nacionales.length} EVENTOS`} />
      <div className={styles.mapaContenedor}>
        <NationalMap eventos={eventos} homeLat={homeLat} homeLon={homeLon} />
      </div>
    </div>
  );
}
