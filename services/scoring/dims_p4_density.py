"""P4 density dims (issue #554): INSPIRE PD 1x1 km population grid taste axis.

Source: INSPIRE (PD) Eesti rahvastikutihedus 1x1km WFS
(``inspire.geoportaal.ee/geoserver/PD_rahvastikutihedus``), publisher
Land and Spatial Administration, source Statistikaamet, licence
CC0_1.0. Default CRS EPSG:3035 (ETRS89-LAEA); WGS84 bbox accepted.

OPENNESS PROBE (2026-09-16, custom UA, 4 requests total: 1
GetCapabilities + 1 DescribeFeatureType + 1 GetFeature rejected on a
client param error + 1 corrected retry, no 429, /tmp only):
* GetCapabilities -> HTTP 200 XML, 111218 B. One feature type:
  ``PD_rahvastikutihedus:PD.StatisticalDistribution``, title
  "INSPIRE (PD) - Eesti rahvastiku tihedus 1x1km (WFS)".
* DescribeFeatureType -> HTTP 200, 4742 B. Per-square schema: cell id
  ``inspireid_identifier_localid`` (e.g. S-10040), count value
  ``value_statisticalvalue_value`` (unit ``measurementunit_uom``
  "person", method "count", domain "demography"), masked squares read
  value 0 WITH ``value_statisticalvalue_specialvalue_*`` set to the
  INSPIRE ``notApplicable`` codelist entry, reference/measurement
  period ``periodofreference_xlink_title`` /
  ``periodofmeasurement_xlink_title``.
* Harjumaa bbox pull (24.5,59.35,25.0,59.55, count=10) -> HTTP 200
  GML, 20 features (count counts returned elements, not squares):
  live values 11 / 64 / 25 / 7 / 8 / 9 / 244 and masked 0-squares
  carrying the notApplicable special value. Reference period on every
  row: **1.1.2024 - 31.12.2024**.

SAME-OR-DIFFERENT VERDICT vs docs/layers.md section 4 (REL2021
asula fallback; "the 1 km grid bulk is a dated negative, so grid
joins stay NULL"): DIFFERENT - proceed. The dated negative is the
census-2021-vintage bulk (REL2021 tree has no grid level, see
docs/p4_rel2021.md); this WFS serves a MAINTAINED annual series with
a 2024 reference year, so it is not the same bulk in a new dress.
The masked-zero rule still holds (0 + notApplicable flag), and the
census-vintage warning is replaced by a 2024-register-vintage label
that still rides in every reason (2024 people != 2026 people -
Lasnamae infill, Rae growth).

TASTE FRAMING (relief #553 precedent, docs/layers.md conformance):
character overlay first (no score field - cell_character says how
built-up a square is, never "dense is 80/100"); scorer legs are
taste-dependent only: urbanist delight (density = delight, capped),
quiet-seeker delight (density = cost, capped), services-viability
floor (density floor for shops/transit frequency claims, stated as
viability not quality). A masked rural square scores None, never
0/100 (pinned by tests). Never interpolate between squares: 1 km
cells are the field, edges included.

BANDS (justified on the Harjumaa distribution, stated for reviewer
recalibration on the first full pull): Tallinn dormitory-ring
squares run in the low hundreds (live edge samples 7-244 sit at the
bbox fringe), Lasnamae/Oismae core squares in the several thousands;
masked rural squares read 0+flag. Bands: <=50 rahulik hajaasustus,
<=500 aarelinn, <=2000 eeslinn, <=6000 linnaline, above that tihe
suda. Taste-leg caps stated below. CC0 - Statamet/Maa-amet
attributed in every reason.

Ingestion (stdlib only, offline-first, mirrors dims_p4_trans.py):
fetch_cached does the polite annual pull (cache hit within TTL makes
NO request; single GET, no retries, 429 is a stop signal; only HTTP
200 bodies over a minimum size are stored - transport errors are
never cached as data). Scorers and tests never touch the network.

Integration (deliberately NOT done here): splicing these legs into
livability.WEIGHTS and any /layers overlay must be one joint change
across batches - existing tests pin set(WEIGHTS) exactly. No shared
files touched: 3 new files only.
"""

