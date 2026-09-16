"""P4 Seveso hazard-avoidance dim (issue #527, measured zone-membership).

Source: Rescue Board (Paasteamet) major-accident-hazard + dangerous
enterprises register via opendata.smit.ee (weekly CSV/GPKG).
Licence CC_BY_NC_ND_4.0 per the national catalogue (attribute
Paasteamet; keep raw snapshots unmodified; no modified redistribution
of raw data — fixtures below are fully synthetic).

OPENNESS (probed 2026-09-16, one polite round, UA
home-finder-idea-probe/1.0, paced >= 3 s, cached to /tmp/hf-526-529-probe,
full evidence in docs/p4_seveso.md):
* ohtlikud_kaitised.csv: HTTP 200, 88 598 B, 238 rows (98 Harju).
  ;-separated: nimi, kaitise_id, aadress, x/y_tegevuskoht (L-EST97),
  x/y_ohuallikas (L-EST97), kaitise_ohtlikkus (A/B/C: 44/37/157),
  tegevusala, doomino_efekt, ohu_tuup (Soojuskiirgus 180,
  Murgised ained 40, Ulerohk 14), kemikaalid, infovoldik,
  lon/lat_ohuallikas (WGS84).
* ohtlikud_kaitised_ohualad.csv: HTTP 200, 355 065 B, 235 rows
  (95 Harju) with WKT danger-area POLYGONs (L-EST97) + raadius.
  Same ohu_tuup distribution (heat 182, toxic 40, overpressure 13).
* Dual-coordinate oracle: all 238 point rows carry BOTH L-EST97 and
  WGS84 — lest97_to_wgs84 reproduces the published WGS84 within
  6.1 cm worst-case (local check, see docs/p4_seveso.md).

HONESTY (AGENTS.md 7.2): danger POLYGONS are the join (flood-table
#487 / EELIS-polygon #488 precedent). Inside a danger polygon scores
low by danger type; outside every polygon is NULL (teadmata, never
"safe") — absence of a registered polygon is not absence of risk.
Point-buffer fallback only with stated per-type radii (observed
ohualad medians, see below). Transport errors are never cached as
data; HTTP 429 stops the run.

Style mirrors services/scoring/dims_p4_paaste_register.py (#523):
pure offline scorers, stdlib-only, local helpers (no sibling imports
— a future central hook may import this module alongside the others).

Judgment calls (reviewable per AGENTS.md 7.5):
* DANGER_SCORES: toxic ("Murgised ained") -> 20, heat
  ("Soojuskiirgus") and overpressure ("Ulerohk") -> 35,
  combustion-promoting ("polem..."/combustion) -> 50 (value NOT
  observed on 2026-09-16 — kept for the catalogue's stated domain),
  unknown text -> 30 (inside a published polygon with an unmapped
  label still reads as hazard, never neutral). Mixed labels
  ("Murgised ained, Soojuskiirgus", observed 4x in points) score the
  binding (lowest) leg.
* FALLBACK_RADII_M are the observed ohualad raadius medians per type
  (toxic 342 -> 350, heat 177.5 -> 180, overpressure 108 -> 110,
  unknown -> 200), rounded up. Point fallback applies ONLY when the
  snapshot carries zero polygons.
* Overlapping polygons score the worst (minimum) — a buyer next to
  two danger areas is not safer than next to one.
* WKT parse keeps the outer ring only; holes are ignored (fail-safe:
  ignoring a hole can only over-cover, never under-cover).
* L-EST97 vertices project via the labelled ~1 m inverse-LCC port
  (batch_tervise.py #511 / batch_accblack.py #522, same constants;
  copied, not imported — per-issue files stay rebase-safe).

Integration (deliberately NOT done here): livability hook +
WEIGHTS rebalance stay one joint change across batches (existing
tests pin set(WEIGHTS)). No shared files touched: 3 new files only.
"""

import csv
import io
import math
import os
import re
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion contract: source identity, politeness, cache.
# ---------------------------------------------------------------------------

