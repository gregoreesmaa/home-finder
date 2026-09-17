"""Building-height character tint sidecar builder (issue #621): LoD1 CityGML -> class grid.

Stdlib only (zipfile + xml.etree + struct + math). Offline,
snapshot-only (NO network): the Maa- ja Ruumiamet LoD1 CityGML harvest
is a polite one-off (custom UA, download-page probe + per-municipality
zips, sequential with pauses; 429 stops the run — see
docs/p4_buildings.md); this builder converts the cached zips into the
map sidecar ``<snap>/buildings/buildings-tint.json`` consumed by
/api/layers/buildings/areas. Pure logic at module top so unit tests
stay hermetic; the sidecar write runs only via the documented rebuild
command.

SCOPE: building-height CHARACTER tint, never a score field — height is
taste (view vs shade, shelter vs openness), not good/bad. Classes are
OUR bins over the publisher's bldg:measuredHeight (stated in the
legend, never publisher classes): <3 / 3-6 / 6-12 / 12-25 / >25 m.
Missing or negative measuredHeight stays MISSING (rendered
transparent, never as a low building — a -12 m "height" is an
underground part, not a shed).

HONESTY (load-bearing): only roof-plane rings (all vertices at the
building's max z — LoD1 flat roofs) paint the grid; walls/ground never
do. Courtyard holes subtract (even-odd fill). LoD1 flat roofs overstate
parapet shade — capped hinnang, never survey-grade (legend says so).
A missing input zip is SKIPPED + counted (unknown, never partial);
per-municipality counts are stamped in stats so a short county reads
as short, never as complete.

Rebuild: python3 scripts/build/batch_buildings.py \\
    --cache-dir /tmp/hf-621-cache --snap ~/hf-data/2026-09-12
"""

import argparse
import base64
import json
import math
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

from batch_canopy import lest97_to_lonlat  # noqa: E402  (true LCC inverse, shared; #648)

#: Sidecar filename inside the snapshot dir.
SIDECAR_PATH = os.path.join("buildings", "buildings-tint.json")

#: Publisher attribution (CC BY 4.0 — stamped in stats, not rows).
ATTRIBUTION = "Maa- ja Ruumiamet 3D hoonete LoD1 (CC BY 4.0)"

#: Target lon/lat grid. DELIBERATELY wider than the relief/canopy
#: window (23.3-25.5, which clips Loksa + eastern Kuusalu + southern
#: Saue/Kose): a building layer must contain whole municipalities, so
#: the window is the union envelope of all 16 LoD1 files, rounded out
#: (E 484696-609984 N 6540304-6618468 -> lon 23.73-25.95 lat
#: 58.99-59.70). Each sidecar carries its own bbox; the client renders
#: per-bbox, so windows need not match across layers.
DST_BBOX = (23.7, 58.95, 26.0, 59.75)
DST_COLS = 1000
DST_ROWS = 570

#: Our height bins over bldg:measuredHeight (metres, EH2000). Stated in
#: the legend as our bins — never publisher classes.
CLASS_NAMES = ["<3m", "3-6m", "6-12m", "12-25m", ">25m"]

#: Harju municipalities (post-2017 reform) with LoD1 CityGML zips.
MUNIS = [
    "Anija_vald", "Harku_vald", "Jõelähtme_vald", "Keila_linn",
    "Kiili_vald", "Kose_vald", "Kuusalu_vald", "Lääne-Harju_vald",
    "Loksa_linn", "Maardu_linn", "Raasiku_vald", "Rae_vald",
    "Saku_vald", "Saue_vald", "Tallinn", "Viimsi_vald",
]


def localname(tag: str) -> str:
    """Strip the {namespace} prefix (CityGML 2.0 tags)."""
    return tag.rpartition("}")[2]


def height_class(h: Optional[float]) -> int:
    """Bin a measuredHeight into a tint class 1-5; 0 = missing.

    Negative heights (underground parts) and absent values are 0 and
    counted by the caller — never painted as low buildings.
    """
    if h is None or not math.isfinite(h) or h < 0:
        return 0
    if h < 3:
        return 1
    if h < 6:
        return 2
    if h < 12:
        return 3
    if h < 25:
        return 4
    return 5


