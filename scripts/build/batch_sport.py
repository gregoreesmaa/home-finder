"""Spordiregister + ujulad harvest + build (issue #607).

Polite single-fetch harvest of the Spordiregister JSON bulk
(spordiehitised.json, WGS84) and the vtiav ujulad XML bulk (L-EST97),
and an offline build of the Harjumaa venue-point extract the
sport_hall/sport_field/sport_pool map overlays serve. Stdlib only;
network lives ONLY in fetch_cached/main.

Feed verdict (2026-09-16, see services/scoring/dims_p4_sportreg.py and
docs/p4_sportreg.md; aggregates only, raw bodies never committed):
4157 venues / 1216 Harjumaa, all with WGS84 kaart_laius/kaart_pikkus,
fresh (newest esitatudkuupaev 2026-09-15); 226 ujulad rows, 219 with
L-EST97 x/y. Slice matchers mirror dims_p4_sportreg.py venue_slices
(pool "siseujula", hall "voimla", field six markers) so map colors and
scored reasons agree by construction (pinned by tests on both sides).

Ujulad rows carry no county column: Harjumaa membership is decided by
the projected point falling in the documented county window below
(approximate bbox, stated — border rows may misclassify, counted in
dropped_outside_county, never silently kept).

Honesty (AGENTS.md 7.2): rows outside Harjumaa, inactive rows,
unsliced kinds, and coordless rows are DROPPED (counted + reported,
never faked); transport errors are never cached as data (fetch_cached
stores only HTTP 200 bodies over a minimum size); names/addresses
never leave the sidecar wire (points carry lat/lon/slice only).
Licence CC BY-SA 3.0 on both bulks — attribution + share-alike ride
in the layer legends and docs/p4_sportreg.md.
"""

import json
import math
import os
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Ingestion contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: Spordiregister venue bulk (verified 2026-09-16: HTTP 200, ~21 MB JSON).
SPORTREG_JSON_URL = (
    "https://www.spordiregister.ee/opendata/files/spordiehitised.json"
)

#: vtiav indoor-pool bulk (verified 2026-09-16: HTTP 200, ~263 KB XML).
UJULAD_XML_URL = "http://vtiav.sm.ee/index.php/opendata/ujulad.xml"

#: Venues change slowly: at most one refresh per 365 d per cache dir.
SPORT_TTL_S = 365 * 24 * 3600

#: Identifying user agent for the polite pull (paced single GETs, no scrape).
SPORT_UA = (
    "home-finder-607-sport/1.0 "
    "(polite yearly harvest, paced single GETs; "
    "GitHub gregoreesmaa/home-finder issue 607)"
)

#: Seconds between harvest GETs (polite pacing on top of the yearly TTL).
SPORT_PACE_S = 5

#: Minimum plausible bodies: the JSON bulk is ~21 MB, the XML ~263 KB —
#: anything smaller is an error page, never data.
JSON_MIN_BYTES = 10_000_000
XML_MIN_BYTES = 100_000

#: Vintage stamped on the extract (harvest date, re-verified per pull).
SPORT_VINTAGE = "2026-09-16"

#: Default cache dir (raw bulks live here; /tmp only, AGENTS.md 5).
DEFAULT_CACHE_DIR = os.path.join("/tmp", "hf-607-sport")

#: Slice matchers mirror services/scoring/dims_p4_sportreg.py (lowercased
#: substring match on `liik`; pool first so combos yield pool AND hall).
POOL_MARKERS = ("siseujula",)
HALL_MARKERS = ("võimla",)
FIELD_MARKERS = ("välispalliväljak", "staadion", "tenniseplats",
                 "püsirada", "vabas õhus", "spordiplats")

#: Only venues in sporting use place points (filter stays for drift).
ACTIVE_STATUS = "Spordialases kasutuses"

#: Approximate Harjumaa county window (WGS84): west Paldiski ~23.8, east
#: ~25.4, south ~58.9, north coast ~59.8. Border rows may misclassify —
#: stated here and in layers_p4_sport.ts, never hidden.
HARJU_BBOX = {"minlon": 23.8, "minlat": 58.9, "maxlon": 25.4,
              "maxlat": 59.8}


