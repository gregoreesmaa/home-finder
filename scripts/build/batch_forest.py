"""Forest-change overlay sidecar builder (issue #624): SHP vintage -> areas.

Stdlib only (zipfile + struct). Offline, snapshot-only (NO network):
the Metsamuutused SHP harvest is a polite one-off (custom UA, single
59 MB zip; 429 stops the run — see docs/p4_forestchange.md); this
builder converts the cached zip into the map sidecar
``<snap>/forest/forest-areas.json`` consumed by
/api/layers/forest/areas. Pure logic at module top so unit tests stay
hermetic; the sidecar write runs only via the documented rebuild
command.

SCOPE: detected-change overlay bands, NULL-empty outside. The overlay
paints DETECTION polygons (class by detection age at build); the
per-listing distance bands (<=3y<=500m->30 etc.) are the SCORER's job
(services/scoring/dims_p4_forestchange.py, flipped by this issue's
licence verdict) — distance is per-listing, never per-polygon.
Detected change is a warning overlay + caveat, never "safe forest".

HONESTY (load-bearing): 3301 is Lambert Conformal Conic 2SP
(EPSG:3301 — see batch_canopy lest97_to_lonlat_lcc, issue #648; the
legacy TM there is 20-85 m off and is NOT used here). Rings are
Douglas-Peucker simplified at 5 m in metric 3301 BEFORE projection
(stated in stats: vertex counts pre/post) — the scorer's distances
read off the same simplified rings, consistently. Polygons outside
Harju+2 km margin are dropped (the margin keeps the scorer's 1500 m
band complete); outside every polygon is NULL (never safe forest).
A missing/unreadable input writes NOTHING (unknown, never partial).

Rebuild: python3 scripts/build/batch_forest.py \\
    --zip /tmp/hf-624-cache/metsamuutused-2024.zip --snap ~/hf-data/2026-09-12
"""

import argparse
import json
import math
import os
import struct
import sys
import zipfile
from datetime import date
from typing import Dict, List, Optional, Tuple

from batch_canopy import lest97_to_lonlat_lcc  # noqa: E402  (true LCC, NOT legacy TM)

#: Sidecar filename inside the snapshot dir.
SIDECAR_PATH = os.path.join("forest", "forest-areas.json")

#: Publisher attribution (ETAK open-data licence 01.01.2025, bundled in
#: the distribution as ETAK-open-data-licence.pdf + Estonian twin;
#: grant-by-use, PUBLIC catalogue access — licence verdict 2026-09-17,
#: see docs/p4_forestchange.md).
ATTRIBUTION = "Maa- ja Ruumiamet metsamuutused 2024 (ETAK avaandmete litsents)"

#: Harvest vintage (detection flight year).
VINTAGE = "2024"

#: Keep window: Harju + 2 km margin (metres, 3301) so the scorer's
#: 1500 m band stays complete at the county edge.
KEEP_BBOX = (478000.0, 6533000.0, 614000.0, 6622000.0)

#: Ring simplification tolerance (metres, in 3301 before projection).
DP_TOL_M = 5.0

#: Overlay classes by detection age at build (mirror the scorer's age
#: brackets; distance bands are per-listing, never per-polygon).
CLASS_NAMES = ["", ">10a", "3-10a", "värske ≤3a"]


def _plus_years(day: date, years: int) -> date:
    # Calendar-year arithmetic (leap-safe): a detection exactly N
    # calendar years before the build is still "within N years", which a
    # days/365.25 float gets wrong at the boundary (1096/365.25 > 3).
    try:
        return day.replace(year=day.year + years)
    except ValueError:  # Feb 29 -> Feb 28
        return day.replace(year=day.year + years, day=28)


def detection_class(second: Optional[date], built: date) -> int:
    """Class 1-3 by detection age; 0 = undatable (dropped + counted)."""
    if second is None or second > built:
        return 0
    if _plus_years(second, 3) >= built:
        return 3
    if _plus_years(second, 10) >= built:
        return 2
    return 1


def _parse_ymd(raw: bytes) -> Optional[date]:
    try:
        text = raw.split(b"\x00")[0].decode("utf-8").strip()[:10]
        y, m, d = text.split("-")
        return date(int(y), int(m), int(d))
    except (ValueError, AttributeError):
        return None


