import { EventList } from "@/components/events/EventList";
import { MapColumn } from "@/components/map/MapColumn";
import { StatusColumn } from "@/components/status/StatusColumn";
import { TopBar } from "@/components/TopBar/TopBar";
import type { EstadoAviso } from "@/state/useAvisoMachine";
import type { LiveEventsState } from "@/state/useLiveEvents";
import styles from "./NormalLayout.module.css";

export function NormalLayout({
  datos,
  aviso,
  ahora,
  homeLat,
  homeLon,
  homeLabel,
}: {
  datos: LiveEventsState;
  aviso: EstadoAviso;
  ahora: Date;
  homeLat: number;
  homeLon: number;
  homeLabel: string;
}) {
  const avisoNivel2 =
    aviso.nivel === 2 && aviso.evento && aviso.cierraEnMs
      ? { evento: aviso.evento, cierraEnMs: aviso.cierraEnMs }
      : null;

  return (
    <>
      <TopBar ahora={ahora} ubicacionLabel={homeLabel} homeLat={homeLat} homeLon={homeLon} health={datos.health} />
      <div className={styles.cuerpo}>
        <div className={styles.col}>
          <MapColumn eventos={datos.eventos48h} homeLat={homeLat} homeLon={homeLon} />
        </div>
        <div className={styles.colB}>
          <EventList
            eventos={datos.eventos48h}
            ahora={ahora}
            homeLat={homeLat}
            homeLon={homeLon}
            avisoNivel2={avisoNivel2}
          />
        </div>
        <div className={styles.colSinBorde}>
          <StatusColumn
            eventos48h={datos.eventos48h}
            eventosSignificativos90d={datos.eventosSignificativos90d}
            health={datos.health}
            connEstado={datos.connEstado}
            ultimoPaqueteEn={datos.ultimoPaqueteEn}
            pollIntervalS={datos.config?.poll_interval_s ?? 30}
            ahora={ahora}
          />
        </div>
      </div>
    </>
  );
}
