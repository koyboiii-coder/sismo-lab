import { AvisoStrip } from "@/components/alert/AvisoStrip";
import { PanelHeader } from "@/components/layout/PanelHeader";
import { ultimoSentido } from "@/lib/derive";
import type { RawEvent } from "@/lib/types";
import { EventRow } from "./EventRow";
import styles from "./EventList.module.css";
import { LastFeltBlock } from "./LastFeltBlock";

const FILAS_VISIBLES = 8;

export function EventList({
  eventos,
  ahora,
  homeLat,
  homeLon,
  avisoNivel2,
}: {
  eventos: RawEvent[];
  ahora: Date;
  homeLat: number;
  homeLon: number;
  avisoNivel2?: { evento: RawEvent; cierraEnMs: number } | null;
}) {
  const visibles = eventos.slice(0, FILAS_VISIBLES);
  const magnitudMaxVisible = Math.max(1, ...visibles.map((e) => e.magnitude ?? 0));
  const ultimo = ultimoSentido(eventos);

  return (
    <div className={styles.columna}>
      <PanelHeader titulo="Últimos eventos · agregado CSN + USGS + EMSC" dato="Orden cronológico inverso" />
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
      <div className={styles.filas}>
        {visibles.map((e) => (
          <EventRow key={e.cluster_key} evento={e} magnitudMaxVisible={magnitudMaxVisible} homeLat={homeLat} homeLon={homeLon} />
        ))}
        {visibles.length === 0 && (
          <div className={styles.sinEventos}>SIN EVENTOS EN LAS ÚLTIMAS 48 HORAS</div>
        )}
      </div>
    </div>
  );
}