import math
import os
import re
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: WFS GetFeature base (keyless, verified 2026-09-16: HTTP 200 GML on
#: a Harjumaa bbox pull, 2024 reference period on every row).
DENSITY_WFS_URL = (
    "https://inspire.geoportaal.ee/geoserver/PD_rahvastikutihedus/wfs"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=PD_rahvastikutihedus:PD.StatisticalDistribution"
)

#: INSPIRE PD series is annual: at most one bulk refresh per year per
#: cache dir (re-probe the reference year, not the rows).
DENSITY_TTL_S = 365 * 24 * 3600

#: Identifying user agent for the polite pull (annual bulk max).
DENSITY_UA = "home-finder density openness-check (annual WFS max, no scrape)"

#: Minimum plausible GetFeature body: the 10-square sample alone is
#: ~49 KB, so anything smaller is an error page, never data.
GML_MIN_BYTES = 4096

#: Live reference period proven on the 2026-09-16 probe (rides in
#: every reason; 2024 people != 2026 people).
VINTAGE_LABEL = "2024 rahvastikutihedus (Statamet/Maa-amet, CC0)"

#: INSPIRE SpecialValue flag marking privacy-masked squares.
MASKED_SPECIAL = "notApplicable"

#: Character bands (inhabitants per 1 km square -> Estonian label).
#: Justified on the Harjumaa distribution (see module docstring);
#: recalibrate on the first full pull if the histogram disagrees.
DENSITY_BANDS = (
    (50, "rahulik hajaasustus"),
    (500, "aarelinn"),
    (2000, "eeslinn"),
    (6000, "linnaline"),
)
DENSE_CORE_LABEL = "tihe suda"

#: Nearest-cell join window: half the 1 km diagonal (~707 m) plus a
#: small margin - the cell containing the listing always joins.
CELL_WINDOW_M = 750.0

#: Urbanist leg: density = delight, capped at 75 (taste, not quality).
URBANIST_BANDS = [(50, 30), (500, 45), (2000, 60), (6000, 70),
                  (float("inf"), 75)]
#: Quiet-seeker leg: density = cost, capped at 80 (silence is cheap).
QUIET_BANDS = [(50, 80), (500, 65), (2000, 50), (6000, 35),
               (float("inf"), 25)]
#: Services-viability leg: density floor for shops/transit frequency
#: claims, stated as viability not quality, capped at 70.
VIABILITY_BANDS = [(50, 30), (500, 45), (2000, 60), (float("inf"), 70)]


def fetch_cached(url: str, cache_dir: str, filename: str,
                 ttl_s: int = DENSITY_TTL_S) -> Optional[str]:
    """Polite single-GET pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made.
    Otherwise one GET with DENSITY_UA and a 30 s timeout; the body is
    stored only on HTTP 200 with at least GML_MIN_BYTES bytes, else
    None is returned and nothing is cached (transport errors are
    never data). No retries - HTTP 429/errors are a stop signal.
    Scorers never call this; tests cover the cache-hit and error
    paths with a stubbed opener, never the network.
    """
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, filename)
    try:
        if (os.path.exists(dest)
                and time.time() - os.path.getmtime(dest) < ttl_s):
            return dest
    except OSError:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": DENSITY_UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                return None
            body = resp.read()
        if len(body) < GML_MIN_BYTES:
            return None
        with open(dest, "wb") as fh:
            fh.write(body)
        return dest
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Offline readers over the cached GetFeature GML (pure; live schema).
# ---------------------------------------------------------------------------

_CELL_RE = re.compile(
    r"<(?:\w+:)?PD\.StatisticalDistribution[ >](.*?)"
    r"</(?:\w+:)?PD\.StatisticalDistribution>",
    re.S,
)


def _field(block: str, name: str) -> Optional[str]:
    m = re.search(r"<(?:\w+:)?%s>([^<]*)</" % re.escape(name), block)
    if m is None:
        return None
    v = m.group(1).strip()
    return v if v else None


