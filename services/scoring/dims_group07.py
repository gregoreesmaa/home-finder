"""Group 7 environmental-health dimensions: batch G07 (issue #140).

Params (this agent only — sibling batches own disjoint sets):
* p61  air quality / industrial proximity (tööstusläheduse proksi)
* p62  ambient odors (puhasti/prügila proksi)
* p66  radon gas levels (DOCUMENTED NO-MAP — always None)
* p67  local pests and wildlife (DOCUMENTED NO-MAP — always None)
* p137 seasonal allergens (DOCUMENTED NO-MAP — always None)

HONESTY (load-bearing, AGENTS.md §7.2): Keskkonnaagentuur air-quality
stations and any measured odor/pollen/radon survey are NOT in the
2026-09-12 snapshot, so p61/p62 are OSM PROXIMITY proxies: high score
= far/clean (hinnang), low score = near/exposed (hinnang). Every
non-None reason says "proksi" and "hinnang"; no reason mentions AQI,
OU/m3, Bq/m3 or pollen grains/m3. p66/p67/p137 have no snapshot
source at all — and p137 must NOT reuse mapped green (parks EMIT
pollen, so a green proxy would read inverted) — so they return None
with a reason that says what is missing, never a faked number.
Unknown (origin or POI list missing) stays None.

Style mirrors services/scoring/livability.py: pure (origin, pois) ->
(Optional[int 0..100], Estonian reason), absolute scales, hermetic
tests. Network lives only in livability.fetch_pois; this module adds no
network calls, only the query fragment + tag mapping the live path needs.

Tag verification (2026-09-12 snapshot, done once by the author, NOT at
runtime):
* harju-amenities.geojson: landuse=industrial x54 features = 27 areas
  + their 27 closed-way twins (used once; same set the GENV lowspec
  layer stamps).
* derived-odor.geojson (one-time PBF export, see
  scripts/build/batch_g07_envhealth.py): man_made=wastewater_plant
  ~36 areas + landuse=landfill ~24 areas (twins/untagged dropped).

Integration (deliberately NOT done here): extending livability.OVERPASS_QUERY
with GROUP07_OVERPASS_FRAGMENT, livability._POI_KIND with GROUP07_POI_KIND,
and rebalancing livability.WEIGHTS (+ apps/web/lib/weights.ts sync) must be
one joint change across all parameter batches — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every sibling.
"""

from typing import Callable, Dict, List, Optional, Tuple

from livability import _band, _fmt_m, _nearest_m

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# New POI kinds + Overpass fragment for the live path.
# Radii are judgment calls: industrial haze and plant/landfill smell
# carry like low-frequency rumble (~1 km window).
# ---------------------------------------------------------------------------

#: Extra (tagkey, {tagvalue: kind}) rows for livability._POI_KIND.
GROUP07_POI_KIND = [
    ("landuse", {"industrial": "industrial",
                 "landfill": "odor"}),
    ("man_made", {"wastewater_plant": "odor"}),
]

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP07_OVERPASS_FRAGMENT = """
  node["landuse"~"industrial|landfill"](around:1000,{lat},{lon});
  node["man_made"="wastewater_plant"](around:1000,{lat},{lon});
  way["landuse"~"industrial|landfill"](around:1000,{lat},{lon});
  way["man_made"="wastewater_plant"](around:1000,{lat},{lon});"""


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 7 kind matching the OSM tags, else None. Pure."""
    for tagkey, mapping in GROUP07_POI_KIND:
        val = (tags or {}).get(tagkey, "").split(";")[0]
        if val in mapping:
            return mapping[val]
    return None


# ---------------------------------------------------------------------------
# p61: industrial-proximity proxy (nearest industrial area).
# ---------------------------------------------------------------------------

def dim_industrial(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p61: cleanliness from distance to the nearest industrial area."""
    if not origin or pois is None:
        return None, "Tööstusläheduse info puudub (õhu proksi, hinnang)"
    m = _nearest_m(origin, pois, {"industrial"})
    if m is None:
        return 85, "Tööstusala üle ~1 km (õhu proksi, hinnang: puhas)"
    s = _band(m, [(200, 30), (500, 55), (1000, 75)])
    assert s is not None
    return s, "Õhu proksi: lähim tööstusala %s (hinnang)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p62: ambient-odor proxy (nearest wastewater plant / landfill).
# ---------------------------------------------------------------------------

def dim_odor(origin: Optional[Tuple[float, float]],
             pois: Optional[List[dict]]) -> Score:
    """p62: cleanliness from distance to the nearest odor source."""
    if not origin or pois is None:
        return None, "Lõhnaallikate info puudub (lõhna proksi, hinnang)"
    m = _nearest_m(origin, pois, {"odor"})
    if m is None:
        return 90, "Puhasti/prügila üle ~1 km (lõhna proksi, hinnang: puhas)"
    s = _band(m, [(200, 30), (500, 55), (1000, 75)])
    assert s is not None
    return s, "Lõhna proksi: lähim puhasti/prügila %s (hinnang)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p66/p67/p137: documented no-map (OTA PR #131 precedent). Registry data
# is absent from the snapshot, so these stay NULL — never faked. p137
# deliberately does NOT reuse mapped green (parks emit pollen).
# ---------------------------------------------------------------------------

def dim_radon(origin: Optional[Tuple[float, float]],
              pois: Optional[List[dict]]) -> Score:
    """p66: radon has no snapshot source — always None."""
    return None, "Radooni info puudub (geoloogiaatlas mõõtmata, hinnangut pole)"


def dim_pests(origin: Optional[Tuple[float, float]],
              pois: Optional[List[dict]]) -> Score:
    """p67: pests/wildlife have no snapshot source — always None."""
    return None, "Kahjurite/metsloomade info puudub (seireta, hinnangut pole)"


def dim_allergens(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p137: allergens have no snapshot source — always None."""
    return None, ("Allergeenide info puudub (õietolmujaamu pole; "
                  "haljas loeks vastupidi, hinnangut pole)")


#: Dim name -> parameters3.md number (no-map dims included: they are
#: scored — as NULL — by score_group07 below).
GROUP07_PARAM_IDS = {
    "industrial": 61,
    "odor": 62,
    "radon": 66,
    "pests": 67,
    "allergens": 137,
}

_DIM_FNS: Dict[str, Callable[[Optional[Tuple[float, float]],
                             Optional[List[dict]]], Score]] = {
    "industrial": dim_industrial,
    "odor": dim_odor,
    "radon": dim_radon,
    "pests": dim_pests,
    "allergens": dim_allergens,
}


def score_group07(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]],
                                                       List[str]]:
    """Score all five Group 7 dims. Pure; NULLs stay NULL."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for name, fn in _DIM_FNS.items():
        score, reason = fn(origin, pois)
        dims[name] = score
        if score is not None:
            reasons.append(reason)
    return dims, reasons
