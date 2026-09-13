"""Group 8 flood/climate per-listing dimensions, batch C (issue #169).

Params (this agent only — sibling batches own disjoint sets):
* p334 high-tide street impassability (surge-band street proximity hinnang)
* p336 avalanche/mudslide buffer (mapped-cliff distance hinnang)
* p371 burn scar mudslide risk (ALWAYS None — no burn scars, do not fake)
* p372 FEMA buyout history (ALWAYS None — no payout register, do not fake)

HONESTY (AGENTS.md section 7.2): the Keskkonnaagentuur flood-hazard
WFS, EFAS/CMEMS reanalyses, Ilmateenistus gauge series, EFFIS burn
perimeters and any flood-compensation/buyout register are NOT in the
2026-09-12 snapshot, so p371/p372 stay NULL with a buyer-check
reason, and p334/p336 are coarse OSM-derived PROXIES. Reasons say
"hinnang" (estimate) and name what is missing — never a flood map, a
passability forecast, a geotechnical ruling, or payout history.

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
drop way-mapped cliffs and the coastline, PR #118):
* slide predicate (natural=cliff, natural=earth_bank): 270 features
  (261 cliff LineStrings incl. named pangad — Leetse, Kakumae,
  Lasnamae/Maarjamae, Toompea — + 8 points + 1 multipolygon; 144
  touch the Tallinn window) — dense enough for a nearest-distance
  dim AND the map (apps/web/lib/layers_group08c.ts).
* surge gate input (natural=coastline): 105376 vertices; county
  carriageways (motorway..unclassified, 63610 ways) gated offline to
  the <=150 m band give named exposed streets (Pirita tee 130 band
  vertices, Reidi tee 82, Uus-Sadama 57, Regati pst 31, Merivälja
  tee 23 in the Tallinn-coast slice).
* flood_prone=yes: 12 features, ALL forest tracks/fords (zero
  streets) — considered and rejected for p334 (cannot answer street
  impassability); kinds_from_tags maps it to None on purpose.
* natural=burnt: 0 features; office=insurance x11 objects are sales
  points, not payout history — both map to None (p371/p372 stay NULL).

Judgment calls (reviewable per AGENTS.md section 7.5):
* p334 dim reuses the raster formula exactly
  (round(100*d/(d+150))) on the "shore" kind: the dim is
  CONSERVATIVE by construction — exposed streets sit inside the
  150 m band, so shore distance understates street clearance by at
  most one band width, flagging more risk, never less. The reason
  names the street check explicitly (the dim never issues a flood
  ruling: "kontrolli", never "üleujutatud"). Ungated highway=*
  maps to None: scoring every inland road as surge risk would invert
  the dim (inland would read bad).
* p336 reuses the raster formula exactly (round(100*d/(d+100))):
  the dim and the map can never disagree. Under 50 m the reason
  flags the ehitusgeoloogia check; the dim never issues a
  geotechnical ruling.
* p371/p372 return None for EVERY input including missing
  origin: inventing a gradient from zero signal would be fake
  precision (OTA PR #131 precedent). The reasons point at the
  forest-service / insurer-KOV check the buyer must do instead.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP08C_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP08C_POI_KIND, centroiding way
geometries to points (cliffs/shore are ways; raw way nodes would
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
# Radii are judgment calls: cliffs mid-sparse (2 km search), shore
# dense along the coast (1.5 km). Both node[...] and way[...] lines are
# required (nwr/ parity): cliffs/shore are ways; node-only drops them
# (PR #118). highway=* is NOT fetched: ungated roads would invert the
# dim inland (see module docstring); the surge gate is builder-side.
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP08C_OVERPASS_FRAGMENT = """
  node["natural"~"cliff|earth_bank"](around:2000,{lat},{lon});
  node["natural"~"coastline|water"](around:1500,{lat},{lon});
  way["natural"~"cliff|earth_bank"](around:2000,{lat},{lon});
  way["natural"~"coastline|water"](around:1500,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
#: "cliff" = mapped slope for the slide-buffer dim (never a slide
#: register); "shore" = mapped shoreline for the conservative
#: street-exposure dim (never a flood map).
GROUP08C_POI_KIND = [
    ("natural", {"cliff": "cliff", "earth_bank": "cliff",
                 "coastline": "shore", "water": "shore"}),
]


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 8-batch-C kind matching the OSM tags, else None. Pure.

    natural=cliff/earth_bank -> "cliff"; natural=coastline/water ->
    "shore". Everything else maps to None on purpose: highway=* (roads
    need the offline surge gate — ungated they would invert inland),
    flood_prone=yes (forest tracks, not streets), natural=burnt (no
    perimeters to map), office=insurance (sales points, not payout
    history), waterways/wetlands (p50 drainage's signal, #151).
    """
    tags = tags or {}
    if str(tags.get("natural", "")).split(";")[0] in ("cliff", "earth_bank"):
        return "cliff"
    if str(tags.get("natural", "")).split(";")[0] in ("coastline", "water"):
        return "shore"
    return None


# ---------------------------------------------------------------------------
# p334: surge-band street exposure (conservative shore-distance hinnang).
# ---------------------------------------------------------------------------

#: Raster half in metres (mirrors G08C_CAL.surgeroad in the TS + builder).
SURGEROAD_HALF_M = 150.0


def dim_surgeroad(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p334: street-exposure goodness 100*d/(d+150) from nearest shore."""
    if not origin or pois is None:
        return None, "Kõrgveeinfo puudub (rannajoone hetktõmmis)"
    m = _nearest_m(origin, pois, {"shore"})
    if m is None:
        return 95, "Rannik 1,5 km raadiuses kaardistamata (hinnang: lainetustsoonist väljas)"
    s = int(round(100.0 * m / (m + SURGEROAD_HALF_M)))
    if m < SURGEROAD_HALF_M:
        return s, "Rannik %s (hinnang) — kõrgvee korral kontrolli tänava läbitavust (see pole üleujutuskaart)" % _fmt_m(m)
    return s, "Rannik %s (hinnang, lainetustsoonist väljas)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p336: cliff/slope buffer distance (mapped-slope distance hinnang).
# ---------------------------------------------------------------------------

#: Raster half in metres (mirrors G08C_CAL.slidebuf in the TS + builder).
SLIDEBUF_HALF_M = 100.0


def dim_slidebuf(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p336: slope-buffer goodness 100*d/(d+100) from nearest cliff."""
    if not origin or pois is None:
        return None, "Järsakuinfo puudub (pankade hetktõmmis)"
    m = _nearest_m(origin, pois, {"cliff"})
    if m is None:
        return 90, "Järsakuid 1,5 km raadiuses kaardistamata (hinnang: varinguvööndist väljas)"
    s = int(round(100.0 * m / (m + SLIDEBUF_HALF_M)))
    if m < 50:
        return s, "Järsak %s (hinnang) — kontrolli ehitusgeoloogiat (see pole varingurisk)" % _fmt_m(m)
    return s, "Järsak %s (hinnang, varinguvööndist väljas)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p371/p372: documented no-map registry NULLs (OTA PR #131 precedent).
# Each is a per-register fact with no honest area signal; the scorer
# reports the gap with a concrete buyer check instead of a faked number.
# ---------------------------------------------------------------------------

def dim_burnscar(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p371: NULL — burn scars need fire perimeters (zero in snapshot)."""
    return None, "Põlengujärgne varingurisk teadmata (tulekahjuinfo: päästeamet/Keskkonnaagentuur — hetktõmmises pole põlengualasid)"


def dim_buyout(origin: Optional[Tuple[float, float]],
               pois: Optional[List[dict]]) -> Score:
    """p372: NULL — buyout/compensation history needs a payout register."""
    return None, "Üleujutushüvitiste ajalugu teadmata (kindlustus/KOV — hetktõmmises pole väljamaksete registrit; kindlustuskontor pole ajalugu)"


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP08C_DIMS: Dict[str, Tuple[str, object]] = {
    "surgeroad": ("Kõrgvee tänav (proksi)", dim_surgeroad),
    "slidebuf": ("Järsaku kaugus (proksi)", dim_slidebuf),
    "burnscar": ("Põlengujärgne varing (kontroll)", dim_burnscar),
    "buyout": ("Hüvitiste ajalugu (kontroll)", dim_buyout),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP08C_PARAM_IDS = {
    "surgeroad": 334,
    "slidebuf": 336,
    "burnscar": 371,
    "buyout": 372,
}


def score_group08c(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 8-batch-C dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP08C_DIMS.items():
        v, reason = fn(origin, pois)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
