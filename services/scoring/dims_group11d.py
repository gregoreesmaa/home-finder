"""Group 11 leftover-batch D scorer registry (issue #135).

Params: p317 park maintenance/enforcement, p346 mailbox placement &
security, p419 alleyway access, p466 trail privacy loss, p470 mail
delivery location.

This module adds NO new scoring semantics. All five params already have
pure, hermetic scorer dims on main -- p317 as an honest stub in
dims_group11.py (batch B2, issue #97: no OSM tag encodes upkeep
quality, so it returns None like livability.dim_air), and p346 / p419 /
p466 / p470 in dims_group11b.py (batch B3, issue #95). Forking second
implementations here would split the future central WEIGHTS integration
across two competing homes for the same params, so this file is a thin
registry: it re-exports the canonical dims and exposes them under one
batch-D entry point (GROUP11D_DIMS / score_group11d) with the map-layer
verdicts from apps/web/lib/layers_group11d.ts pinned next to each row.

Map verdicts (documented in full in layers_group11d.ts):
* p317: documented no-map (OTA PR #131 precedent) -- upkeep quality is
  not in OSM; the B2 stub stands.
* p346/p419/p466/p470: real snapshot layers (mailbox / alley /
  trailprivacy / postal); the dims below are their listing-side
  counterparts.
"""

from typing import Callable, Dict, List, Optional, Tuple

from dims_group11 import dim_park_upkeep
from dims_group11b import (
    dim_alley,
    dim_letterbox,
    dim_postal,
    dim_trail_privacy,
)

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


def dim_park_upkeep_listing(
    origin: Optional[Tuple[float, float]], pois: Optional[List[dict]]
) -> Score:
    """p317 adapter: the canonical stub takes no inputs (there is no
    upkeep signal to score); the batch registry needs the uniform
    (origin, pois) shape, so the inputs are accepted and ignored."""
    _ = (origin, pois)
    return dim_park_upkeep()


#: Batch-D registry: (registry key, parameters3.md param id, Estonian
#: title, scorer). Scorers are the canonical merged implementations,
#: NOT copies -- see the module docstring.
GROUP11D_DIMS: Tuple[Tuple[str, str, str, Callable[..., Score]], ...] = (
    ("park_upkeep", "p317", "Pargihooldus", dim_park_upkeep_listing),
    ("letterbox", "p346", "Postkast", dim_letterbox),
    ("alley", "p419", "Taga-tänav", dim_alley),
    ("trail_privacy", "p466", "Rajaprivaatsus", dim_trail_privacy),
    ("postal", "p470", "Postiteenus", dim_postal),
)


def score_group11d(
    origin: Optional[Tuple[float, float]], pois: Optional[List[dict]]
) -> Dict[str, Optional[int]]:
    """All five batch-D dims for one listing (entry point for the central
    weight-rebalance follow-up; keys match GROUP11D_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, _, fn in GROUP11D_DIMS}
