"""Group 18 solar/shade/privacy OSM dimensions (issue #123).

Params (this agent only — sibling batches own disjoint sets; Group 18 is
parameters3.md section 5.18, re-derived here from OSM morphology because
the Group 18 primaries — Maa-amet LoD2 3D meshes, PVLib ray-tracing,
VIIRS night lights, lux meters, solar cadastre — are NOT in the
2026-09-12 snapshot):

* p253 micro-shade mapping (building/tree density shade PROXY)
* p443 winter sun angles (latitude-plus-south-obstruction PROXY)
* p64  solar energy potential (roof-openness/south-exposure PROXY)
* p480 exterior light trespass (streetlight-density PROXY, inverted)
* p40  privacy (building-proximity overlook PROXY, inverted)

HONESTY (AGENTS.md section 7.2): DSM height models, solar-cadastre
kWh, sun-hour ray-tracing and lux-meter readings are NOT in the
snapshot, so every scorer below is an honestly-labeled morphological
proxy — green/red means "open/obstructed surroundings (estimate)",
never measured shade, sun hours, kWh, or lux. Every reason says
"hinnang" (estimate); p253 says "mitte mõõdetud vari", p443 "mitte
mõõdetud päikesetunnid", p64 "mitte mõõdetud kWh", p480 "mitte
mõõdetud luksid", p40 "mitte mõõdetud vaateväljad". LAYER_META below
carries the same labels for the future web layer (title/legend/source
all say "(hinnang)").

Style mirrors services/scoring/dims_group18.py (issue #113): every
scorer is pure and offline-tested — (origin, pois) -> (Optional[int
0..100], Estonian reason). Network lives only in livability.fetch_pois;
this module adds no network calls, only the query fragment + tag
mapping the live path needs.

Helpers are local copies (not imported from livability): a future
central hook may import this module from livability.py, and importing
livability here would turn that into a cycle (same precedent as
PRs #100/#106/#113).

Tag verification (2026-09-12, done once by the author with osmium
against ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at
runtime; `nwr/` filters per PR #118, OPL primitive counts so
way-member nodes don't inflate the numbers):
* building: 252589 ways (+ 41 tagged nodes, 236 relations) — ways are
  the rule, nodes the exception; node-only extraction would drop ~all.
* building:levels: 14816 ways (tagged nodes negligible) — sparse
  (~6% of buildings), so untagged buildings read as low-rise.
* natural=tree: 43522 nodes, 0 ways — true points, no centroid issue.
* natural=wood: 4097 ways + 106 relations — way-centers are
  conservative (edge can be nearer than the center; documented below).
* highway=street_lamp: 29473 nodes — true points.
* lit=yes: 25991 ways; lit=no: 4941 ways (lit=no excluded by
  construction, same as PR #113).

Judgment calls (reviewable per AGENTS.md section 7.5):
* sol_tall = building:levels >= 4 (~12 m+, casts meaningful shade at
  Tallinn latitudes). Untagged buildings read as low-rise (sol_bld):
  levels coverage is sparse, so absence is weak evidence of lowness —
  p64/p443 fallbacks stay below 100 for this reason.
* One POI carries one kind: tall > any-building > tree/wood > lamp >
  lit corridor. A lit tall-building center reads as sol_tall, never as
  lighting (losing one lit point is negligible — lit ways are dense).
* Bearings use true bearing from the listing; p443 reads only the
  southern sector (135-225 deg): at Tallinn (59.4 N) December noon sun
  sits at ~7 deg altitude, so only southern masses block winter sun.
  Northern/eastern/western masses are ignored BY DESIGN, not by bug.
* Deciduous vs evergreen is UNMAPPABLE (no species/leaf_cycle split was
  verified), so p443 counts all southern trees as obstructions — a
  known conservative bias, stated in the reasoniq ("puud varjavad").
* p253 direction: shade availability reads UP (cool refuges nearby are
  a mild good), capped at 80 — shade is not an amenity.
* p480/p40 are INVERTED: lamps/neighbours nearby score DOWN.
* p40 bands start at 20 m because way-centers overstate setback for
  big footprints (center vs wall); documented, not tuned away.
* Residual twin risk (layers.md open issue): node+area twins ~20 m
  apart can double-count. p443/p64/p40 use nearest-only so twins are
  harmless there; p253/p480 use counts, so a twin can add +1 — bounded
  by the band caps, flagged for the planned OSM-id dedupe.

Delivery (stated per the task brief): scorer dims ONLY, no raster
masters. Why: (1) these are per-listing morphological proxies over
Overpass-center POIs — the same shape as PRs #100/#101/#106/#113 —
not network-kernel densities; stamping five county+metro Dijkstra
rasters would need a new bearing-sector builder for p443 anyway;
(2) five masters plus layers.ts/snapshot.ts hook edits would collide
with the open layer batches; (3) repo precedent is scorer-first with
one central integration later. LAYER_META below stages the honest web
labels for that follow-up.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP18_SOLAR_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP18_SOLAR_POI_KIND (routing building /
building:levels / lit keys through kinds_from_tags where the static
table cannot split — same precedent as PR #113), and rebalancing
livability.WEIGHTS must be one joint change across all parameter
batches — existing tests pin set(WEIGHTS) exactly, so per-batch
WEIGHTS edits would break every sibling. NOTE for that hook:
livability maps natural/wood -> "forest" in its static table, so the
hook must route natural=* through kinds_from_tags FIRST (wood ->
sol_wood must win over forest for these dims) or accept dual kinds.
"""

