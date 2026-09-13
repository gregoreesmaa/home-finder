"""Overturn #239 G8 KAUR/EFAS flood-zone join: hermetic tests.

No network, no snapshot, no live WFS: the flood GML extract is an
inline fixture string (mirroring the real
eelis:kr_yleujutusohuga_ala shape -- gml:Polygon/exterior/LinearRing/
posList, WFS 2.0 EPSG:4326 axis order lat lon -- with FICTITIOUS
names so no fixture is ever mistaken for a real zone). Fetch paths
use tmp_path + stubbed urlopen only. Run from repo root:
  python3 -m pytest services/scoring/tests/test_dims_overturn_flood.py -q
"""

import os
import re
import urllib.request

import dims_overturn_flood as F
from dims_overturn_flood import (
    CACHE_FILENAME,
    FLOOD_BBOX_TALLINN,
    FLOOD_LAYER,
    FLOOD_POI_KIND,
    FLOOD_TTL_S,
    FLOOD_UA,
    FLOOD_ZONE_SCORE,
    OVERTURN_FLOOD_DIMS,
    RECHECK_AFTER,
    VERDICT_DATE,
    WFS_BASE,
    _getfeature_url,
    _point_in_ring,
    dim_burnscar_p371,
    dim_buyout_p372,
    dim_drought_p118,
    dim_envrisk_p46,
    dim_floodcreep_p429,
    dim_floodzone_p112,
    dim_frost_p377,
    dim_saltwater_p378,
    dim_searise_p117,
    dim_winddir_p182,
    fetch_flood_snapshot,
    parse_flood_snapshot,
    score_overturn_flood,
    zones_to_pois,
)

#: Fixture GML: two fictitious squares (FICTITIOUS names on purpose),
#: one feature without geometry (skipped), one with a broken ring
#: (skipped). North square spans lat 59.449-59.451 / lon 24.749-24.751,
#: south square lat 59.429-59.431 / lon 24.759-24.761.
FIXTURE_GML = """<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
  xmlns:gml="http://www.opengis.net/gml/3.2"
  xmlns:eelis="http://kemit.ee/eelis/avaandmed" numberMatched="4">
<eelis:kr_yleujutusohuga_ala gml:id="kr_yleujutusohuga_ala.0">
<eelis:shape><gml:Polygon srsName="urn:ogc:def:crs:EPSG::4326"><gml:exterior>
<gml:LinearRing><gml:posList>59.449 24.749 59.449 24.751 59.451 24.751
59.451 24.749 59.449 24.749</gml:posList></gml:LinearRing></gml:exterior>
</gml:Polygon></eelis:shape>
<eelis:sys_id>9001</eelis:sys_id><eelis:versioon>1.0</eelis:versioon>
<eelis:id>111</eelis:id><eelis:nimi>FIKTIIVNE katseala P&#245;hja</eelis:nimi>
<eelis:kr_kood>LTA9KATSE1</eelis:kr_kood>
<eelis:vveekogu>Katsej&#245;gi VEE0000001</eelis:vveekogu>
<eelis:tyyp>Suurte &#252;leujutusaladega siseveekogu</eelis:tyyp>
</eelis:kr_yleujutusohuga_ala>
<eelis:kr_yleujutusohuga_ala gml:id="kr_yleujutusohuga_ala.1">
<eelis:shape><gml:Polygon srsName="urn:ogc:def:crs:EPSG::4326"><gml:exterior>
<gml:LinearRing><gml:posList>59.429 24.759 59.429 24.761 59.431 24.761
59.431 24.759 59.429 24.759</gml:posList></gml:LinearRing></gml:exterior>
</gml:Polygon></eelis:shape>
<eelis:sys_id>9002</eelis:sys_id><eelis:versioon>1.0</eelis:versioon>
<eelis:id>112</eelis:id><eelis:nimi>FIKTIIVNE katseala L&#245;una</eelis:nimi>
<eelis:kr_kood>LTA9KATSE2</eelis:kr_kood>
<eelis:sveekogu>Katsejarv VEE0000002</eelis:sveekogu>
<eelis:tyyp>Suurte &#252;leujutusaladega siseveekogu</eelis:tyyp>
</eelis:kr_yleujutusohuga_ala>
<eelis:kr_yleujutusohuga_ala gml:id="kr_yleujutusohuga_ala.2">
<eelis:sys_id>9003</eelis:sys_id>
<eelis:nimi>FIKTIIVNE geomeetriata kirje</eelis:nimi>
<eelis:kr_kood>LTA9KATSE3</eelis:kr_kood>
</eelis:kr_yleujutusohuga_ala>
<eelis:kr_yleujutusohuga_ala gml:id="kr_yleujutusohuga_ala.3">
<eelis:shape><gml:Polygon srsName="urn:ogc:def:crs:EPSG::4326"><gml:exterior>
<gml:LinearRing><gml:posList>katki andmed</gml:posList></gml:LinearRing>
</gml:exterior></gml:Polygon></eelis:shape>
<eelis:sys_id>9004</eelis:sys_id>
<eelis:nimi>FIKTIIVNE katkise ringiga kirje</eelis:nimi>
<eelis:kr_kood>LTA9KATSE4</eelis:kr_kood>
</eelis:kr_yleujutusohuga_ala>
</wfs:FeatureCollection>
"""

