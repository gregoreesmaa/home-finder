"""PLANK/TPR designated-use polygon harvest (issue #492): polite WFS pull.

Stdlib only. Harvests kehtestatud designated-use polygons from the PLANK
national WFS into the `plank/areas.json` sidecar served by
apps/web/lib/server/snapshot.ts (the planktpr layer draws them as exact
per-parcel fills). Pure logic + fixture readers live at module top so
unit tests stay hermetic; network lives ONLY in the fetch helpers below.

POLITENESS (AGENTS.md section 7.4): max 1 download / 14 d per cache dir
(PLANKTPR_TTL_S; parameters3.md section 5.5 bi-weekly ticket). Cache hit
within TTL performs NO request. While no open bulk endpoint exists
(PLANK_BULK_URL is None) the harvester performs no request at all and
reports the dated negative — the missing endpoint stays an explicit code
path, not a hidden assumption. With a bulk URL: GetCapabilities once,
then one GetFeature per harvest with PLANKTPR_UA and a 30 s timeout, no
retries (HTTP 429/errors are a stop signal). Transport errors are never
cached as data (a body is stored only on HTTP 200 with a JSON content
type that parses). TPR has no WFS at all (human web register) — when a
TPR bulk feed is verified, it arrives as a second typename on the same
ticket, never as scraping.

VERDICT (checked 2026-09-13, re-verified for #492 the same day — fresh
evidence in docs/p4_planktpr.md): the PLANK national WFS endpoint is
GONE (GetCapabilities follows to the E-ehitus SPA shell, zero WFS
markers) and TPR serves no bulk (Angular SPA shell, no
wfs/bulk/api/download link). So the live path below is honest plumbing
with NO live data: harvest() returns None while PLANK_BULK_URL is None,
the sidecar stays absent (the layer renders honestly empty), and the
scored shapes are proven on fixtures only. Reopening checklist lives in
docs/p4_planktpr.md.

Sidecar schema (what the harvester stores; fixtures match it):
  [{"plan_id": str, "use": str (raw designated-use code),
    "stage": str, "kov": str, "rings": [[[lon, lat], ...], ...]}]
Only kehtestatud Tallinn rows are kept (the layer's exact-join scope —
same filter as dims_overturn_planktpr DECREE_STAGE/TALLINN_KOVS).
Malformed features are skipped, never faked.

BANDS (first-cut fit bands for a kehtestatud residential purchase —
mirrors USE_BANDS in services/scoring/dims_overturn_planktpr.py AND
PLANKTPR_USE_BANDS in apps/web/lib/layers_planktpr.ts exactly; the
pytest parses all three and fails on drift):
  residential 80 / mixed 60 / commercial 35 / restricted 20 (cap 80).
Must be recalibrated from a real snapshot on reopen.

Usage:
  python3 scripts/build/batch_planktpr_wfs.py --cache-dir <dir>   # harvest (polite)
  python3 scripts/build/batch_planktpr_wfs.py --probe             # headers-only openness re-check
"""

