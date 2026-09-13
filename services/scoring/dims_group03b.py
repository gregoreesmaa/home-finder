"""Group 3 cadastre ground-truth per-listing dimensions, batch B (issue #152).

Params (this agent only — sibling batches own disjoint sets):
* p183 local water table depth (mapped shallow-table-indicator proximity)
* p184 geothermal suitability (ALWAYS None — no honest signal, do not fake)
* p201 septic leach field location (mapped setback-receptor proximity)
* p228 water rights, riparian (mapped flowing-water proximity)
* p251 soil percolation rate (ALWAYS None — no honest signal, do not fake)

HONESTY (AGENTS.md section 7.2): the Maa-amet Geoportaal WFS grids
(hydrogeology, subsurface heat, soil DB) are NOT in the 2026-09-12
snapshot, so p184/p251 stay NULL with a buyer-check reason, and
p183/p201/p228 are coarse OSM-derived PROXIES. Reasons say "hinnang"
(estimate) and name what is missing — never measured water tables,
drilling suitability, percolation rates, or resolved water rights.

Style mirrors services/scoring/livability.py and sibling batch
dims_group10c.py (#121): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls, only the query fragment + tag mapping the live path needs.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #121).

Tag verification (2026-09-12, done once by the author with osmium
tags-filter/tags-count against
~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at runtime;
nwr/ filters throughout — node-only would silently drop way-mapped
wetlands, PR #118):
* man_made=water_well: 28 points; natural=spring: 35 points (+4
  lines) — shallow-groundwater indicators, sparse county-wide (a
  gradient map from 63 points would paint Tallinn flat red, so p183
  stays a per-listing dim; the area question is covered by the p50
  drainage proxy, #151).
* natural=wetland: 606 polygons + 548 lines — shallow-table +
  septic-setback evidence (dense enough for nearest-distance dims,
  far too binary for a second drainage gradient next to #151).
* waterway=river/stream/canal/ditch/drain: flowing lines (riparian
  rights attach to watercourses, not ponds — disjoint from p338
  weedwater's natural=water amenity by kind AND framing).
* derived-soil.geojson: 53 features, keys barrier/landuse/gate junk,
  ZERO soil attributes — p251 has nothing to calibrate against.

Judgment calls (reviewable per AGENTS.md section 7.5):
* p183 scores the NEAREST shallow-table indicator (well/spring/
  wetland): near = shallow table likely = LOW (basement/foundation
  risk). Absence within 3 km is a WEAK good sign only (cap 75, reason
  says "nõrk hea-märk"): unmapped is not deep.
* p201 scores the nearest setback receptor (well/spring/wetland): a
  leach field needs distance from receptors, so near = constrained =
  LOW. The reason names the UVK gap explicitly (sewered Tallinn
  flats do not need a field at all).
* p228 scores the nearest FLOWING water only (ponds/lakes excluded):
  near = riparian questions likely = MID (flags the title check
  without resolving it, never a rights guarantee). Far is neutral
  (85 cap): no frontage also means no riparian benefit to score.
* p184/p251 return None for EVERY input including missing origin:
  inventing a gradient from zero signal would be fake precision
  (OTA PR #131 precedent). The reasons point at the registry/KOV
  check the buyer must do instead.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP03B_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP03B_POI_KIND, centroiding way
geometries to points (wetlands/waterways are ways/relations; raw
way nodes would multi-count — residual twin risk per PR #118 must
be noted by the hook author), and rebalancing livability.WEIGHTS
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
# Radii are judgment calls: shallow-table indicators mid-sparse (3 km
# search), setback receptors checked tight (1 km), flowing water
# mid-density (2 km). Both node[...] and way[...] lines are required
# (nwr/ parity): wells are points but wetlands/waterways are
# ways/relations; node-only drops them (PR #118).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP03B_OVERPASS_FRAGMENT = """
  node["man_made"="water_well"](around:3000,{lat},{lon});
  node["natural"="spring"](around:3000,{lat},{lon});
  node["natural"="wetland"](around:3000,{lat},{lon});
  node["waterway"~"river|stream|canal|ditch|drain"](around:2000,{lat},{lon});
  way["natural"="wetland"](around:3000,{lat},{lon});
  way["waterway"~"river|stream|canal|ditch|drain"](around:2000,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
#: "shallowsrc" = shallow-table indicator AND septic-setback receptor
#: (wells/springs); "wetland" likewise for wetlands (kept separate so
#: the hook author can weight or split them); "flowwater" = flowing
#: waterways only (ponds/lakes stay p338 weedwater's amenity kind).
GROUP03B_POI_KIND = [
    ("man_made", {"water_well": "shallowsrc"}),
    ("natural", {"spring": "shallowsrc", "wetland": "wetland"}),
    ("waterway", {"river": "flowwater", "stream": "flowwater",
                  "canal": "flowwater", "ditch": "flowwater",
                  "drain": "flowwater"}),
]


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 3-batch-B kind matching the OSM tags, else None. Pure.

    wetland maps to "wetland" (not "shallowsrc") even though both dims
    consume it — the split keeps the water-table vs septic framings
    auditable at the kind level.
    """
    tags = tags or {}
    ww = str(tags.get("waterway", "")).split(";")[0]
    if ww in ("river", "stream", "canal", "ditch", "drain"):
        return "flowwater"
    if str(tags.get("man_made", "")).split(";")[0] == "water_well":
        return "shallowsrc"
    nat = str(tags.get("natural", "")).split(";")[0]
    if nat == "spring":
        return "shallowsrc"
    if nat == "wetland":
        return "wetland"
    return None


# ---------------------------------------------------------------------------
# p183: local water table depth (mapped shallow-table-indicator proxy).
# ---------------------------------------------------------------------------

#: Shallow-table-indicator search radius in metres (mid-sparse tier).
WATERTABLE_RADIUS_M = 3000.0


def dim_water_table(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p183: nearest mapped shallow-groundwater indicator (kaev/allikas/märgala)."""
    if not origin or pois is None:
        return None, "Veetaseme info puudub"
    m = _nearest_m(origin, pois, {"shallowsrc", "wetland"})
    if m is None or m > WATERTABLE_RADIUS_M:
        return 75, ("Kaardistatud kõrge veetaseme tunnust 3 km raadiuses pole "
                    "(nõrk hea-märk, mitte mõõdetud veetase; Maa-ameti "
                    "hüdrogeoloogia registrit snapshots pole)")
    s = _band(m, [(200, 35), (600, 55), (1500, 70)])
    return s, ("Lähim kaardistatud kõrge veetaseme tunnus %s "
               "(veetaseme hinnang, mitte puurkaevu mõõtmine)") % _fmt_m(m)


# ---------------------------------------------------------------------------
# p184: geothermal suitability (no honest signal — always None).
# ---------------------------------------------------------------------------

def dim_geothermal(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p184: NULL — subsurface grids are not in the snapshot (do not fake)."""
    return None, ("Geotermilise sobivuse registriandmeid (aluspõhi/soojusvoog) "
                  "snapshots pole — vajab Maa-ameti puurkoha hinnangut (EI OLE "
                  "hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p201: septic leach field location (mapped setback-receptor proxy).
# ---------------------------------------------------------------------------

#: Setback-receptor search radius in metres (tight tier).
SEPTIC_RADIUS_M = 1000.0


def dim_septic(origin: Optional[Tuple[float, float]],
               pois: Optional[List[dict]]) -> Score:
    """p201: nearest mapped receptor needing a leach-field setback."""
    if not origin or pois is None:
        return None, "Imbväljaku info puudub"
    m = _nearest_m(origin, pois, {"shallowsrc", "wetland"})
    if m is None or m > SEPTIC_RADIUS_M:
        return 85, ("Kaardistatud kaevu/allikat/märgala 1 km raadiuses pole "
                    "(nõrk hea-märk; ÜVK/kanalisatsiooni registrit snapshots "
                    "pole — hinnang eeldab lokaalset puhastitarvet)")
    s = _band(m, [(50, 40), (150, 60), (400, 75)])
    return s, ("Lähim imbväljaku kaugust vajav objekt %s "
               "(asendi-hinnang, mitte pinnase läbilaskvuse mõõtmine)") % _fmt_m(m)


# ---------------------------------------------------------------------------
# p228: water rights, riparian (mapped flowing-water proxy).
# ---------------------------------------------------------------------------

#: Flowing-water search radius in metres (mid-density tier).
WATERRIGHTS_RADIUS_M = 2000.0


def dim_water_rights(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p228: nearest mapped flowing water (kallasoniguse kontrollivajadus)."""
    if not origin or pois is None:
        return None, "Kallasõiguse info puudub"
    m = _nearest_m(origin, pois, {"flowwater"})
    if m is None or m > WATERRIGHTS_RADIUS_M:
        return 85, ("Kaardistatud vooluvett 2 km raadiuses pole "
                    "(kallasõiguse küsimust vee põhjal pole; "
                    "kinnistusraamatu kontrolli hinnang ei asenda)")
    s = _band(m, [(100, 55), (300, 70), (1000, 80)])
    return s, ("Lähim kaardistatud vooluvesi %s — võimalik kallasõiguse/ "
               "kaitsevööndi kontroll (hinnang, mitte õiguste lahendamine)") % _fmt_m(m)


# ---------------------------------------------------------------------------
# p251: soil percolation rate (no honest signal — always None).
# ---------------------------------------------------------------------------

def dim_soil_percolation(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p251: NULL — soil DB is not in the snapshot (do not fake)."""
    return None, ("Pinnase läbilaskvuse andmebaasi (ESDAC/SoilGrids) snapshots pole — "
                  "vajab KOV-tabeli / pinnaseuuringu kontrolli (EI OLE "
                  "hinnangut, ära feigi)")


GROUP03B_DIMS = (
    ("water_table", "p183", dim_water_table),
    ("geothermal", "p184", dim_geothermal),
    ("septic", "p201", dim_septic),
    ("water_rights", "p228", dim_water_rights),
    ("soil_percolation", "p251", dim_soil_percolation),
)


def score_group03b(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All five Group 3 batch-B dims for one listing (entry point for the
    weight-rebalance follow-up; keys match GROUP03B_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP03B_DIMS}
