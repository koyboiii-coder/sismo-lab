"use client";

import { TopBar } from "@/components/TopBar/TopBar";
import { duracionHoraMin, horaCLT } from "@/lib/derive";
import type { FuenteId, RawHealth } from "@/lib/types";
import styles from "./ErrorState.module.css";

const FUENTES: FuenteId[] = ["CSN", "USGS", "EMSC"];

export function ErrorState({
  ahora,
  ultimoPaqueteEn,
  health,
  sourceCadenceS,
  homeLat,
  homeLon,
  homeLabel,
}: {
  ahora: Date;
  ultimoPaqueteEn: number | null;
  health: RawHealth | null;
  sourceCadenceS: Record<FuenteId, number | null> | null;
  homeLat: number | null;
  homeLon: number | null;
  homeLabel: string;
}) {
  const sinDatoMs = ultimoPaqueteEn != null ? ahora.getTime() - ultimoPaqueteEn : null;

  return (
    <>
      <div className={styles.barraGris}>
        <TopBar
          ahora={ahora}
          ubicacionLabel={homeLabel}
          homeLat={homeLat}
          homeLon={homeLon}
          health={health}
          sourceCadenceS={sourceCadenceS}
        />
      </div>
      <div className={styles.cuerpo}>
        <span className={styles.sinDatoCifra}>{sinDatoMs != null ? duracionHoraMin(sinDatoMs) : "—"}</span>
        <span className={styles.sinDatoEtiqueta}>
          SIN DATO {ultimoPaqueteEn != null && `· ÚLTIMO PAQUETE VÁLIDO ${horaCLT(new Date(ultimoPaqueteEn).toISOString())}`}
        </span>

        <p className={styles.mensajeCentral}>NO PUEDO AFIRMAR QUE NO HAY SISMOS</p>

        <div className={styles.filasFuente}>
          {FUENTES.map((f) => (
            <div key={f} className={styles.filaFuente}>
              <span className={styles.puntoAmbar} />
              <span className={styles.sigla}>{f}</span>
              <span className={styles.etiquetaSinDato}>SIN DATO</span>
            </div>
          ))}
        </div>

        <span className={styles.reintento}>REINTENTANDO CONEXIÓN…</span>
      </div>
    </>
  );
}
