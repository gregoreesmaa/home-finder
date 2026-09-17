"""KPO restriction-zone sidecar builder (issue #626): WFS zones -> map polygons.

Stdlib only. Offline, snapshot-only (NO network in build): the KMA
``kmakitsendused`` WFS harvest is a polite one-off pull (custom UA,
paced, 429 stops the run -- AGENTS.md 7.4) into per-window raw GML
caches; this script parses the caches into the sidecar. Transport
errors are never cached as data; a missing/unreadable input writes
NOTHING (unknown, never partial).

WHY PARCEL WINDOWS (issue #626): a full Harju pull is infeasible --
``elekter`` alone matches ~479k features in the Harju window. The
sidecar covers the known-parcel windows (snapshot
``maa/parcel-areas.json``): one multi-family GetFeature per parcel
bbox + margin, subdividing on cap-hits (maaparcel-tile precedent
#520). Coverage is honestly labelled (parcel windows, never the
whole county); outside every polygon stays NULL (never clean
title). Bulk work converges over runs: fresh caches win, no
re-request.

LICENCE (gate cleared 2026-09-17, issue #626): the service Abstract
(Maa- ja Ruumiamet public WFS) publishes data under CC-BY 4.0
(https://creativecommons.org/licenses/by/4.0/) unless a layer sets
separate conditions -- a re-probe found NO per-layer conditions, so
the default covers all 18 families. Attribution rides the sidecar +
legend. No login/session flow, no scraped publications, no personal
data (AGENTS.md section 5).

Geometry: members carry EPSG:3301 posLists in (N, E) axis order;
rings project via the TRUE LCC twins from batch_canopy (issue #648
-- never Transverse Mercator). Exterior rings only (documented:
zones are influence areas; holes are negligible for a warning
overlay, and inventing even-odd fills from uninspected interiors
would be fake precision).

Usage:
  python3 scripts/build/batch_kpo.py \\
      --cache-dir /tmp/hf-626-cache --snap ~/hf-data/2026-09-12
  (harvest writes raw GML per parcel window; build assembles
  kpo/kpo-areas.json. --harvest-only / --merge-only split the steps.)
"""

import argparse
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile  # noqa: F401  (kept for harvest-zip parity with siblings)
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from batch_canopy import lest97_to_lonlat_lcc  # noqa: E402  (true LCC, #648)

#: KMA restriction-zone WFS (CC-BY 4.0 default, see module docstring).
KPO_WFS = "https://gsavalik.envir.ee/geoserver/kmakitsendused/wfs"

#: The 18 public zone families (kma_avalik_*), probed 1 row each 2026-09-17.
FAMILIES = [
    "asjaoigus", "elekter", "gaas", "geodeesia", "kaugkyte", "kemikaal",
    "looduskaitse", "maaparandus", "muinsuskaitse", "planeering",
    "reostusoht", "ressurss", "riigikaitse", "side", "sundvaldus",
    "transport", "veekogu", "veevarustus",
]

#: Publisher attribution (CC-BY 4.0 default; stamped in stats, not rows).
ATTRIBUTION = ("Maa- ja Ruumiamet kmakitsendused WFS (CC-BY 4.0, "
               "allikas: Majandus- ja Kommunikatsiooniministeerium)")

#: Harvest politeness (AGENTS.md 7.4): one GET per window, paced.
UA = "home-finder kpo-harvest (paced, resume-via-cache, 429 stops run)"
PACE_S = 3.0
PER_REQUEST_TIMEOUT = 60

#: Window cap: a window returning this many members subdivides
#: (never raise the cap -- dense city tiles split down to MAXDEPTH).
WINDOW_COUNT = 100
MAXDEPTH = 3

#: Parcel bbox margin (degrees) so zones clipping the parcel edge join.
PARCEL_MARGIN_DEG = 0.002

#: Sidecar filename inside the snapshot dir.
SIDECAR_PATH = os.path.join("kpo", "kpo-areas.json")


class _StopSignal(RuntimeError):
    """HTTP 429 back-off signal: stop the run, rerun resumes via cache."""


