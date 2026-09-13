"""EELIS nature-polygon sidecar builder (issue #488): WFS GeoJSON -> map polygons.

Stdlib only. Offline, snapshot-only (NO network): the EELIS WFS pull
lives in services/scoring/dims_p4_eelis.py (fetch_eelis_snapshot,
polite annual BBOX-filtered GETs); this builder converts already-cached
WFS GetFeature GeoJSON files (one per polygon table) into the map
sidecar ``<snap>/eelis/eelis-areas.json`` consumed by
/api/layers/eelis/areas. Pure logic at module top so unit tests stay
hermetic; the sidecar write runs only via the documented rebuild
command.

SCOPE (three layers, honest): this builder serves ONLY the nature
polygons — "kaitse" (kr_kaitseala, P4-015 leg), "niit" (niidud, P4-024
proxy leg), "raie" (kaadamisalad, P4-030 flag leg) — as per-parcel
zone-MEMBERSHIP choropleths (inside a named polygon vs
outside/unknown). It builds NO raster and NO score field — the map
paints basemap + polygon fills only (polygons only, never a gradient,
per docs/p4_eelis.md). The per-listing scorer dims live in
services/scoring/dims_p4_eelis.py; the tiny contains() helper below
mirrors its nearest-centroid gate with a true containment check so the
sidecar shape is join-proven on fixtures, but production joins run in
the scorer, never here.

REFUSED (documented): the flood table (kr_yleujutusohuga_ala) is
skipped — owned by the #487 floodzone overlay, one layer per source.
The emitter register (kr_puhasti + kr_jaakreostus) is skipped — point
locations, not zone polygons (the P4-053 sector dim stays
scorer-side). Point features inside the three polygon collections are
SKIPPED (a centroid is not a polygon; the centroid join stays
scorer-side).

HONESTY (load-bearing): malformed features are SKIPPED (never faked);
a missing input file means that table is not provided (skipped, counted
in stats); a PROVIDED-but-unparseable file yields NO sidecar at all
(unknown, never a partial zone list presented as complete). Rings keep
WFS EPSG:4326 GeoJSON [lon, lat] order into the sidecar (no axis flip —
pinned by test); ALL exterior rings are kept (MultiPolygon members are
real area, dropping them would fake absence).

Rebuild: python3 scripts/build/batch_eelis_poly.py \\
    --kaitse ~/hf-cache/eelis-kaitse.geojson \\
    --niidud ~/hf-cache/eelis-niidud.geojson \\
    --raie ~/hf-cache/eelis-kaadamisalad.geojson \\
    --snap ~/hf-data/2026-09-12
(any --<table> may be omitted when that pull is not cached)
"""

import argparse
import json
import math
import os
import sys
from typing import Dict, List, Optional, Tuple

#: Sidecar filename inside the snapshot dir.
SIDECAR_PATH = os.path.join("eelis", "eelis-areas.json")

#: (cli flag, sidecar kind, WFS layer, id field, lisa field) pull plan.
TABLES = (
    ("kaitse", "kaitse", "eelis:kr_kaitseala", "id", "tyyp"),
    ("niidud", "niit", "eelis:niidud", "id", None),
    ("raie", "raie", "eelis:kaadamisalad", "id", "aasta"),
)


def _finite_lonlat(pt) -> Optional[Tuple[float, float]]:
    """[lon, lat] pair -> (lat, lon) when finite, else None."""
    if not isinstance(pt, (list, tuple)) or len(pt) < 2:
        return None
    try:
        lon, lat = float(pt[0]), float(pt[1])
    except (TypeError, ValueError):
        return None
    if isinstance(pt[0], bool) or not (
            math.isfinite(lat) and math.isfinite(lon)):
        return None
    return (lat, lon)


def _exterior_rings(geom: dict) -> List[List[Tuple[float, float]]]:
    """GeoJSON Polygon/MultiPolygon -> exterior rings as (lat, lon) lists.

    Interior holes are dropped (documented): the scorer gates on the
    labelled centroid and the map paints membership fills — holes are
    sub-parcel detail neither consumer resolves. Point geometries yield
    [] (skipped by the caller, never centroid-faked into polygons).
    """
    if not isinstance(geom, dict):
        return []
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not isinstance(coords, list):
        return []
    polys: List[list] = []
    if gtype == "Polygon":
        polys = [coords]
    elif gtype == "MultiPolygon":
        polys = [p for p in coords if isinstance(p, list)]
    else:
        return []
    rings = []
    for poly in polys:
        if not poly or not isinstance(poly[0], list):
            continue
        ring = [_finite_lonlat(pt) for pt in poly[0]]
        ring = [pt for pt in ring if pt is not None]
        if len(ring) >= 4:
            rings.append(ring)
    return rings


def parse_collection(text: str, kiht: str, id_field: str = "id",
                     lisa_field: Optional[str] = None) -> Optional[List[dict]]:
    """WFS GeoJSON text -> zone records (or None when unparseable).

    Returns [{kiht, zone_id, nimi, lisa, polys}] with polys as lists of
    [(lat, lon)] exterior rings; malformed features skipped. None means
    unknown (never an empty zone list).
    """
    try:
        collection = json.loads(text)
    except ValueError:
        return None
    if not isinstance(collection, dict):
        return None
    feats = collection.get("features")
    if not isinstance(feats, list):
        return None
    zones = []
    for feat in feats:
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties")
        geom = feat.get("geometry")
        if not isinstance(props, dict):
            continue
        rings = _exterior_rings(geom) if isinstance(geom, dict) else []
        if not rings:
            continue
        ident = props.get(id_field)
        if ident is None:
            ident = props.get("sys_id", "tundmatu")
        nimi = props.get("nimi") or props.get("nimetus") or "tundmatu"
        lisa = ""
        if lisa_field and props.get(lisa_field) is not None:
            lisa = str(props.get(lisa_field))
        zones.append({
            "kiht": kiht,
            "zone_id": str(ident),
            "nimi": str(nimi),
            "lisa": lisa,
            "polys": rings,
        })
    return zones


