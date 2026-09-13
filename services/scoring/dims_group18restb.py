"""Group 18 rest per-listing dimensions, batch B (issue #173).

Params (this agent only — sibling batches own disjoint sets):
* p394 patio sun orientation (ALWAYS None — per-building azimuth fact)
* p403 natural EM shielding (ALWAYS None — terrain + transmitter fact)
* p405 circadian lighting potential (mapped-building openness hinnang)
* p468 corner lot fishbowl effect (mapped corner-furniture hinnang)
* p479 roof moss/algae shading (mapped-forest distance, raster formula)

HONESTY (AGENTS.md section 7.2): Maa-amet LoD2 3D CityGML meshes, ALS
LiDAR point clouds, PVLib/PVGIS solar models and any RF transmitter
register are NOT in the 2026-09-12 snapshot, so p394/p403 stay NULL
with a buyer-check reason, and p405/p468/p479 are coarse OSM-derived
PROXIES. Reasons say "hinnang" (estimate) and name what is missing —
never a lux measurement, a cadastral corner-lot ruling, or a roof
moisture reading.

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
~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at runtime):
* forest predicate (natural=wood or landuse=forest): 17,113 objects
  county-wide (8,683 forest polygons + 8,367 wood lines + 63 points).
  43,522 natural=tree points drop out BY DESIGN (a street tree is not
  a moss stand — a panel is not a farm, #163 precedent).
* buildings: ~/hf-data/2026-09-12/osm/derived-buildings.json holds
  252,140 bare centroids (no tags to verify); any building=* value
  except "no" counts.
* corner furniture (highway=crossing/traffic_signals or junction=yes)
  is a LIVE SUBSET ONLY: the map (fishbowl) scores full ≥3-arm
  foot-graph junctions (144,580 county-wide, 139,474 settled), which
  have no OSM tags to fetch per listing. The dim scores mapped corner
  furniture instead — same direction (near = exposed), honestly
  narrower source (the reason says so).
* patio orientation: zero azimuth keys anywhere — the snapshot
  carries building centroids only, no footprints/heights/orientation.
* EM shielding: no DEM and no transmitter objects anywhere in the
  snapshot; forest density alone cannot carry an EM claim.

Judgment calls (reviewable per AGENTS.md section 7.5):
* p405 bands track the raster loosely (raw 300 m counts at probes:
  Nõmme/Pirita 0-10, Paljassaare/Viimsi/Ülemiste 19-29, Lasnamäe 37,
  Õismäe 55, Viru/Balti 90-100, Kohtuotsa 226): <=10 scores 90
  (open), <=30 scores 75, <=60 scores 60, <=100 scores 45, beyond 30
  (dense canyon). Dense-city reasons flag the overshadowing check.
* p468 bands track the raster loosely (100*d/(d+150): 100 m ~= 40,
  200 m ~= 57, 400 m ~= 73): <=100 m scores 30, <=200 m 50, <=400 m
  70, beyond 80 (calm mid-block). Under 100 m the reason flags the
  privacy check (privaatsus). Absence means no MAPPED furniture, and
  the reason says so — never "no corners".
* p479 reuses the raster formula exactly (round(100*d/(d+250))):
  the dim and the map can never disagree. Under 150 m the reason
  flags the roof-aspect check (katuse suund); the dim never issues a
  moisture reading ("kontrolli", never a measurement).
* p394/p403 return None for EVERY input including missing
  origin: inventing an azimuth from centroids (or an EM field from
  zero transmitters) would be fake precision (OTA PR #131
  precedent). The reasons point at the LoD2/DTM check the buyer must
  do instead.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP18B_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP18B_POI_KIND, centroiding way
geometries to points (forest stands are ways/relations; raw way
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
# Radii are judgment calls: buildings dense in town (300 m search),
# corner furniture pocket-scale (400 m), forest stands sparse (1000 m).
# Both node[...] and way[...] lines are required (nwr/ parity): forest
# stands and buildings are ways/relations; node-only drops them
# (PR #118).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP18B_OVERPASS_FRAGMENT = """
  node["building"](around:300,{lat},{lon});
  node["highway"~"crossing|traffic_signals"](around:400,{lat},{lon});
  node["junction"="yes"](around:400,{lat},{lon});
  node["natural"="wood"](around:1000,{lat},{lon});
  node["landuse"="forest"](around:1000,{lat},{lon});
  way["building"](around:300,{lat},{lon});
  way["highway"~"crossing|traffic_signals"](around:400,{lat},{lon});
  way["natural"="wood"](around:1000,{lat},{lon});
  way["landuse"="forest"](around:1000,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
#: "building" = any mapped building for the openness dim (building=no
#: maps to None — demolished/proposed is not shade); "cornerfurn" =
#: mapped corner furniture for the fishbowl dim (a live SUBSET of the
#: map's full junction set — the reason says so); "forest" = mapped
#: forest stand for the moss dim (street trees map to None: a street
#: tree is not a moss stand).
GROUP18B_POI_KIND = [
    ("building", {"yes": "building"}),
    ("highway", {"crossing": "cornerfurn", "traffic_signals": "cornerfurn"}),
    ("junction", {"yes": "cornerfurn"}),
    ("natural", {"wood": "forest"}),
    ("landuse", {"forest": "forest"}),
]


def _first_value(value) -> str:
    if value is None:
        return ""
    try:
        return str(value).split(";")[0].strip()
    except (TypeError, AttributeError):
        return ""


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 18-batch-B kind matching the OSM tags, else None. Pure.

    Any building=* value except "no" maps to "building" (values are
    open-ended: yes/house/apartments/...); highway crossing /
    traffic_signals and junction=yes map to "cornerfurn" (the live
    subset of the map's junction set); natural=wood and
    landuse=forest map to "forest". natural=tree maps to None by
    design (a street tree is not a moss stand).
    """
    tags = tags or {}
    if _first_value(tags.get("building")) not in ("", "no"):
        return "building"
    if _first_value(tags.get("highway")) in ("crossing", "traffic_signals"):
        return "cornerfurn"
    if _first_value(tags.get("junction")) == "yes":
        return "cornerfurn"
    if _first_value(tags.get("natural")) == "wood":
        return "forest"
    if _first_value(tags.get("landuse")) == "forest":
        return "forest"
    return None


# ---------------------------------------------------------------------------
# p405: circadian lighting potential (building-openness hinnang).
# ---------------------------------------------------------------------------

#: Search radius for the building count (open-sky pocket reading).
DAYLIGHT_RADIUS_M = 300.0


def dim_daylight(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p405: daylight reading from mapped buildings within 300 m."""
    if not origin or pois is None:
        return None, "Päevavalguse info puudub (hoonete hetktõmmis)"
    n = _count_within_m(origin, pois, {"building"}, DAYLIGHT_RADIUS_M)
    s = _band(float(n), [(10, 90), (30, 75), (60, 60), (100, 45),
                         (float("inf"), 30)])
    assert s is not None
    if s <= 45:
        return s, "Päevavalgus (hinnang): 300 m raadiuses %d hoonet — tihe vari, kontrolli varjutust (luksimõõtmine puudub)" % n
    return s, "Päevavalgus (hinnang): 300 m raadiuses %d hoonet (avar)" % n


# ---------------------------------------------------------------------------
# p468: corner lot fishbowl effect (corner-furniture hinnang).
# ---------------------------------------------------------------------------

#: Search radius for corner furniture (pocket-scale exposure reading).
FISHBOWL_RADIUS_M = 400.0


def dim_fishbowl(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p468: corner-exposure reading from mapped corner furniture."""
    if not origin or pois is None:
        return None, "Nurgakrundi info puudub (ristmike hetktõmmis)"
    m = _nearest_m(origin, pois, {"cornerfurn"})
    if m is None:
        return 80, "Nurgakrundi-mööbel 400 m raadiuses kaardistamata (hinnang: rahulik kvartal, katastriotsus puudub)"
    s = _band(m, [(100, 30), (200, 50), (400, 70), (float("inf"), 80)])
    assert s is not None
    if s <= 50:
        return s, "Nurgakrundi efekt (hinnang): lähim ristmiku-mööbel %s — avatud kahelt poolt, kontrolli privaatsust" % _fmt_m(m)
    return s, "Nurgakrundi efekt (hinnang): lähim ristmiku-mööbel %s (kaitstud)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p479: roof moss/algae shading (mapped-forest distance, raster formula).
# ---------------------------------------------------------------------------

#: Raster half in metres (mirrors G18B_CAL.mossrisk in the TS + builder).
MOSSRISK_HALF_M = 250.0

#: Search radius for forest stands (sparse source, wide net).
MOSSRISK_RADIUS_M = 1000.0


def dim_mossrisk(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p479: moss-pressure calmness 100*d/(d+250) from nearest mapped stand."""
    if not origin or pois is None:
        return None, "Samblariski info puudub (metsade hetktõmmis)"
    near = [p for p in pois if p.get("kind") == "forest" and p.get("lat") is not None
            and _haversine_m(origin, p["lat"], p["lon"]) <= MOSSRISK_RADIUS_M]
    m = _nearest_m(origin, near, {"forest"})
    if m is None:
        return 88, "Mets 1 km raadiuses kaardistamata (hinnang: kuiv katus)"
    s = int(round(100.0 * m / (m + MOSSRISK_HALF_M)))
    if m < 150:
        return s, "Samblarisk %s metsaservast (hinnang) — kontrolli katuse suunda ja varju (niiskusmõõtmine puudub)" % _fmt_m(m)
    return s, "Samblarisk (hinnang): lähim mets %s (niiskusmõõtmine puudub)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p394/p403: documented no-map registry NULLs (OTA PR #131 precedent).
# Each is a per-building/per-terrain fact with no honest area signal;
# the scorer reports the gap with a concrete buyer check instead of a
# faked number.
# ---------------------------------------------------------------------------

def dim_patiosun(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p394: NULL — patio sun needs per-building azimuth (no map)."""
    return None, "Patio päikese suund teadmata (hoone asimuut; hetktõmmises on ainult hoonekeskmed — kontrolli Maa-amet LoD2 + päikesemudelist)"


def dim_emshield(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p403: NULL — EM shielding needs terrain + transmitters (no map)."""
    return None, "Looduslik EM-varjestus teadmata (reljeef + saatjad; hetktõmmises pole DEM-i ega saatjaregistrit — metsa tihedus üksi EM-väidet ei kanna)"


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP18B_DIMS: Dict[str, Tuple[str, object]] = {
    "patiosun": ("Patio päike (kontroll)", dim_patiosun),
    "emshield": ("EM-varjestus (kontroll)", dim_emshield),
    "daylight": ("Päevavalgus (proksi)", dim_daylight),
    "fishbowl": ("Nurgakrunt (proksi)", dim_fishbowl),
    "mossrisk": ("Samblarisk (proksi)", dim_mossrisk),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP18B_PARAM_IDS = {
    "patiosun": 394,
    "emshield": 403,
    "daylight": 405,
    "fishbowl": 468,
    "mossrisk": 479,
}


def score_group18restb(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 18-rest-B dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP18B_DIMS.items():
        v, reason = fn(origin, pois)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
