"""Group 6 heritage/conservation per-listing dimensions, batch G06 (issue #138).

Params (this agent only — sibling batches own disjoint sets):
* p72  historic district guidelines (mapped-heritage density proxy)
* p158 historical tax credits (EUR fiscal instrument — documented no-map)
* p272 facade easements (parcel-legal fact — documented no-map)
* p320 historic commission friction (inverse-density process heuristic)
* p351 lead glass window preservation (component level — documented no-map)

HONESTY (AGENTS.md section 7.2): the Muinsuskaitseamet heritage registry
(register.muinsuskaitseamet.ee) and the Maa-amet mka:ehitis /
mka:kaitsevoond WFS layers are NOT in the 2026-09-12 snapshot, so every
scorer below is an honestly-labeled OSM-derived PROXY or an explicit
None stub. Reasons must say "kaardistatud" (mapped) and "hinnang"
(estimate), never claim a conservation-zone decision, a EUR tax figure,
a registered easement, or a window survey.

Style mirrors services/scoring/livability.py and sibling batch
dims_group10c.py (#121): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network lives
only in livability.fetch_pois; this module adds no network calls, only
the query fragment + tag mapping the live path needs.

Helpers are local copies (not imported from livability or the sibling
batches): a future central hook may import this module alongside them,
and importing any of them here would turn that into a cycle (same
precedent as batch B3, PR #100, and siblings #105/#107/#121).

Tag verification (2026-09-12, done once by the author with osmium
tags-filter against ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf,
NOT at runtime; extraction used nwr/ filters throughout — node-only
would silently drop way-mapped manors/castles, PR #118):
* nwr/heritage + nwr/historic + nwr/unesco: 1003 features; top values
  memorial 274, ruins 170, manor 147, yes 133, archaeological_site 40,
  wreck 36 (sea cells), fort 21, building 21. heritage=1/yes nearly
  absent (4) — the registry is NOT in OSM, hence hinnang everywhere.

Judgment calls (reviewable per AGENTS.md section 7.5):
* p72 counts mapped heritage objects within 800 m (the map layer's
  walk-kernel sigma). Bands are modest: a single mapped object scores
  45, never green — one manor is not a district (mirrors the map half).
  Zero mapped objects = 20, not 0: absence from OSM is weak evidence
  of absence on the ground (rural mapping is thin).
* p320 is the deliberate INVERSE of p72: renovation inside a heritage
  cluster needs Muinsuskaitseamet/KOV milieu-area coordination, so
  friction grows with mapped density. Bands stay soft (25..90, never
  0/100): proximity predicts review likelihood, never a named
  commission decision. A buyer who values character reads p72 green;
  a buyer who fears renovation hassle reads p320 — both from the same
  honest source, opposite directions, documented here.
* p158/p272/p351 are constant-None stubs WITH registry entries (not
  omitted): omitting them would let a downstream scorer silently treat
  them as 0/neutral. p158 keeps the parameters3.md "Abort deal score
  if missing" semantics — the None plus the reason forces the abort.
  A tax-credit EUR figure, an easement fact, or a window survey
  guessed from heritage proximity would be fake precision; the stub
  says which register to query instead.
* "heritage" kind is disjoint from all sibling batches (grep 2026-09-12:
  no sibling _POI_KIND row or kinds_from_tags claims historic/heritage/
  unesco): dims_group09b mentions heritage windmills only to EXCLUDE
  them from vibration scoring.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP06_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP06_POI_KIND (via kinds_from_tags below),
centroiding way geometries to points (manors/castles are usually
area-mapped; raw way nodes would multi-count — residual twin risk per
PR #118 must be noted by the hook author), and rebalancing
livability.WEIGHTS must be one joint change across all parameter
batches — existing tests pin set(WEIGHTS) exactly, so per-batch WEIGHTS
edits would break every sibling.
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


def _count_within_m(origin: Tuple[float, float], pois: List[dict],
                    kinds: set, radius_m: float) -> int:
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
# The fragment queries at 2 km (sparse tier — heritage objects are
# sparser than shops but denser than broadcast masts); the scorers count
# within HERITAGE_RADIUS_M 800 m (the map layer's walk-kernel sigma, so
# the per-listing dims agree with the map about what "nearby" means).
# Both node[...] and way[...] lines are required (nwr/ parity):
# manors/castles/forts are usually area-mapped; node-only drops them.
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP06_OVERPASS_FRAGMENT = """
  node["historic"](around:2000,{lat},{lon});
  node["heritage"](around:2000,{lat},{lon});
  node["unesco"](around:2000,{lat},{lon});
  way["historic"](around:2000,{lat},{lon});
  way["heritage"](around:2000,{lat},{lon});
  way["unesco"](around:2000,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND. Any
#: non-empty historic/heritage/unesco value maps to "heritage" (checked
#: via kinds_from_tags — a static value table cannot express "any
#: value", so the central hook must route these three keys through
#: kinds_from_tags).
GROUP06_POI_KIND = [
    ("historic", {}),
    ("heritage", {}),
    ("unesco", {}),
]


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 6 kind matching the OSM tags, else None. Pure.

    Any non-empty historic/heritage/unesco value maps to "heritage"
    (the fallback heuristic of parameters3.md section 5.6 — mapped
    objects, never registry facts). Wrecks/ships keep the kind: they
    are mapped heritage, and scorers count them only when near a
    listing (sea cells rarely are). Empty-string values map to None.
    """
    tags = tags or {}
    for key in ("historic", "heritage", "unesco"):
        if str(tags.get(key, "")).split(";")[0].strip():
            return "heritage"
    return None


# ---------------------------------------------------------------------------
# p72: historic district guidelines (mapped-heritage density proxy).
# ---------------------------------------------------------------------------

#: Heritage-density count radius in metres (map sigma parity).
HERITAGE_RADIUS_M = 800.0


def dim_heritage_district(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p72: mapped heritage objects within 800 m (muinsusala-hinnang)."""
    if not origin or pois is None:
        return None, "Muinsusala info puudub"
    n = _count_within_m(origin, pois, {"heritage"}, HERITAGE_RADIUS_M)
    if n == 0:
        return 20, ("Kaardistatud muinsusobjekte 800 m raadiuses pole "
                    "(muinsusala-hinnang, mitte registriotsus; "
                    "Muinsuskaitseameti registrit snapshots pole)")
    s = _band(n, [(1, 45), (3, 65), (6, 85), (float("inf"), 100)])
    return s, ("Kaardistatud muinsusobjekte 800 m raadiuses: %d "
               "(muinsusala-hinnang, mitte kaitsevööndiotsus)") % n


# ---------------------------------------------------------------------------
# p158: historical tax credits (EUR) — documented no-map (None stub).
# ---------------------------------------------------------------------------

def dim_tax_credits(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p158: ALWAYS None — the EUR tax-credit register is not mapped.

    A euro figure guessed from heritage proximity would be fake
    precision with deal-killing consequences; per parameters3.md the
    missing value must abort the deal score, and only an explicit None
    forces that path.
    """
    return None, ("Ajalooliste hoonete maksusoodustuse (EUR) registrit "
                  "snapshots pole — hinnangut ei saa anda, vajab "
                  "Muinsuskaitseameti registri päringut (tehingu skoor "
                  "katkestatakse)")


# ---------------------------------------------------------------------------
# p272: facade easements — documented no-map (None stub).
# ---------------------------------------------------------------------------

def dim_facade_easements(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p272: ALWAYS None — easements are parcel-legal facts, unmapped."""
    return None, ("Fassaadi servituutide registrit snapshots pole — "
                  "hinnangut ei saa anda, vajab katastriseaduslikku "
                  "päringut (lähedased muinsusobjektid ei tõesta "
                  "servituuti)")


# ---------------------------------------------------------------------------
# p320: historic commission friction (inverse-density heuristic).
# ---------------------------------------------------------------------------

def dim_commission(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p320: renovation-friction heuristic — HIGHER score = LESS friction.

    Deliberate inverse of p72 from the same honest source: dense mapped
    heritage predicts Muinsuskaitseamet/KOV coordination need. Bands are
    soft (25..90): proximity predicts review likelihood, never a named
    commission decision.
    """
    if not origin or pois is None:
        return None, "Komisjoni menetluse info puudub"
    n = _count_within_m(origin, pois, {"heritage"}, HERITAGE_RADIUS_M)
    if n == 0:
        return 90, ("Läheduses kaardistatud muinsusobjekte pole — "
                    "komisjoni kooskõlastuse tõenäosus väike (hinnang, "
                    "mitte menetlusotsus)")
    s = _band(n, [(1, 70), (3, 55), (6, 40), (float("inf"), 25)])
    return s, ("Kaardistatud muinsusobjekte 800 m raadiuses: %d — "
               "renoveerimisel tõenäoline kooskõlastusvajadus "
               "(hinnang, mitte menetlusotsus)") % n


# ---------------------------------------------------------------------------
# p351: lead glass window preservation — documented no-map (None stub).
# ---------------------------------------------------------------------------

def dim_leadglass(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p351: ALWAYS None — window preservation is component-level, unmapped."""
    return None, ("Akende säilivuse registrit snapshots pole — hinnangut "
                  "ei saa anda (OSM-is aknaregister puudub; lähedased "
                  "muinsusobjektid ei tõesta akende olukorda)")


#: Registry for the central weight-rebalance follow-up: (dims key, param id, fn).
GROUP06_DIMS = (
    ("heritage_district", "p72", dim_heritage_district),
    ("tax_credits", "p158", dim_tax_credits),
    ("facade_easements", "p272", dim_facade_easements),
    ("commission", "p320", dim_commission),
    ("leadglass", "p351", dim_leadglass),
)


def score_group06(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All five Group 6 batch-G06 dims for one listing (entry point for the
    weight-rebalance follow-up; keys match GROUP06_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP06_DIMS}
