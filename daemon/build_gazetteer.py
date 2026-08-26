"""Builds `data/cl_gazetteer.tsv.gz`, the offline locality dataset used by
`geocoding.py` to resolve CSN's `RefGeografica` free-text references
("49 km al SE de Socaire").

Why an embedded dataset instead of a geocoding API: the daemon runs 24/7 on
a Raspberry Pi with three fragile network sources already (rule 4 in
CLAUDE.md, "degradacion con gracia"); a fourth network dependency purely
for geocoding would add another way for the pipeline to stall, for no
benefit -- Chilean locality names don't change often enough to need a live
service, and the whole point of CSN's `RefGeografica` is that it's built
from a fixed gazetteer on their end too. An embedded extract is also fully
offline-reproducible and doesn't leak query patterns (roughly: recent
earthquake locations) to a third party on every event.

Source: GeoNames' per-country extract for Chile (CL.zip), which is placed
in the public domain under CC BY 4.0 (https://www.geonames.org/, see
https://download.geonames.org/export/dump/). Filtered here to feature
classes/codes that plausibly appear in a Spanish-language "de <lugar>"
locality reference -- populated places, named localities/salt flats/ports,
capes/coves/harbors, and named terrain features (mountains, volcanoes,
points, passes, islands). Excludes administrative-only rows, facilities
(farms, hotels, mines, churches, etc.) and anything outside feature classes
P/L/H/T, which would otherwise add noise without ever being the kind of
name CSN cites.

This is a one-off maintenance script, not run by the daemon or the Docker
build. Re-run it only when refreshing the embedded dataset from a newer
GeoNames export.

Usage:
    curl -O https://download.geonames.org/export/dump/CL.zip
    unzip CL.zip CL.txt
    python build_gazetteer.py CL.txt data/cl_gazetteer.tsv.gz
"""

from __future__ import annotations

import argparse
import csv
import gzip
import sys

# GeoNames feature class/code whitelist -- see module docstring. Reference:
# https://www.geonames.org/export/codes.html
_WHITELIST = (
    {("P", code) for code in (
        "PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLC", "PPLF", "PPLL",
        "PPLQ", "PPLS", "PPLX", "PPLH",
    )}
    | {("L", code) for code in ("LCTY", "OAS", "SALT", "PRK")}
    | {("H", code) for code in ("BAY", "COVE", "GULF", "INLT", "LK", "STRT", "FJD", "HBR")}
    | {("T", code) for code in (
        "MT", "MTS", "PK", "PKS", "VLC", "PT", "PTS", "CAPE", "ISL", "ISLS",
        "ISLT", "PEN", "VAL", "VALS", "PASS", "HLL", "HLLS", "RDGE",
    )}
)

# Column layout of GeoNames' per-country dump (see readme.txt in CL.zip).
_GEONAMES_COLUMNS = (
    "geonameid", "name", "asciiname", "alternatenames", "latitude",
    "longitude", "feature_class", "feature_code", "country_code", "cc2",
    "admin1_code", "admin2_code", "admin3_code", "admin4_code",
    "population", "elevation", "dem", "timezone", "modification_date",
)

_OUTPUT_HEADER = ("name", "asciiname", "lat", "lon", "fclass", "fcode", "admin1", "population")


def build(src_path: str, dst_path: str) -> None:
    kept = []
    with open(src_path, encoding="utf-8") as src:
        for line in src:
            fields = dict(zip(_GEONAMES_COLUMNS, line.rstrip("\n").split("\t")))
            key = (fields["feature_class"], fields["feature_code"])
            if key not in _WHITELIST:
                continue
            kept.append((
                fields["name"],
                fields["asciiname"],
                fields["latitude"],
                fields["longitude"],
                fields["feature_class"],
                fields["feature_code"],
                fields["admin1_code"],
                fields["population"],
            ))

    with gzip.open(dst_path, "wt", encoding="utf-8", newline="") as dst:
        writer = csv.writer(dst, delimiter="\t")
        writer.writerow(_OUTPUT_HEADER)
        writer.writerows(kept)

    print(f"wrote {len(kept)} localities to {dst_path}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src", help="path to GeoNames' CL.txt")
    parser.add_argument("dst", help="output path, e.g. data/cl_gazetteer.tsv.gz")
    args = parser.parse_args()
    build(args.src, args.dst)
