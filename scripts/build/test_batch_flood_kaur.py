"""KAUR flood-zone builder tests (issue #487): hermetic tests.

No network, no snapshot: the parser runs on a tiny inline GML fixture
(two synthetic zone boxes + one malformed row), the writer on tmp dirs.
Coordinates are synthetic fixture boxes — only the zone NAMES mirror the
verdict doc's real samples (docs/overturn_flood.md); no real register
geometry is committed anywhere.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_flood_kaur as G


def feat(nimi, kr_kood, pos):
    return """  <eelis:kr_yleujutusohuga_ala>
    <eelis:sys_id>1001</eelis:sys_id>
    <eelis:nimi>%s</eelis:nimi>
    <eelis:kr_kood>%s</eelis:kr_kood>
    <eelis:vveekogu>Fixture järv</eelis:vveekogu>
    <eelis:tyyp>Suurte üleujutusaladega siseveekogu</eelis:tyyp>
    <eelis:shape><gml:Polygon><gml:exterior><gml:LinearRing>
      <gml:posList>%s</gml:posList>
    </gml:LinearRing></gml:exterior></gml:Polygon></eelis:shape>
  </eelis:kr_yleujutusohuga_ala>""" % (nimi, kr_kood, pos)


GML = """<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
    xmlns:eelis="http://kemit.ee/eelis/avaandmed"
    xmlns:gml="http://www.opengis.net/gml/3.2">
%s
%s
  <eelis:kr_yleujutusohuga_ala>
    <eelis:nimi>katkine kirje</eelis:nimi>
    <eelis:shape><gml:Polygon><gml:exterior><gml:LinearRing>
      <gml:posList>58.2 22.0 oops</gml:posList>
    </gml:LinearRing></gml:exterior></gml:Polygon></eelis:shape>
  </eelis:kr_yleujutusohuga_ala>
</wfs:FeatureCollection>""" % (
    feat("Mullutu-Suurlaht kogu kalda ulatuses", "KR-001",
         "58.20 22.00 58.20 22.20 58.30 22.20 58.30 22.00 58.20 22.00"),
    feat("Suur-Emajõgi koos vanajõgedega kogu ulatuses", "KR-002",
         "58.40 26.70 58.40 26.90 58.50 26.90 58.50 26.70 58.40 26.70"),
)


def test_parse_valid_zones():
    zones = G.parse_gml_text(GML)
    assert zones is not None
    # Two valid rows; the malformed row is skipped, never faked.
    assert len(zones) == 2
    assert zones[0]["nimi"] == "Mullutu-Suurlaht kogu kalda ulatuses"
    assert zones[0]["zone_id"] == "KR-001"
    assert zones[1]["zone_id"] == "KR-002"
    assert zones[0]["tyyp"] == "Suurte üleujutusaladega siseveekogu"


def test_parse_unparseable_is_none():
    assert G.parse_gml_text("<not xml") is None


def test_sidecar_flips_to_lonlat_with_box():
    zones = G.parse_gml_text(GML)
    rows = G.to_sidecar(zones)
    assert len(rows) == 2
    # Contract keys consumed by layers_flood.ts isFloodArea (drift pin).
    assert set(rows[0].keys()) == {"zone_id", "nimi", "veekogu", "tyyp", "b", "r"}
    ring = rows[0]["r"][0]
    assert ring[0] == [22.00, 58.20]
    assert rows[0]["b"] == [22.00, 58.20, 22.20, 58.30]
    assert rows[1]["b"] == [26.70, 58.40, 26.90, 58.50]


def test_contains_joins_per_parcel():
    zones = G.parse_gml_text(GML)
    hit = G.contains(zones, 58.25, 22.10)
    assert hit is not None and hit["zone_id"] == "KR-001"
    # Centre and edge of a polygon join alike (no distance decay, pinned).
    assert G.contains(zones, 58.29, 22.19)["zone_id"] == "KR-001"
    # Outside every polygon stays NULL (unknown, never "dry").
    assert G.contains(zones, 59.44, 24.75) is None
    assert G.contains(None, 58.25, 22.10) is None


def test_build_writes_sidecar_and_stats(tmp_path):
    gml = tmp_path / "flood-snapshot.gml"
    gml.write_text(GML, encoding="utf-8")
    snap = tmp_path / "snap"
    stats = G.build_sidecar(str(gml), str(snap))
    assert stats["ok"] is True
    assert stats["zones"] == 2
    dest = os.path.join(str(snap), "kaur", "flood-areas.json")
    rows = json.load(open(dest, encoding="utf-8"))
    assert len(rows) == 2
    assert rows[0]["nimi"].startswith("Mullutu-Suurlaht")


def test_build_missing_gml_writes_nothing(tmp_path):
    snap = tmp_path / "snap"
    stats = G.build_sidecar(str(tmp_path / "absent.gml"), str(snap))
    assert stats["ok"] is False
    assert not os.path.exists(os.path.join(str(snap), "kaur", "flood-areas.json"))


def test_build_unparseable_gml_writes_nothing(tmp_path):
    gml = tmp_path / "flood-snapshot.gml"
    gml.write_text("<not xml", encoding="utf-8")
    stats = G.build_sidecar(str(gml), str(tmp_path / "snap"))
    assert stats["ok"] is False


def test_builder_is_offline_by_construction():
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "batch_flood_kaur.py"), encoding="utf-8").read()
    for mod in ("urllib", "socket", "http.client", "requests"):
        assert ("import %s" % mod) not in src
