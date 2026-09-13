"""MARU per-KOV market choropleth county masters (issue #486): kovkasv
(p41 YoY appreciation), kovkaive (p149 quarterly deals), kovedas (p43
resale composite), kovkiirus (p484 deal-velocity QoQ, weak flip cap 70).

Stdlib only. Offline, snapshot-only (NO network): KOV polygons come from
the LOCAL Harjumaa/Estonia PBF via the documented osmium pre-step, values
from a maintainer-placed quarterly MARU KOV export in OUR import schema
(kov;quarter;median_eur_m2;deals -- see parse rows below; the MARU query
env is form-driven with no bulk contract, docs/overturn_maru.md).
Pure logic + fixture readers live at module top so unit tests stay
hermetic; full-county builds run only via the documented rebuild commands.

SCOPE (four layers, honest exact joins): every cell holds its own KOV's
band score -- never a kernel, never smoothing across KOV borders, never
interpolation, never forward-fill. A KOV whose quarterly row (or required
quarter PAIR) is absent stays 255 unknown (EI OLE), exactly like the
scorer-side dims_overturn_maru.py NULLs. p421 is REFUSED for the map: the
appraisal-gap band needs the LISTING asking price, so no per-KOV cell
value exists (IA028 national-grain refusal precedent, #485).

BANDS (locked 2026-09-13 from dims_overturn_maru.py -- mirrors
apps/web/lib/layers_maru.ts MARUKOV_BANDS exactly; a pytest parses that
file and fails on drift):
* kovkasv YoY% (same quarter a year apart, never annualised):
  <=-5 -> 75, <0 -> 65, <=+5 -> 50, <=+10 -> 40, above -> 30.
* kovkaive deals (latest quarter, first-cut Harju bands):
  >=300 -> 80, >=100 -> 65, >=30 -> 50, below -> 35.
* kovedas composite (deals>=100, yoy>=0; a missing leg NULLs, no
  half-comps): TT -> 70, TF -> 55, FT -> 50, FF -> 35.
* kovkiirus QoQ% (consecutive quarters, WEAK flip cap 70 -- the
  KV-adapter inventory leg is named EI OLE, never guessed):
  >=+10 -> 70, >=-10 -> 55, below -> 40.

JOIN (KOV-identity or NULL, never faked): normalise_kov is the EXACT
scorer join (lowercase + whitespace collapse, mirroring
dims_overturn_maru.normalise_kov -- local copy, no cross-tree import).
No suffix stripping, no fuzzy match. The build asserts the join BOTH
ways fail-closed: fixture KOVs without polygons and polygons without
fixture rows both abort loudly. The committed
maru_kov_tables.example.json is SYNTHETIC demo data under FAKE kov
names, so building it against the real extract fails closed by
construction (never a silent fake map).

Polygons (same open source as #485, verified on the snapshot extract):
  osmium getid ~/hf-data/2026-09-12/osm/estonia-260911.osm.pbf \
    -r <16 Harju KOV relation ids> \
    -o kov16.osm.pbf && osmium export kov16.osm.pbf -o kov16.geojson
16 admin_level=7 features (name + admin_level survive export; TEHAK:code
does not -- the join is the normalised name, asserted both ways,
fail-closed). Island/islet side-features (place=island, no admin_level)
are OUT by design: the KOV multipolygons already carry their inhabited
islands as outer members; lone skerries stay 255, never guessed.
Rebuild (once the maintainer places the quarterly export):
  python3 scripts/build/batch_maru_choropleth.py --all \
    --tables /path/to/maru_kov_export.json \
    --kov-extract /tmp/kov16.geojson \
    --outdir ~/hf-data/2026-09-12/osm
"""

import argparse
import base64
import json
import math
import os

# ---------------------------------------------------------------------------
# Constants (mirrors walk_raster / batch_statkov_choropleth scales).
# ---------------------------------------------------------------------------

COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
LON_KM = 57.29
LAT_KM = 110.57
STEP_M = 75.0
UNKNOWN = 255
SIGMA = 0.5  # wire sigma == DECAY: Euclidean fallback kernel width only
# (the master itself is exact-fill, no kernel). MARUKOV_DECAY mirrors this.

