"""Group 5 plans-D per-listing dimensions, batch G05D (issue #164).

Params (this agent only — sibling batches own disjoint sets):
* p226 heritage tree ordinances (restriction fact — documented no-map)
* p230 short-term rental saturation (mapped-accommodation proxy)
* p244 non-conforming use certificate (per-parcel fact — no-map)
* p275 pre-existing non-conforming use (per-parcel fact — no-map)
* p280 eminent domain history (records fact — documented no-map)

HONESTY (AGENTS.md section 7.2): the PLANK WFS (planeeringud.ee), the
Tallinna Planeeringute Register and any Airbnb/booking listing register
are NOT in the 2026-09-12 snapshot, so the p230 scorer below is an
honestly-labeled OSM-derived PROXY and the other four are explicit None
stubs. Reasons must say "kaardistatud" (mapped) and "hinnang"
(estimate), never claim a listing count, an ordinance ruling, a
certificate status, a grandfathered right, or an expropriation record.

Style mirrors services/scoring/livability.py and sibling batch
dims_group08b.py (#168): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network lives
only in livability.fetch_pois; this module adds no network calls, only
the query fragment + tag mapping the live path needs.

Helpers are local copies (not imported from livability or the sibling
batches): a future central hook may import this module alongside them,
and importing any of them here would turn that into a cycle (same
precedent as batch B3, PR #100, and siblings #105/#107/#121/#168).

Tag verification (2026-09-12, done once by the author with osmium
tags-filter against ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf,
NOT at runtime; extraction used nwr/ filters throughout — node-only
would silently drop way-mapped hotels, PR #118):
* nwr/tourism=apartment|guest_house|hostel|hotel|motel: 334 kept in
  the keep_strstay predicate (hotel 168, guest_house 84, hostel 55,
  apartment 25, motel 2; 209 in the Tallinn window).
* nwr/natural=tree: 43522 features, but only 7 carry
  denotation=natural_monument and 2 more protected=yes — hence the
  p226 no-map (9 mapped significant trees cannot carry a restriction
  gradient; unmapped-but-protected parcels would read false green).

Judgment calls (reviewable per AGENTS.md section 7.5):
* p230 scores NEAREST mapped-bed distance (the map layer's
  inverse-distance shape): the adjacent guest turnover drives
  saturation attention. Bands stay soft (25..85, never 0/100):
  holiday-flat mapping is thin (most Airbnbs carry no OSM tag), so
  far-from-mapped-beds reads 85 with a thin-mapping caveat, never a
  saturation all-clear.
* p226/p244/p275/p280 are constant-None stubs WITH registry entries
  (not omitted): omitting them would let a downstream scorer silently
  treat them as 0/neutral. Heritage protection needs the Keskkonnaamet
  register, p244/p275 need a TPR/certificate lookup, p280 needs
  expropriation records — none is predictable from mapped density, and
  guessing would be fake precision.
* "strstay" kind is disjoint from all sibling batches (novel kind
  string; no sibling scores tourism tags).

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP05D_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP05D_POI_KIND (via kinds_from_tags
below), centroiding way geometries to points (hotels are usually
area-mapped; raw way nodes would multi-count — residual twin risk per
PR #118 must be noted by the hook author), and rebalancing
livability.WEIGHTS must be one joint change across all parameter
batches — existing tests pin set(WEIGHTS) exactly, so per-batch WEIGHTS
edits would break every sibling.
"""

import math
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Local pure helpers (livability-shaped; see module docstring for why local).
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


def _nearest_within_m(origin: Tuple[float, float], pois: List[dict],
                      kinds: set) -> Optional[float]:
    best: Optional[float] = None
    for p in pois:
        if p.get("kind") in kinds and p.get("lat") is not None:
            d = _haversine_m(origin, p["lat"], p["lon"])
            if best is None or d < best:
                best = d
    return best


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


# ---------------------------------------------------------------------------
# Live-path wiring: Overpass fragment + tag mapping.
# The fragment queries at 2 km (holiday-flat mapping is thin — a tighter
# radius would read false calm); the p230 scorer reads nearest-bed
# distance outright (the map layer's inverse-distance shape, so the
# per-listing dim agrees with the map about what "nearby" means).
# Node AND way lines are required (nwr/ parity): hotels are usually
# area-mapped; node-only drops them.
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP05D_OVERPASS_FRAGMENT = """
  node["tourism"~"apartment|guest_house|hostel|hotel|motel"](around:2000,{lat},{lon});
  way["tourism"~"apartment|guest_house|hostel|hotel|motel"](around:2000,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
#: tourism is value-routed through kinds_from_tags (five overnight-guest
#: values share one kind; restaurants/museums map to None).
GROUP05D_POI_KIND = [
    ("tourism", {"apartment": "strstay", "guest_house": "strstay",
                 "hostel": "strstay", "hotel": "strstay",
                 "motel": "strstay"}),
]

#: tourism values hosting overnight guests (saturation-pressure signal).
STAY_VALUES = frozenset(
    {"apartment", "guest_house", "hostel", "hotel", "motel"}
)


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 5D kind matching the OSM tags, else None. Pure.

    tourism=apartment/guest_house/hostel/hotel/motel -> "strstay" (p230
    saturation-pressure proxy). Restaurants, museums and all other
    tourism values map to None: foot traffic without beds carries no
    G05D signal. Multi-values ("hotel;apartments") take the first
    segment.
    """
    tags = tags or {}
    first = str(tags.get("tourism", "")).split(";")[0].strip()
    if first in STAY_VALUES:
        return "strstay"
    return None


