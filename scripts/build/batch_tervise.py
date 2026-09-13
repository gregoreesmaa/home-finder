"""Terviseamet bathing-water (suplusvesi) harvest + build (issue #494).

Polite single-fetch harvest of the vtiav.sm.ee "Avaandmed" bulk XML feeds
(supluskohad.xml + yearly supluskoha_veeproovid_YYYY.xml) and an offline
build of the bathing-site monitoring-point extract the `tervise` map
overlay serves. Stdlib only; network lives ONLY in fetch_cached/main.

Feed verdict (2026-09-14, polite harvest, custom UA, paced single GETs,
HTTP 429 is a stop signal — AGENTS.md 7.4): the "Avaandmed" JS tab IS a
bulk machine feed (yearly XML + XSD + PDF per dataset), so PR #510's
"no machine feed" verdict was wrong for the P4-024 bathing-water slice.
The P4-017 drinking-water slice stays human-only (per-veevark lookup UI,
no bulk export) and its scorer dim stays NULL in dims_p4_tervise.py.

Coordinates are L-EST97 metres (EPSG:3301: x = northing ~6.4-6.6M,
y = easting ~0.37-0.74M — magnitudes + the #490 Transpordiamet family
precedent), projected here with a LABELLED inverse Lambert Conformal
Conic 2SP (Maa-amet/EPSG constants below). The projection math is exact;
the GRS80(ETRS89)~WGS84 datum gap drifts ~1 m, so every projected point
is honest to ~1 m — stated on the extract + in layers_tervise.ts, never
hidden. Verified 2026-09-14: this module's projection agrees with
pyproj EPSG:3301->EPSG:4326 to <1 mm on all 320 feed coordinates, and
Pirita (59.4722, 24.8310) / Stroomi (59.4425, 24.6839) / Kakumae
(59.4483, 24.5744) land on their beaches.

Honesty (AGENTS.md 7.2): sites without coordinates are DROPPED from the
extract (counted + reported, never faked); per-point quality is NULL
where the samples do not support it; a fresh "ei vasta noutele" sample
caps the band at 30 with its date; transport errors are never cached as
data (fetch_cached stores only HTTP 200 bodies over a minimum size).
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

#: Bathing-site register (verified 2026-09-14: HTTP 200, ~314 KB XML).
TERVISE_SITES_URL = (
    "https://vtiav.sm.ee/index.php/opendata/supluskohad.xml"
)

#: Yearly water-sample bulks (verified 2026-09-14: HTTP 200, ~0.9 MB each).
TERVISE_SAMPLES_URLS = {
    2026: "https://vtiav.sm.ee/index.php/opendata/supluskoha_veeproovid_2026.xml",
    2025: "https://vtiav.sm.ee/index.php/opendata/supluskoha_veeproovid_2025.xml",
}

#: The feed is a yearly vintage: at most one refresh per 365 d per cache dir.
TERVISE_TTL_S = 365 * 24 * 3600

#: Identifying user agent for the polite pull (paced single GETs, no scrape).
TERVISE_UA = (
    "home-finder-494-tervise-xml/1.0 "
    "(polite yearly harvest, paced single GETs; "
    "GitHub gregoreesmaa/home-finder issue 494)"
)

#: Seconds between harvest GETs (polite pacing on top of the yearly TTL).
TERVISE_PACE_S = 5

#: Minimum plausible XML body: the live register alone is ~314 KB, so
#: anything smaller is an error page, never data.
XML_MIN_BYTES = 100_000

#: Default cache dir (raw XML lives here; /tmp + fixtures only, AGENTS.md 5).
DEFAULT_CACHE_DIR = os.path.join("/tmp", "hf-494-tervise-xml")


def fetch_cached(url: str, cache_dir: str, filename: str,
                 ttl_s: int = TERVISE_TTL_S) -> Optional[str]:
    """Polite single-GET pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made. Otherwise
    one GET with TERVISE_UA and a 60 s timeout; the body is stored only on
    HTTP 200 with at least XML_MIN_BYTES bytes, else None is returned
    and nothing is cached (transport errors are never data). No retries
    - HTTP 429/errors are a stop signal. Scorers never call this; tests
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
    req = urllib.request.Request(url, headers={"User-Agent": TERVISE_UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
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


# ---------------------------------------------------------------------------
# L-EST97 (EPSG:3301) -> WGS84, labelled approximate (~1 m).
# ---------------------------------------------------------------------------

#: GRS80 ellipsoid (L-EST97 datum; ETRS89, drifts ~1 m from WGS84 Gxxx).
_LEST_A = 6378137.0
_LEST_F = 1 / 298.257222101
_LEST_E2 = 2 * _LEST_F - _LEST_F * _LEST_F
_LEST_E = math.sqrt(_LEST_E2)

#: L-EST97 projection constants (Maa-amet / EPSG:3301 registry).
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

#: Accuracy label stamped on every extract (reviewable, never hidden).
LEST97_ACCURACY_LABEL = (
    "L-EST97 (EPSG:3301) inverse-LCC poordumine, GRS80~WGS84 "
    "daatumi vahe ~1 m — punktid on ausad ~1 m tapsusega"
)


def lest97_to_wgs84(northing: float, easting: float) -> Tuple[float, float]:
    """Project L-EST97 metres to (lat, lon). Labelled ~1 m (see above).

    Feed convention: <x> is the northing (~6.4-6.6M), <y> the easting
    (~0.37-0.74M). Raises ValueError on non-finite input (callers drop
    such sites, never fake them).
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
# Pure offline readers (hermetic, pinned by test_batch_tervise.py).
# ---------------------------------------------------------------------------

def _text(el: Optional[ET.Element], tag: str) -> str:
    if el is None:
        return ""
    child = el.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def parse_supluskohad_xml(text: str) -> List[dict]:
    """Parse the site register. One dict per <supluskoht> (raw strings)."""
    root = ET.fromstring(text)
    sites = []
    for sc in root.iter("supluskoht"):
        coord = sc.find("./koordinaadid/koordinaat")
        sites.append({
            "id": _text(sc, "id"),
            "name": _text(sc, "nimetus"),
            "water": _text(sc, "veekogu_nimi"),
            "water_type": _text(sc, "veekogu_tyyp"),
            "x": _text(coord, "x") if coord is not None else "",
            "y": _text(coord, "y") if coord is not None else "",
            "last_sample": _text(sc, "viimane_proovivott"),
            "quality_now": _text(sc, "veekvaliteet"),
            "quality_class": _text(sc, "suplusvee_kvaliteediklass"),
        })
    return sites


def parse_veeproovid_xml(text: str) -> List[dict]:
    """Parse one yearly sample bulk. One dict per <katseprotokoll>."""
    root = ET.fromstring(text)
    out = []
    for pv in root.iter("proovivott"):
        site_id = _text(pv, "supluskoht_id")
        taken = _text(pv, "proovivotu_aeg")  # "25.08.2026 00:00"
        for kp in pv.findall("./katseprotokollid/katseprotokoll"):
            out.append({
                "site_id": site_id,
                "date": taken.split(" ")[0] if taken else "",
                "ok": _text(kp, "hinnang") == "vastab n\u00f5uetele",
                "raw": _text(kp, "hinnang"),
            })
    return out


def _parse_estonian_date(s: str) -> Tuple[int, int, int]:
    """DD.MM.YYYY -> (YYYY, MM, DD); unparseable -> (0, 0, 0) (sorts first)."""
    try:
        d, m, y = s.split(".")
        return int(y), int(m), int(d)
    except (ValueError, AttributeError):
        return (0, 0, 0)


def latest_sample_by_site(samples: List[dict]) -> Dict[str, dict]:
    """Latest dated protocol verdict per site id.

    A site event fails when ANY of its protocols reads "ei vasta
    noutele" (single failing indicator fails the sample — the Anne kanal
    2026-08-25 precedent: one seirepunkt fails, the other passes).
    Undated rows never outrank dated ones.
    """
    best: Dict[str, dict] = {}
    for s in samples:
        if not s["site_id"]:
            continue
        key = (_parse_estonian_date(s["date"]), s["date"])
        cur = best.get(s["site_id"])
        if cur is None or key > cur["_key"]:
            best[s["site_id"]] = {"date": s["date"], "ok": s["ok"], "_key": key}
        elif key == cur["_key"] and not s["ok"]:
            cur["ok"] = False
    for v in best.values():
        v.pop("_key", None)
    return best


#: Seasonal/current grade -> coarse band (cap 80: amenity proximity is
#: never a 100; unknown is None, never a faked middle).
GRADE_BANDS = {
    "v\u00e4ga hea": 80,
    "hea": 70,
    "piisav": 60,
    "kesine": 45,
    "halb": 30,
}

#: Fresh sample failure caps the band (dated negative evidence beats an
#: older class — reviewable judgment call, stated not hidden).
SAMPLE_FAIL_CAP = 30

#: No quality signal at all: monitored water nearby, grade unknown.
UNKNOWN_BAND = 60


def quality_band(quality_class: str, quality_now: str,
                 latest: Optional[dict]) -> Tuple[Optional[int], str]:
    """Effective (band, Estonian reason) for one site. Band None = NULL."""
    base: Optional[int] = None
    base_reason = ""
    cls = (quality_class.split("-", 1)[-1].strip().lower()
           if "-" in quality_class else "")
    if cls in GRADE_BANDS:
        base = GRADE_BANDS[cls]
        base_reason = "kvaliteediklass %s" % quality_class.strip()
    elif quality_now.strip().lower() in GRADE_BANDS:
        base = GRADE_BANDS[quality_now.strip().lower()]
        base_reason = "veekvaliteet %s" % quality_now.strip()
    if latest and latest.get("date"):
        if not latest["ok"]:
            capped = SAMPLE_FAIL_CAP if base is None else min(base, SAMPLE_FAIL_CAP)
            return capped, ("viimane proov %s ei vasta n\u00f5uetele"
                            % latest["date"])
        if base is None:
            return 70, ("viimane proov %s vastab n\u00f5uetele, klass m\u00e4\u00e4ramata"
                        % latest["date"])
        return base, "%s; viimane proov %s vastab" % (base_reason, latest["date"])
    if base is not None:
        return base, base_reason
    return None, "kvaliteet teadmata (proovid + klass puuduvad)"


def build_points(sites: List[dict],
                 latest: Dict[str, dict]) -> Tuple[List[dict], dict]:
    """Project sites to WGS84 extract points. Returns (points, stats).

    Sites without finite L-EST97 coordinates are dropped (counted in
    stats, never faked). Quality rides as q (None = NULL).
    """
    points = []
    stats = {"sites": len(sites), "plotted": 0, "dropped_no_coord": 0,
             "quality_null": 0, "duplicate_coords": 0}
    seen = set()
    for s in sites:
        try:
            lat, lon = lest97_to_wgs84(float(s["x"]), float(s["y"]))
        except (ValueError, TypeError):
            stats["dropped_no_coord"] += 1
            continue
        band, reason = quality_band(s["quality_class"], s["quality_now"],
                                    latest.get(s["id"]))
        if band is None:
            stats["quality_null"] += 1
        key = (round(lat, 6), round(lon, 6))
        # Distinct register rows may share feed coordinates (2026-09-14:
        # Haapsalu 124 Aafrika rand + 165 Vaike-Viik carry identical
        # raw x/y). Both rows are kept (the register says two sites);
        # the counter names the quirk for the reviewer.
        if key in seen:
            stats["duplicate_coords"] += 1
        seen.add(key)
        points.append({
            "id": s["id"],
            "name": s["name"],
            "lat": key[0],
            "lon": key[1],
            "q": band,
            "grade": reason,
            "last_sample": s["last_sample"] or None,
        })
        stats["plotted"] += 1
    return points, stats


def build_extract(sites: List[dict], samples: List[dict],
                  vintage: str) -> dict:
    """Full offline build: join + project. Pure (no network, no disk)."""
    latest = latest_sample_by_site(samples)
    points, stats = build_points(sites, latest)
    return {
        "fetched": vintage,
        "vintage": vintage,
        "transform": LEST97_ACCURACY_LABEL,
        "sources": {
            "sites": TERVISE_SITES_URL,
            "samples": sorted(TERVISE_SAMPLES_URLS.values()),
        },
        "stats": stats,
        "points": points,
    }


def main() -> int:
    """Polite harvest (paced single GETs, 429 = stop) + extract build."""
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    ap.add_argument("--out", default=None,
                    help="extract JSON path (default: <cache-dir>/tervise-extract.json)")
    ap.add_argument("--vintage", default="2026-09-14",
                    help="vintage label stamped on the extract")
    args = ap.parse_args()

    sites_path = fetch_cached(TERVISE_SITES_URL, args.cache_dir,
                              "supluskohad.xml")
    if sites_path is None:
        print("STOP: supluskohad.xml fetch failed (see headers in cache dir)")
        return 1
    time.sleep(TERVISE_PACE_S)
    samples: List[dict] = []
    for year in sorted(TERVISE_SAMPLES_URLS):
        p = fetch_cached(TERVISE_SAMPLES_URLS[year], args.cache_dir,
                         "supluskoha_veeproovid_%d.xml" % year)
        if p is None:
            print("STOP: samples %d fetch failed" % year)
            return 1
        with open(p, encoding="utf-8") as f:
            samples.extend(parse_veeproovid_xml(f.read()))
        time.sleep(TERVISE_PACE_S)

    with open(sites_path, encoding="utf-8") as f:
        sites = parse_supluskohad_xml(f.read())
    extract = build_extract(sites, samples, args.vintage)
    out = args.out or os.path.join(args.cache_dir, "tervise-extract.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(extract, f, ensure_ascii=False, indent=1)
    print("sites=%d plotted=%d dropped_no_coord=%d quality_null=%d "
          "samples=%d -> %s"
          % (extract["stats"]["sites"], extract["stats"]["plotted"],
             extract["stats"]["dropped_no_coord"],
             extract["stats"]["quality_null"], len(samples), out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