def read_dbf(dbf: bytes) -> List[Dict]:
    """DBF rows as dicts (UTF-8 per .cpg)."""
    nrec = struct.unpack("<I", dbf[4:8])[0]
    hlen = struct.unpack("<H", dbf[8:10])[0]
    rlen = struct.unpack("<H", dbf[10:12])[0]
    fields: List[Tuple[str, int]] = []
    p = 32
    while dbf[p] != 0x0D:
        fields.append((dbf[p:p + 11].split(b"\x00")[0].decode("latin-1"), dbf[p + 16]))
        p += 32
    rows = []
    for n in range(nrec):
        row = dbf[hlen + n * rlen: hlen + (n + 1) * rlen]
        if row[:1] == b"*":
            continue  # deleted
        vals: Dict[str, bytes] = {}
        q = 1
        for name, fl in fields:
            vals[name] = row[q:q + fl]
            q += fl
        rows.append(vals)
    return rows


def read_shp_polygons(shp: bytes) -> List[Tuple[Tuple[float, float, float, float], List[List[Tuple[float, float]]]]]:
    """SHP Polygon records as (bbox, parts); parts are (E, N) rings."""
    stype = struct.unpack("<i", shp[32:36])[0]
    if stype != 5:
        raise ValueError("expected Polygon (5), got %d" % stype)
    out = []
    pos = 100
    while pos + 8 <= len(shp):
        rlen16 = struct.unpack(">i", shp[pos + 4:pos + 8])[0]
        end = pos + 8 + rlen16 * 2
        if end > len(shp):
            break
        t = struct.unpack("<i", shp[pos + 8:pos + 12])[0]
        if t != 5:
            raise ValueError("mixed shape type %d" % t)
        xmin, ymin, xmax, ymax = struct.unpack("<4d", shp[pos + 12:pos + 44])
        nparts, npts = struct.unpack("<ii", shp[pos + 44:pos + 52])
        starts = struct.unpack("<%di" % nparts, shp[pos + 52:pos + 52 + 4 * nparts])
        pts = struct.unpack("<%dd" % (2 * npts), shp[pos + 52 + 4 * nparts:pos + 52 + 4 * nparts + 16 * npts])
        parts = []
        for i in range(nparts):
            lo = starts[i]
            hi = starts[i + 1] if i + 1 < nparts else npts
            parts.append([(pts[j * 2], pts[j * 2 + 1]) for j in range(lo, hi)])
        out.append(((xmin, ymin, xmax, ymax), parts))
        pos = end
    return out


