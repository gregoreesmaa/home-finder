"""Group 3 cadastre-E dims (issue #155): hermetic tests.

No network: both scorers are unconditional NULLs, so the tests pin the
NULL contract for every input shape plus the registry surface.
"""

from dims_group03e import (
    GROUP03E_DIMS,
    GROUP03E_PARAM_IDS,
    dim_fence_ownership,
    dim_yard_drainage,
    score_group03e,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


POIS = [
    _poi("open_water", 0.001),
    _poi("shallowsrc", 0.004),
]


def test_fence_ownership_is_always_none_with_seller_check():
    for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                         (None, POIS), (TALLINN, None)]:
        v, reason = dim_fence_ownership(origin, pois)
        assert v is None
        assert "kinnistusraamat" in reason
        assert "EI OLE" in reason


def test_yard_drainage_is_always_none_with_site_check():
    for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                         (None, POIS), (TALLINN, None)]:
        v, reason = dim_yard_drainage(origin, pois)
        assert v is None
        assert "kohapealset" in reason
        assert "p50" in reason
        assert "EI OLE" in reason


def test_reasons_name_no_measured_claim():
    for fn in (dim_fence_ownership, dim_yard_drainage):
        _, reason = fn(TALLINN, POIS)
        assert "hinnangut" in reason
        assert "teadmata" in reason
        lowered = reason.lower()
        assert "mõõdetud" not in lowered
        assert "garanteeritud" not in lowered


def test_registry_covers_both_params():
    assert set(GROUP03E_DIMS) == {"fence_ownership", "yard_drainage"}
    assert GROUP03E_PARAM_IDS == {"fence_ownership": 397, "yard_drainage": 400}
    for title, fn in GROUP03E_DIMS.values():
        assert isinstance(title, str) and len(title) > 0
        assert callable(fn)


def test_score_group03e_returns_nulls():
    assert score_group03e(TALLINN, POIS) == {
        "fence_ownership": None, "yard_drainage": None}
    assert score_group03e(None, None) == {
        "fence_ownership": None, "yard_drainage": None}
