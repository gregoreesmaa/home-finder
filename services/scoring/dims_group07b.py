"""Group 7 environmental-health dimensions: batch G07B (issue #141).

Params (this agent only — sibling batches own disjoint sets):
* p189 soil history / toxicity (pruunvälja proksi)
* p202 buried oil tanks (mahutite proksi)
* p227 agricultural boundaries (põllumajandusmaa proksi)
* p204 hazardous materials (DOCUMENTED NO-MAP — always None)
* p252 invasive plant species (DOCUMENTED NO-MAP — always None)

HONESTY (load-bearing, AGENTS.md §7.2): no soil-toxicity survey, no
buried-tank register and no PRIA spray map exist in the 2026-09-12
snapshot, so p189/p202/p227 are OSM PROXIMITY proxies: high score =
far/clean (hinnang), low score = near/exposed (hinnang). Every
non-None reason says "proksi" and "hinnang"; no reason mentions mg/kg,
tank counts, spray doses or Seveso classes. p204/p252 have no snapshot
source at all — and p252 must NOT reuse mapped green (most mapped
trees are native/planted, so a green proxy would be meaningless) — so
they return None with a reason that says what is missing, never a
faked number. Unknown (origin or POI list missing) stays None.

Style mirrors services/scoring/livability.py: pure (origin, pois) ->
(Optional[int 0..100], Estonian reason), absolute scales, hermetic
tests. Network lives only in livability.fetch_pois; this module adds no
network calls, only the query fragment + tag mapping the live path needs.

Tag verification (2026-09-12 snapshot, done once by the author, NOT at
runtime):
* derived-soil.geojson (one-time PBF export, see
  scripts/build/batch_g07b_envhealth.py): landuse=brownfield, 24
  areas (twins/untagged dropped by the reader).
* derived-tanks.geojson (one-time PBF export): man_made=storage_tank,
  402 areas + 24 points (twins dropped; no content allowlist — OSM
  does not distinguish buried tanks).
* derived-agri.geojson (one-time PBF export): landuse=farmland (1545
  areas) + farmyard (284 areas); meadow/orchard deliberately excluded.

Integration (deliberately NOT done here): extending livability.OVERPASS_QUERY
with GROUP07B_OVERPASS_FRAGMENT, livability._POI_KIND with GROUP07B_POI_KIND,
and rebalancing livability.WEIGHTS (+ apps/web/lib/weights.ts sync) must be
one joint change across all parameter batches — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every sibling.
"""

from typing import Callable, Dict, List, Optional, Tuple

from livability import _band, _fmt_m, _nearest_m

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# New POI kinds + Overpass fragment for the live path.
# Radii are judgment calls: parcel hazards (brownfields, tank yards) read
# at the ~1 km window; spray/dust drift reads slightly wider.
# ---------------------------------------------------------------------------

#: Extra (tagkey, {tagvalue: kind}) rows for livability._POI_KIND.
GROUP07B_POI_KIND = [
    ("landuse", {"brownfield": "brownsoil",
                 "farmland": "agriland",
                 "farmyard": "agriland"}),
    ("man_made", {"storage_tank": "oiltank"}),
]

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP07B_OVERPASS_FRAGMENT = """
  node["landuse"~"brownfield|farmland|farmyard"](around:1000,{lat},{lon});
  node["man_made"="storage_tank"](around:1000,{lat},{lon});
  way["landuse"~"brownfield|farmland|farmyard"](around:1000,{lat},{lon});
  way["man_made"="storage_tank"](around:1000,{lat},{lon});"""


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 7B kind matching the OSM tags, else None. Pure."""
    for tagkey, mapping in GROUP07B_POI_KIND:
        val = (tags or {}).get(tagkey, "").split(";")[0]
        if val in mapping:
            return mapping[val]
    return None


# ---------------------------------------------------------------------------
# p189: soil-history proxy (nearest brownfield).
# ---------------------------------------------------------------------------

def dim_brownsoil(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p189: cleanliness from distance to the nearest brownfield."""
    if not origin or pois is None:
        return None, "Pruunväljade info puudub (mulla proksi, hinnang)"
    m = _nearest_m(origin, pois, {"brownsoil"})
    if m is None:
        return 85, "Pruunväli üle ~1 km (mulla proksi, hinnang: puhas)"
    s = _band(m, [(200, 30), (500, 55), (1000, 75)])
    assert s is not None
    return s, "Mulla proksi: lähim pruunväli %s (hinnang)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p202: buried-oil-tank proxy (nearest mapped tank).
# ---------------------------------------------------------------------------

def dim_oiltank(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p202: cleanliness from distance to the nearest mapped tank."""
    if not origin or pois is None:
        return None, "Mahutite info puudub (õlimahutite proksi, hinnang)"
    m = _nearest_m(origin, pois, {"oiltank"})
    if m is None:
        return 85, "Mahuti üle ~1 km (õlimahutite proksi, hinnang: puhas)"
    s = _band(m, [(200, 30), (500, 55), (1000, 75)])
    assert s is not None
    return s, "Mahutite proksi: lähim mahuti %s (hinnang)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p227: agricultural-boundary proxy (nearest farmland/farmyard).
# ---------------------------------------------------------------------------

def dim_agriland(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p227: cleanliness from distance to the nearest farmland/farmyard."""
    if not origin or pois is None:
        return None, "Põllumajandusmaa info puudub (triivi proksi, hinnang)"
    m = _nearest_m(origin, pois, {"agriland"})
    if m is None:
        return 90, "Põld üle ~1 km (triivi proksi, hinnang: puhas)"
    s = _band(m, [(200, 30), (500, 55), (1000, 75)])
    assert s is not None
    return s, "Triivi proksi: lähim põld %s (hinnang)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p204/p252: documented no-map (OTA PR #131 precedent). Registry data
# is absent from the snapshot, so these stay NULL — never faked. p252
# deliberately does NOT reuse mapped green (most mapped trees are
# native/planted, so a green proxy would be meaningless).
# ---------------------------------------------------------------------------

def dim_hazmat(origin: Optional[Tuple[float, float]],
               pois: Optional[List[dict]]) -> Score:
    """p204: hazardous materials have no snapshot source — always None."""
    return None, "Ohtlike ainete info puudub (kemikaaliregister mõõtmata, hinnangut pole)"


def dim_invasive(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p252: invasive plants have no snapshot source — always None."""
    return None, ("Invasiivtaimede info puudub (liigiseiret pole; "
                  "haljas loeks mõttetult, hinnangut pole)")


#: Dim name -> parameters3.md number (no-map dims included: they are
#: scored — as NULL — by score_group07b below).
GROUP07B_PARAM_IDS = {
    "brownsoil": 189,
    "oiltank": 202,
    "agriland": 227,
    "hazmat": 204,
    "invasive": 252,
}

_DIM_FNS: Dict[str, Callable[[Optional[Tuple[float, float]],
                             Optional[List[dict]]], Score]] = {
    "brownsoil": dim_brownsoil,
    "oiltank": dim_oiltank,
    "agriland": dim_agriland,
    "hazmat": dim_hazmat,
    "invasive": dim_invasive,
}


def score_group07b(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]],
                                                        List[str]]:
    """Score all five Group 7B dims. Pure; NULLs stay NULL."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for name, fn in _DIM_FNS.items():
        score, reason = fn(origin, pois)
        dims[name] = score
        if score is not None:
            reasons.append(reason)
    return dims, reasons
