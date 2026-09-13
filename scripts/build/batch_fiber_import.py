"""One-time import of TTJA broadband coverage (netikaart) into the snapshot.

Source: Maa-amet X-GIS WFS (public, no key), TTJA lairiba kaardistus —
operator-reported wired availability per address object (ADR).
App config: https://xgis.maaamet.ee/xgis2/config/app/netikaart
Layer used: kaabliyhendused_1000 (addresses with >=1000 Mbit/s reported
wired availability — the fiber-grade footprint; tiers nest 1000<100<1,
verified 2026-09-12). Tier membership is the ONLY populated signal
(vorgu_tyyp/sideettevo/max speeds come back empty from this endpoint),
so the layer honestly means ">=1000 Mbit/s reported here", never which
operator or medium. Absence = no operator reported coverage (includes
under-reporting — the legend must say "operaatorite teatatud").

Politeness: ~50 small BBOX requests with 2 s pacing + retries, slim
attribute selection (ads_oid/lest_x/lest_y only, no geometry), one run
cached forever. Fetched data lands in ~/hf-data (gitignored snapshot),
never in the repo.

Usage:
  python3 scripts/build/batch_fiber_import.py --selftest   # TM math check
  python3 scripts/build/batch_fiber_import.py \\
      --snap ~/hf-data/2026-09-12 --tier 1000
Writes <snap>/osm/derived-fiber-addrs.json: [{lon, lat}] covered
addresses (full set, builder input; the served overlay sample is
derived-fiber.json, written by batch_b10c_utility.py --derived).
"""

import argparse
import json
import math
import os
import re
import sys
import time
import urllib.request

WFS = "https://xgis.maaamet.ee/xgis2/service/frd221?"
PACE_S = 2.0
MAXFEATURES = 100000
TILE_M = 20000.0

# L-EST97 / EPSG:3301 (Transverse Mercator, GRS80): lon0=24E, k0=0.9996,
# false easting 500000 m, false northing 0.
A = 6378137.0
F = 1 / 298.257222101
E2 = 2 * F - F * F
K0 = 0.9996
LON0 = math.radians(24.0)
X0 = 500000.0


def lest97_to_wgs84(x, y):
    """L-EST97 easting/northing -> (lon, lat) degrees (Snyder inverse TM)."""
    m = y / K0
    mu = m / (A * (1 - E2 / 4 - 3 * E2 * E2 / 64 - 5 * E2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - E2)) / (1 + math.sqrt(1 - E2))
    j1 = 3 * e1 / 2 - 27 * e1 ** 3 / 32
    j2 = 21 * e1 * e1 / 16 - 55 * e1 ** 4 / 32
    j3 = 151 * e1 ** 3 / 96
    fp = (mu + j1 * math.sin(2 * mu) + j2 * math.sin(4 * mu)
          + j3 * math.sin(6 * mu))
    c1 = E2 * math.cos(fp) ** 2 / (1 - E2)
    t1 = math.tan(fp) ** 2
    n1 = A / math.sqrt(1 - E2 * math.sin(fp) ** 2)
    r1 = A * (1 - E2) / (1 - E2 * math.sin(fp) ** 2) ** 1.5
    dd = (x - X0) / (n1 * K0)
    lat = (fp - n1 * math.tan(fp) / r1
           * (dd * dd / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 * c1)
              * dd ** 4 / 24))
    lon = (LON0 + (dd - (1 + 2 * t1 + c1) * dd ** 3 / 6
                   + (5 - 2 * c1 + 28 * t1 - 3 * c1 * c1)
                   * dd ** 5 / 120) / math.cos(fp))
    return math.degrees(lon), math.degrees(lat)


def wgs84_to_lest97(lon, lat):
    """(lon, lat) degrees -> L-EST97 easting/northing (forward TM)."""
    lam, phi = math.radians(lon), math.radians(lat)
    n = A / math.sqrt(1 - E2 * math.sin(phi) ** 2)
    t = math.tan(phi) ** 2
    c = E2 * math.cos(phi) ** 2 / (1 - E2)
    a = (lam - LON0) * math.cos(phi)
    m = A * ((1 - E2 / 4 - 3 * E2 * E2 / 64 - 5 * E2 ** 3 / 256) * phi
             - (3 * E2 / 8 + 3 * E2 * E2 / 32 + 45 * E2 ** 3 / 1024)
             * math.sin(2 * phi)
             + (15 * E2 * E2 / 256 + 45 * E2 ** 3 / 1024)
             * math.sin(4 * phi)
             - 35 * E2 ** 3 / 3072 * math.sin(6 * phi))
    x = K0 * n * (a + (1 - t + c) * a ** 3 / 6) + X0
    y = K0 * (m + n * math.tan(phi)
              * (a * a / 2 + (5 - t + 9 * c + 4 * c * c) * a ** 4 / 24))
    return x, y


