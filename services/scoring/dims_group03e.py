"""Group 3 cadastre-E dimensions: batch G03E (issue #155).

Params (this agent only — sibling batches own disjoint sets):
* p397 perimeter fence ownership (documented no-map: NULL + seller check)
* p400 yard drainage and swales (documented no-map: NULL + site check)

HONESTY (load-bearing, AGENTS.md §7.2): p397 asks WHO owns the boundary
fence (buyer / neighbour / shared) — a bilateral per-parcel legal fact
with zero snapshot signal (no ownership=* / owner=* on any of the 36384
snapshot barrier objects; the 364 operator=* tags sit on school /
substation compound fences and answer a different question). p400 asks
about per-parcel micro-drainage (swales, grading, French drains, sump
routing) whose works are unobservable at area scale; the only area
signal (8973 ditch/drain lines, 2663 in Tallinn) is already consumed by
the p50 drainage proxy (#151) with the opposite polarity, so a second
gradient would duplicate or contradict it. Both dims stay None with a
concrete buyer check — never a faked number. Unknown (origin or POI
list missing) stays None too.

Style mirrors services/scoring/dims_group03.py NULL dims (p68/p71/p75):
pure (origin, pois) -> (None, Estonian reason), hermetic tests. No
helpers are needed (no livability import, no local copies): NULL dims
take no measurements. Network lives only in livability.fetch_pois;
this module adds no network calls and no Overpass fragment — NULL dims
need no fetch.

Tag verification (2026-09-12 snapshot PBF, done once by the author,
NOT at runtime — osmium tags-filter nwr/ + export, PR #118):
* barrier: 36384 objects, fence 11308; ownership=* keys 0, owner=* keys
  0, operator=* keys 364 (198 Tallinna Haridusamet school yards, ~90
  Elering/Elektrilevi substations — institutional compounds, not
  residential boundary ownership). Note the osmium pitfall hit during
  verification: space-separated expressions must be SEPARATE argv items
  (OR); a single quoted "a b" string matches nothing.
* waterway=ditch 7657 + waterway=drain 1316 tagged lines (2663 in the
  Tallinn bbox) — dense, but every one of these tags already feeds p50.

Integration (deliberately NOT done here): rebalancing
livability.WEIGHTS (+ apps/web/lib/weights.ts sync) must be one joint
change across all parameter batches — existing tests pin set(WEIGHTS)
exactly, so per-batch WEIGHTS edits would break every sibling.
"""

from typing import Callable, Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# p397/p400: documented no-map registry NULLs (OTA PR #131 precedent).
# Each is a per-parcel fact (legal ownership / micro-drainage works) with
# no honest area signal; the scorer reports the gap with a concrete buyer
# check instead of a faked number.
# ---------------------------------------------------------------------------

def dim_fence_ownership(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p397: NULL — fence ownership is a per-parcel legal fact (no map)."""
    return None, ("Piirdeaia omand teadmata (ostja/naaber/ühine selgub "
                  "müüjalt ja kinnistusraamatust/piiriprotokollist; "
                  "hetktõmmises omandi-märgendeid pole — EI OLE hinnangut, "
                  "ära feigi)")


def dim_yard_drainage(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p400: NULL — yard drainage works are per-parcel facts (no map)."""
    return None, ("Hoovi kuivendus teadmata (kalded, kraavid, sademevee "
                  "ärajuhtimine ja ÜVK liitumine vajavad kohapealset "
                  "kontrolli, parim kevadel; piirkonna märguskontekst on "
                  "p50 drenaažiproksi kiht — EI OLE hoovi hinnangut, "
                  "ära feigi)")


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP03E_DIMS: Dict[str, Tuple[str, Callable[..., Score]]] = {
    "fence_ownership": ("Piirdeaia omand", dim_fence_ownership),
    "yard_drainage": ("Hoovi kuivendus", dim_yard_drainage),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP03E_PARAM_IDS = {
    "fence_ownership": 397,
    "yard_drainage": 400,
}


def score_group03e(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """Both Group 3-E dims at once: {param: None} (NULLs by verdict)."""
    return {key: fn(origin, pois)[0] for key, (_, fn) in GROUP03E_DIMS.items()}
