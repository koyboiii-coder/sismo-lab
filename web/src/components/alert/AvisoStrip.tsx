"use client";

import { cuentaRegresiva, haceTiempo, km, magnitud, mmiRomano } from "@/lib/derive";
import type { RawEvent } from "@/lib/types";
import styles from "./AvisoStrip.module.css";

/** handoff §5.1, nivel 2: franja discreta de 120px sobre la lista de
 * eventos. No pide toque, no suena -- se cierra sola. */
export function AvisoStrip({ evento, cierraEnMs, ahoraMs }: { evento: RawEvent; cierraEnMs: number; ahoraMs: number }) {
  const restanteS = Math.max(0, Math.round((cierraEnMs - ahoraMs) / 1000));
  const mmiTexto = mmiRomano(evento.estimated_mmi);

  return (
    <div className={styles.franja}>
      <div className={styles.barraLateral} />
      <span className={styles.magnitud}>M {magnitud(evento.magnitude)}</span>
      <span className={styles.separador} />
      <div className={styles.detalle}>
        <span className={styles.lugar}>
          {evento.region ?? "región desconocida"} · {km(evento.distance_km)}
        </span>
        <span className={styles.meta}>
          {mmiTexto ? `MMI ${mmiTexto} AQUÍ` : "SIN MMI AQUÍ"} · PROF. {km(evento.depth_km)} ·{" "}
          {haceTiempo(evento.origin_time, ahoraMs)}
        </span>
      </div>
      <span className={styles.cuentaRegresiva}>SE CIERRA EN {cuentaRegresiva(restanteS)}</span>
    </div>
  );
}