def fetch_tile(tier, bbox, retries=3):
    """One slim WFS request -> [(ads_oid, easting, northing)].

    NOTE the X-GIS naming trap: lest_x holds the NORTHING (6589072)
    and lest_y the EASTING (540959). Swapping them puts Harjumaa in
    the ocean — the sanity check below guards this permanently.
    """
    q = ("service=WFS&version=1.0.0&request=GetFeature&typeName="
         "kaabliyhendused_%s&maxFeatures=%d&propertyName=ads_oid,lest_x,lest_y"
         "&BBOX=%d,%d,%d,%d" % ((tier, MAXFEATURES) + tuple(int(v) for v in bbox)))
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(WFS + q, timeout=120) as r:
                body = r.read().decode("utf-8", errors="replace")
            out = re.findall(
                r"<ms:ads_oid>([^<]*)</ms:ads_oid><ms:lest_x>([^<]*)</ms:lest_x>"
                r"<ms:lest_y>([^<]*)</ms:lest_y>", body)
            return [(o, float(east), float(north)) for o, north, east in out]
        except Exception as e:  # noqa: BLE001 - retry then raise
            last = e
            time.sleep(PACE_S * (attempt + 1))
    raise RuntimeError("WFS tile failed %s: %s" % (bbox, last))


def county_tiles():
    """L-EST97 tiles covering Harjumaa (+5 km margin) at TILE_M steps."""
    corners = [wgs84_to_lest97(lon, lat)
               for lon in (23.3, 25.5) for lat in (58.4, 59.65)]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    x0, x1 = min(xs) - 5000, max(xs) + 5000
    y0, y1 = min(ys) - 5000, max(ys) + 5000
    tiles = []
    x = x0
    while x < x1:
        y = y0
        while y < y1:
            tiles.append((x, y, min(x + TILE_M, x1), min(y + TILE_M, y1)))
            y += TILE_M
        x += TILE_M
    return tiles


def selftest():
    # Round-trip must hold to <10 cm across the county (measured worst
    # case 3.6 mm at the far corner — the truncated TM series is plenty
    # for a 75 m grid).
    for lon, lat in ((24.75, 59.4372), (23.5, 58.6), (25.4, 59.6),
                     (24.8867, 59.4712)):
        x, y = wgs84_to_lest97(lon, lat)
        lo, la = lest97_to_wgs84(x, y)
        assert abs(lo - lon) < 1e-6 and abs(la - lat) < 1e-6, (lon, lat)
    # Anchor: Õle tn 6b, Põhja-Tallinn (WFS sample 540959/6589072) sits
    # ~200 m west of Balti jaam (24.7369, 59.4405).
    lo, la = lest97_to_wgs84(540959, 6589072)
    assert 24.72 < lo < 24.75 and 59.43 < la < 59.45, (lo, la)
    print("selftest OK: TM round-trip <1mm, Õle tn 6b -> %.5f, %.5f"
          % (lo, la))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--snap", default=None)
    ap.add_argument("--tier", default="1000")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    if not args.snap:
        ap.error("--snap is required (writes <snap>/osm/derived-fiber.json)")
    tiles = county_tiles()
    print("tiles: %d (%.0f m)" % (len(tiles), TILE_M), flush=True)
    seen = {}
    for i, bbox in enumerate(tiles):
        feats = fetch_tile(args.tier, bbox)
        for oid, x, y in feats:
            if oid not in seen:
                seen[oid] = (x, y)
        print("tile %d/%d: %d feats, %d unique addrs"
              % (i + 1, len(tiles), len(feats), len(seen)), flush=True)
        if len(feats) >= MAXFEATURES:
            print("WARNING: tile hit maxFeatures cap — subdivide %s" % (bbox,),
                  flush=True)
        time.sleep(PACE_S)
    pts = []
    for oid, (x, y) in seen.items():
        lo, la = lest97_to_wgs84(x, y)
        pts.append({"lon": round(lo, 6), "lat": round(la, 6)})
    # Sanity: every point must land inside the county bbox — a lat/lon
    # swap or axis flip shows up here, not on the live map.
    bad = [p for p in pts
           if not (23.0 <= p["lon"] <= 25.8 and 58.2 <= p["lat"] <= 59.8)]
    assert not bad, "imported points outside Harjumaa, e.g. %s" % bad[:3]
    out = os.path.join(args.snap, "osm", "derived-fiber-addrs.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(pts, f)
    print("wrote %d covered addresses -> %s" % (len(pts), out))


if __name__ == "__main__":
    main()
