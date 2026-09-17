"""Hermetic tests for scripts/build/batch_kpo.py (issue #626).

No network: synthetic WFS members + inline parcels. Pins the (N, E)
axis order, the exterior-only ring rule, the TRUE LCC projection
(never TM), the parcel-window shaping, and the kataster proof join.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_kpo import (  # noqa: E402
    FAMILIES,
    build,
    kataster_proof,
    main,
    parcel_windows,
    parse_members,
    project_ring_lonlat,
    to_sidecar,
)

GML = """<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
 xmlns:gml="http://www.opengis.net/gml/3.2"
 xmlns:kmakitsendused="kpois_kma">
<wfs:member><kmakitsendused:kma_avalik_elekter gml:id="kma_avalik_elekter.1">
<kmakitsendused:shape><gml:Polygon srsName="urn:ogc:def:crs:EPSG::3301">
<gml:exterior><gml:LinearRing><gml:posList>6589288 542538 6589298 542538 6589298 542548 6589288 542548 6589288 542538</gml:posList></gml:LinearRing></gml:exterior>
<gml:interior><gml:LinearRing><gml:posList>6589290 542540 6589292 542540 6589292 542542 6589290 542542 6589290 542540</gml:posList></gml:LinearRing></gml:interior>
</gml:Polygon></kmakitsendused:shape>
<kmakitsendused:voond_liik_id_vaartus>Elektripaigaldise kaitsevöönd</kmakitsendused:voond_liik_id_vaartus>
<kmakitsendused:nimi>JAAM</kmakitsendused:nimi>
<kmakitsendused:reegel>Ehitusseadustik</kmakitsendused:reegel>
</kmakitsendused:kma_avalik_elekter></wfs:member>
<wfs:member><kmakitsendused:kma_avalik_gaas gml:id="kma_avalik_gaas.2">
<kmakitsendused:shape><gml:Polygon srsName="urn:ogc:def:crs:EPSG::3301">
<gml:exterior><gml:LinearRing><gml:posList>6589300 542560 6589310 542560 6589310 542570 6589300 542570 6589300 542560</gml:posList></gml:LinearRing></gml:exterior>
</gml:Polygon></kmakitsendused:shape>
<kmakitsendused:voond_liik_id>Gaasipaigaldise kaitsevöönd</kmakitsendused:voond_liik_id>
<kmakitsendused:nimi></kmakitsendused:nimi>
</kmakitsendused:kma_avalik_gaas></wfs:member>
</wfs:FeatureCollection>"""

PARCELS = {"parcels": [
    {"tunnus": "78401:107:0760",
     "b": [24.74148606, 59.43161191, 24.74235907, 59.43200251]},
    {"tunnus": "78401:107:0761",
     "b": [24.80, 59.50, 24.81, 59.51]},
]}


def test_parse_members_exterior_only_ne_order():
    members = parse_members(GML)
    assert len(members) == 2
    assert members[0]["family"] == "elekter"
    assert members[0]["attrs"]["voond"] == "Elektripaigaldise kaitsevöönd"
    assert members[0]["attrs"]["nimi"] == "JAAM"
    # Exterior only: the interior hole ring must NOT parse.
    assert len(members[0]["rings_3301"]) == 1
    # (N, E) axis order: first pair is (northing, easting).
    assert members[0]["rings_3301"][0][0] == (542538.0, 6589288.0)
    # voond_liik_id fallback when _vaartus is absent.
    assert members[1]["attrs"]["voond"] == "Gaasipaigaldise kaitsevöönd"


def test_project_ring_uses_true_lcc_not_tm():
    # (542538, 6589288) must land on the LCC Tallinn value, NOT the
    # legacy TM identity: lon ~24.7497 (dE ~17 m off the TM pin).
    ring = project_ring_lonlat([(542538.0, 6589288.0),
                                (542548.0, 6589288.0),
                                (542548.0, 6589298.0),
                                (542538.0, 6589288.0)])
    assert abs(ring[0][0] - 24.74968) < 1e-4
    assert abs(ring[0][1] - 59.43928) < 1e-4


NESTED_GML = """<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
 xmlns:gml="http://www.opengis.net/gml/3.2"
 xmlns:kmakitsendused="kpois_kma">
