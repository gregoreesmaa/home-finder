"""Monthly huvipunktid long-tail harvest (issue #612, P4 POI register).

Polls the Maa- ja Ruumiamet huvipunktid WFS for the three long-tail
types with no dedicated issue (raamatukogu / post / tervisekaubad —
scorer LONG_TAIL in services/scoring/dims_p4_poi.py) and builds the
`poi/poi-points.json` snapshot sidecar the map serves
(apps/web/lib/layers_p4_poi.ts).

Licence (gate OPENED 2026-09-16, issue #612): the WFS
GetCapabilities ServiceIdentification Abstract states the Maa- ja
Ruumiamet open spatial-data licence applies unless a layer says
otherwise ("Maa- ja Ruumiameti avatud ruumiandmete litsents",
https://geoportaal.maaamet.ee/avaandmete-litsents; Fees/AccessConstraints
"puudub"; HTTP 200, 191 963 B, cached at /tmp/hf-612-poi/). The
sidecar stamps this licence + vintage on every build.

Politeness (AGENTS.md section 7.4): 3 type-bounded GetFeature pulls
(Harjumaa CQL filter, no national dump) per TTL window (30 d —
monthly feed), labelled UA, 2 s pacing, single attempts, HTTP 429 /
errors are a STOP signal (never cached as data). Raw XML lives in
/tmp only — the only committed outputs are this script, its tests,
and the aggregate sidecar (points + counts + stamps, no names or
addresses — TAG_ALLOWLIST precedent).

Dedicated split: the harvest requests ONLY long-tail types
(dedicated #527/#528/#530/#531/#532 types are never pulled, never
scored here — DEDICATED_SPLIT in dims_p4_poi.py, disjointness pinned
by test). Post INCLUDES pakiautomaat (parcel lockers, 521/536):
post-flip judgment call (#612 title) — lockers are the dominant
postal access in Harjumaa; offices-only would fake scarcity. The
subgroup split rides the sidecar stats + the layer source note.

Coverage honesty: coordless features are dropped and COUNTED (never
zero-filled); per-type andmeseis stamps build the staleness table
(monthly vahekiht over source registers of varying vintage — every
reason says so).
"""

import json
import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

WFS_BASE_URL = "https://gsavalik.envir.ee/geoserver/huvipunkt/wfs"

POI_UA = (
    "home-finder-612-poi-wfs/1.0 "
    "(polite monthly harvest, paced type-bounded GETs; "
    "GitHub gregoreesmaa/home-finder issue 612)"
)

#: Seconds between harvest GETs.
POI_PACE_S = 2

#: Monthly feed: re-pull at most every 30 days.
POI_TTL_S = 30 * 24 * 3600

#: Minimum plausible XML body: the smallest county extract
#: (raamatukogu, 124 features) is ~184 KB, so anything smaller is an
#: error page, never data.
XML_MIN_BYTES = 50_000

DEFAULT_CACHE_DIR = os.path.join("/tmp", "hf-612-poi")

#: Licence stamped on the sidecar (verified 2026-09-16, see header).
POI_LICENCE = (
    "Maa- ja Ruumiamet avatud ruumiandmete litsents "
    "(https://geoportaal.maaamet.ee/avaandmete-litsents)"
)

#: Harvested type -> map slice (mirrors LONG_TAIL + POI_DIMS slices).
POI_TYPES: Tuple[Tuple[str, str], ...] = (
    ("raamatukogu", "library"),
    ("post", "post"),
    ("tervisekaubad", "pharmacy"),
)

HARJU_CQL = "mk='Harju maakond'"

NS = {
    # Observed live 2026-09-16 (xmlns:huvipunkt="maaruum.huvipunkt").
    "h": "maaruum.huvipunkt",
    "gml": "http://www.opengis.net/gml/3.2",
}


