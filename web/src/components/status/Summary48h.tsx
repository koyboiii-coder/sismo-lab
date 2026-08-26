import { resumen48h } from "@/lib/derive";
import type { RawEvent } from "@/lib/types";
import styles from "./StatusColumn.module.css";

function Celda({ valor, etiqueta }: { valor: number | string; etiqueta: string }) {
  const esCero = valor === 0 || valor === "0";
  return (
    <div className={styles.celdaResumen}>
      <span className={esCero ? styles.cifraResumenCero : styles.cifraResumen}>{valor}</span>
      <span className={styles.etiquetaResumen}>{etiqueta}</span>
    </div>
  );
}

export function Summary48h({ eventos }: { eventos: RawEvent[] }) {
  const r = resumen48h(eventos);
  return (
    <section className={styles.modulo}>
      <span className={styles.tituloModulo}>Resumen 48 h · Chile</span>
      <div className={styles.grillaResumen}>
        <Celda valor={r.total} etiqueta="Eventos" />
        <Celda valor={String(r.sobreMag4).padStart(2, "0")} etiqueta="M 4.0+" />
        <Celda valor={r.magMax != null ? r.magMax.toFixed(1) : "—"} etiqueta="Magnitud máx." />
        <Celda valor={String(r.sentidosAqui).padStart(2, "0")} etiqueta="Sentidos aquí" />
      </div>
    </section>
  );
}