def _get(url: str) -> bytes:
    """One polite GET (429 -> _StopSignal, never cached as data)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=PER_REQUEST_TIMEOUT) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise _StopSignal("HTTP 429 -- stop signal")
        raise RuntimeError("HTTP %d on %s" % (exc.code, url))


def _window_key(minlon: float, minlat: float,
                maxlon: float, maxlat: float) -> str:
    return "w_%.5f_%.5f_%.5f_%.5f" % (minlon, minlat, maxlon, maxlat)


def _fetch_window(cache_dir: str, bbox: Tuple[float, float, float, float],
                  depth: int = 0) -> List[str]:
    """Harvest one lon/lat window (all families, one GET), subdividing on
    cap-hits. Returns cache paths holding raw GML. Cached windows win
    (no request). 429 stops the whole run via _StopSignal."""
    minlon, minlat, maxlon, maxlat = bbox
    key = _window_key(minlon, minlat, maxlon, maxlat)
    path = os.path.join(cache_dir, key + ".gml")
    if os.path.exists(path):
        return [path]
    types = ",".join("kmakitsendused:kma_avalik_%s" % f for f in FAMILIES)
    # WFS 2.0 + EPSG:4326 URN wants lat,lon axis order in bbox.
    qs = urllib.parse.urlencode({
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeName": types, "count": WINDOW_COUNT,
        "bbox": "%.5f,%.5f,%.5f,%.5f,urn:ogc:def:crs:EPSG:4326"
                % (minlat, minlon, maxlat, maxlon),
    })
    raw = _get(KPO_WFS + "?" + qs)
    time.sleep(PACE_S)
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        # A corrupt window fails LOUD (exit 1, writes nothing): silent
        # drops would let the "known-parcel windows" coverage claim
        # quietly overstate. Caught in main like every error path.
        raise ValueError("unparseable GML for window %s" % key)
    members = root.findall(
        "{http://www.opengis.net/wfs/2.0}member")
    if len(members) >= WINDOW_COUNT and depth < MAXDEPTH:
        # Cap-hit: subdivide (dense tiles split, never raise the cap).
        midlon, midlat = (minlon + maxlon) / 2, (minlat + maxlat) / 2
        out = []
        for quad in ((minlon, minlat, midlon, midlat),
                     (midlon, minlat, maxlon, midlat),
                     (minlon, midlat, midlon, maxlat),
                     (midlon, midlat, maxlon, maxlat)):
            out.extend(_fetch_window(cache_dir, quad, depth + 1))
        return out
    os.makedirs(cache_dir, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(raw)
    return [path]


def parse_members(xml_text: str) -> List[dict]:
    """Raw WFS members -> [{family, attrs, rings_3301}] (pure).

    Exterior posList rings only (see module docstring); (N, E) axis
    order per srsName EPSG:3301. Malformed members are skipped, never
    faked.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    out = []
    wfs_member = "{http://www.opengis.net/wfs/2.0}member"
    # Multi-typeName responses nest one FeatureCollection per family
    # inside an outer member: walk ALL descendant members and keep the
    # ones whose child is a kma_avalik_* feature (wrappers skip).
    for member in root.iter(wfs_member):
        if len(member) == 0:
            continue
        feat = member[0]
        tag = feat.tag
        fam = tag.split("kma_avalik_")[-1] if "kma_avalik_" in tag else ""
        if fam not in FAMILIES:
            continue

        def text(local: str) -> str:
            el = feat.find("kmakitsendused:%s" % local,
                           {"kmakitsendused": "kpois_kma"})
            return (el.text or "").strip() if el is not None and el.text else ""

        rings = []
        # Walk with ancestry: exterior posLists only (interiors skipped,
        # documented in the module docstring).
        stack = [(feat, False)]
        while stack:
            el, interior = stack.pop()
            for child in list(el):
                tag = child.tag
                child_interior = interior or "nterior" in tag
                if tag.endswith("}posList"):
                    if child_interior:
                        continue
                    nums = re.findall(r"[-+]?\d+(?:\.\d+)?",
                                      child.text or "")
                    pts = []
                    for i in range(0, len(nums) - 1, 2):
                        try:
                            n, e = float(nums[i]), float(nums[i + 1])
                        except ValueError:
                            continue
                        pts.append((e, n))
                    if len(pts) >= 4:
                        rings.append(pts)
                else:
                    stack.append((child, child_interior))
        if not rings:
            continue
        out.append({
            "family": fam,
            "attrs": {
                "nimi": text("nimi"),
                "voond": text("voond_liik_id_vaartus") or text("voond_liik_id"),
                "reegel": text("reegel"),
                "klass": text("klass"),
            },
            "rings_3301": rings,
        })
    return out


