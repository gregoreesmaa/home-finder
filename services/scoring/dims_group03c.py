"""Group 3 cadastre per-listing dimensions, batch C (issue #153).

Params (this agent only — sibling batches own disjoint sets):
* p254 protected wetlands proximity (mapped wetland/reserve distance, metres)
* p256 natural springs and high water (mapped spring/well proximity)
* p258 soil pH and composition (ALWAYS None — no honest signal, do not fake)
* p273 unregistered easements (ALWAYS None — unmappable by definition)
* p277 riparian constraints (mapped flowing-water-or-shore proximity)

HONESTY (AGENTS.md section 7.2): the Maa-amet Geoportaal WFS grids
(cadastre, KKIS easements, soil DB) and the EELIS protection register
are NOT in the 2026-09-12 snapshot, so p258/p273 stay NULL with a
buyer-check reason, and p254/p256/p277 are coarse OSM-derived PROXIES.
Reasons say "hinnang" (estimate) and name what is missing — never
measured distances to protected sites, water tables, soil pH values,
cleared titles, or resolved riparian rights.

Style mirrors sibling batch dims_group03b.py (#152): every scorer is
pure and offline-tested — (origin, pois) -> (Optional[int 0..100],
Estonian reason). Network lives only in livability.fetch_pois; this
module adds no network calls, only the query fragment + tag mapping
the live path needs.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Tag verification (2026-09-12, done once by the author with osmium
tags-filter nwr/ + export against
~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at runtime;
node-only would silently drop way-mapped wetlands/reserves, PR #118):
* natural=spring: 43 tagged features (35 Points + 4 LineStrings + 4
  MultiPolygons) county-wide — far too sparse for a Tallinn gradient
  (flat red, not info; same verdict as p183, #152).
* man_made=water_well: 30 tagged features (28 Points + twins).
* natural=wetland: 1264 tagged features (667 MultiPolygons + 637
  LineStrings + 2 Points) — dense, but already feeding TWO shipped
  gradients (p50 drainage #151, wildcorr #143); a third re-skin with a
  "protected" claim the snapshot cannot resolve would mislead.
* leisure=nature_reserve: 137 tagged features (32 MultiPolygons);
  boundary=protected_area: 167 tagged features (51 MultiPolygons).
  Reserves exist, but per-wetland protection status is an EELIS
  register fact, not an OSM attribute.
* derived-soil.geojson: 53 features, keys barrier/gate/landuse junk,
  ZERO soil attributes — p258 has nothing to calibrate against
  (same verdict as p68 #151 / p251 #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* p254 scores the NEAREST mapped wetland OR reserve and reports the
  raw metres (the param's own REAL unit): near = restriction check
  likely = LOW-MID (never a veto — valence is two-sided: building
  restriction vs nature amenity). Absence within 3 km is a WEAK good
  sign only (cap 75, reason says "nõrk hea-märk"): unmapped is not
  unprotected (EELIS gap).
* p256 scores the nearest spring/well ONLY (kinds {"shallowsrc"}):
  near = high-water hint = LOW (foundation/basement risk). Disjoint
  from p183 (#152) on purpose: p183 also counts wetlands, p256 does
  not (documented in the p256 reason). Absence cap 70 — strictly
  weaker than p183's 75 because wetlands are excluded.
* p277 scores the nearest FLOWING water OR SEA SHORE (kinds
  {"flowwater", "shore"}): near = constraint check likely = MID
  (flags the KOV/kinnistusraamat check without resolving it). Disjoint
  from p228 (#152, flowwater only): the Water Act ehituskeelu- and
  kaitsevöönd also bind the sea shore, so the shore is in here and
  out there. Ponds/lakes stay p338 weedwater's amenity kind. Far is
  neutral (85 cap): no frontage also means no riparian benefit.
* p258/p273 return None for EVERY input including missing origin:
  inventing a gradient from zero signal would be fake precision
  (OTA PR #131 precedent). p273 is stronger than p71 (#151): an
  UNREGISTERED easement is invisible by definition — not even KKIS
  can show it. The reasons point at the check the buyer must do
  (soil survey / seller disclosure + title audit).

Kind-string reuse (for the future integrator): "wetland",
"shallowsrc" and "flowwater" are spelled EXACTLY as in
dims_group03b.py GROUP03B_POI_KIND (identical tag meanings — the
integrator dedups the rows, it must not double-count). "reserve"
(boundary/leisure protected areas) and "shore" (sea coastline) are
NEW kinds owned by this batch.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP03C_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP03C_POI_KIND, centroiding way
geometries to points (wetlands/reserves/waterways are ways/relations;
raw way nodes would multi-count — residual twin risk per PR #118 must
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
# Radii are judgment calls: wetland/reserve + spring/well sparse-to-mid
# (3 km search), flowing-water/shore mid-density (2 km). Both node[...]
# and way[...] lines are required (nwr/ parity): springs/wells are
# points but wetlands/reserves/waterways are ways/relations; node-only
# drops them (PR #118).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP03C_OVERPASS_FRAGMENT = """
  node["natural"="wetland"](around:3000,{lat},{lon});
  node["natural"="spring"](around:3000,{lat},{lon});
  node["man_made"="water_well"](around:3000,{lat},{lon});
  node["leisure"="nature_reserve"](around:3000,{lat},{lon});
  node["boundary"="protected_area"](around:3000,{lat},{lon});
  node["natural"="coastline"](around:2000,{lat},{lon});
  node["waterway"~"river|stream|canal|ditch|drain"](around:2000,{lat},{lon});
  way["natural"="wetland"](around:3000,{lat},{lon});
  way["leisure"="nature_reserve"](around:3000,{lat},{lon});
  way["boundary"="protected_area"](around:3000,{lat},{lon});
  way["natural"="coastline"](around:2000,{lat},{lon});
  way["waterway"~"river|stream|canal|ditch|drain"](around:2000,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
#: "wetland"/"shallowsrc"/"flowwater" intentionally reuse the #152
#: kind strings (identical meanings — dedup on integration, do not
#: double-count); "reserve" and "shore" are new kinds owned here.
GROUP03C_POI_KIND = [
    ("natural", {"wetland": "wetland", "spring": "shallowsrc",
                 "coastline": "shore"}),
    ("man_made", {"water_well": "shallowsrc"}),
    ("leisure", {"nature_reserve": "reserve"}),
    ("boundary", {"protected_area": "reserve",
                  "nature_reserve": "reserve"}),
    ("waterway", {"river": "flowwater", "stream": "flowwater",
                  "canal": "flowwater", "ditch": "flowwater",
                  "drain": "flowwater"}),
]


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 3-batch-C kind matching the OSM tags, else None. Pure.

    Flowing water wins over the shore/wetland framings (a riverbank is
    a riparian question first); springs/wells map to "shallowsrc" exactly
    as in #152 (shared kind, shared meaning). natural=water (ponds/
    lakes) is None — p338 weedwater owns that amenity kind.
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
    if nat == "coastline":
        return "shore"
    if str(tags.get("leisure", "")).split(";")[0] == "nature_reserve":
        return "reserve"
    bd = str(tags.get("boundary", "")).split(";")[0]
    if bd in ("protected_area", "nature_reserve"):
        return "reserve"
    return None


