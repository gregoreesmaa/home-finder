"""Hermetic tests for scripts/build/batch_density.py (issue #622).

No network, no snapshot files: inline GeoJSON fixtures only.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_density import (  # noqa: E402
    VINTAGE,
    build_sidecar,
    density_class,
    main,
    square_record,
)


def feature(zone_id, value, ring=None):
    ring = ring or [[[24.27, 58.94], [24.27, 58.96], [24.30, 58.96],
                     [24.30, 58.94], [24.27, 58.94]]]
    return {
        "type": "Feature",
        "properties": {
            "inspireid_identifier_localid": zone_id,
            "value_statisticalvalue_value": value,
            "periodofreference_xlink_title": "1.1.2024 - 31.12.2024",
        },
        "geometry": {"type": "Polygon", "coordinates": ring},
    }


def test_density_class_bins_and_edges():
    assert density_class(None) == -1
    assert density_class("x") == -1
    assert density_class(float("nan")) == -1
    # 0 covers empty AND privacy-masked (<4): the feed never
    # distinguishes them, so neither do we (never "empty").
    assert density_class(0) == 0
    assert density_class(3) == 1
    assert density_class(9.9) == 1
    assert density_class(10) == 2
    assert density_class(99.9) == 2
    assert density_class(100) == 3
    assert density_class(999.9) == 3
    assert density_class(1000) == 4
    assert density_class(4999.9) == 4
    assert density_class(5000) == 5
    assert density_class(16231) == 5


def test_square_record_keeps_quad():
    row = square_record(feature("S-1", 1781))
    assert row["zone_id"] == "S-1"
    assert row["value"] == 1781
    assert row["cls"] == 4
    assert row["b"] == [24.27, 58.94, 24.3, 58.96]
    assert len(row["r"]) == 1 and len(row["r"][0]) == 5


def test_square_record_drops_gracefully():
    assert square_record(feature("S-2", None)) is None
    assert square_record(feature("S-3", "nope")) is None
    assert square_record({"type": "Feature"}) is None
    assert square_record(feature("S-4", 5, ring=[[["x"]]])) is None
    assert square_record("junk") is None


def test_sidecar_shape():
    doc = build_sidecar([{"zone_id": "S-1", "value": 5, "cls": 1,
                           "b": [0, 0, 1, 1], "r": []}],
                        {"squares": 1, "vintage": VINTAGE})
    assert doc["vintage"] == "2024"
    assert "CC0" in doc["source"]
    assert doc["stats"]["squares"] == 1
    assert len(doc["areas"]) == 1


def test_main_counts_and_drops(tmp_path):
    src = str(tmp_path / "pd.json")
    with open(src, "w", encoding="utf-8") as fh:
        json.dump({"features": [feature("S-1", 5), feature("S-2", 0),
                                {"broken": True}]}, fh)
    rc = main(["--json", src, "--snap", str(tmp_path / "snap")])
    assert rc == 0
    doc = json.load(open(str(tmp_path / "snap" / "density" / "density-areas.json")))
    assert doc["stats"]["squares"] == 2
    assert doc["stats"]["dropped"] == 1
    assert doc["stats"]["bands"] == [1, 1, 0, 0, 0, 0]


def test_missing_input_writes_nothing(tmp_path, capsys):
    rc = main(["--json", str(tmp_path / "nope.json"), "--snap", str(tmp_path / "snap")])
    assert rc == 1
    assert not os.path.exists(str(tmp_path / "snap" / "density" / "density-areas.json"))
    assert "NOTHING" in capsys.readouterr().out