def roof_rings_lonlat(building: ET.Element) -> List[List[Tuple[float, float]]]:
    """Exterior + interior roof-plane rings of one bldg:Building, lon/lat.

    Roof plane = the building's max z over all LoD1 vertices (flat
    roofs); only polygons lying fully in that plane count, so walls
    (spanning z) and ground never paint. Interior rings are kept so the
    fill can subtract courtyards (even-odd). Returns [exterior,
    interior, ...] ring lists; empty when no roof plane resolves.

    AXES (load-bearing): EPSG:3301 axis order is NORTHING,EASTING (the
    envelope lowerCorner reads N E h), so posList triples are (n, e, h)
    — swapped on ingest, never assumed.
    """
    polys: List[Tuple[List[Tuple[float, float, float]], List[List[Tuple[float, float, float]]]]] = []
    for poly in building.iter():
        if localname(poly.tag) != "Polygon":
            continue
        ext: List[Tuple[float, float, float]] = []
        holes: List[List[Tuple[float, float, float]]] = []
        for child in poly:
            ln = localname(child.tag)
            if ln not in ("exterior", "interior"):
                continue
            pts: List[Tuple[float, float, float]] = []
            for pl in child.iter():
                if localname(pl.tag) != "posList" or pl.text is None:
                    continue
                nums = [float(v) for v in pl.text.split()]
                pts = [
                    (nums[i], nums[i + 1], nums[i + 2])
                    for i in range(0, len(nums) - 2, 3)
                ]
            if len(pts) >= 4:
                if ln == "exterior":
                    ext = pts
                else:
                    holes.append(pts)
        if ext:
            polys.append((ext, holes))
    if not polys:
        return []
    roof_z = max(p[2] for ext, _ in polys for p in ext)

    def project(pts: List[Tuple[float, float, float]]) -> List[Tuple[float, float]]:
        # Triples are (northing, easting, up): easting=p[1], northing=p[0].
        return [lest97_to_lonlat(p[1], p[0]) for p in pts]

    rings: List[List[Tuple[float, float]]] = []
    for ext, holes in polys:
        if any(abs(p[2] - roof_z) > 1e-6 for p in ext):
            continue  # wall or slope, never roof
        rings.append(project(ext))
        for hole in holes:
            if hole and all(abs(p[2] - roof_z) <= 1e-6 for p in hole):
                rings.append(project(hole))
    return rings


def parse_building(elem: ET.Element) -> Tuple[Optional[float], str, List[List[Tuple[float, float]]]]:
    """measuredHeight, ALS year, roof rings for one Building element."""
    height: Optional[float] = None
    year = ""
    for node in elem.iter():
        ln = localname(node.tag)
        if ln == "measuredHeight" and node.text is not None:
            try:
                height = float(node.text.strip())
            except ValueError:
                height = None
        elif ln == "stringAttribute" and node.get("name") == "lod1_muutmisaeg":
            for val in node:
                if localname(val.tag) == "value" and val.text:
                    year = val.text.strip()[:4]
    return height, year, roof_rings_lonlat(elem)


def fill_rings(
    grid: List[int],
    rings: List[List[Tuple[float, float]]],
    cls: int,
) -> int:
    """Even-odd scanline fill of lon/lat rings onto the county grid.

    Max class wins per cell (a tower over a porch reads as a tower).
    Returns painted cell count.
    """
    if cls <= 0 or not rings:
        return 0
    minlon, minlat, maxlon, maxlat = DST_BBOX
    lon_span = maxlon - minlon
    lat_span = maxlat - minlat
    painted = 0

    def merge(col: int, row: int) -> None:
        nonlocal painted
        if 0 <= col < DST_COLS and 0 <= row < DST_ROWS:
            k = row * DST_COLS + col
            if cls > grid[k]:
                grid[k] = cls
                painted += 1

    # Centroid splat: every building marks at least its own cell (a 10 m
    # house never contains a 128 m cell centre, so footprint fill alone
    # would drop it). The cell DOES contain the building — no invented
    # area; max-wins merge is stated.
    cx = sum(p[0] for p in rings[0]) / len(rings[0])
    cy = sum(p[1] for p in rings[0]) / len(rings[0])
    merge(
        int((cx - minlon) / lon_span * DST_COLS),
        int((maxlat - cy) / lat_span * DST_ROWS),
    )
    pts = [
        (
            (lon - minlon) / lon_span * DST_COLS,
            (maxlat - lat) / lat_span * DST_ROWS,
        )
        for ring in rings
        for lon, lat in ring
    ]
    # NOTE: rings are ONE building's [exterior, interior, ...] and are
    # filled jointly: even-odd subtracts that building's courtyards.
    # Separate buildings merge by max-wins below (never by holes), so
    # shared rowhouse walls cannot unpaint each other.
    rows: Dict[int, List[float]] = {}
    idx = 0
    for ring in rings:
        n = len(ring)
        for i in range(n):
            x0, y0 = pts[idx + i]
            x1, y1 = pts[idx + (i + 1) % n]
            if y0 == y1:
                continue
            lo, hi = (y0, y1) if y0 < y1 else (y1, y0)
            r0 = max(0, int(math.ceil(lo - 0.5)))
            r1 = min(DST_ROWS - 1, int(math.floor(hi - 0.5)))
            for r in range(r0, r1 + 1):
                y = r + 0.5
                x = x0 + (x1 - x0) * (y - y0) / (y1 - y0)
                rows.setdefault(r, []).append(x)
        idx += n
    for r, xs in rows.items():
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            c0 = max(0, int(math.ceil(xs[i] - 0.5)))
            c1 = min(DST_COLS - 1, int(math.floor(xs[i + 1] - 0.5)))
            for c in range(c0, c1 + 1):
                merge(c, r)
    return painted


