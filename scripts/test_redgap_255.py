"""Red-gap regression tests (issue #96): 255 attribution on /layers rasters.

Hermetic by default: reads only the LOCAL 2026-09-12 snapshot
(HF_SNAPSHOT_DIR or ~/hf-data/2026-09-12); the whole module SKIPS when the
snapshot is absent (e.g. CI runners without hf-data). No live Overpass, no
network -- except test_live_matches_replica, which runs only when
HF_LIVE_URL is set (explicitly-flagged integration test).

What is locked:
  * wire validity of all 16 walk-raster masters (county 75 m + metro 9.375 m);
  * red-amid-green speckle == 0 over dense Tallinn, all 8 layers (the
    min-distance-per-cell restamp fix);
  * every rural residual-255 cell is faithful no-data: its independent
    Euclidean kernel score from snapshot features is < 3 (renders red
    either way), i.e. zero cells with score >= 10 (would-be-visible green);
  * city views render zero in-view unknown cells at client resolution;
  * the serve replica used here is bit-exact with the live server
    (integration, flagged).

Run: python3 -m pytest scripts/ -q   (from repo root)
"""
import base64
import json
import math
import os
import urllib.request

import pytest

SNAP = os.environ.get(
    "HF_SNAPSHOT_DIR", os.path.join(os.path.expanduser("~"), "hf-data", "2026-09-12"))
OSM = os.path.join(SNAP, "osm")

LAYERS = ["transit", "parks", "schools", "walkability", "pedinfra",
          "cycling", "grocery", "healthcare"]
SIGMA = {"transit": 0.2, "parks": 0.25, "schools": 0.8, "walkability": 0.2,
         "pedinfra": 0.25, "cycling": 0.3, "grocery": 0.3, "healthcare": 0.8}
HALF = {"transit": 1500.0, "parks": 15.0, "walkability": 300.0,
        "pedinfra": 12.0, "cycling": 3.0, "grocery": 6.0, "healthcare": 20.0}

TALLINN_DENSE = (24.70, 59.415, 24.77, 59.445)
KANGRU_RURAL = (24.64, 59.335, 24.72, 59.375)
KRISTIINE = (24.66, 59.405, 24.72, 59.435)

FILL_PASSES = 64  # must match FILL_PASSES in lib/server/snapshot.ts


def _snapshot_present():
    try:
        return all(
            os.path.exists(os.path.join(OSM, f"{layer}-{kind}.json"))
            for layer in LAYERS for kind in ("walk-raster", "metro"))
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not _snapshot_present(),
    reason=f"local snapshot absent at {SNAP} (needs hf-data/2026-09-12)")


