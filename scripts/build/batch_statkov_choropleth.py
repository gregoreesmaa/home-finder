"""Statamet per-KOV choropleth county masters (issue #485): kovmigr (RVR02
2025 net migration), kovehit (EH44U 2025 completions), kovfisc (RR300 2025
operating margin).

Stdlib only. Offline, snapshot-only (NO network): KOV polygons come from
the LOCAL Harjumaa/Estonia PBF via the documented osmium pre-step, values
from the committed aggregate fixture scripts/build/statkov_px_tables.json
(harvested once by harvest_statkov_px.py, quarterly refresh). Pure logic +
fixture readers live at module top so unit tests stay hermetic; full-county
builds run only via the documented rebuild commands.

SCOPE (three layers, honest exact joins): every cell holds its own KOV's
band score -- never a kernel, never smoothing across KOV borders, never
interpolation. A KOV whose series row is absent stays 255 unknown (EI OLE),
exactly like the scorer-side dims_p4_stat.py NULLs. IA028 (dwelling-price
index) is REFUSED for the map: NATIONAL grain only (Aasta/Kvartal/
Eluaseme liik, no area dimension, verified 2026-09-13) -- a national
constant painted per-KOV would be one flat colour, not a map (MARU/Euribor
PR #475 precedent). EH permits are REFUSED as a ratio leg: no KOV grain
(EH04 national, EH045 county) -- kovehit scores completions only, capped
at 70 with the permits leg named missing (MARU p484 weak-flip precedent).

BANDS (locked 2026-09-13 from the real fixture -- mirrors
apps/web/lib/layers_statkov.ts STATKOV_BANDS exactly; a pytest parses that
file and fails on drift):
* kovmigr net migration /1000 (dims_p4_stat.dim_micro_liquidity_stat bands):
  >=+10 -> 75, >=-5 -> 60, >=-20 -> 45, below -> 30.
* kovehit completions /1000 (weak flip, cap 70 -- permits leg missing):
  >=20 -> 30, >=10 -> 45, >=4 -> 60, below -> 70.
* kovfisc operating margin tulem/tulud % (weak flip, cap 70 -- debt-stock
  leg missing, named EI OLE): >=+10 -> 70, >=+5 -> 60, >=0 -> 45, below -> 30.
Denominator: mid-2025 population (mean of RV0291U 01.01.2025 + 01.01.2026).

Polygons (verified on the snapshot extract 2026-09-13):
  osmium getid ~/hf-data/2026-09-12/osm/estonia-260911.osm.pbf \
    -r r350208 r350346 r350633 r350740 r350902 r351474 r351602 r352021 \
       r352240 r352559 r352581 r352935 r353192 r355398 r350547 r7692055 \
    -o kov16.osm.pbf && osmium export kov16.osm.pbf -o kov16.geojson
16 admin_level=7 features (name + admin_level survive export; TEHAK:code
does not -- the join is the normalised name, asserted 16/16 both ways,
fail-closed). Island/islet side-features (place=island, no admin_level)
are OUT by design: the KOV multipolygons already carry their inhabited
islands as outer members (Viimsi 55, Kuusalu 35 polys); lone skerries
stay 255, never guessed into a KOV.
Rebuild: python3 scripts/build/batch_statkov_choropleth.py --all \
  --kov-extract /tmp/kov16.geojson \
  --outdir ~/hf-data/2026-09-12/osm
"""

import argparse
import base64
import json
import math
import os

# ---------------------------------------------------------------------------
# Constants (mirrors walk_raster / batch_rsafety_osm scales).
# ---------------------------------------------------------------------------

COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
LON_KM = 57.29
LAT_KM = 110.57
STEP_M = 75.0
UNKNOWN = 255
SIGMA = 0.5  # wire sigma == DECAY: Euclidean fallback kernel width only
# (the master itself is exact-fill, no kernel). STATKOV_DECAY mirrors this.

LAYER_IDS = ("kovmigr", "kovehit", "kovfisc")

# Locked bands (mirrored in layers_statkov.ts STATKOV_BANDS -- drift-pinned).
# (threshold, score): first threshold met from the top wins.
STATKOV_BANDS = {
    "kovmigr": [(10.0, 75), (-5.0, 60), (-20.0, 45)],
    "kovmigr_default": 30,
    "kovehit": [(20.0, 30), (10.0, 45), (4.0, 60)],
    "kovehit_default": 70,
    "kovfisc": [(10.0, 70), (5.0, 60), (0.0, 45)],
    "kovfisc_default": 30,
}

