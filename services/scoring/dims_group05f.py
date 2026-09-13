"""Group 5 plans per-listing dimensions, batch F (issue #166).

Params (this agent only — sibling batches own disjoint sets):
* p389 dark sky community designation (ALWAYS None — IDA-register fact)
* p485 zoning upcycling potential (mapped derelict-stock count hinnang)

HONESTY (AGENTS.md section 7.2): the PLANK register, Tallinna
Planeeringute Register and the DarkSky International places register
are NOT in the 2026-09-12 snapshot, so p389 stays NULL with a
buyer-check reason and p485 is a coarse OSM-derived PROXY. Reasons
say "hinnang" (estimate) and name what is missing — never a KOV
rezoning ruling or an IDA designation.

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
nwr/ filters throughout — the whole Tallinn window here is
ways/relations (zero points), so node-only would drop the entire
city signal, PR #118):
* derelict predicate (abandoned=yes or disused=yes WITH a building
  key, or abandoned:building with a building-ish value): 202 objects
  county-wide (114 after the 20 m dedupe, 77 in the Tallinn window;
  the raw window extract is 69 outlines + 69 lines, zero points). Dropped by design: 84 forest/military bunkers
  (building=bunker or abandoned:building=bunker — a bunker field is
  not rezoning stock), bare disused=yes without a building key
  (stale flags, incl. the ACTIVE Reisisadama A-terminal which
  carries disused=yes), abandoned=tunnel/highway fragments,
  abandoned:landuse=quarry/landfill (quarries already score as
  nuisance in p408 lowspec; landfills are env-health), untagged
  relation members, and abandoned:building=roof/level_crossing
  mistags. Zero overlap with landuse=industrial/brownfield, so
  industprox (G07) and brownsoil (G07B) are never re-skinned.
* dark-sky keys (dark_sky/darksky/lighting): ZERO matches in the
  whole PBF — p389 has nothing to calibrate against, and the only
  mappable darkness signal (lit=yes + street_lamp) is owned by
  p63's darksky proxy. Sibling p188 (dark sky compliance, same IDA
  register) already went no-map (#162).

Judgment calls (reviewable per AGENTS.md section 7.5):
* p485 counts mapped derelict buildings within 800 m (moorage-style
  saturating reading, buildout bands at the same city scale):
  >=3 scores 80 (reuse pocket), >=1 scores 65, else 45 with an
  unknown/stability reason. Green sits NEAR the stock (potential
  likely), never a rezoning ruling — the reason names the derelict
  stock so a stillness-seeking buyer reads HIGH as "busy" (buildout
  precedent, #162).
* p389 returns None for EVERY input including missing origin:
  inventing a gradient from zero signal (or re-skinning p63) would
  be fake precision (OTA PR #131 precedent). The reason points at
  the IDA-register check the buyer must do instead.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP05F_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP05F_POI_KIND, centroiding way
geometries to points (derelict stock is outlines/lines; raw way
nodes would multi-count — residual twin risk per PR #118 must be
noted by the hook author), filtering bunker/stale-flag features via
kinds_from_tags (the fragment rows are coarse key queries; the
bunker + stale-flag exclusions live in the mapping, same split as
the rooftop exclusion in #163), and rebalancing livability.WEIGHTS
must be one joint change across all parameter batches — existing
tests pin set(WEIGHTS) exactly, so per-batch WEIGHTS edits would
break every sibling.
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
# Radius is a judgment call: derelict buildings are town-dense, so an
# 800 m pocket search matches the retail-parks precedent (#163). Both
# node[...] and way[...] lines are required (nwr/ parity): the whole
# Tallinn window here is outlines/lines (zero points); node-only would
# drop the entire city signal (PR #118).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP05F_OVERPASS_FRAGMENT = """
  node["abandoned"](around:800,{lat},{lon});
  node["disused"](around:800,{lat},{lon});
  node["abandoned:building"](around:800,{lat},{lon});
  way["abandoned"](around:800,{lat},{lon});
  way["disused"](around:800,{lat},{lon});
  way["abandoned:building"](around:800,{lat},{lon});"""

#: abandoned:building values that count as reuse stock (bunkers, roof
#: fragments and level_crossing mistags are OUT — a bunker field is
#: not rezoning stock).
KEEP_AB_BUILDING = (
    "yes", "garage", "apartments", "school", "house", "detached",
    "industrial", "warehouse", "church", "hospital", "hangar",
    "retail", "commercial", "office", "civic", "terrace",
    "semidetached_house", "hut", "shed", "stable", "barn",
    "greenhouse", "dormitory", "kindergarten", "hotel", "shop",
)

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
#: "derelict" = mapped abandoned/disused building for the reuse-stock
#: dim. The rows are coarse key queries (same split as #163: the
#: fragment stays plain source tags); the bunker + stale-flag
#: exclusions live in kinds_from_tags below, which the hook author
#: must apply when centroiding (bare disused=yes without a building
#: key — e.g. the ACTIVE ferry terminal — maps to None here).
GROUP05F_POI_KIND = [
    ("abandoned", {"yes": "derelict"}),
    ("disused", {"yes": "derelict"}),
    ("abandoned:building", {v: "derelict" for v in KEEP_AB_BUILDING}),
]


def _first_value(value) -> str:
    if value is None:
        return ""
    try:
        return str(value).split(";")[0].strip()
    except (TypeError, AttributeError):
        return ""


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 5-batch-F kind matching the OSM tags, else None. Pure.

    abandoned=yes or disused=yes WITH a building key maps to
    "derelict"; abandoned:building maps by value (KEEP_AB_BUILDING —
    bunkers, roof fragments and level_crossing mistags map to None).
    building=bunker always maps to None (a forest bunker is not
    rezoning stock); bare lifecycle flags without a building key map
    to None (stale flags, e.g. the active ferry terminal).
    """
    tags = tags or {}
    if _first_value(tags.get("building")) == "bunker":
        return None
    if _first_value(tags.get("abandoned")) == "yes" and "building" in tags:
        return "derelict"
    if _first_value(tags.get("disused")) == "yes" and "building" in tags:
        return "derelict"
    if _first_value(tags.get("abandoned:building")) in KEEP_AB_BUILDING:
        return "derelict"
    return None