# ---------------------------------------------------------------------------
# p254: protected wetlands proximity (mapped wetland/reserve distance).
# ---------------------------------------------------------------------------

#: Wetland/reserve search radius in metres (mid-density tier).
WETLAND_RADIUS_M = 3000.0


def dim_wetland_proximity(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p254: nearest mapped wetland or reserve, raw metres + constraint hint."""
    if not origin or pois is None:
        return None, "Märgala info puudub"
    m = _nearest_m(origin, pois, {"wetland", "reserve"})
    if m is None or m > WETLAND_RADIUS_M:
        return 75, ("Kaardistatud märgala/kaitseala 3 km raadiuses pole "
                    "(nõrk hea-märk, mitte kaitseotsus; EELIS registrit "
                    "snapshots pole — hinnang eeldab kaardistatut)")
    s = _band(m, [(150, 45), (500, 60), (1500, 72)])
    return s, ("Lähim kaardistatud märgala/kaitseala %s "
               "(kaitsepiirangu kontrollivajadus, hinnang — parameeter "
               "meetrites, mitte kaitseotsus)") % _fmt_m(m)


# ---------------------------------------------------------------------------
# p256: natural springs and high water (mapped spring/well proxy).
# ---------------------------------------------------------------------------

#: Spring/well search radius in metres (sparse tier).
SPRINGS_RADIUS_M = 3000.0


def dim_springs(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p256: nearest mapped spring or well (kõrge veetaseme tunnus)."""
    if not origin or pois is None:
        return None, "Allika info puudub"
    m = _nearest_m(origin, pois, {"shallowsrc"})
    if m is None or m > SPRINGS_RADIUS_M:
        return 70, ("Kaardistatud allikat/kaevu 3 km raadiuses pole "
                    "(nõrk hea-märk — märgalad arvestamata, need loeb "
                    "p183; Maa-ameti hüdrogeoloogia registrit snapshots "
                    "pole)")
    s = _band(m, [(200, 35), (600, 55), (1500, 70)])
    return s, ("Lähim kaardistatud allikas/kaev %s "
               "(kõrge veetaseme hinnang, mitte puurkaevu mõõtmine)") % _fmt_m(m)


# ---------------------------------------------------------------------------
# p258: soil pH and composition (no honest signal — always None).
# ---------------------------------------------------------------------------

def dim_soil_ph(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p258: NULL — soil DB is not in the snapshot (do not fake)."""
    return None, ("Mulla pH/lõimise andmebaasi (ESDAC/SoilGrids) snapshots pole — "
                  "vajab KOV-tabeli / pinnaseuuringu kontrolli (EI OLE "
                  "hinnangut, ära feigi)")


# ---------------------------------------------------------------------------
# p273: unregistered easements (unmappable by definition — always None).
# ---------------------------------------------------------------------------

def dim_unregistered_easements(origin: Optional[Tuple[float, float]],
                               pois: Optional[List[dict]]) -> Score:
    """p273: NULL — unregistered burdens are invisible to every register."""
    return None, ("Registreerimata servituuti ei näita ükski register (EI OLE "
                  "hinnangut) — vajab müüja kirjalikku avaldust ja "
                  "ostueelset õigusauditit (kinnistusraamat/KKIS katab vaid "
                  "registreeritu)")


# ---------------------------------------------------------------------------
# p277: riparian constraints (mapped flowing-water-or-shore proxy).
# ---------------------------------------------------------------------------

#: Flowing-water/shore search radius in metres (mid-density tier).
RIPARIAN_RADIUS_M = 2000.0


def dim_riparian_constraints(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """p277: nearest mapped flowing water or sea shore (piirangu-kontroll)."""
    if not origin or pois is None:
        return None, "Kaldapiirangu info puudub"
    m = _nearest_m(origin, pois, {"flowwater", "shore"})
    if m is None or m > RIPARIAN_RADIUS_M:
        return 85, ("Kaardistatud vooluvett/mereranda 2 km raadiuses pole "
                    "(ehituskeelu/kaitsevööndi küsimust vee põhjal pole; "
                    "kinnistusraamatu/KOV kontrolli hinnang ei asenda)")
    s = _band(m, [(100, 55), (300, 70), (1000, 80)])
    return s, ("Lähim kaardistatud vooluvesi/mererand %s — võimalik "
               "ehituskeelu-/kaitsevööndi/kallasraja kontroll (hinnang, "
               "mitte piirangute lahendamine)") % _fmt_m(m)


GROUP03C_DIMS = (
    ("wetland_proximity", "p254", dim_wetland_proximity),
    ("springs", "p256", dim_springs),
    ("soil_ph", "p258", dim_soil_ph),
    ("unregistered_easements", "p273", dim_unregistered_easements),
    ("riparian_constraints", "p277", dim_riparian_constraints),
)


def score_group03c(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All five Group 3 batch-C dims for one listing (entry point for the
    weight-rebalance follow-up; keys match GROUP03C_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP03C_DIMS}