PROBE_POINTS = {  # lon, lat -- band witnesses, also --probe output
    "Tallinn-kesk": (24.7536, 59.4364),
    "Viimsi": (24.8311, 59.5412),
    "Keila-Joa": (24.2900, 59.4000),  # Lääne-Harju witness (Loksa town sits
    # past the county grid edge 25.5E -- platform-wide clip, see docstring)
    "Keila": (24.4212, 59.3134),
    "Kuusalu": (25.4417, 59.4461),
    "Gulf": (24.7, 59.72),  # sea: must stay 255
}


# ---------------------------------------------------------------------------
# Pure join + rate + band logic (hermetically tested).
# ---------------------------------------------------------------------------

def normalise_kov(raw):
    """Canonical KOV key: lowercase, leading dots stripped, -vald/-linn off.

    PX texts ('..Anija vald', '..Tallinn') and OSM names ('Anija vald',
    'Tallinn', 'Keila linn') meet here. Exact match only, never fuzzy.
    """
    if raw is None:
        return None
    key = " ".join(str(raw).strip().lower().lstrip(".").split())
    for suffix in (" vald", " linn"):
        if key.endswith(suffix):
            key = key[: -len(suffix)]
    return key or None


def fixture_rates(kovs):
    """Per-KOV derived rates from the fixture table (None-safe).

    Returns {kov: {"net_k": saldo/1000, "comp_k": completions/1000,
    "margin": tulem/tulud %}}; any missing input NULLs that KOV's rate.
    """
    out = {}
    for name, row in (kovs or {}).items():
        pop25 = row.get("pop_2025_01_01")
        pop26 = row.get("pop_2026_01_01")
        pop = None
        if isinstance(pop25, (int, float)) and isinstance(pop26, (int, float)):
            if pop25 > 0 and pop26 > 0:
                pop = (pop25 + pop26) / 2.0
        saldo = row.get("rvr_saldo_2025")
        comp = row.get("eh_completions_2025")
        tulud = row.get("rr_tulud_2025")
        tulem = row.get("rr_tulem_2025")
        net_k = (saldo / pop * 1000.0
                 if isinstance(saldo, (int, float)) and pop else None)
        comp_k = (comp / pop * 1000.0
                  if isinstance(comp, (int, float)) and pop else None)
        margin = (tulem / tulud * 100.0
                  if isinstance(tulem, (int, float))
                  and isinstance(tulud, (int, float)) and tulud > 0 else None)
        out[name] = {"net_k": net_k, "comp_k": comp_k, "margin": margin}
    return out


