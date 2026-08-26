/**
 * Todo lo que docs/design/handoff.md §7 asume que el backend entrega
 * (lugar, rumbo, "sentido", nivel de aviso, resúmenes) pero que la API
 * real (api/notifier.py) no calcula, se deriva acá a partir de los campos
 * crudos de RawEvent. Ver lib/types.ts para por qué.
 */
import {
  CHILE_BBOX,
  MMI_SILENCIOSO,
  MMI_ALERTA_COMPLETA,
  MAGNITUD_MUNDIAL,
} from "./constants";
import type { FuenteId, RawEvent, RawEventReport } from "./types";

const ORDEN_FUENTES: FuenteId[] = ["CSN", "USGS", "EMSC"];

/** "CSN + USGS · 2 DE 3 FUENTES CONFIRMAN" -- a partir de los reportes
 * crudos de GET /api/events/{cluster_key} (ver state/useEventDetail.ts). */
export function fuentesConfirmantes(reportes: RawEventReport[]): FuenteId[] {
  const vistas = new Set(reportes.map((r) => r.source));
  return ORDEN_FUENTES.filter((f) => vistas.has(f));
}

// ---------------------------------------------------------------------
// Geometría: rumbo desde HOME hacia el epicentro
// ---------------------------------------------------------------------

const COMPASS_8 = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"] as const;
export type Rumbo = (typeof COMPASS_8)[number];

/** Rumbo inicial (great-circle) de home hacia (lat, lon), en 8 puntos. */
export function rumboDesdeHome(
  homeLat: number,
  homeLon: number,
  lat: number,
  lon: number,
): Rumbo {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const phi1 = toRad(homeLat);
  const phi2 = toRad(lat);
  const deltaLambda = toRad(lon - homeLon);
  const y = Math.sin(deltaLambda) * Math.cos(phi2);
  const x =
    Math.cos(phi1) * Math.sin(phi2) -
    Math.sin(phi1) * Math.cos(phi2) * Math.cos(deltaLambda);
  const deg = ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
  const index = Math.round(deg / 45) % 8;
  return COMPASS_8[index];
}

export function sinUbicar(event: RawEvent): boolean {
  return event.latitude == null || event.longitude == null;
}

export function enChile(event: RawEvent): boolean {
  if (sinUbicar(event)) return false;
  const { latitude: lat, longitude: lon } = event;
  return (
    lat! >= CHILE_BBOX.minLat &&
    lat! <= CHILE_BBOX.maxLat &&
    lon! >= CHILE_BBOX.minLon &&
    lon! <= CHILE_BBOX.maxLon
  );
}

// ---------------------------------------------------------------------
// Intensidad
// ---------------------------------------------------------------------

const NUMERALES_ROMANOS = [
  "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII",
];

/** null si la intensidad es demasiado baja para considerarse perceptible. */
export function mmiRomano(mmi: number | null): string | null {
  if (mmi == null || mmi < 1) return null;
  const indice = Math.min(12, Math.max(1, Math.round(mmi))) - 1;
  return NUMERALES_ROMANOS[indice];
}

/** handoff §4/§5: "sentido" = intensidad estimada aquí en umbral de aviso silencioso o más. */
export function esSentido(event: RawEvent): boolean {
  return event.estimated_mmi != null && event.estimated_mmi >= MMI_SILENCIOSO;
}

export function esMundial(event: RawEvent): boolean {
  return event.magnitude != null && event.magnitude >= MAGNITUD_MUNDIAL;
}

