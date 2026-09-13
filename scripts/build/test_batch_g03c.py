"""Hermetic unit tests for the Group 3 cadastre-C evidence probe (issue #153).

No network, no snapshot: exports are tiny inline fixtures in tmp files,
and the TS drift guard parses the committed registry file. Run:
  python3 -m pytest scripts/build/test_batch_g03c.py -q
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_g03c_cadastre as C

TS_REGISTRY = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "apps", "web", "lib", "layers_group03c.ts")


def spring_export():
    # RS-delimited geojsonseq, like `osmium export` writes.
    feats = [
        {"type": "Feature",
         "properties": {"natural": "spring", "name": "Sõeru ohvriallikas"},
         "geometry": {"type": "Point", "coordinates": [24.5, 59.3]}},
        {"type": "Feature", "properties": {"natural": "spring"},
         "geometry": {"type": "LineString",
                      "coordinates": [[24.5, 59.3], [24.51, 59.31]]}},
        {"type": "Feature", "properties": {"UID": "7"},  # untagged member
         "geometry": {"type": "LineString",
                      "coordinates": [[24.5, 59.3], [24.51, 59.31]]}},
    ]
    return "".join("\x1e" + json.dumps(f) + "\n" for f in feats)


def test_summarize_features_splits_tagged_and_geom():
    feats = [
        ({"natural": "wetland"}, "MultiPolygon"),
        ({"natural": "wetland"}, "LineString"),
        ({"UID": "3"}, "LineString"),  # untagged member: reported, not folded
        ({"leisure": "nature_reserve"}, "Point"),
        ({"natural": "wetland"}, "WeirdGeometry"),
    ]
    out = C.summarize_features(feats)
    assert out["tagged"] == 4
    assert out["untagged"] == 1
    assert out["by_geom"] == {"Point": 1, "LineString": 2, "MultiPolygon": 1}
    assert out["by_geom_other"] == 1


def test_has_soil_attrs_rejects_barrier_junk_accepts_ph():
    assert not C.has_soil_attrs({"barrier": "gate", "source": "Yahoo"})
    assert not C.has_soil_attrs({"landuse": "farm", "access": "yes"})
    assert not C.has_soil_attrs({})
    assert C.has_soil_attrs({"soil:ph": "6.2"})
    assert C.has_soil_attrs({"TEXTURE": "sandy loam"})
    assert C.has_soil_attrs({"clay": "12%"})


def test_iter_export_features_reads_rs_delimited_seq(tmp_path):
    p = str(tmp_path / "spring.geojsonseq")
    with open(p, "w", encoding="utf-8") as f:
        f.write(spring_export())
    feats = C.iter_export_features(p)
    assert len(feats) == 3
    out = C.summarize_features(feats)
    assert (out["tagged"], out["untagged"]) == (2, 1)
    assert out["by_geom"]["Point"] == 1
    assert out["by_geom"]["LineString"] == 2


def test_iter_export_features_reads_plain_geojson(tmp_path):
    doc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"man_made": "water_well"},
         "geometry": {"type": "Point", "coordinates": [24.7, 59.4]}}]}
    p = str(tmp_path / "well.geojson")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    assert len(C.iter_export_features(p)) == 1


def test_summarize_soil_file_counts_attrs(tmp_path):
    doc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"barrier": "gate"},
         "geometry": {"type": "Point", "coordinates": [0, 0]}},
        {"type": "Feature", "properties": {"soil:ph": "5.8"},
         "geometry": {"type": "Point", "coordinates": [0, 0]}}]}
    p = str(tmp_path / "soil.geojson")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    assert C.summarize_soil_file(p) == {"features": 2, "soil_attrs": 1}


def test_main_stat_and_soil_end_to_end(tmp_path, capsys):
    sp = str(tmp_path / "spring.geojsonseq")
    with open(sp, "w", encoding="utf-8") as f:
        f.write(spring_export())
    doc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"barrier": "gate"},
         "geometry": {"type": "Point", "coordinates": [0, 0]}}]}
    op = str(tmp_path / "soil.geojson")
    with open(op, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    assert C.main(["--stat", "springsTagged=" + sp, "--soil", op]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["springsTagged"]["tagged"] == 2
    assert report["soil"] == {"features": 1, "soil_attrs": 0}


def test_main_rejects_missing_stat_file(capsys):
    assert C.main(["--stat", "x=/no/such/file"]) == 2


def test_check_ts_registry_matches_locked_evidence():
    assert os.path.isfile(TS_REGISTRY), TS_REGISTRY
    assert C.check_ts_registry(TS_REGISTRY) == []
    assert C.check_ts_registry(TS_REGISTRY) is not None
    # Every locked key is actually present in the TS file (no silent skip).
    import re
    text = open(TS_REGISTRY, encoding="utf-8").read()
    for key in C.LOCKED_EVIDENCE:
        assert re.search(r"%s:\s*\d+" % key, text), key
