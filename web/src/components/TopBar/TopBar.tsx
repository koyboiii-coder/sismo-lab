"use client";

import { fechaLargaCLT, horaCLT } from "@/lib/derive";
import type { FuenteId, RawHealth } from "@/lib/types";
import styles from "./TopBar.module.css";

const FUENTES: FuenteId[] = ["CSN", "USGS", "EMSC"];

function colorEstado(status: RawHealth[FuenteId]["status"] | undefined): string {
  if (status === "ok") return "var(--nominal)";
  if (status === "degraded") return "var(--degradado)";
  return "var(--tinta-4)";
}

export function TopBar({
  ahora,
  ubicacionLabel,
  homeLat,
  homeLon,
  health,
}: {
  ahora: Date;
  ubicacionLabel: string;
  // null mientras /api/config no ha llegado (o falló) -- nunca se rellena
  // con una coordenada de relleno que parezca un dato real, ver
  // CLAUDE.md "Sin default de ubicación en silencio".
  homeLat: number | null;
  homeLon: number | null;
  health: RawHealth | null;
}) {
  const ubicacionTexto =
    homeLat != null && homeLon != null
      ? `${ubicacionLabel.toUpperCase()} · ${Math.abs(homeLat).toFixed(3)}°${homeLat < 0 ? "S" : "N"} ${Math.abs(homeLon).toFixed(3)}°${homeLon < 0 ? "W" : "E"}`
      : "UBICACIÓN NO DISPONIBLE";

  return (
    <header className={styles.barra}>
      <span className={styles.titulo}>MONITOR SÍSMICO</span>
      <span className={styles.separador} />
      <span className={styles.ubicacion}>{ubicacionTexto}</span>

      <span className={styles.relleno} />

      <div className={styles.fuentes}>
        {FUENTES.map((f) => (
          <span key={f} className={styles.fuente}>
            <span
              className={styles.puntoFuente}
              style={{ background: colorEstado(health?.[f]?.status) }}
              aria-hidden
            />
            {f}
          </span>
        ))}
      </div>

      <span className={styles.separador} />

      <div className={styles.reloj}>
        <span className={styles.horaGrande}>{horaCLT(ahora.toISOString())}</span>
        <span className={styles.fecha}>{fechaLargaCLT(ahora)}</span>
      </div>
    </header>
  );
}
