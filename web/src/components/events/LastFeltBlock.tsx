import { duracionHoraMin, haceTiempo, magnitud, mmiRomano } from "@/lib/derive";
import type { RawEvent } from "@/lib/types";
import styles from "./LastFeltBlock.module.css";

export function LastFeltBlock({ evento, ahora }: { evento: RawEvent | null; ahora: Date }) {
  if (!evento) {
    return (
      <div className={styles.bloque}>
        <span className={styles.sinDato}>SIN SISMOS SENTIDOS EN EL PERÍODO REGISTRADO</span>
      </div>
    );
  }

  const rachaMs = ahora.getTime() - new Date(evento.origin_time).getTime();

  return (
    <div className={styles.bloque}>
      <div className={styles.izquierda}>
        <span className={styles.hace}>{haceTiempo(evento.origin_time, ahora.getTime())}</span>
        <span className={styles.separador} />
        <span className={styles.resumen}>
          M {magnitud(evento.magnitude)} · {evento.region ?? "región desconocida"} · Mercalli{" "}
          {mmiRomano(evento.estimated_mmi) ?? "—"}
        </span>
      </div>
      <div className={styles.derecha}>
        <span className={styles.etiquetaRacha}>RACHA SIN SISMOS SENTIBLES</span>
        <span className={styles.racha}>{duracionHoraMin(rachaMs)}</span>
      </div>
    </div>
  );
}
