import type { FuenteId, RawHealth, RawEvent } from "@/lib/types";
import type { SseEstado } from "@/lib/sse";
import { FeltHistory90d } from "./FeltHistory90d";
import { SourceHealth } from "./SourceHealth";
import styles from "./StatusColumn.module.css";
import { StatusFooter } from "./StatusFooter";
import { Summary48h } from "./Summary48h";
import { WorldQuakes } from "./WorldQuakes";

export function StatusColumn({
  eventos48h,
  eventosSignificativos90d,
  health,
  sourceCadenceS,
  connEstado,
  ultimoPaqueteEn,
  pollIntervalS,
  ahora,
}: {
  eventos48h: RawEvent[];
  eventosSignificativos90d: RawEvent[];
  health: RawHealth | null;
  sourceCadenceS: Record<FuenteId, number | null> | null;
  connEstado: SseEstado;
  ultimoPaqueteEn: number | null;
  pollIntervalS: number;
  ahora: Date;
}) {
  return (
    <div className={styles.columna}>
      <SourceHealth health={health} sourceCadenceS={sourceCadenceS} ahora={ahora} />
      <WorldQuakes eventos={eventos48h} ahora={ahora} />
      <Summary48h eventos={eventos48h} />
      <FeltHistory90d eventos={eventosSignificativos90d} />
      <StatusFooter
        ultimoPaqueteEn={ultimoPaqueteEn}
        connEstado={connEstado}
        pollIntervalS={pollIntervalS}
        ahoraMs={ahora.getTime()}
      />
    </div>
  );
}