import math
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# Tallinn latitude: December solar-noon altitude ~= 90 - 59.4 - 23.44.
TALLINN_LAT = 59.4
#: Southern sector bearings (degrees, 180 = due south) that can block
#: low winter sun.
SOUTH_SECTOR = (135.0, 225.0)


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


def _bearing_deg(origin: Tuple[float, float], lat: float, lon: float) -> float:
    """Initial bearing from origin to point, degrees 0..360 (0 = north)."""
    la1, lo1, la2, lo2 = map(math.radians, (origin[0], origin[1], lat, lon))
    dlo = lo2 - lo1
    x = math.sin(dlo) * math.cos(la2)
    y = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(dlo)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def _band(value: Optional[float], bands: List[Tuple[float, int]]) -> Optional[int]:
    """First score whose threshold covers the value; None stays None."""
    if value is None:
        return None
    for limit, pts in bands:
        if value <= limit:
            return pts
    return bands[-1][1]


def _nearest_m(origin: Tuple[float, float], pois: List[dict], kinds: set,
               max_m: float = float("inf")) -> Optional[float]:
    best: Optional[float] = None
    for p in pois:
        if p.get("kind") in kinds and p.get("lat") is not None:
            d = _haversine_m(origin, p["lat"], p["lon"])
            if d <= max_m and (best is None or d < best):
                best = d
    return best


def _nearest_in_sector_m(origin: Tuple[float, float], pois: List[dict], kinds: set,
                         lo_deg: float, hi_deg: float,
                         max_m: float = float("inf")) -> Optional[float]:
    """Nearest POI distance whose bearing from origin falls in [lo, hi]."""
    best: Optional[float] = None
    for p in pois:
        if p.get("kind") in kinds and p.get("lat") is not None:
            b = _bearing_deg(origin, p["lat"], p["lon"])
            if lo_deg <= b <= hi_deg:
                d = _haversine_m(origin, p["lat"], p["lon"])
                if d <= max_m and (best is None or d < best):
                    best = d
    return best


