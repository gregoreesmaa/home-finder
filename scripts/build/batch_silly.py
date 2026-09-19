"""Silly-bundle pins builder (issue #774, option A): export -> sidecar.

Reads an ``osmium export`` GeoJSON slice of the held Estonia extract
(nodes as Points, ways as polygons/lines — never the live API) and
writes the servable pins sidecar ``silly/silly-points.json``:
``{"vintage", "source", "counts", "points"}`` with points carrying
lat/lon/slice only (sport #607 precedent). Real mapped objects
replace the 2-3 demo samples per layer.

Geometry rule: Points serve directly; every other geometry serves
its bbox-centre centroid (one marker per mapped object — a swim
spot tagged both leisure=swimming_area and sport=swimming is ONE
point, never two). Relations are outside the export (documented in
docs/p4_silly.md); untagged export artefacts never become points.

Hermetic by construction: pure classify/extract/build functions
pinned by test_batch_silly.py against inline GeoJSON fixtures. The
real run is a one-off local build (see below), never CI, never the
pole.

Real build (dev machine, held extract + osmium):
  osmium tags-filter /private/tmp/estonia-260914.osm.pbf \\
      amenity=place_of_worship amenity=marketplace ... (18 vocabs) \\
      -o /tmp/hf-silly/all.osm.pbf --overwrite
  osmium export /tmp/hf-silly/all.osm.pbf -f geojson \\
      -o /tmp/hf-silly/all.geojson
  python3 scripts/build/batch_silly.py --extract /tmp/hf-silly/all.geojson \\
      --out ~/hf-data/2026-09-12/silly/silly-points.json --vintage 2026-09-14
"""

import argparse
import json
import os
import sys
from typing import Dict, List, Optional

#: Extract vintage (held file estonia-260914.osm.pbf).
VINTAGE_DEFAULT = "2026-09-14"

#: Silly layer -> OSM (key, value) vocabularies (mirror of
#: SILLY_TAGS in apps/web/lib/layers_p4_silly.ts).
LAYER_TAGS: Dict[str, List[tuple]] = {
    "kirikukellad": [("amenity", "place_of_worship")],
    "kajakad": [("landuse", "harbour"), ("amenity", "marketplace"),
                ("landuse", "landfill")],
    "manguvaljakud": [("leisure", "playground")],
    "koertepargid": [("leisure", "dog_park")],
    "saunad": [("leisure", "sauna")],
    "talisuplus": [("leisure", "swimming_area"), ("sport", "swimming")],
    "tanavasport": [("leisure", "fitness_station"),
                    ("sport", "skateboard"), ("sport", "disc_golf")],
    "vesi": [("amenity", "fountain"), ("amenity", "drinking_water")],
    "wc": [("amenity", "toilets")],
    "aed": [("emergency", "defibrillator")],
    "raamatukapid": [("amenity", "public_bookcase")],
    "kalmistu": [("landuse", "cemetery")],
}

_LOOKUP = {(k, v): layer
           for layer, pairs in LAYER_TAGS.items()
           for (k, v) in pairs}


def classify_tags(tags: Dict[str, str]) -> Optional[str]:
    """OSM tag dict -> silly layer id, or None when unmapped (pure)."""
    for (k, v), layer in _LOOKUP.items():
        if tags.get(k) == v:
            return layer
    return None


def _positions(geom: dict, out: list) -> None:
    coords = geom.get("coordinates")
    if not isinstance(coords, list):
        return
    if coords and isinstance(coords[0], (int, float)):
        out.append(coords)
        return
    for part in coords:
        if isinstance(part, list):
            _positions({"coordinates": part}, out)


def centroid_of(geom: dict) -> Optional[tuple]:
    """Geometry -> (lat, lon): points direct, others bbox-centre (pure).

    None for missing/degenerate geometries (never a faked zero).
    """
    if not isinstance(geom, dict):
        return None
    if geom.get("type") == "Point":
        coords = geom.get("coordinates")
        if (isinstance(coords, list) and len(coords) >= 2
                and isinstance(coords[0], (int, float))
                and isinstance(coords[1], (int, float))):
            return (coords[1], coords[0])
        return None
    pts: list = []
    _positions(geom, pts)
    if not pts:
        return None
    lons = [p[0] for p in pts]
    lats = [p[1] for p in pts]
    return ((min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2)


def extract_points_geojson(doc: dict) -> List[dict]:
    """Export doc -> classified points (pure).

    One point per mapped object (dual-tagged objects classify once);
    unmapped or geometry-less features are skipped, never zero-filled.
    """
    points: List[dict] = []
    if not isinstance(doc, dict):
        return points
    for feat in doc.get("features", []):
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties")
        tags = props if isinstance(props, dict) else {}
        layer = classify_tags({k: v for k, v in tags.items()
                               if isinstance(v, str)})
        if layer is None:
            continue
        centre = centroid_of(feat.get("geometry", {}))
        if centre is None:
            continue
        lat, lon = centre
        if 57.0 <= lat <= 60.5 and 21.5 <= lon <= 28.5:
            points.append({"lat": lat, "lon": lon, "slice": layer})
    return points


def build_sidecar(points: List[dict], vintage: str = VINTAGE_DEFAULT,
                  source: str = "estonia-260914 export (nodes + way centroids)"
                  ) -> Dict:
    """Classified points -> servable sidecar doc (pure).

    Points carry lat/lon/slice only; per-layer tallies ride counts.
    """
    by_layer: Dict[str, int] = {}
    for p in points:
        by_layer[p["slice"]] = by_layer.get(p["slice"], 0) + 1
    return {"vintage": vintage,
            "source": source,
            "counts": {"total": len(points), "by_layer": by_layer},
            "points": [{"lat": p["lat"], "lon": p["lon"],
                        "slice": p["slice"]} for p in points]}


def main(argv: Optional[List[str]] = None) -> int:
    """CLI: --extract export GeoJSON --out sidecar.json. Exit code."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--extract", required=True,
                    help="osmium export GeoJSON (nodes + ways)")
    ap.add_argument("--out", required=True, help="sidecar JSON path")
    ap.add_argument("--vintage", default=VINTAGE_DEFAULT)
    args = ap.parse_args(argv)
    try:
        with open(args.extract, encoding="utf-8") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        print("error: extracti pole (%s) - midagi ei kirjutatud."
              % args.extract, file=sys.stderr)
        return 1
    except ValueError as exc:
        print("error: katkine GeoJSON (%s) - midagi ei kirjutatud."
              % exc, file=sys.stderr)
        return 1
    points = extract_points_geojson(doc)
    out = build_sidecar(points, vintage=args.vintage)
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    tmp = args.out + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    os.replace(tmp, args.out)
    print("wrote %d points (%d layers) -> %s"
          % (out["counts"]["total"], len(out["counts"]["by_layer"]),
             args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
