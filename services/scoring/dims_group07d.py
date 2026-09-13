"""Group 7 environmental-health dimensions: batch G07D (issue #143).

Params (this agent only — sibling batches own disjoint sets):
* p409 proximity to active agriculture (põllumajandusmaa proksi)
* p450 wildlife migration corridors (elupaiga proksi)
* p448 harvest season dust/traffic (DOCUMENTED NO-MAP — always None)
* p471 lead water service lines (DOCUMENTED NO-MAP — always None)
* p499 radon mitigation aesthetic (DOCUMENTED NO-MAP — always None)

HONESTY (load-bearing, AGENTS.md S7.2): no PRIA spray map, no
harvest-activity log, no corridor register, no pipe-material registry
and no mitigation survey exist in the 2026-09-12 snapshot, so
p409/p450 are OSM PROXIMITY proxies: high score = far/clean
(hinnang), low score = near/exposed (hinnang). Every non-None reason
says "proksi" and "hinnang"; no reason mentions spray doses, corridor
ids, pipe counts or radon classes. p448/p471/p499 have no snapshot
source at all — and p448 must NOT reuse the agrifield footprint with
seasonal meaning (that would duplicate p409's map as fake harvest
timing), p471 must NOT reuse building age (0.13% coverage, zero pipe
tags — noise presented as plumbing), and p499 is a facade-aesthetics
judgment with no data at all — so they return None with a reason that
says what is missing, never a faked number. Unknown (origin or POI
list missing) stays None.

Style mirrors services/scoring/livability.py: pure (origin, pois) ->
(Optional[int 0..100], Estonian reason), absolute scales, hermetic
tests. Network lives only in livability.fetch_pois; this module adds no
network calls, only the query fragment + tag mapping the live path needs.

Tag verification (2026-09-12 snapshot, done once by the author, NOT at
runtime):
* derived-agrifull.geojson (one-time PBF export, see
  scripts/build/batch_g07d_envhealth.py): landuse=farmland (1545
  areas) + farmyard (284) + meadow (1549) + orchard (9) +
  greenhouse_horticulture (42). Broader than the #141 agriland
  footprint on purpose (active-ag proximity, not spray-specific).
* derived-habitat.geojson (one-time PBF export): natural=wood (3642
  areas) + natural=wetland (606) + leisure/boundary nature_reserve
  (26 areas). Corridor centrelines are unmapped: this is an encounter
  proxy (game moves through mapped habitat).

Integration (deliberately NOT done here): extending livability.OVERPASS_QUERY
with GROUP07D_OVERPASS_FRAGMENT, livability._POI_KIND with GROUP07D_POI_KIND,
and rebalancing livability.WEIGHTS (+ apps/web/lib/weights.ts sync) must be
one joint change across all parameter batches — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every sibling.
"""

from typing import Callable, Dict, List, Optional, Tuple

from livability import _band, _fmt_m, _nearest_m

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# New POI kinds + Overpass fragment for the live path.
# Radii are judgment calls: drift/odour from fields reads wider than the
# parcel-scale habitat edge (same halves as the county masters).
# ---------------------------------------------------------------------------