def _count_within_m(
    origin: Tuple[float, float], pois: List[dict], kinds: set, radius_m: float
) -> int:
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
# Radii are judgment calls: buildings/lighting read at night-walk and
# overlook scale (500 m fetch, scored tighter), trees/lamps are
# hyper-local points (300 m). building:levels rides on the building
# fetch (same objects); ways MUST be fetched (252k ways vs 41 nodes —
# node-only would drop ~all buildings, PR #118 lesson). Way geometries
# arrive as centroids via `out center` (parse_overpass already handles
# el.center); the scorers below are center-based by construction.
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP18_SOLAR_OVERPASS_FRAGMENT = """
  node["building"](around:500,{lat},{lon});
  way["building"](around:500,{lat},{lon});
  node["natural"="tree"](around:300,{lat},{lon});
  node["natural"="wood"](around:500,{lat},{lon});
  way["natural"="wood"](around:500,{lat},{lon});
  node["highway"="street_lamp"](around:300,{lat},{lon});
  way["lit"~"yes|24/7|automatic|limited"](around:500,{lat},{lon});"""

#: Static (tagkey, {value: kind}) rows for livability._POI_KIND. Value-split
#: tags (building:levels tiers, lit variants, any building value) need
#: kinds_from_tags below — the static table alone cannot split them, so
#: the central hook must route building / building:levels / lit keys
#: through kinds_from_tags. CAUTION: livability already maps
#: natural/wood -> "forest"; the hook must route natural=* through
#: kinds_from_tags first so wood reads as sol_wood for these dims.
GROUP18_SOLAR_POI_KIND = [
    ("natural", {"tree": "sol_tree"}),
    ("highway", {"street_lamp": "sol_lamp"}),
]

#: building:levels at/above this reads as shade-casting mass (~12 m+).
TALL_LEVELS = 4
#: lit=* values meaning "this corridor is lit" (lit=no excluded).
LIT_VALUES = frozenset({"yes", "24/7", "automatic", "limited"})
#: Kinds that cast meaningful shade (tall masses, trees, woods).
SHADE_KINDS = frozenset({"sol_tall", "sol_tree", "sol_wood"})
#: Kinds that overlook (any neighbouring building mass).
OVERLOOK_KINDS = frozenset({"sol_tall", "sol_bld"})
#: Kinds that leak light at night (lamps + lit corridors).
LIGHT_KINDS = frozenset({"sol_lamp", "sol_lit"})


def _levels(value: object) -> Optional[int]:
    """Parse an OSM building:levels tag ('5', '3;4') to an int."""
    if not isinstance(value, str):
        return None
    try:
        v = int(float(value.split(";")[0].strip()))
    except ValueError:
        return None
    return v if v > 0 else None


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 18 solar kind matching the OSM tags, else None. Pure.

    Priority (documented judgment call): tall building > any building >
    tree/wood > street lamp > lit corridor, so one way-center feeds
    exactly one scorer and masses always read as mass, never as light.
    """
    if not isinstance(tags, dict):
        return None
    if "building" in tags and isinstance(tags["building"], str):
        if tags["building"].split(";")[0].strip() not in ("", "no"):
            lv = _levels(tags.get("building:levels"))
            return "sol_tall" if lv is not None and lv >= TALL_LEVELS else "sol_bld"
    nat = tags.get("natural", "")
    nat = nat.split(";")[0].strip() if isinstance(nat, str) else ""
    if nat == "tree":
        return "sol_tree"
    if nat == "wood":
        return "sol_wood"
    if tags.get("highway") == "street_lamp":
        return "sol_lamp"
    lit = tags.get("lit", "")
    lit = lit.split(";")[0].strip() if isinstance(lit, str) else ""
    if lit in LIT_VALUES and tags.get("highway"):
        return "sol_lit"
    return None


# ---------------------------------------------------------------------------
# p253: micro-shade mapping — building/tree density shade PROXY.
# Reads UP (shade availability nearby is a mild good), capped at 80.
# ---------------------------------------------------------------------------

def dim_shade(origin: Optional[Tuple[float, float]],
              pois: Optional[List[dict]]) -> Score:
    """p253: shade-casting mass/tree density within 150 m (estimate)."""
    if not origin or pois is None:
        return None, "Varjuinfo puudub"
    n = _count_within_m(origin, pois, SHADE_KINDS, 150)
    if n == 0:
        return 25, ("Varju napib: varju andvaid hooneid/puid 150 m "
                    "raadiuses pole (varjuhinnang, mitte mõõdetud vari)")
    s = _band(n, [(2, 55), (5, 70)])
    assert s is not None
    if n >= 6:
        s = 80  # abundant shade, still capped: shade is not an amenity
    return min(s, 80), ("Varju andvaid hooneid/puid 150 m raadiuses: %d "
                        "(varjuhinnang, mitte mõõdetud vari)" % n)


# ---------------------------------------------------------------------------
# p443: winter sun angles — latitude-plus-south-obstruction PROXY.
# Only the southern sector (135-225 deg) can block low winter sun at
# 59.4 N; other sectors are ignored BY DESIGN (see module docstring).
# ---------------------------------------------------------------------------

def dim_winter_sun(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p443: southern-arc openness estimate (winter-sun proxy)."""
    if not origin or pois is None:
        return None, "Talvepäikese info puudub"
    m = _nearest_in_sector_m(origin, pois, {"sol_tall", "sol_tree"},
                             SOUTH_SECTOR[0], SOUTH_SECTOR[1], 300)
    if m is None:
        return 85, ("Lõunakaar avatud 300 m ulatuses – talvepäike pääseb "
                    "peale (hinnang, mitte mõõdetud päikesetunnid)")
    s = _band(m, [(50, 30), (100, 45), (200, 60), (300, 75)])
    assert s is not None
    return s, ("Talvepäikese hinnang: lähim lõunakaare takistus %s "
               "(mitte mõõdetud päikesetunnid)" % _fmt_m(m))


