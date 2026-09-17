"""Strategic-noise overlay harvester + sidecar builder (issue #625).

Polite tiled WFS harvest of the two 2022 strategic summary legs
(Lden + Lnight, Tallinn + Tartu + main roads) into snapshot
``<snap>/noise/noise-areas.json`` consumed by /api/layers/noise/areas.
Stdlib only (urllib + xml.etree). Harvest converges over runs:
per-cell raw XML cache under ``<snap>/noise/cache/<leg>/`` is
resume-aware (existing non-empty cells are skipped), pulls are paced
(default 3 s), custom UA, and HTTP 429 (or any transport error) stops
the run with nonzero exit — rerun later to continue. The build step is
fully offline (parses the cache only).

SCOPE: measured-map overlay bands, NULL-empty outside. Each sidecar
row carries leg (Lden/Lnight) + band lower bound dB + simplified
lon/lat rings. The per-listing binding leg (min wins) is the SCORER's
job (services/scoring/dims_p4_noisemap.py) — the map paints bands,
never scores. Legend states modeled-not-measured, always.

HONESTY (load-bearing): 3301 is Lambert Conformal Conic 2SP
(EPSG:3301 — true LCC lives in batch_canopy, issue #648; this module
imports it, never the legacy TM). WFS 2.0 serves EPSG:3301 in
NORTHING,EASTING axis order (verified 2026-09-17: BBOX + posList both
N,E) — the parser swaps to (E,N) once, loudly. Rings are
Douglas-Peucker simplified at 5 m in metric 3301 BEFORE projection.
Polygons outside Harju+2 km margin are dropped; outside every polygon
is NULL (never quiet). A missing/unreadable cache builds NOTHING.

Usage:
  python3 scripts/build/batch_noisemap.py harvest --snap ~/hf-data/2026-09-12 [--pace 3] [--cell-km 10]
  python3 scripts/build/batch_noisemap.py build --snap ~/hf-data/2026-09-12
"""

import argparse
import hashlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from batch_canopy import lest97_to_lonlat_lcc  # noqa: E402  (true LCC, NOT legacy TM)

#: Harvested legs: (sidecar leg name, WFS typeName).
LEGS = (
    ("Lden", "ms:myra22_strat_sum_oopaev"),
    ("Lnight", "ms:myra22_strat_sum_oo"),
)

WFS_BASE = "https://teenus.maaamet.ee/ows/myrakaart"
UA = "home-finder-dev/0.1 (polite tiled harvest; issue #625)"

#: Keep window: Harju + 2 km margin (metres, 3301 E,N) so map bands
#: stay complete at the county edge.
KEEP_BBOX = (478000.0, 6533000.0, 614000.0, 6622000.0)

#: Ring simplification tolerance (metres, in 3301 before projection).
DP_TOL_M = 5.0

#: Sidecar filename inside the snapshot dir.
SIDECAR_PATH = os.path.join("noise", "noise-areas.json")

#: Publisher attribution (service self-declares Fees none +
#: AccessConstraints NONE; no data licence stated anywhere — owner
#: decision 2026-09-17: usable without a licence).
ATTRIBUTION = "Maa- ja Ruumiamet strateegilised mürakaardid 2022 (WFS myrakaart)"

#: Harvest vintage (modelled year).
VINTAGE = "2022"

NS = {
    "wfs": "http://www.opengis.net/wfs/2.0",
    "gml": "http://www.opengis.net/gml/3.2",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
    "ows": "http://www.opengis.net/ows/1.1",
}


def _cell_boxes(cell_km: float) -> List[Tuple[int, Tuple[float, float, float, float]]]:
    """Non-overlapping grid cells over KEEP_BBOX; returns (idx, (E0,N0,E1,N1))."""
    emin, nmin, emax, nmax = KEEP_BBOX
    step = cell_km * 1000.0
    boxes = []
    idx = 0
    n0 = nmin
    while n0 < nmax:
        e0 = emin
        while e0 < emax:
            boxes.append((idx, (e0, n0, min(e0 + step, emax), min(n0 + step, nmax))))
            idx += 1
            e0 += step
        n0 += step
    return boxes


def _wfs_get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 429:
                raise RuntimeError("HTTP 429 — stop signal, rerun later")
            return resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise RuntimeError("HTTP 429 — stop signal, rerun later")
        raise RuntimeError("HTTP %d on %s" % (exc.code, url))


