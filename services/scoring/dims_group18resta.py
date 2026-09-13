"""Group 18 spatial-models per-listing dimensions, rest batch A (issue #172).

Params (this agent only — sibling batches own disjoint sets):
* p34  natural light (mapped tall-mass openness hinnang)
* p100 window placement and cross-ventilation (ALWAYS None — floorplan fact)
* p231 driveway incline angle (ALWAYS None — no grade signal in snapshot)
* p287 zoom-ready lighting (ALWAYS None — interior room fact, do not fake)
* p305 exterior reflective glare (mapped glass-facade distance hinnang)

HONESTY (AGENTS.md section 7.2): Maa-amet LoD2 3D meshes, PVLib
ray-tracing, lux meters, floorplans and any DEM/DTM/elevation model are
NOT in the 2026-09-12 snapshot (zero contour objects; registries/ holds
no Maa-amet data — verified 2026-09-13 with osmium tags-filter
nwr/contour against ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf),
so p100/p231/p287 stay NULL with a buyer-check reason, and p34/p305
are coarse OSM-derived PROXIES. Reasons say "hinnang" (estimate) and
name what is missing — never sun hours, lux, window positions, or a
measured driveway grade.

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
tower footprints and facade polygons, PR #118):
* tall predicate (building:levels >= 4, sol_tall precedent from
  dims_group18_solar.py #123): levels-tagged buildings parse to
  integers; >= 4 reads tall. Untagged buildings read as low-rise BY
  DESIGN (levels coverage is sparse, ~6% of buildings, so absence is
  weak evidence of lowness — the p34 fallback stays below 100).
* glass predicate (building:material glass/mirror): 382 features
  county-wide (337 glass + 12 mirror + untagged relation members
  that drop out in keep_glass). Sparse by nature — glass towers are
  rare; absence in-window reads as calm evidence, capped below 100.
* window key: exactly 1 feature county-wide — window placement has
  no mappable signal at all (floorplan fact, OTA PR #131 precedent).
* incline key: 1430 ways with a value, of which 1068 are highway=
  steps (pedestrian stairs), 146 footway, 90 path; 1342 carry only
  directional up/down (no grade magnitude); 83 are highway=service
  and ~0 driveways carry a numeric grade. Steps are not driveways
  and up/down cannot discriminate a 2% ramp from a 15% slope — a
  proximity gradient would be fake precision.
* indoor lighting keys: OSM carries no per-room lux/lamp data by
  construction — zoom-ready lighting is an interior fact (lamp
  placement, window behind/in front of the desk), never an area
  signal.

Judgment calls (reviewable per AGENTS.md section 7.5):
* p34 reuses the raster formula exactly (round(100*d/(d+150))):
  the dim and the map can never disagree. Under 75 m the reason
  flags the obstruction check (varjutus); the dim never issues sun
  hours ("päikesetunde mõõdetud pole"). halfM=150 m: a 15 m block
  150 m away subtends ~6 degrees of sky — minor loss; adjacent is
  severe. Trees are OUT by design (deciduous bias precedent, #123):
  leafy low-rise Nõmme has good daylight; only tall masses count.
* p305 bands track the raster formula loosely (100*d/(d+200):
  100 m ~= 33, 200 m = 50, 400 m ~= 67): <=100 m scores 35, <=200 m
  50, mapped-but-far stays 70 (commbleed precedent), absence in 2 km
  reads 85. Under 200 m the reason flags the glare check (pimestus
  madala päiksega). Glare is an outside-view fact: the scorer reads
  distance to the facade, never inside it.
* One POI carries one kind: tall wins over glass (sol_tall
  precedent, #123) — a 20-storey glass tower CERTAINLY blocks
  daylight while its glare is orientation-dependent. Levels tagging
  is sparse, so most glass facades still read as glare; the county
  raster (separate extracts) has no conflict at all.
* p100/p231/p287 return None for EVERY input including missing
  origin: inventing a gradient from zero signal would be fake
  precision (OTA PR #131 precedent). The reasons point at the
  floorplan / site-visit / buyer-lamp check instead.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP18A_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP18A_POI_KIND, centroiding way
geometries to points (tower footprints and facade polygons are
ways/relations; raw way nodes would multi-count — residual twin
risk per PR #118 must be noted by the hook author), and rebalancing
livability.WEIGHTS must be one joint change across all parameter
batches — existing tests pin set(WEIGHTS) exactly, so per-batch
WEIGHTS edits would break every sibling.
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
# Radii are judgment calls: tall masses dense in town (800 m search),
# glass towers sparse (2 km). Both node[...] and way[...] lines are
# required (nwr/ parity): tower footprints and facade polygons are
# ways/relations; node-only drops them (PR #118).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP18A_OVERPASS_FRAGMENT = """
  node["building"](around:800,{lat},{lon});
  node["building:levels"](around:800,{lat},{lon});
  node["building:material"~"glass|mirror"](around:2000,{lat},{lon});
  way["building"](around:800,{lat},{lon});
  way["building:levels"](around:800,{lat},{lon});
  way["building:material"~"glass|mirror"](around:2000,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
#: "tallmass" = levels>=4 tower for the daylight-obstruction dim
#: (untagged buildings stay low-rise: absence is weak evidence);
#: "glassface" = glass/mirror facade for the glare dim. One POI
#: carries one kind: tall wins over glass (mass certainty beats
#: orientation-dependent glare — see module docstring).
GROUP18A_POI_KIND = [
    ("building:levels", {"tall": "tallmass"}),
    ("building:material", {"glass": "glassface", "mirror": "glassface"}),
]

#: Facade materials that reflect (glare sources).
GLASS_MATERIALS = ("glass", "mirror")

#: Levels at/above which a building casts meaningful shade at Tallinn
#: latitudes (sol_tall precedent, dims_group18_solar.py #123).
TALL_LEVELS = 4


def _first_value(value) -> str:
    try:
        return str(value).split(";")[0].strip()
    except (TypeError, AttributeError):
        return ""


def _levels_int(tags: dict) -> Optional[int]:
    try:
        return int(_first_value(tags.get("building:levels")))
    except (ValueError, TypeError):
        return None


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 18-rest-A kind matching the OSM tags, else None. Pure.

    building:levels >= 4 maps to "tallmass" (a glass tower is mass
    first — its daylight obstruction is certain, its glare is
    orientation-dependent); building:material glass/mirror maps to
    "glassface". Untagged buildings map to None (absence is weak
    evidence of lowness, never a scored fact).
    """
    tags = tags or {}
    n = _levels_int(tags)
    if n is not None and n >= TALL_LEVELS:
        return "tallmass"
    if _first_value(tags.get("building:material")) in GLASS_MATERIALS:
        return "glassface"
    return None


# ---------------------------------------------------------------------------
# p34: natural light (mapped tall-mass openness hinnang).
# ---------------------------------------------------------------------------

#: Raster half in metres (mirrors G18A_CAL.dayopen in the TS + builder).
DAYOPEN_HALF_M = 150.0


def dim_dayopen(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p34: daylight-openness calmness 100*d/(d+150) from nearest tall mass."""
    if not origin or pois is None:
        return None, "Päevavalguse info puudub (hoonestuse hetktõmmis)"
    m = _nearest_m(origin, pois, {"tallmass"})
    if m is None:
        return 90, "Kõrge hoonestus 800 m raadiuses kaardistamata (hinnang: avatud taevas)"
    s = int(round(100.0 * m / (m + DAYOPEN_HALF_M)))
    if m < 75:
        return s, "Päevavalgus varjutatud (hinnang): lähim kõrghoone %s — kontrolli varjutust (päikesetunde mõõdetud pole)" % _fmt_m(m)
    return s, "Päevavalguse avatus %s lähima kõrghooneni (hinnang, mõõdetud päikesetundideta)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p305: exterior reflective glare (mapped glass-facade distance hinnang).
# ---------------------------------------------------------------------------

#: Raster half in metres (mirrors G18A_CAL.glassglare in the TS + builder).
GLASSGLARE_HALF_M = 200.0


def dim_glassglare(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p305: glare-exposure calmness from nearest mapped glass facade."""
    if not origin or pois is None:
        return None, "Peegelduspimestuse info puudub (fassaadide hetktõmmis)"
    m = _nearest_m(origin, pois, {"glassface"})
    if m is None:
        return 85, "Klaasfassaad 2 km raadiuses kaardistamata (hinnang: peegeldusvaba)"
    s = _band(m, [(100, 35), (200, 50), (400, 70)])
    assert s is not None
    if s <= 50:
        return s, "Peegelduspimestus (hinnang): lähim klaasfassaad %s — kontrolli pimestust madala päiksega" % _fmt_m(m)
    return s, "Peegelduspimestus (hinnang): lähim klaasfassaad %s (rahulik)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p100/p231/p287: documented no-map NULLs (OTA PR #131 precedent).
# Each is a per-unit/per-parcel/per-room fact with no honest area
# signal; the scorer reports the gap with a concrete buyer check
# instead of a faked number.
# ---------------------------------------------------------------------------

def dim_crossvent(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p100: NULL — window placement is a per-floorplan fact (no map)."""
    return None, "Akende paigutus ja risttuulutus teadmata (korruseplaan; hetktõmmises on 1 akna-märgend kogu maakonnas — kontrolli plaanilt)"


def dim_driveway(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p231: NULL — driveway grade is a per-parcel construction fact (no map)."""
    return None, "Sissesõidutee kalle teadmata (ehitusfakt; hetktõmmises pole kõrgusmudelit ja kalde-märgendid on trepid/suund — kontrolli kohapeal)"


def dim_zoomlight(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p287: NULL — video-call lighting is a per-room interior fact (no map)."""
    return None, "Videokõne-valgus teadmata (toasisene fakt: lamp ja aken laua suhtes — kaardilt pole mõõdetav, kontrolli õhtusel vaatlusel)"


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP18A_DIMS: Dict[str, Tuple[str, object]] = {
    "crossvent": ("Risttuulutus (kontroll)", dim_crossvent),
    "driveway": ("Sissesõidutee kalle (kontroll)", dim_driveway),
    "zoomlight": ("Videokõne-valgus (kontroll)", dim_zoomlight),
    "dayopen": ("Päevavalguse avatus (proksi)", dim_dayopen),
    "glassglare": ("Peegelduspimestus (proksi)", dim_glassglare),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP18A_PARAM_IDS = {
    "crossvent": 100,
    "driveway": 231,
    "zoomlight": 287,
    "dayopen": 34,
    "glassglare": 305,
}


def score_group18resta(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 18-rest-A dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP18A_DIMS.items():
        v, reason = fn(origin, pois)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