const DESCRIPCION_MMI: Record<number, string> = {
  1: "Imperceptible, solo registrado por instrumentos.",
  2: "Lo sienten muy pocas personas en reposo.",
  3: "Se percibe claramente en interiores, como el paso de un camión liviano.",
  4: "Lo sienten muchos en interiores, pocos afuera. Vibran vajillas y ventanas.",
  5: "Lo siente casi todos. Objetos pequeños se desplazan, algunos duermen despiertan.",
  6: "Sacudida fuerte. Objetos inestables se desplazan o caen. Daño leve.",
  7: "Daño despreciable en construcciones bien diseñadas, considerable en las deficientes.",
  8: "Daño leve en estructuras especialmente diseñadas, grande en construcciones ordinarias.",
  9: "Daño considerable en estructuras diseñadas, grandes daños en edificios comunes.",
  10: "Destrucción de muchas estructuras de madera y mampostería bien construidas.",
  11: "Pocas estructuras de mampostería quedan en pie. Puentes destruidos.",
  12: "Destrucción total. Ondas visibles en la superficie del suelo.",
};

export function descripcionMmi(mmi: number | null): string | null {
  if (mmi == null || mmi < 1) return null;
  const indice = Math.min(12, Math.max(1, Math.round(mmi)));
  return DESCRIPCION_MMI[indice];
}

// ---------------------------------------------------------------------
// Nivel de aviso -- handoff §5.1, derivado de estimated_mmi (ver
// lib/constants.ts: el backend ya hace esta clasificación por evento vía
// alert_level_sent, esto solo reproduce el mismo umbral para la máquina
// de estados del aviso en el cliente).
// ---------------------------------------------------------------------

export type NivelAviso = 1 | 2 | 3;

export function nivelAviso(event: RawEvent): NivelAviso {
  const mmi = event.estimated_mmi;
  if (mmi != null && mmi >= MMI_ALERTA_COMPLETA) return 3;
  if (mmi != null && mmi >= MMI_SILENCIOSO) return 2;
  return 1;
}

// ---------------------------------------------------------------------
// Tiempo -- todo en hora de Chile en la capa de presentación (CLAUDE.md
// regla 1: se almacena en UTC, se convierte solo acá).
// ---------------------------------------------------------------------

const TZ = "America/Santiago";

