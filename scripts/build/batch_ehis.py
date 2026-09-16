"""EHIS school-building harvest + build (issue #608).

Polite single-fetch harvest of the EHIS buildings bulk (hooned XML,
L-EST97) joined to the institutions bulk (oppeasutused XML, type +
status), and an offline build of the Harjumaa school-point extract the
ehis_school/ehis_kindergarten/ehis_hobby map overlays serve. Stdlib
only; network lives ONLY in fetch_cached/main.

Feed verdict (2026-09-16, see services/scoring/dims_p4_ehis_map.py and
docs/p4_ehis_map.md; aggregates only, raw bodies never committed):
2180 <hoone> rows; 739 mention Harju maakond, of which 703 carry
<koordinaatX>/<koordinaatY> (L-EST97, x = northing, y = easting) +
<ehrKood> + <adsOid>/<adsAdrId>. Type map mirrors
dims_p4_ehis_map.py TYPE_SLICES exactly (pohikool voi gumnaasium ->
school; lasteaed/koolieelne lasteasutus/lastehoid -> kindergarten;
huvikool -> hobby; only Registreeritud), so map colors and scored
reasons agree by construction (pinned by tests on both sides). NO
language column exists anywhere in the 12.6 MB bulk — language slices
are impossible, documented, never guessed.

Harjumaa membership is decided by the <aadress> naming Harju maakond
(the feed's own county label, same "739 mention Harju" rule as the
verdict — reviewable, never hidden). Rows without coordinates, Suletud
/ unsliced institutions, and other counties are DROPPED (counted +
reported, never faked); transport errors are never cached as data
(fetch_cached stores only HTTP 200 bodies over a minimum size);
names/EHR/ADS codes never leave the sidecar wire (points carry
lat/lon/slice only). Licence CC BY-SA 3.0 — attribution + share-alike
ride in the layer legends and docs/p4_ehis_map.md.
"""

import math
import os
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Ingestion contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: EHIS buildings bulk (verified 2026-09-16: HTTP 200, ~1.1 MB XML).
EHIS_HOONED_URL = "http://enda.ehis.ee/avaandmed/rest/hooned"

#: EHIS institutions bulk (verified 2026-09-16: HTTP 200, ~12.6 MB XML).
EHIS_OPPEASUTUSED_URL = (
    "http://enda.ehis.ee/avaandmed/rest/oppeasutused/-/-/-/-/-/-/-/-/-/-/0/0/XML"
)

#: Buildings change slowly: at most one refresh per 90 d per cache dir.
EHIS_TTL_S = 90 * 24 * 3600

#: Identifying user agent for the polite pull (paced single GETs, no scrape).
EHIS_UA = (
    "home-finder-608-ehis/1.0 "
    "(polite quarterly harvest, paced single GETs; "
    "GitHub gregoreesmaa/home-finder issue 608)"
)

#: Seconds between harvest GETs (polite pacing on top of the TTL).
EHIS_PACE_S = 5

#: Minimum plausible bodies: hooned ~1.1 MB, oppeasutused ~12.6 MB —
#: anything smaller is an error page, never data.
HOONED_MIN_BYTES = 500_000
OPPE_MIN_BYTES = 5_000_000

#: Vintage stamped on the extract (harvest date, re-verified per pull).
EHIS_VINTAGE = "2026-09-16"

#: Default cache dir (raw bulks live here; /tmp only, AGENTS.md 5).
DEFAULT_CACHE_DIR = os.path.join("/tmp", "hf-608-ehis")

#: Institution type -> slice, mirroring dims_p4_ehis_map.TYPE_SLICES
#: (diacritics folded the same way). Only Registreeritud places.
TYPE_SLICES = {
    "pohikool voi gumnaasium": "school",
    "lasteaed": "kindergarten",
    "koolieelne lasteasutus": "kindergarten",
    "lastehoid": "kindergarten",
    "huvikool": "hobby",
}
ACTIVE_STATUS = "Registreeritud"