def project_ring_lonlat(ring_3301: List[Tuple[float, float]]
                        ) -> List[List[float]]:
    """One 3301 (easting, northing) ring -> [[lon, lat]] (pure).

    TRUE LCC via batch_canopy (issue #648 -- never TM). Vertices that
    fail project out; <4 survivors read as unusable (callers skip).
    """
    out = []
    for easting, northing in ring_3301:
        try:
            lon, lat = lest97_to_lonlat_lcc(float(easting),
                                            float(northing))
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(lon) and math.isfinite(lat)):
            continue
        out.append([lon, lat])
    return out


def to_sidecar(members: List[dict]) -> List[dict]:
    """Parsed members -> sidecar rows (lon/lat rings + box + attrs).

    Malformed rows are skipped, never faked. Rings with <4 projected
    vertices drop (a broken polygon must not flag a parcel).
    """
    rows = []
    for m in members or []:
        if not isinstance(m, dict):
            continue
        attrs = m.get("attrs") or {}
        rings = []
        for ring in m.get("rings_3301") or []:
            proj = project_ring_lonlat(ring)
            if len(proj) >= 4:
                rings.append(proj)
        if not rings:
            continue
        los = [p[0] for ring in rings for p in ring]
        las = [p[1] for ring in rings for p in ring]
        rows.append({
            "family": m.get("family", "?"),
            "nimi": str(attrs.get("nimi") or "tundmatu"),
            "voond": str(attrs.get("voond") or "tundmatu"),
            "reegel": str(attrs.get("reegel") or ""),
            "b": [min(los), min(las), max(los), max(las)],
            "r": rings,
        })
    return rows


def parcel_windows(parcel_doc: dict) -> List[dict]:
    """Snapshot parcels -> [{tunnus, bbox}] query windows (pure)."""
    out = []
    for p in (parcel_doc or {}).get("parcels") or []:
        tunnus = (p or {}).get("tunnus")
        b = (p or {}).get("b")
        if not tunnus or not isinstance(b, list) or len(b) != 4:
            continue
        try:
            minlon, minlat, maxlon, maxlat = (float(v) for v in b)
        except (TypeError, ValueError):
            continue
        out.append({
            "tunnus": str(tunnus),
            "bbox": (minlon - PARCEL_MARGIN_DEG, minlat - PARCEL_MARGIN_DEG,
                     maxlon + PARCEL_MARGIN_DEG, maxlat + PARCEL_MARGIN_DEG),
        })
    return out


def _ring_bbox(rings: List[List[List[float]]]
               ) -> Optional[Tuple[float, float, float, float]]:
    xs = [p[0] for ring in rings for p in ring]
    ys = [p[1] for ring in rings for p in ring]
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def kataster_proof(parcels: List[dict], rows: List[dict],
                   parcel_rings: Optional[Dict[str, list]] = None) -> dict:
    """Join every parcel AREA against sidecar rows (pure).

    Bidirectional vertex containment (parcel verts in zones + zone
    verts in parcels) behind a bbox prefilter -- a centroid-only join
    underclaims (an easement crossing a parcel corner misses the
    centroid), and underclaiming would fail the >=20-parcel bar
    artificially. Returns {tunnus: [voond...]} hits + totals: the
    >=20-parcel live proof (kataster tunnus) on live rows, counted
    honestly even when some parcels stay empty.
    """
    scoring_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "..", "services", "scoring")
    sys.path.insert(0, scoring_dir)
    try:
        from dims_p4_kitsendus import point_in_polygon
    finally:
        # pop(0) restores OUR entry: bare pop() eats a stdlib entry
        # off the end per call, eventually breaking lazy stdlib
        # imports suite-wide (datetime.strptime -> _strptime).
        if sys.path and sys.path[0] == scoring_dir:
            del sys.path[0]
    parcel_rings = parcel_rings or {}
    # Zone bboxes once (the ray-casts run only on bbox overlap).
    zb = []
    for r in rows:
        bb = _ring_bbox(r.get("r") or [])
        if bb is not None:
            zb.append((r, bb))
    hits: Dict[str, List[str]] = {}
    for p in parcels:
        prings = parcel_rings.get(p["tunnus"], [])
        if not prings:
            # No ring on file: fall back to the window bbox corners
            # (honest subset -- a corner hit still proves the join).
            b = p["bbox"]
            prings = [[[b[0], b[1]], [b[2], b[1]],
                       [b[2], b[3]], [b[0], b[3]]]]
        pb = _ring_bbox(prings)
        if pb is None:
            continue
        found = set()
        for r, (x0, y0, x1, y1) in zb:
            if x1 < pb[0] or x0 > pb[2] or y1 < pb[1] or y0 > pb[3]:
                continue
            hit = any(point_in_polygon(x, y, zr)
                      for pring in prings for x, y in pring
                      for zr in r["r"])
            if not hit:
                hit = any(point_in_polygon(x, y, pring)
                          for zr in r["r"] for x, y in zr
                          for pring in prings)
            if hit:
                found.add(str(r.get("voond", "?")))
        if found:
            hits[p["tunnus"]] = sorted(found)
    return {"hits": hits, "parcels_hit": len(hits),
            "parcels_total": len(parcels)}