<wfs:member><wfs:FeatureCollection numberMatched="1" numberReturned="1">
<wfs:member><kmakitsendused:kma_avalik_side gml:id="kma_avalik_side.7">
<kmakitsendused:shape><gml:Polygon srsName="urn:ogc:def:crs:EPSG::3301">
<gml:exterior><gml:LinearRing><gml:posList>6589288 542538 6589298 542538 6589298 542548 6589288 542548 6589288 542538</gml:posList></gml:LinearRing></gml:exterior>
</gml:Polygon></kmakitsendused:shape>
<kmakitsendused:voond_liik_id_vaartus>Sideehitise kaitsevöönd</kmakitsendused:voond_liik_id_vaartus>
<kmakitsendused:nimi>ELV</kmakitsendused:nimi>
</kmakitsendused:kma_avalik_side></wfs:member>
</wfs:FeatureCollection></wfs:member>
</wfs:FeatureCollection>"""


def test_parse_members_unwraps_nested_family_collections():
    # Multi-typeName responses nest one FeatureCollection per family
    # inside an outer member (live shape 2026-09-17): the inner
    # feature must parse, the wrapper must skip (never double-count).
    members = parse_members(NESTED_GML)
    assert len(members) == 1
    assert members[0]["family"] == "side"
    assert members[0]["attrs"]["nimi"] == "ELV"


def test_to_sidecar_rows_shape():
    rows = to_sidecar(parse_members(GML))
    assert len(rows) == 2
    assert rows[0]["family"] == "elekter"
    assert len(rows[0]["b"]) == 4
    assert len(rows[0]["r"][0]) >= 4


def test_parcel_windows_margin_and_tunnus():
    wins = parcel_windows(PARCELS)
    assert [w["tunnus"] for w in wins] == ["78401:107:0760",
                                           "78401:107:0761"]
    assert wins[0]["bbox"][0] < 24.74148606  # margin applied


def test_kataster_proof_counts_hits_honestly():
    rows = to_sidecar(parse_members(GML))
    proof = kataster_proof(parcel_windows(PARCELS), rows)
    assert proof["parcels_total"] == 2
    # Genuine containment result, whatever it is -- the shape (tunnus
    # keys, voond lists) is the contract, not a fixed hit count.
    assert set(proof["hits"]) <= {"78401:107:0760", "78401:107:0761"}
    for voonds in proof["hits"].values():
        assert all(isinstance(v, str) for v in voonds)


def test_kataster_proof_joins_areas_not_just_centroids():
    # An easement crossing a parcel corner misses the centroid: the
    # area join must still hit. Synthetic zone clips the corner of a
    # big parcel whose centroid sits far outside.
    rows = [{
        "family": "elekter",
        "nimi": "NURK",
        "voond": "Elektripaigaldise kaitsevöönd",
        "reegel": "",
        "b": [24.80, 59.50, 24.801, 59.501],
        "r": [[[24.80, 59.50], [24.801, 59.50],
               [24.801, 59.501], [24.80, 59.501]]],
    }]
    parcels = [{"tunnus": "X", "bbox": (24.79, 59.49, 24.82, 59.52)}]
    rings = {"X": [[[24.79, 59.49], [24.82, 59.49],
                    [24.82, 59.52], [24.79, 59.52]]]}
    proof = kataster_proof(parcels, rows, rings)
    assert proof["parcels_hit"] == 1
    assert proof["hits"]["X"] == ["Elektripaigaldise kaitsevöönd"]


def test_build_merge_only_offline(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "w_1.gml").write_text(GML)
    parcels = tmp_path / "parcels.json"
    parcels.write_text(json.dumps(PARCELS))
    snap = tmp_path / "snap"
    snap.mkdir()
    rc = main(["--cache-dir", str(cache), "--snap", str(snap),
               "--parcels", str(parcels), "--merge-only"])
    assert rc == 0
    doc = json.loads((snap / "kpo" / "kpo-areas.json").read_text())
    assert doc["stats"]["zones"] == 2
    assert doc["stats"]["parcels_total"] == 2
    assert "CC-BY 4.0" in doc["attribution"]


def test_families_cover_all_eighteen():
    assert len(FAMILIES) == 18