# ---------------------------------------------------------------------------
# p485: zoning upcycling potential (mapped-stock count hinnang).
# ---------------------------------------------------------------------------

#: Search radius for the derelict-stock count (moorage-style pocket reading).
UPCYCLE_RADIUS_M = 800.0


def dim_upcycle(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p485: reuse-potential reading from mapped derelict stock within 800 m."""
    if not origin or pois is None:
        return None, "Ümberarenduse info puudub (hoonefondi hetktõmmis)"
    n = _count_within_m(origin, pois, {"derelict"}, UPCYCLE_RADIUS_M)
    if n >= 3:
        return 80, "Ümberarenduse potentsiaal (hinnang): %d mahajäetud hoonet 800 m raadiuses — taaskasutusala" % n
    if n >= 1:
        return 65, "Ümberarenduse potentsiaal (hinnang): %d mahajäetud hoone 800 m raadiuses — KOV otsust mõõdetud pole" % n
    return 45, "Ümberarenduse potentsiaal teadmata (hinnang): 800 m raadiuses kaardistatud mahajäetud hooneid pole — stabiilne hoonestus"


# ---------------------------------------------------------------------------
# p389: documented no-map registry NULL (OTA PR #131 precedent).
# A DarkSky-places designation with zero snapshot signal and a p63-owned
# proxy direction; the scorer reports the gap with a concrete buyer
# check instead of a faked number.
# ---------------------------------------------------------------------------

def dim_darksky_community(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p389: NULL — community designation needs the IDA register (no map)."""
    return None, "Pimeda taeva kogukonna staatus teadmata (IDA register/KOV valgustusnõuded; hetktõmmises pole pimedataeva-tunnuseid — valgusproksi kuulub p63-le)"


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP05F_DIMS: Dict[str, Tuple[str, object]] = {
    "darksky_community": ("Pime taevas (kontroll)", dim_darksky_community),
    "upcycle": ("Ümberarendus (proksi)", dim_upcycle),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP05F_PARAM_IDS = {
    "darksky_community": 389,
    "upcycle": 485,
}


def score_group05f(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 5-batch-F dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP05F_DIMS.items():
        v, reason = fn(origin, pois)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