import argparse
import json
import os
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Ingestion contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: Documented PLANK WFS base (parameters3.md Group 5; verified 2026-09-13:
#: HTTP 301 to the E-ehitus SPA — the WFS itself is gone, see docstring).
PLANK_WFS_URL = "https://planeeringud.ee/geoserver/wfs"

#: Open bulk endpoint: NONE found 2026-09-13 (dated negative, see module
#: docstring). Stays None until the reopening checklist in
#: docs/p4_planktpr.md names a verified bulk URL; while None, the
#: harvester performs no requests.
PLANK_BULK_URL: Optional[str] = None

#: Max one download per 14 d per cache dir (parameters3.md section 5.5:
#: bi-weekly ticket — the overturn p47/p74 precedent).
PLANKTPR_TTL_S = 14 * 24 * 3600

#: Sidecar filename inside the cache dir (served as plank/areas.json).
CACHE_FILENAME = "areas.json"

#: Identifying user agent for the polite pull (no scrape, single GETs).
PLANKTPR_UA = "home-finder planktpr-harvest (max 1 req/14d, no scrape)"

#: Plan stage kept as decree (parity with the scorer + web layer).
DECREE_STAGE = "kehtestatud"

#: Tallinn kov spellings kept by the harvest filter (lowercased).
TALLINN_KOVS = frozenset({"tallinn", "tallinna linn"})

#: First-cut fit bands (drift-pinned against the scorer + web layer).
USE_BANDS = {"residential": 80, "mixed": 60, "commercial": 35,
             "restricted": 20}

WFS_VERSION = "2.0.0"


def _headers() -> dict:
    return {"User-Agent": PLANKTPR_UA}


def _get(url: str, timeout_s: int = 30) -> Optional[Tuple[bytes, str]]:
    """One polite GET: (body, content-type) on HTTP 200, else None.

    No retries — HTTP 429/errors are a stop signal. Transport errors are
    never data.
    """
    try:
        req = urllib.request.Request(url, headers=_headers())
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            status = getattr(resp, "status", 200)
            ctype = resp.headers.get("Content-Type", "")
            if status != 200:
                return None
            return resp.read(), ctype
    except Exception:
        return None


def probe() -> Dict[str, object]:
    """Headers-only openness re-check (no bulk pull, no scraping).

    Returns a small evidence dict: final URL + content type + size +
    whether any WFS marker survived. Pure observation, safe to run any
    time (4 tiny requests, paced by the caller).
    """
    evidence: Dict[str, object] = {"requests": []}
    reqs = list(evidence["requests"])  # type: ignore[union-attr]
    getcap = (PLANK_WFS_URL
              + "?service=WFS&version=%s&request=GetCapabilities" % WFS_VERSION)
    for url in (PLANK_WFS_URL, getcap, "https://tpr.tallinn.ee/"):
        got = _get(url)
        time.sleep(3)
        if got is None:
            reqs.append({"url": url, "observed": "no-200"})
            continue
        body, ctype = got
        head = body[:4000].decode("utf-8", "replace").lower()
        markers = [m for m in ("wfs:", "opengis", "featuretype",
                               "getcapabilities")
                   if m in head]
        reqs.append({"url": url, "content_type": ctype,
                     "bytes": len(body), "wfs_markers": markers})
    return evidence


def parse_capabilities(xml_bytes: bytes) -> List[str]:
    """GetCapabilities doc -> candidate designated-use FeatureType names.

    Pure (stdlib XML). Returns [] when the doc is not a capabilities
    document (e.g. the E-ehitus SPA shell) — never raises on junk.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []
    names = []
    for el in root.iter():
        if el.tag.endswith("FeatureType"):
            for child in el:
                if child.tag.endswith("Name") and (child.text or "").strip():
                    names.append(child.text.strip())
    needles = ("planeering", "sihtotstar", "zoning", "tpr",
               "detailplaneering", "kehtestatud")
    picks = [n for n in names
             if any(k in n.split(":")[-1].lower() for k in needles)]
    return picks or names


def _num(v) -> Optional[float]:
    if isinstance(v, bool):
        return None
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) != float("inf") else None


def _clean_ring(coords) -> Optional[List[List[float]]]:
    """One linear ring -> [[lon, lat], ...] or None when degenerate."""
    if not isinstance(coords, (list, tuple)):
        return None
    ring = []
    for pt in coords:
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            return None
        lon, lat = _num(pt[0]), _num(pt[1])
        if lon is None or lat is None:
            return None
        ring.append([lon, lat])
    return ring if len(ring) >= 3 else None


def feature_to_row(feature: dict) -> Optional[dict]:
    """One GeoJSON feature -> sidecar row, or None when unusable.

    Pure: keeps kehtestatud Tallinn polygons with finite rings only.
    Property lookup is tolerant (register exports vary) but never
    invents values: a missing use/stage/kov drops the row.
    """
    if not isinstance(feature, dict):
        return None
    props = feature.get("properties")
    geom = feature.get("geometry")
    if not isinstance(props, dict) or not isinstance(geom, dict):
        return None
    stage = props.get("stage", props.get("use_stage", props.get("staadium")))
    kov = props.get("kov", props.get("municipality", props.get("omavalitsus")))
    use = props.get("use", props.get("designated_use",
                                     props.get("sihtotstarve")))
    if not isinstance(stage, str) or not isinstance(kov, str):
        return None
    if not isinstance(use, str) or not use.strip():
        return None
    if stage.strip().lower() != DECREE_STAGE:
        return None
    if kov.strip().lower() not in TALLINN_KOVS:
        return None
    plan_id = props.get("plan_id", props.get("id", props.get("tunnus")))
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    rings: List[List[List[float]]] = []
    if gtype == "Polygon" and isinstance(coords, list):
        for ring_coords in coords[:1]:  # outer ring only (holes stay out)
            ring = _clean_ring(ring_coords)
            if ring is None:
                return None
            rings.append(ring)
    elif gtype == "MultiPolygon" and isinstance(coords, list):
        for poly in coords:
            if not isinstance(poly, list) or not poly:
                return None
            ring = _clean_ring(poly[0])
            if ring is None:
                return None
            rings.append(ring)
    else:
        return None
    if not rings:
        return None
    return {"plan_id": str(plan_id or "tundmatu"), "use": use.strip(),
            "stage": stage.strip(), "kov": kov.strip(), "rings": rings}


def parse_feature_collection(payload: bytes) -> List[dict]:
    """WFS GeoJSON body -> sidecar rows (malformed features skipped)."""
    try:
        doc = json.loads(payload)
    except ValueError:
        return []
    if not isinstance(doc, dict):
        return []
    features = doc.get("features")
    if not isinstance(features, list):
        return []
    rows = []
    for f in features:
        row = feature_to_row(f)
        if row is not None:
            rows.append(row)
    return rows


def harvest(cache_dir: str,
            ttl_s: int = PLANKTPR_TTL_S,
            bulk_url: Optional[str] = PLANK_BULK_URL,
            ) -> Optional[str]:
    """Polite WFS harvest into <cache_dir>/plank/areas.json.

    Cache hit (fresh sidecar within ttl_s): NO request is made. With no
    known bulk endpoint (bulk_url None) performs no request and returns
    None (the dated negative). With a bulk URL: GetCapabilities once to
    pick the designated-use typename, then one GetFeature pull;
    the sidecar is written only when the pull parses to rows.
    Returns the sidecar path or None.
    """
    plank_dir = os.path.join(cache_dir, "plank")
    os.makedirs(plank_dir, exist_ok=True)
    dest = os.path.join(plank_dir, CACHE_FILENAME)
    try:
        if (os.path.exists(dest)
                and time.time() - os.path.getmtime(dest) < ttl_s):
            return dest
    except OSError:
        return None
    if bulk_url is None:
        return None
    got = _get(bulk_url + "?service=WFS&version=%s&request=GetCapabilities"
               % WFS_VERSION)
    if got is None:
        return None
    typenames = parse_capabilities(got[0])
    if not typenames:
        return None
    gurl = (bulk_url + "?service=WFS&version=%s&request=GetFeature"
            "&typeNames=%s&outputFormat=application/json&count=10000"
            % (WFS_VERSION, typenames[0]))
    pulled = _get(gurl)
    if pulled is None:
        return None
    body, ctype = pulled
    if "json" not in ctype:
        return None
    rows = parse_feature_collection(body)
    if not rows:
        return None
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-dir", default=None,
                    help="snapshot cache dir (harvest writes plank/areas.json)")
    ap.add_argument("--probe", action="store_true",
                    help="headers-only openness re-check (no bulk pull)")
    args = ap.parse_args()
    if args.probe or not args.cache_dir:
        print(json.dumps(probe(), ensure_ascii=False, indent=2))
        return 0
    dest = harvest(args.cache_dir)
    if dest is None:
        print("EI OLE: PLANK/TPR bulk endpoint missing "
              "(dated negative 2026-09-13) — no requests made, sidecar absent")
        return 0
    print("harvested sidecar: %s" % dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
