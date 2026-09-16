"""P4 building-era mix dims (issue #555): hermetic tests.

No network: the EHR backfill gate is unmet (#537 dated negative -
live base unrouted), so production joins are NULL by contract and
every test runs on hand-built year records and mix POIs. Scorers
are proven network-free by running them with urlopen stubbed to
raise (they never import urllib at all). The aggregation grain
(MIN_BUILDINGS privacy floor) and the era-band boundaries are
pinned here.
"""

import dims_p4_era as p4e
import pytest
from dims_p4_era import (
    ERA_CUT_NEW,
    ERA_CUT_OLD,
    MIN_BUILDINGS,
    P4_ERA_DIMS,
    aggregate_era_mix,
    dim_newbuild,
    dim_old_charm,
    era_character,
    score_p4_era,
)

# Tallinn centre: hand-built mix cells sit ~57 m east unless stated.
TALLINN = (59.4372, 24.7536)


def mkpoi(pre1945=0.1, mid=0.6, post1990=0.3, n=20,
          lat=59.4372, lon=24.7546):
    return {"kind": "eramix_p4", "lat": lat, "lon": lon,
            "pre1945": pre1945, "mid": mid, "post1990": post1990, "n": n}


def recs(years):
    return [{"year": y} for y in years]


ALL_FNS = [dim_old_charm, dim_newbuild]


def test_cuts_and_privacy_floor_documented():
    assert (ERA_CUT_OLD, ERA_CUT_NEW) == (1945, 1990)
    assert MIN_BUILDINGS == 5  # privacy: never identify single houses


def test_scorers_never_touch_network(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("scorer used the network")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    for fn in ALL_FNS:
        fn(TALLINN, [mkpoi()])
    score_p4_era(TALLINN, [mkpoi()])


# ---------------------------------------------------------------------------
# Aggregation grain: shares + privacy floor.
# ---------------------------------------------------------------------------

def test_aggregate_computes_shares_over_known_years():
    mix = aggregate_era_mix(recs([1920, 1930, 1965, 1975, 1985, 2005, 2015,
                                  2020, None, "x", True, 1500, 2050]))
    assert mix is not None
    assert mix["n"] == 8  # only usable years count
    assert mix["pre1945"] == pytest.approx(2 / 8)
    assert mix["mid"] == pytest.approx(3 / 8)
    assert mix["post1990"] == pytest.approx(3 / 8)


def test_aggregate_thin_area_stays_null_for_privacy():
    assert aggregate_era_mix(recs([1920, 2005])) is None  # 2 < 5
    assert aggregate_era_mix(recs([1920, 1930, 1965, 1975])) is None  # 4 < 5
    assert aggregate_era_mix(recs([1920, 1930, 1965, 1975, 2005])) is not None
    assert aggregate_era_mix([]) is None
    assert aggregate_era_mix(recs([None, "x", True])) is None


def test_aggregate_boundary_years():
    mix = aggregate_era_mix(recs([1944, 1945, 1990, 1991, 1991]))
    assert mix is not None
    assert mix["pre1945"] == pytest.approx(0.2)   # < 1945
    assert mix["mid"] == pytest.approx(0.4)       # 1945..1990
    assert mix["post1990"] == pytest.approx(0.4)  # > 1990


# ---------------------------------------------------------------------------
# Character overlay labels (no score field).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mix,expected", [
    ({"pre1945": 0.5, "mid": 0.3, "post1990": 0.2}, "puitasum"),
    ({"pre1945": 0.4, "mid": 0.3, "post1990": 0.3}, "puitasum"),
    ({"pre1945": 0.1, "mid": 0.6, "post1990": 0.3}, "paneel"),
    ({"pre1945": 0.1, "mid": 0.3, "post1990": 0.6}, "uusasum"),
    ({"pre1945": 0.2, "mid": 0.4, "post1990": 0.4}, "sega"),
    (None, "ajastumiks teadmata"),
])
def test_character_labels(mix, expected):
    assert era_character(mix) == expected


