import { eventosMundiales, haceTiempo, km, magnitud } from "@/lib/derive";
import type { RawEvent } from "@/lib/types";
import styles from "./StatusColumn.module.css";

export function WorldQuakes({ eventos, ahora }: { eventos: RawEvent[]; ahora: Date }) {
  const mundiales = eventosMundiales(eventos).slice(0, 3);
  return (
    <section className={styles.modulo}>
      <span className={styles.tituloModulo}>Sismicidad mundial M 6.0+</span>
      {mundiales.length === 0 ? (
        <span className={styles.sinDato}>SIN EVENTOS M 6.0+ EN EL PERÍODO</span>
      ) : (
        <div className={styles.listaMundial}>
          {mundiales.map((e) => (
            <div key={e.cluster_key} className={styles.itemMundial}>
              <div className={styles.filaMundialSuperior}>
                <span className={styles.magnitudMundial}>{magnitud(e.magnitude)}</span>
                <span className={styles.lugarMundial}>{e.region ?? "región desconocida"}</span>
              </div>
              <span className={styles.metaMundial}>
                {haceTiempo(e.origin_time, ahora.getTime())} · PROF. {km(e.depth_km)}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
