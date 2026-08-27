/**
 * El navegador (tablet o cualquier PC en la LAN) habla solo con este mismo
 * origen -- Next.js reescribe /api/* hacia la API dentro de la red de
 * Docker (ver next.config.ts). Rutas relativas a propósito: no hay URL de
 * API que resolver desde el cliente, así que no puede apuntar a
 * "localhost" (el device del propio navegador) ni al hostname interno
 * "api" (solo resuelve dentro de Docker) por error de configuración.
 */
import type { RawConfig, RawEvent, RawEventDetail, RawHealth, RawNote, RawStroke } from "./types";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`GET ${path} -> ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function fetchEvents(sinceIso: string, limit = 500): Promise<RawEvent[]> {
  const params = new URLSearchParams({ since: sinceIso, limit: String(limit) });
  return getJson<RawEvent[]>(`/api/events?${params.toString()}`);
}

/** `significant` reusa el flag ya calculado por el backend (is_significant)
 * -- ver api/routers/events.py -- para no traer 90 días completos de
 * sismicidad chilena solo para quedarnos con los pocos sentidos en casa. */
export function fetchSignificantEvents(sinceIso: string, limit = 100): Promise<RawEvent[]> {
  const params = new URLSearchParams({ since: sinceIso, limit: String(limit), significant: "true" });
  return getJson<RawEvent[]>(`/api/events?${params.toString()}`);
}

export function fetchEventDetail(clusterKey: string): Promise<RawEventDetail> {
  return getJson<RawEventDetail>(`/api/events/${clusterKey}`);
}

export function fetchHealth(): Promise<RawHealth> {
  return getJson<RawHealth>("/api/health");
}

export function fetchConfig(): Promise<RawConfig> {
  return getJson<RawConfig>("/api/config");
}

/** Único dominio de la API con escritura directa (no pasa por el daemon):
 * las notas manuscritas no tienen relación con el pipeline sísmico -- ver
 * CLAUDE.md, "Arquitectura". */
export function fetchNotes(limit = 20): Promise<RawNote[]> {
  return getJson<RawNote[]>(`/api/notes?limit=${limit}`);
}

export async function createNote(strokes: RawStroke[]): Promise<RawNote> {
  const res = await fetch("/api/notes", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ strokes }),
  });
  if (!res.ok) throw new Error(`POST /api/notes -> ${res.status}`);
  return res.json() as Promise<RawNote>;
}

export async function deleteNote(id: number): Promise<void> {
  const res = await fetch(`/api/notes/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 404) throw new Error(`DELETE /api/notes/${id} -> ${res.status}`);
}
