"""P4 public-shelter proximity dim (issue #528, honest proximity layer).

Source: Rescue Board (Päästeamet) registered public shelters
(varjumiskohad) via opendata.smit.ee (weekly CSV/GPKG).
Licence CC_BY_NC_4.0 per the national catalogue (attribute
Paasteamet; weekly TTL at most).

OPENNESS (probed 2026-09-16, one polite round, UA
home-finder-idea-probe/1.0, paced >= 3 s, cached to /tmp/hf-526-529-probe,
full evidence in docs/p4_shelters.md):
* varjumiskohad.csv: HTTP 200, 34 768 B, 303 rows (67 Tallinn,
  77 Harju — well above the issue's <5 token threshold, so a real
  proximity layer is viable, not a no-map).
* ;-separated: id, nimi, aadress, lest_x (northing), lest_y
  (easting), L-EST97 metres. No WGS84 columns (unlike the Seveso
  register) — projection uses the labelled ~1 m inverse-LCC port
  (batch_tervise.py #511 via batch_accblack.py #522, same constants;
  axis order verified against the Seveso dual-coordinate oracle,
  238 rows / 6.1 cm worst-case, same day).
* Publisher caveat (issue body): brand-new register (2026-07-29),
  data may shift between publications — restated in every reason
  via the snapshot date.

HONESTY (AGENTS.md 7.2): green = near a public shelter (walk-graph
bands per the issue: <=500 m -> 80, <=1 km -> 65, <=2 km -> 50),
capped at 80 (reassurance, never a guarantee); beyond 2 km is NULL
(unknown, never "unsafe"). Every reason carries the 72 h Government-
order caveat and the not-daily-use caveat. Non-public shelters are
not published and are never hunted. Straight-line bands only —
no routing claims. Transport errors are never cached as data;
HTTP 429 stops the run.

Style mirrors services/scoring/dims_p4_seveso.py (#527, same
session): pure offline scorers, stdlib-only, local helpers (no
sibling imports — a future central hook may import this module
alongside the others).

Judgment calls (reviewable per AGENTS.md 7.5):
* Bands are the issue's proposal verbatim (80/65/50, cap 80);
  the nearest shelter wins (a second shelter 200 m further adds no
  reassurance worth scoring).
* The dim reads pre-projected points (lat/lon + the ~1 m transform
  label); parse_shelters_csv is the only place L-EST97 appears, so
  band tests never depend on projection.
* Rows without finite coordinates are skipped and counted by
  summarize_snapshot (never zero-filled, never plotted).
* L-EST97 plausibility gate (Estonian northings ~6.36-6.66M,
  eastings ~0.33-0.74M) rejects WGS84-scale mixups the way
  batch_accblack.py does — it never validates truth.

Integration (deliberately NOT done here): livability hook +
WEIGHTS rebalance stay one joint change across batches (existing
tests pin set(WEIGHTS)). No shared files touched: 3 new files only.
"""

import csv
import io
import math
import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion contract: source identity, politeness, cache.
# ---------------------------------------------------------------------------

#: Public shelters (verified 2026-09-16: HTTP 200, 34 768 B, 303 rows).
SHELTERS_URL = "https://opendata.smit.ee/gis/varjumiskohad.csv"
SHELTERS_USER_AGENT = (
    "home-finder-p4-shelters/1.0 (Estonia open-data weekly adapter; "
    "polite single-pull, cache-first)"
)
#: Publisher updates weekly: at most one live pull per week.
SHELTERS_CACHE_TTL_S = 7 * 86400
SHELTERS_CACHE_NAME = "varjumiskohad.csv"

#: Proximity bands (metres -> score), capped at 80 by construction.
SHELTER_BANDS = ((500.0, 80), (1000.0, 65), (2000.0, 50))
SHELTER_CAP = 80

#: L-EST97 plausibility gate (metres, padded; batch_accblack.py precedent).
LEST97_N_MIN, LEST97_N_MAX = 6360000.0, 6655000.0
LEST97_E_MIN, LEST97_E_MAX = 330000.0, 740000.0


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
# <1 mm vs pyproj there) via scripts/build/batch_accblack.py (#522)
# and services/scoring/dims_p4_seveso.py (#527, 238-row dual-coordinate
# oracle, 6.1 cm worst-case, same day). Same constants, same datum
# label. Copied, not imported: per-issue files stay rebase-safe. ---

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