def band_score(layer, value):
    """Band a rate to 0..100 (None -> None = honestly unknown)."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    for threshold, score in STATKOV_BANDS[layer]:
        if value >= threshold:
            return score
    return STATKOV_BANDS[layer + "_default"]


def kov_scores(fixture):
    """{kov: {layer: score|None}} for the three layers (fixture grain)."""
    rates = fixture_rates(fixture.get("kovs"))
    out = {}
    for name, rate in rates.items():
        out[name] = {
            "kovmigr": band_score("kovmigr", rate["net_k"]),
            "kovehit": band_score("kovehit", rate["comp_k"]),
            "kovfisc": band_score("kovfisc", rate["margin"]),
        }
    return out


# ---------------------------------------------------------------------------
# Geometry: simplify + exact scanline fill (no kernel, hermetically tested).
# ---------------------------------------------------------------------------

def _perp_dist(pt, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    denom = math.hypot(dx, dy)
    if denom == 0:
        return math.hypot(pt[0] - a[0], pt[1] - a[1])
    return abs((pt[0] - a[0]) * dy - (pt[1] - a[1]) * dx) / denom


def douglas_peucker(ring, tol):
    """Simplify a ring (tolerance in degrees); endpoints always kept."""
    if len(ring) <= 4:
        return list(ring)
    keep = [False] * len(ring)
    keep[0] = keep[-1] = True
    stack = [(0, len(ring) - 1)]
    while stack:
        first, last = stack.pop()
        if last <= first + 1:
            continue
        a, b = ring[first], ring[last]
        best, idx = 0.0, -1
        for i in range(first + 1, last):
            d = _perp_dist(ring[i], a, b)
            if d > best:
                best, idx = d, i
        if best > tol:
            keep[idx] = True
            stack.append((first, idx))
            stack.append((idx, last))
    return [pt for pt, k in zip(ring, keep) if k]


class Grid:
    """75 m county grid (mirrors walk_raster.Grid indexing)."""

    def __init__(self, bbox=COUNTY_BBOX, step_m=STEP_M):
        self.bbox = list(bbox)
        self.step = step_m
        minlon, minlat, maxlon, maxlat = bbox
        self.cols = int(round((maxlon - minlon) * LON_KM * 1000 / step_m))
        self.rows = int(round((maxlat - minlat) * LAT_KM * 1000 / step_m))

    def cell_of(self, lon, lat):
        minlon, minlat, _, _ = self.bbox
        ix = int((lon - minlon) * LON_KM * 1000 / self.step)
        iy = int((lat - minlat) * LAT_KM * 1000 / self.step)
        if 0 <= ix < self.cols and 0 <= iy < self.rows:
            return iy * self.cols + ix
        return None

    def center_of(self, k):
        minlon, minlat, _, _ = self.bbox
        ix, iy = k % self.cols, k // self.cols
        return (minlon + (ix + 0.5) * self.step / 1000 / LON_KM,
                minlat + (iy + 0.5) * self.step / 1000 / LAT_KM)


def _row_of(grid, lat):
    return int((lat - grid.bbox[1]) * LAT_KM * 1000 / grid.step)


def _col_of(grid, lon):
    return int((lon - grid.bbox[0]) * LON_KM * 1000 / grid.step)


def fill_cells(grid, rings):
    """Cell indices whose center falls inside the rings (even-odd rule).

    All rings of one KOV (outers + holes) fill together: a hole toggles
    back off, an island in a lake toggles back on -- correct for clean
    OSM multipolygon topology. Cell centers only, no antialiasing.
    """
    cells = set()
    segs = []
    for ring in rings:
        if len(ring) < 4:
            continue
        pts = ring if ring[0] == ring[-1] else ring + [ring[0]]
        segs.extend(zip(pts, pts[1:]))
    if not segs:
        return cells
    lats = [p[1] for ring in rings for p in ring]
    iy0 = max(0, _row_of(grid, min(lats)))
    iy1 = min(grid.rows - 1, _row_of(grid, max(lats)))
    for iy in range(iy0, iy1 + 1):
        y = grid.bbox[1] + (iy + 0.5) * grid.step / 1000 / LAT_KM
        xs = []
        for (x1, y1), (x2, y2) in segs:
            if (y1 > y) != (y2 > y):
                xs.append(x1 + (y - y1) / (y2 - y1) * (x2 - x1))
        xs.sort()
        for j in range(0, len(xs) - 1, 2):
            ix0 = max(0, _col_of(grid, xs[j]))
            ix1 = min(grid.cols - 1, _col_of(grid, xs[j + 1]))
            for ix in range(ix0, ix1 + 1):
                cells.add(iy * grid.cols + ix)
    return cells


# ---------------------------------------------------------------------------
# Extract reading + master build (I/O below this line).
# ---------------------------------------------------------------------------

def read_kov_rings(extract_path, simplify_tol=0.0007):
    """{canonical kov: [simplified rings]} from an osmium-exported extract.

    Keeps Polygon/MultiPolygon features with admin_level == "7" and a
    name; island side-products (place=island/islet, no admin_level) drop
    out. Fail-closed: every kept feature must normalise to non-None.

    GRID-EDGE CLIP (platform-wide, not this layer's gap): the shared
    county grid ends at 25.5E, so Loksa town (25.70-25.74E) and the
    far-eastern Kuusalu/Anija forest fringe fill ZERO cells and render
    255 unknown on EVERY raster layer -- the page legend already says red
    covers unknown areas. Loksa's fixture rows stay shipped (true data,
    renders if the grid ever extends); the build warns LOUDLY for any
    zero-cell KOV.
    """
    with open(extract_path, encoding="utf-8") as fh:
        data = json.load(fh)
    out = {}
    for feat in data.get("features", []):
        geom = feat.get("geometry") or {}
        if geom.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        props = feat.get("properties") or {}
        if str(props.get("admin_level")) != "7" or not props.get("name"):
            continue
        key = normalise_kov(props.get("name"))
        if not key:
            raise SystemExit("unjoinable KOV name in extract: %r"
                             % props.get("name"))
        polys = (geom["coordinates"] if geom["type"] == "MultiPolygon"
                 else [geom["coordinates"]])
        rings = []
        for poly in polys:
            for ring in poly:
                simp = douglas_peucker([(float(x), float(y)) for x, y in ring],
                                       simplify_tol)
                if len(simp) >= 4:
                    rings.append(simp)
        if not rings:
            raise SystemExit("KOV %r lost all rings to simplification" % key)
        if key in out:
            raise SystemExit("duplicate KOV feature in extract: %r" % key)
        out[key] = rings
    return out


def build_layer(grid, layer, kov_rings, scores):
    """{cell: score} for one layer; border cells first-wins (counted)."""
    if layer not in LAYER_IDS:
        raise SystemExit("unknown layer %s" % layer)
    merged = {}
    conflicts = 0
    for kov in sorted(kov_rings):
        score = scores.get(kov, {}).get(layer)
        if score is None:
            print("  %s: series row absent -> 255 (EI OLE)" % kov)
            continue
        for cell in fill_cells(grid, kov_rings[kov]):
            if cell in merged:
                conflicts += 1
                continue
            merged[cell] = score
    return merged, conflicts


def encode_wire(grid, values, layer):
    n = grid.cols * grid.rows
    buf = bytearray([UNKNOWN]) * n
    for k, v in values.items():
        buf[k] = max(0, min(100, int(v)))
    minlon, minlat, maxlon, maxlat = grid.bbox
    return {
        "bbox": {"minlon": minlon, "minlat": minlat,
                 "maxlon": maxlon, "maxlat": maxlat},
        "step_m": grid.step,
        "cols": grid.cols, "rows": grid.rows,
        "half": None, "sigma": SIGMA, "per": 0, "cap": 0,
        "unknown": UNKNOWN, "dtype": "uint8",
        "data": base64.b64encode(bytes(buf)).decode("ascii"),
    }


def write_master(outdir, layer, doc):
    name = "%s-walk-raster.json" % layer
    with open(os.path.join(outdir, name), "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    print("wrote %s (%d B)" % (name, os.path.getsize(
        os.path.join(outdir, name))))


def probe_scores(masters, grid):
    for name, (lon, lat) in PROBE_POINTS.items():
        k = grid.cell_of(lon, lat)
        vals = {}
        for layer, cells in masters.items():
            vals[layer] = cells.get(k) if k is not None else None
        print("  %-13s -> %s" % (name, vals))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", choices=list(LAYER_IDS) + ["all"],
                    default="all")
    ap.add_argument("--tables", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "statkov_px_tables.json"))
    ap.add_argument("--kov-extract", default=None)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--probe", action="store_true",
                    help="print probe scores, write nothing")
    args = ap.parse_args(argv)

    with open(args.tables, encoding="utf-8") as fh:
        fixture = json.load(fh)
    scores = kov_scores(fixture)
    keyed = {normalise_kov(name): row for name, row in scores.items()}

    if args.kov_extract is None:
        raise SystemExit("--kov-extract is required (see module docstring)")
    kov_rings = read_kov_rings(args.kov_extract)
    missing_geo = set(keyed) - set(kov_rings)
    if missing_geo:
        raise SystemExit("fixture KOVs without polygons: %s"
                         % sorted(missing_geo))
    missing_data = set(kov_rings) - set(keyed)
    if missing_data:
        raise SystemExit("polygons without fixture rows: %s"
                         % sorted(missing_data))

    grid = Grid()
    for kov in sorted(kov_rings):
        n = len(fill_cells(grid, kov_rings[kov]))
        print("  %-12s %d cells" % (kov, n))
        if n == 0:
            print("  WARNING: %s fills zero cells (grid-edge clip?) -- "
                  "renders 255 unknown" % kov)
    layers = list(LAYER_IDS) if args.layer == "all" else [args.layer]
    masters = {}
    for layer in layers:
        cells, conflicts = build_layer(grid, layer, kov_rings, keyed)
        print("%s: %d cells, %d border conflicts, %d unknown-KOV skips"
              % (layer, len(cells), conflicts,
                 len(kov_rings) - len([k for k in kov_rings
                                       if keyed.get(k, {}).get(layer)
                                       is not None])))
        masters[layer] = cells
    probe_scores(masters, grid)
    if args.probe:
        return
    if args.outdir is None:
        raise SystemExit("--outdir is required to write masters")
    for layer in layers:
        write_master(args.outdir, layer, encode_wire(grid, masters[layer],
                                                     layer))


if __name__ == "__main__":
    main()