# ---------------------------------------------------------------------------
# p226: heritage tree ordinances — documented no-map (None stub).
# ---------------------------------------------------------------------------

def dim_heritage_trees(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p226: ALWAYS None — 9 mapped significant trees, needs the register."""
    return None, ("Pärandpuude kaitse teadmata — hetktõmmises on ainult "
                  "9 kaardistatud väärispuud (kontrollitud; kaardistamata "
                  "≠ kaitsmata), vajab Keskkonnaameti registri / KOV "
                  "päringut enne raiet")


# ---------------------------------------------------------------------------
# p230: short-term rental saturation (nearest-mapped-bed proxy).
# ---------------------------------------------------------------------------

#: 50-score walk-km mirror (map layer half 0.35 km, avoid-kind).
STRSAT_HALF_M = 350.0


def dim_strsat(origin: Optional[Tuple[float, float]],
               pois: Optional[List[dict]]) -> Score:
    """p230: nearest mapped tourist bed (küllastussurve-hinnang).

    Inverse like the map layer: adjacent guest turnover drives the score
    DOWN. Bands stay soft (25..85, never 0/100): holiday-flat mapping is
    thin, so far-from-mapped-beds is calm with a caveat, never a
    saturation all-clear.
    """
    if not origin or pois is None:
        return None, "Lühiajalise üüri info puudub"
    d = _nearest_within_m(origin, pois, {"strstay"})
    if d is None:
        return 85, ("Kaardistatud turismimajutust läheduses pole "
                    "(küllastussurve-hinnang; üürikorterite kaardistus on "
                    "hõre — kaardistamata korterid ei loe)")
    s = _band(d, [(100, 25), (250, 40), (500, 55), (1000, 70),
                  (float("inf"), 85)])
    return s, ("Lähim kaardistatud turismimajutus %s kaugusel "
               "(küllastussurve-hinnang, mitte Airbnb loendus)" % _fmt_m(d))


# ---------------------------------------------------------------------------
# p244: non-conforming use certificate — documented no-map (None stub).
# ---------------------------------------------------------------------------

def dim_nonconforming_cert(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """p244: ALWAYS None — certificate status is a per-parcel fact."""
    return None, ("Mittevastava kasutuse sertifikaadi staatus teadmata — "
                  "vajab Tallinna Planeeringute Registri / ehitusloa "
                  "päringut krundi kohta (kaarditihedus seda ei ennusta)")


# ---------------------------------------------------------------------------
# p275: pre-existing non-conforming use — documented no-map (None stub).
# ---------------------------------------------------------------------------

def dim_preexisting_nonconforming(origin: Optional[Tuple[float, float]],
                                  pois: Optional[List[dict]]) -> Score:
    """p275: ALWAYS None — grandfathered status is a per-parcel fact."""
    return None, ("Omandatud mittevastava kasutuse staatus teadmata — "
                  "vajab planeeringu / ehitusloa arhiivipäringut krundi "
                  "kohta (kaarditihedus seda ei ennusta)")


# ---------------------------------------------------------------------------
# p280: eminent domain history — documented no-map (None stub).
# ---------------------------------------------------------------------------

def dim_eminent_history(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p280: ALWAYS None — history needs expropriation records."""
    return None, ("Sundvõõrandamise ajalugu teadmata — vajab Riigi Teataja / "
                  "KOV otsuste päringut (koridori geomeetria mõõdaks riski, "
                  "mitte ajalugu)")


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP05D_DIMS: Dict[str, Tuple[str, object]] = {
    "heritage_trees": ("Pärandpuud (kontroll)", dim_heritage_trees),
    "strsat": ("Lühiajalise üüri küllastus (proksi)", dim_strsat),
    "nonconforming_cert": ("Mittevastav kasutus (kontroll)", dim_nonconforming_cert),
    "preexisting_nonconforming": ("Omandatud mittevastavus (kontroll)",
                                  dim_preexisting_nonconforming),
    "eminent_history": ("Sundvõõrandamine (kontroll)", dim_eminent_history),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP05D_PARAM_IDS = {
    "heritage_trees": 226,
    "strsat": 230,
    "nonconforming_cert": 244,
    "preexisting_nonconforming": 275,
    "eminent_history": 280,
}


def score_group05d(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 5-batch-D dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP05D_DIMS.items():
        v, reason = fn(origin, pois)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