def parse_zip(path: str) -> Tuple[List[Tuple[Optional[float], str, List[List[Tuple[float, float]]]]], str]:
    """All (height, year, rings) buildings from one municipality zip."""
    out: List[Tuple[Optional[float], str, List[List[Tuple[float, float]]]]] = []
    with zipfile.ZipFile(path) as zf:
        names = [i.filename for i in zf.infolist() if i.filename.lower().endswith(".gml")]
        if len(names) != 1:
            raise ValueError("expected exactly one .gml in %s, got %s" % (path, names))
        with zf.open(names[0]) as fh:
            for _ev, elem in ET.iterparse(fh, events=("end",)):
                if localname(elem.tag) == "Building":
                    out.append(parse_building(elem))
                    elem.clear()
    return out, names[0]


def build_sidecar(
    grid: List[int],
    stats: Dict,
) -> Dict:
    """Assemble the sidecar doc (JSON-serializable)."""
    counts = [0] * 6
    for c in grid:
        counts[c] += 1
    return {
        "vintage": stats.get("years", {}),
        "source": ATTRIBUTION,
        "cols": DST_COLS,
        "rows": DST_ROWS,
        "bbox": {
            "minlon": DST_BBOX[0],
            "minlat": DST_BBOX[1],
            "maxlon": DST_BBOX[2],
            "maxlat": DST_BBOX[3],
        },
        "unit": "class",
        "classes": ["<3m/puudub", "0-3m", "3-6m", "6-12m", "12-25m", ">25m"],
        "bins": "our bins over bldg:measuredHeight (never publisher classes)",
        "encoding": "base64-uint8",
        "stats": stats,
        "counts": counts,
        "data": base64.b64encode(bytes(grid)).decode("ascii"),
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Build the buildings tint-grid sidecar.")
    ap.add_argument("--cache-dir", required=True, help="Dir with hooned_lod1-<muni>-citygml.zip.")
    ap.add_argument("--snap", required=True, help="Snapshot dir.")
    ap.add_argument("--munis", nargs="*", default=MUNIS, help="Municipality subset (default: all Harju).")
    args = ap.parse_args(argv)
    grid = [0] * (DST_COLS * DST_ROWS)
    stats: Dict = {
        "buildings": 0,
        "no_height": 0,
        "negative_height": 0,
        "no_roof": 0,
        "years": {},
        "munis": {},
        "missing_zips": [],
    }
    for muni in args.munis:
        path = os.path.join(args.cache_dir, "hooned_lod1-%s-citygml.zip" % muni)
        if not os.path.exists(path):
            stats["missing_zips"].append(muni)
            continue
        try:
            buildings, _gml = parse_zip(path)
        except (ValueError, zipfile.BadZipFile, ET.ParseError, OSError) as exc:
            print("unreadable %s (%s): SKIPPED, counted" % (path, exc))
            stats["missing_zips"].append(muni)
            continue
        n0 = stats["buildings"]
        for height, year, rings in buildings:
            stats["buildings"] += 1
            if height is None:
                stats["no_height"] += 1
                continue
            if height < 0 or not math.isfinite(height):
                stats["negative_height"] += 1
                continue
            if year:
                stats["years"][year] = stats["years"].get(year, 0) + 1
            if rings:
                fill_rings(grid, rings, height_class(height))
            else:
                stats["no_roof"] += 1
        stats["munis"][muni] = stats["buildings"] - n0
        print("ok %s buildings=%d" % (muni, stats["buildings"] - n0))
    doc = build_sidecar(grid, stats)
    dest = os.path.join(args.snap, SIDECAR_PATH)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    painted = sum(doc["counts"][1:])
    print(
        "ok=True %s buildings=%d painted=%d/%d missing_zips=%s"
        % (dest, stats["buildings"], painted, len(grid), stats["missing_zips"])
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
