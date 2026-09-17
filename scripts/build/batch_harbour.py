"""Harbour overlay harvester + sidecar builder (issue #627).

Joins three proven-public sources into snapshot
``<snap>/harbour/harbour-areas.json`` consumed by
/api/layers/harbour/areas. Stdlib only.

1. Port register: one GET of
   https://www.sadamaregister.ee/api/ports/public-active (245 rows:
   name, address, portFunction 1/2/3, publicId). ApiBaseUrl resolved
   2026-09-17 by reading the app bundle (AGENTS.md §7.7: the JS shell
   was the lead, ``window.appSettings.ApiBaseUrl`` + ``/ports/…``
   paths the find). Function enum mapped from the app's own UI
   strings: 1 = full-service port, 2 = small port (paid, <24 m
   craft), 3 = small port (no paid services).
2. Geometry: INSPIRE TN_sadam PortNode Harju pull, joined on the
   register publicId (``EE-PIR_168`` ↔ publicId 168, proven). NOTE:
   the WFS labels CRS84 but serves 3301 NORTHING,EASTING (verified
   against Pirita: pos 6592572/546582) — swapped once, loudly.
3. AIS density: pleasure-craft 500 m cells (2024 vintage) read off
   the cached ``ais_density_shp.zip`` (CC BY-SA 3.0, Transpordiamet),
   Tallinn Bay window only. Season data is NOT public (per-port
   detail endpoints 401) — no calendar leg is built, stated.

HONESTY: a missing/unreadable input writes NOTHING (unknown, never
partial). Outside every port/cell is NULL (never calm). Transport
errors are never cached; HTTP 429 stops the run (exit 2, rerun
resumes via the cache).

Usage:
  python3 scripts/build/batch_harbour.py --ports-json <file|-> --snap DIR
      [--nodes-xml FILE] [--ais-zip FILE] [--pace 3]
  (--ports-json - reads stdin; live pulls are one polite GET each.)
"""

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from batch_canopy import lest97_to_lonlat_lcc  # noqa: E402  (true LCC, NOT legacy TM)

UA = "home-finder-dev/0.1 (polite one-off harvest; issue #627)"
PORTS_URL = "https://www.sadamaregister.ee/api/ports/public-active"
NODES_URL = ("https://inspire.geoportaal.ee/geoserver/TN_sadam/wfs"
             "?service=WFS&version=2.0.0&request=GetFeature"
             "&typeNames=TN_sadam:TN.WaterTransportNetwork.PortNode"
             "&BBOX=59.3,23.3,59.65,25.5,urn:ogc:def:crs:EPSG::4326")

#: Function enum (mapped 2026-09-17 from the register app's own UI).
FUNCTION_LABEL = {
    1: "täisteenus (kõik veesõidukid)",
    2: "väikesadam (tasulised, <24 m)",
    3: "väikesadam (tasuta)",
}

#: Tallinn Bay AIS window (lon/lat): pleasure cells kept inside it.
BAY_BBOX = (24.55, 59.35, 25.10, 59.55)

#: AIS vintage harvested (annual TTL — a new vintage re-runs the build).
AIS_VINTAGE = "2024"

#: 3301 keep sanity: joined nodes must land inside Harju+margin.
KEEP_3301 = (478000.0, 6533000.0, 614000.0, 6622000.0)

NS = {
    "wfs": "http://www.opengis.net/wfs/2.0",
    "gml": "http://www.opengis.net/gml/3.2",
}


class _StopSignal(RuntimeError):
    """HTTP 429 back-off signal: stop the run, rerun resumes via cache."""


def _get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 429:
                raise RuntimeError("HTTP 429 — stop signal")
            return resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise _StopSignal("HTTP 429 — stop signal")
        raise RuntimeError("HTTP %d on %s" % (exc.code, url))


def _node_pos(member: ET.Element) -> Optional[Tuple[str, float, float, str]]:
    """One PortNode member -> (gml_id, E, N in 3301)."""
    gid, name, pos = "", "", ""
    for child in member.iter():
        if child.tag.endswith("}gml_id") and child.text:
            gid = child.text.strip()
        if child.tag.endswith("}spellingofname_text") and child.text:
            name = child.text.strip()
        if child.tag == "{%s}pos" % NS["gml"] and child.text:
            pos = child.text.strip()
    if not gid or not pos:
        return None
    try:
        n, e = (float(v) for v in pos.split())
    except ValueError:
        return None
    # Served N,E despite the CRS84 label (verified 2026-09-17).
    emin, nmin, emax, nmax = KEEP_3301
    if not (emin <= e <= emax and nmin <= n <= nmax):
        return None
    return gid, e, n, name


def parse_nodes(raw: bytes) -> Dict[str, Dict]:
    """WFS PortNode doc -> {publicId: {lon, lat, node_name}} (pure)."""
    root = ET.fromstring(raw)
    out: Dict[str, Dict] = {}
    for member in root.findall("wfs:member", NS):
        parsed = _node_pos(member)
        if parsed is None:
            continue
        gid, e, n, name = parsed
        pub = gid.split("_")[-1]
        if not pub.isdigit():
            continue
        lon, lat = lest97_to_lonlat_lcc(e, n)
        out[pub] = {"lon": lon, "lat": lat, "node_name": name}
    return out


