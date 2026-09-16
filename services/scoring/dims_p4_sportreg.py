"""P4 Spordiregister + ujulad sport-proximity dims (issue #531).

Params (this module only):
* P4-048 family-buyer facility slice: year-round sport within 15 min
  (pool, hall, stadium/field).

LIVE FEED VERDICT (checked 2026-09-16, polite one-off round, custom UA
`home-finder-research/0.1`, single GETs, no retries; aggregates only, raw
bodies never committed):
* `https://www.spordiregister.ee/opendata/files/spordiehitised.json`
  -> HTTP 200, application/octet-stream, 21 259 733 B. 4157 venues, 1216
  in Harjumaa (`maakond` == "Harjumaa"), ALL 1216 with `kaart_laius` /
  `kaart_pikkus` (WGS84, 0 coord-less), ALL `ehstaatus` ==
  "Spordialases kasutuses", newest `esitatudkuupaev` 2026-09-15 (yesterday):
  the feed is FRESH — the catalogue `updated` = 2022-11-23 staleness flag
  in the issue is overturned (stale catalogue page, live bulk). Venue-type
  column `liik` supports pool/hall/field slices (see below).
* `http://vtiav.sm.ee/index.php/opendata/ujulad.xml`
  -> HTTP 200, text/xml, 262 833 B. 226 `<ujula>` rows, 101 Harju/Tallinn,
  219 with `<koordinaadid><x>/<y>` (L-EST97; 7 without, counted),
  `<tyyp>` uldkasutatav 94 / lasteasutuse 52 / kooli 32 / vaikeujula 22 /
  tervishoiuasutus 17 / valiujula 3 / muu 1 / empty 5, plus
  `<viimane_inspekteerimine>` dates (2026 x9 … 2018 x20) and nested
  `<basseinid>`. Same vtiav "Avaandmed" tab family #494 proved for bathing
  water. Overturns docs/p4_recre.md (#312) for the venue slice: neither
  bulk was ever probed there.

Slices (pinned by tests; `liik` is comma-combined, matched per substring):
* hall: "Voimla" (Voimla, spordihall, spordisaal) — 282 Harju rows.
* field: "Valispallivaljak", "Staadion", "Tenniseplats", "pusirada",
  "vabas ohus", "spordiplats" — outdoor ball/stadium/track venues.
* pool (register leg): "Siseujula" in `liik` — 37 Harju rows.
* pool (ujulad leg): every vtiav `<ujula>` with coordinates, any tyyp —
  inspected indoor pools; reasons carry the inspection date where known.
* Unsliced (never scored): "Muu sportimiseks kasutatav objekt",
  "Muu hoones asuv spordiobjekt", "Spordi abihoone" and rows whose
  `ehstaatus` is not "Spordialases kasutuses" (zero today, filter stays
  for harvest drift). A venue whose `liik` matches two slices (e.g.
  "Siseujula, Voimla, spordihall, spordisaal") yields one POI PER slice:
  it genuinely offers both, and dims score per slice.
* Timetables/prices/capacity stay human-page buyer checks (p4_recre
  precedent — locations are not opening hours). EHIS huvikool/spordikool
  rows (#530) are SCHOOLS, these are VENUES: distinct keys, no
  double-score of one signal.

Bands (straight-line haversine ⇒ reasons say "hinnang (linnulennult,
mitte marsruut)"): nearest sliced venue <= 500 m -> 80, <= 1 km -> 65,
<= 2 km -> 50, beyond -> NULL. Missing origin or no sliced POIs of that
kind -> NULL with an EI OLE reason + buyer check.

Style mirrors services/scoring/livability.py and sibling batch
dims_p4_ehis_map.py (#530): scorers are pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network lives
nowhere in this module: the polite harvest (annual is plenty for venues)
is a future adapter job; parse helpers below take bulk text.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside them,
and importing any of them here would turn that into a cycle (same
precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Ujulad `tyyp` does not gate: a kooli/lasteasutuse pool near a listing
  is still a pool, and access rules stay the buyer check (named). Only
  missing coordinates gate.
* Inspection dates are vintage, not quality: reasons cite the last
  inspection date without grading water (that is #494's bathing-water job
  for OUTDOOR sites; indoor pool water is not scored anywhere).
* Licensed CC BY-SA 3.0 (both bulks): attribute + share-alike
  (see docs/p4_sportreg.md). Annual harvest is plenty (TTL 365 d).

Integration (deliberately NOT done here): no livability.OVERPASS_QUERY /
livability._POI_KIND extension, no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

import json
import math
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Proximity bands: (radius_km, score). Beyond 2 km -> NULL (distance only).
PROX_BANDS = ((0.5, 80), (1.0, 65), (2.0, 50))

#: POI kinds (caller-side contracts for harvested register venues).
HALL_KIND = "sport_hall"
FIELD_KIND = "sport_field"
POOL_KIND = "sport_pool"
UJULAD_KIND = "ujulad_pool"

#: Only venues in sporting use place POIs (zero exceptions today; the
#: filter stays so harvest drift can never silently score dead venues).
ACTIVE_STATUS = "Spordialases kasutuses"

#: `liik` substring matchers per slice (lowercased, diacritics kept as-is
#: from the feed; matched case-insensitively). Order matters: pool first so
#: combo venues ("Siseujula, Voimla, ...") yield a pool POI AND a hall POI.
POOL_MARKERS = ("siseujula",)
HALL_MARKERS = ("võimla",)
FIELD_MARKERS = ("välispalliväljak", "staadion", "tenniseplats", "püsirada",
                 "vabas õhus", "spordiplats")

#: Feed identity (verified 2026-09-16, both HTTP 200).
SPORTREG_JSON_URL = "https://www.spordiregister.ee/opendata/files/spordiehitised.json"
SPORTREG_XML_URL = "https://www.spordiregister.ee/opendata/files/spordiehitised.xml"
UJULAD_XML_URL = "http://vtiav.sm.ee/index.php/opendata/ujulad.xml"
SPORTREG_USER_AGENT = (
    "home-finder-p4-sportreg/1.0 (Estonia open-data annual adapter; "
    "polite single-pull, cache-first)"
)
#: Venues change slowly: at most one live pull per year, cache wins inside.
SPORTREG_CACHE_TTL_S = 365 * 86400
SPORTREG_LICENCE = "CC BY-SA 3.0 (Spordiregister / Kultuuriministeerium)"
UJULAD_LICENCE = "CC BY-SA 3.0 (Terviseamet, vtiav avaandmed)"


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


def _pois_of(pois: Optional[List[dict]], kind: str) -> List[dict]:
    out = []
    for p in pois or []:
        if not isinstance(p, dict) or p.get("kind") != kind:
            continue
        if p.get("lat") is None or p.get("lon") is None:
            continue
        out.append(p)
    return out


def _nearest(origin: Tuple[float, float],
             pois: List[dict]) -> Tuple[Optional[dict], Optional[float]]:
    best = None
    best_km = None
    for p in pois:
        km = haversine_km(origin, (p["lat"], p["lon"]))
        if best_km is None or km < best_km:
            best, best_km = p, km
    return best, best_km


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
# Pure offline readers (hermetic; parse harvested bulk text, no network).
# ---------------------------------------------------------------------------

def venue_slices(liik: Optional[str], ehstaatus: Optional[str]) -> List[str]:
    """Map a Spordiregister (liik, ehstaatus) to its slices (pure).

    Only venues in sporting use slice; combo `liik` values yield one slice
    per match; unlisted kinds read as [] (never guessed, never scored).
    """
    if ehstaatus != ACTIVE_STATUS:
        return []
    if not isinstance(liik, str):
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


_SLICE_KINDS = {"pool": POOL_KIND, "hall": HALL_KIND, "field": FIELD_KIND}


def parse_spordiehitised_json(text: str) -> Tuple[List[dict], dict]:
    """Parse the Spordiregister JSON bulk into scorer POIs (pure).

    Coordinates ship as WGS84 (`kaart_laius`/`kaart_pikkus`) and are used
    as-is. Rows without coordinates, inactive rows, and unsliced kinds are
    dropped with counts. Returns (pois, stats).
    """
    rows = json.loads(text)
    pois: List[dict] = []
    stats = {"rows": 0, "placed": 0, "dropped_no_xy": 0,
             "dropped_inactive": 0, "dropped_other_type": 0}
    for row in rows:
        if not isinstance(row, dict):
            continue
        stats["rows"] += 1
        slices = venue_slices(row.get("liik"), row.get("ehstaatus"))
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
        base = {"lat": lat, "lon": lon,
                "name": row.get("rajatisnimi") or "",
                "address": row.get("aadress") or "",
                "liik": row.get("liik") or ""}
        for sl in slices:
            pois.append(dict(base, kind=_SLICE_KINDS[sl]))
            stats["placed"] += 1
    return pois, stats


def _xtext(el: Optional[ET.Element], tag: str) -> str:
    if el is None:
        return ""
    child = el.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def parse_ujulad_xml(text: str) -> Tuple[List[dict], dict]:
    """Parse the vtiav ujulad XML bulk into scorer POIs (pure).

    L-EST97 `<x>/<y>` projected via the local converter; rows without
    coordinates dropped with counts; every other row places regardless of
    `<tyyp>` (access rules stay the buyer check). Returns (pois, stats).
    """
    root = ET.fromstring(text)
    pois: List[dict] = []
    stats = {"rows": 0, "placed": 0, "dropped_no_xy": 0}
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
        pois.append({
            "kind": UJULAD_KIND, "lat": lat, "lon": lon,
            "name": _xtext(node, "nimetus"),
            "address": _xtext(node, "aadress"),
            "tyyp": _xtext(node, "tyyp"),
            "inspected": _xtext(node, "viimane_inspekteerimine"),
        })
        stats["placed"] += 1
    return pois, stats


# ---------------------------------------------------------------------------
# Scorers: measured register proximity bands, NULL beyond 2 km.
# ---------------------------------------------------------------------------

def _band_score(km: float) -> Optional[int]:
    for radius, pts in PROX_BANDS:
        if km <= radius:
            return pts
    return None


def _slice_dim(kind: str, label: str, check: str,
               origin: Optional[Tuple[float, float]],
               pois: Optional[List[dict]], vintage: str = "") -> Score:
    mine = _pois_of(pois, kind)
    if not origin:
        return None, ("%s teadmata (EI OLE hinnangut): aadress puudub — "
                      "registri spordirajatiste kaugus selgub aadressi "
                      "puhvrist, mitte tühjalt" % label)
    if not mine:
        return None, ("%s teadmata (EI OLE hinnangut): hetktõmmises pole "
                      "uhtki %s rajatist — %s; kaugemal kui 2 km pole "
                      "samuti hinnet, ainult kaugus (lahtiolekuajad ja "
                      "hinnad selguvad rajatise kodulehelt, ära feigi)"
                      % (label, label.lower(), check))
    nearest, km = _nearest(origin, mine)
    assert nearest is not None and km is not None
    score = _band_score(km)
    vin = (" (%s)" % vintage) if vintage else ""
    if score is None:
        return None, ("%s kaugemal kui 2 km (EI OLE hinnet, ainult kaugus): "
                      "lähim registri rajatis %s on %.1f km linnulennult "
                      "(hinnang, mitte marsruut)%s — ajakava ja hind "
                      "selguvad rajatisest" % (label, nearest.get("name")
                                               or "teadmata", km, vin))
    return score, ("%s: lähim registri rajatis %s on %.1f km linnulennult "
                   "(hinnang, mitte marsruut-aeg)%s — kauguse, mitte sisu "
                   "hinne; lahtiolekuajad ja hinnad selguvad rajatisest"
                   % (label, nearest.get("name") or "teadmata", km, vin))


def dim_sport_hall(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """P4-048 hall slice: nearest võimla/spordihall (Spordiregister)."""
    return _slice_dim(HALL_KIND, "Lähim spordihall",
                      "kontrolli treeningaegu halli kodulehelt", origin, pois)


def dim_sport_field(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """P4-048 field slice: nearest outdoor pitch/stadium/track."""
    return _slice_dim(FIELD_KIND, "Lähim väliväljak",
                      "kontrolli väljakute broneerimist KOV-ist", origin, pois)


def dim_sport_pool(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """P4-048 pool slice (register leg): nearest Siseujula venue."""
    return _slice_dim(POOL_KIND, "Lähim siseujula",
                      "kontrolli ujula piletit ja ujumisradu", origin, pois)


def dim_ujulad_pool(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """P4-048 pool slice (Terviseamet leg): nearest inspected ujula."""
    mine = _pois_of(pois, UJULAD_KIND)
    vintage = ""
    if origin and mine:
        nearest, _ = _nearest(origin, mine)
        if nearest and nearest.get("inspected"):
            vintage = "viimati inspekteeritud %s" % nearest["inspected"]
    return _slice_dim(UJULAD_KIND, "Lähim ujula (Terviseamet)",
                      "kontrolli ujula ligipääsu ja piletit", origin, pois,
                      vintage=vintage)


P4_SPORTREG_DIMS = (
    ("sport_hall", "P4-048", dim_sport_hall),
    ("sport_field", "P4-048", dim_sport_field),
    ("sport_pool", "P4-048", dim_sport_pool),
    ("ujulad_pool", "P4-048", dim_ujulad_pool),
)


def score_p4_sportreg(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All four P4 sport-proximity dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_SPORTREG_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_SPORTREG_DIMS}
