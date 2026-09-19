"""P4 VIIRS brightness-proxy per-listing dim (issue #719 build).

Follow-up of the POSITIVE probe #699: NASA GIBS serves keyless
VIIRS_Black_Marble tiles (annual composite, vintage 2016), sampled
by scripts/build/batch_viirs.py into a block-mean grid. This module
owns ONLY the new brightness-proxy leg under the distinct
``viirs_brightness`` key — the login-walled EOG radiance leg
(``viirs_radiance``, dims_p4_viirs.py, dated-negative NULL) and the
lamp/sun/lidar/ehr/osm sibling slices are owned elsewhere and
untouched (no double-scoring, no shared-file edits).

BRIGHTNESS PROXY (load-bearing honesty): tile means are a
visualization-brightness proxy, never radiometry — the reason says
"heledusproksi" and names the 2016 composite vintage. Coastal
listings may read darker than the sky is (open water carries no
lights — disclosed in docs/p4_viirs_build.md, never silently
corrected).

Style mirrors the delay dims (pure, offline-tested): (origin,
grid) -> (Optional[int 0..100], Estonian reason), where grid is the
caller-supplied block-mean table (test fixtures; production loads
the pole-built grid). No network, no Overpass fragment.

Integration (deliberately NOT done here): no WEIGHTS change —
existing tests pin set(WEIGHTS) exactly, so per-batch WEIGHTS edits
would break every sibling. Rebalancing stays one joint change.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Darkness ladder off block means (mirrors batch_viirs
#: brightness_band — changing the builder without changing this, or
#: vice versa, is a drift bug, pinned by test).
_BAND_UPPER = ((15, 90), (40, 70), (100, 50), (180, 30))


def brightness_band(mean: Optional[float]) -> Optional[int]:
    """Block mean -> darkness band 10..90. Pure (proxy ladder)."""
    if not isinstance(mean, (int, float)) or mean < 0:
        return None
    for upper, band in _BAND_UPPER:
        if mean <= upper:
            return band
    return 10


def nearest_cell(origin: Tuple[float, float],
                 cells: List[dict]) -> Optional[dict]:
    """Nearest grid cell to origin ( equirectangular, pure)."""
    if not origin or not cells:
        return None
    lat, lon = origin
    best = None
    best_d = None
    for c in cells:
        try:
            d = abs(float(c["lat"]) - lat) + abs(float(c["lon"]) - lon)
        except (KeyError, TypeError, ValueError):
            continue
        if best_d is None or d < best_d:
            best, best_d = c, d
    return best


def dim_viirs_brightness(origin: Optional[Tuple[float, float]],
                         cells: Optional[List[dict]]) -> Score:
    """P4-035: darkness hinnang off the GIBS brightness proxy."""
    if not origin or not cells:
        return None, ("Öötaeva pimedus on teadmata (VIIRS "
                      "heledusproksi ruudustik puudub): ära feigi "
                      "olematut pimedushinnet")
    cell = nearest_cell(origin, cells)
    if cell is None:
        return None, ("Öötaeva pimedus on teadmata (lähim "
                      "heledusproksi ruut puudub)")
    band = brightness_band(cell.get("mean"))
    if band is None:
        return None, ("Öötaeva pimedus on teadmata (ruudu "
                      "heledusloend puudub)")
    return band, ("Öötaeva pimedus (VIIRS Black Marble 2016 "
                  "heledusproksi, hinnang %d — heleduspilt, mitte "
                  "mõõdetud radiomeetria; rannikul võib merepimedus "
                  "lugeda; kontrolli detsembris kell 15:30 kohapeal)"
                  % band)


VIIRS_DIMS = (
    ("viirs_brightness", "P4-035", dim_viirs_brightness),
)


def score_viirs(origin: Optional[Tuple[float, float]],
                cells: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 VIIRS brightness dim for one listing (entry point for
    the weight-rebalance follow-up; keys match VIIRS_DIMS)."""
    return {key: fn(origin, cells)[0] for key, _, fn in VIIRS_DIMS}
