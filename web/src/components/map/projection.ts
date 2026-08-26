import { geoMercator, geoPath, type GeoPath, type GeoPermissibleObjects } from "d3-geo";
import chileGeo from "@/data/chile.geo.json";

export const MAPA_ANCHO = 518;
export const MAPA_ALTO = 856;

let cache: { projection: ReturnType<typeof geoMercator>; path: GeoPath } | null = null;

/** Proyección Mercator ajustada al contorno de Chile (handoff §3.2). Se
 * memoiza: fitSize recorre toda la geometría, no hace falta repetirlo por
 * render. */
export function proyeccionNacional() {
  if (cache) return cache;
  const projection = geoMercator().fitSize(
    [MAPA_ANCHO, MAPA_ALTO],
    chileGeo as unknown as GeoPermissibleObjects,
  );
  const path = geoPath(projection);
  cache = { projection, path };
  return cache;
}

export function chilePath(): string {
  const { path } = proyeccionNacional();
  return path(chileGeo as unknown as GeoPermissibleObjects) ?? "";
}

export function proyectar(lat: number, lon: number): [number, number] | null {
  const { projection } = proyeccionNacional();
  return projection([lon, lat]);
}