def fetch_cached(url: str, cache_dir: str, filename: str,
                 min_bytes: int,
                 ttl_s: int = EHIS_TTL_S) -> Optional[str]:
    """Polite single-GET pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made. Otherwise
    one GET with EHIS_UA and a 60 s timeout; the body is stored only on
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
    req = urllib.request.Request(url, headers={"User-Agent": EHIS_UA})
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

    EHIS convention: <koordinaatX> is the northing, <koordinaatY> the
    easting. Raises ValueError on non-finite input (callers drop such
    rows, never fake them).
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
# Pure offline readers (hermetic, pinned by test_batch_ehis.py).
# ---------------------------------------------------------------------------

def _fold(s: str) -> str:
    return (s.strip().lower().replace("õ", "o").replace("ü", "u")
            .replace("ö", "o").replace("ä", "a"))


def _xtext(el: Optional[ET.Element], tag: str) -> str:
    if el is None:
        return ""
    child = el.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def parse_type_map(root: ET.Element) -> Dict[str, dict]:
    """Map oppeasutusId -> {tyyp, status, slice} (dims_p4_ehis_map shape).

    Slice is None for Suletud / unsliced types (never scored); status is
    kept so closed institutions count honestly instead of vanishing.
    """
    out: Dict[str, dict] = {}
    for node in root.iter("oppeasutus"):
        kid = _xtext(node, "koolId")
        if not kid:
            continue
        staatus = _xtext(node, "staatus")
        tyyp = _xtext(node, "tyyp")
        sl = (TYPE_SLICES.get(_fold(tyyp))
              if staatus == ACTIVE_STATUS else None)
        out[kid] = {"tyyp": tyyp, "status": staatus, "slice": sl}
    return out


def parse_hooned_rows(root: ET.Element,
                      type_by_id: Dict[str, dict]
                      ) -> Tuple[List[dict], dict]:
    """Join <hoone> rows to slices via <oppeasutusId>, Harju only (pure).

    Harjumaa membership = <aadress> naming Harju maakond (the feed's own
    county label). Drops (counted): other counties, closed/unsliced
    institutions, coordless rows. Every sliced building places
    (dims_p4_ehis_map precedent — peahoone is NOT a filter).
    """
    pois: List[dict] = []
    stats = {"rows": 0, "placed": 0, "dropped_other_county": 0,
             "dropped_closed": 0, "dropped_other_type": 0,
             "dropped_no_xy": 0}
    for kool in root.iter("kool"):
        info = type_by_id.get(_xtext(kool, "oppeasutusId"), {})
        sl = info.get("slice")
        for home in kool.findall("./hooned/hoone"):
            stats["rows"] += 1
            if sl is None:
                if info.get("status") and info.get("status") != ACTIVE_STATUS:
                    stats["dropped_closed"] += 1
                else:
                    stats["dropped_other_type"] += 1
                continue
            if "Harju maakond" not in _xtext(home, "aadress"):
                stats["dropped_other_county"] += 1
                continue
            try:
                lat, lon = lest97_to_wgs84(
                    float(_xtext(home, "koordinaatX").replace(",", ".")),
                    float(_xtext(home, "koordinaatY").replace(",", ".")))
            except (ValueError, TypeError):
                stats["dropped_no_xy"] += 1
                continue
            pois.append({"lat": lat, "lon": lon, "slice": sl})
            stats["placed"] += 1
    return pois, stats


def build_sidecar(oppe_root: ET.Element, hooned_root: ET.Element,
                   out_dir: str) -> dict:
    """Build ehis/ehis-points.json from parsed bulks; returns the doc."""
    import json
    pois, stats = parse_hooned_rows(hooned_root, parse_type_map(oppe_root))
    counts = {"school": 0, "kindergarten": 0, "hobby": 0}
    for p in pois:
        counts[p["slice"]] += 1
    doc = {
        "vintage": EHIS_VINTAGE,
        "licence": "CC BY-SA 3.0 (EHIS / Haridus- ja Teadusministeerium)",
        "accuracy": ("L-EST97 (EPSG:3301) inverse-LCC pooramine, "
                     "GRS80~WGS84 daatumi vahe ~1 m"),
        "counts": dict(counts, total=len(pois)),
        "dropped": stats,
        "points": pois,
    }
    ehis_dir = os.path.join(out_dir, "ehis")
    os.makedirs(ehis_dir, exist_ok=True)
    with open(os.path.join(ehis_dir, "ehis-points.json"), "w",
              encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    return doc


def main(cache_dir: str = DEFAULT_CACHE_DIR,
         out_dir: Optional[str] = None) -> int:
    """Harvest both bulks (polite, TTL-guarded) and build the extract."""
    hooned_path = fetch_cached(EHIS_HOONED_URL, cache_dir, "hooned.xml",
                               HOONED_MIN_BYTES)
    time.sleep(EHIS_PACE_S)
    oppe_path = fetch_cached(EHIS_OPPEASUTUSED_URL, cache_dir,
                             "oppeasutused.xml", OPPE_MIN_BYTES)
    if hooned_path is None or oppe_path is None:
        print("ehis harvest incomplete (transport refused or thin body); "
              "no sidecar written")
        return 1
    hooned_root = ET.parse(hooned_path).getroot()
    oppe_root = ET.parse(oppe_path).getroot()
    doc = build_sidecar(oppe_root, hooned_root,
                        out_dir or os.path.join(cache_dir, "snapshot"))
    print("ehis extract: %d points %s (vintage %s)" % (
        doc["counts"]["total"], doc["counts"], doc["vintage"]))
    print("dropped: %s" % (doc["dropped"],))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