def _dp_dist(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def simplify_ring(ring: List[Tuple[float, float]], tol: float) -> List[Tuple[float, float]]:
    """Douglas-Peucker (iterative); closed rings stay closed."""
    if len(ring) <= 4:
        return list(ring)
    closed = ring[0] == ring[-1]
    pts = ring[:-1] if closed else list(ring)
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        dmax, idx = 0.0, -1
        for i in range(a + 1, b):
            dd = _dp_dist(pts[i][0], pts[i][1], pts[a][0], pts[a][1], pts[b][0], pts[b][1])
            if dd > dmax:
                dmax, idx = dd, i
        if dmax > tol:
            keep[idx] = True
            stack.append((a, idx))
            stack.append((idx, b))
    out = [p for p, k in zip(pts, keep) if k]
    if closed:
        out.append(out[0])
    return out


def project_ring(ring: List[Tuple[float, float]]) -> List[List[float]]:
    """3301 (E, N) ring -> lon/lat ring, 5 decimals (~1 m)."""
    return [[round(lon, 5), round(lat, 5)] for lon, lat in
            (lest97_to_lonlat_lcc(e, n) for e, n in ring)]


def change_record(change_id: str, season: str, first: Optional[date],
                  second: Optional[date], area_ha: float,
                  parts: List[List[Tuple[float, float]]],
                  built: date) -> Optional[Dict]:
    """One sidecar row, or None (undatable/degenerate — counted)."""
    cls = detection_class(second, built)
    if cls <= 0 or not parts:
        return None
    rings = []
    for part in parts:
        simp = simplify_ring(part, DP_TOL_M)
        if len(simp) >= 4:
            rings.append(project_ring(simp))
    if not rings:
        return None
    lons = [p[0] for r in rings for p in r]
    lats = [p[1] for r in rings for p in r]
    return {
        "change_id": change_id,
        "season": season,
        "first": first.isoformat() if first else None,
        "second": second.isoformat() if second else None,
        "area_ha": round(area_ha, 2),
        "cls": cls,
        "b": [min(lons), min(lats), max(lons), max(lats)],
        "r": rings,
    }


def build_sidecar(rows: List[Dict], stats: Dict) -> Dict:
    """Assemble the sidecar doc (JSON-serializable)."""
    return {
        "vintage": VINTAGE,
        "source": ATTRIBUTION,
        "unit": "detected canopy-change polygon (second_date 2024)",
        "classes": ["", ">10a", "3-10a", "2024 värske"],
        "simplify_m": DP_TOL_M,
        "stats": stats,
        "areas": rows,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Build the forest-change areas sidecar.")
    ap.add_argument("--zip", required=True, help="Cached Metsamuutused_YYYY.zip.")
    ap.add_argument("--snap", required=True, help="Snapshot dir.")
    ap.add_argument("--built", default="2026-09-17", help="Build date YYYY-MM-DD (age anchor).")
    args = ap.parse_args(argv)
    built = date(*[int(v) for v in args.built.split("-")])
    if not os.path.exists(args.zip):
        print("missing input %s: wrote NOTHING (unknown, never partial)" % args.zip)
        return 1
    try:
        zf = zipfile.ZipFile(args.zip)
    except (zipfile.BadZipFile, OSError) as exc:
        print("unreadable input %s (%s): wrote NOTHING" % (args.zip, exc))
        return 1
    rows: List[Dict] = []
    stats: Dict = {"polygons": 0, "dropped": 0, "seasons": {},
                   "verts_raw": 0, "verts_kept": 0, "built": args.built}
    for fn in sorted(set(n for n in zf.namelist() if n.endswith(".shp"))):
        # fn like 2024_kevad.shp -> season kevad.
        season = fn.rsplit(".", 1)[0].split("_", 1)[1] if "_" in fn else "?"
        try:
            polys = read_shp_polygons(zf.read(fn))
            dbf_rows = read_dbf(zf.read(fn[:-4] + ".dbf"))
        except (ValueError, struct.error, KeyError) as exc:
            print("unreadable member %s (%s): SKIPPED, counted" % (fn, exc))
            stats.setdefault("broken_members", []).append(fn)
            continue
        n0 = len(rows)
        for idx, ((xmin, ymin, xmax, ymax), parts) in enumerate(polys):
            stats["polygons"] += 1
            if xmax < KEEP_BBOX[0] or xmin > KEEP_BBOX[2] or \
               ymax < KEEP_BBOX[1] or ymin > KEEP_BBOX[3]:
                continue
            dbf = dbf_rows[idx] if idx < len(dbf_rows) else {}
            try:
                area_ha = float(dbf.get("Pindala", b"0").strip() or 0)
            except ValueError:
                area_ha = 0.0
            stats["verts_raw"] += sum(len(p) for p in parts)
            row = change_record(
                "%s-%d" % (season, idx),
                season,
                _parse_ymd(dbf.get("Algus", b"")),
                _parse_ymd(dbf.get("Lopp", b"")),
                area_ha,
                parts,
                built,
            )
            if row is None:
                stats["dropped"] += 1
                continue
            stats["verts_kept"] += sum(len(r) for r in row["r"])
            rows.append(row)
        stats["seasons"][season] = len(rows) - n0
        print("ok %s kept=%d" % (fn, len(rows) - n0))
    doc = build_sidecar(rows, stats)
    dest = os.path.join(args.snap, SIDECAR_PATH)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    print("ok=True %s polygons=%d kept=%d dropped=%d verts=%d->%d"
          % (dest, stats["polygons"], len(rows), stats["dropped"],
             stats["verts_raw"], stats["verts_kept"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
