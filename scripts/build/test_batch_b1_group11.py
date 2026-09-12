"""Hermetic tests for batch B1 (Group 11 amenity layers, issue #98).

No network, no snapshot reads: predicates run on inline tag dicts, counts
are locked from the verified 2026-09-12 snapshot sweep (see builder
docstring), scoring math mirrors walk_raster.saturate exactly. Run:
python3 -m pytest scripts/build/test_batch_b1_group11.py -q
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from batch_b1_group11 import (  # noqa: E402
    LAYER_DEFAULTS,
    PREDS,
    is_community,
    is_culture,
    is_library,
    is_nightlife,
    is_pets,
)

from walk_raster import saturate  # noqa: E402

# Verified 2026-09-12 snapshot counts (harju-amenities.geojson sweep).
# Verified 2026-09-12 snapshot counts (harju-amenities.geojson sweep via
# resolve_with_tags: community loses the double-tagged Teachers' House to
# culture, so 238 not 239).
SNAPSHOT_COUNTS = {
    "pets": 229,
    "community": 238,
    "culture": 259,
    "nightlife": 283,
    "libraries": 86,
}

POSITIVES = {
    "pets": [{"leisure": "dog_park"}, {"amenity": "veterinary"}, {"shop": "pet"}],
    "community": [
        {"amenity": "community_centre"},
        {"amenity": "social_facility"},
        {"amenity": "townhall"},
    ],
    "culture": [
        {"amenity": "arts_centre"},
        {"amenity": "theatre"},
        {"amenity": "studio"},
        {"tourism": "museum"},
        {"tourism": "gallery"},
        # Double-tagged Teachers' House reads as culture, not community.
        {"amenity": "community_centre", "tourism": "museum"},
    ],
    "nightlife": [
        {"amenity": "bar"},
        {"amenity": "pub"},
        {"amenity": "nightclub"},
        {"amenity": "cinema"},
        {"amenity": "casino"},
    ],
    "libraries": [{"amenity": "library"}, {"amenity": "public_bookcase"}],
}

NEGATIVES = [
    {},
    {"amenity": "school"},
    {"amenity": "restaurant"},
    {"amenity": "pharmacy"},
    {"shop": "supermarket"},
    {"leisure": "park"},
    {"tourism": "hotel"},
    {"amenity": "hospital"},
    {"amenity": "events_venue"},  # p462 territory (batch B10), never ours
    {"leisure": "stadium"},
    {"amenity": "festival_grounds"},  # p442 territory, never ours
    {"amenity": "music_school"},  # education catchments, never ours
]


def test_predicates_accept_their_tags():
    for layer, tags_list in POSITIVES.items():
        for tags in tags_list:
            assert PREDS[layer](tags), (layer, tags)


def test_predicates_reject_everything_else():
    for layer, pred in PREDS.items():
        for tags in NEGATIVES:
            assert not pred(tags), (layer, tags)


def test_predicates_reject_garbage():
    for pred in PREDS.values():
        assert not pred(None)
        assert not pred("amenity=bar")
        assert not pred({"amenity": 42})


def test_layers_are_pairwise_disjoint():
    corpus = [t for tags in POSITIVES.values() for t in tags] + NEGATIVES
    for tags in corpus:
        hits = [layer for layer, pred in PREDS.items() if pred(tags)]
        assert len(hits) <= 1, (tags, hits)


def test_teachers_house_reads_culture_not_community():
    tags = {"amenity": "community_centre", "tourism": "museum"}
    assert is_culture(tags)
    assert not is_community(tags)


def test_is_helpers_match_registry():
    assert PREDS["pets"] is is_pets
    assert PREDS["community"] is is_community
    assert PREDS["culture"] is is_culture
    assert PREDS["nightlife"] is is_nightlife
    assert PREDS["libraries"] is is_library


def test_snapshot_counts_documented():
    # Every counted feature exists in the snapshot (no faked tags); the
    # builder sweep produced exactly these totals.
    assert set(SNAPSHOT_COUNTS) == set(PREDS)
    assert all(n > 0 for n in SNAPSHOT_COUNTS.values())
    assert sum(SNAPSHOT_COUNTS.values()) == 229 + 238 + 259 + 283 + 86


def test_sigmas_follow_trip_rarely_scale():
    assert LAYER_DEFAULTS["pets"]["sigma"] == 0.5
    assert LAYER_DEFAULTS["community"]["sigma"] == 0.5
    assert LAYER_DEFAULTS["culture"]["sigma"] == 0.8
    assert LAYER_DEFAULTS["nightlife"]["sigma"] == 0.8
    assert LAYER_DEFAULTS["libraries"]["sigma"] == 0.8


def test_halves_match_ts_bonus_spec():
    # Locked with bonusSpecFor() in apps/web/lib/layers_batch1.ts; the
    # server rejects rasters built with different numbers.
    import json as _json

    ts_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "..",
        "apps",
        "web",
        "lib",
        "layers_batch1.ts",
    )
    src = open(ts_path, encoding="utf-8").read()
    for layer, defs in LAYER_DEFAULTS.items():
        half = defs["half"]
        assert half > 0
        assert ("half: %s" % _json.dumps(half)) in src, layer


def test_anchor_scores_read_sensibly():
    # House unweighted-count semantics (as grocery half=6, where one
    # adjacent store reads ~14): singletons stay low so lone features never
    # blob districts green; real clusters (S~10, Old Town scale) read green;
    # thin traces stay deep red.
    for layer, defs in LAYER_DEFAULTS.items():
        half = defs["half"]
        assert saturate(half, half) == 50, layer
        assert saturate(1.0, half) < 30, layer
        assert saturate(10.0, half) >= 55, layer
        assert saturate(0.05, half) < 15, layer
