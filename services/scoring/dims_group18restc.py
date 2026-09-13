"""Group 18 rest dimensions: batch G18C (issue #197).

Params (this agent only — sibling batches own disjoint sets):
* p132 window views (documented no-map: NULL + viewing-visit check)

HONESTY (load-bearing, AGENTS.md §7.2): p132 asks what a buyer sees
from THEIR windows (floor + window orientation + what stands directly
in front) — a per-unit view-shed fact with zero snapshot signal
(exactly ONE window=* key county-wide; 252,140 bare building
centroids with no footprints/heights/orientation). The only area
signals a view proxy could lean on are already consumed — openness by
daylight p405 (#173) and dayopen p34 (#172), viewpoints by viewshed
p225 (#163) — so a third openness gradient would duplicate them
(p222 precedent, #163). The dim stays None with a concrete buyer
check — never a faked number. Unknown (origin or POI list missing)
stays None too.

Style mirrors services/scoring/dims_group03e.py NULL dims (#155):
pure (origin, pois) -> (None, Estonian reason), hermetic tests. No
helpers are needed (no livability import, no local copies): NULL dims
take no measurements. Network lives only in livability.fetch_pois;
this module adds no network calls and no Overpass fragment — NULL dims
need no fetch.

Tag verification (2026-09-13 snapshot PBF, done once by the author,
NOT at runtime — osmium tags-filter nwr/ + export, PR #118):
* nwr/window: 1 object county-wide (zero window signal by
  construction — a gradient has nothing to calibrate).
* nwr/building:levels: 33,311 features, of which 7,853 parse to
  levels>=4 (first-semicolon value, int(float)); the tall-mass signal
  already feeds dayopen p34 (#172).
* derived-buildings.json: 252,140 bare [{lon, lat}] centroids (no tags
  to verify); the openness inventory daylight p405 already inverts
  (#173).

Integration (deliberately NOT done here): rebalancing
livability.WEIGHTS (+ apps/web/lib/weights.ts sync) must be one joint
change across all parameter batches — existing tests pin set(WEIGHTS)
exactly, so per-batch WEIGHTS edits would break every sibling.
"""

from typing import Callable, Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# p132: documented no-map registry NULL (OTA PR #131 precedent).
# A per-unit view-shed fact (floor + orientation + what blocks YOUR
# windows) with no honest area signal; the scorer reports the gap with a
# concrete buyer check instead of a faked number.
# ---------------------------------------------------------------------------

def dim_windowviews(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p132: NULL — window views need floor + orientation (no map)."""
    return None, ("Aknavaade teadmata (korrus, akende suund ja vaadet "
                  "varjav hoonestus selguvad ainult kohapealsel külastusel; "
                  "hetktõmmises on ainult hoonekeskmed — jalajäljed, "
                  "kõrgused ja asimuudid puuduvad ning aknamärgendeid on "
                  "terves maakonnas üks — EI OLE vaate hinnangut, ära "
                  "feigi; piirkonna avaruskontekst on daylight/dayopen/"
                  "vaatekaitse kihtidel)")


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP18C_DIMS: Dict[str, Tuple[str, Callable[..., Score]]] = {
    "windowviews": ("Aknavaade (kontroll)", dim_windowviews),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP18C_PARAM_IDS = {
    "windowviews": 132,
}


def score_group18restc(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """Group 18-rest-C dims at once: {param: None} (NULLs by verdict)."""
    return {key: fn(origin, pois)[0] for key, (_, fn) in GROUP18C_DIMS.items()}
