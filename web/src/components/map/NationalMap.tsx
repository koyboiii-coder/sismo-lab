"use client";

import { useMemo, type MouseEvent } from "react";
import { colorPorProfundidad, diametroPorMagnitud } from "@/lib/constants";
import { enChile, sinUbicar } from "@/lib/derive";
import type { RawEvent } from "@/lib/types";
import { chilePath, MAPA_ALTO, MAPA_ANCHO, proyectar } from "./projection";
import styles from "./NationalMap.module.css";

export function NationalMap({
  eventos,
  homeLat,
  homeLon,
  explorando = false,
  onSeleccionarEvento,
}: {
  eventos: RawEvent[];
  homeLat: number;
  homeLon: number;
  /** Modo exploración (ver state/useExploreMode.ts). */
  explorando?: boolean;
  onSeleccionarEvento?: (clusterKey: string) => void;
}) {
  // enChile, no solo "tiene coordenadas": eventos48h es el log GLOBAL (USGS
  // y sobre todo EMSC no filtran por Chile -- ver CLAUDE.md, fuentes de
  // datos), así que sin este filtro el mapa nacional terminaba dibujando
  // también la sismicidad mundial de las últimas 48h (cientos de eventos
  // reales, no un bug de datos) encima de Chile. La cabecera del panel
  // (MapColumn.tsx) ya contaba solo los de Chile; el mapa ahora cuenta lo
  // mismo que muestra esa cifra.
  const ubicables = useMemo(() => eventos.filter((e) => !sinUbicar(e) && enChile(e)), [eventos]);
  const homePos = proyectar(homeLat, homeLon);
  const path = useMemo(() => chilePath(), []);

  /**
   * Un solo listener en el <svg>, no un círculo invisible por punto: en
   * la tablet real, tocar un punto seguía abriendo un "detalle" vacío --
   * el objetivo de toque de cada punto (antes, un <circle> transparente
   * de 44px) dependía de que el mapeo de coordenadas de pantalla a
   * unidades del viewBox fuera 1:1, algo que no se puede asumir bajo
   * cualquier configuración de zoom/escala del WebView (Fully Kiosk
   * permite fijar su propio initial-scale y tamaño de fuente por
   * separado de esta página). getScreenCTM().inverse() traduce el punto
   * de toque real a coordenadas del viewBox sin importar ese factor de
   * escala externo, y de ahí se busca el evento más cercano -- así
   * "tocar cerca de un punto" siempre resuelve a ALGÚN evento en vez de,
   * si el toque cae unos px al lado, no tocar nada.
   */
  function alTocarMapa(evt: MouseEvent<SVGSVGElement>) {
    if (!explorando || ubicables.length === 0 || !onSeleccionarEvento) return;
    const svg = evt.currentTarget;
    const ctm = svg.getScreenCTM();
    if (!ctm) return;
    const punto = svg.createSVGPoint();
    punto.x = evt.clientX;
    punto.y = evt.clientY;
    const local = punto.matrixTransform(ctm.inverse());

    let mejor: RawEvent | null = null;
    let mejorDist = Infinity;
    for (const e of ubicables) {
      const pos = proyectar(e.latitude!, e.longitude!);
      if (!pos) continue;
      const dx = pos[0] - local.x;
      const dy = pos[1] - local.y;
      const dist = dx * dx + dy * dy;
      if (dist < mejorDist) {
        mejorDist = dist;
        mejor = e;
      }
    }
    if (mejor) onSeleccionarEvento(mejor.cluster_key);
  }

  return (
    <div className={styles.contenedor}>
      <div className={styles.lienzo}>
        <svg
          className={styles.mapaSvg}
          viewBox={`0 0 ${MAPA_ANCHO} ${MAPA_ALTO}`}
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label="Mapa de actividad sísmica nacional"
          onClick={explorando ? alTocarMapa : undefined}
          style={explorando ? { cursor: "pointer" } : undefined}
        >
          <path d={path} fill="var(--fondo-lienzo)" stroke="var(--div-fuerte)" strokeWidth={1} />
          {ubicables.map((e) => {
            const pos = proyectar(e.latitude!, e.longitude!);
            if (!pos) return null;
            const diametro = diametroPorMagnitud(e.magnitude);
            const color = colorPorProfundidad(e.depth_km);
            return (
              <circle
                key={e.cluster_key}
                cx={pos[0]}
                cy={pos[1]}
                r={diametro / 2}
                fill={color}
                fillOpacity={0.28}
                stroke={color}
                strokeWidth={1.5}
              />
            );
          })}
          {homePos && (
            <rect
              x={homePos[0] - 9}
              y={homePos[1] - 9}
              width={18}
              height={18}
              fill="none"
              stroke="var(--tinta)"
              strokeWidth={2}
            />
          )}
        </svg>
      </div>

      <div className={styles.leyenda}>
        <div className={styles.leyendaGrupo}>
          <span className={styles.leyendaEtiqueta}>PROFUNDIDAD</span>
          <span className={styles.leyendaItem}>
            <span className={styles.muestraColor} style={{ background: "var(--degradado)" }} /> 0–35 KM
          </span>
          <span className={styles.leyendaItem}>
            <span className={styles.muestraColor} style={{ background: "var(--nominal)" }} /> 35–120 KM
          </span>
          <span className={styles.leyendaItem}>
            <span className={styles.muestraColor} style={{ background: "var(--profundo)" }} /> +120 KM
          </span>
        </div>
        <div className={styles.leyendaGrupo}>
          <span className={styles.leyendaEtiqueta}>MAGNITUD</span>
          {[2, 3, 4, 5].map((m) => (
            <span key={m} className={styles.leyendaItem}>
              <span
                className={styles.muestraCirculo}
                style={{ width: diametroPorMagnitud(m), height: diametroPorMagnitud(m) }}
              />
              M{m}
            </span>
          ))}
        </div>
        <div className={styles.leyendaGrupo}>
          <span className={styles.leyendaItem}>
            <span className={styles.muestraCuadrado} /> MI UBICACIÓN
          </span>
        </div>
      </div>
    </div>
  );
}
