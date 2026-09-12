"""Hermetic unit tests for Group 9b environmental-exposure dims (issue #124).

No network, no snapshot: all POIs are synthetic. Run from repo root:
  python3 -m pytest services/scoring/tests/test_dims_group09b.py -q
"""

import dims_group09b as G
from dims_group09b import (
    dim_flightcorr,
    dim_lowspec,
    dim_vibration,
    kinds_from_tags,
    score_group09b,
)

TALLINN = (59.4372, 24.7536)  # city centre reference origin


def poi(kind, metres_north, lon_off=0.0):
    """Synthetic POI `metres_north` metres north of TALLINN."""
    return {"kind": kind, "lat": TALLINN[0] + metres_north / 111320.0,
            "lon": TALLINN[1] + lon_off}


def test_none_when_missing():
    for fn in (dim_vibration, dim_lowspec, dim_flightcorr):
        assert fn(None, [])[0] is None
        assert fn(TALLINN, None)[0] is None
        assert fn(None, None)[0] is None
    dims, reasons = score_group09b(None, None)
    assert set(dims) == {"vibration", "lowspec", "flightcorr"}
    assert all(v is None for v in dims.values())
    assert reasons == []


def test_reasons_honest():
    # Every reason says proksi/(hinnang); dB/dBA nowhere, magnitudes nowhere.
    _, reasons = score_group09b(TALLINN, [poi("vibra_rail", 100),
                                          poi("heavy_road", 100),
                                          poi("runway", 100)])
    assert len(reasons) == 3
    for r in reasons:
        assert "proksi" in r
        assert "(hinnang" in r
        assert "dB" not in r
    for fn in (dim_vibration, dim_lowspec, dim_flightcorr):
        assert "proksi" in fn(None, None)[1]


def test_vibration_bands():
    assert dim_vibration(TALLINN, [poi("vibra_rail", 100)])[0] == 30
    assert dim_vibration(TALLINN, [poi("vibra_rail", 300)])[0] == 50
    assert dim_vibration(TALLINN, [poi("vibra_rail", 500)])[0] == 70
    # Heavy-truck routes vibrate too; tram shares the rail kind.
    assert dim_vibration(TALLINN, [poi("heavy_road", 100)])[0] == 30
    # Industry hum is airborne, not ground vibration: excluded.
    assert dim_vibration(TALLINN, [poi("industrial09b", 100)])[0] == 85
    # Empty window -> calm.
    assert dim_vibration(TALLINN, [])[0] == 85


def test_lowspec_bands():
    assert dim_lowspec(TALLINN, [poi("heavy_road", 100)])[0] == 33
    assert dim_lowspec(TALLINN, [poi("heavy_road", 500)])[0] == 50
    assert dim_lowspec(TALLINN, [poi("heavy_road", 900)])[0] == 67
    # Rail and industry rumble too (this is the wider set vs p234).
    assert dim_lowspec(TALLINN, [poi("vibra_rail", 100)])[0] == 33
    assert dim_lowspec(TALLINN, [poi("industrial09b", 100)])[0] == 33
    assert dim_lowspec(TALLINN, [])[0] == 90


def test_flightcorr_bands():
    assert dim_flightcorr(TALLINN, [poi("runway", 500)])[0] == 33
    assert dim_flightcorr(TALLINN, [poi("runway", 1500)])[0] == 50
    assert dim_flightcorr(TALLINN, [poi("runway", 3000)])[0] == 75
    assert dim_flightcorr(TALLINN, [poi("airfield", 500)])[0] == 33
    # No runway in the 8 km window -> outside the corridor.
    assert dim_flightcorr(TALLINN, [])[0] == 95
    s, reason = dim_flightcorr(TALLINN, [poi("runway", 500)])
    assert s == 33
    assert "hooajalisus teadmata" in reason


def test_kinds_from_tags():
    assert kinds_from_tags({"highway": "motorway"}) == "heavy_road"
    assert kinds_from_tags({"highway": "trunk"}) == "heavy_road"
    assert kinds_from_tags({"highway": "primary"}) == "heavy_road"
    # Secondary/tertiary are local distributors, not heavy corridors.
    assert kinds_from_tags({"highway": "secondary"}) is None
    assert kinds_from_tags({"highway": "residential"}) is None
    assert kinds_from_tags({"railway": "rail"}) == "vibra_rail"
    assert kinds_from_tags({"railway": "tram"}) == "vibra_rail"
    assert kinds_from_tags({"aeroway": "runway"}) == "runway"
    assert kinds_from_tags({"aeroway": "aerodrome"}) == "airfield"
    assert kinds_from_tags({"landuse": "industrial"}) == "industrial09b"
    assert kinds_from_tags({"amenity": "bar"}) is None


def test_param_ids():
    assert G.GROUP09B_PARAM_IDS == {"vibration": 234, "lowspec": 408,
                                   "flightcorr": 445}
    assert set(G.GROUP09B_DIMS) == set(G.GROUP09B_PARAM_IDS)


def test_fragment_uses_nwr():
    # PR #118: carriageways/runways are way-mapped; node-only would drop them.
    assert "nwr[\"highway\"" in G.GROUP09B_OVERPASS_FRAGMENT
    assert "nwr[\"railway\"" in G.GROUP09B_OVERPASS_FRAGMENT
    assert "nwr[\"aeroway\"" in G.GROUP09B_OVERPASS_FRAGMENT
    assert "nwr[\"landuse\"" in G.GROUP09B_OVERPASS_FRAGMENT
    for line in G.GROUP09B_OVERPASS_FRAGMENT.strip().splitlines():
        assert line.strip().startswith("nwr["), line