# ---------------------------------------------------------------------------
# Taste legs: bands + honesty rules pinned.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("share,expected", [
    (0.0, 35), (0.1, 35), (0.11, 50), (0.25, 50),
    (0.26, 60), (0.4, 60), (0.41, 70), (0.9, 70),
])
def test_old_charm_bands_capped(share, expected):
    v, r = dim_old_charm(TALLINN, [mkpoi(pre1945=share)])
    assert v == expected, r
    assert "hinnang" in r and "lakke 70" in r
    assert "pole seisukord" in r  # era != condition


@pytest.mark.parametrize("share,expected", [
    (0.0, 35), (0.15, 35), (0.16, 50), (0.35, 50),
    (0.36, 60), (0.5, 60), (0.51, 70), (0.9, 70),
])
def test_newbuild_bands_capped(share, expected):
    v, r = dim_newbuild(TALLINN, [mkpoi(post1990=share)])
    assert v == expected, r
    assert "hinnang" in r and "lakke 70" in r
    assert "pole seisukord" in r


def test_thin_mix_stays_null_not_single_house_taste():
    for poi in (mkpoi(n=4), mkpoi(n=0)):
        for fn in ALL_FNS:
            v, r = fn(TALLINN, [poi])
            assert v is None, (fn.__name__, poi)
            assert "EI OLE" in r


def test_gate_null_names_the_blocker():
    for fn in ALL_FNS:
        v, r = fn(TALLINN, None)
        assert v is None
        assert "EI OLE" in r and "537" in r


def test_window_boundary():
    assert p4e.MIX_WINDOW_M == 500.0
    far = mkpoi(lat=TALLINN[0], lon=TALLINN[1] + 0.05)  # ~2.9 km
    for fn in ALL_FNS:
        v, r = fn(TALLINN, [far])
        assert v is None, fn.__name__
        assert "EI OLE" in r


def test_dims_ignore_other_kinds_and_garbage():
    for poi in ({"kind": "accident_p4", "lat": 59.4372, "lon": 24.7546},
                mkpoi(pre1945="vana"),
                mkpoi(pre1945=True),
                mkpoi(pre1945=1.5),
                mkpoi(n="palju"),
                mkpoi(n=True),
                {"kind": "eramix_p4", "lat": None, "lon": 24.75}):
        for fn in ALL_FNS:
            v, r = fn(TALLINN, [poi])
            assert v is None, (fn.__name__, poi)
            assert "EI OLE" in r, fn.__name__


def test_all_null_for_missing_inputs():
    for fn in ALL_FNS:
        for origin, pois in [(None, [mkpoi()]), (TALLINN, None),
                             (None, None), (TALLINN, [])]:
            v, r = fn(origin, pois)
            assert v is None, (fn.__name__, origin, pois)
            assert "EI OLE" in r, fn.__name__


def test_honesty_markers():
    scored = [(dim_old_charm, [mkpoi(pre1945=0.5)]),
              (dim_newbuild, [mkpoi(post1990=0.6)])]
    for fn, pois in scored:
        v, r = fn(TALLINN, pois)
        assert v is not None
        assert "hinnang" in r and "EI OLE" not in r, fn.__name__
        assert "garanteeritud" not in r


def test_registry_and_aggregator_cover_both():
    assert [k for k, _, _ in P4_ERA_DIMS] == ["old_charm", "newbuild"]
    assert len({fn for _, _, fn in P4_ERA_DIMS}) == 2
    out = score_p4_era(TALLINN, [mkpoi(pre1945=0.5, post1990=0.1)])
    assert out == {"old_charm": 70, "newbuild": 35}
    assert score_p4_era(None, None) == {
        k: None for k, _, _ in P4_ERA_DIMS}
    assert p4e.P4_ERA_DIMS is P4_ERA_DIMS