def hav_km(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin(math.radians(lat2 - lat1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def jround(x):
    """Math.round replica (half up; Python round() is half-even)."""
    return math.floor(x + 0.5)


def kernel(d, sigma):
    return math.exp(-d * d / (2 * sigma * sigma))


def saturate(s, half):
    return 100.0 * s / (s + half) if s > 0 else 0.0


_CACHE = {}


def load_county(layer):
    if ("c", layer) not in _CACHE:
        with open(os.path.join(OSM, f"{layer}-walk-raster.json"),
                  encoding="utf-8") as f:
            doc = json.load(f)
        _CACHE[("c", layer)] = (doc, base64.b64decode(doc["data"]))
    return _CACHE[("c", layer)]


def load_metro(layer):
    if ("m", layer) not in _CACHE:
        with open(os.path.join(OSM, f"{layer}-metro.json"),
                  encoding="utf-8") as f:
            meta = json.load(f)
        with open(os.path.join(OSM, f"{layer}-metro.u8"), "rb") as f:
            vals = f.read()
        _CACHE[("m", layer)] = (meta, vals)
    return _CACHE[("m", layer)]


def metro_nearest(vals, meta, lon, lat):
    b = meta["bbox"]
    ix = math.floor(((lon - b["minlon"]) / (b["maxlon"] - b["minlon"])) * meta["cols"])
    iy = math.floor(((lat - b["minlat"]) / (b["maxlat"] - b["minlat"])) * meta["rows"])
    if ix < 0 or iy < 0 or ix >= meta["cols"] or iy >= meta["rows"]:
        return None
    return vals[iy * meta["cols"] + ix]


def county_sample(vals, doc, lon, lat):
    """Replica of sampleRaster(): bilinear, unknown-skip, nearest fallback."""
    b, cols, rows = doc["bbox"], doc["cols"], doc["rows"]
    gx = ((lon - b["minlon"]) / (b["maxlon"] - b["minlon"])) * cols - 0.5
    gy = ((lat - b["minlat"]) / (b["maxlat"] - b["minlat"])) * rows - 0.5
    if gx < -0.5 or gy < -0.5 or gx > cols - 0.5 or gy > rows - 0.5:
        return None
    x0, y0 = math.floor(gx), math.floor(gy)
    fx, fy = gx - x0, gy - y0
    sv = sw = 0.0
    nearest, nd_best = None, float("inf")
    for ix, iy, fw in ((x0, y0, (1 - fx) * (1 - fy)),
                       (x0 + 1, y0, fx * (1 - fy)),
                       (x0, y0 + 1, (1 - fx) * fy),
                       (x0 + 1, y0 + 1, fx * fy)):
        if ix < 0 or iy < 0 or ix >= cols or iy >= rows:
            continue
        v = vals[iy * cols + ix]
        if v == 255:
            continue
        d = abs(ix - gx) + abs(iy - gy)
        if d < nd_best:
            nd_best, nearest = d, v
        sv += fw * v
        sw += fw
    if sw > 0:
        return sv / sw
    return float(nearest) if nearest is not None else None


def serve(layer, view, cols, rows):
    """Bit-exact replica of loadWindowRaster() (verified diff=0 vs :3108)."""
    doc, cvals = load_county(layer)
    meta, mvals = load_metro(layer)
    minlon, minlat, maxlon, maxlat = view
    out = bytearray(cols * rows)
    cover = bytearray(cols * rows)
    for iy in range(rows):
        lat = minlat + ((iy + 0.5) / rows) * (maxlat - minlat)
        for ix in range(cols):
            lon = minlon + ((ix + 0.5) / cols) * (maxlon - minlon)
            v = None
            m = metro_nearest(mvals, meta, lon, lat)
            if m is not None and m != 255:
                v = m
            if v is None:
                hit = county_sample(cvals, doc, lon, lat)
                if hit is not None:
                    v = jround(hit)
            i = iy * cols + ix
            out[i] = 255 if v is None else v
            cb = doc["bbox"]
            cover[i] = 1 if (cb["minlon"] <= lon <= cb["maxlon"]
                             and cb["minlat"] <= lat <= cb["maxlat"]) else 0
    fill = bytearray(cols * rows)
    known = 0
    for i in range(len(out)):
        if out[i] == 255:
            if cover[i] == 1:
                fill[i] = 1
        else:
            known += 1
    if known:
        src = bytearray(out)
        dst = bytearray(out)
        for _ in range(FILL_PASSES):
            max_change = 0
            for yy in range(rows):
                for xx in range(cols):
                    i = yy * cols + xx
                    if fill[i] != 1:
                        dst[i] = src[i]
                        continue
                    s = n = 0
                    if xx > 0 and src[i - 1] != 255:
                        s += src[i - 1]; n += 1
                    if xx + 1 < cols and src[i + 1] != 255:
                        s += src[i + 1]; n += 1
                    if yy > 0 and src[i - cols] != 255:
                        s += src[i - cols]; n += 1
                    if yy + 1 < rows and src[i + cols] != 255:
                        s += src[i + cols]; n += 1
                    if n:
                        vv = jround(s / n)
                        prev = -1 if src[i] == 255 else src[i]
                        c = abs(vv - prev)
                        max_change = max(max_change, c)
                        dst[i] = vv
                    else:
                        dst[i] = 255
            src, dst = dst, src
            if max_change == 0:
                break
        out = src
    return bytes(out)


def speckle(out, cols, rows):
    n = 0
    for yy in range(1, rows - 1):
        for xx in range(1, cols - 1):
            i = yy * cols + xx
            if out[i] == 255 and all(
                    out[(yy + dy) * cols + xx + dx] != 255
                    for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                    if (dx, dy) != (0, 0)):
                n += 1
    return n


def grocery_points(view, margin=0.05):
    with open(os.path.join(OSM, "derived-grocery.json"), encoding="utf-8") as f:
        pts = json.load(f)
    return [(p["lon"], p["lat"]) for p in pts
            if view[0] - margin <= p["lon"] <= view[2] + margin
            and view[1] - margin <= p["lat"] <= view[3] + margin]


def parks_features(view, margin=0.05):
    with open(os.path.join(OSM, "derived-parks.json"), encoding="utf-8") as f:
        pts = json.load(f)
    with open(os.path.join(OSM, "park-areas.json"), encoding="utf-8") as f:
        areas = json.load(f)
    nominal = {"playground": 0.1, "garden": 0.15, "park": 2.0}
    near_p = []
    for p in pts:
        if view[0] - margin <= p["lon"] <= view[2] + margin \
           and view[1] - margin <= p["lat"] <= view[3] + margin:
            tags = p.get("tags") if isinstance(p.get("tags"), dict) else {}
            near_p.append((p["lon"], p["lat"],
                           nominal.get(tags.get("leisure"), 0.3)))
    near_a = [a for a in areas
              if a["b"][0] <= view[2] + margin and a["b"][2] >= view[0] - margin
              and a["b"][1] <= view[3] + margin and a["b"][3] >= view[1] - margin]
    return near_p, near_a


def euclid_grocery(lon, lat, pts):
    s = 0.0
    for plon, plat in pts:
        if abs(plon - lon) > 0.03 or abs(plat - lat) > 0.03:
            continue
        dd = hav_km(lon, lat, plon, plat)
        if dd <= 4 * SIGMA["grocery"] + 0.05:
            s += kernel(dd, SIGMA["grocery"])
    return saturate(s, HALF["grocery"])


def euclid_parks(lon, lat, near_p, near_a):
    s = 0.0
    for plon, plat, w in near_p:
        if abs(plon - lon) > 0.03 or abs(plat - lat) > 0.03:
            continue
        dd = hav_km(lon, lat, plon, plat)
        if dd <= 4 * SIGMA["parks"] + 0.05:
            s += w * kernel(dd, SIGMA["parks"])
    for a in near_a:
        b = a["b"]
        dc = 0.0 if (b[0] <= lon <= b[2] and b[1] <= lat <= b[3]) else hav_km(
            lon, lat, min(max(lon, b[0]), b[2]), min(max(lat, b[1]), b[3]))
        if dc <= 4 * SIGMA["parks"] + 0.05:
            s += a["a"] * kernel(dc, SIGMA["parks"])
    return saturate(s, HALF["parks"])


def test_masters_wire_valid():
    for layer in LAYERS:
        doc, cvals = load_county(layer)
        meta, mvals = load_metro(layer)
        assert len(cvals) == doc["cols"] * doc["rows"] > 0
        assert len(mvals) == meta["cols"] * meta["rows"] > 0
        assert set(cvals) | set(mvals) <= set(range(101)) | {255}
        # county + metro share one calibration per layer (stale-master guard)
        for k in ("half", "sigma", "per", "cap", "unknown", "dtype"):
            assert doc[k] == meta[k], (layer, k)


def test_dense_tallinn_no_speckle_all_layers():
    for layer in LAYERS:
        out = serve(layer, TALLINN_DENSE, 128, 64)
        assert speckle(out, 128, 64) == 0, layer
        assert sum(1 for v in out if v == 255) == 0, layer


def test_kangru_grocery_residuals_faithful():
    view, cols, rows = KANGRU_RURAL, 128, 64
    out = serve("grocery", view, cols, rows)
    n255 = sum(1 for v in out if v == 255)
    assert n255 > 0  # the red patch under test exists
    pts = grocery_points(view)
    worst = 0.0
    for i in range(len(out)):
        if out[i] != 255:
            continue
        lon = view[0] + ((i % cols) + 0.5) / cols * (view[2] - view[0])
        lat = view[1] + ((i // cols) + 0.5) / rows * (view[3] - view[1])
        sc = euclid_grocery(lon, lat, pts)
        worst = max(worst, sc)
        assert sc < 10, (lon, lat, sc)
    assert worst < 3  # renders red either way: faithful no-data


def test_kangru_parks_no_highvalue_unknown():
    view, cols, rows = KANGRU_RURAL, 128, 64
    out = serve("parks", view, cols, rows)
    assert sum(1 for v in out if v == 255) > 0
    near_p, near_a = parks_features(view)
    for i in range(len(out)):
        if out[i] != 255:
            continue
        lon = view[0] + ((i % cols) + 0.5) / cols * (view[2] - view[0])
        lat = view[1] + ((i // cols) + 0.5) / rows * (view[3] - view[1])
        assert euclid_parks(lon, lat, near_p, near_a) < 10, (lon, lat)


def _client_grid(view):
    spanM = (view[2] - view[0]) * 57300
    latM = (view[3] - view[1]) * 110570
    cols = min(512, max(64, round(spanM / 12)))
    rows = min(512, max(64, round(latM / 12)))
    padLon = (view[2] - view[0]) * 0.2
    padLat = (view[3] - view[1]) * 0.2
    return ((view[0] - padLon, view[1] - padLat,
             view[2] + padLon, view[3] + padLat), cols, rows)


def test_kristiine_inview_clean_client_res():
    view, cols, rows = _client_grid(KRISTIINE)
    for layer in ("transit", "parks", "grocery"):
        out = serve(layer, view, cols, rows)
        n_in = 0
        for i in range(len(out)):
            if out[i] != 255:
                continue
            lon = view[0] + ((i % cols) + 0.5) / cols * (view[2] - view[0])
            lat = view[1] + ((i // cols) + 0.5) / rows * (view[3] - view[1])
            if KRISTIINE[0] <= lon <= KRISTIINE[2] \
               and KRISTIINE[1] <= lat <= KRISTIINE[3]:
                n_in += 1
        assert n_in == 0, (layer, n_in)


def test_live_matches_replica_kangru_grocery():
    base = os.environ.get("HF_LIVE_URL")
    if not base:
        pytest.skip("HF_LIVE_URL unset (explicitly-flagged integration test)")
    view, cols, rows = KANGRU_RURAL, 128, 64
    q = (f"minlon={view[0]}&minlat={view[1]}&maxlon={view[2]}&maxlat={view[3]}"
         f"&cols={cols}&rows={rows}")
    with urllib.request.urlopen(f"{base}/api/layers/grocery/window?{q}",
                                timeout=120) as r:
        live = base64.b64decode(json.load(r)["data"])
    assert bytes(live) == serve("grocery", view, cols, rows)