def parse_density_gml(path: str) -> List[dict]:
    """Parse the cached WFS GetFeature GML. Offline.

    Returns per-square dicts: ``cell_id`` (e.g. S-10040), ``value``
    (inhabitants int, or None when privacy-masked), ``masked``
    (True when the INSPIRE notApplicable special value is set),
    ``period`` (reference-period title, e.g. 1.1.2024 - 31.12.2024).
    A masked square reads value 0 in the wire format - the reader
    converts it to None so scorers can never score it as empty.
    """
    with open(path, encoding="utf-8", errors="replace") as fh:
        xml = fh.read()
    out = []
    for block in _CELL_RE.findall(xml):
        special = _field(block, "value_statisticalvalue_specialvalue_xlink_title")
        masked = special == MASKED_SPECIAL
        raw = _field(block, "value_statisticalvalue_value")
        try:
            value: Optional[int] = int(str(raw).strip())
        except (TypeError, ValueError, AttributeError):
            value = None
        if masked:
            value = None
        elif value is not None and value < 0:
            value = None
        out.append({
            "cell_id": _field(block, "inspireid_identifier_localid"),
            "value": value,
            "masked": masked,
            "period": _field(block, "periodofreference_xlink_title"),
        })
    return out


def density_cells_from_values(cells: List[dict]) -> List[dict]:
    """WGS84 cell centroids + values -> scorer POIs. Pure.

    Cells carry ``lat``/``lon`` (reprojected upstream: the wire CRS
    is EPSG:3035, fixtures carry WGS84 directly) plus ``value`` (int
    inhabitants, None when masked) and ``cell_id``. Malformed points
    are skipped, never faked.
    """
    pois = []
    for c in cells:
        try:
            lat = float(c["lat"])
            lon = float(c["lon"])
        except (TypeError, ValueError, KeyError):
            continue
        if isinstance(c.get("lat"), bool) or isinstance(c.get("lon"), bool):
            continue
        if not (math.isfinite(lat) and math.isfinite(lon)):
            continue
        value = c.get("value")
        if isinstance(value, bool):
            continue
        if value is not None:
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
            if value < 0:
                continue
        pois.append({"kind": "densitycell_p4", "lat": lat, "lon": lon,
                     "value": value, "cell_id": c.get("cell_id")})
    return pois


# ---------------------------------------------------------------------------
# Local pure helpers (livability-shaped; local to avoid import cycles).
# ---------------------------------------------------------------------------

def _haversine_m(origin: Tuple[float, float], lat: float, lon: float) -> float:
    """Great-circle distance in metres."""
    r = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (origin[0], origin[1], lat, lon))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(
        (lo2 - lo1) / 2
    ) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _band(value: Optional[float], bands: List[Tuple[float, int]]) -> Optional[int]:
    """First score whose threshold covers the value; None stays None."""
    if value is None:
        return None
    for limit, pts in bands:
        if value <= limit:
            return pts
    return bands[-1][1]


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


def _nearest_cell(origin: Tuple[float, float],
                  pois: List[dict]) -> Optional[Tuple[float, dict]]:
    """(distance_m, poi) of the nearest well-formed density cell."""
    best = None
    for p in pois:
        if not isinstance(p, dict) or p.get("kind") != "densitycell_p4":
            continue
        try:
            lat = float(p["lat"])
            lon = float(p["lon"])
        except (TypeError, ValueError, KeyError):
            continue
        if isinstance(p.get("lat"), bool) or isinstance(p.get("lon"), bool):
            continue
        if not (math.isfinite(lat) and math.isfinite(lon)):
            continue
        d = _haversine_m(origin, lat, lon)
        if best is None or d < best[0]:
            best = (d, p)
    return best