LAYER_IDS = ("kovkasv", "kovkaive", "kovedas", "kovkiirus")

# Locked bands (mirrored in layers_maru.ts MARUKOV_BANDS -- drift-pinned).
# kovkasv rows are (threshold, score) with per-row comparators documented
# in the TS header (<= -5 -> 75, < 0 -> 65, <= +5 -> 50, <= +10 -> 40);
# kovkaive/kovkiirus rows are [threshold, score], first met from the top.
MARU_BANDS = {
    "kovkasv": [(-5.0, 75), (0.0, 65), (5.0, 50), (10.0, 40)],
    "kovkasv_default": 30,
    "kovkaive": [(300.0, 80), (100.0, 65), (30.0, 50)],
    "kovkaive_default": 35,
    "kovkiirus": [(10.0, 70), (-10.0, 55)],
    "kovkiirus_default": 40,
}


# ---------------------------------------------------------------------------
# Pure join + quarter + band logic (hermetically tested). Local copies of
# the dims_overturn_maru.py join core (no cross-tree import: scripts/build
# files ship per-issue and must stay rebase-safe).
# ---------------------------------------------------------------------------

def normalise_kov(raw):
    """Canonical KOV key: lowercase, whitespace collapsed. Exact only."""
    if raw is None:
        return None
    key = " ".join(str(raw).strip().lower().split())
    return key or None


def _quarter_key(q):
    try:
        year, qq = str(q).split("-Q")
        return (int(year), int(qq))
    except (ValueError, AttributeError):
        return None


def _num(row, key):
    v = row.get(key)
    return float(v) if isinstance(v, (int, float)) else None


def latest_rows(rows, kov):
    """Rows for the exact KOV at the latest quarter present (no trending)."""
    key = normalise_kov(kov)
    if not key:
        return []
    mine = [r for r in rows if normalise_kov(r.get("kov")) == key]
    if not mine:
        return []
    keys = sorted({_quarter_key(r.get("quarter")) for r in mine} - {None})
    if not keys:
        return mine
    latest = keys[-1]
    return [r for r in mine if _quarter_key(r.get("quarter")) == latest]


def kov_value(kov, rows, value_key, quarter=None):
    """Latest-quarter (or pinned-quarter) numeric cell, exact KOV."""
    if quarter is not None:
        key = normalise_kov(kov)
        cand = [r for r in rows
                if normalise_kov(r.get("kov")) == key
                and _quarter_key(r.get("quarter")) == _quarter_key(quarter)]
    else:
        cand = latest_rows(rows, kov)
    for r in cand:
        v = _num(r, value_key)
        if v is not None:
            return v
    return None


def kov_quarters(kov, rows):
    """Sorted quarter labels present for the exact KOV."""
    key = normalise_kov(kov)
    out = sorted({_quarter_key(r.get("quarter")) for r in rows
                  if normalise_kov(r.get("kov")) == key} - {None})
    return ["%d-Q%d" % (y, q) for y, q in out]


def yoy_pct(kov, rows):
    """YoY% of the KOV median (same quarter a year apart, else None)."""
    mine = latest_rows(rows, kov)
    if not mine:
        return None
    now_q = _quarter_key(mine[0].get("quarter"))
    if now_q is None:
        return None
    then = "%d-Q%d" % (now_q[0] - 1, now_q[1])
    med_now = kov_value(kov, rows, "median_eur_m2")
    med_then = kov_value(kov, rows, "median_eur_m2", quarter=then)
    if med_now is None or med_then is None or med_then <= 0:
        return None
    return (med_now - med_then) / med_then * 100.0


def qoq_pct(kov, rows):
    """QoQ% of the KOV deal count (consecutive quarters, else None)."""
    quarters = kov_quarters(kov, rows)
    if len(quarters) < 2:
        return None
    y_now, q_now = _quarter_key(quarters[-1])
    y_prev, q_prev = _quarter_key(quarters[-2])
    consecutive = (y_now == y_prev and q_now == q_prev + 1) or (
        q_now == 1 and q_prev == 4 and y_now == y_prev + 1)
    if not consecutive:
        return None
    now_d = kov_value(kov, rows, "deals", quarter=quarters[-1])
    prev_d = kov_value(kov, rows, "deals", quarter=quarters[-2])
    if now_d is None or prev_d is None or prev_d <= 0:
        return None
    return (now_d - prev_d) / prev_d * 100.0


