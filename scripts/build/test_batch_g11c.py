"""Hermetic tests for batch G11C (Group 11 leftovers A, issue #134).

No network, no snapshot reads: predicates run on inline tag dicts, the
p88 stop gate runs on inline coords, forest centroids run on inline
polygons, counts are locked from the verified 2026-09-12 snapshot sweep
(see builder docstring), scoring math mirrors walk_raster.saturate
exactly. Run:
python3 -m pytest scripts/build/test_batch_g11c.py -q
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from batch_g11c_amenity import (  # noqa: E402
    LAYER_DEFAULTS,
    PREDS,
    SCHOOLBUS_GATE_KM,
    is_forage_tags,
    is_medspecial,
    is_recspecial,
    is_school,
    is_stop,
    is_worship,
    read_forest_points,
    resolve_schoolbus,
)

from walk_raster import saturate  # noqa: E402

# Verified 2026-09-12 snapshot counts (harju-amenities.geojson sweep via
# resolve_with_tags, plus the PBF forest export via read_forest_points:
# schoolbus loses 5 stop-less rural schools to the gate).
SNAPSHOT_COUNTS = {
    "schoolbus": 337,
    "recspecial": 523,
    "medspecial": 120,
    "worship": 241,
    "forage": 19473,
}

POSITIVES = {
    "recspecial": [
        {"leisure": "sports_centre"},
        {"leisure": "sports_hall"},
        {"leisure": "stadium"},
        {"leisure": "swimming_pool"},
        {"leisure": "water_park"},
        {"leisure": "ice_rink"},
        {"leisure": "golf_course"},
        {"leisure": "fitness_centre"},
    ],
    "medspecial": [{"amenity": "hospital"}, {"amenity": "dentist"}],
    "worship": [{"amenity": "place_of_worship"}, {"amenity": "monastery"}],
}

NEGATIVES = [
    {"leisure": "park"},  # generic green stays in p19
    {"leisure": "playground"},
    {"leisure": "pitch"},  # plain pitches are not specialised venues
    {"amenity": "pharmacy"},  # GP-level care stays in p20
    {"amenity": "doctors"},
    {"amenity": "school"},
    {"amenity": "restaurant"},
    {"tourism": "museum"},
    {"landuse": "meadow"},
    {"natural": "water"},
    {},
    None,
]


def _feature(props, geom=None):
    return {
        "type": "Feature",
        "properties": props,
        "geometry": geom or {"type": "Point", "coordinates": [24.75, 59.43]},
    }


def test_predicates_accept_their_tier_only():
    for layer, tags_list in POSITIVES.items():
        for tags in tags_list:
            assert PREDS[layer](tags), (layer, tags)
    for tags in NEGATIVES:
        for layer in PREDS:
            assert not PREDS[layer](tags), (layer, tags)


def test_school_gate_uses_schools_not_kindergartens():
    assert is_school({"amenity": "school"})
    assert not is_school({"amenity": "kindergarten"})
    assert not is_school({"amenity": "university"})
    assert not is_school(None)


def test_stop_predicate_covers_bus_tram_train():
    assert is_stop({"highway": "bus_stop"})
    assert is_stop({"public_transport": "platform"})
    assert is_stop({"public_transport": "stop_position"})
    assert is_stop({"railway": "tram_stop"})
    assert not is_stop({"amenity": "school"})
    assert not is_stop({"highway": "traffic_signals"})


def test_schoolbus_gate_keeps_stop_served_schools_only(tmp_path):
    # Two schools; only the first has a stop within 500 m.
    lines = [
        _feature({"amenity": "school"}, {"type": "Point", "coordinates": [24.7500, 59.4300]}),
        _feature({"amenity": "school"}, {"type": "Point", "coordinates": [24.7600, 59.4300]}),
        _feature({"highway": "bus_stop"}, {"type": "Point", "coordinates": [24.7505, 59.4300]}),
        # A far-away stop must not rescue the second school (> 500 m).
        _feature({"highway": "bus_stop"}, {"type": "Point", "coordinates": [25.0000, 59.4300]}),
    ]
    poi = tmp_path / "amen.geojson"
    poi.write_text("\n".join(json.dumps(f) for f in lines), encoding="utf-8")
    gated, stats = resolve_schoolbus(str(poi))
    assert stats["schools"] == 2
    assert stats["stops"] == 2
    assert len(gated) == 1
    assert abs(gated[0][0] - 24.7500) < 1e-9
    assert SCHOOLBUS_GATE_KM == 0.5


def test_forage_reader_centroids_polygons_and_dedupes(tmp_path):
    poly = {
        "type": "Polygon",
        "coordinates": [[[24.0, 59.0], [24.01, 59.0], [24.01, 59.01], [24.0, 59.01], [24.0, 59.0]]],
    }
    lines = [
        _feature({"landuse": "forest"}, poly),
        _feature({"landuse": "forest"}, poly),  # twin export reads once
        _feature({"natural": "wood"}, {"type": "Point", "coordinates": [24.5, 59.4]}),
        _feature({"natural": "water"}, poly),  # not forage
    ]
    src = tmp_path / "forest.geojson"
    src.write_text("\n".join(json.dumps(f) for f in lines), encoding="utf-8")
    pts, stats = read_forest_points(str(src))
    assert stats["features"] == 4
    assert len(pts) == 2
    assert is_forage_tags({"landuse": "forest"})
    assert is_forage_tags({"natural": "scrub"})
    assert is_forage_tags({"natural": "heath"})
    assert not is_forage_tags({"natural": "water"})
    assert not is_forage_tags({"landuse": "farmland"})  # no access-right signal


def test_snapshot_counts_documented():
    assert set(SNAPSHOT_COUNTS) == set(LAYER_DEFAULTS)
    assert all(n > 0 for n in SNAPSHOT_COUNTS.values())
    assert sum(SNAPSHOT_COUNTS.values()) == 337 + 523 + 120 + 241 + 19473


def test_sigmas_follow_trip_rarely_scale():
    assert LAYER_DEFAULTS["schoolbus"]["sigma"] == 0.5
    assert LAYER_DEFAULTS["recspecial"]["sigma"] == 0.8
    assert LAYER_DEFAULTS["medspecial"]["sigma"] == 0.8
    assert LAYER_DEFAULTS["worship"]["sigma"] == 0.8
    assert LAYER_DEFAULTS["forage"]["sigma"] == 0.5


def test_halves_match_ts_bonus_spec():
    # Locked with G11C_BONUS in apps/web/lib/layers_group11c.ts; the
    # server rejects rasters built with different numbers.
    ts_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "..",
        "apps",
        "web",
        "lib",
        "layers_group11c.ts",
    )
    src = open(ts_path, encoding="utf-8").read()
    for layer, defs in LAYER_DEFAULTS.items():
        half = defs["half"]
        assert half > 0
        assert ("half: %s" % json.dumps(half)) in src, layer


def test_anchor_scores_read_sensibly():
    # Unweighted-count semantics (as grocery half=6, where one adjacent
    # feature reads ~14): singletons stay low so lone features never blob
    # districts green; real clusters read green. Forage runs a denser
    # centroid field, so its bands sit higher (S~10 is wooded fringe,
    # S~50 deep forest).
    for layer, defs in LAYER_DEFAULTS.items():
        half = defs["half"]
        assert saturate(half, half) == 50, layer
        assert saturate(1.0, half) < 30, layer
    for layer in ("schoolbus", "recspecial", "medspecial", "worship"):
        half = LAYER_DEFAULTS[layer]["half"]
        assert saturate(10.0, half) >= 55, layer
        assert saturate(0.05, half) < 15, layer
    assert saturate(10.0, LAYER_DEFAULTS["forage"]["half"]) < 55
    assert saturate(50.0, LAYER_DEFAULTS["forage"]["half"]) >= 55


def test_medical_tier_excludes_gp_level():
    assert is_medspecial({"amenity": "hospital"})
    assert is_medspecial({"amenity": "dentist"})
    assert not is_medspecial({"amenity": "pharmacy", "healthcare": "dentist"})
    assert is_recspecial({"leisure": "stadium"})
    assert not is_recspecial({"leisure": "park"})
    assert is_worship({"amenity": "place_of_worship", "religion": "christian"})
    assert is_worship({"amenity": "monastery"})
