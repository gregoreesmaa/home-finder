"""Group 18 rest-C dims (issue #197): hermetic tests.

No network: the scorer is an unconditional NULL, so the tests pin the
NULL contract for every input shape plus the registry surface.
"""

from dims_group18restc import (
    GROUP18C_DIMS,
    GROUP18C_PARAM_IDS,
    dim_windowviews,
    score_group18restc,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


POIS = [
    _poi("building", 0.001),
    _poi("viewpoint", 0.004),
]


def test_windowviews_is_always_none_with_visit_check():
    for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                         (None, POIS), (TALLINN, None)]:
        v, reason = dim_windowviews(origin, pois)
        assert v is None
        assert "külastusel" in reason
        assert "EI OLE" in reason


def test_windowviews_names_the_gap_honestly():
    _, reason = dim_windowviews(TALLINN, POIS)
    assert "hinnangut" in reason
    assert "teadmata" in reason
    assert "LoD2" in reason or "asimuudid" in reason
    # Points at the already-shipped openness context, never re-scores it.
    assert "daylight" in reason
    lowered = reason.lower()
    assert "mõõdetud" not in lowered
    assert "garanteeritud" not in lowered


def test_registry_covers_p132_only():
    assert set(GROUP18C_DIMS) == {"windowviews"}
    assert GROUP18C_PARAM_IDS == {"windowviews": 132}
    for title, fn in GROUP18C_DIMS.values():
        assert isinstance(title, str) and len(title) > 0
        assert callable(fn)


def test_score_group18restc_returns_nulls():
    assert score_group18restc(TALLINN, POIS) == {"windowviews": None}
    assert score_group18restc(None, None) == {"windowviews": None}
