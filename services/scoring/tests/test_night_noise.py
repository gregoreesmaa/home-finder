"""Hermetic unit tests for night-noise density bands (#695).

No network, no snapshot: all venue lists are synthetic. Run from repo root:
  python3 -m pytest services/scoring/tests/test_night_noise.py -q

Import note (same as #701): the brief snippet shows services.scoring.X,
but the repo suite imports top-level module names (conftest puts
services/scoring on sys.path), so this follows the sibling convention.
Direction is PINNED here (no `or True`): noisier = lower score.
"""

from dims_night_noise import NIGHTLIFE_KINDS, night_noise


def test_night_noise_bands_on_fixture():
    assert night_noise([]) is None
    assert night_noise(None) is None
    # Pinned direction: noisier = lower score (brief's `or True` resolved).
    assert night_noise(["bar"] * 20)[0] < night_noise(["bar"] * 2)[0]


def test_bands_decrease_monotonically():
    scores = [night_noise(["bar"] * n)[0] for n in (1, 2, 3, 6, 11, 21, 67)]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] > scores[-1]


def test_vanalinna_floor_and_quiet_street():
    assert night_noise(["bar"] * 67)[0] == 20  # held-extract Vanalinn peak
    assert night_noise(["pub"])[0] == 80  # lone venue: rahulik


def test_grouped_kind_and_poi_dicts_count():
    assert night_noise([{"kind": "nightlife"}] * 4)[0] == night_noise(["bar"] * 4)[0]
    assert night_noise([{"kind": "school"}, {"kind": "park"}])[0] == 85


def test_cinema_excluded_like_group09():
    """amenity=cinema is seated culture, not nuisance (GROUP09 verdict)."""
    assert "cinema" not in NIGHTLIFE_KINDS
    assert night_noise(["cinema"] * 30)[0] == 85
