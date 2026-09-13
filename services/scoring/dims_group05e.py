"""Group 5 plans per-listing dimensions, batch E (issue #165).

Params (this agent only — sibling batches own disjoint sets):
* p365 multi-family conversion zoning (ALWAYS None — per-parcel legal fact)
* p381 equestrian community access (mapped riding-facility count hinnang)
* p382 fly-in residential airparks (ALWAYS None — scored twice already)
* p384 55+ age-restricted enforcement (ALWAYS None — community-rules fact)
* p387 agrihoods (ALWAYS None — growing halves scored twice already)

HONESTY (AGENTS.md section 7.2): the PLANK register, Tallinna
Planeeringute Register, any conversion-zoning table, any 55+
community register and any agrihood developer plan are NOT in the
2026-09-12 snapshot, so p365/p382/p384/p387 stay NULL with a
buyer-check reason, and p381 is a coarse OSM-derived PROXY. Reasons
say "hinnang" (estimate) and name what is missing — never a KOV
zoning decision or a riding-community membership list.

Style mirrors services/scoring/livability.py and sibling batch
dims_group05c.py (#163): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls, only the query fragment + tag mapping the live path needs.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #163).

Tag verification (2026-09-12, done once by the author with osmium
tags-filter/export against
~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at runtime;
nwr/ filters throughout — node-only would silently drop way-mapped
arenas and stable campuses, PR #118):
* riding predicate (leisure=horse_riding or sport=equestrian or
  highway=bridleway or building=stable): 86 raw features (~46 unique
  sites — osmium export doubles closed ways as LineString +
  MultiPolygon twins; 15 in the Tallinn window: Veskimetsa
  ratsakeskus, Vääna tallid, Lagedi Ratsaspordikool, Jüri Tall,
  Suuresti tall + arena pitches). leisure=pitch WITHOUT
  sport=equestrian stays OUT (a football pitch is not an arena).
* conversion zoning: zero zoning keys anywhere in the PBF — a
  per-parcel legal status has no area signal to calibrate.
* fly-in airparks: small-airfield proximity is already scored twice
  (flightcorr p445 corridors + droneclear p220 aerodrome distance);
  no fly-in residential community exists in the snapshot area.
* 55+ enforcement: zero age-restriction keys anywhere in the PBF.
* agrihoods: no master-plan keys anywhere in the PBF; the
  growing-soil halves are already scored twice (gardens p106
  allotments/community-gardens + agrifield p409 farmland/orchard).

Judgment calls (reviewable per AGENTS.md section 7.5):
* p381 counts mapped riding facilities within 800 m (viewshed-style
  saturating reading): >=3 scores 80 (riding pocket), >=1 scores
  65, else 45 with an unknown-access reason. Green sits NEAR the
  amenity (access likely), never a zoning decision.
* p365/p382/p384/p387 return None for EVERY input including missing
  origin: inventing a gradient from zero signal (or triplicating
  flightcorr/droneclear, duplicating gardens/agrifield) would be
  fake precision (OTA PR #131 precedent). The reasons point at the
  register/layer check the buyer must do instead.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP05E_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP05E_POI_KIND, centroiding way
geometries to points (arenas/stable campuses are ways; raw way
nodes would multi-count — residual twin risk per PR #118 must be
noted by the hook author), and rebalancing livability.WEIGHTS must
be one joint change across all parameter batches — existing tests
pin set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break
every sibling.
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


def _count_within_m(origin: Tuple[float, float], pois: List[dict], kinds: set,
                    radius_m: float) -> int:
    n = 0
    for p in pois:
        if p.get("kind") in kinds and p.get("lat") is not None:
            if _haversine_m(origin, p["lat"], p["lon"]) <= radius_m:
                n += 1
    return n


# ---------------------------------------------------------------------------
# Live-path wiring: Overpass fragment + tag mapping.
# Radius is a judgment call: riding campuses are pocket-scale (800 m
# search, viewshed precedent). Both node[...] and way[...] lines are
# required (nwr/ parity): arenas and stable campuses are ways;
# node-only drops them (PR #118).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP05E_OVERPASS_FRAGMENT = """
  node["leisure"="horse_riding"](around:800,{lat},{lon});
  node["sport"="equestrian"](around:800,{lat},{lon});
  node["highway"="bridleway"](around:800,{lat},{lon});
  node["building"="stable"](around:800,{lat},{lon});
  way["leisure"="horse_riding"](around:800,{lat},{lon});
  way["sport"="equestrian"](around:800,{lat},{lon});
  way["highway"="bridleway"](around:800,{lat},{lon});
  way["building"="stable"](around:800,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
#: "riding" = mapped riding centre, equestrian arena, stable building
#: or bridleway for the access dim. leisure=pitch maps to None unless
#: sport=equestrian carries the meaning (a football pitch is not an
#: arena) — that check lives in kinds_from_tags, not in this table.
GROUP05E_POI_KIND = [
    ("leisure", {"horse_riding": "riding"}),
    ("sport", {"equestrian": "riding"}),
    ("highway", {"bridleway": "riding"}),
    ("building", {"stable": "riding"}),
]


def _first_value(value) -> str:
    try:
        return str(value).split(";")[0].strip()
    except (TypeError, AttributeError):
        return ""


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 5-batch-E kind matching the OSM tags, else None. Pure.

    leisure=horse_riding, sport=equestrian, highway=bridleway and
    building=stable map to "riding". leisure=pitch maps to None: a
    football pitch is not an arena — only the sport=equestrian tag
    carries the equestrian meaning.
    """
    tags = tags or {}
    if _first_value(tags.get("leisure")) == "horse_riding":
        return "riding"
    if _first_value(tags.get("sport")) == "equestrian":
        return "riding"
    if _first_value(tags.get("highway")) == "bridleway":
        return "riding"
    if _first_value(tags.get("building")) == "stable":
        return "riding"
    return None


# ---------------------------------------------------------------------------
# p381: equestrian community access (mapped-facility count hinnang).
# ---------------------------------------------------------------------------

#: Search radius for the facility count (viewshed-style pocket reading).
EQUESTRIAN_RADIUS_M = 800.0


def dim_equestrian(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p381: riding-access reading from mapped facilities within 800 m."""
    if not origin or pois is None:
        return None, "Ratsutamisalade info puudub (ratsutamisalade hetktõmmis)"
    n = _count_within_m(origin, pois, {"riding"}, EQUESTRIAN_RADIUS_M)
    if n >= 3:
        return 80, "Ratsutamisvõimalus (hinnang): %d ratsutamisobjekti 800 m raadiuses — ligipääs hea" % n
    if n >= 1:
        return 65, "Ratsutamisvõimalus (hinnang): %d ratsutamisobjekt 800 m raadiuses — planeeringuotsust mõõdetud pole" % n
    return 45, "Ratsutamisvõimalus teadmata (hinnang): 800 m raadiuses kaardistatud ratsutamisobjekt puudub"


# ---------------------------------------------------------------------------
# p365/p382/p384/p387: documented no-map registry NULLs (OTA PR #131).
# Each is a per-parcel/per-rules fact with no honest area signal (or an
# already-scored-twice duplicate); the scorer reports the gap with a
# concrete buyer check instead of a faked number.
# ---------------------------------------------------------------------------

def dim_multifam(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p365: NULL — conversion zoning is a per-parcel legal fact (no map)."""
    return None, "Mitmepereelamuks ümberehituse võimalus teadmata (KOV planeeringuotsus/tsoon; hetktõmmises pole tsoonimisandmeid — kontrolli planeeringute registrist)"


def dim_flyin(origin: Optional[Tuple[float, float]],
              pois: Optional[List[dict]]) -> Score:
    """p382: NULL — small-airfield proximity already scored twice (no map)."""
    return None, "Lennukitega elamurajoon kaardil pole (Lennuamet; stardiraja lähedus on juba flightcorr/droneclear — Eestis lennukitega elamurajoone pole)"


def dim_age55(origin: Optional[Tuple[float, float]],
              pois: Optional[List[dict]]) -> Score:
    """p384: NULL — age restriction is a community-rules fact (no map)."""
    return None, "55+ vanusepiirangu info puudub (arendaja/ühistu kodukord; hetktõmmises pole vanusepiirangu andmeid — kontrolli arendajalt)"


def dim_agrihood(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p387: NULL — growing halves already scored twice, no plan key (no map)."""
    return None, "Agrihood-planeering kaardil pole (arendaja planeering; aianduspool on juba gardens/agrifield kaardil — kontrolli arendajalt)"


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP05E_DIMS: Dict[str, Tuple[str, object]] = {
    "multifam": ("Mitmepere-ümberehitus (kontroll)", dim_multifam),
    "equestrian": ("Ratsutamisvõimalus (proksi)", dim_equestrian),
    "flyin": ("Lennukelamu (kontroll)", dim_flyin),
    "age55": ("55+ piirang (kontroll)", dim_age55),
    "agrihood": ("Agrihood (kontroll)", dim_agrihood),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP05E_PARAM_IDS = {
    "multifam": 365,
    "equestrian": 381,
    "flyin": 382,
    "age55": 384,
    "agrihood": 387,
}


def score_group05e(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 5-batch-E dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP05E_DIMS.items():
        v, reason = fn(origin, pois)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