#: Accuracy label stamped on every projected point (reviewable, never hidden).
LEST97_ACCURACY_LABEL = (
    "L-EST97 (EPSG:3301) inverse-LCC pöördumine, GRS80~WGS84 "
    "daatumi vahe ~1 m — punktid on ausad ~1 m täpsusega"
)


def lest97_to_wgs84(northing: float, easting: float) -> Tuple[float, float]:
    """Project L-EST97 metres to (lat, lon). Labelled ~1 m (see above).

    Register convention: lest_x is the northing, lest_y the easting.
    Raises ValueError on non-finite input (callers drop such rows,
    never fake them).
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


def has_lest97(northing: object, easting: object) -> bool:
    """True when lest_x/lest_y are finite L-EST97-plausible metres (pure)."""
    try:
        n = float(str(northing).strip())
        e = float(str(easting).strip())
    except (TypeError, ValueError, AttributeError):
        return False
    if not (math.isfinite(n) and math.isfinite(e)):
        return False
    return (LEST97_N_MIN <= n <= LEST97_N_MAX
            and LEST97_E_MIN <= e <= LEST97_E_MAX)


# ---------------------------------------------------------------------------
# Ingestion: polite cached pull (live path, NOT unit-run) + pure parse.
# ---------------------------------------------------------------------------

def _cache_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, SHELTERS_CACHE_NAME)


def cache_is_fresh(path: str, ttl_s: int = SHELTERS_CACHE_TTL_S,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_s."""
    try:
        age_s = (now if now is not None else time.time()) - os.path.getmtime(path)
    except OSError:
        return False
    return age_s < ttl_s