#: Enterprise points (verified 2026-09-16: HTTP 200, 88 598 B, 238 rows).
SEVESO_POINTS_URL = "https://opendata.smit.ee/gis/ohtlikud_kaitised.csv"
#: Danger-area polygons (verified 2026-09-16: HTTP 200, 355 065 B, 235 rows).
SEVESO_DANGER_URL = (
    "https://opendata.smit.ee/gis/ohtlikud_kaitised_ohualad.csv"
)
SEVESO_USER_AGENT = (
    "home-finder-p4-seveso/1.0 (Estonia open-data weekly adapter; "
    "polite single-pull, cache-first)"
)
#: Publisher updates weekly: at most one live pull per week.
SEVESO_CACHE_TTL_S = 7 * 86400
SEVESO_POINTS_CACHE_NAME = "ohtlikud_kaitised.csv"
SEVESO_DANGER_CACHE_NAME = "ohtlikud_kaitised_ohualad.csv"

#: Inside-polygon scores by danger type (binding leg wins on mixed labels).
DANGER_SCORES = {
    "toxic": 20,        # Murgised ained
    "heat": 35,         # Soojuskiirgus
    "overpressure": 35,  # Ulerohk
    "combustion": 50,   # polem... (catalogue domain; unobserved 2026-09-16)
    "unknown": 30,      # unmapped label inside a polygon: hazard, never neutral
}

#: Point-fallback radii per danger class = observed ohualad raadius
#: medians per ohu_tuup, rounded up (toxic 342, heat 177.5,
#: overpressure 108; unknown 200). Polygons preferred; these apply
#: only when the snapshot carries zero polygons.
FALLBACK_RADII_M = {
    "toxic": 350.0,
    "heat": 180.0,
    "overpressure": 110.0,
    "combustion": 200.0,
    "unknown": 200.0,
}


# ---------------------------------------------------------------------------
# Local pure helpers (livability-shaped; see module docstring for why local).
# ---------------------------------------------------------------------------

def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Great-circle distance in km between two (lat, lon) points (pure)."""
    r = 6371.0
    la1, la2 = math.radians(a[0]), math.radians(b[0])
    dla = math.radians(b[0] - a[0])
    dlo = math.radians(b[1] - a[1])
    h = (math.sin(dla / 2.0) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2.0) ** 2)
    return 2.0 * r * math.asin(min(1.0, math.sqrt(h)))


# --- L-EST97 (EPSG:3301) -> WGS84, labelled approximate (~1 m). Ported
# from scripts/build/batch_tervise.py::lest97_to_wgs84 (#511, verified
# <1 mm vs pyproj there) via scripts/build/batch_accblack.py (#522).
# Same constants, same datum label. Copied, not imported: per-issue
# files stay rebase-safe against unmerged siblings. ---

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

#: Accuracy label stamped on projected points (reviewable, never hidden).
LEST97_ACCURACY_LABEL = (
    "L-EST97 (EPSG:3301) inverse-LCC poordumine, GRS80~WGS84 "
    "daatumi vahe ~1 m — punktid on ausad ~1 m tapsusega"
)


def lest97_to_wgs84(northing: float, easting: float) -> Tuple[float, float]:
    """Project L-EST97 metres to (lat, lon). Labelled ~1 m (see above).

    Register convention: x_* columns are the northing (~6.4-6.6M),
    y_* columns the easting (~0.34-0.74M). Raises ValueError on
    non-finite input (callers drop such rows, never fake them).
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


def classify_danger(raw: Optional[str]) -> str:
    """Map an ohu_tuup label to a DANGER_SCORES key (pure, fail-closed).

    Mixed labels ("Murgised ained, Soojuskiirgus") classify binding:
    toxic wins over heat/overpressure over combustion over unknown.
    """
    text = (raw or "").lower()
    if "mürgised" in text or "murgised" in text:
        return "toxic"
    if "ülerõhk" in text or "ulerohk" in text:
        return "overpressure"
    if "soojus" in text:
        return "heat"
    if "põlem" in text or "polem" in text or "combust" in text:
        return "combustion"
    return "unknown"


_NUM_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


def _fnum(value: object) -> Optional[float]:
    try:
        text = str(value).strip().replace(" ", "").replace(",", ".")
    except (TypeError, AttributeError):
        return None
    if not text:
        return None
    try:
        v = float(text)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


_WKT_RING_RE = re.compile(
    r"POLYGON\s*\(\(\s*([^()]*?)\)", re.IGNORECASE | re.DOTALL)


