import { colorSaludFuente, haceTiempo, saludFuente } from "@/lib/derive";
import type { FuenteId, RawHealth } from "@/lib/types";
import styles from "./StatusColumn.module.css";

const FUENTES: FuenteId[] = ["CSN", "USGS", "EMSC"];

function latenciaLabel(salud: string, detalle: RawHealth[FuenteId] | undefined, ahoraMs: number): string {
  if (!detalle?.last_success_at) return "SIN DATO";
  const hace = haceTiempo(detalle.last_success_at, ahoraMs);
  return salud === "falla" ? `FALLA · ÚLT. OK ${hace}` : `ÚLT. OK ${hace}`;
}

export function SourceHealth({
  health,
  sourceCadenceS,
  ahora,
}: {
  health: RawHealth | null;
  sourceCadenceS: Record<FuenteId, number | null> | null;
  ahora: Date;
}) {
  const ahoraMs = ahora.getTime();
  return (
    <section className={styles.modulo}>
      <span className={styles.tituloModulo}>SALUD DEL SISTEMA</span>
      <div className={styles.filasFuente}>
        {FUENTES.map((f) => {
          const detalle = health?.[f];
          const salud = saludFuente(detalle, sourceCadenceS?.[f], ahoraMs);
          return (
            <div key={f} className={styles.filaFuente}>
              <span className={styles.puntoFuente} style={{ background: colorSaludFuente(salud) }} />
              <span className={styles.siglaFuente}>{f}</span>
              {/* El color del punto (verde/ámbar/gris) ya lleva el juicio de
                  saludFuente; el texto solo distingue "normal" de "atención"
                  -- no necesita un tercer estilo de texto. */}
              <span className={salud === "ok" ? styles.latencia : styles.latenciaFalla}>
                {latenciaLabel(salud, detalle, ahoraMs)}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
