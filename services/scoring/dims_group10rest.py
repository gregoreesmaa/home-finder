"""Group 10 utilities-rest per-listing dimensions (issue #171).

Params (this agent only — sibling batches own disjoint sets):
* p215 satellite internet line-of-sight (mapped-obstruction open-sky hinnang)
* p491 indoor dead zones (ALWAYS None — per-room RF measurement, do not fake)

HONESTY (AGENTS.md section 7.2): the TTJA Lairiba katvuskaart,
OpenCellID/CellMapper measurements and any dish line-of-sight survey
are NOT in the 2026-09-12 snapshot (zero satellite-dish and zero
indoor-signal keys — verified with osmium tags-count), so p215 is a
coarse OSM-derived PROXY and p491 stays NULL with a buyer check.
Titles, legends, and reasons must say "kaardistatud" (mapped) and
"hinnang" (estimate), never claim measured coverage, throughput, or
indoor signal strength.

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
buildings and forest polygons, PR #118):
* building:levels >= 5: 5604 objects county-wide (5330 in the
  Tallinn window: Lasnamäe/Õismäe/Mustamäe panel districts). 1-4
  storey houses are OUT (a family house does not block the dish
  cone); level-less buildings are OUT (guessing height would fake
  precision).
* natural=wood / landuse=forest: 15928 features county-wide (~8.7k
  true polygons, 4266 in the Tallinn window: Nõmme-Mustamäe, Pirita,
  Viimsi woods). Tree rows and lone trees are OUT (a row is not a
  canopy).
* satellite dishes / indoor-signal keys: ZERO anywhere in the PBF —
  p215 has no measured-signal shape and p491 has no area signal at
  all. building:material (5131 uses, ~2% of buildings) is the wrong
  shape for p491 (own-wall material, not an area gradient).

Judgment calls (reviewable per AGENTS.md section 7.5):
* p215 bands track the raster formula loosely (100*d/(d+150): 75 m
  ~= 33, 150 m = 50, 300 m ~= 67): <=75 m scores 35, <=150 m 50,
  <=300 m 70, beyond 85 (calm: open sky, reason says so). Under
  75 m the reason flags the Starlink-app obstruction check. The
  field is radial while real obstruction is directional — red means
  "check", never "no satellite here".
* p491 returns None for EVERY input including missing origin:
  inventing a gradient from zero signal would be fake precision
  (OTA PR #131 precedent). The reason points at the on-site
  measurement the buyer must do instead.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP10REST_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP10REST_POI_KIND, centroiding way
geometries to points (tall buildings and forests are ways/relations;
raw way nodes would multi-count — residual twin risk per PR #118
must be noted by the hook author), and rebalancing livability.WEIGHTS
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
# Radii are judgment calls: tall buildings dense in town (500 m search),
# forests broad (1 km). Both node[...] and way[...] lines are required
# (nwr/ parity): tall buildings and forests are ways/relations;
# node-only drops them (PR #118).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP10REST_OVERPASS_FRAGMENT = """
  node["building"]["building:levels"](around:500,{lat},{lon});
  node["natural"="wood"](around:1000,{lat},{lon});
  node["landuse"="forest"](around:1000,{lat},{lon});
  way["building"]["building:levels"](around:500,{lat},{lon});
  way["natural"="wood"](around:1000,{lat},{lon});
  way["landuse"="forest"](around:1000,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
#: "skyobst" = mapped tall building (5+ storeys) or mapped forest
#: canopy for the open-sky dim. Family houses, level-less buildings,
#: tree rows and lone trees map to None (not obstructions).
GROUP10REST_POI_KIND = [
    ("natural", {"wood": "skyobst"}),
    ("landuse", {"forest": "skyobst"}),
]

#: Storeys at/above which a mapped building is a sky obstruction.
TALL_LEVELS = 5


def _first_value(value) -> str:
    try:
        return str(value).split(";")[0].strip()
    except (TypeError, AttributeError):
        return ""


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 10-rest kind matching the OSM tags, else None. Pure.

    buildings with building:levels >= 5 map to "skyobst";
    natural=wood and landuse=forest map to "skyobst". Family houses
    (< 5 storeys), level-less buildings, tree rows and lone trees map
    to None (not obstructions).
    """
    tags = tags or {}
    if "building:levels" in tags:
        try:
            if int(_first_value(tags.get("building:levels"))) >= TALL_LEVELS:
                return "skyobst"
        except ValueError:
            pass
        return None
    if _first_value(tags.get("natural")) == "wood":
        return "skyobst"
    if _first_value(tags.get("landuse")) == "forest":
        return "skyobst"
    return None


# ---------------------------------------------------------------------------
# p215: satellite internet line-of-sight (mapped-obstruction hinnang).
# ---------------------------------------------------------------------------

#: Raster half in metres (mirrors G10R_CAL.skyview in the TS + builder).
SKYVIEW_HALF_M = 150.0


def dim_skyview(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p215: open-sky calmness from nearest mapped tall building/forest."""
    if not origin or pois is None:
        return None, "Satelliit-interneti info puudub (takistuste hetktõmmis)"
    m = _nearest_m(origin, pois, {"skyobst"})
    if m is None:
        return 90, "Kõrghoone/mets 1 km raadiuses kaardistamata (hinnang: lage taevas)"
    s = _band(m, [(75, 35), (150, 50), (300, 70), (float("inf"), 85)])
    assert s is not None
    if s <= 50:
        return s, "Satelliit-vaade (hinnang): lähim takistus %s — kontrolli antenni vaatevälja Starlink rakendusega" % _fmt_m(m)
    return s, "Satelliit-vaade (hinnang): lähim takistus %s (lage)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p491: documented no-map registry NULL (OTA PR #131 precedent).
# Indoor dead zones are per-room RF measurements with no honest area
# signal; the scorer reports the gap with a concrete buyer check
# instead of a faked number.
# ---------------------------------------------------------------------------

def dim_deadzone(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p491: NULL — indoor dead zones need on-site measurement (no map)."""
    return None, "Siseruumide leviaugud teadmata (mõõtmata siseruumi signaal; hetktõmmises pole siseruumiandmeid — mõõda kohapeal telefoniga või küsi operaatorilt)"


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP10REST_DIMS: Dict[str, Tuple[str, object]] = {
    "skyview": ("Satelliidi avatud taevas (proksi)", dim_skyview),
    "deadzone": ("Siseruumi leviaugud (kontroll)", dim_deadzone),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP10REST_PARAM_IDS = {
    "skyview": 215,
    "deadzone": 491,
}


def score_group10rest(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 10-rest dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP10REST_DIMS.items():
        v, reason = fn(origin, pois)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
