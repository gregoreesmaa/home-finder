"""Hermetic tests for scripts/build/batch_quarry.py (issue #614).

Covers ONLY the pure sidecar projection — the WFS harvest is a polite
one-off (custom UA, paced, /tmp-only) and is never called here
(AGENTS.md section 7.6). Scorer math is pinned in
test_dims_p4_maavara_extract.py (reused, never re-tested here).
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_quarry import (  # noqa: E402
    build_sidecar,
    parse_explore_gml,
    parse_extract_gml,
    parse_loa_lopp,
    to_sidecar,
)

from datetime import date  # noqa: E402

GML_EXTRACT = """<?xml version='1.0' encoding="UTF-8" ?>
<wfs:FeatureCollection xmlns:ms="http://mapserver.gis.umn.edu/mapserver"
 xmlns:gml="http://www.opengis.net/gml">
<gml:featureMember>
<ms:maeeraldis_aktiivne fid="maeeraldis_aktiivne.13379">
<gml:boundedBy><gml:Box srsName="EPSG:3301"><gml:coordinates>1,2 3,4</gml:coordinates></gml:Box></gml:boundedBy>
<ms:msGeometry><gml:Polygon srsName="EPSG:3301"><gml:outerBoundaryIs><gml:LinearRing><gml:coordinates>542000,6593000 542100,6593000 542100,6593100 542000,6593100 542000,6593000</gml:coordinates></gml:LinearRing></gml:outerBoundaryIs></gml:Polygon></ms:msGeometry>
<ms:ME_ID>13379</ms:ME_ID>
<ms:NIMETUS>Huntaugu I liivakarjäär</ms:NIMETUS>
<ms:LOA_NUMBER>HARM-139</ms:LOA_NUMBER>
<ms:KAEVANDAJA>AS TREV-2 Grupp</ms:KAEVANDAJA>
<ms:LOA_LOPP>20310301</ms:LOA_LOPP>
<ms:ME_OLEK>aktiivne</ms:ME_OLEK>
</ms:maeeraldis_aktiivne>
</gml:featureMember>
<gml:featureMember>
<ms:maeeraldis_aktiivne fid="maeeraldis_aktiivne.9">
<ms:msGeometry><gml:Polygon srsName="EPSG:3301"><gml:outerBoundaryIs><gml:LinearRing><gml:coordinates>542000,6593000 542100,6593000 542100,6593100 542000,6593100 542000,6593000</gml:coordinates></gml:LinearRing></gml:outerBoundaryIs></gml:Polygon></ms:msGeometry>
<ms:ME_ID>9</ms:ME_ID>
<ms:NIMETUS>Vana lubjakivikarjäär</ms:NIMETUS>
<ms:LOA_NUMBER>HARM-1</ms:LOA_NUMBER>
<ms:KAEVANDAJA>Keegi</ms:KAEVANDAJA>
<ms:LOA_LOPP>20200101</ms:LOA_LOPP>
<ms:ME_OLEK>aktiivne</ms:ME_OLEK>
</ms:maeeraldis_aktiivne>
</gml:featureMember>
</wfs:FeatureCollection>
"""

GML_EXPLORE = """<?xml version='1.0' encoding="UTF-8" ?>
<wfs:FeatureCollection xmlns:ms="http://mapserver.gis.umn.edu/mapserver"
 xmlns:gml="http://www.opengis.net/gml">
<gml:featureMember>
<ms:Aktiivne_uuringuala fid="Aktiivne_uuringuala.5">
<ms:msGeometry><gml:Polygon srsName="EPSG:3301"><gml:outerBoundaryIs><gml:LinearRing><gml:coordinates>543000,6594000 543100,6594000 543100,6594100 543000,6594100 543000,6594000</gml:coordinates></gml:LinearRing></gml:outerBoundaryIs></gml:Polygon></ms:msGeometry>
<ms:U_ALA_ID>5</ms:U_ALA_ID>
<ms:U_ALA_NIMI>Test-uuring</ms:U_ALA_NIMI>
<ms:LOA_NR>U-7</ms:LOA_NR>
<ms:LOA_LOPP>20271012</ms:LOA_LOPP>
<ms:U_TEOSTAJA>Geoloog OÜ</ms:U_TEOSTAJA>
</ms:Aktiivne_uuringuala>
</gml:featureMember>
</wfs:FeatureCollection>
"""

TODAY = date(2026, 9, 17)


def test_parse_loa_lopp():
    assert parse_loa_lopp("20310301") == date(2031, 3, 1)
    assert parse_loa_lopp("") is None
    assert parse_loa_lopp("pole kuupäev") is None
    assert parse_loa_lopp(None) is None


def test_parse_extract_keeps_only_live_permits():
    zones = parse_extract_gml(GML_EXTRACT, TODAY)
    assert zones is not None
    assert len(zones) == 1
    assert zones[0]["cls"] == "active"
    assert zones[0]["loa"] == "HARM-139"
    assert zones[0]["loa_lopp"] == "20310301"
    assert len(zones[0]["polys"][0]) >= 4


def test_parse_extract_unknown_on_garbage():
    assert parse_extract_gml("not gml at all", TODAY) is None
    assert parse_extract_gml("", TODAY) is None


def test_parse_explore_carries_dated_watch():
    zones = parse_explore_gml(GML_EXPLORE)
    assert zones is not None
    assert len(zones) == 1
    assert zones[0]["cls"] == "exploration"
    assert zones[0]["loa_lopp"] == "20271012"


def test_sidecar_rows_carry_geojson_lonlat_rings():
    zones = ((parse_extract_gml(GML_EXTRACT, TODAY) or [])
             + (parse_explore_gml(GML_EXPLORE) or []))
    rows = to_sidecar(zones)
    assert len(rows) == 2
    lon, lat = rows[0]["r"][0][0]
    assert 23.0 < lon < 26.0 and 58.5 < lat < 60.0
    b = rows[0]["b"]
    assert b[0] <= lon <= b[2] and b[1] <= lat <= b[3]


def test_build_sidecar_writes_counts_and_attribution(tmp_path):
    extract = tmp_path / "extract.gml"
    extract.write_text(GML_EXTRACT, encoding="utf-8")
    explore = tmp_path / "explore.gml"
    explore.write_text(GML_EXPLORE, encoding="utf-8")
    snap = tmp_path / "snap"
    stats = build_sidecar({"extract": str(extract),
                           "explore": str(explore)}, str(snap))
    assert stats["ok"] is True
    assert stats["zones"] == 2
    assert stats["by_cls"] == {"active": 1, "exploration": 1}
    assert "Maa- ja Ruumiamet" in stats["attribution"]
    dest = snap / "quarry" / "quarry-areas.json"
    rows = json.loads(dest.read_text(encoding="utf-8"))
    assert len(rows) == 2


def test_build_sidecar_refuses_without_input(tmp_path):
    stats = build_sidecar({"extract": str(tmp_path / "missing.gml"),
                           "explore": None}, str(tmp_path / "s"))
    assert stats["ok"] is False
    assert not (tmp_path / "s" / "quarry" / "quarry-areas.json").exists()
