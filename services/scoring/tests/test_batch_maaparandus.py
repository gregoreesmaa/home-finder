"""Hermetic tests for scripts/build/batch_maaparandus.py (issue #616).

Covers ONLY the pure sidecar projection — the WFS harvest is a polite
one-off (custom UA, paced, /tmp-only) and is never called here
(AGENTS.md section 7.6). Scorer math is pinned in
test_dims_p4_maaparandus.py (reused, never re-tested here).
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_maaparandus import (  # noqa: E402
    build_sidecar,
    parse_outflow_collection,
    parse_polygon_collection,
    to_sidecar,
)

VORK_GEOJSON = json.dumps({
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature",
         "properties": {"ms_kood": "5111040011290", "ehitise_nimi": "Allika5",
                        "ms_url": "https://portaal.agri.ee/avalik/#/maaparandus/systeem/5111040011290"},
         "geometry": {"type": "Polygon", "coordinates": [[
             [24.74, 59.43], [24.75, 59.43], [24.75, 59.44],
             [24.74, 59.44], [24.74, 59.43]]]}},
        {"type": "Feature",
         "properties": {"ms_kood": "x"},
         "geometry": {"type": "Point", "coordinates": [24.74, 59.43]}},
    ],
})

EESVOOL_GEOJSON = json.dumps({
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature",
         "properties": {"ev_id": 7, "vnimi": "Kraav", "ms_kood": "1",
                        "ms_url": ""},
         "geometry": {"type": "LineString", "coordinates": [
             [24.76, 59.43], [24.77, 59.44]]}},
        {"type": "Feature",
         "properties": {"ev_id": 8},
         "geometry": {"type": "Polygon", "coordinates": [[
             [24.76, 59.43], [24.77, 59.43], [24.77, 59.44],
             [24.76, 59.44], [24.76, 59.43]]]}},
    ],
})


def test_parse_polygons_keeps_rings_skips_points():
    zones = parse_polygon_collection(VORK_GEOJSON, "network", "ms_kood",
                                     "ehitise_nimi")
    assert zones is not None
    assert len(zones) == 1
    assert zones[0]["cls"] == "network"
    assert zones[0]["ms_kood"] == "5111040011290"
    assert zones[0]["ms_url"].startswith("https://portaal.agri.ee/")
    assert len(zones[0]["polys"][0]) >= 4


def test_parse_polygons_unknown_on_garbage():
    assert parse_polygon_collection("not json", "network", "a", "b") is None
    assert parse_polygon_collection("", "network", "a", "b") is None


def test_parse_outflows_keeps_lines_skips_polygons():
    zones = parse_outflow_collection(EESVOOL_GEOJSON)
    assert zones is not None
    assert len(zones) == 1
    assert zones[0]["cls"] == "outflow"
    assert zones[0]["nimi"] == "Kraav"
    assert len(zones[0]["lines"][0]) == 2


def test_sidecar_rows_split_r_and_l():
    zones = ((parse_polygon_collection(VORK_GEOJSON, "network", "ms_kood",
                                       "ehitise_nimi") or [])
             + (parse_outflow_collection(EESVOOL_GEOJSON) or []))
    rows = to_sidecar(zones)
    assert len(rows) == 2
    poly, line = rows
    assert poly["cls"] == "network" and "r" in poly and "l" not in poly
    assert line["cls"] == "outflow" and "l" in line and "r" not in line
    lon, lat = poly["r"][0][0]
    assert (lon, lat) == (24.74, 59.43)
    lon2, lat2 = line["l"][0][0]
    assert (lon2, lat2) == (24.76, 59.43)


def test_build_sidecar_writes_counts_and_attribution(tmp_path):
    vork = tmp_path / "vork.json"
    vork.write_text(VORK_GEOJSON, encoding="utf-8")
    eesvool = tmp_path / "eesvool.json"
    eesvool.write_text(EESVOOL_GEOJSON, encoding="utf-8")
    snap = tmp_path / "snap"
    stats = build_sidecar({"vork": str(vork), "kehtetu": None,
                           "eesvool": str(eesvool)}, str(snap))
    assert stats["ok"] is True
    assert stats["zones"] == 2
    assert stats["by_cls"] == {"network": 1, "outflow": 1}
    assert stats["skipped_tables"] == ["kehtetu"]
    assert "Kliimaministeerium" in stats["attribution"]
    dest = snap / "maaparandus" / "maaparandus-areas.json"
    rows = json.loads(dest.read_text(encoding="utf-8"))
    assert len(rows) == 2


def test_build_sidecar_refuses_without_input(tmp_path):
    stats = build_sidecar({"vork": str(tmp_path / "missing.json"),
                           "kehtetu": None, "eesvool": None},
                          str(tmp_path / "s"))
    assert stats["ok"] is False
    assert not (tmp_path / "s" / "drainage" / "drainage-areas.json").exists()