def fetch_cached(type_name: str, cache_dir: str,
                 ttl_s: int = POI_TTL_S) -> Optional[str]:
    """Polite single-GET Harjumaa pull with a monthly TTL.

    Returns the local path or None. Cache hit (fresh mtime within
    ttl_s): NO request is made. Otherwise one type-bounded GetFeature
    GET (Harjumaa CQL filter) with POI_UA; the body is stored only on
    HTTP 200 with at least XML_MIN_BYTES bytes. No retries — HTTP
    429/errors are a stop signal. Tests cover the pure parser, never
    this.
    """
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, "harju-%s.xml" % type_name)
    try:
        if (os.path.exists(dest)
                and time.time() - os.path.getmtime(dest) < ttl_s):
            return dest
    except OSError:
        return None
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": "huvipunkt:%s" % type_name,
        "CQL_FILTER": HARJU_CQL,
    }
    url = "%s?%s" % (WFS_BASE_URL, urllib.parse.urlencode(params))
    req = urllib.request.Request(url, headers={"User-Agent": POI_UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
            if resp.status != 200:
                return None
            body = resp.read()
    except Exception:
        return None
    if len(body) < XML_MIN_BYTES:
        return None
    try:
        with open(dest, "wb") as f:
            f.write(body)
    except OSError:
        return None
    return dest


def _text(feature: ET.Element, name: str) -> str:
    child = feature.find("h:%s" % name, NS)
    return child.text.strip() if child is not None and child.text else ""


def parse_features(xml_path: str, type_name: str,
                   slice_name: str) -> Tuple[List[dict], dict]:
    """Parse one county extract into sidecar points + stats (pure).

    Returns ([{lat, lon, slice}], stats). Coordless features are
    dropped and counted (never zero-filled); names/addresses never
    leave this function. Tested hermetically with fixture XML.
    """
    root = ET.parse(xml_path).getroot()
    points: List[dict] = []
    stats: Dict[str, object] = {
        "features": 0, "plotted": 0, "dropped_no_coord": 0,
        "stamps": {}, "sources": {}, "subgroups": {},
    }
    for feature in root.iter():
        if feature.tag != "{%s}%s" % (NS["h"], type_name):
            continue
        stats["features"] += 1
        # Feed-level tallies (stamps/sources/subgroups) cover EVERY
        # feature, plotted or dropped — they describe upstream vintage,
        # not the map.
        for key, field in (("stamps", "andmeseis"), ("sources", "allikas"),
                           ("subgroups", "alamgrupp")):
            bucket = stats[key]
            assert isinstance(bucket, dict)
            value = _text(feature, field) or "(märkimata)"
            bucket[value] = bucket.get(value, 0) + 1
        try:
            lon = float(_text(feature, "pikkus"))
            lat = float(_text(feature, "laius"))
        except ValueError:
            stats["dropped_no_coord"] += 1
            continue
        if not (Number_finite(lon) and Number_finite(lat)):
            stats["dropped_no_coord"] += 1
            continue
        if not (21.0 <= lon <= 29.0 and 57.0 <= lat <= 60.5):
            stats["dropped_no_coord"] += 1
            continue
        points.append({"lat": round(lat, 6), "lon": round(lon, 6),
                       "slice": slice_name})
        stats["plotted"] += 1
    return points, stats


def Number_finite(value: float) -> bool:
    """Local finite check (no math import needed elsewhere)."""
    return value == value and value not in (float("inf"), float("-inf"))


def build_sidecar(points: List[dict], per_type: Dict[str, dict],
                  vintage: str, out_dir: str) -> dict:
    """Write poi/poi-points.json; returns the doc."""
    doc = {
        "vintage": vintage,
        "licence": POI_LICENCE,
        "attribution": "Maa- ja Ruumiamet huvipunktid (vahekiht)",
        "counts": {t: s for t, s in per_type.items()},
        "points": points,
    }
    poi_dir = os.path.join(out_dir, "poi")
    os.makedirs(poi_dir, exist_ok=True)
    with open(os.path.join(poi_dir, "poi-points.json"), "w",
              encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    return doc


def main() -> int:
    """Monthly long-tail harvest (paced type-bounded GETs, 429 = stop)."""
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    ap.add_argument("--out-dir", default=None,
                    help="snapshot dir receiving poi/poi-points.json "
                         "(default: <cache-dir>/snapshot)")
    ap.add_argument("--vintage", default="2026-09-16",
                    help="vintage label stamped on the sidecar")
    args = ap.parse_args()

    all_points: List[dict] = []
    per_type: Dict[str, dict] = {}
    first = True
    for type_name, slice_name in POI_TYPES:
        if not first:
            time.sleep(POI_PACE_S)
        first = False
        xml_path = fetch_cached(type_name, args.cache_dir)
        if xml_path is None:
            print("STOP: %s pull failed (transport refused or thin "
                  "body) — no sidecar written" % type_name)
            return 1
        points, stats = parse_features(xml_path, type_name, slice_name)
        time.sleep(POI_PACE_S)
        all_points.extend(points)
        per_type[slice_name] = stats
        print("%s: features=%d plotted=%d dropped_no_coord=%d" % (
            type_name, stats["features"], stats["plotted"],
            stats["dropped_no_coord"]))
        print("  stamps=%s" % (stats["stamps"],))
        print("  sources=%s subgroups=%s"
              % (stats["sources"], stats["subgroups"]))
    doc = build_sidecar(all_points, per_type, args.vintage,
                        args.out_dir
                        or os.path.join(args.cache_dir, "snapshot"))
    print("poi extract: %d points (vintage %s, %s)"
          % (len(all_points), args.vintage, POI_LICENCE))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
