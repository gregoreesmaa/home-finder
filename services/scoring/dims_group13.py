"""Group 13 drone-logistics dimensions (issue #126): p220/p270 scorers.

Params (this agent only — sibling batches own disjoint sets; Group 13 is
parameters3.md section 5.13, Omniva/locker feeds + Wolt/Bolt polygons with
an EANS DroneMap + Maa-amet yard-clearance fallback):
* p220 drone delivery clearance (airspace-restriction PROXY)
* p270 drone delivery viability (clearance + landing-space PROXY)

HONESTY (AGENTS.md section 7.2): the EANS (Lennuliiklusteeninduse AS) UTM
DroneMap WFS and the Maa-amet Maakataster yard clearances are NOT in the
2026-09-12 snapshot (MANIFEST gaps list registries as "not yet pulled"),
so NEITHER param measures real drone permission or landing suitability.
Both are honestly-labeled OSM proximity proxies and every reason says
"hinnang" (estimate) plus "mitte EANS DroneMap" (not the EANS DroneMap):
* p220 = INVERTED distance to the nearest aeroway=aerodrome/helipad site
  (closer site -> more likely controlled airspace -> lower score).
* p270 = min(clearance leg, yard leg): the same airspace distance with
  gentler bands, combined with the distance to the nearest open landing
  proxy (livability "park" kind: leisure park/garden/playground,
  landuse grass/meadow). A drone needs BOTH clear airspace AND somewhere
  to land, so min() is the honest combiner (binding constraint, not an
  average that hides the blocker). Documented judgment call.

p220 bands (nearest aerodrome|helipad, metres): <=500: 20, <=1000: 40,
<=2000: 60, <=4000: 75, <=8000: 90, else 90. No site mapped at all -> 90
(aeroway mapping is sparse outside cities, so absence is weak evidence —
same precedent as p82's no-arterial 90 in PR #115, documented here).
p270 clearance leg (gentler): <=500: 30, <=1000: 55, <=2000: 75,
<=4000: 90, else 95 (no site -> 90, same sparse-mapping discount).
p270 yard leg (nearest "park"): <=100: 100, <=300: 80, <=500: 60,
<=1000: 40, else 25 (no park kind in range -> 25: dense blocks genuinely
lack landing space; livability already fetches these tags live).

Style mirrors services/scoring/livability.py: pure scorers,
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network lives
only in livability.fetch_pois; this module adds no network calls, only
the query fragment + tag mapping the live path needs.

Helpers are local copies (not imported from livability): a future central
hook may import this module from livability.py, and importing livability
here would turn that into a cycle (same precedent as PRs #100/#106/#115).

Tag verification (2026-09-12, done once by the author with osmium against
~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at runtime):
* aeroway=aerodrome: 7 nodes + 3 ways (named: Tallinna lennujaam, Ämari,
  Haapsalu, Paslepa, Lyckholm, Humala, Aespa, Rapla, Kose, Jägala).
* aeroway=helipad: 26 nodes + 7 ways (incl. a ~20-pad cluster at Ämari
  24.216-24.220/59.264 and hospital/city pads e.g. 24.7369/59.4311).
* Node-only (n/) extraction would drop the 3 aerodrome + 7 helipad ways —
  including the Tallinna lennujaam polygon — so extraction MUST use nwr/
  filters (PR #118 rule).

Way geometries need centroid handling (extraction side, staged here as
documented convention): polygon bbox-center / LineString midpoint, the
same three cases as batch_b4_common.feature_point. Note the residual twin
risk (PR #118): Tallinna lennujaam exports as BOTH a LineString (centroid
24.803/59.418) and a MultiPolygon (24.841/59.414, ~2.1 km apart), Ämari
and Haapsalu likewise, and filter output also carries untagged member
nodes of matched ways. Both scorers below are nearest-only, hence
twin-immune (duplicates cannot move a minimum); a future count/kernel
builder MUST dedupe first (~20-50 m cell, PR #118 dedupe_points
precedent) or the Ämari pad cluster / dual airport geometries spike it.

Delivery (stated per the task brief): scorer dims ONLY, no raster masters.
Why: (1) airspace sites are sparse polygons/points, not the dense
point-kernel shape the walk-raster pipeline stamps — county rasters would
be near-empty with single-cell spikes at centroids; (2) raster masters
plus hook edits to layers.ts/snapshot.ts would collide with open sibling
PRs; (3) the repo precedent (PRs #101/#106/#115) is scorer-first with one
central integration later. LAYER_META below stages the honest web labels.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP13_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP13_POI_KIND, and rebalancing
livability.WEIGHTS must be one joint change across all parameter batches —
existing tests pin set(WEIGHTS) exactly, so per-batch WEIGHTS edits would
break every sibling. The p270 "park" leg reuses livability's existing
park kind (leisure park/garden/playground + landuse grass/meadow), so no
new fetch is needed for it — same precedent as p88 reusing bus_stop in
PR #101 and p441 reusing school in PR #115.
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


#: POI kinds that proxy controlled airspace (verified in snapshot).
AERO_KINDS = {"aerodrome", "helipad"}

#: p220 bands: nearest airspace site (INVERTED — closer reads lower).
CLEARANCE_BANDS = [(500, 20), (1000, 40), (2000, 60), (4000, 75), (8000, 90),
                   (float("inf"), 90)]
#: Sparse-mapping fallback (no aeroway site mapped): weak evidence, not clear.
CLEARANCE_FALLBACK = 90
#: p270 clearance leg (gentler than p220 — viability is not permission).
VIABILITY_CLEAR_BANDS = [(500, 30), (1000, 55), (2000, 75), (4000, 90),
                         (float("inf"), 95)]
#: p270 yard leg: nearest open landing proxy ("park" kind).
YARD_BANDS = [(100, 100), (300, 80), (500, 60), (1000, 40),
              (float("inf"), 25)]


# ---------------------------------------------------------------------------
# Live-path wiring: Overpass fragment + tag mapping.
# Radius is a judgment call: drone restrictions bite within single-digit km
# of a site, and 15 km keeps the live query bounded while covering CTR
# fringe. The p270 "park" leg reuses livability's existing kinds/query.
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP13_OVERPASS_FRAGMENT = """
  node["aeroway"~"aerodrome|helipad"](around:15000,{lat},{lon});
  way["aeroway"~"aerodrome|helipad"](around:15000,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
GROUP13_POI_KIND = [
    ("aeroway", {"aerodrome": "aerodrome", "helipad": "helipad"}),
]


def kinds_from_tags(tags: dict) -> Optional[str]:
    """Group 13 kind for OSM tags (airspace sites only), else None. Pure."""
    if not isinstance(tags, dict):
        return None
    aero = tags.get("aeroway", "")
    aero = aero.split(";")[0].strip() if isinstance(aero, str) else ""
    if aero == "aerodrome":
        return "aerodrome"
    if aero == "helipad":
        return "helipad"
    return None


# ---------------------------------------------------------------------------
# p220: drone delivery clearance — airspace-restriction PROXY (inverted).
# ---------------------------------------------------------------------------

def dim_drone_clearance(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p220: likely-clear airspace (high) vs airfield proximity (low).

    Honest proxy only: closer to a mapped aerodrome/helipad reads as more
    likely controlled airspace. Never a permission statement.
    """
    if not origin or pois is None:
        return None, "Drooni õhuruumi info puudub"
    m = _nearest_m(origin, pois, AERO_KINDS)
    if m is None:
        return CLEARANCE_FALLBACK, ("Kaardistatud lennuvälja/helikopteriväljakut "
                                    "lähedal pole (õhuruumi hinnang, mitte EANS DroneMap)")
    s = _band(m, CLEARANCE_BANDS)
    assert s is not None
    return s, ("Droonilennu hinnang (mitte EANS DroneMap): lähim lennuväli/helikopteriväljak %s"
               % _fmt_m(m))


# ---------------------------------------------------------------------------
# p270: drone delivery viability — min(clearance, landing-space) PROXY.
# ---------------------------------------------------------------------------

def dim_drone_viability(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p270: viable (high) only when airspace is likely clear AND open
    landing space is near. min() combiner: the blocker binds, never hides
    behind an average. Both legs are honestly-labeled proxies."""
    if not origin or pois is None:
        return None, "Droonitarne info puudub"
    m_aero = _nearest_m(origin, pois, AERO_KINDS)
    if m_aero is None:
        clear = CLEARANCE_FALLBACK
        aero_txt = "lennuvälja kaardistamata"
    else:
        clear = _band(m_aero, VIABILITY_CLEAR_BANDS)
        assert clear is not None
        aero_txt = "lennuväli %s" % _fmt_m(m_aero)
    m_yard = _nearest_m(origin, pois, {"park"})
    if m_yard is None:
        yard = 25
        yard_txt = "avatud maandumisala kaardistamata"
    else:
        yard = _band(m_yard, YARD_BANDS)
        assert yard is not None
        yard_txt = "avatud ala %s" % _fmt_m(m_yard)
    s = min(clear, yard)
    return s, ("Droonitarne hinnang (mitte EANS DroneMap): õhuruum %s, %s → %d"
               % (aero_txt, yard_txt, s))


#: Registry for the central weight-rebalance follow-up: (dims key, param id).
GROUP13_DIMS = (
    ("drone_clearance", "p220", dim_drone_clearance),
    ("drone_viability", "p270", dim_drone_viability),
)


def score_group13(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All Group 13 drone dims for one listing (entry point for the follow-up)."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP13_DIMS}


#: Honest Estonian web labels for the follow-up layers batch. Both titles
#: say "(hinnang)" and both sources disclaim the EANS DroneMap — these must
#: never render as permission statements.
LAYER_META = {
    "drone_clearance": {
        "param": 220,
        "title": "Droonilend (lennuvälja läheduse hinnang)",
        "good": "roheline = lennuväljad kaugel (hinnang)",
        "bad": "punane = lennuväli/helikopteriväljak lähedal (hinnang, mitte keeld)",
        "source": ("kohalik hetktõmmis 2026-09-12 "
                   "(aeroway; hinnang, mitte EANS DroneMap)"),
    },
    "drone_viability": {
        "param": 270,
        "title": "Droonitarne (hinnang)",
        "good": "roheline = õhuruum vaba ja avatud ala lähedal (hinnang)",
        "bad": "punane = lennuväli lähedal või maandumisala kaugel (hinnang)",
        "source": ("kohalik hetktõmmis 2026-09-12 "
                   "(aeroway + haljasala; hinnang, mitte EANS DroneMap)"),
    },
}