def _joined_cell(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Tuple[Optional[dict], Optional[str]]:
    """Shared join: nearest cell within the window, masked-aware.

    Returns (cell-poi-or-None, null-reason-or-None). A joined masked
    cell (value None) is returned WITH a masked flag so legs score
    None with the masking reason instead of a number.
    """
    if not origin or pois is None:
        return None, ("Rahvastikutiheduse info puudub (EI OLE "
                      "INSPIRE-PD 1x1 km liidestust hetktõmmes)")
    hit = _nearest_cell(origin, pois)
    if hit is None or hit[0] > CELL_WINDOW_M:
        return None, ("Aadress pole tihedusruuduga liidestatud - hinnangut "
                      "pole (EI OLE 1x1 km ruuduliidestust, mitte "
                      "mõõdetud tühjus)")
    _, poi = hit
    value = poi.get("value")
    if isinstance(value, bool):
        return None, ("Tihedusruudu kirje vigane - hinnangut pole (EI OLE "
                      "loetavat ruuduliidestust)")
    if value is None:
        return None, ("Tihedusruut on privaatsusmaskeeritud (<4 elanikku "
                      "loeb 0) - hinnangut pole (EI OLE avatud "
                      "ruuduandmeid, mitte tühi maa)")
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None, ("Tihedusruudu kirje vigane - hinnangut pole (EI OLE "
                      "loetavat ruuduliidestust)")
    if value < 0:
        return None, ("Tihedusruudu kirje vigane - hinnangut pole (EI OLE "
                      "loetavat ruuduliidestust)")
    cell = dict(poi)
    cell["value"] = value
    return cell, None


def cell_character(value: Optional[int]) -> str:
    """Character overlay label (no score): how built-up the square is."""
    if value is None:
        return "maskeeritud hajaasustus"
    for limit, label in DENSITY_BANDS:
        if value <= limit:
            return label
    return DENSE_CORE_LABEL


# ---------------------------------------------------------------------------
# Taste legs (capped; character, never goodness).
# ---------------------------------------------------------------------------

def dim_urbanist_delight(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """Urbanist leg: density = delight, capped at 75 (taste, not quality)."""
    cell, null = _joined_cell(origin, pois)
    if cell is None:
        assert null is not None
        return None, null
    value = cell["value"]
    s = _band(value, URBANIST_BANDS)
    assert s is not None
    return s, ("Linnamelu-maitse hinnang (%s: ruudus ~%d elanikku) -> "
               "skoor %d (lakke 75, maitse, mitte kvaliteet)"
               % (VINTAGE_LABEL, value, s))


def dim_quiet_delight(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """Quiet-seeker leg: density = cost, capped at 80 (silence is cheap)."""
    cell, null = _joined_cell(origin, pois)
    if cell is None:
        assert null is not None
        return None, null
    value = cell["value"]
    s = _band(value, QUIET_BANDS)
    assert s is not None
    return s, ("Vaikuse-maitse hinnang (%s: ruudus ~%d elanikku) -> "
               "skoor %d (lakke 80, maitse, mitte kvaliteet)"
               % (VINTAGE_LABEL, value, s))


def dim_services_viability(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """Services-viability leg: density floor for shops/transit claims.

    Stated as viability, not quality: a thin square cannot carry
    frequent shops/transit, but a dense square guarantees nothing.
    """
    cell, null = _joined_cell(origin, pois)
    if cell is None:
        assert null is not None
        return None, null
    value = cell["value"]
    s = _band(value, VIABILITY_BANDS)
    assert s is not None
    return s, ("Teenuste-elujõu hinnang (%s: ruudus ~%d elanikku) -> "
               "skoor %d (elujõud, mitte kvaliteet)"
               % (VINTAGE_LABEL, value, s))


#: Registry for the central weight-rebalance follow-up: (dim key, param id).
P4_DENSITY_DIMS = (
    ("urbanist_delight", "P4-density", dim_urbanist_delight),
    ("quiet_delight", "P4-density", dim_quiet_delight),
    ("services_viability", "P4-density", dim_services_viability),
)


def score_p4_density(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """P4 density taste legs for one listing (entry point for follow-up)."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_DENSITY_DIMS}
