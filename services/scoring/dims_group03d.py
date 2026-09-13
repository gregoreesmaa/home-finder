"""Group 3 cadastre waterfront per-listing dimensions, batch D (issue #154).

Params (this agent only — sibling batches own disjoint sets):
* p331 bulkhead/seawall structure (ALWAYS None — per-structure fact, do not fake)
* p332 dock/mooring opportunity (mapped marina/mooring proximity hinnang)
* p337 lake water level fluctuation (ALWAYS None — no gauges, do not fake)
* p339 well water recharge rate (ALWAYS None — no hydrogeology, do not fake)
* p340 shoreline setback distance (mapped-shore distance, raster formula)

HONESTY (AGENTS.md section 7.2): the Maa-amet cadastre/permit WFS,
EELIS gauge time series and hydrogeology grids are NOT in the
2026-09-12 snapshot, so p331/p337/p339 stay NULL with a buyer-check
reason, and p332/p340 are coarse OSM-derived PROXIES. Reasons say
"hinnang" (estimate) and name what is missing — never a permit
register, a legal setback ruling, a measured seawall condition, gauge
readings, or a recharge rate.

Style mirrors services/scoring/livability.py and sibling batch
dims_group03b.py (#152): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls, only the query fragment + tag mapping the live path needs.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Tag verification (2026-09-12, done once by the author with osmium
tags-filter/tags-count against
~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at runtime;
nwr/ filters throughout — node-only would silently drop way-mapped
marinas and the coastline, PR #118):
* moorage predicate (leisure=marina, seamark:type mooring/harbour,
  harbour=yes, mooring=yes-ish, mooring=no out, bare piers out):
  195 objects county-wide, 41 in the Tallinn window (Kakumae,
  Hundipea, Lennusadam/Noblessner, Kalasadam, Vanasadam, Pirita,
  Kalevi) — dense enough for a nearest-distance dim AND the area
  map (apps/web/lib/layers_group03d.ts).
* shore predicate (natural=coastline + natural=water polygons,
  rivers/wetlands out): 620 coastline ways + standing-water
  polygons — the param's own ST_Distance input, disjoint from p50
  drainage (#151) by kind.
* man_made=breakwater x47 ways + man_made=quay x14 ways carry ZERO
  condition attributes — locations without soundness, so p331 stays
  a per-structure dim (a gradient from locations would answer the
  wrong question: presence, not condition).
* man_made=monitoring_station x28 objects: air_quality/weather/
  traffic tags only; the sole water_level mentions say
  water_level=no — p337 has nothing to calibrate against.
* man_made=water_well x28 + natural=spring x35 say PRESENCE, never
  RATE, and p183 (#152) already scores indicator proximity — p339
  stays NULL with the KOV-table check.

Judgment calls (reviewable per AGENTS.md section 7.5):
* p332 bands track the raster half loosely (one marina within a
  short walk ~= 50 on the map): <=150 m scores 85, <=400 m 70,
  <=800 m 55, <=1.5 km 40, beyond 25 (weak: mapped facilities are
  sparse, unmapped shore may still take a jetty — reason says so).
  The reason names the permit gap explicitly (the permit itself is a
  per-parcel KOV/valla fact).
* p340 reuses the raster formula exactly (round(100*d/(d+100))):
  the dim and the map can never disagree. Under 50 m the reason
  flags the strict-zone check (Veeseadus 50-100 m); the dim never
  issues a legal ruling ("kontrolli", never "keelatud").
* p331/p337/p339 return None for EVERY input including missing
  origin: inventing a gradient from zero signal would be fake
  precision (OTA PR #131 precedent). The reasons point at the
  inspection/register/KOV-table check the buyer must do instead.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP03D_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP03D_POI_KIND, centroiding way
geometries to points (marinas/shore are ways/relations; raw way
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


def _band(value: Optional[float], bands: List[Tuple[float, int]]) -> Optional[int]:
    """First score whose threshold covers the value; None stays None."""
    if value is None:
        return None
    for limit, pts in bands:
        if value <= limit:
            return pts
    return bands[-1][1]


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
# Radii are judgment calls: marinas mid-sparse (2 km search), shore
# dense along the coast (1.5 km). Both node[...] and way[...] lines are
# required (nwr/ parity): marinas/shore are ways/relations; node-only
# drops them (PR #118).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP03D_OVERPASS_FRAGMENT = """
  node["leisure"="marina"](around:2000,{lat},{lon});
  node["seamark:type"~"mooring|harbour"](around:2000,{lat},{lon});
  node["harbour"="yes"](around:2000,{lat},{lon});
  node["natural"~"coastline|water"](around:1500,{lat},{lon});
  way["leisure"="marina"](around:2000,{lat},{lon});
  way["seamark:type"~"mooring|harbour"](around:2000,{lat},{lon});
  way["harbour"="yes"](around:2000,{lat},{lon});
  way["natural"~"coastline|water"](around:1500,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
#: "moorage" = dock/mooring opportunity (never a permit); "shore" =
#: mapped shoreline for the setback dim (rivers/wetlands stay p50's).
GROUP03D_POI_KIND = [
    ("leisure", {"marina": "moorage"}),
    ("seamark:type", {"mooring": "moorage", "harbour": "moorage"}),
    ("harbour", {"yes": "moorage"}),
    ("mooring", {"yes": "moorage", "yacht": "moorage",
                 "private": "moorage", "declaration": "moorage",
                 "commercial": "moorage"}),
    ("natural", {"coastline": "shore", "water": "shore"}),
]


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 3-batch-D kind matching the OSM tags, else None. Pure.

    mooring=no never maps (absent from the mooring values on purpose);
    bare piers/breakwaters/quays map to None (p331 locations, not p332
    opportunity); waterways/wetlands map to None (p50's signal).
    """
    tags = tags or {}
    if str(tags.get("leisure", "")).split(";")[0] == "marina":
        return "moorage"
    if str(tags.get("seamark:type", "")).split(";")[0] in ("mooring", "harbour"):
        return "moorage"
    if str(tags.get("harbour", "")).split(";")[0] == "yes":
        return "moorage"
    if str(tags.get("mooring", "")).split(";")[0] in (
            "yes", "yacht", "private", "declaration", "commercial"):
        return "moorage"
    if str(tags.get("natural", "")).split(";")[0] in ("coastline", "water"):
        return "shore"
    return None


# ---------------------------------------------------------------------------
# p332: dock/mooring opportunity (mapped-facility proximity hinnang).
# ---------------------------------------------------------------------------

def dim_moorage(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p332: mooring-opportunity goodness from nearest mapped facility."""
    if not origin or pois is None:
        return None, "Sildumisinfo puudub (sadamate hetktõmmis)"
    m = _nearest_m(origin, pois, {"moorage"})
    if m is None:
        return 25, "Sildumiskoht 2 km raadiuses kaardistamata (hinnang, nõrk); luba ise on krundi-põhine KOV fakt"
    s = _band(m, [(150, 85), (400, 70), (800, 55), (1500, 40)])
    assert s is not None
    if s <= 40:
        return s, "Sildumisvõimalus (hinnang): lähim sadam %s — kaugel; luba kontrolli KOV-st" % _fmt_m(m)
    return s, "Sildumisvõimalus (hinnang): lähim sadam %s (luba ise krundi-põhine)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p340: shoreline setback distance (mapped-shore distance, raster formula).
# ---------------------------------------------------------------------------

#: Raster half in metres (mirrors G03D_CAL.shoredist in the TS + builder).
SHOREDIST_HALF_M = 100.0


def dim_shoredist(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p340: setback goodness 100*d/(d+100) from nearest mapped shore."""
    if not origin or pois is None:
        return None, "Rannajoone info puudub (rannajoone hetktõmmis)"
    m = _nearest_m(origin, pois, {"shore"})
    if m is None:
        return 90, "Rannajoon 1,5 km raadiuses kaardistamata (hinnang: keeluvööndist väljas)"
    s = int(round(100.0 * m / (m + SHOREDIST_HALF_M)))
    if m < 50:
        return s, "Rannajoon %s (hinnang) — kontrolli ehituskeeluvööndit (Veeseadus 50-100 m)" % _fmt_m(m)
    return s, "Rannajoone kaugus %s (hinnang, keeluvööndi servast väljas)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p331/p337/p339: documented no-map registry NULLs (OTA PR #131 precedent).
# Each is a per-structure/per-register Maa-amet/EELIS fact with no honest
# area signal; the scorer reports the gap with a concrete buyer check
# instead of a faked number.
# ---------------------------------------------------------------------------

def dim_seawall(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p331: NULL — seawall condition needs a structural survey (no map)."""
    return None, "Müürseina seisund teadmata (per-rajatis; telli ehituslik inspektsioon — hetktõmmises pole seisundiandmeid)"


def dim_lake_level(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p337: NULL — lake fluctuation needs gauge series (no gauges)."""
    return None, "Järve veetaseme kõikumine teadmata (EELIS/Keskkonnaagentuur seire; hetktõmmises pole mõõtejaamu)"


def dim_recharge(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p339: NULL — recharge rate needs hydrogeology/KOV table (no map)."""
    return None, "Kaevuvee taastumiskiirus teadmata (hüdrogeoloogia/KOV tabel; kaevu olemasolu pole kiirus)"


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP03D_DIMS: Dict[str, Tuple[str, object]] = {
    "seawall": ("Müürsein (kontroll)", dim_seawall),
    "moorage": ("Sildumisvõimalus (proksi)", dim_moorage),
    "lake_level": ("Järve veetase (kontroll)", dim_lake_level),
    "recharge": ("Kaevuvee taastumine (kontroll)", dim_recharge),
    "shoredist": ("Rannajoone kaugus", dim_shoredist),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP03D_PARAM_IDS = {
    "seawall": 331,
    "moorage": 332,
    "lake_level": 337,
    "recharge": 339,
    "shoredist": 340,
}


def score_group03d(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 3-batch-D dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP03D_DIMS.items():
        v, reason = fn(origin, pois)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
