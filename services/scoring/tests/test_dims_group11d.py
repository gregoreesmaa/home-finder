"""Batch-D scorer registry (issue #135): re-exports, not forks.

Hermetic: fixture POIs only, no network, no snapshot reads. Run:
python3 -m pytest services/scoring/tests/test_dims_group11d.py -q
"""

import dims_group11 as g11
import dims_group11b as g11b
from dims_group11d import GROUP11D_DIMS, dim_park_upkeep_listing, score_group11d

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


def test_registry_covers_all_five_batch_params():
    assert [p for _, p, _, _ in GROUP11D_DIMS] == ["p317", "p346", "p419", "p466", "p470"]
    assert [k for k, _, _, _ in GROUP11D_DIMS] == [
        "park_upkeep",
        "letterbox",
        "alley",
        "trail_privacy",
        "postal",
    ]


def test_registry_reexports_canonical_dims_not_copies():
    by_key = {k: fn for k, _, _, fn in GROUP11D_DIMS}
    assert by_key["letterbox"] is g11b.dim_letterbox
    assert by_key["alley"] is g11b.dim_alley
    assert by_key["trail_privacy"] is g11b.dim_trail_privacy
    assert by_key["postal"] is g11b.dim_postal
    # p317 has no (origin, pois) scorer on main -- only the zero-arg stub.
    assert by_key["park_upkeep"] is dim_park_upkeep_listing


def test_park_upkeep_adapter_preserves_honest_stub():
    score, reason = dim_park_upkeep_listing(TALLINN, [_poi("park", 0.001)])
    assert score is None
    assert reason == g11.dim_park_upkeep()[1]
    assert "puudub" in reason


def test_score_group11d_mirrors_canonical_scorers():
    pois = [
        _poi("letter_box", 0.002),
        _poi("alley", 0.001),
        _poi("trail", 0.003),
        _poi("post_office", 0.004),
    ]
    got = score_group11d(TALLINN, pois)
    assert got["letterbox"] == g11b.dim_letterbox(TALLINN, pois)[0]
    assert got["alley"] == g11b.dim_alley(TALLINN, pois)[0]
    assert got["trail_privacy"] == g11b.dim_trail_privacy(TALLINN, pois)[0]
    assert got["postal"] == g11b.dim_postal(TALLINN, pois)[0]
    assert got["park_upkeep"] is None


def test_missing_inputs_stay_honest():
    got = score_group11d(None, None)
    assert got["letterbox"] is None
    assert got["alley"] is None
    assert got["trail_privacy"] is None
    assert got["postal"] is None
    assert got["park_upkeep"] is None
