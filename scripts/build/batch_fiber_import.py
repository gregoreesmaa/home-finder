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
  python3 scripts/build/batch_fiber_import.py --selftest   # LCC pin check
  python3 scripts/build/batch_fiber_import.py \\
      --snap ~/hf-data/2026-09-12 --tier 1000
Writes <snap>/osm/derived-fiber-addrs.json: [{lon, lat}] covered
addresses (full set, builder input; the served overlay sample is
derived-fiber.json, written by batch_b10c_utility.py --derived).
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request

WFS = "https://xgis.maaamet.ee/xgis2/service/frd221?"
PACE_S = 2.0
MAXFEATURES = 100000
TILE_M = 20000.0

#: True L-EST97 = Lambert Conformal Conic 2SP (EPSG:3301), shared
#: implementation in batch_canopy (#648 retired the legacy Transverse
#: Mercator twins, which disagreed with LCC by 20-85 m across Harju).
#: NOTE the arg-order trap: lest97_to_wgs84 takes (easting, northing)
#: like batch_canopy.lest97_to_lonlat -- most other batch_* twins take
#: (northing, easting). Call sites below are unchanged.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from batch_canopy import lest97_to_lonlat, lonlat_to_lest97  # noqa: E402


def lest97_to_wgs84(x, y):
    """L-EST97 easting/northing -> (lon, lat) degrees (true LCC, #654)."""
    return lest97_to_lonlat(x, y)


def wgs84_to_lest97(lon, lat):
    """(lon, lat) degrees -> L-EST97 easting/northing (true LCC, #654)."""
    return lonlat_to_lest97(lon, lat)


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
    # Absolute LCC pins (EPSG:3301 definition, #648 precedent) -- the
    # old selftest round-tripped TM against TM, which is circular and
    # passes under either projection.
    for lon, lat in ((24.75, 59.4372), (23.5, 58.6), (25.4, 59.6),
                     (24.8867, 59.4712)):
        x, y = wgs84_to_lest97(lon, lat)
        lo, la = lest97_to_wgs84(x, y)
        assert abs(lo - lon) < 1e-6 and abs(la - lat) < 1e-6, (lon, lat)
    # Origin-exact + Tallinn discriminator (absolute, non-circular).
    e, n = wgs84_to_lest97(24.0, 57.5175538888889)
    assert abs(e - 500000.0) < 1e-6 and abs(n - 6375000.0) < 1e-6, (e, n)
    e, n = wgs84_to_lest97(24.75, 59.44)
    assert abs(e - 542555.36) < 0.01 and abs(n - 6589368.19) < 0.01, (e, n)
    # Anchor: Õle tn 6b, Põhja-Tallinn (WFS sample 540959/6589072) sits
    # ~200 m west of Balti jaam (24.7369, 59.4405); LCC truth
    # (retired TM read 24.72213, 59.43822 -- ~80 m off).
    lo, la = lest97_to_wgs84(540959, 6589072)
    assert abs(lo - 24.72181) < 1e-4 and abs(la - 59.43750) < 1e-4, (lo, la)
    print("selftest OK: LCC origin-exact + Tallinn pin, Õle tn 6b -> "
          "%.5f, %.5f" % (lo, la))


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