INSIDE_NORTH = (59.450, 24.750)   # centre of the north square
NEAR_EDGE_NORTH = (59.4492, 24.750)  # shallow inside, same square
INSIDE_SOUTH = (59.430, 24.760)
OUTSIDE = (59.4372, 24.7536)      # Tallinn centre, outside both


def write_gml(tmpdir, text=FIXTURE_GML):
    path = os.path.join(str(tmpdir), CACHE_FILENAME)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _tmp_pois():
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".gml")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(FIXTURE_GML)
    return path


# ---------------------------------------------------------------------------
# Offline readers: malformed rows skipped, missing file is unknown.
# ---------------------------------------------------------------------------

def test_parse_missing_and_garbage_is_none(tmpdir):
    assert parse_flood_snapshot(os.path.join(str(tmpdir), "nope.gml")) is None
    bad = os.path.join(str(tmpdir), "bad.gml")
    with open(bad, "w", encoding="utf-8") as fh:
        fh.write("{pole xml")
    assert parse_flood_snapshot(bad) is None


def test_parse_keeps_two_fictitious_zones_and_skips_broken(tmpdir):
    zones = parse_flood_snapshot(write_gml(tmpdir))
    assert zones is not None and len(zones) == 2
    north, south = zones
    assert north["zone_id"] == "LTA9KATSE1"
    assert "Põhja" in north["nimi"] and "FIKTIIVNE" in north["nimi"]
    assert north["veekogu"] == "Katsejõgi VEE0000001"
    assert south["zone_id"] == "LTA9KATSE2"
    assert south["veekogu"] == "Katsejarv VEE0000002"  # sveekogu fallback
    assert len(north["poly"]) == 5 and len(south["poly"]) == 5


def test_zones_to_pois_none_is_no_join_and_kind_is_distinct():
    assert zones_to_pois(None) == []
    assert zones_to_pois("praht") == []
    pois = zones_to_pois(parse_flood_snapshot(_tmp_pois()))
    assert {p["kind"] for p in pois} == {FLOOD_POI_KIND}
    assert FLOOD_POI_KIND == "flood_zone_overturn"
    # Distinct POI kind from the sibling P4 KAUR pipeline (no overlap).
    assert FLOOD_POI_KIND != "kaur_zone_p4"


# ---------------------------------------------------------------------------
# Point-in-ring geometry.
# ---------------------------------------------------------------------------

def test_point_in_ring_inside_outside():
    ring = [(59.449, 24.749), (59.449, 24.751), (59.451, 24.751),
            (59.451, 24.749)]
    assert _point_in_ring(59.450, 24.750, ring) is True
    assert _point_in_ring(59.4372, 24.7536, ring) is False
    assert _point_in_ring(59.460, 24.750, ring) is False


# ---------------------------------------------------------------------------
# p112: zone join (choropleth) -- scored inside, NULL outside.
# ---------------------------------------------------------------------------