def _parse_wkt_outer_ring(wkt: str) -> List[Tuple[float, float]]:
    """Parse a POLYGON WKT outer ring to [(easting, northing)] (pure).

    Keeps the outer ring only (holes ignored — fail-safe towards
    over-coverage, see module docstring). Unparseable WKT reads as [].
    """
    m = _WKT_RING_RE.search(wkt or "")
    if not m:
        return []
    ring: List[Tuple[float, float]] = []
    for pair in m.group(1).split(","):
        nums = _NUM_RE.findall(pair)
        if len(nums) < 2:
            continue
        try:
            ring.append((float(nums[0].replace(",", ".")),
                         float(nums[1].replace(",", "."))))
        except ValueError:
            continue
    return ring


def _project_ring_lest97(ring: List[Tuple[float, float]]
                         ) -> List[Tuple[float, float]]:
    """Project an L-EST97 (easting, northing) ring to [(lat, lon)] (pure).

    Vertices that fail to project are dropped; a ring left with fewer
    than 4 vertices reads as unusable (callers skip it, never fake it).
    """
    out: List[Tuple[float, float]] = []
    for easting, northing in ring:
        try:
            out.append(lest97_to_wgs84(northing, easting))
        except ValueError:
            continue
    return out


def point_in_ring(lat: float, lon: float,
                  ring: List[Tuple[float, float]]) -> bool:
    """Ray-casting containment of (lat, lon) in a [(lat, lon)] ring (pure)."""
    inside = False
    n = len(ring)
    if n < 4:
        return False
    j = n - 1
    for i in range(n):
        yi, xi = ring[i]
        yj, xj = ring[j]
        if ((yi > lat) != (yj > lat)
                and lon < (xj - xi) * (lat - yi) / (yi - yj or 1e-300) + xi):
            inside = not inside
        j = i
    return inside


# ---------------------------------------------------------------------------
# Ingestion: polite cached pull (live path, NOT unit-run) + pure parse.
# ---------------------------------------------------------------------------

def _cache_paths(cache_dir: str) -> Tuple[str, str]:
    return (os.path.join(cache_dir, SEVESO_POINTS_CACHE_NAME),
            os.path.join(cache_dir, SEVESO_DANGER_CACHE_NAME))


