"""Group 7 environmental-health dimensions: batch G07C (issue #142).

Params (this agent only — sibling batches own disjoint sets):
* p257 endemic local pests (vektorihinnang: mapped tick/mosquito habitat
  proximity — wood/forest/scrub/heath/meadow/wetland)
* p260 ambient dust and pollen trap (tolmuproksi: heavy-road/quarry/
  industrial/construction proximity; the POLLEN side belongs to sibling
  p137, issue #140 — the reason says so)
* p316 municipal water treatment (no-map: central-supply scorer only)
* p401 VOC off-gassing (no-map: indoor phenomenon, listing-age scorer)
* p402 water hardness (no-map: Tallinn surface-water scorer)

HONESTY (load-bearing, AGENTS.md section 7.2): pest-surveillance trap
counts, Õhuseire PM10/pollen readings, ÜVK treatment telemetry, indoor
VOC measurements and a hardness registry are ALL absent from the
2026-09-12 snapshot, so no scorer below reports a measured quantity.
p257/p260 are OSM PROXIMITY proxies (every reason says "proksi" and
"hinnang"); p316/p401/p402 score coarse listing/regional knowledge and
return None when it is missing — never a faked number.

Boundary with sibling batches (reviewable per AGENTS.md section 7.5):
* p67 (issue #140, larger wildlife) may share wood/forest sources —
  different question (nuisance animals vs disease vectors).
* p137 (issue #140, seasonal allergens) owns pollen; p260 here scores
  DUST only, and its reason defers pollen to p137.
* p408 (lowspec, PR #131) already maps heavy/industrial proximity as
  noise; p260 reuses those sources for the DUST question, which lowspec
  does not answer.
* p450/wildcorr (issue #143) shares forest/wetland sources — different
  question (corridor connectivity vs vector proximity).

Style mirrors services/scoring/livability.py and sibling batch
dims_group09.py (#112): pure (origin, pois) -> (Optional[int 0..100],
Estonian reason) scorers, absolute scales, hermetic tests. p316/p401/
p402 take small extra listing/region arguments (dim_connect/dim_safety
precedent in livability.py). Network lives only in
livability.fetch_pois; this module adds no network calls, only the query
fragment + tag mapping the live path needs.

Tag verification (2026-09-12, done once by the author with osmium
tags-count against ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf,
NOT at runtime; extraction used nwr/ throughout, PR #118):
* natural=wood x3643, landuse=forest x4539, natural=scrub x1652,
  landuse=meadow x1549, natural=wetland x606, natural=heath x171
  (habitat set; the map builder drops < 2500 m2 micro-fragments and
  fills polygon interiors — the per-listing scorer below uses nearest
  mapped habitat honestly without those refinements).
* landuse=industrial x600, landuse=quarry x78, landuse=construction
  x166, man_made=works x80 (dust set; heavy roads come from the car
  graph offline — the live fragment below covers highway classes).
* man_made=water_works x1 (a distance gradient to one plant would be
  fake precision — hence p316 no-map).

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP07C_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP07C_POI_KIND, and rebalancing
livability.WEIGHTS (+ apps/web/lib/weights.ts sync) must be one joint
change across all parameter batches — existing tests pin set(WEIGHTS)
exactly, so per-batch WEIGHTS edits would break every sibling.
"""

from typing import Callable, Dict, List, Optional, Tuple

from livability import _band, _fmt_m, _nearest_m

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# New POI kinds + Overpass fragment for the live path.
# ---------------------------------------------------------------------------

#: Extra (tagkey, {tagvalue: kind}) rows for livability._POI_KIND.
GROUP07C_POI_KIND = [
    ("natural", {"wood": "vector_habitat", "scrub": "vector_habitat",
                 "heath": "vector_habitat", "wetland": "vector_habitat"}),
    ("landuse", {"forest": "vector_habitat", "meadow": "vector_habitat",
                 "quarry": "dust_source", "industrial": "dust_source",
                 "construction": "dust_source"}),
    ("highway", {"motorway": "dust_source", "trunk": "dust_source",
                 "primary": "dust_source"}),
]

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP07C_OVERPASS_FRAGMENT = """
  node["natural"~"wood|scrub|heath|wetland"](around:1500,{lat},{lon});
  node["landuse"~"forest|meadow|quarry|industrial|construction"](around:1500,{lat},{lon});
  node["highway"~"motorway|trunk|primary"](around:1000,{lat},{lon});
  way["natural"~"wood|scrub|heath|wetland"](around:1500,{lat},{lon});
  way["landuse"~"forest|meadow|quarry|industrial|construction"](around:1500,{lat},{lon});
  way["highway"~"motorway|trunk|primary"](around:1000,{lat},{lon});"""


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 7C kind matching the OSM tags, else None. Pure."""
    for tagkey, mapping in GROUP07C_POI_KIND:
        val = (tags or {}).get(tagkey, "").split(";")[0]
        if val in mapping:
            return mapping[val]
    return None


# ---------------------------------------------------------------------------
# p257: endemic-pest vector-habitat proxy (nearest mapped habitat).
# ---------------------------------------------------------------------------

def dim_vector_habitat(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p257: calmness from distance to the nearest vector habitat."""
    if not origin or pois is None:
        return None, "Vektorielupaiga info puudub (hinnang)"
    m = _nearest_m(origin, pois, {"vector_habitat"})
    if m is None:
        return 92, "Kaardistatud elupaik kaugel (vektorihinnang, proksi)"
    s = _band(m, [(150, 30), (300, 50), (600, 70), (1200, 85)])
    assert s is not None
    return s, "Vektorihinnang (proksi): lähim elupaik %s" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p260: ambient-dust proxy (DUST side only; pollen -> sibling p137).
