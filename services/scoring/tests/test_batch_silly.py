"""Tests for scripts/build/batch_silly.py (issue #774, option A).

Hermetic: inline GeoJSON fixtures only — never the 123 MB held
extract, no network. Pins the tag->layer mapping for all twelve
silly layers, centroid extraction (points direct, polygons/lines via
bbox centre), the servable sidecar shape (points carry lat/lon/slice
only), and the CLI end-to-end (fixture GeoJSON in, sidecar JSON out).
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_silly import (  # noqa: E402
    build_sidecar,
    classify_tags,
    extract_points_geojson,
    main,
)

TAGS_BY_LAYER = {
    "kirikukellad": {"amenity": "place_of_worship"},
    "kajakad": {"landuse": "harbour"},
    "manguvaljakud": {"leisure": "playground"},
    "koertepargid": {"leisure": "dog_park"},
    "saunad": {"leisure": "sauna"},
    "talisuplus": {"leisure": "swimming_area"},
    "tanavasport": {"leisure": "fitness_station"},
    "vesi": {"amenity": "fountain"},
    "wc": {"amenity": "toilets"},
    "aed": {"emergency": "defibrillator"},
    "raamatukapid": {"amenity": "public_bookcase"},
    "kalmistu": {"landuse": "cemetery"},
}

FIXTURE_DOC = {
    "type": "FeatureCollection",
    "features": [
        # Node church -> direct point.
        {"type": "Feature",
         "geometry": {"type": "Point", "coordinates": [24.71339, 59.43763]},
         "properties": {"amenity": "place_of_worship"}},
        # Playground polygon -> bbox-centre centroid.
        {"type": "Feature",
         "geometry": {"type": "Polygon",
                      "coordinates": [[[24.69, 59.44], [24.70, 59.44],
                                       [24.70, 59.45], [24.69, 59.45],
                                       [24.69, 59.44]]]},
         "properties": {"leisure": "playground"}},
        # Dual-tagged swim spot -> ONE point (never double markers).
        {"type": "Feature",
         "geometry": {"type": "Point", "coordinates": [24.9348, 59.43103]},
         "properties": {"leisure": "swimming_area",
                        "sport": "swimming"}},
        # Untagged export artefact -> skipped (never a fake point).
        {"type": "Feature",
         "geometry": {"type": "Point", "coordinates": [24.75, 59.44]},
         "properties": {}},
        # Unmapped bench -> skipped.
        {"type": "Feature",
         "geometry": {"type": "Point", "coordinates": [24.0, 59.0]},
         "properties": {"amenity": "bench"}},
    ],
}


def test_classify_tags_covers_all_twelve_layers():
    assert len(TAGS_BY_LAYER) == 12
    for layer, tags in TAGS_BY_LAYER.items():
        assert classify_tags(tags) == layer, layer
    # Multi-tag layers accept every documented vocabulary value.
    assert classify_tags({"amenity": "marketplace"}) == "kajakad"
    assert classify_tags({"landuse": "landfill"}) == "kajakad"
    assert classify_tags({"sport": "swimming"}) == "talisuplus"
    assert classify_tags({"sport": "skateboard"}) == "tanavasport"
    assert classify_tags({"sport": "disc_golf"}) == "tanavasport"
    assert classify_tags({"amenity": "drinking_water"}) == "vesi"


def test_classify_tags_skips_unmapped():
    assert classify_tags({"amenity": "bench"}) is None
    assert classify_tags({}) is None


def test_extract_points_geojson_centroids_and_dedup():
    points = extract_points_geojson(FIXTURE_DOC)
    assert len(points) == 3
    by_slice = {p["slice"]: p for p in points}
    assert by_slice["kirikukellad"] == {"lat": 59.43763, "lon": 24.71339,
                                        "slice": "kirikukellad"}
    # Polygon centroid, not a corner.
    assert by_slice["manguvaljakud"] == {"lat": 59.445, "lon": 24.695,
                                         "slice": "manguvaljakud"}
    assert by_slice["talisuplus"]["slice"] == "talisuplus"


def test_build_sidecar_shape_and_counts():
    doc = build_sidecar(extract_points_geojson(FIXTURE_DOC),
                        vintage="2026-09-14", source="fixture (test only)")
    assert doc["vintage"] == "2026-09-14"
    assert [k for k in doc["points"][0].keys()] == ["lat", "lon", "slice"]
    assert doc["counts"]["total"] == 3
    assert doc["counts"]["by_layer"]["talisuplus"] == 1


def test_main_fixture_geojson_to_sidecar(tmp_path):
    src = tmp_path / "filtered.geojson"
    src.write_text(json.dumps(FIXTURE_DOC), encoding="utf-8")
    out = tmp_path / "silly-points.json"
    rc = main(["--extract", str(src), "--out", str(out),
               "--vintage", "2026-09-14"])
    assert rc == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["counts"]["total"] == 3
    assert {p["slice"] for p in doc["points"]} == {
        "kirikukellad", "manguvaljakud", "talisuplus"}


def test_main_refuses_missing_extract(tmp_path):
    rc = main(["--extract", str(tmp_path / "nope.geojson"),
               "--out", str(tmp_path / "out.json")])
    assert rc != 0
    assert not (tmp_path / "out.json").exists()
