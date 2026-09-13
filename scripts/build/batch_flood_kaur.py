"""KAUR flood-zone sidecar builder (issue #487): GML snapshot -> map polygons.

Stdlib only. Offline, snapshot-only (NO network): the KAUR/EELIS WFS pull
lives in services/scoring/dims_overturn_flood.py (fetch_flood_snapshot,
polite annual BBOX-filtered GET); this builder converts an already-cached
`flood-snapshot.gml` into the map sidecar `<snap>/kaur/flood-areas.json`
consumed by /api/layers/floodzone/areas. Pure logic at module top so unit
tests stay hermetic; the sidecar write runs only via the documented
rebuild command.

SCOPE (one layer, honest): this builder serves ONLY "floodzone" (p112
per-parcel zone-MEMBERSHIP choropleth: inside a named KAUR polygon vs
outside/unknown). It builds NO raster and NO score field — the map paints
basemap + polygon fills only (polygons only, never a gradient, per
docs/overturn_flood.md). The per-listing scorer dim lives in
services/scoring/dims_overturn_flood.py (dim_floodzone_p112); the tiny
contains() helper below mirrors its _joined_zone ring math so the sidecar
shape is join-proven on fixtures, but production joins run in the scorer,
never here.

HONESTY (load-bearing): malformed GML rows are SKIPPED (never faked);
a missing/unparseable snapshot yields NO sidecar rows for that file
(unknown, never an empty zone list presented as "no flood zones" — the
route serves honestly-empty and the legend says outside = teadmata).
Rings flip from WFS 2.0 (lat, lon) axis order to GeoJSON [lon, lat] on
write (pinned by test); exterior rings only (object-register polygons —
scorer parity: the join uses the same ring).

Rebuild: python3 scripts/build/batch_flood_kaur.py \\
    --gml ~/hf-cache/flood-snapshot.gml --snap ~/hf-data/2026-09-12
"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

NS = {
    "eelis": "http://kemit.ee/eelis/avaandmed",
    "gml": "http://www.opengis.net/gml/3.2",
}

#: Feature element local name on the KAUR WFS (see docs/overturn_flood.md).
FLOOD_MEMBER = "kr_yleujutusohuga_ala"

#: Sidecar filename inside the snapshot dir.
SIDECAR_PATH = os.path.join("kaur", "flood-areas.json")


def parse_ring_latlon(pos_text: str) -> Optional[List[Tuple[float, float]]]:
    """posList (WFS 2.0 EPSG:4326 axis order: lat lon) -> ring or None.

    Mirrors services/scoring/dims_overturn_flood._parse_ring (same
    validity bar: >= 4 pairs, finite plausible coords); malformed input
    is None, never a faked ring.
    """
    try:
        nums = [float(t) for t in pos_text.split()]
    except ValueError:
        return None
    if len(nums) < 8 or len(nums) % 2:
        return None
    ring = [(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)]
    if any(not (-90.0 <= la <= 90.0 and -180.0 <= lo <= 180.0)
           for la, lo in ring):
        return None
    return ring


def parse_gml_text(text: str) -> Optional[List[dict]]:
    """GML snapshot text -> zone records (or None when unparseable).

    Returns [{zone_id, nimi, veekogu, tyyp, poly}] with poly as
    [(lat, lon)] exterior rings; malformed rows skipped. None means
    unknown (never an empty zone list).
    """
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    zones = []
    for feat in root.findall("eelis:" + FLOOD_MEMBER, NS):
        def _text(tag: str) -> Optional[str]:
            el = feat.find("eelis:" + tag, NS)
            if el is None or el.text is None:
                return None
            s = el.text.strip()
            return s if s else None
        pos = feat.find("eelis:shape/gml:Polygon/gml:exterior/"
                        "gml:LinearRing/gml:posList", NS)
        if pos is None or pos.text is None:
            continue
        ring = parse_ring_latlon(pos.text)
        if ring is None:
            continue
        sys_id = _text("sys_id")
        kr_kood = _text("kr_kood")
        veekogu = _text("vveekogu") or _text("sveekogu")
        zones.append({
            "zone_id": kr_kood or (("sys:%s" % sys_id) if sys_id else None)
            or "tundmatu",
            "nimi": _text("nimi") or "tundmatu",
            "veekogu": veekogu or "tundmatu",
            "tyyp": _text("tyyp") or "tundmatu",
            "poly": ring,
        })
    return zones


def bbox_lonlat(poly: List[Tuple[float, float]]) -> List[float]:
    """Prefilter box [minlon, minlat, maxlon, maxlat] over a (lat, lon) ring."""
    los = [lo for _, lo in poly]
    las = [la for la, _ in poly]
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
        poly = row.get("poly")
        if (not isinstance(poly, list) or len(poly) < 4
                or any(not (isinstance(pt, (list, tuple)) and len(pt) == 2)
                       for pt in poly)):
            continue
        try:
            ring = [(float(la), float(lo)) for la, lo in poly]
        except (TypeError, ValueError):
            continue
        rows.append({
            "zone_id": str(row.get("zone_id") or "tundmatu"),
            "nimi": str(row.get("nimi") or "tundmatu"),
            "veekogu": str(row.get("veekogu") or "tundmatu"),
            "tyyp": str(row.get("tyyp") or "tundmatu"),
            "b": bbox_lonlat(ring),
            "r": [[[lo, la] for la, lo in ring]],
        })
    return rows


def point_in_ring(lat: float, lon: float,
                  ring: List[Tuple[float, float]]) -> bool:
    """Ray casting over (lon=x, lat=y). Mirrors the scorer's _point_in_ring."""
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
    """First zone whose polygon holds (lat, lon); None = outside/unknown.

    Fixture-level proof that the sidecar shape joins per-parcel (inside
    scores, outside stays NULL); production joins run in the scorer.
    """
    for z in zones or []:
        if not isinstance(z, dict):
            continue
        poly = z.get("poly")
        if not isinstance(poly, list) or len(poly) < 4:
            continue
        try:
            if point_in_ring(float(lat), float(lon),
                             [(float(a), float(b)) for a, b in poly]):
                return z
        except (TypeError, ValueError):
            continue
    return None


def build_sidecar(gml_path: str, snap_dir: str) -> Dict[str, object]:
    """Cached GML -> <snap>/kaur/flood-areas.json. Returns a stats dict.

    Missing/unparseable GML: writes NOTHING and reports ok=False
    (unknown, never an empty zone list). No network, ever.
    """
    try:
        with open(gml_path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        return {"ok": False, "error": "unreadable gml: %s" % exc}
    zones = parse_gml_text(text)
    if zones is None:
        return {"ok": False, "error": "unparseable gml"}
    rows = to_sidecar(zones)
    dest_dir = os.path.join(snap_dir, "kaur")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(snap_dir, SIDECAR_PATH)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False)
    return {"ok": True, "dest": dest, "zones": len(rows),
            "skipped": len(zones) - len(rows)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build KAUR flood sidecar.")
    ap.add_argument("--gml", required=True, help="Cached flood-snapshot.gml")
    ap.add_argument("--snap", required=True, help="Snapshot dir to write to")
    args = ap.parse_args(argv)
    stats = build_sidecar(args.gml, args.snap)
    print(json.dumps(stats, ensure_ascii=False))
    return 0 if stats.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
