"""Group 5 plans per-listing dimensions, batch C (issue #163).

Params (this agent only — sibling batches own disjoint sets):
* p221 eminent domain risk (ALWAYS None — per-parcel legal fact, do not fake)
* p222 flight path re-routing (ALWAYS None — schedule fact + scored twice already)
* p223 commercial zoning bleed (mapped commercial-zone proximity hinnang)
* p224 wind/solar farm proximity (mapped farm distance, raster formula)
* p225 view shedding ordinances (mapped viewpoint-count hinnang)

HONESTY (AGENTS.md section 7.2): the PLANK register, Tallinna
Planeeringute Register, KOV sundvõõrandamine decisions, EANS route
schedules and the Elering generation register are NOT in the
2026-09-12 snapshot, so p221/p222 stay NULL with a buyer-check reason,
and p223/p224/p225 are coarse OSM-derived PROXIES. Reasons say
"hinnang" (estimate) and name what is missing — never a KOV zoning
decision, an Elering production ruling, or a height-limit register
entry.

Style mirrors services/scoring/livability.py and sibling batch
dims_group08b.py (#168): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls, only the query fragment + tag mapping the live path needs.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #168).

Tag verification (2026-09-12, done once by the author with osmium
tags-filter/export against
~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at runtime;
nwr/ filters throughout — node-only would silently drop way-mapped
retail parks and farm polygons, PR #118):
* commercial predicate (landuse commercial/retail or shop=mall): 854
  objects county-wide (670 in the Tallinn window: Ülemiste, Rocca al
  Mare, Mustakivi). 200 untagged relation members drop out. Plain
  supermarkets stay grocery's (#98) — malls/retail parks are bleed
  pressure, not errands.
* farm predicate (wind any location; solar ONLY ground/surface/
  overground): 155 objects county-wide (53 wind + 102 farm solar, 91
  in the Tallinn window incl. a Nõmme turbine). 1734 rooftop panels
  drop out BY DESIGN (a panel is not a farm); diesel/gas/biofuel/
  hydro are OUT (not wind/solar).
* viewpoint predicate (tourism=viewpoint): 88 objects county-wide
  (44 in the Tallinn window: Kohtuotsa/Patkuli/Piiskopi platforms,
  klint edges). Bog bird-towers dilute the rural field by design.
* eminent domain: zero expropriation keys anywhere in the PBF — a
  rare per-parcel legal event has no area signal to calibrate.
* flight re-routing: no EANS route/timetable objects exist; runway
  proximity is already scored twice (flightcorr p445 corridors +
  droneclear p220 aerodrome distance) — a third gradient duplicates.

Judgment calls (reviewable per AGENTS.md section 7.5):
* p223 bands track the raster formula loosely (100*d/(d+300): 150 m
  ~= 33, 300 m = 50, 600 m ~= 67): <=150 m scores 35, <=300 m 50,
  <=600 m 70, beyond 85 (calm: detached residential, reason says
  so). Under 150 m the reason flags the planeering check
  (liiklus/müra).
* p224 reuses the raster formula exactly (round(100*d/(d+800))):
  the dim and the map can never disagree. Under 300 m the reason
  flags the noise/shading check (müra/varjutus); the dim never
  issues a production ruling ("kontrolli", never a register entry).
* p225 counts mapped viewpoints within 800 m (moorage-style
  saturating reading): >=3 scores 80 (protected pocket), >=1
  scores 65, else 45 with an unknown-protection reason. Green sits
  NEAR the amenity (protection likely), never a height-limit ruling.
* p221/p222 return None for EVERY input including missing
  origin: inventing a gradient from zero signal (or duplicating
  flightcorr/droneclear) would be fake precision (OTA PR #131
  precedent). The reasons point at the KOV-register/EANS check the
  buyer must do instead.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP05C_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP05C_POI_KIND, centroiding way
geometries to points (retail parks/farms are ways/relations; raw way
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


def _count_within_m(origin: Tuple[float, float], pois: List[dict], kinds: set,
                    radius_m: float) -> int:
    n = 0
    for p in pois:
        if p.get("kind") in kinds and p.get("lat") is not None:
            if _haversine_m(origin, p["lat"], p["lon"]) <= radius_m:
                n += 1
    return n


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


# ---------------------------------------------------------------------------
# Live-path wiring: Overpass fragment + tag mapping.
# Radii are judgment calls: retail parks dense in town (800 m search),
# farms sparse (2 km), viewpoints pocket-scale (800 m). Both node[...]
# and way[...] lines are required (nwr/ parity): retail parks and farm
# polygons are ways/relations; node-only drops them (PR #118).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP05C_OVERPASS_FRAGMENT = """
  node["landuse"~"commercial|retail"](around:800,{lat},{lon});
  node["shop"="mall"](around:800,{lat},{lon});
  node["power"="generator"](around:2000,{lat},{lon});
  node["tourism"="viewpoint"](around:800,{lat},{lon});
  way["landuse"~"commercial|retail"](around:800,{lat},{lon});
  way["shop"="mall"](around:800,{lat},{lon});
  way["power"="generator"](around:2000,{lat},{lon});
  way["tourism"="viewpoint"](around:800,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
#: "commzone" = mapped commercial/retail zone or mall for the bleed dim
#: (plain supermarkets stay grocery's); "windfarm"/"solarfarm" = farm
#: scale only (rooftop panels map to None — a panel is not a farm);
#: "viewpoint" = mapped scenic viewpoint for the view-protection dim.
GROUP05C_POI_KIND = [
    ("landuse", {"commercial": "commzone", "retail": "commzone"}),
    ("shop", {"mall": "commzone"}),
    ("power", {"generator": "windfarm"}),
    ("tourism", {"viewpoint": "viewpoint"}),
]

#: Solar locations that count as farm scale (rooftop + unknown OUT).
FARM_SOLAR_LOCATIONS = ("ground", "surface", "overground")


def _first_value(value) -> str:
    try:
        return str(value).split(";")[0].strip()
    except (TypeError, AttributeError):
        return ""


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 5-batch-C kind matching the OSM tags, else None. Pure.

    landuse commercial/retail and shop=mall map to "commzone";
    power=generator maps by generator:source — wind always counts,
    solar only on farm-scale locations (rooftop/unknown map to None:
    a panel is not a farm); tourism=viewpoint maps to "viewpoint".
    """
    tags = tags or {}
    if _first_value(tags.get("landuse")) in ("commercial", "retail"):
        return "commzone"
    if _first_value(tags.get("shop")) == "mall":
        return "commzone"
    if _first_value(tags.get("power")) == "generator":
        src = _first_value(tags.get("generator:source"))
        if src == "wind":
            return "windfarm"
        if src == "solar" and _first_value(tags.get("location")) in FARM_SOLAR_LOCATIONS:
            return "solarfarm"
        return None
    if _first_value(tags.get("tourism")) == "viewpoint":
        return "viewpoint"
    return None


# ---------------------------------------------------------------------------
# p223: commercial zoning bleed (mapped-zone proximity hinnang).
# ---------------------------------------------------------------------------

def dim_commbleed(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p223: bleed-pressure calmness from nearest mapped commercial zone."""
    if not origin or pois is None:
        return None, "Äritsoonide info puudub (planeeringute hetktõmmis)"
    m = _nearest_m(origin, pois, {"commzone"})
    if m is None:
        return 85, "Äritsoon 800 m raadiuses kaardistamata (hinnang: rahulik elamupiirkond)"
    s = _band(m, [(150, 35), (300, 50), (600, 70)])
    assert s is not None
    if s <= 50:
        return s, "Äritsooni surve (hinnang): lähim äri-/kaubandustsoon %s — kontrolli planeeringut (liiklus/müra)" % _fmt_m(m)
    return s, "Äritsooni surve (hinnang): lähim äri-/kaubandustsoon %s (rahulik)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p224: wind/solar farm proximity (mapped-farm distance, raster formula).
# ---------------------------------------------------------------------------

#: Raster half in metres (mirrors G05C_CAL.windsolar in the TS + builder).
WINDSOLAR_HALF_M = 800.0


def dim_windsolar(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p224: farm-exposure calmness 100*d/(d+800) from nearest mapped farm."""
    if not origin or pois is None:
        return None, "Tuule-/päikeseparkide info puudub (parkide hetktõmmis)"
    m = _nearest_m(origin, pois, {"windfarm", "solarfarm"})
    if m is None:
        return 90, "Tuule-/päikesepark 2 km raadiuses kaardistamata (hinnang: parkidest väljas)"
    s = int(round(100.0 * m / (m + WINDSOLAR_HALF_M)))
    if m < 300:
        return s, "Tuule-/päikesepark %s (hinnang) — kontrolli müra ja varjutust" % _fmt_m(m)
    return s, "Tuule-/päikesepargi kaugus %s (hinnang, tootmisregistrita)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p225: view shedding ordinances (mapped viewpoint-count hinnang).
# ---------------------------------------------------------------------------

#: Search radius for the viewpoint count (moorage-style pocket reading).
VIEWSHED_RADIUS_M = 800.0


def dim_viewshed(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p225: view-protection reading from mapped viewpoints within 800 m."""
    if not origin or pois is None:
        return None, "Vaatepunktide info puudub (vaadete hetktõmmis)"
    n = _count_within_m(origin, pois, {"viewpoint"}, VIEWSHED_RADIUS_M)
    if n >= 3:
        return 80, "Vaatekaitse (hinnang): %d vaatepunkti 800 m raadiuses — vaade tõenäoliselt kaitstud" % n
    if n >= 1:
        return 65, "Vaatekaitse (hinnang): %d vaatepunkt 800 m raadiuses — kõrguspiirangud võimalikud" % n
    return 45, "Vaatekaitse teadmata (hinnang): 800 m raadiuses kaardistatud vaatepunkt puudub"


# ---------------------------------------------------------------------------
# p221/p222: documented no-map registry NULLs (OTA PR #131 precedent).
# Each is a per-register/per-schedule fact with no honest area signal;
# the scorer reports the gap with a concrete buyer check instead of a
# faked number.
# ---------------------------------------------------------------------------

def dim_eminent(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p221: NULL — eminent domain is a per-parcel legal fact (no map)."""
    return None, "Sundvõõrandamise risk teadmata (KOV sundvõõrandamisotsus; hetktõmmises pole võõrandamisandmeid — kontrolli planeeringute registrist)"


def dim_flightreroute(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p222: NULL — re-routing is a schedule fact, already scored twice (no map)."""
    return None, "Lennutrajektooride muutmise risk kaardil pole (EANS marsruudiotsus; stardiraja lähedus on juba flightcorr/droneclear — kontrolli EANSist)"


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP05C_DIMS: Dict[str, Tuple[str, object]] = {
    "eminent": ("Sundvõõrandamine (kontroll)", dim_eminent),
    "flightreroute": ("Lennutrajektoor (kontroll)", dim_flightreroute),
    "commbleed": ("Äritsooni surve (proksi)", dim_commbleed),
    "windsolar": ("Tuule-/päikesepark (proksi)", dim_windsolar),
    "viewshed": ("Vaatekaitse (proksi)", dim_viewshed),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP05C_PARAM_IDS = {
    "eminent": 221,
    "flightreroute": 222,
    "commbleed": 223,
    "windsolar": 224,
    "viewshed": 225,
}


def score_group05c(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 5-batch-C dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP05C_DIMS.items():
        v, reason = fn(origin, pois)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
