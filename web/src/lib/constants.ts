/**
 * Umbrales espejados desde el backend -- CLAUDE.md "Motor de reglas" y
 * daemon/intensity.py (LOCAL_SIGNIFICANT_MMI, FULL_ALERT_MMI). El backend
 * ya hace la clasificación autoritativa por evento vía `is_significant` /
 * `alert_level_sent`; estas constantes solo sirven para decidir la
 * escalera de aviso (nivel 1/2/3, handoff §5.1) en el cliente a partir de
 * `estimated_mmi`, sin reimplementar el GMPE. Si CLAUDE.md cambia estos
 * números, actualizar ambos lados.
 */
export const MMI_SILENCIOSO = 3; // III
export const MMI_ALERTA_COMPLETA = 5; // V
export const MAGNITUD_MUNDIAL = 6.5;

/** Ventana de eventos "nacional" mostrada en columna A / lista principal. */
export const VENTANA_EVENTOS_HORAS = 48;

/** handoff §7: "Sondeo cada 30 s". */
export const POLL_INTERVAL_S_DEFAULT = 30;

/** handoff §5.1 -- duraciones de cada nivel de aviso. */
export const DURACION_AVISO_NIVEL2_S = 3 * 60;
export const DURACION_AVISO_NIVEL3_S = 45;

/** handoff §4 -- fin del estado de alerta: 20 min sin réplica M>=3.5. */
export const ALERTA_SALIDA_MINUTOS = 20;
export const ALERTA_REPLICA_MAGNITUD_MIN = 3.5;

/** handoff §5.1 -- ventana de silencio/atenuación nocturna, hora local Chile. */
export const NOCHE_INICIO_HORA = 23;
export const NOCHE_FIN_HORA = 7;

/** handoff §3.1 -- reintento de reconexión SSE, backoff exponencial. */
export const SSE_BACKOFF_INICIAL_MS = 1000;
export const SSE_BACKOFF_MAXIMO_MS = 30_000;

/**
 * Modo exploración (puntos 4/5 del feedback post-tablet, ver CLAUDE.md) --
 * único punto de entrada táctil del dashboard, fuera del requisito de
 * diseño "sin interacción" (handoff §1). Presión larga, no un tap: un
 * roce contra la pared no debe sacar el dashboard de su estado normal.
 */
export const EXPLORACION_PRESION_LARGA_MS = 800;
export const EXPLORACION_INACTIVIDAD_S = 120;
/** Gracia extra, avisada, antes de descartar una nota con trazos sin
 * guardar -- escribir a mano toma más que mirar un mapa. */
export const EXPLORACION_AVISO_DESCARTE_S = 30;

/** handoff §3.2 -- radio de círculo por magnitud, en px de diámetro. */
export const RADIO_POR_MAGNITUD: { magnitudMin: number; diametroPx: number }[] = [
  { magnitudMin: 2, diametroPx: 8 },
  { magnitudMin: 3, diametroPx: 16 },
  { magnitudMin: 4, diametroPx: 26 },
  { magnitudMin: 5, diametroPx: 38 },
];

/** daemon/dedup.py:in_chile_bbox -- mismo bounding box que usa el backend. */
export const CHILE_BBOX = { minLat: -56, maxLat: -17, minLon: -76, maxLon: -66 };

/** handoff §3.2 -- diámetro de círculo por magnitud, interpolado entre los
 * puntos dados y extrapolado linealmente sobre M5 (no especificado, pero
 * los sismos grandes deben seguir creciendo, no aplanarse en 38px). */
export function diametroPorMagnitud(magnitud: number | null): number {
  if (magnitud == null) return RADIO_POR_MAGNITUD[0].diametroPx;
  const tabla = RADIO_POR_MAGNITUD;
  if (magnitud <= tabla[0].magnitudMin) return tabla[0].diametroPx;
  for (let i = 0; i < tabla.length - 1; i++) {
    const a = tabla[i];
    const b = tabla[i + 1];
    if (magnitud >= a.magnitudMin && magnitud <= b.magnitudMin) {
      const t = (magnitud - a.magnitudMin) / (b.magnitudMin - a.magnitudMin);
      return a.diametroPx + t * (b.diametroPx - a.diametroPx);
    }
  }
  const ultimo = tabla[tabla.length - 1];
  const penultimo = tabla[tabla.length - 2];
  const pendiente = (ultimo.diametroPx - penultimo.diametroPx) / (ultimo.magnitudMin - penultimo.magnitudMin);
  return ultimo.diametroPx + pendiente * (magnitud - ultimo.magnitudMin);
}

/** handoff §2 -- color por profundidad, única escala cromática del mapa/lista. */
export function colorPorProfundidad(depthKm: number | null): string {
  if (depthKm == null) return "var(--tinta-4)";
  if (depthKm < 35) return "var(--degradado)";
  if (depthKm <= 120) return "var(--nominal)";
  return "var(--profundo)";
}
