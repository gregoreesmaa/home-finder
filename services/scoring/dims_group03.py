"""Group 3 cadastre-A dimensions: batch G03 (issue #151).

Params (this agent only — sibling batches own disjoint sets):
* p29  lot size (krundi suurus: listing's own lot area vs Tallinn band)
* p50  topography and drainage (drenaažiproksi: open-water proximity)
* p68  soil stability (documented no-map: NULL + buyer check)
* p71  easements and rights-of-way (documented no-map: NULL + check)
* p75  property line clarity (documented no-map: NULL + check)

HONESTY (load-bearing, AGENTS.md §7.2): the Maa-amet cadastre WFS
(parcels, KKIS easements), LiDAR DEM and soil DB are NOT in the
2026-09-12 snapshot, so only p50 gets a spatial proxy — distance to
mapped open water (sea shore, lakes, rivers, wetlands), honestly
labelled "drenaažiproksi (hinnang)". p29 scores the listing's OWN lot
area (a per-deal fact, never a map); p68/p71/p75 are per-parcel
registry/survey facts with no honest area signal (see NO-MAP VERDICTS
in apps/web/lib/layers_group03.ts) and stay None with a check reason —
never a faked number. Unknown (origin or POI list missing) stays None.

Style mirrors services/scoring/livability.py: pure (origin, pois) ->
(Optional[int 0..100], Estonian reason), absolute scales, hermetic
tests. Network lives only in livability.fetch_pois; this module adds no
network calls, only the query fragment + tag mapping the live path needs.

Tag verification (2026-09-12 snapshot PBF, done once by the author,
NOT at runtime — osmium tags-count + tags-filter nwr/, PR #118):
* natural=coastline x620, natural=water x3684, natural=wetland x606,
  waterway=river x1022, waterway=stream x1593 objects; extract keeps
  21843 features, open-water predicate keeps shore + inland water +
  wetlands + flowing lines (coast 885, inland 7986, waterway 11539).
  derived-water.geojson alone is insufficient (no sea, no rivers).
* p29/p68/p71/p75 need no tags: p29 reads the listing record, the rest
  are registry NULLs by verdict.

Integration (deliberately NOT done here): extending livability.OVERPASS_QUERY
with GROUP03_OVERPASS_FRAGMENT, livability._POI_KIND with GROUP03_POI_KIND,
and rebalancing livability.WEIGHTS (+ apps/web/lib/weights.ts sync) must be
one joint change across all parameter batches — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every sibling.
"""

from typing import Callable, Dict, List, Optional, Tuple

from livability import _band, _fmt_m, _nearest_m

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# New POI kinds + Overpass fragment for the live path.
# The drainage proxy reads mapped open water within ~1.2 km; p29/p68/p71/
# p75 need no fetch (listing record / registry NULLs by verdict).
# ---------------------------------------------------------------------------

#: Extra (tagkey, {tagvalue: kind}) rows for livability._POI_KIND.
GROUP03_POI_KIND = [
    ("natural", {"water": "open_water", "wetland": "open_water",
                 "coastline": "open_water"}),
    ("waterway", {"river": "open_water", "stream": "open_water",
                  "canal": "open_water", "ditch": "open_water",
                  "drain": "open_water"}),
]

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP03_OVERPASS_FRAGMENT = """
  node["natural"~"water|wetland|coastline"](around:1200,{lat},{lon});
  node["waterway"~"river|stream|canal|ditch|drain"](around:1200,{lat},{lon});
  way["natural"~"water|wetland|coastline"](around:1200,{lat},{lon});
  way["waterway"~"river|stream|canal|ditch|drain"](around:1200,{lat},{lon});"""


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 3 kind matching the OSM tags, else None. Pure."""
    for tagkey, mapping in GROUP03_POI_KIND:
        val = (tags or {}).get(tagkey, "").split(";")[0]
        if val in mapping:
            return mapping[val]
    return None


# ---------------------------------------------------------------------------
# p29: lot size (the listing's own lot area vs the Tallinn house-plot band).
# Not spatial: korteriomand flats carry no lot (None); houses score their
# recorded lot m². Tallinn house plots cluster ~400-1200 m² (author
# judgment, reviewable): generous plots saturate, tiny yards read low.
# ---------------------------------------------------------------------------

def dim_lot_size(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]],
                 lot_m2: Optional[float] = None) -> Score:
    """p29: lot-size goodness from the listing record (m²), else None."""
    if lot_m2 is None:
        return None, "Krundi suurus teadmata (kinnistusraamat/kuulutus)"
    if lot_m2 <= 0:
        return None, "Krundi suurus vigane (kinnistusraamat/kuulutus)"
    s = _band(lot_m2, [(400, 45), (800, 65), (1500, 80)])
    assert s is not None
    return s, "Krundi suurus %d m² (Tallinna majakruntide mediaan ~700 m²)" % round(lot_m2)


# ---------------------------------------------------------------------------
# p50: topography/drainage proxy (nearest mapped open water).
# DEM absent: far-from-water reads dry (good drainage assumption),
# on/near water reads wet (high-water-table / check-drainage hint).
# Bands track the raster half (300 m -> 50) within band rounding.
# ---------------------------------------------------------------------------

def dim_drainage(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p50: drainage goodness from distance to mapped open water."""
    if not origin or pois is None:
        return None, "Drenaaži info puudub (drenaažiproksi)"
    m = _nearest_m(origin, pois, {"open_water"})
    if m is None:
        return 85, "Avatud vesi üle ~1 km (drenaažiproksi: kuiv)"
    s = _band(m, [(100, 25), (300, 50), (600, 67), (1200, 80)])
    assert s is not None
    return s, "Drenaažiproksi (hinnang): lähim avavesi %s" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p68/p71/p75: documented no-map registry NULLs (OTA PR #131 precedent).
# Each is a per-parcel Maa-amet/kinnistusraamat fact with no honest area
# signal; the scorer reports the gap with a concrete buyer check instead
# of a faked number.
# ---------------------------------------------------------------------------

def dim_soil_stability(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p68: NULL — soil DB absent from the snapshot (no honest proxy)."""
    return None, "Pinnase info puudub (Maa-amet pinnaseandmed pole hetktõmmises; küsi geoloogiauuringut)"


def dim_easements(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p71: NULL — KKIS servitudes are per-parcel legal facts (no map)."""
    return None, "Servituutide info puudub (KKIS/kinnistusraamat; kontrolli ostueelses õigusauditis)"


def dim_boundary_clarity(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p75: NULL — boundary clarity is a per-parcel survey fact (no map)."""
    return None, "Piiride info puudub (katastrimõõdistus; kontrolli piirimärke kohapeal)"


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP03_DIMS: Dict[str, Tuple[str, Callable[..., Score]]] = {
    "lot_size": ("Krundi suurus", dim_lot_size),
    "drainage": ("Drenaaž (proksi)", dim_drainage),
    "soil_stability": ("Pinnase stabiilsus", dim_soil_stability),
    "easements": ("Servituudid", dim_easements),
    "boundary_clarity": ("Piiride selgus", dim_boundary_clarity),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP03_PARAM_IDS = {
    "lot_size": 29,
    "drainage": 50,
    "soil_stability": 68,
    "easements": 71,
    "boundary_clarity": 75,
}


def score_group03(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 3 dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP03_DIMS.items():
        v, reason = fn(origin, pois)
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