def test_p112_scores_inside_with_zone_naming_reason():
    v, reason = dim_floodzone_p112(INSIDE_NORTH, zones_to_pois(
        parse_flood_snapshot(_tmp_pois())))
    assert v == FLOOD_ZONE_SCORE == 25
    assert "hinnang" in reason
    assert "tsooniliide" in reason
    assert "LTA9KATSE1" in reason and "Põhja" in reason


def test_p112_names_the_joined_south_zone():
    v, reason = dim_floodzone_p112(INSIDE_SOUTH, zones_to_pois(
        parse_flood_snapshot(_tmp_pois())))
    assert v == 25
    assert "LTA9KATSE2" in reason and "Lõuna" in reason


def test_p112_is_choropleth_not_gradient():
    # Depth inside the polygon changes nothing: centre and near-edge
    # score alike, and the reason carries no distance.
    pois = zones_to_pois(parse_flood_snapshot(_tmp_pois()))
    v_deep, _ = dim_floodzone_p112(INSIDE_NORTH, pois)
    v_shallow, reason = dim_floodzone_p112(NEAR_EDGE_NORTH, pois)
    assert v_deep == v_shallow == 25
    assert re.search(r"\d\s*(m|km)\b", reason) is None


def test_p112_does_not_reskin_drainage_or_street():
    _, reason = dim_floodzone_p112(INSIDE_NORTH, zones_to_pois(
        parse_flood_snapshot(_tmp_pois())))
    assert "tsooniliide" in reason
    assert "mitte drenaaži" in reason
    assert "läbitavus" not in reason and "kõrgvesi" not in reason


def test_p112_outside_is_unknown_never_dry():
    v, reason = dim_floodzone_p112(OUTSIDE, zones_to_pois(
        parse_flood_snapshot(_tmp_pois())))
    assert v is None
    assert "EI OLE" in reason
    assert "teadmata, mitte kuiv" in reason


def test_p112_null_without_join():
    for origin, p in [(None, None), (INSIDE_NORTH, None),
                      (INSIDE_NORTH, []), (None, [])]:
        v, reason = dim_floodzone_p112(origin, p)
        assert v is None
        assert "EI OLE" in reason


def test_p112_ignores_foreign_poi_kinds():
    foreign = [{"kind": "kaur_zone_p4", "lat": 59.450, "lon": 24.750,
                "zone": "t10", "name": "võõras", "zone_id": "x"}]
    v, _ = dim_floodzone_p112(INSIDE_NORTH, foreign)
    assert v is None


def test_p112_network_free(monkeypatch):
    def _boom(req, timeout=None):
        raise AssertionError("network used by scorer")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    pois = zones_to_pois(parse_flood_snapshot(_tmp_pois()))
    assert dim_floodzone_p112(INSIDE_NORTH, pois)[0] == 25
    assert dim_floodzone_p112(OUTSIDE, pois)[0] is None


# ---------------------------------------------------------------------------
# Dated-negative NULLs: always None, EI OLE + missing-input pointer.
# ---------------------------------------------------------------------------

NULL_DIMS_AND_MARKERS = [
    (dim_envrisk_p46, "KOV keskkonnainfot"),
    (dim_searise_p117, "kõverat"),
    (dim_drought_p118, "mullakaart"),
    (dim_winddir_p182, "edelavool"),
    (dim_burnscar_p371, "EFFIS"),
    (dim_buyout_p372, "väljamaksete"),
    (dim_frost_p377, "geotehniline"),
    (dim_saltwater_p378, "analüüs"),
    (dim_floodcreep_p429, "ajalugu"),
]


def test_dated_nulls_always_none_for_every_input():
    pois = zones_to_pois(parse_flood_snapshot(_tmp_pois()))
    for fn, _ in NULL_DIMS_AND_MARKERS:
        for origin, p in [(INSIDE_NORTH, pois), (OUTSIDE, pois),
                          (OUTSIDE, []), (None, None), (None, pois),
                          (INSIDE_NORTH, None)]:
            v, reason = fn(origin, p)
            assert v is None
            assert "EI OLE" in reason


