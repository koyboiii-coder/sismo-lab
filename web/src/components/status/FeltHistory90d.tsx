import { esSentido, horaCortaCLT, magnitud, mmiRomano } from "@/lib/derive";
import type { RawEvent } from "@/lib/types";
import styles from "./StatusColumn.module.css";

const FILAS_VISIBLES = 4;

export function FeltHistory90d({ eventos }: { eventos: RawEvent[] }) {
  const sentidos = eventos
    .filter(esSentido)
    .sort((a, b) => new Date(b.origin_time).getTime() - new Date(a.origin_time).getTime())
    .slice(0, FILAS_VISIBLES);

  return (
    <section className={`${styles.modulo} ${styles.moduloFlex}`}>
      <span className={styles.tituloModulo}>Sentidos aquí · 90 días</span>
      <div className={styles.filasSentidos}>
        {sentidos.length === 0 && <span className={styles.sinDato}>SIN SISMOS SENTIDOS EN 90 DÍAS</span>}
        {sentidos.map((e) => {
          const romano = mmiRomano(e.estimated_mmi);
          const esAlto = (e.estimated_mmi ?? 0) >= 5;
          return (
            <div key={e.cluster_key} className={styles.filaSentido}>
              <span className={styles.fechaSentido}>{horaCortaCLT(e.origin_time)}</span>
              <span className={styles.magnitudSentido}>M{magnitud(e.magnitude)}</span>
              <span className={styles.lugarSentido}>{e.region ?? "región desconocida"}</span>
              <span className={`${styles.mmiSentido} ${esAlto ? styles.mmiSentidoAlerta : ""}`}>
                MMI {romano ?? "—"}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
