import type { FuenteId, RawHealth } from "@/lib/types";
import styles from "./StatusColumn.module.css";

const FUENTES: FuenteId[] = ["CSN", "USGS", "EMSC"];

function colorEstado(status: RawHealth[FuenteId]["status"] | undefined): string {
  if (status === "ok") return "var(--nominal)";
  if (status === "degraded") return "var(--degradado)";
  return "var(--tinta-4)";
}

function latenciaLabel(detalle: RawHealth[FuenteId] | undefined): string {
  if (!detalle || !detalle.last_success_at) return "SIN DATO";
  const segundos = Math.round((Date.now() - new Date(detalle.last_success_at).getTime()) / 1000);
  return `ÚLT. OK HACE ${segundos} S`;
}

export function SourceHealth({ health }: { health: RawHealth | null }) {
  return (
    <section className={styles.modulo}>
      <span className={styles.tituloModulo}>SALUD DEL SISTEMA</span>
      <div className={styles.filasFuente}>
        {FUENTES.map((f) => {
          const detalle = health?.[f];
          const enFalla = detalle?.status !== "ok";
          return (
            <div key={f} className={styles.filaFuente}>
              <span className={styles.puntoFuente} style={{ background: colorEstado(detalle?.status) }} />
              <span className={styles.siglaFuente}>{f}</span>
              <span className={enFalla ? styles.latenciaFalla : styles.latencia}>
                {enFalla ? "SIN DATO" : latenciaLabel(detalle)}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
