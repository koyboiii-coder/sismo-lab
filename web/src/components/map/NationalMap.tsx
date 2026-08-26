"use client";

import { useMemo } from "react";
import { colorPorProfundidad, diametroPorMagnitud } from "@/lib/constants";
import { sinUbicar } from "@/lib/derive";
import type { RawEvent } from "@/lib/types";
import { chilePath, MAPA_ALTO, MAPA_ANCHO, proyectar } from "./projection";
import styles from "./NationalMap.module.css";

const HISTOGRAMA_ANCHO = 64;
const HISTOGRAMA_BANDAS = 14;

export function NationalMap({
  eventos,
  homeLat,
  homeLon,
}: {
  eventos: RawEvent[];
  homeLat: number;
  homeLon: number;
}) {
  const ubicables = useMemo(() => eventos.filter((e) => !sinUbicar(e)), [eventos]);
  const homePos = proyectar(homeLat, homeLon);
  const path = useMemo(() => chilePath(), []);

  const bandas = useMemo(() => {
    const conteos = new Array(HISTOGRAMA_BANDAS).fill(0);
    for (const e of ubicables) {
      const y = proyectar(e.latitude!, e.longitude!)?.[1];
      if (y == null) continue;
      const indice = Math.min(
        HISTOGRAMA_BANDAS - 1,
        Math.max(0, Math.floor((y / MAPA_ALTO) * HISTOGRAMA_BANDAS)),
      );
      conteos[indice] += 1;
    }
    const max = Math.max(1, ...conteos);
    return conteos.map((n, i) => ({
      n,
      y: (i / HISTOGRAMA_BANDAS) * MAPA_ALTO,
      alto: MAPA_ALTO / HISTOGRAMA_BANDAS - 1,
      anchoPx: (n / max) * HISTOGRAMA_ANCHO,
    }));
  }, [ubicables]);

  return (
    <div className={styles.contenedor}>
      <div className={styles.lienzo}>
        <svg
          width={MAPA_ANCHO}
          height={MAPA_ALTO}
          viewBox={`0 0 ${MAPA_ANCHO} ${MAPA_ALTO}`}
          role="img"
          aria-label="Mapa de actividad sísmica nacional"
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

        <svg
          className={styles.histograma}
          width={HISTOGRAMA_ANCHO}
          height={MAPA_ALTO}
          aria-hidden
        >
          {bandas.map(
            (b, i) =>
              b.n > 0 && (
                <rect
                  key={i}
                  x={0}
                  y={b.y}
                  width={b.anchoPx}
                  height={b.alto}
                  fill="var(--degradado)"
                  fillOpacity={0.75}
                />
              ),
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
