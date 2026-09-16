"""Drainage-network + outflow sidecar builder (issue #616): cached WFS GeoJSON -> map shapes.

Stdlib only. Offline, snapshot-only (NO network): the maaparandus GIS
WFS pull is a polite one-off harvest (custom UA, paced >= 3 s, 429
stops the run — see docs/p4_maaparandus.md §6); this builder converts
the already-cached GetFeature GeoJSON files (pta:msr_vork regulating-
network areas + pta:kehtetu_maaparandussysteem invalid systems +
pta:msr_eesvool outflows, Harju window, EPSG:4326) into the map sidecar
``<snap>/maaparandus/maaparandus-areas.json`` consumed by
/api/layers/maaparandus/areas. Pure logic at module top so unit tests stay
hermetic; the sidecar write runs only via the documented rebuild
command.

SCOPE: regulating-network POLYGONS (msr_vork, class "network") +
invalid-system POLYGONS (kehtetu, class "invalid") + outflow
LINESTRINGS (msr_eesvool, class "outflow" — centerlines painted thin,
the <= 100 m near-band stays scorer-side). CC BY 4.0 with
Kliimaministeerium attribution. Duty (kraavihooldus) is REFUSED
everywhere (the register carries no duty attributes — scorer parity:
duty always NULLs with an MSR-check reason).

HONESTY (load-bearing): malformed rows are SKIPPED (never faked); a
missing input file writes NOTHING and reports ok=False (unknown, never
a partial zone list presented as complete). Rings keep the service's
EPSG:4326 GeoJSON [lon, lat] order into the sidecar (no axis flip —
pinned by test); ALL exterior rings are kept (MultiPolygon members are
real area, dropping them would fake absence); interior holes are
dropped (sub-parcel detail neither consumer resolves — documented).
Outflow lines paint as what they are (centerlines, width 2, no fill,
no buffer — the band is scorer-side, the legend says so).

Rebuild: python3 scripts/build/batch_maaparandus.py \\
    --vork /tmp/hf-616-cache/vork.json \\
    --kehtetu /tmp/hf-616-cache/kehtetu.json \\
    --eesvool /tmp/hf-616-cache/eesvool.json \\
    --snap ~/hf-data/2026-09-12
(any table may be omitted when that pull is not cached)
"""

import argparse
import json
import math
import os
import sys
from typing import Dict, List, Optional

#: Sidecar filename inside the snapshot dir.
SIDECAR_PATH = os.path.join("maaparandus", "maaparandus-areas.json")

#: Publisher attribution (CC BY 4.0 — stamped in stats, not rows).
ATTRIBUTION = ("Allikas: Kliimaministeerium / Maa- ja Ruumiamet, "
               "maaparanduse GIS (CC BY 4.0)")

#: Map classes (scorer parity: network wetness / invalid risk / outflow dampness).
CLASSES = ("network", "invalid", "outflow")


def _finite_lonlat(pt) -> Optional[tuple]:
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


def _exterior_rings(geom: dict) -> List[List[tuple]]:
    """GeoJSON Polygon/MultiPolygon -> exterior rings as (lat, lon) lists.

    Interior holes are dropped (documented): the scorer gates on
    containment/adjacency and the map paints membership fills — holes
    are sub-parcel detail neither consumer resolves.
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


def _lines(geom: dict) -> List[List[tuple]]:
    """GeoJSON LineString/MultiLineString -> lines as (lat, lon) lists."""
    if not isinstance(geom, dict):
        return []
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not isinstance(coords, list):
        return []
    parts: List[list] = []
    if gtype == "LineString":
        parts = [coords]
    elif gtype == "MultiLineString":
        parts = [p for p in coords if isinstance(p, list)]
    else:
        return []
    lines = []
    for part in parts:
        line = [_finite_lonlat(pt) for pt in part]
        line = [pt for pt in line if pt is not None]
        if len(line) >= 2:
            lines.append(line)
    return lines


def parse_polygon_collection(text: str, cls: str, id_key: str,
                             name_key: str) -> Optional[List[dict]]:
    """Polygon GeoJSON text -> zone records (or None when unparseable).

    Returns [{zone_id, nimi, cls, ms_kood, ms_url, polys}]; malformed
    features skipped. None means unknown (never an empty zone list).
    """
    if cls not in ("network", "invalid"):
        raise ValueError("polygon class must be network or invalid")
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
        code = str(props.get(id_key) or "").strip()
        zones.append({
            "zone_id": code or "tundmatu",
            "nimi": str(props.get(name_key) or ""),
            "cls": cls,
            "ms_kood": code,
            "ms_url": str(props.get("ms_url") or ""),
            "polys": rings,
        })
    return zones


def parse_outflow_collection(text: str) -> Optional[List[dict]]:
    """Outflow-line GeoJSON text -> line records (or None when unparseable).

    Returns [{zone_id, nimi, cls, ms_kood, ms_url, lines}]; malformed
    features skipped. None means unknown (never an empty zone list).
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
        lines = _lines(geom) if isinstance(geom, dict) else []
        if not lines:
            continue
        code = str(props.get("ms_kood") or "").strip()
        zones.append({
            "zone_id": str(props.get("ev_id") or code or "tundmatu"),
            "nimi": str(props.get("vnimi") or props.get("ehitise_nimi") or ""),
            "cls": "outflow",
            "ms_kood": code,
            "ms_url": str(props.get("ms_url") or ""),
            "lines": lines,
        })
    return zones