#: Extra (tagkey, {tagvalue: kind}) rows for livability._POI_KIND.
GROUP07D_POI_KIND = [
    ("landuse", {"farmland": "agrifield",
                 "farmyard": "agrifield",
                 "meadow": "agrifield",
                 "orchard": "agrifield",
                 "greenhouse_horticulture": "agrifield"}),
    ("natural", {"wood": "wildcorr",
                 "wetland": "wildcorr"}),
    ("leisure", {"nature_reserve": "wildcorr"}),
    ("boundary", {"nature_reserve": "wildcorr"}),
]

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP07D_OVERPASS_FRAGMENT = """
  node["landuse"~"farmland|farmyard|meadow|orchard|greenhouse_horticulture"](around:1000,{lat},{lon});
  node["natural"~"wood|wetland"](around:1000,{lat},{lon});
  node["leisure"="nature_reserve"](around:1000,{lat},{lon});
  way["landuse"~"farmland|farmyard|meadow|orchard|greenhouse_horticulture"](around:1000,{lat},{lon});
  way["natural"~"wood|wetland"](around:1000,{lat},{lon});
  way["leisure"="nature_reserve"](around:1000,{lat},{lon});"""


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 7D kind matching the OSM tags, else None. Pure."""
    for tagkey, mapping in GROUP07D_POI_KIND:
        val = (tags or {}).get(tagkey, "").split(";")[0]
        if val in mapping:
            return mapping[val]
    return None


# ---------------------------------------------------------------------------
# p409: active-agriculture proximity proxy (nearest field/farmyard/meadow).
# ---------------------------------------------------------------------------

def dim_agrifield(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p409: cleanliness from distance to the nearest active agriculture."""
    if not origin or pois is None:
        return None, "Põllumajandusmaa info puudub (proksi, hinnang)"
    m = _nearest_m(origin, pois, {"agrifield"})
    if m is None:
        return 90, "Haritav maa üle ~1 km (põllumajanduse proksi, hinnang: puhas)"
    s = _band(m, [(200, 30), (500, 55), (1000, 75)])
    assert s is not None
    return s, "Põllumajanduse proksi: lähim haritav maa %s (hinnang)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p450: wildlife-corridor encounter proxy (nearest mapped habitat).
# ---------------------------------------------------------------------------

def dim_wildcorr(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p450: cleanliness from distance to the nearest mapped habitat."""
    if not origin or pois is None:
        return None, "Elupaikade info puudub (koridoride proksi, hinnang)"
    m = _nearest_m(origin, pois, {"wildcorr"})
    if m is None:
        return 85, "Elupaik üle ~1 km (koridoride proksi, hinnang: puhas)"
    s = _band(m, [(200, 30), (500, 55), (1000, 75)])
    assert s is not None
    return s, "Koridoride proksi: lähim elupaik %s (hinnang)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p448/p471/p499: documented no-map (OTA PR #131 precedent). Registry
# data is absent from the snapshot, so these stay NULL — never faked.
# p448 deliberately does NOT reuse the agrifield footprint (a spatial
# copy with seasonal meaning would be fake harvest timing); p471 does
# NOT reuse building age (644/509656 = 0.13% age tags, zero pipe tags);
# p499 is an aesthetics judgment with no data at all.
# ---------------------------------------------------------------------------

def dim_harvest(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p448: harvest dust/traffic has no snapshot source — always None."""
    return None, "Lõikusaja info puudub (hooaja ajastus mõõtmata, hinnangut pole)"


def dim_leadpipes(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p471: lead service lines have no snapshot source — always None."""
    return None, "Torustiku info puudub (torumaterjal kaardistamata, hinnangut pole)"


def dim_radonaesth(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p499: mitigation aesthetics have no snapshot source — always None."""
    return None, "Radoonitõrje esteetika mõõtmata (hinnangut pole)"


#: Dim name -> parameters3.md number (no-map dims included: they are
#: scored — as NULL — by score_group07d below).
GROUP07D_PARAM_IDS = {
    "agrifield": 409,
    "wildcorr": 450,
    "harvest": 448,
    "leadpipes": 471,
    "radonaesth": 499,
}

_DIM_FNS: Dict[str, Callable[[Optional[Tuple[float, float]],
                             Optional[List[dict]]], Score]] = {
    "agrifield": dim_agrifield,
    "wildcorr": dim_wildcorr,
    "harvest": dim_harvest,
    "leadpipes": dim_leadpipes,
    "radonaesth": dim_radonaesth,
}


def score_group07d(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]],
                                                        List[str]]:
    """Score all five Group 7D dims. Pure; NULLs stay NULL."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for name, fn in _DIM_FNS.items():
        score, reason = fn(origin, pois)
        dims[name] = score
        if score is not None:
            reasons.append(reason)
    return dims, reasons