# ---------------------------------------------------------------------------
# p64: solar energy potential — roof-openness/south-exposure PROXY.
# Open surroundings -> high. Never measured kWh.
# ---------------------------------------------------------------------------

def dim_solar(origin: Optional[Tuple[float, float]],
              pois: Optional[List[dict]]) -> Score:
    """p64: roof-shading openness estimate from tall masses nearby."""
    if not origin or pois is None:
        return None, "Päikesepotentsiaali info puudub"
    m = _nearest_m(origin, pois, {"sol_tall"}, 250)
    if m is None:
        near_low = _count_within_m(origin, pois, {"sol_bld"}, 30)
        if near_low >= 3:
            return 70, ("Katus eeldatavalt pigem avatud, kuid madalhoonestus "
                        "tihe (päikesehinnang, mitte mõõdetud kWh)")
        return 85, ("Ümbrus avatud: varjutavaid kõrghooneid 250 m raadiuses "
                    "pole (päikesehinnang, mitte mõõdetud kWh)")
    s = _band(m, [(50, 35), (100, 50), (150, 65), (250, 75)])
    assert s is not None
    return s, ("Päikesepotentsiaali hinnang: lähim varjutav kõrghoone %s "
               "(mitte mõõdetud kWh)" % _fmt_m(m))


# ---------------------------------------------------------------------------
# p480: exterior light trespass — streetlight-density PROXY.
# INVERTED: lamps nearby -> lower score. Never measured lux.
# ---------------------------------------------------------------------------