def fetch_cached(url: str, cache_dir: str, filename: str,
                 min_bytes: int,
                 ttl_s: int = SPORT_TTL_S) -> Optional[str]:
    """Polite single-GET pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made. Otherwise
    one GET with SPORT_UA and a 60 s timeout; the body is stored only on
    HTTP 200 with at least min_bytes bytes, else None is returned and
    nothing is cached (transport errors are never data). No retries —
    HTTP 429/errors are a stop signal. Scorers never call this; tests
    cover the pure readers, never the network.
    """
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, filename)
    try:
        if (os.path.exists(dest)
                and time.time() - os.path.getmtime(dest) < ttl_s):
            return dest
    except OSError:
        return None
    req = urllib.request.Request(url, headers={"User-Agent": SPORT_UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status != 200:
                return None
            body = resp.read()
    except Exception:
        return None
    if len(body) < min_bytes:
        return None
    try:
        with open(dest, "wb") as f:
            f.write(body)
    except OSError:
        return None
    return dest


# ---------------------------------------------------------------------------
# L-EST97 (EPSG:3301) -> WGS84, labelled approximate (~1 m). Local copy of
# scripts/build/batch_tervise.py (stdlib inverse-LCC, Maa-amet constants).
# ---------------------------------------------------------------------------

_LEST_A = 6378137.0
_LEST_F = 1 / 298.257222101
_LEST_E2 = 2 * _LEST_F - _LEST_F * _LEST_F
_LEST_E = math.sqrt(_LEST_E2)

_LEST_PHI0 = math.radians(57.5175539305556)
_LEST_LAM0 = math.radians(24.0)
_LEST_PHI1 = math.radians(59.3333333333333)
_LEST_PHI2 = math.radians(58.0)
_LEST_E0 = 500000.0
_LEST_N0 = 6375000.0


def _lest_m(phi: float) -> float:
    return math.cos(phi) / math.sqrt(1 - _LEST_E2 * math.sin(phi) ** 2)


def _lest_t(phi: float) -> float:
    s = _LEST_E * math.sin(phi)
    return math.tan(math.pi / 4 - phi / 2) / ((1 - s) / (1 + s)) ** (_LEST_E / 2)


_LEST_M1, _LEST_M2 = _lest_m(_LEST_PHI1), _lest_m(_LEST_PHI2)
_LEST_T1, _LEST_T2 = _lest_t(_LEST_PHI1), _lest_t(_LEST_PHI2)
_LEST_T0 = _lest_t(_LEST_PHI0)
_LEST_N = ((math.log(_LEST_M1) - math.log(_LEST_M2))
           / (math.log(_LEST_T1) - math.log(_LEST_T2)))
_LEST_FF = _LEST_M1 / (_LEST_N * _LEST_T1 ** _LEST_N)
_LEST_RHO0 = _LEST_A * _LEST_FF * _LEST_T0 ** _LEST_N


def lest97_to_wgs84(northing: float, easting: float) -> Tuple[float, float]:
    """Project L-EST97 metres to (lat, lon). Labelled ~1 m.

    Ujulad convention: <x> is the northing, <y> the easting. Raises
    ValueError on non-finite input (callers drop such rows, never fake).
    """
    if not (math.isfinite(northing) and math.isfinite(easting)):
        raise ValueError("non-finite L-EST97 coordinate")
    rho = math.copysign(
        math.hypot(easting - _LEST_E0, _LEST_RHO0 - (northing - _LEST_N0)),
        _LEST_N)
    theta = math.atan2(easting - _LEST_E0, _LEST_RHO0 - (northing - _LEST_N0))
    t = (rho / (_LEST_A * _LEST_FF)) ** (1 / _LEST_N)
    lam = theta / _LEST_N + _LEST_LAM0
    phi = math.pi / 2 - 2 * math.atan(t)
    for _ in range(20):
        s = _LEST_E * math.sin(phi)
        phi = math.pi / 2 - 2 * math.atan(t * ((1 - s) / (1 + s)) ** (_LEST_E / 2))
    return math.degrees(phi), math.degrees(lam)


# ---------------------------------------------------------------------------
# Pure offline readers (hermetic, pinned by test_batch_sport.py).
# ---------------------------------------------------------------------------

def _slices_of(liik: object, ehstaatus: object) -> List[str]:
    """Mirror of dims_p4_sportreg.venue_slices (kept in sync by test)."""
    if ehstaatus != ACTIVE_STATUS or not isinstance(liik, str):
        return []
    low = liik.lower()
    out = []
    if any(m in low for m in POOL_MARKERS):
        out.append("pool")
    if any(m in low for m in HALL_MARKERS):
        out.append("hall")
    if any(m in low for m in FIELD_MARKERS):
        out.append("field")
    return out


def _in_harju(lat: float, lon: float) -> bool:
    return (HARJU_BBOX["minlon"] <= lon <= HARJU_BBOX["maxlon"]
            and HARJU_BBOX["minlat"] <= lat <= HARJU_BBOX["maxlat"])


def parse_venue_rows(rows: list) -> Tuple[List[dict], dict]:
    """Map Spordiregister rows to sliced Harjumaa points (pure).

    Drops (counted): other counties, inactive status, unsliced kinds,
    coordless rows. Combo `liik` yields one point per slice.
    """
    pois: List[dict] = []
    stats = {"rows": 0, "placed": 0, "dropped_other_county": 0,
             "dropped_inactive": 0, "dropped_other_type": 0,
             "dropped_no_xy": 0}
    for row in rows:
        if not isinstance(row, dict):
            continue
        stats["rows"] += 1
        if row.get("maakond") != "Harjumaa":
            stats["dropped_other_county"] += 1
            continue
        slices = _slices_of(row.get("liik"), row.get("ehstaatus"))
        if not slices:
            if row.get("ehstaatus") != ACTIVE_STATUS:
                stats["dropped_inactive"] += 1
            else:
                stats["dropped_other_type"] += 1
            continue
        try:
            lat = float(str(row.get("kaart_laius")).replace(",", "."))
            lon = float(str(row.get("kaart_pikkus")).replace(",", "."))
        except (TypeError, ValueError):
            stats["dropped_no_xy"] += 1
            continue
        if not (math.isfinite(lat) and math.isfinite(lon)):
            stats["dropped_no_xy"] += 1
            continue
        for sl in slices:
            pois.append({"lat": lat, "lon": lon, "slice": sl})
            stats["placed"] += 1
    return pois, stats


def _xtext(el: Optional[ET.Element], tag: str) -> str:
    if el is None:
        return ""
    child = el.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def parse_ujulad_rows(root: ET.Element) -> Tuple[List[dict], dict]:
    """Map vtiav ujulad rows to pool points in the Harju window (pure).

    Every coord-carrying row places regardless of <tyyp> (access rules
    stay the buyer check — dims_p4_sportreg precedent); rows projecting
    outside HARJU_BBOX are dropped + counted (no county column exists).
    """
    pois: List[dict] = []
    stats = {"rows": 0, "placed": 0, "dropped_no_xy": 0,
             "dropped_outside_county": 0}
    for node in root.iter("ujula"):
        stats["rows"] += 1
        coord = node.find("./koordinaadid/koordinaat")
        try:
            lat, lon = lest97_to_wgs84(
                float(_xtext(coord, "x").replace(",", ".")),
                float(_xtext(coord, "y").replace(",", ".")))
        except (ValueError, TypeError, AttributeError):
            stats["dropped_no_xy"] += 1
            continue
        if not _in_harju(lat, lon):
            stats["dropped_outside_county"] += 1
            continue
        pois.append({"lat": lat, "lon": lon, "slice": "pool"})
        stats["placed"] += 1
    return pois, stats


def build_sidecar(venue_rows: list, ujulad_root: ET.Element,
                  out_dir: str) -> dict:
    """Build sport/sport-points.json from parsed bulks; returns the doc."""
    venue_pois, venue_stats = parse_venue_rows(venue_rows)
    ujulad_pois, ujulad_stats = parse_ujulad_rows(ujulad_root)
    points = venue_pois + ujulad_pois
    counts = {"hall": 0, "field": 0, "pool": 0}
    for p in points:
        counts[p["slice"]] += 1
    doc = {
        "vintage": SPORT_VINTAGE,
        "licence": "CC BY-SA 3.0 (Spordiregister/Kultuuriministeerium, Terviseamet/vtiav)",
        "accuracy": ("L-EST97 (EPSG:3301) inverse-LCC pooramine ujulate "
                     "ridadel, ~1 m tapsus; spordiregistri koordinaadid "
                     "valmis WGS84 kujul"),
        "counts": dict(counts, total=len(points)),
        "dropped": {"venues": venue_stats, "ujulad": ujulad_stats},
        "points": points,
    }
    sport_dir = os.path.join(out_dir, "sport")
    os.makedirs(sport_dir, exist_ok=True)
    with open(os.path.join(sport_dir, "sport-points.json"), "w",
              encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    return doc


def main(cache_dir: str = DEFAULT_CACHE_DIR,
         out_dir: Optional[str] = None) -> int:
    """Harvest both bulks (polite, TTL-guarded) and build the extract."""
    json_path = fetch_cached(SPORTREG_JSON_URL, cache_dir,
                             "spordiehitised.json", JSON_MIN_BYTES)
    time.sleep(SPORT_PACE_S)
    xml_path = fetch_cached(UJULAD_XML_URL, cache_dir, "ujulad.xml",
                            XML_MIN_BYTES)
    if json_path is None or xml_path is None:
        print("sport harvest incomplete (transport refused or thin body); "
              "no sidecar written")
        return 1
    with open(json_path, encoding="utf-8") as f:
        venue_rows = json.load(f)
    ujulad_root = ET.parse(xml_path).getroot()
    doc = build_sidecar(venue_rows, ujulad_root,
                        out_dir or os.path.join(cache_dir, "snapshot"))
    print("sport extract: %d points %s (vintage %s)" % (
        doc["counts"]["total"], doc["counts"], doc["vintage"]))
    print("dropped venues: %s" % (doc["dropped"]["venues"],))
    print("dropped ujulad: %s" % (doc["dropped"]["ujulad"],))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