def yoy_band(yoy):
    """p41 band (None -> None = honestly unknown)."""
    if yoy is None or (isinstance(yoy, float) and math.isnan(yoy)):
        return None
    if yoy <= -5.0:
        return 75
    if yoy < 0.0:
        return 65
    if yoy <= 5.0:
        return 50
    if yoy <= 10.0:
        return 40
    return MARU_BANDS["kovkasv_default"]


def deals_band(deals):
    """p149 band (None -> None = honestly unknown)."""
    if deals is None or (isinstance(deals, float) and math.isnan(deals)):
        return None
    for threshold, score in MARU_BANDS["kovkaive"]:
        if deals >= threshold:
            return score
    return MARU_BANDS["kovkaive_default"]


def resale_band(deals, yoy):
    """p43 composite (a missing leg NULLs -- no half-comps)."""
    if deals is None or yoy is None:
        return None
    deep = deals >= 100
    rising = yoy >= 0.0
    if deep and rising:
        return 70
    if deep:
        return 55
    if rising:
        return 50
    return 35


def qoq_band(chg):
    """p484 weak velocity band (None -> None; max 70 = the weak cap)."""
    if chg is None or (isinstance(chg, float) and math.isnan(chg)):
        return None
    for threshold, score in MARU_BANDS["kovkiirus"]:
        if chg >= threshold:
            return score
    return MARU_BANDS["kovkiirus_default"]


def kov_scores(rows):
    """{normalised kov: {layer: score|None}} for the four layers."""
    kovs = {normalise_kov(r.get("kov")) for r in rows} - {None}
    out = {}
    for kov in sorted(kovs):
        deals = kov_value(kov, rows, "deals")
        yoy = yoy_pct(kov, rows)
        out[kov] = {
            "kovkasv": yoy_band(yoy),
            "kovkaive": deals_band(deals),
            "kovedas": resale_band(deals, yoy),
            "kovkiirus": qoq_band(qoq_pct(kov, rows)),
        }
    return out


# ---------------------------------------------------------------------------
# Geometry: simplify + exact scanline fill (no kernel, hermetically tested).
# Mirrors walk_raster.Grid indexing via batch_statkov_choropleth.py (#485)
# -- copied, not imported: scripts/build files ship per-issue and must
# stay rebase-safe against unmerged siblings.
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
    county grid ends at 25.5E, so far-eastern fringes fill ZERO cells and
    render 255 unknown on EVERY raster layer -- the page legend already
    says red covers unknown areas. The build warns LOUDLY for any
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
            print("  %s: quarterly pair absent -> 255 (EI OLE)" % kov)
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


def load_tables(tables_path):
    """Maintainer-export rows (or the synthetic demo fixture)."""
    with open(tables_path, encoding="utf-8") as fh:
        fixture = json.load(fh)
    rows = fixture.get("rows") or []
    if fixture.get("synthetic"):
        print("NOTE: synthetic demo fixture (fake KOV names) -- masters "
              "built from it are DEMO ONLY, never MARU data")
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", choices=list(LAYER_IDS) + ["all"],
                    default="all")
    ap.add_argument("--tables", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "maru_kov_tables.example.json"))
    ap.add_argument("--kov-extract", default=None)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--probe", action="store_true",
                    help="print probe scores, write nothing")
    args = ap.parse_args(argv)

    rows = load_tables(args.tables)
    scores = kov_scores(rows)
    keyed = {normalise_kov(name): row for name, row in scores.items()}
    for kov in sorted(keyed):
        print("  %-12s %s" % (kov, keyed[kov]))

    if args.kov_extract is None:
        if args.probe:
            return
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
    if args.probe:
        return
    if args.outdir is None:
        raise SystemExit("--outdir is required to write masters")
    for layer in layers:
        write_master(args.outdir, layer, encode_wire(grid, masters[layer],
                                                     layer))


if __name__ == "__main__":
    main()
