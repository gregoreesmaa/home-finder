"""Group 11 leftover-A layer companion dims (issue #134).

Params (this layer batch only -- sibling batches own disjoint sets):
* p88  school bus route accessibility (HONEST PROXY)
* p101 specialized recreation proximity (real)
* p124 specialized medical access (real)
* p169 philosophical/religious proximity (real)
* p190 foraging and natural resources access (real)

This module adds NO new scorer math: the canonical dims already exist
and are well-tested (dims_group11.py batch B2 for p88/p101/p124/p190,
dims_group11b.py batch B3 for p169). Duplicating them here would create
two sources of truth for the same params. Instead this module binds each
layer-batch param to its canonical dim, declares the per-param map
verdict (mirrored in apps/web/lib/layers_group11c.ts G11C_VERDICTS),
and exposes the layer-id-keyed entry point the map side needs.

Map verdicts (see also the layer file header):
* p88 "proxy": route=school_bus has ~2 uses globally, so real routes are
  unmapped. The dim (and the raster) score stop-served schools as a
  labelled estimate -- every reason says "hinnang", never a route.
* p101/p124/p169/p190 "real": the raster stamps mapped OSM features
  directly (specialised leisure, hospitals/dentists, places of worship,
  forest/scrub/heath units).

No network: pure functions on (origin, pois) only, like the canonical
dims. Weighting into combine/enrich_row stays central (see the canonical
modules); this module only re-keys their outputs by map layer id.
"""

from typing import Callable, Dict, List, Optional, Tuple

from dims_group11 import (
    dim_forage,
    dim_medical_special,
    dim_rec_special,
    dim_school_bus,
)
from dims_group11b import dim_worship

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Layer id -> (param id, Estonian title, canonical dim fn).
G11C_LAYER_DIMS: Dict[str, Tuple[int, str, Callable[..., Score]]] = {
    "schoolbus": (88, "Koolibussiühendus (hinnang)", dim_school_bus),
    "recspecial": (101, "Erisport ja vaba aeg", dim_rec_special),
    "medspecial": (124, "Eriarstiabi", dim_medical_special),
    "worship": (169, "Pühakojad", dim_worship),
    "forage": (190, "Korjealad (seen/mari)", dim_forage),
}

#: Per-param map verdict (mirrors G11C_VERDICTS in layers_group11c.ts).
G11C_VERDICTS: Dict[int, str] = {
    88: "proxy",
    101: "real",
    124: "real",
    169: "real",
    190: "real",
}


def score_group11c(
    origin: Optional[Tuple[float, float]],
    pois: Optional[List[dict]],
) -> Dict[str, Optional[int]]:
    """All five leftover-A layer dims at once, keyed by map layer id."""
    return {layer: fn(origin, pois)[0] for layer, (_, _, fn) in G11C_LAYER_DIMS.items()}