export function horaCLT(isoUtc: string): string {
  return new Intl.DateTimeFormat("es-CL", {
    timeZone: TZ,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(isoUtc));
}

export function horaCortaCLT(isoUtc: string): string {
  return new Intl.DateTimeFormat("es-CL", {
    timeZone: TZ,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(isoUtc));
}

const DIAS: Record<string, string> = {
  Mon: "LUN", Tue: "MAR", Wed: "MIÉ", Thu: "JUE", Fri: "VIE", Sat: "SÁB", Sun: "DOM",
};
const MESES: Record<string, string> = {
  Jan: "ENE", Feb: "FEB", Mar: "MAR", Apr: "ABR", May: "MAY", Jun: "JUN",
  Jul: "JUL", Aug: "AGO", Sep: "SEP", Oct: "OCT", Nov: "NOV", Dec: "DIC",
};

/**
 * "LUN 25 AGO 2026 · CLT" -- handoff §3.1. Se arma a partir de partes en
 * inglés (estables, sin puntuación de locale) para no depender de cómo
 * cada motor formatea abreviaturas en es-CL (varía: "lun.", "lun", "LUN").
 */
export function fechaLargaCLT(fecha: Date): string {
  const partes = new Intl.DateTimeFormat("en-US", {
    timeZone: TZ,
    weekday: "short",
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).formatToParts(fecha);
  const get = (tipo: string) => partes.find((p) => p.type === tipo)?.value ?? "";
  const diaSemana = DIAS[get("weekday")] ?? get("weekday").toUpperCase();
  const mes = MESES[get("month")] ?? get("month").toUpperCase();
  return `${diaSemana} ${get("day")} ${mes} ${get("year")} · CLT`;
}

/** "HACE 30 MIN" / "HACE 3 DÍAS" / "HACE 8 S" -- handoff, mayúsculas. */
export function haceTiempo(isoUtc: string, ahoraMs: number = Date.now()): string {
  const diffS = Math.max(0, Math.round((ahoraMs - new Date(isoUtc).getTime()) / 1000));
  if (diffS < 60) return `HACE ${diffS} S`;
  const diffMin = Math.round(diffS / 60);
  if (diffMin < 60) return `HACE ${diffMin} MIN`;
  const diffH = Math.round(diffMin / 60);
  if (diffH < 24) return `HACE ${diffH} H`;
  const diffD = Math.round(diffH / 24);
  return `HACE ${diffD} ${diffD === 1 ? "DÍA" : "DÍAS"}`;
}

/** "72 h 14 min" -- handoff §3.2, racha sin sismos sentibles. */
export function duracionHoraMin(ms: number): string {
  const totalMin = Math.max(0, Math.floor(ms / 60_000));
  const h = Math.floor(totalMin / 60);
  const min = totalMin % 60;
  return `${h} h ${String(min).padStart(2, "0")} min`;
}

/** "2:20" -- cuenta regresiva mm:ss para el pie del aviso emergente. */
export function cuentaRegresiva(segundosRestantes: number): string {
  const s = Math.max(0, Math.round(segundosRestantes));
  const min = Math.floor(s / 60);
  const seg = s % 60;
  return `${min}:${String(seg).padStart(2, "0")}`;
}

export function esHorarioNocturno(fecha: Date, inicioHora: number, finHora: number): boolean {
  const horaCL = Number(
    new Intl.DateTimeFormat("en-US", { timeZone: TZ, hour: "2-digit", hour12: false }).format(
      fecha,
    ),
  );
  if (inicioHora > finHora) {
    return horaCL >= inicioHora || horaCL < finHora;
  }
  return horaCL >= inicioHora && horaCL < finHora;
}

// ---------------------------------------------------------------------
// Formato numérico
// ---------------------------------------------------------------------

export function km(valor: number | null): string {
  if (valor == null) return "—";
  return `${Math.round(valor)} km`;
}

export function magnitud(valor: number | null): string {
  if (valor == null) return "M?";
  return valor.toFixed(1);
}

// ---------------------------------------------------------------------
// Agregados -- columna C / hero de columna B, sobre la lista ya cargada
// ---------------------------------------------------------------------

export interface Resumen48h {
  total: number;
  sobreMag4: number;
  magMax: number | null;
  sentidosAqui: number;
}

export function resumen48h(eventos: RawEvent[]): Resumen48h {
  const enChile48h = eventos.filter(enChile);
  const magnitudes = enChile48h.map((e) => e.magnitude).filter((m): m is number => m != null);
  return {
    total: enChile48h.length,
    sobreMag4: enChile48h.filter((e) => (e.magnitude ?? 0) >= 4).length,
    magMax: magnitudes.length ? Math.max(...magnitudes) : null,
    sentidosAqui: eventos.filter(esSentido).length,
  };
}

export function eventosMundiales(eventos: RawEvent[]): RawEvent[] {
  return eventos
    .filter(esMundial)
    .sort((a, b) => new Date(b.origin_time).getTime() - new Date(a.origin_time).getTime());
}

export function ultimoSentido(eventos: RawEvent[]): RawEvent | null {
  const sentidos = eventos
    .filter(esSentido)
    .sort((a, b) => new Date(b.origin_time).getTime() - new Date(a.origin_time).getTime());
  return sentidos[0] ?? null;
}

/** Severidad relativa dentro de la lista visible -- handoff §2 regla 3: sin color, solo peso. */
export function pesoSeveridad(event: RawEvent, maxMagnitudVisible: number): 1 | 2 | 3 | 4 {
  if (event.magnitude == null || maxMagnitudVisible <= 0) return 4;
  const proporcion = event.magnitude / maxMagnitudVisible;
  if (proporcion >= 0.85) return 1;
  if (proporcion >= 0.6) return 2;
  if (proporcion >= 0.35) return 3;
  return 4;
}