def test_dated_nulls_name_the_missing_input():
    for fn, marker in NULL_DIMS_AND_MARKERS:
        _, reason = fn(OUTSIDE, [])
        assert marker in reason, fn.__name__


# ---------------------------------------------------------------------------
# Registry, aggregator, verdict dating, fetch contract.
# ---------------------------------------------------------------------------

def test_registry_covers_ten_params_with_distinct_keys():
    assert len(OVERTURN_FLOOD_DIMS) == 10
    keys = [k for k, _, _ in OVERTURN_FLOOD_DIMS]
    assert all(k.endswith("_overturn_flood") for k in keys)
    assert len(set(keys)) == 10
    assert [p for _, p, _ in OVERTURN_FLOOD_DIMS] == [
        46, 112, 117, 118, 182, 371, 372, 377, 378, 429]
    assert len({fn for _, _, fn in OVERTURN_FLOOD_DIMS}) == 10
    assert F.OVERTURN_FLOOD_DIMS is OVERTURN_FLOOD_DIMS


def test_aggregator_flips_only_p112():
    pois = zones_to_pois(parse_flood_snapshot(_tmp_pois()))
    got = score_overturn_flood(INSIDE_NORTH, pois)
    assert got["floodzone_overturn_flood"] == 25
    assert all(v is None for k, v in got.items()
               if k != "floodzone_overturn_flood")
    assert all(v is None for v in
               score_overturn_flood(OUTSIDE, pois).values())
    assert all(v is None for v in
               score_overturn_flood(None, None).values())


def test_verdict_is_dated_with_recheck_note():
    assert VERDICT_DATE == "2026-09-13"
    assert RECHECK_AFTER == "2027-03-13"
    assert RECHECK_AFTER > VERDICT_DATE


def test_fetch_url_names_layer_srs_and_bbox():
    url = _getfeature_url(FLOOD_BBOX_TALLINN)
    assert url.startswith(WFS_BASE)
    assert FLOOD_LAYER in url
    assert "EPSG::4326" in url
    assert "24.4" in url and "59.7" in url
    assert "bbox" not in _getfeature_url(None).lower()


def test_fetch_cache_hit_performs_no_request(tmpdir, monkeypatch):
    dest = write_gml(tmpdir)

    def _boom(req, timeout=None):
        raise AssertionError("network used on cache hit")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    assert fetch_flood_snapshot(str(tmpdir)) == dest


def test_fetch_transport_error_caches_nothing(tmpdir, monkeypatch):
    class _Bad:
        def __enter__(self):
            raise IOError("down")

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=None: _Bad())
    assert fetch_flood_snapshot(str(tmpdir)) is None
    assert os.listdir(str(tmpdir)) == []


def test_fetch_non_xml_body_caches_nothing(tmpdir, monkeypatch):
    class _Resp:
        status = 200
        headers = {"Content-Type": "text/html"}

        def read(self):
            return b"<html>pole xml</html>"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=None: _Resp())
    assert fetch_flood_snapshot(str(tmpdir)) is None
    assert os.listdir(str(tmpdir)) == []


def test_fetch_garbage_xml_caches_nothing(tmpdir, monkeypatch):
    class _Resp:
        status = 200
        headers = {"Content-Type": "application/gml+xml"}

        def read(self):
            return b"<wfs:katki"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=None: _Resp())
    assert fetch_flood_snapshot(str(tmpdir)) is None
    assert os.listdir(str(tmpdir)) == []


def test_fetch_200_xml_is_cached(tmpdir, monkeypatch):
    class _Resp:
        status = 200
        headers = {"Content-Type": "application/gml+xml; version=3.2"}

        def read(self):
            return FIXTURE_GML.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=None: _Resp())
    dest = fetch_flood_snapshot(str(tmpdir))
    assert dest is not None and dest.endswith(CACHE_FILENAME)
    assert parse_flood_snapshot(dest) is not None


def test_ttl_is_annual_and_ua_identifies():
    assert FLOOD_TTL_S == 365 * 24 * 3600
    assert "home-finder" in FLOOD_UA
    assert FLOOD_BBOX_TALLINN == (24.4, 59.2, 25.5, 59.7)