def harvest(snap: str, pace: float, cell_km: float) -> int:
    """Pull every (leg, cell) missing from the cache. Returns 0 when complete."""
    cachedir = os.path.join(snap, "noise", "cache")
    total = 0
    missing = 0
    for leg, typename in LEGS:
        legdir = os.path.join(cachedir, leg)
        os.makedirs(legdir, exist_ok=True)
        for idx, (e0, n0, e1, n1) in _cell_boxes(cell_km):
            total += 1
            path = os.path.join(legdir, "cell-%03d.xml" % idx)
            if os.path.exists(path) and os.path.getsize(path) > 0:
                continue
            missing += 1
            # N,E axis order for EPSG:3301 under WFS 2.0 (verified).
            bbox = "%f,%f,%f,%f,urn:ogc:def:crs:EPSG::3301" % (n0, e0, n1, e1)
            qs = urllib.parse.urlencode({
                "service": "WFS", "version": "2.0.0", "request": "GetFeature",
                "typeName": typename, "BBOX": bbox,
                "srsName": "urn:ogc:def:crs:EPSG::3301",
            })
            print("get %s cell %03d ..." % (leg, idx), flush=True)
            try:
                raw = _wfs_get(WFS_BASE + "?" + qs)
            except RuntimeError as exc:
                print("STOP: %s (%d/%d cells cached)" % (exc, total - missing, total))
                return 2
            with open(path, "wb") as fh:
                fh.write(raw)
            n = _count_features(raw)
            print("  cell %03d: %d features, %d bytes" % (idx, n, len(raw)), flush=True)
            time.sleep(pace)
    print("harvest complete: %d cells cached" % total)
    return 0


def _count_features(raw: bytes) -> int:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return -1
    if root.tag.endswith("ExceptionReport"):
        return -1
    members = root.findall("wfs:member", NS)
    return len(members)


def parse_feature_member(member: ET.Element) -> Optional[Dict]:
    """One wfs:member -> {fid, band_db, rings_3301} (E,N tuples).

    Pure + hermetic (tested with synthetic GML). posList arrives in
    N,E order under EPSG:3301 — swapped once here. MYRAKLASS domain
    (confirmed 2026-09-17: plain 5 dB lower bounds '45','50','55',…)
    parses as int; anything else -> None (fail closed, row dropped +
    counted by the caller).
    """
    feature = next(iter(member), None)
    if feature is None:
        return None
    # Identity is the member-level gml:id (unique per member, stable
    # across cells, so edge overlaps dedupe; multipart pieces carry
    # .N suffixes and stay separate rows). ms:ID is a CATEGORY code
    # (63-69…), never an identity — keying on it collapses the layer.
    fid = (feature.attrib.get("{%s}id" % NS["gml"], "") or "").strip()
    if not fid:
        return None
    klass = (feature.findtext("{%s}MYRAKLASS" % NS["ms"]) or "").strip()
    try:
        band = int(klass)
    except ValueError:
        return None
    rings = []
    for poslist in feature.iter("{%s}posList" % NS["gml"]):
        nums = (poslist.text or "").split()
        if len(nums) < 8:
            continue
        # N,E -> (E,N).
        ring = [(float(nums[i + 1]), float(nums[i])) for i in range(0, len(nums) - 1, 2)]
        if ring and ring[0] != ring[-1]:
            ring.append(ring[0])
        if len(ring) >= 4:
            rings.append(ring)
    if not rings:
        return None
    return {"fid": fid, "band_db": band, "rings_3301": rings}


def _dp_simplify(ring: List[Tuple[float, float]], tol: float) -> List[Tuple[float, float]]:
    pts = list(ring)
    closed = len(pts) > 1 and pts[0] == pts[-1]
    if closed:
        pts = pts[:-1]
    if len(pts) <= 3:
        return ring
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    # Closed rings have no natural endpoints: seed the split at the
    # vertex farthest from pts[0] (a degenerate seed segment keeps
    # every distance at zero and collapses the whole ring).
    if closed:
        ax, ay = pts[0]
        imax = max(range(1, len(pts)),
                   key=lambda i: (pts[i][0] - ax) ** 2 + (pts[i][1] - ay) ** 2)
        keep[imax] = True
        stack = [(0, imax), (imax, len(pts) - 1)]
    else:
        stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        denom = math.hypot(dx, dy) or 1.0
        best, idx = 0.0, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            dist = abs(dy * px - dx * py + bx * ay - by * ax) / denom
            if dist > best:
                best, idx = dist, i
        if best > tol and idx > 0:
            keep[idx] = True
            stack.append((a, idx))
            stack.append((idx, b))
    out = [p for p, k in zip(pts, keep) if k]
    if closed and out:
        out.append(out[0])
    return out


def _in_keep(e: float, n: float) -> bool:
    emin, nmin, emax, nmax = KEEP_BBOX
    return emin <= e <= emax and nmin <= n <= nmax


def _geom_key(rings: List[List[Tuple[float, float]]]) -> str:
    """Identity hash of simplified-then-rounded geometry (mm grid).

    WFS members carry no per-polygon id (gml:id repeats per category,
    ms:ID IS the category), so edge overlaps across cells dedupe on
    identical geometry: intersecting cells return full (unclipped)
    source polygons, byte-identical down to rounding.
    """
    h = hashlib.sha1()
    for ring in rings:
        for x, y in ring:
            h.update(("%0.3f,%0.3f;" % (x, y)).encode())
        h.update(b"|")
    return h.hexdigest()[:16]


