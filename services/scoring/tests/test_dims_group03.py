"""Hermetic unit tests for Group 3 cadastre-A dims (issue #151).

No network, no snapshot: all POIs are synthetic. Run from repo root:
  python3 -m pytest services/scoring/tests/test_dims_group03.py -q
"""

import dims_group03 as G
from dims_group03 import (
    dim_boundary_clarity,
    dim_drainage,
    dim_easements,
    dim_lot_size,
    dim_soil_stability,
    kinds_from_tags,
    score_group03,
)

TALLINN = (59.4372, 24.7536)  # city centre reference origin


def poi(kind, metres_north, lon_off=0.0):
    """Synthetic POI `metres_north` metres north of TALLINN."""
    return {"kind": kind, "lat": TALLINN[0] + metres_north / 111320.0,
            "lon": TALLINN[1] + lon_off}


def test_none_when_missing():
    for fn in (dim_drainage, dim_soil_stability, dim_easements,
               dim_boundary_clarity):
        assert fn(None, [])[0] is None
        assert fn(TALLINN, None)[0] is None
        assert fn(None, None)[0] is None
    # Lot size keys off the listing record, not the map.
    assert dim_lot_size(TALLINN, [])[0] is None
    assert dim_lot_size(TALLINN, [], lot_m2=None)[0] is None
    assert dim_lot_size(TALLINN, [], lot_m2=0)[0] is None
    assert dim_lot_size(TALLINN, [], lot_m2=-5)[0] is None


def test_drainage_bands_track_half_300():
    assert dim_drainage(TALLINN, [poi("open_water", 50)])[0] == 25
    assert dim_drainage(TALLINN, [poi("open_water", 250)])[0] == 50
    assert dim_drainage(TALLINN, [poi("open_water", 500)])[0] == 67
    assert dim_drainage(TALLINN, [poi("open_water", 1000)])[0] == 80
    # Empty POI list: no mapped water within the fetch window -> dry.
    assert dim_drainage(TALLINN, [])[0] == 85


def test_drainage_reason_is_honest_proxy():
    _, reason = dim_drainage(TALLINN, [poi("open_water", 250)])
    assert "drenaažiproksi" in reason.lower()
    assert "hinnang" in reason
    for bad in ("meetrit kõrgust", "vooluhulk", "üleujutustsoon"):
        assert bad not in reason


def test_kinds_from_tags():
    assert kinds_from_tags({"natural": "water"}) == "open_water"
    assert kinds_from_tags({"natural": "wetland"}) == "open_water"
    assert kinds_from_tags({"natural": "coastline"}) == "open_water"
    assert kinds_from_tags({"waterway": "river"}) == "open_water"
    assert kinds_from_tags({"waterway": "ditch"}) == "open_water"
    assert kinds_from_tags({"natural": "scrub"}) is None
    assert kinds_from_tags({"amenity": "bar"}) is None


def test_lot_size_bands():
    assert dim_lot_size(TALLINN, [], lot_m2=200)[0] == 45
    assert dim_lot_size(TALLINN, [], lot_m2=600)[0] == 65
    assert dim_lot_size(TALLINN, [], lot_m2=1000)[0] == 80
    assert dim_lot_size(TALLINN, [], lot_m2=5000)[0] == 80
    _, reason = dim_lot_size(TALLINN, [], lot_m2=600)
    assert "600" in reason and "m²" in reason


def test_registry_nulls_stay_null_with_checks():
    for fn, needle in ((dim_soil_stability, "geoloogiauuringut"),
                       (dim_easements, "õigusauditis"),
                       (dim_boundary_clarity, "piirimärke")):
        v, reason = fn(TALLINN, [])
        assert v is None
        assert needle in reason


def test_score_group03_registry():
    dims, reasons = score_group03(TALLINN, [poi("open_water", 500)])
    assert set(dims) == {"lot_size", "drainage", "soil_stability",
                         "easements", "boundary_clarity"}
    assert dims["drainage"] == 67
    # Listing record absent -> lot stays None; registry NULLs stay None.
    assert dims["lot_size"] is None
    assert dims["soil_stability"] is None
    assert dims["easements"] is None
    assert dims["boundary_clarity"] is None
    assert any("Drenaažiproksi" in r for r in reasons)
    assert G.GROUP03_PARAM_IDS == {"lot_size": 29, "drainage": 50,
                                   "soil_stability": 68, "easements": 71,
                                   "boundary_clarity": 75}
