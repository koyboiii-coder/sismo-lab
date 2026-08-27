import { MMI_ALERTA_COMPLETA } from "@/lib/constants";
import { haceTiempo, mmiRomano } from "@/lib/derive";
import type { SseEstado } from "@/lib/sse";
import styles from "./StatusColumn.module.css";

export function StatusFooter({
  ultimoPaqueteEn,
  connEstado,
  pollIntervalS,
  ahoraMs,
}: {
  ultimoPaqueteEn: number | null;
  connEstado: SseEstado;
  pollIntervalS: number;
  ahoraMs: number;
}) {
  const colorPunto = connEstado === "conectado" ? "var(--nominal)" : "var(--degradado)";

  return (
    <div className={styles.pie}>
      <div className={styles.pieSuperior}>
        <span className={styles.puntoNominal} style={{ background: colorPunto }} />
        <span>
          {ultimoPaqueteEn != null
            ? `PAQUETE RECIBIDO ${haceTiempo(new Date(ultimoPaqueteEn).toISOString(), ahoraMs)}`
            : "SIN PAQUETES RECIBIDOS"}
        </span>
      </div>
      <span className={styles.pieInferior}>
        SONDEO CADA {pollIntervalS} S · AGREGADOR v1.0 · UMBRAL DE AVISO MMI {mmiRomano(MMI_ALERTA_COMPLETA)} O M 5.5 A MENOS DE 300 KM
      </span>
    </div>
  );
}
