"""Group 8 flood/climate per-listing dimensions, batch D (issue #170).

Params (this agent only — sibling batches own disjoint sets):
* p377 frost heave foundation damage (ALWAYS None — no soil data, do not fake)
* p378 saltwater intrusion (ALWAYS None — no well-salinity series, do not fake)
* p429 flood zone creep (ALWAYS None — no zone time series, do not fake)
* p447 vernal pools / seasonal swamps (mapped ephemeral-pond proximity hinnang)

HONESTY (AGENTS.md section 7.2): the Keskkonnaagentuur flood-hazard
WFS, EFAS/CMEMS reanalyses, Ilmateenistus archives, soil
frost-susceptibility grids and well-salinity series are NOT in the
2026-09-12 snapshot, so p377/p378/p429 stay NULL with a buyer-check
reason, and p447 is a coarse OSM-derived PROXY. Reasons say
"hinnang" (estimate) and name what is missing — never a flood zone,
a return period, a measured frost depth, a salinity reading, or a
zone-creep trend.

Style mirrors services/scoring/livability.py and sibling batch
dims_group03d.py (#154): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls, only the query fragment + tag mapping the live path needs.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #154).

Tag verification (2026-09-12, done once by the author with osmium
tags-filter/export against
~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at runtime;
nwr/ filters throughout — node-only would silently drop way-mapped
ponds, PR #118):
* ephemeral predicate (natural=water, water=pond/basin,
  intermittent=yes): 33 features = 17 areas + 16 closed-way twins =
  17 unique bodies county-wide (8 ponds + 9 basins), 5 unique in the
  Tallinn window — sparse enough that in-bbox absence is clean
  evidence, dense enough for a nearest-distance dim AND the map
  (apps/web/lib/layers_group08d.ts).
* intermittent=yes overall is 299 features but 211 are ditches/drains
  + 14 rivers + 7 streams: flow features that belong to p50 drainage
  (#151) and are EXCLUDED by the keeper (a ditch is not a vernal
  pool).
* seasonal=* (133 features) lives on tourism features, never on
  water/wetland — no vernal signal.
* natural=wetland (1306 features) carries zero intermittent/seasonal
  tags: all-wetland proximity would re-skin p50 drainage (#151) and
  p257 vectorhabitat (#142), so wetlands stay out by design.
* flood_prone=yes x12: anecdotal points, not a zone — p429 has
  nothing to calibrate a creep trend against.
* salt key x149: ~all salt=no freshwater confirmations (76 ponds, 24
  lakes, 14 wetlands) + 2 salt=yes wetlands — zero aquifer signal,
  so p378 stays a per-well dim.
* No geology/soil tags in the snapshot — p377 has nothing to
  calibrate against (and wetland nearness would duplicate p50).

Judgment calls (reviewable per AGENTS.md section 7.5):
* p447 reuses the raster formula exactly (round(100*d/(d+300))):
  the dim and the map can never disagree. The half (300 m) matches
  the parcel-scale still-water nuisance (soggy ground + mosquitoes),
  same half as #151 drainage and #142 vectorhabitat. Absence within
  the 1.5 km search reads 95 (near-clean: unmapped pools may still
  exist — reason says so), never 100.
* p377/p378/p429 return None for EVERY input including missing
  origin: inventing a gradient from zero signal would be fake
  precision (OTA PR #131 precedent). The reasons point at the
  survey/well-test/flood-map check the buyer must do instead.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP08D_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP08D_POI_KIND, centroiding way
geometries to points (ponds are ways; raw way nodes would
multi-count — residual twin risk per PR #118 must be noted by the
hook author), and rebalancing livability.WEIGHTS must be one joint
change across all parameter batches — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling.
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


def _nearest_m(origin: Tuple[float, float], pois: List[dict], kinds: set) -> Optional[float]:
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
# Radii are judgment calls: ephemeral ponds are sparse (1.5 km search),
# both node[...] and way[...] lines are required (nwr/ parity): ponds
# are ways; node-only drops them (PR #118).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP08D_OVERPASS_FRAGMENT = """
  node["natural"="water"]["water"~"pond|basin"]["intermittent"="yes"](around:1500,{lat},{lon});
  way["natural"="water"]["water"~"pond|basin"]["intermittent"="yes"](around:1500,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
#: "vernalpool" = mapped ephemeral still water (never a flood zone).
#: NOTE: livability._POI_KIND is keyed per single tag, so this row is
#: DELIBERATELY over-inclusive (all natural=water) — integration MUST
#: gate every candidate through kinds_from_tags below (pond/basin +
#: intermittent=yes) before scoring, or lakes/rivers would fake the dim.
GROUP08D_POI_KIND = [
    ("natural", {"water": "vernalpool"}),
]


def kinds_from_tags(tags: dict) -> Optional[str]:
    """Group 8-batch-D kind matching the OSM tags, else None. Pure.

    Strict predicate (mirrors scripts/build/batch_g08d_flood.py
    keep_vernalpool): natural=water + water=pond/basin +
    intermittent=yes. Ditches/drains/rivers/streams with
    intermittent=yes map to None (p50 drainage's signal); wetlands
    map to None (p50/p257 own them); seasonal=* alone maps to None
    (tourism tagging, never water in this snapshot).
    """
    tags = tags or {}
    if str(tags.get("natural", "")).split(";")[0] != "water":
        return None
    if str(tags.get("water", "")).split(";")[0] not in ("pond", "basin"):
        return None
    if str(tags.get("intermittent", "")).split(";")[0] != "yes":
        return None
    return "vernalpool"


# ---------------------------------------------------------------------------
# p447: vernal pools / seasonal swamps (ephemeral-pond proximity hinnang).
# ---------------------------------------------------------------------------

#: Raster half in metres (mirrors G08D_CAL.vernalpool in the TS + builder).
VERNALPOOL_HALF_M = 300.0


def dim_vernalpool(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p447: dryness goodness 100*d/(d+300) from nearest ephemeral pond."""
    if not origin or pois is None:
        return None, "Ajutiste veekogude info puudub (hetktõmmis)"
    m = _nearest_m(origin, pois, {"vernalpool"})
    if m is None:
        return 95, "Ajutist veekogu 1,5 km raadiuses kaardistamata (hinnang: kuiv; kaardistamata lompe võib siiski olla)"
    s = int(round(100.0 * m / (m + VERNALPOOL_HALF_M)))
    if m < 100:
        return s, "Ajutine veekogu %s (hinnang) — kevaditi võimalik liigniiskus/sääsed" % _fmt_m(m)
    return s, "Lähim ajutine veekogu %s (hinnang)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p377/p378/p429: documented no-map registry NULLs (OTA PR #131 precedent).
# Each is a per-site/per-register Keskkonnaagentuur fact with no honest
# area signal; the scorer reports the gap with a concrete buyer check
# instead of a faked number.
# ---------------------------------------------------------------------------

def dim_frost_heave(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p377: NULL — frost-heave risk needs a geotechnical survey (no map)."""
    return None, "Külmakerkeoht teadmata (pinnase-uuring; telli geotehniline inspektsioon — hetktõmmises pole pinnaseandmeid)"


def dim_saltwater(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p378: NULL — saltwater intrusion needs well-salinity data (no map)."""
    return None, "Soolase vee sissetung teadmata (kaevuvee analüüs/KOV hüdrogeoloogia; hetktõmmise salt=silt kinnitab vaid magevett)"


def dim_floodcreep(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p429: NULL — flood-zone creep needs zone time series (no map)."""
    return None, "Üleujutustsooni laienemine teadmata (Keskkonnaagentuur üleujutuskaart; hetktõmmises pole tsoonide ajalugu)"


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP08D_DIMS: Dict[str, Tuple[str, object]] = {
    "frost_heave": ("Külmakerge (kontroll)", dim_frost_heave),
    "saltwater": ("Soolane vesi (kontroll)", dim_saltwater),
    "floodcreep": ("Tsooni laienemine (kontroll)", dim_floodcreep),
    "vernalpool": ("Ajutised veekogud (proksi)", dim_vernalpool),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP08D_PARAM_IDS = {
    "frost_heave": 377,
    "saltwater": 378,
    "floodcreep": 429,
    "vernalpool": 447,
}


def score_group08d(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 8-batch-D dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP08D_DIMS.items():
        v, reason = fn(origin, pois)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