def read_ais_cells(zip_path: str, vintage: str = AIS_VINTAGE) -> List[Dict]:
    """Pleasure>0 cells inside BAY_BBOX from the cached AIS zip (pure IO).

    Returns [{lon, lat, pleasure, all}] cell centroids. Cells with no
    pleasure traffic are skipped (the overlay grades recreation
    pressure, not empty water).
    """
    import struct
    zf = zipfile.ZipFile(zip_path)
    base = next((n[:-4] for n in zf.namelist()
                 if vintage in n and n.endswith(".shp")), None)
    if base is None:
        raise ValueError("no %s .shp in %s" % (vintage, zip_path))
    shp = zf.read(base + ".shp")
    dbf = zf.read(base + ".dbf")
    nrec, hlen, rlen = struct.unpack("<IHH", dbf[4:12])
    if rlen != 119:
        raise ValueError("AIS DBF record-length drift: %d != 119" % rlen)
    cells = []
    off = 100
    for i in range(nrec):
        rwords = struct.unpack(">i", shp[off + 4:off + 8])[0]
        xmin, ymin, xmax, ymax = struct.unpack("<4d", shp[off + 12:off + 44])
        rec = dbf[hlen + i * 119: hlen + (i + 1) * 119]
        try:
            all_n = int(rec[1:11] or 0)
            pleasure = int(rec[41:51] or 0)
        except ValueError:
            pleasure, all_n = 0, 0
        if pleasure > 0:
            ce, cn = (xmin + xmax) / 2, (ymin + ymax) / 2
            lon, lat = lest97_to_lonlat_lcc(ce, cn)
            if BAY_BBOX[0] <= lon <= BAY_BBOX[2] and BAY_BBOX[1] <= lat <= BAY_BBOX[3]:
                cells.append({"lon": round(lon, 5), "lat": round(lat, 5),
                              "pleasure": pleasure, "all": all_n})
        off += 8 + rwords * 2
    return cells


def build(ports: List[Dict], nodes: Dict[str, Dict],
          cells: List[Dict]) -> Dict:
    """Join register rows to node geometry + AIS cells (pure)."""
    joined, unplaced = [], 0
    for p in ports:
        pub = str(p.get("publicId", ""))
        node = nodes.get(pub)
        fn = p.get("portFunction")
        if node is None or fn not in FUNCTION_LABEL:
            unplaced += 1
            continue
        joined.append({
            "harbour_id": "port-%s" % pub,
            "name": p.get("name", ""),
            "function": fn,
            "function_label": FUNCTION_LABEL[fn],
            "address": p.get("address", ""),
            "lon": round(node["lon"], 5),
            "lat": round(node["lat"], 5),
        })
    return {
        "vintage": AIS_VINTAGE,
        "source": ("sadamaregister public-active + INSPIRE TN_sadam "
                   "PortNode + Transpordiamet AIS density (CC BY-SA 3.0)"),
        "unit": "joined port point (function) + pleasure-cell centroid",
        "stats": {"ports": len(joined), "unplaced": unplaced,
                  "cells": len(cells)},
        "ports": joined,
        "cells": cells,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Build the harbour sidecar.")
    ap.add_argument("--ports-json", required=True,
                    help="Cached public-active JSON, or - to pull live once.")
    ap.add_argument("--snap", required=True, help="Snapshot dir.")
    ap.add_argument("--nodes-xml", default=None,
                    help="Cached PortNode Harju pull (else pulled live once).")
    ap.add_argument("--ais-zip", default=None,
                    help="Cached ais_density_shp.zip (else cells skipped).")
    ap.add_argument("--pace", type=float, default=3.0)
    args = ap.parse_args(argv)
    try:
        if args.ports_json == "-":
            ports_raw = _get(PORTS_URL)
            time.sleep(args.pace)
        else:
            with open(args.ports_json, "rb") as fh:
                ports_raw = fh.read()
        ports = json.loads(ports_raw)
        if args.nodes_xml:
            with open(args.nodes_xml, "rb") as fh:
                nodes_raw = fh.read()
        else:
            nodes_raw = _get(NODES_URL)
        nodes = parse_nodes(nodes_raw)
        cells = read_ais_cells(args.ais_zip) if args.ais_zip else []
    except _StopSignal as exc:
        print("harvest stopped (%s) — writing NOTHING" % exc)
        return 2
    except (RuntimeError, OSError, ValueError, ET.ParseError,
            zipfile.BadZipFile, KeyError) as exc:
        print("harvest failed (%s) — writing NOTHING" % exc)
        return 1
    doc = build(ports, nodes, cells)
    if not doc["ports"]:
        print("zero joined ports — writing NOTHING")
        return 1
    outdir = os.path.join(args.snap, "harbour")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "harbour-areas.json"), "w") as fh:
        json.dump(doc, fh)
    print("ok=True ports=%d unplaced=%d cells=%d"
          % (doc["stats"]["ports"], doc["stats"]["unplaced"],
             doc["stats"]["cells"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