def cache_is_fresh(path: str, ttl_s: int = SEVESO_CACHE_TTL_S,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_s."""
    try:
        age_s = (now if now is not None else time.time()) - os.path.getmtime(path)
    except OSError:
        return False
    return age_s < ttl_s


def _pull(url: str, path: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": SEVESO_USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        if resp.status == 429:
            raise RuntimeError("Päästeamet/opendata vastas 429 — peatu, ara reetry")
        if resp.status != 200:
            raise RuntimeError(
                "opendata.smit.ee vastas HTTP %s — vahemalu puutumata" % resp.status
            )
        body = resp.read().decode("utf-8-sig", errors="replace")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return body


def fetch_seveso_snapshot(
    cache_dir: Optional[str] = None,
    ttl_s: int = SEVESO_CACHE_TTL_S,
) -> Tuple[dict, str]:
    """Polite cached pull of both Seveso CSVs (live path, NOT unit-run).

    Fresh cache wins per file (no request). Any transport error raises
    and cached files are left untouched — transport errors are never
    cached as data, and 429 stops the run. Returns (snapshot, provenance)
    with provenance "cache" or "live".
    """
    if cache_dir is None:
        cache_dir = os.path.join("/tmp", "hf-seveso-cache")
    os.makedirs(cache_dir, exist_ok=True)
    points_path, danger_path = _cache_paths(cache_dir)
    provenance = "cache"
    texts = []
    for url, path in ((SEVESO_POINTS_URL, points_path),
                      (SEVESO_DANGER_URL, danger_path)):
        if cache_is_fresh(path, ttl_s):
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                texts.append(fh.read())
            continue
        texts.append(_pull(url, path))
        provenance = "live"
    snapshot = {
        "points": parse_points_csv(texts[0]),
        "areas": parse_danger_csv(texts[1]),
        "fetched": time.strftime("%Y-%m-%d", time.gmtime()),
        "source": "Päästeameti ohtlike ettevõtete register (opendata.smit.ee)",
    }
    return snapshot, provenance


def _point_latlon(row: dict) -> Tuple[Optional[float], Optional[float]]:
    """Best WGS84 for a points row: published lon/lat, else projected L-EST97."""
    lat = _fnum(row.get("lat_ohuallikas"))
    lon = _fnum(row.get("lon_ohuallikas"))
    if lat is not None and lon is not None:
        return lat, lon
    xn = _fnum(row.get("x_ohuallikas"))
    ye = _fnum(row.get("y_ohuallikas"))
    if xn is None or ye is None:
        return None, None
    try:
        return lest97_to_wgs84(xn, ye)
    except ValueError:
        return None, None


def parse_points_csv(csv_text: str) -> List[dict]:
    """Parse ohtlikud_kaitised.csv into point rows (pure).

    ;-separated, BOM-tolerant. Rows without any usable coordinate are
    skipped (counted by summarize_snapshot, never zero-filled).
    """
    reader = csv.DictReader(io.StringIO((csv_text or "").lstrip("\ufeff")),
                            delimiter=";")
    out: List[dict] = []
    for row in reader:
        lat, lon = _point_latlon(row)
        if lat is None or lon is None:
            continue
        domino = str(row.get("doomino_efekt") or "").strip().lower() == "true"
        out.append({
            "name": (row.get("nimi") or "").strip(),
            "address": (row.get("aadress") or "").strip(),
            "lat": lat,
            "lon": lon,
            "danger": classify_danger(row.get("ohu_tuup")),
            "danger_label": (row.get("ohu_tuup") or "").strip(),
            "chemicals": (row.get("kemikaalid") or "").strip(),
            "leaflet": (row.get("infovoldik") or "").strip(),
            "domino": domino,
            "transform": LEST97_ACCURACY_LABEL,
        })
    return out


def parse_danger_csv(csv_text: str) -> List[dict]:
    """Parse ohtlikud_kaitised_ohualad.csv into danger areas (pure).

    WKT polygons (L-EST97) project to WGS84 rings once, here — the dim
    only ray-casts. Rows with unusable rings are skipped (counted by
    summarize_snapshot, never faked).
    """
    reader = csv.DictReader(io.StringIO((csv_text or "").lstrip("\ufeff")),
                            delimiter=";")
    out: List[dict] = []
    for row in reader:
        ring = _project_ring_lest97(
            _parse_wkt_outer_ring(row.get("WKT") or ""))
        if len(ring) < 4:
            continue
        lats = [p[0] for p in ring]
        lons = [p[1] for p in ring]
        domino = str(row.get("doomino_efekt") or "").strip().lower() == "true"
        out.append({
            "name": (row.get("nimi") or "").strip(),
            "address": (row.get("aadress") or "").strip(),
            "danger": classify_danger(row.get("ohu_tuup")),
            "danger_label": (row.get("ohu_tuup") or "").strip(),
            "radius_m": _fnum(row.get("raadius")),
            "chemicals": (row.get("kemikaalid") or "").strip(),
            "leaflet": (row.get("infovoldik") or "").strip(),
            "domino": domino,
            "ring": ring,
            "bbox": (min(lats), min(lons), max(lats), max(lons)),
            "transform": LEST97_ACCURACY_LABEL,
        })
    return out


def summarize_snapshot(points_text: str, danger_text: str) -> dict:
    """Honest counts for a CSV pair: parsed / skipped / Harju (pure)."""
    points = parse_points_csv(points_text)
    areas = parse_danger_csv(danger_text)
    return {
        "points": len(points),
        "areas": len(areas),
        "harju_points": sum(1 for p in points if "Harju" in p["address"]),
        "harju_areas": sum(1 for a in areas if "Harju" in a["address"]),
    }


# ---------------------------------------------------------------------------
# Scorer: zone-membership overlay (polygons preferred, point fallback).
# ---------------------------------------------------------------------------

def _in_bbox(lat: float, lon: float, bbox: Tuple[float, float, float, float]
             ) -> bool:
    la0, lo0, la1, lo1 = bbox
    return la0 <= lat <= la1 and lo0 <= lon <= lo1


def dim_seveso_zone(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]] = None,
                    danger: Optional[dict] = None) -> Score:
    """Seveso danger-area membership: inside scores low, outside NULLs.

    `danger` is the snapshot from fetch_seveso_snapshot (areas +
    points). `pois` is accepted for the uniform scorer shape and
    ignored — Seveso areas are not OSM POIs.
    """
    _ = pois
    snap = danger if isinstance(danger, dict) else None
    if not origin:
        return None, ("Seveso ohuala teadmata (EI OLE hinnangut): aadress "
                      "puudub — Päästeameti ohtlike ettevõtete ohualade "
                      "(Muuga, Väo, Suur-Sõjamäe) kaugus selgub aadressi "
                      "asendi, mitte tuhjalt")
    areas = [a for a in (snap or {}).get("areas", []) if isinstance(a, dict)]
    points = [p for p in (snap or {}).get("points", []) if isinstance(p, dict)]
    if not areas and not points:
        return None, ("Seveso ohuala teadmata (EI OLE hinnangut): ohualade "
                      "hetktõmmist pole — Päästeameti ohtlike ettevõtete "
                      "register (opendata.smit.ee, CC BY-NC-ND, iganädalane) "
                      "selgub nädala väljavõttest; kontrolli ettevõtte "
                      "infovoldikut ja Päästeameti teavitust kohapeal")
    lat, lon = origin
    if areas:
        hits = [a for a in areas
                if _in_bbox(lat, lon, a.get("bbox", (0, 0, 0, 0)))
                and point_in_ring(lat, lon, a.get("ring", []))]
        if hits:
            hits.sort(key=lambda a: DANGER_SCORES.get(a.get("danger"),
                                                      DANGER_SCORES["unknown"]))
            worst = hits[0]
            score = DANGER_SCORES.get(worst.get("danger"),
                                      DANGER_SCORES["unknown"])
            extra = ("; doominoseos võimalik" if worst.get("domino") else "")
            return score, ("Seveso ohualas (hinnang — valtimiskiht, mitte "
                           "mõõdetud risk): %s, ohutüüp «%s»%s — tutvu "
                           "ettevõtte infovoldikuga ja Päästeameti "
                           "kaitumisjuhistega enne broneerimist"
                           % (worst.get("name") or "teadmata ettevõte",
                              worst.get("danger_label") or "teadmata",
                              extra))
        return None, ("Seveso ohuala teadmata (EI OLE hinnangut): aadress "
                      "ei jää ühtegi registreeritud ohualasse — alade "
                      "puudumine ei ole ohutuse hinnang; Muuga/Vao/Suur-"
                      "Sõjamäe tööstusvööndi selgub Päästeameti registrist "
                      "ja ettevõtte infovoldikust")
    near = None
    near_km = None
    for p in points:
        if p.get("lat") is None or p.get("lon") is None:
            continue
        radius_m = FALLBACK_RADII_M.get(p.get("danger"),
                                        FALLBACK_RADII_M["unknown"])
        km = haversine_km(origin, (p["lat"], p["lon"]))
        if km * 1000.0 <= radius_m and (near_km is None or km < near_km):
            near, near_km = p, km
    if near is None:
        return None, ("Seveso ohuala teadmata (EI OLE hinnangut): "
                      "ohualade polügoone hetktõmmises pole ja lähimas "
                      "punkti-puhvris (hinnanguline raadius ohutüübi "
                      "mediaanist) ohtlikku ettevõtet ei ole — puhvri "
                      "puudumine ei ole ohutuse hinnang; kontrolli "
                      "Päästeameti registrit ja ettevõtte infovoldikut")
    score = DANGER_SCORES.get(near.get("danger"),
                              DANGER_SCORES["unknown"])
    extra = ("; doominoseos võimalik" if near.get("domino") else "")
    return score, ("Ohtliku ettevõtte lähedus (hinnang — punktipuhver "
                   "ohualade puudumisel, mitte polügoon): %s (%.0f m), "
                   "ohutüüp «%s»%s — ohuala polügoon puudub, tutvu "
                   "ettevõtte infovoldikuga"
                   % (near.get("name") or "teadmata ettevõte",
                      (near_km or 0) * 1000.0,
                      near.get("danger_label") or "teadmata", extra))


def score_p4_seveso(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]] = None,
                    danger: Optional[dict] = None
                    ) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """Rollup: {dim_key: score|None} + non-NULL reasons (pure)."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for key, _label, fn in P4_SEVESO_DIMS:
        value, reason = fn(origin, pois, danger)
        dims[key] = value
        if value is not None:
            reasons.append(reason)
    return dims, reasons


P4_SEVESO_DIMS = (
    ("seveso_zone", "Seveso", dim_seveso_zone),
)