def fetch_shelters_snapshot(
    cache_dir: Optional[str] = None,
    ttl_s: int = SHELTERS_CACHE_TTL_S,
) -> Tuple[dict, str]:
    """Polite cached pull of varjumiskohad.csv (live path, NOT unit-run).

    Fresh cache wins (no request). Any transport error raises and the
    cache file is left untouched — transport errors are never cached
    as data, and 429 stops the run. Returns (snapshot, provenance)
    with provenance "cache" or "live".
    """
    if cache_dir is None:
        cache_dir = os.path.join("/tmp", "hf-shelters-cache")
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir)
    provenance = "cache"
    if cache_is_fresh(path, ttl_s):
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    else:
        req = urllib.request.Request(
            SHELTERS_URL, headers={"User-Agent": SHELTERS_USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            if resp.status == 429:
                raise RuntimeError("opendata.smit.ee vastas 429 — peatu, ära reetry")
            if resp.status != 200:
                raise RuntimeError(
                    "opendata.smit.ee vastas HTTP %s — vahemalu puutumata"
                    % resp.status
                )
            text = resp.read().decode("utf-8-sig", errors="replace")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        provenance = "live"
    snapshot = {
        "points": parse_shelters_csv(text),
        "fetched": time.strftime("%Y-%m-%d", time.gmtime()),
        "source": "Päästeameti avalike varjumiskohtade register "
                  "(opendata.smit.ee, CC BY-NC 4.0)",
    }
    return snapshot, provenance


def parse_shelters_csv(csv_text: str) -> List[dict]:
    """Parse varjumiskohad.csv into shelter points (pure).

    id;nimi;aadress;lest_x;lest_y, BOM-tolerant. Rows without
    L-EST97-plausible coordinates are skipped (counted by
    summarize_snapshot, never zero-filled).
    """
    reader = csv.DictReader(io.StringIO((csv_text or "").lstrip("\ufeff")),
                            delimiter=";")
    out: List[dict] = []
    for row in reader:
        if not has_lest97(row.get("lest_x"), row.get("lest_y")):
            continue
        try:
            lat, lon = lest97_to_wgs84(float(str(row["lest_x"]).strip()),
                                       float(str(row["lest_y"]).strip()))
        except ValueError:
            continue
        out.append({
            "id": (row.get("id") or "").strip(),
            "name": (row.get("nimi") or "").strip(),
            "address": (row.get("aadress") or "").strip(),
            "lat": lat,
            "lon": lon,
            "transform": LEST97_ACCURACY_LABEL,
        })
    return out


def summarize_snapshot(csv_text: str) -> dict:
    """Honest counts for a CSV payload: parsed / skipped / Tallinn (pure)."""
    points = parse_shelters_csv(csv_text)
    reader = csv.DictReader(io.StringIO((csv_text or "").lstrip("\ufeff")),
                            delimiter=";")
    total = sum(1 for _ in reader)
    return {
        "rows": total,
        "points": len(points),
        "skipped": total - len(points),
        "tallinn": sum(1 for p in points if "Tallinn" in p["address"]),
        "harju": sum(1 for p in points if "Harju" in p["address"]),
    }


# ---------------------------------------------------------------------------
# Scorer: honest proximity (bands capped, beyond is NULL).
# ---------------------------------------------------------------------------

def _nearest(origin: Tuple[float, float],
             points: List[dict]) -> Tuple[Optional[dict], Optional[float]]:
    best = None
    best_km = None
    for p in points:
        if p.get("lat") is None or p.get("lon") is None:
            continue
        km = haversine_km(origin, (p["lat"], p["lon"]))
        if best_km is None or km < best_km:
            best, best_km = p, km
    return best, best_km


def dim_shelter_proximity(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]] = None,
                          shelters: Optional[dict] = None) -> Score:
    """Public-shelter proximity: near scores (capped), far NULLs.

    `shelters` is the snapshot from fetch_shelters_snapshot. `pois`
    is accepted for the uniform scorer shape and ignored — shelters
    are not OSM POIs. Straight-line bands only (no routing claims).
    """
    _ = pois
    snap = shelters if isinstance(shelters, dict) else None
    if not origin:
        return None, ("Varjumiskoha lähedus teadmata (EI OLE hinnangut): "
                      "aadress puudub — lähima avaliku varjumiskoha kaugus "
                      "(72 h valmisolek, mitte igapäevakasutus) selgub "
                      "aadressi asendist, mitte tühjalt")
    points = [p for p in (snap or {}).get("points", []) if isinstance(p, dict)]
    if not points:
        return None, ("Varjumiskoha lähedus teadmata (EI OLE hinnangut): "
                      "avalike varjumiskohtade hetktõmmist pole — "
                      "Päästeameti register (opendata.smit.ee, CC BY-NC 4.0, "
                      "iganädalane; uus register, andmed võivad muutuda) "
                      "selgub nädala väljavõttest; kontrolli riigiinfo "
                      "käitumisjuhiseid ja lähimat varjumiskohta kohapeal")
    nearest, km = _nearest(origin, points)
    assert (nearest is None) == (km is None)
    if nearest is None or km is None:
        return None, ("Varjumiskoha lähedus teadmata (EI OLE hinnangut): "
                      "hetktõmmise ühelgi kirjel pole koordinaate — "
                      "kontrolli Päästeameti registrit kohapeal")
    fetched = snap.get("fetched") if isinstance(snap.get("fetched"), str) \
        else "teadmata"
    for limit_m, pts in SHELTER_BANDS:
        if km * 1000.0 <= limit_m:
            return pts, ("Avalik varjumiskoht %s (%.0f m linnulennult, "
                         "hinnang, mitte marsruut; ülempiir 80): lähedus on "
                         "leevendus, mitte garantii — varjumiskohad avatakse "
                         "kõigile Vabariigi Valitsuse korraldusel 72 h "
                         "jooksul, igapäevakasutust pole; register uueneb "
                         "iganädalaselt (väljavõte %s, andmed võivad muutuda)"
                         % (nearest.get("name") or "teadmata",
                            km * 1000.0, fetched))
    return None, ("Varjumiskoha lähedus teadmata (EI OLE hinnangut): "
                  "lähim avalik varjumiskoht %s on %.1f km kaugusel "
                  "(üle 2 km — väljaspool hinnanguala): kaugus ei ole "
                  "ebaturvalisuse hinnang; varjumiskohad avatakse 72 h "
                  "jooksul valitsuse korraldusel (väljavõte %s)"
                  % (nearest.get("name") or "teadmata", km, fetched))


def score_p4_shelters(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]] = None,
                      shelters: Optional[dict] = None
                      ) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """Rollup: {dim_key: score|None} + non-NULL reasons (pure)."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for key, _label, fn in P4_SHELTERS_DIMS:
        value, reason = fn(origin, pois, shelters)
        dims[key] = value
        if value is not None:
            reasons.append(reason)
    return dims, reasons


P4_SHELTERS_DIMS = (
    ("shelter_proximity", "Shelters", dim_shelter_proximity),
)