def build(cache_dir: str, parcel_doc: dict) -> dict:
    """Cached GML windows + parcels -> sidecar doc (offline).

    Returns {"areas", "stats"}; stats carry the honest coverage
    (parcel windows, per-family zone counts, parcel hit tally).
    """
    members = []
    for fn in sorted(os.listdir(cache_dir) if os.path.isdir(cache_dir) else []):
        if not fn.endswith(".gml"):
            continue
        with open(os.path.join(cache_dir, fn), encoding="utf-8",
                  errors="replace") as fh:
            members.extend(parse_members(fh.read()))
    rows = to_sidecar(members)
    parcels = parcel_windows(parcel_doc)
    rings = {str(p.get("tunnus")): (p.get("r") or [])
             for p in (parcel_doc or {}).get("parcels") or []}
    proof = kataster_proof(parcels, rows, rings)
    fam_counts: Dict[str, int] = {}
    for r in rows:
        fam_counts[r["family"]] = fam_counts.get(r["family"], 0) + 1
    return {
        "attribution": ATTRIBUTION,
        "coverage": ("KPO zones in known-parcel windows "
                     "(maa/parcel-areas.json + margin, never the whole "
                     "county); outside every polygon stays NULL"),
        "areas": rows,
        "stats": {
            "zones": len(rows),
            "families": fam_counts,
            "parcels_total": proof["parcels_total"],
            "parcels_hit": proof["parcels_hit"],
        },
        "proof": proof["hits"],
    }


def harvest(cache_dir: str, parcel_doc: dict) -> List[str]:
    """Pull every parcel window (cached wins, 429 stops). Returns paths."""
    os.makedirs(cache_dir, exist_ok=True)
    paths = []
    for p in parcel_windows(parcel_doc):
        paths.extend(_fetch_window(cache_dir, p["bbox"]))
    return paths


def main(argv=None) -> int:
    """Harvest (polite) and/or build the KPO sidecar. 0 ok, 1 failed
    (writes NOTHING), 2 stopped on 429 (rerun resumes via cache)."""
    ap = argparse.ArgumentParser(description="Build the KPO sidecar.")
    ap.add_argument("--cache-dir", required=True,
                    help="Dir with per-window raw GML caches.")
    ap.add_argument("--snap", required=True, help="Snapshot dir.")
    ap.add_argument("--parcels", default=None,
                    help="parcel-areas.json (default: <snap>/maa/).")
    ap.add_argument("--harvest-only", action="store_true")
    ap.add_argument("--merge-only", action="store_true")
    args = ap.parse_args(argv)
    try:
        parcels_path = args.parcels or os.path.join(
            args.snap, "maa", "parcel-areas.json")
        with open(parcels_path, encoding="utf-8") as fh:
            parcel_doc = json.load(fh)
        if not args.merge_only:
            harvest(args.cache_dir, parcel_doc)
        if args.harvest_only:
            print("harvest ok (merge skipped)")
            return 0
        doc = build(args.cache_dir, parcel_doc)
    except _StopSignal as exc:
        print("harvest stopped (%s) -- writing NOTHING" % exc)
        return 2
    except (RuntimeError, OSError, ValueError, ET.ParseError,
            zipfile.BadZipFile, KeyError) as exc:
        print("harvest failed (%s) -- writing NOTHING" % exc)
        return 1
    if not doc["areas"]:
        print("zero zones -- writing NOTHING")
        return 1
    outdir = os.path.join(args.snap, "kpo")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "kpo-areas.json"), "w") as fh:
        json.dump(doc, fh)
    print("ok=True zones=%d parcels_hit=%d/%d"
          % (doc["stats"]["zones"], doc["stats"]["parcels_hit"],
             doc["stats"]["parcels_total"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
