"""Group 8 flood/climate per-listing dimensions, batch A (issue #167).

Params (this agent only — sibling batches own disjoint sets):
* p46 environmental risks (ALWAYS None — composite index, do not fake)
* p69 wildfire defensible space (mapped-fuel clearance hinnang)
* p112 flood history and elevation (ALWAYS None — no archive/DEM, do not fake)
* p117 sea level rise projections (ALWAYS None — no DEM/curve, do not fake)

HONESTY (AGENTS.md section 7.2): the Keskkonnaagentuur flood-hazard
WFS, Ilmateenistus/ERA5 archives, any flood-event register, any DEM
and any sea-level projection are NOT in the 2026-09-12 snapshot, so
p46/p112/p117 stay NULL with a buyer-check reason, and p69 is a
coarse OSM-derived PROXY. Reasons say "hinnang" (estimate) and name
what is missing — never burn probabilities, flood zones, return
periods, or sea-level curves.

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
tags-filter against ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf,
NOT at runtime; nwr/ filters throughout — node-only would silently
drop way-mapped forest polygons, PR #118):
* fuel predicate (landuse=forest, natural=wood/scrub/heath):
  20682 features = forest 4525 + wood 3625 + scrub 1652 + heath 171
  MultiPolygon areas + closed-way twins + ~100 Points — dense enough
  for a nearest-distance dim AND the clearance map
  (apps/web/lib/layers_group08a.ts). natural=grassland (lawns/parks)
  and landuse=meadow are NOT fuel and stay out by design (p257
  vectorhabitat owns the habitat reading).
* flood_prone probe (p112 evidence): 30 features county-wide, only 8
  with flood_prone=yes (all LineString river segments) — no polygon
  signal, so no honest flood gradient exists; any water field would
  re-skin p50 drainage (#151).
* Coastline distance would re-skin p340 shoredist (#154, same halfM)
  while faking projection precision — p117 stays NULL.

Judgment calls (reviewable per AGENTS.md section 7.5):
* p69 reuses the raster formula exactly (round(100*d/(d+100))): the
  dim and the map can never disagree. Under 30 m (no statutory
  defensible-space ring exists in Estonia — the 30 m is the
  international clearance rule of thumb, labelled as such) the reason
  flags the on-site check; the dim never issues a fire-service
  verdict ("kontrolli", never "ohutu/ohtlik").
* p46/p112/p117 return None for EVERY input including missing
  origin: inventing a gradient from zero signal would be fake
  precision (OTA PR #131 precedent). The reasons point at the
  KOV-table/archive/DEM check the buyer must do instead.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP08A_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP08A_POI_KIND, centroiding way
geometries to points (fuel stands are ways/relations; raw way nodes
would multi-count — residual twin risk per PR #118 must be noted by
the hook author), and rebalancing livability.WEIGHTS must be one
joint change across all parameter batches — existing tests pin
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
# Forest stands are dense county-wide (1.5 km search). Both node[...]
# and way[...] lines are required (nwr/ parity): fuel stands are
# ways/relations; node-only drops them (PR #118).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP08A_OVERPASS_FRAGMENT = """
  node["landuse"="forest"](around:1500,{lat},{lon});
  node["natural"~"wood|scrub|heath"](around:1500,{lat},{lon});
  way["landuse"="forest"](around:1500,{lat},{lon});
  way["natural"~"wood|scrub|heath"](around:1500,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
#: "fuel" = mapped flammable vegetation for the clearance dim (meadow,
#: grassland and wetland stay out — not fuel, see module docstring).
GROUP08A_POI_KIND = [
    ("landuse", {"forest": "fuel"}),
    ("natural", {"wood": "fuel", "scrub": "fuel", "heath": "fuel"}),
]


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 8-batch-A kind matching the OSM tags, else None. Pure.

    Meadow/grassland/wetland map to None (not fuel — p257's habitat
    reading); wooden houses map to None (p356 woodfire's signal).
    """
    tags = tags or {}
    if str(tags.get("landuse", "")).split(";")[0] == "forest":
        return "fuel"
    if str(tags.get("natural", "")).split(";")[0] in ("wood", "scrub", "heath"):
        return "fuel"
    return None


# ---------------------------------------------------------------------------
# p69: wildfire defensible space (mapped-fuel clearance, raster formula).
# ---------------------------------------------------------------------------

#: Raster half in metres (mirrors G08A_CAL.wildfire in the TS + builder).
WILDFIRE_HALF_M = 100.0


def dim_wildfire(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p69: defensible-space clearance 100*d/(d+100) from nearest fuel."""
    if not origin or pois is None:
        return None, "Metsatuleohu info puudub (kütuse hetktõmmis)"
    m = _nearest_m(origin, pois, {"fuel"})
    if m is None:
        return 90, "Küttev mets 1,5 km raadiuses kaardistamata (hinnang: kaitseruum olemas)"
    s = int(round(100.0 * m / (m + WILDFIRE_HALF_M)))
    if m < 30:
        return s, "Küttev mets %s (hinnang) — kontrolli kaitseruum kohapeal (rahvusvaheline rusikareegel ~30 m)" % _fmt_m(m)
    return s, "Metsatuleohu puhver %s (hinnang, tuleohutusproksi)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p46/p112/p117: documented no-map registry NULLs (OTA PR #131 precedent).
# Composite index, event archive + DEM, and DEM + projection curve are
# all absent from the snapshot; the scorer reports the gap with a
# concrete buyer check instead of a faked number.
# ---------------------------------------------------------------------------

def dim_envrisk(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p46: NULL — composite incident index needs a register/KOV table."""
    return None, "Keskkonnariskide koondindeks teadmata (intsidendiregister puudub; küsi KOV keskkonnainfot — hetktõmmis pole register)"


def dim_floodhist(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p112: NULL — flood history needs an event archive, elevation a DEM."""
    return None, "Üleujutusajalugu ja kõrgus teadmata (Keskkonnaagentuuri arhiiv + DEM mõõtmata; hetktõmmises vaid 8 flood_prone=lõiku)"


def dim_searise(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p117: NULL — sea level rise needs a DEM plus a projection curve."""
    return None, "Merepinna tõusu projektsioon teadmata (DEM + CMEMS/IPCC kõver mõõtmata; rannajoone kaugus pole projektsioon)"


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP08A_DIMS: Dict[str, Tuple[str, object]] = {
    "envrisk": ("Keskkonnariskid (kontroll)", dim_envrisk),
    "wildfire": ("Metsatuleohu puhver (proksi)", dim_wildfire),
    "floodhist": ("Üleujutusajalugu (kontroll)", dim_floodhist),
    "searise": ("Merepinna tõus (kontroll)", dim_searise),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP08A_PARAM_IDS = {
    "envrisk": 46,
    "wildfire": 69,
    "floodhist": 112,
    "searise": 117,
}


def score_group08a(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 8-batch-A dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP08A_DIMS.items():
        v, reason = fn(origin, pois)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
