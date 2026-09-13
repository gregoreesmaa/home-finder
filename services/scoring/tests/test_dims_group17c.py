"""Group 17 HOA-C dims (issue #207): hermetic tests.

No network: the scorer runs on fixture POIs; there is no Overpass
fragment and no tag mapping by design (a per-KÜ fee has no OSM tags).
"""

import dims_group17c as g17c
from dims_group17c import (
    GROUP17C_DIMS,
    GROUP17C_PARAM_IDS,
    dim_hoa_fees,
    score_group17c,
)

TALLINN = (59.4372, 24.7536)

POIS = [{"kind": "privroad", "lat": TALLINN[0] + 0.001, "lon": TALLINN[1]}]


def test_hoa_fees_is_always_none_with_kue_check_reason():
    for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None)]:
        v, reason = dim_hoa_fees(origin, pois)
        assert v is None
        assert "teadmata" in reason
        assert "Äriregistrist" in reason
        # Monthly fee, not the one-off initiation fee (p427, G17-rest).
        assert "Igakuine" in reason


def test_registry_covers_exactly_p3():
    assert set(GROUP17C_DIMS) == {"hoa_fees"}
    assert GROUP17C_PARAM_IDS == {"hoa_fees": 3}
    assert GROUP17C_DIMS["hoa_fees"][0] == "Haldustasu (kontroll)"
    assert GROUP17C_DIMS["hoa_fees"][1] is dim_hoa_fees
    assert g17c.GROUP17C_DIMS is GROUP17C_DIMS


def test_score_group17c_rolls_up_null_without_reasons():
    dims, reasons = score_group17c(TALLINN, POIS)
    assert dims == {"hoa_fees": None}
    # NULL dims contribute no reasons (no fake evidence).
    assert reasons == []
    dims_none, _ = score_group17c(None, None)
    assert dims_none == {"hoa_fees": None}