# ---------------------------------------------------------------------------

def dim_dust(origin: Optional[Tuple[float, float]],
             pois: Optional[List[dict]]) -> Score:
    """p260: calmness from distance to the nearest dust source."""
    if not origin or pois is None:
        return None, "Tolmuallika info puudub (hinnang)"
    m = _nearest_m(origin, pois, {"dust_source"})
    if m is None:
        return 92, "Kaardistatud tolmuallikas kaugel (tolmuproksi)"
    s = _band(m, [(200, 35), (400, 55), (800, 75), (1500, 88)])
    assert s is not None
    return s, "Tolmuproksi (hinnang): lähim allikas %s (õietolm: p137)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p316/p402: Tallinn central-water knowledge (documented no-map params).
# ---------------------------------------------------------------------------

#: Approximate Tallinn central-supply box (lon_min, lat_min, lon_max, lat_max).
#: Judgment call: inside ~= Tallinna Vesi surface water (Ülemiste). The
#: reason always says "hinnang" so a boundary listing is reviewable, not
#: presented as metered truth.
TALLINN_SUPPLY_BBOX = (24.55, 59.35, 24.95, 59.50)


def _in_tallinn_supply(origin: Tuple[float, float]) -> bool:
    lon, lat = origin[1], origin[0]
    lo0, la0, lo1, la1 = TALLINN_SUPPLY_BBOX
    return lo0 <= lon <= lo1 and la0 <= lat <= la1


def dim_water_treatment(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]],
                        water_source: Optional[str] = None) -> Score:
    """p316: municipal-treatment confidence (no-map; coarse knowledge).

    water_source: "central" | "well" | None (listing attribute).
    """
    if water_source == "well":
        return None, "Kaevuvesi: käitlusjaama register puudub (hinnangut ei anta)"
    if water_source == "central" or (origin is not None and _in_tallinn_supply(origin)):
        return 85, "Tsentraalne puhastatud vesi (hinnang, Ülemiste)"
    return None, "Veekäitluse register puudub (hinnangut ei anta)"


def dim_water_hardness(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]],
                       water_source: Optional[str] = None) -> Score:
    """p402: hardness comfort (no-map; coarse knowledge).

    Tallinn central water is soft surface water (appliance-friendly);
    limestone-well water runs harder. Unknown stays None.
    """
    if water_source == "well" or water_source == "central":
        if water_source == "central":
            return 80, "Pehme pinnavesi (Tallinna Vesi, hinnang)"
        return 45, "Kaevuvesi: paekivil karedam (hinnang)"
    if origin is not None and _in_tallinn_supply(origin):
        return 80, "Pehme pinnavesi (Tallinna Vesi, hinnang)"
    return None, "Kareduse register puudub (hinnangut ei anta)"


# ---------------------------------------------------------------------------
# p401: VOC off-gassing from listing age (no-map; indoor phenomenon).
# ---------------------------------------------------------------------------

def dim_voc(origin: Optional[Tuple[float, float]],
            pois: Optional[List[dict]],
            building_year: Optional[int] = None,
            renovated_year: Optional[int] = None,
            current_year: int = 2026) -> Score:
    """p401: off-gassing caution from finishes age (no-map).

    Fresh finishes off-gas most: a new/renovated flat scores modestly
    with ventilation advice; a settled one scores calmly. No indoor
    measurement exists in the snapshot, so unknown age stays None —
    never a faked g/m3 reading.
    """
    ages = []
    if isinstance(building_year, int):
        ages.append(current_year - building_year)
    if isinstance(renovated_year, int):
        ages.append(current_year - renovated_year)
    if not ages:
        return None, "Hoone vanus teadmata (VOC-hinnangut ei anta)"
    if min(ages) <= 2:
        return 50, "Värske viimistlus: tuuluta esimesed aastad (hinnang)"
    return 85, "Sisseelatud viimistlus (VOC-hinnang)"


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP07C_DIMS: Dict[str, Tuple[str, Callable[..., Score]]] = {
    "vector_habitat": ("Vektorielupaik (proksi)", dim_vector_habitat),
    "dust": ("Tolm (proksi)", dim_dust),
    "water_treatment": ("Veekäitlus (hinnang)", dim_water_treatment),
    "voc": ("VOC (hinnang)", dim_voc),
    "water_hardness": ("Veekaredus (hinnang)", dim_water_hardness),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP07C_PARAM_IDS = {
    "vector_habitat": 257,
    "dust": 260,
    "water_treatment": 316,
    "voc": 401,
    "water_hardness": 402,
}


def score_group07c(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]],
                   water_source: Optional[str] = None,
                   building_year: Optional[int] = None,
                   renovated_year: Optional[int] = None,
                   current_year: int = 2026) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 7C dims at once: ({param: score}, [reasons]).

    Listing knowledge (water_source / building_year / renovated_year)
    threads explicitly into the no-map dims; the OSM-proxy dims take
    (origin, pois) only.
    """
    calls: Dict[str, Score] = {
        "vector_habitat": dim_vector_habitat(origin, pois),
        "dust": dim_dust(origin, pois),
        "water_treatment": dim_water_treatment(origin, pois, water_source),
        "voc": dim_voc(origin, pois, building_year, renovated_year,
                       current_year),
        "water_hardness": dim_water_hardness(origin, pois, water_source),
    }
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (v, reason) in calls.items():
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