def dim_trespass(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p480: night-light trespass estimate from lamps/lit corridors."""
    if not origin or pois is None:
        return None, "Valgustrespassi info puudub"
    n = _count_within_m(origin, pois, {"sol_lamp"}, 100)
    lit_m = _nearest_m(origin, pois, {"sol_lit"}, 500)
    if n == 0 and lit_m is None:
        return 85, ("Tänavavalgustid kaardistamata 500 m raadiuses – öö "
                    "eeldatavalt pime (hinnang, mitte mõõdetud luksid)")
    s = _band(n, [(0, 75), (1, 70), (3, 55)])
    assert s is not None
    if n >= 4:
        s = 40
    if lit_m is not None and lit_m <= 100:
        s = min(s, 60)
    bits = "tänavalateraid 100 m raadiuses: %d" % n
    if lit_m is not None:
        bits += ", valgustatud tee %s" % _fmt_m(lit_m)
    return s, "Valgustrespassi hinnang (%s; mitte mõõdetud luksid)" % bits


# ---------------------------------------------------------------------------
# p40: privacy — building-proximity overlook PROXY.
# INVERTED: neighbours close -> lower score. Never measured viewsheds.
# ---------------------------------------------------------------------------

def dim_privacy(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p40: overlook exposure estimate from nearest building center."""
    if not origin or pois is None:
        return None, "Privaatsusinfo puudub"
    m = _nearest_m(origin, pois, OVERLOOK_KINDS, 500)
    if m is None:
        return 90, ("Kaardistatud hooneid 500 m raadiuses pole – privaatne "
                    "(hinnang, mitte mõõdetud vaateväljad)")
    s = _band(m, [(20, 30), (40, 45), (75, 60), (150, 75)])
    assert s is not None
    if m > 150:
        s = 85  # nearest neighbour beyond overlook range: quite private
    if m <= 150:
        tail = " (privaatsuse hinnang, mitte mõõdetud vaateväljad)"
    else:
        tail = " – üsna privaatne (hinnang, mitte mõõdetud vaateväljad)"
    return min(s, 85), "Lähim hoone %s%s" % (_fmt_m(m), tail)


#: Registry for the central weight-rebalance follow-up: (dims key, param id).
GROUP18_SOLAR_DIMS = (
    ("shade", "p253", dim_shade),
    ("winter_sun", "p443", dim_winter_sun),
    ("solar", "p64", dim_solar),
    ("trespass", "p480", dim_trespass),
    ("privacy", "p40", dim_privacy),
)


def score_group18_solar(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All five Group 18 solar dims for one listing (entry point for the
    weight-rebalance follow-up; keys match GROUP18_SOLAR_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP18_SOLAR_DIMS}


#: Honest Estonian web labels for the follow-up layers batch. Every title
#: says "(hinnang)" — never bare "shade", "solar", "lux", or "sun hours".
LAYER_META = {
    "shade": {
        "param": 253,
        "title": "Mikrovari (hinnang)",
        "good": "roheline = varju andvaid hooneid/puid lähedal (hinnang)",
        "bad": "punane = vari napib (hinnang, mitte mõõdetud vari)",
        "source": ("kohalik hetktõmmis 2026-09-12 "
                   "(hooned + puud; hinnang, mitte mõõdetud vari)"),
    },
    "winter_sun": {
        "param": 443,
        "title": "Talvepäike (hinnang)",
        "good": "roheline = lõunakaar avatud (hinnang)",
        "bad": "punane = lõunakaares takistused (hinnang, mitte mõõdetud päikesetunnid)",
        "source": ("kohalik hetktõmmis 2026-09-12 "
                   "(59,4° laius + lõunakaare takistused; hinnang)"),
    },
    "solar": {
        "param": 64,
        "title": "Päikesepotentsiaal (hinnang)",
        "good": "roheline = ümbrus avatud (hinnang)",
        "bad": "punane = kõrghooned varjutavad (hinnang, mitte mõõdetud kWh)",
        "source": ("kohalik hetktõmmis 2026-09-12 "
                   "(katuse avarus; hinnang, mitte mõõdetud kWh)"),
    },
    "trespass": {
        "param": 480,
        "title": "Valgustrespass (hinnang)",
        "good": "roheline = tänavavalgustid kaugel (hinnang)",
        "bad": "punane = laternad/valgustatud teed lähedal (hinnang, mitte mõõdetud luksid)",
        "source": ("kohalik hetktõmmis 2026-09-12 "
                   "(laternad + lit; hinnang, mitte mõõdetud luksid)"),
    },
    "privacy": {
        "param": 40,
        "title": "Privaatsus (hinnang)",
        "good": "roheline = naaberhooned kaugel (hinnang)",
        "bad": "punane = naaberhooned vahetus läheduses (hinnang, mitte mõõdetud vaateväljad)",
        "source": ("kohalik hetktõmmis 2026-09-12 "
                   "(hoonete lähedus; hinnang, mitte mõõdetud vaateväljad)"),
    },
}
