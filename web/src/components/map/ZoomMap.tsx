"use client";

import styles from "./ZoomMap.module.css";

const ANCHO = 718;
const ALTO = 620;
const PX_POR_KM = 1.3;
const ANILLOS_KM = [50, 100, 200];

/**
 * Proyección local plana (equirectangular corregida por coseno de
 * latitud), no Mercator: a esta escala (radio <300km) la distorsión de
 * Mercator no aporta nada y complica el cálculo de los anillos de
 * distancia, que son círculos euclidianos por construcción acá.
 */
function proyectarLocal(homeLat: number, homeLon: number, lat: number, lon: number): [number, number] {
  const kmPorGradoLat = 111.32;
  const kmPorGradoLon = 111.32 * Math.cos((homeLat * Math.PI) / 180);
  const dx = (lon - homeLon) * kmPorGradoLon * PX_POR_KM;
  const dy = (lat - homeLat) * kmPorGradoLat * PX_POR_KM;
  return [ANCHO / 2 + dx, ALTO / 2 - dy];
}

export function ZoomMap({
  homeLat,
  homeLon,
  eventoLat,
  eventoLon,
}: {
  homeLat: number;
  homeLon: number;
  eventoLat: number | null;
  eventoLon: number | null;
}) {
  const home: [number, number] = [ANCHO / 2, ALTO / 2];
  const epicentro =
    eventoLat != null && eventoLon != null ? proyectarLocal(homeLat, homeLon, eventoLat, eventoLon) : null;

  return (
    <svg width={ANCHO} height={ALTO} viewBox={`0 0 ${ANCHO} ${ALTO}`} className={styles.svg} role="img" aria-label="Epicentro y distancia">
      {ANILLOS_KM.map((km) => (
        <g key={km}>
          <circle cx={home[0]} cy={home[1]} r={km * PX_POR_KM} fill="none" stroke="var(--div-fuerte)" strokeWidth={1} />
          <text x={home[0] + km * PX_POR_KM + 6} y={home[1] - 4} className={styles.etiquetaAnillo}>
            {km} KM
          </text>
        </g>
      ))}
      <line x1={home[0] - 14} y1={home[1]} x2={home[0] + 14} y2={home[1]} stroke="var(--tinta)" strokeWidth={2} />
      <line x1={home[0]} y1={home[1] - 14} x2={home[0]} y2={home[1] + 14} stroke="var(--tinta)" strokeWidth={2} />
      {epicentro && (
        <>
          <line x1={home[0]} y1={home[1]} x2={epicentro[0]} y2={epicentro[1]} stroke="var(--alerta)" strokeWidth={1} strokeDasharray="4 4" />
          <circle cx={epicentro[0]} cy={epicentro[1]} r={10} fill="var(--alerta)" fillOpacity={0.3} stroke="var(--alerta)" strokeWidth={2} />
        </>
      )}
    </svg>
  );
}
