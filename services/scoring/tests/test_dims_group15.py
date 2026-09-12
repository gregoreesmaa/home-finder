"""Hermetic tests for dims_group15.py (issue #116).

No network, no snapshot: hand-made POI lists only. Run:
  python3 -m pytest services/scoring/tests/test_dims_group15.py -q
"""

import math

import dims_group15 as G
from dims_group15 import (
    dim_festival,
    dim_redistrict,
    dim_school_choice,
    dim_stadium,
    dim_water_weed,
    kinds_from_tags,
    score_group15,
)

BALTI = (59.4405, 24.7369)  # (lat, lon)


def mk(kind, dlat_m=0.0, dlon_m=0.0, base=BALTI):
    """POI offset metres north/east of base (equirectangular, Tallinn)."""
    return {"kind": kind, "lat": base[0] + dlat_m / 110570.0,
            "lon": base[1] + dlon_m / 57290.0}


def test_none_only_when_missing():
    for fn in (dim_school_choice, dim_redistrict, dim_water_weed,
               dim_festival, dim_stadium):
        s, _ = fn(None, [])
        assert s is None
        s, _ = fn(BALTI, None)
        assert s is None


def test_reasons_are_estonian_proxies():
    _, r = dim_school_choice(BALTI, [mk("school", 100)])
    assert "proksi" in r and "OSM" in r
    _, r = dim_redistrict(BALTI, [mk("school", 100)])
    assert "proksi" in r
    _, r = dim_water_weed(BALTI, [mk("water", 100)])
    assert "hooldusinfo OSM-is puudub" in r
    _, r = dim_festival(BALTI, [mk("venue", 100)])
    assert "proksi" in r
    _, r = dim_stadium(BALTI, [mk("stadium", 100)])
    assert "proksi" in r
    # Never presented as official lottery odds.
    for fn, pois in ((dim_school_choice, [mk("school")]),
                     (dim_redistrict, [mk("school")])):
        _, r = fn(BALTI, pois)
        assert "loosi" not in r.lower() or "proksi" in r


def test_choice_saturates_on_count():
    assert dim_school_choice(BALTI, [])[0] == 0  # absence is evidence
    one = dim_school_choice(BALTI, [mk("school", 200)])[0]
    assert one == round(100 * 1 / 7)
    many = dim_school_choice(
        BALTI, [mk("school", 100 * i, 50 * i) for i in range(12)])[0]
    assert many == round(100 * 12 / 18)
    assert 0 <= one < many <= 100


def test_dedupe_collapses_node_way_dupes():
    dupes = [mk("school", 200), dict(mk("school", 200))]
    single = dim_school_choice(BALTI, [mk("school", 200)])[0]
    assert dim_school_choice(BALTI, dupes)[0] == single
    # ...but two genuinely distinct schools both count.
    two = dim_school_choice(BALTI, [mk("school", 200), mk("school", 210)])[0]
    assert two == round(100 * 2 / 8)


def test_depend_radius_wider_than_choice():
    # One school at 1700 m: inside the 2 km dependency window only.
    pois = [mk("school", 1700)]
    assert dim_school_choice(BALTI, pois)[0] == 0
    assert dim_redistrict(BALTI, pois)[0] == round(100 * 1 / 3)


def test_redistrict_sparse_end_discriminates():
    assert dim_redistrict(BALTI, [])[0] == 0
    s1 = dim_redistrict(BALTI, [mk("school", 300)])[0]
    s3 = dim_redistrict(
        BALTI, [mk("school", 300), mk("school", 900), mk("school", 1500)])[0]
    assert (s1, s3) == (round(100 / 3), round(100 * 3 / 5))


def test_water_amenity_decays():
    assert dim_water_weed(BALTI, [])[0] == 0
    near = dim_water_weed(BALTI, [mk("water", 100)])[0]
    assert near == round(100 * 600 / 700)
    far = dim_water_weed(BALTI, [mk("water", 5000)])[0]
    assert far == round(100 * 600 / 5600)
    assert far < near


def test_festival_inverted():
    # Near venue = disruption = LOW score (red); far = calm = HIGH (green).
    assert dim_festival(BALTI, [])[0] == 100
    near = dim_festival(BALTI, [mk("venue", 219)])[0]
    assert near in (30, 31)  # nominal 219 m reads ~220 m measured
    far = dim_festival(BALTI, [mk("venue", 5000)])[0]
    assert far > near


def test_stadium_inverted():
    assert dim_stadium(BALTI, [])[0] == 100
    near = dim_stadium(BALTI, [mk("stadium", 306)])[0]
    assert near == round(100 * 306 / 1106)
    assert dim_stadium(BALTI, [mk("stadium", 3730)])[0] > near


def test_kinds_from_tags():
    assert kinds_from_tags({"leisure": "stadium"}) == "stadium"
    assert kinds_from_tags({"leisure": "pitch"}) is None  # pitches excluded
    assert kinds_from_tags({"amenity": "events_venue"}) == "venue"
    assert kinds_from_tags({"amenity": "marketplace"}) == "venue"
    assert kinds_from_tags({"tourism": "attraction"}) == "venue"
    # Sibling batch B1 tags stay unclaimed (disjoint layers).
    assert kinds_from_tags({"amenity": "theatre"}) is None
    assert kinds_from_tags({"tourism": "museum"}) is None
    assert kinds_from_tags({"amenity": "community_centre"}) is None
    assert kinds_from_tags({}) is None


def test_fragment_documents_snapshot_tags():
    frag = G.GROUP15_OVERPASS_FRAGMENT
    assert "stadium" in frag and "events_venue" in frag
    assert "marketplace" in frag and "attraction" in frag
    assert "theatre" not in frag  # p89 culture's tag, not ours


def test_registry_and_entry_point():
    assert [p for _, p, _ in G.GROUP15_DIMS] == [
        "p130", "p314", "p338", "p442", "p462"]
    out = score_group15(BALTI, [mk("school", 200), mk("stadium", 3000)])
    assert set(out) == {"school_choice", "redistrict", "water_weed",
                        "festival", "stadium"}
    assert all(v is None or 0 <= v <= 100 for v in out.values())
    assert out["school_choice"] == dim_school_choice(
        BALTI, [mk("school", 200), mk("stadium", 3000)])[0]
    assert score_group15(None, None) == {k: None for k in out}


def test_calibration_constants():
    assert (G.CHOICE_RADIUS_M, G.CHOICE_HALF) == (1500.0, 6.0)
    assert (G.DEPEND_RADIUS_M, G.DEPEND_HALF) == (2000.0, 2.0)
    assert G.WATER_HALF_M == 600.0
    assert G.VENUE_HALF_M == 500.0
    assert G.STADIUM_HALF_M == 800.0
