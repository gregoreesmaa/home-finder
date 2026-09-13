"""Group 8 flood/climate per-listing dimensions, batch B (issue #168).

Params (this agent only — sibling batches own disjoint sets):
* p118 drought tolerance (ALWAYS None — no soil survey, do not fake)
* p182 prevailing wind direction (ALWAYS None — uniform wind, do not fake)
* p255 wind tunneling effects (mapped 5+-storey proximity hinnang)
* p333 salt air corrosion exposure (mapped SEA-shore distance, raster formula)

HONESTY (AGENTS.md section 7.2): the Maa-amet mullakaart soil
survey, Ilmateenistus/ERA5 wind fields and a coastal corrosion
register are NOT in the 2026-09-12 snapshot, so p118/p182 stay NULL
with a buyer-check reason, and p255/p333 are coarse OSM-derived
PROXIES. Reasons say "hinnang" (estimate) and name what is missing
— never a soil measurement, an anemometer reading, or a
corrosion-rate ruling.

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
tags-filter/tags-count against
~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at runtime;
nwr/ filters throughout — node-only would silently drop way-mapped
towers and the coastline, PR #118):
* tall predicate (building:levels first ;-value >= 5): 5622 objects
  county-wide (4 Points + 2794 footprint rings + 2824
  MultiPolygons; 5512 in the Tallinn window) — dense enough for a
  nearest-distance dim AND the map
  (apps/web/lib/layers_group08b.ts). building:height is OUT (metres
  confound a tall villa with a tower); building:part sections are
  IN (same tower).
* sea predicate (natural=coastline ONLY): 620 lines + 265
  islet/island MultiPolygons — the param's ST_Distance input, SEA
  only so it never re-skins p340 shoredist (#154, shore + lakes).
* soil/drought keys: ZERO matches in the whole PBF (no soil,
  irrigation, drought or moisture keys) — p118 has nothing to
  calibrate against.
* wind direction: Harjumaa prevailing wind is a uniform regional SW
  flow (Ilmateenistus climate normals) — a 0..100 per-parcel
  gradient of a uniform field would be fake precision by
  construction; the 6 monitoring:weather objects are station points,
  not a direction raster. p182 stays NULL with an orientation
  check.

Judgment calls (reviewable per AGENTS.md section 7.5):
* p255 bands track the raster formula loosely (100*d/(d+200): 100 m
  ~= 33, 200 m = 50, 400 m ~= 67): <=100 m scores 35, <=200 m 50,
  <=400 m 70, beyond 85 (calm: detached stock, reason says so).
* p333 reuses the raster formula exactly (round(100*d/(d+500))):
  the dim and the map can never disagree. Under 200 m the reason
  flags the facade/material check (soolane prits — fassaad,
  aknad, katus); the dim never issues a corrosion-rate ruling
  ("kontrolli", never a rate).
* p118/p182 return None for EVERY input including missing
  origin: inventing a gradient from zero signal would be fake
  precision (OTA PR #131 precedent). The reasons point at the
  mullakaart/orientation check the buyer must do instead.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP08B_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP08B_POI_KIND, centroiding way
geometries to points (towers/shore are ways/relations; raw way
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
# Radii are judgment calls: towers dense in town (800 m search), sea
# sparse inland (2 km). Both node[...] and way[...] lines are required
# (nwr/ parity): towers/shore are ways/relations; node-only drops
# them (PR #118).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP08B_OVERPASS_FRAGMENT = """
  node["building:levels"](around:800,{lat},{lon});
  node["natural"="coastline"](around:2000,{lat},{lon});
  way["building:levels"](around:800,{lat},{lon});
  way["natural"="coastline"](around:2000,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
#: "tallbuild" = 5+-storey tower for the tunneling dim (levels check
#: stays in kinds_from_tags — height alone never maps); "seashore" =
#: mapped SEA shore for the salt dim (lakes stay p340's).
GROUP08B_POI_KIND = [
    ("building:levels", {}),
    ("natural", {"coastline": "seashore"}),
]

#: Levels at/above which a building counts as wind-channeling stock.
TALL_LEVELS = 5.0


def _first_levels(value) -> Optional[float]:
    try:
        return float(str(value).split(";")[0].strip())
    except (TypeError, ValueError, AttributeError):
        return None


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 8-batch-B kind matching the OSM tags, else None. Pure.

    levels < 5 (villas, slabs under the threshold) map to None;
    height without levels maps to None (metres are not storeys);
    natural=water maps to None (lake spray is not salty — p340's).
    """
    tags = tags or {}
    lv = _first_levels(tags.get("building:levels"))
    if lv is not None and lv >= TALL_LEVELS:
        return "tallbuild"
    if str(tags.get("natural", "")).split(";")[0] == "coastline":
        return "seashore"
    return None


# ---------------------------------------------------------------------------
# p255: wind tunneling effects (mapped-tower proximity hinnang).
# ---------------------------------------------------------------------------

def dim_windtunnel(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p255: tunneling-exposure calmness from nearest 5+-storey tower."""
    if not origin or pois is None:
        return None, "Kõrghoonete info puudub (tuule hetktõmmis)"
    m = _nearest_m(origin, pois, {"tallbuild"})
    if m is None:
        return 85, "Kõrghoone 800 m raadiuses kaardistamata (hinnang: tuulevaikne)"
    s = _band(m, [(100, 35), (200, 50), (400, 70)])
    assert s is not None
    if s <= 50:
        return s, "Tuuletunneli proksi (hinnang): lähim 5+-korruseline %s — kanjoniefekt võimalik" % _fmt_m(m)
    return s, "Tuuletunneli proksi (hinnang): lähim 5+-korruseline %s (tuulevaikne)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p333: salt air corrosion exposure (mapped-SEA-shore distance, raster formula).
# ---------------------------------------------------------------------------

#: Raster half in metres (mirrors G08B_CAL.saltspray in the TS + builder).
SALTSPRAY_HALF_M = 500.0


def dim_saltspray(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p333: salt-exposure calmness 100*d/(d+500) from nearest SEA shore."""
    if not origin or pois is None:
        return None, "Mererannajoone info puudub (rannajoone hetktõmmis)"
    m = _nearest_m(origin, pois, {"seashore"})
    if m is None:
        return 90, "Mererand 2 km raadiuses kaardistamata (hinnang: soolapritsmest väljas)"
    s = int(round(100.0 * m / (m + SALTSPRAY_HALF_M)))
    if m < 200:
        return s, "Mererand %s (hinnang) — kontrolli fassaadi/aknaid/katust soolakorrosiooni suhtes" % _fmt_m(m)
    return s, "Soolapritsme kaugus %s mererannast (hinnang, merepiirita)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p118/p182: documented no-map registry NULLs (OTA PR #131 precedent).
# Each is a per-register/per-site fact with no honest area signal; the
# scorer reports the gap with a concrete buyer check instead of a
# faked number.
# ---------------------------------------------------------------------------

def dim_drought(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p118: NULL — drought tolerance needs a soil survey (no map)."""
    return None, "Põuakindlus teadmata (mullakaart/KOV mulla-uuring; hetktõmmises pole pinnaseandmeid)"


def dim_winddir(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p182: NULL — prevailing wind is a uniform regional SW flow (no map)."""
    return None, "Valitsev tuulesuund kaardil pole (Harjumaal ühtlane edelavool; hoone orientatsiooni kontrolli kohapeal)"


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP08B_DIMS: Dict[str, Tuple[str, object]] = {
    "drought": ("Põuakindlus (kontroll)", dim_drought),
    "winddir": ("Tuulesuund (kontroll)", dim_winddir),
    "windtunnel": ("Tuuletunnel (proksi)", dim_windtunnel),
    "saltspray": ("Soolapritse (proksi)", dim_saltspray),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP08B_PARAM_IDS = {
    "drought": 118,
    "winddir": 182,
    "windtunnel": 255,
    "saltspray": 333,
}


def score_group08b(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 8-batch-B dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP08B_DIMS.items():
        v, reason = fn(origin, pois)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