def bbox_lonlat(shapes: List[List[tuple]]) -> List[float]:
    """Prefilter box [minlon, minlat, maxlon, maxlat] over (lat, lon) shapes."""
    los = [lo for shape in shapes for _, lo in shape]
    las = [la for shape in shapes for la, _ in shape]
    return [min(los), min(las), max(los), max(las)]


def to_sidecar(zones: Optional[List[dict]]) -> List[dict]:
    """Zone records -> sidecar rows (GeoJSON [lon, lat] shapes + box).

    Polygon rows carry r (rings); outflow rows carry l (linestrings) —
    the painter draws fills for r and thin centerlines for l (never a
    buffer). None (unknown snapshot) -> [] stays OUT of the writer:
    build_sidecar refuses to write it (unknown is never an empty zone
    list). Malformed rows are skipped, never faked.
    """
    rows = []
    for row in zones or []:
        if not isinstance(row, dict):
            continue
        if row.get("cls") not in CLASSES:
            continue
        base = {
            "zone_id": str(row.get("zone_id") or "tundmatu"),
            "nimi": str(row.get("nimi") or ""),
            "cls": row.get("cls"),
            "ms_kood": str(row.get("ms_kood") or ""),
            "ms_url": str(row.get("ms_url") or ""),
        }
        if row.get("cls") == "outflow":
            lines = row.get("lines")
            if (not isinstance(lines, list) or not lines
                    or any(not (isinstance(ln, list) and len(ln) >= 2)
                           for ln in lines)):
                continue
            try:
                clean = [[(float(la), float(lo)) for la, lo in ln]
                         for ln in lines]
            except (TypeError, ValueError):
                continue
            base["l"] = [[[lo, la] for la, lo in ln] for ln in clean]
            base["b"] = bbox_lonlat(clean)
        else:
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
            base["r"] = [[[lo, la] for la, lo in ring] for ring in rings]
            base["b"] = bbox_lonlat(rings)
        rows.append(base)
    return rows


def build_sidecar(inputs: Dict[str, Optional[str]],
                  snap_dir: str) -> Dict[str, object]:
    """Cached WFS GeoJSON files -> <snap>/maaparandus/maaparandus-areas.json.

    inputs maps table ("vork"/"kehtetu"/"eesvool") to a GeoJSON path or
    None (table not provided — skipped, counted). A provided-but-missing
    or unparseable file: writes NOTHING and reports ok=False (unknown,
    never a partial zone list). No network, ever.
    """
    zones: List[dict] = []
    tables: Dict[str, int] = {}
    skipped_tables: List[str] = []
    specs = (("vork", "network", "ms_kood", "ehitise_nimi"),
             ("kehtetu", "invalid", "kood", "nimi"))
    for flag, cls, id_key, name_key in specs:
        path = inputs.get(flag)
        if not path:
            skipped_tables.append(flag)
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            return {"ok": False, "error": "unreadable %s: %s" % (flag, exc)}
        parsed = parse_polygon_collection(text, cls, id_key, name_key)
        if parsed is None:
            return {"ok": False, "error": "unparseable %s" % flag}
        zones.extend(parsed)
        tables[flag] = len(parsed)
    eesvool_path = inputs.get("eesvool")
    if not eesvool_path:
        skipped_tables.append("eesvool")
    else:
        try:
            with open(eesvool_path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            return {"ok": False, "error": "unreadable eesvool: %s" % (exc,)}
        parsed = parse_outflow_collection(text)
        if parsed is None:
            return {"ok": False, "error": "unparseable eesvool"}
        zones.extend(parsed)
        tables["eesvool"] = len(parsed)
    rows = to_sidecar(zones)
    dest_dir = os.path.join(snap_dir, "maaparandus")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(snap_dir, SIDECAR_PATH)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False)
    by_cls: Dict[str, int] = {}
    for row in rows:
        by_cls[str(row["cls"])] = by_cls.get(str(row["cls"]), 0) + 1
    return {"ok": True, "dest": dest, "zones": len(rows),
            "skipped": len(zones) - len(rows), "tables": tables,
            "by_cls": by_cls, "skipped_tables": skipped_tables,
            "attribution": ATTRIBUTION}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build drainage sidecar.")
    ap.add_argument("--vork", default=None,
                    help="Cached pta:msr_vork GetFeature GeoJSON")
    ap.add_argument("--kehtetu", default=None,
                    help="Cached pta:kehtetu_maaparandussysteem GeoJSON")
    ap.add_argument("--eesvool", default=None,
                    help="Cached pta:msr_eesvool GetFeature GeoJSON")
    ap.add_argument("--snap", required=True,
                    help="Snapshot dir to write to")
    args = ap.parse_args(argv)
    stats = build_sidecar({"vork": args.vork, "kehtetu": args.kehtetu,
                           "eesvool": args.eesvool}, args.snap)
    print(json.dumps(stats, ensure_ascii=False))
    return 0 if stats.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
