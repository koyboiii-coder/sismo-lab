// Extracts Chile's national outline from world-atlas's countries-50m
// TopoJSON (Natural Earth data, public domain) and writes it as plain
// GeoJSON to src/data/chile.geo.json.
//
// Run once at dev time, not at build/runtime: shipping the whole
// countries-50m.json (~750 KB) to a tablet that only ever renders Chile
// would be wasted bandwidth/parse time for no benefit (CLAUDE.md rule 5 --
// the Pi/tablet have limited resources). This keeps the topojson->geojson
// step (and the topojson-client/world-atlas dependencies it needs) out of
// the runtime bundle entirely, same as daemon/build_gazetteer.py generates
// daemon/data/cl_gazetteer.tsv.gz once and commits the result.
//
// Re-run with `node scripts/build-chile-map-data.mjs` only if a different
// resolution/source is needed.

import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import * as topojsonClient from "topojson-client";
import worldTopo from "world-atlas/countries-50m.json" with { type: "json" };

const CHILE_NUMERIC_ID = "152"; // ISO 3166-1 numeric, per world-atlas's `id` field

const chileGeometry = worldTopo.objects.countries.geometries.find(
  (g) => g.id === CHILE_NUMERIC_ID,
);

if (!chileGeometry) {
  throw new Error("Chile (id 152) not found in world-atlas countries-50m.json");
}

const chileTopology = {
  type: "Topology",
  arcs: worldTopo.arcs,
  transform: worldTopo.transform,
  objects: { chile: chileGeometry },
};

const feature = topojsonClient.feature(chileTopology, chileTopology.objects.chile);

const outPath = fileURLToPath(new URL("../src/data/chile.geo.json", import.meta.url));
writeFileSync(outPath, JSON.stringify(feature));

console.log(`wrote ${outPath}`);