def build(snap: str) -> int:
    """Offline: cache -> sidecar + histogram. Returns 0 on success."""
    cachedir = os.path.join(snap, "noise", "cache")
    if not os.path.isdir(cachedir):
        print("no cache at %s — run harvest first; writing NOTHING" % cachedir)
        return 1
    seen = set()
    rows: List[Dict] = []
    stats: Dict = {"legs": {}, "dropped": 0, "unparseable": 0, "verts": [0, 0]}
    for leg, _typename in LEGS:
        legdir = os.path.join(cachedir, leg)
        n_feat = 0
        if not os.path.isdir(legdir):
            stats["legs"][leg] = 0
            continue
        for name in sorted(os.listdir(legdir)):
            if not name.endswith(".xml"):
                continue
            try:
                root = ET.parse(os.path.join(legdir, name)).getroot()
            except ET.ParseError:
                stats["unparseable"] += 1
                continue
            for member in root.findall("wfs:member", NS):
                parsed = parse_feature_member(member)
                if parsed is None:
                    stats["unparseable"] += 1
                    continue
                out_rings = []
                for ring in parsed["rings_3301"]:
                    stats["verts"][0] += len(ring)
                    if not all(_in_keep(e, n) for e, n in ring):
                        continue
                    simp = _dp_simplify(ring, DP_TOL_M)
                    stats["verts"][1] += len(simp)
                    if len(simp) < 3:
                        # DP collapsed a tiny sliver below validity;
                        # the map guard would (rightly) reject it.
                        stats["slivers"] = stats.get("slivers", 0) + 1
                        continue
                    out_rings.append([[lest97_to_lonlat_lcc(e, n)[0],
                                       lest97_to_lonlat_lcc(e, n)[1]] for e, n in simp])
                if not out_rings:
                    stats["dropped"] += 1
                    continue
                key = (leg, parsed["band_db"], _geom_key(out_rings))
                if key in seen:
                    stats["dupes"] = stats.get("dupes", 0) + 1
                    continue
                seen.add(key)
                lons = [p[0] for r in out_rings for p in r]
                lats = [p[1] for r in out_rings for p in r]
                n_feat += 1
                rows.append({
                    "noise_id": "%s-%d-%s" % (leg, parsed["band_db"], key[2]),
                    "leg": leg,
                    "band_db": parsed["band_db"],
                    "b": [min(lons), min(lats), max(lons), max(lats)],
                    "r": out_rings,
                })
        stats["legs"][leg] = n_feat
    if not rows:
        print("cache parsed but zero rows — writing NOTHING")
        return 1
    doc = {
        "vintage": VINTAGE,
        "source": ATTRIBUTION,
        "unit": "strategic-noise band polygon (5 dB lower bound)",
        "legs": [leg for leg, _t in LEGS],
        "simplify_m": DP_TOL_M,
        "stats": stats,
        "areas": rows,
    }
    outdir = os.path.join(snap, "noise")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "noise-areas.json"), "w") as fh:
        json.dump(doc, fh)
    # Tallinn histogram (band table justification): rows whose bbox
    # centre falls in the Tallinn box (E 525000-555000, N 6580000-6598000).
    hist: Dict = {}
    for r in rows:
        clon = (r["b"][0] + r["b"][2]) / 2
        clat = (r["b"][1] + r["b"][3]) / 2
        lon_e, lat_n = clon, clat
        # bbox stored lon/lat; convert centre back via forward LCC is
        # wasteful — approximate Tallinn box in lon/lat instead.
        if 24.55 <= lon_e <= 25.10 and 59.35 <= lat_n <= 59.50:
            hist[(r["leg"], r["band_db"])] = hist.get((r["leg"], r["band_db"]), 0) + 1
    print("ok=True rows=%d dropped=%d unparseable=%d verts=%d->%d"
          % (len(rows), stats["dropped"], stats["unparseable"],
             stats["verts"][0], stats["verts"][1]))
    print("Tallinn histogram (leg, band_db): count")
    for key in sorted(hist):
        print("  %s %d dB: %d" % (key[0], key[1], hist[key]))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Harvest/build the noise overlay sidecar.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ph = sub.add_parser("harvest", help="Pull missing WFS cells into the cache.")
    ph.add_argument("--snap", required=True)
    ph.add_argument("--pace", type=float, default=3.0)
    ph.add_argument("--cell-km", type=float, default=10.0)
    pb = sub.add_parser("build", help="Offline: cache -> sidecar.")
    pb.add_argument("--snap", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "harvest":
        return harvest(args.snap, args.pace, args.cell_km)
    return build(args.snap)


if __name__ == "__main__":
    sys.exit(main())