def bbox_lonlat(polys: List[List[Tuple[float, float]]]) -> List[float]:
    """Prefilter box [minlon, minlat, maxlon, maxlat] over (lat, lon) rings."""
    los = [lo for ring in polys for _, lo in ring]
    las = [la for ring in polys for la, _ in ring]
    return [min(los), min(las), max(los), max(las)]


def to_sidecar(zones: Optional[List[dict]]) -> List[dict]:
    """Zone records -> sidecar rows (GeoJSON [lon, lat] rings + box).

    None (unknown snapshot) -> [] stays OUT of the writer: build_sidecar
    refuses to write it (unknown is never an empty zone list). Malformed
    rows are skipped, never faked.
    """
    rows = []
    for row in zones or []:
        if not isinstance(row, dict):
            continue
        if row.get("kiht") not in ("kaitse", "niit", "raie"):
            continue
        polys = row.get("polys")
        if (not isinstance(polys, list) or not polys
                or any(not (isinstance(ring, list) and len(ring) >= 4)
                       for ring in polys)):
            continue
        try:
            rings = [[(float(la), float(lo)) for la, lo in ring]
                     for ring in polys]
        except (TypeError, ValueError):
            continue
        rows.append({
            "kiht": row.get("kiht"),
            "zone_id": str(row.get("zone_id") or "tundmatu"),
            "nimi": str(row.get("nimi") or "tundmatu"),
            "lisa": str(row.get("lisa") or ""),
            "b": bbox_lonlat(rings),
            "r": [[[lo, la] for la, lo in ring] for ring in rings],
        })
    return rows


def point_in_ring(lat: float, lon: float,
                  ring: List[Tuple[float, float]]) -> bool:
    """Ray casting over (lon=x, lat=y). Mirrors the scorer's ring math."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        yi, xi = ring[i][0], ring[i][1]
        yj, xj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat):
            xhit = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < xhit:
                inside = not inside
        j = i
    return inside


def contains(zones: Optional[List[dict]], lat: float,
             lon: float) -> Optional[dict]:
    """First zone with any polygon holding (lat, lon); None = outside/unknown.

    Fixture-level proof that the sidecar shape joins per-parcel (inside
    scores, outside stays NULL); production joins run in the scorer.
    """
    for z in zones or []:
        if not isinstance(z, dict):
            continue
        polys = z.get("polys")
        if not isinstance(polys, list):
            continue
        for ring in polys:
            if not isinstance(ring, list) or len(ring) < 4:
                continue
            try:
                clean = [(float(a), float(b)) for a, b in ring]
            except (TypeError, ValueError):
                continue
            try:
                if point_in_ring(float(lat), float(lon), clean):
                    return z
            except (TypeError, ValueError):
                continue
    return None


def build_sidecar(inputs: Dict[str, Optional[str]],
                  snap_dir: str) -> Dict[str, object]:
    """Cached WFS GeoJSON files -> <snap>/eelis/eelis-areas.json.

    inputs maps cli flag ("kaitse"/"niidud"/"raie") to a GeoJSON path or
    None (table not provided — skipped, counted). A provided-but-missing
    or unparseable file: writes NOTHING and reports ok=False (unknown,
    never a partial zone list). No network, ever.
    """
    zones: List[dict] = []
    tables: Dict[str, int] = {}
    skipped: List[str] = []
    for flag, kiht, _layer, id_field, lisa_field in TABLES:
        path = inputs.get(flag)
        if not path:
            skipped.append(flag)
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            return {"ok": False, "error": "unreadable %s: %s" % (flag, exc)}
        parsed = parse_collection(text, kiht, id_field, lisa_field)
        if parsed is None:
            return {"ok": False, "error": "unparseable %s" % flag}
        zones.extend(parsed)
        tables[kiht] = len(parsed)
    rows = to_sidecar(zones)
    dest_dir = os.path.join(snap_dir, "eelis")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(snap_dir, SIDECAR_PATH)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False)
    return {"ok": True, "dest": dest, "zones": len(rows),
            "skipped": len(zones) - len(rows), "tables": tables,
            "skipped_tables": skipped}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build EELIS nature sidecar.")
    ap.add_argument("--kaitse", default=None,
                    help="Cached kr_kaitseala GetFeature GeoJSON")
    ap.add_argument("--niidud", default=None,
                    help="Cached niidud GetFeature GeoJSON")
    ap.add_argument("--raie", default=None,
                    help="Cached kaadamisalad GetFeature GeoJSON")
    ap.add_argument("--snap", required=True,
                    help="Snapshot dir to write to")
    args = ap.parse_args(argv)
    stats = build_sidecar({"kaitse": args.kaitse, "niidud": args.niidud,
                           "raie": args.raie}, args.snap)
    print(json.dumps(stats, ensure_ascii=False))
    return 0 if stats.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
