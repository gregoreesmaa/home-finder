"""Hermetic tests for scripts/build/batch_fiber_import.py (issue #654).

No network, no snapshot files: pins the shared-LCC flip (the fiber
Snyder TM pair disagreed with true L-EST97 by ~20-85 m, #648
precedent) with absolute, non-circular pins.
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_canopy import lest97_to_lonlat, lonlat_to_lest97  # noqa: E402
from batch_fiber_import import (  # noqa: E402
    county_tiles,
    lest97_to_wgs84,
    selftest,
    wgs84_to_lest97,
)


def test_delegates_match_shared_lcc():
    # The fiber twins are thin delegates onto batch_canopy -- same
    # function, same values, no second implementation to drift.
    for lon, lat in ((24.75, 59.44), (23.5, 58.6), (25.4, 59.6)):
        assert wgs84_to_lest97(lon, lat) == lonlat_to_lest97(lon, lat)
    for e, n in ((542555.36, 6589368.19), (500000.0, 6375000.0)):
        assert lest97_to_wgs84(e, n) == lest97_to_lonlat(e, n)


def test_lcc_origin_exact():
    # EPSG:3301 definition: the projection origin maps EXACTLY to
    # (E0, N0). Non-circular (no Tallinn reference involved).
    e, n = wgs84_to_lest97(24.0, 57.5175538888889)
    assert abs(e - 500000.0) < 1e-6
    assert abs(n - 6375000.0) < 1e-6


def test_lcc_tallinn_discriminator():
    # True LCC E542555.36 N6589368.19 for (24.75, 59.44) -- the retired
    # TM code lands ~17 m / ~80 m off (dE/dN), so this pin fails under
    # the old projection while origin/meridian pins pass under both.
    e, n = wgs84_to_lest97(24.75, 59.44)
    assert abs(e - 542555.36) < 0.01
    assert abs(n - 6589368.19) < 0.01
    assert math.hypot(e - 542538, n - 6589288) > 50  # old TM pin is far


def test_ole_anchor_lcc_truth():
    # WFS sample 540959/6589072 (Õle tn 6b): LCC truth, tightened from
    # the old loose bbox (retired TM read 24.72213, 59.43822).
    lo, la = lest97_to_wgs84(540959, 6589072)
    assert abs(lo - 24.72181) < 1e-4
    assert abs(la - 59.43750) < 1e-4


def test_selftest_runs_green(capsys):
    selftest()
    assert "LCC origin-exact + Tallinn pin" in capsys.readouterr().out


def test_county_tiles_cover_harju():
    tiles = county_tiles()
    assert len(tiles) > 10
    for x0, y0, x1, y1 in tiles:
        assert x0 < x1 and y0 < y1
    xs = [t[0] for t in tiles] + [t[2] for t in tiles]
    ys = [t[1] for t in tiles] + [t[3] for t in tiles]
    # LCC envelope of Harjumaa + 5 km margin (E ~430k-620k, N ~6450k-6630k).
    assert min(xs) < 470000 < max(xs)
    assert min(ys) < 6480000 < max(ys)
