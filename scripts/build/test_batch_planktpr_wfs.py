"""Hermetic tests for batch_planktpr_wfs.py (issue #492).

Synthetic fixtures only: no WFS, no network, no snapshot. The live
endpoint is gone (dated negative 2026-09-13), so every live path is
covered as an explicit no-request branch, and the join shapes are proven
on fixtures only.
"""

import json
import os

import batch_planktpr_wfs as b

HERE = os.path.dirname(os.path.abspath(__file__))
TS_PATH = os.path.join(HERE, "..", "..", "apps", "web", "lib",
                       "layers_planktpr.ts")
SCORER_PATH = os.path.join(HERE, "..", "..", "services", "scoring",
                           "dims_overturn_planktpr.py")

SQUARE = [[[24.7, 59.43], [24.72, 59.43], [24.72, 59.45], [24.7, 59.45]]]


def _feature(**kw):
    base = {"type": "Feature",
            "properties": {"plan_id": "DP-001", "use": "elamumaa",
                           "stage": "kehtestatud", "kov": "Tallinn"},
            "geometry": {"type": "Polygon", "coordinates": SQUARE}}
    base["properties"].update(kw)
    return base


def test_capabilities_picks_designated_use_typename():
    xml = (b'<wfs:WFS_Capabilities xmlns:wfs="http://www.opengis.net/wfs/2.0"'
           b' xmlns="http://www.opengis.net/wfs/2.0">'
           b"<FeatureTypeList>"
           b"<FeatureType><Name>plank:katastriyksus</Name></FeatureType>"
           b"<FeatureType><Name>plank:sihtotstarve</Name></FeatureType>"
           b"</FeatureTypeList></wfs:WFS_Capabilities>")
    assert b.parse_capabilities(xml) == ["plank:sihtotstarve"]


def test_capabilities_spa_shell_is_no_typename():
    # The E-ehitus SPA shell (current live answer): zero WFS markers.
    assert b.parse_capabilities(b"<html><head><title>e-ehituse "
                                   b"platvorm</title></head></html>") == []
    assert b.parse_capabilities(b"not xml at all {{{") == []


def test_feature_to_row_keeps_decree_tallinn_polygons():
    row = b.feature_to_row(_feature())
    assert row is not None
    assert row["plan_id"] == "DP-001"
    assert row["use"] == "elamumaa"
    assert row["rings"] == SQUARE


def test_feature_to_row_refuses_everything_unscored():
    assert b.feature_to_row(_feature(stage="menetluses")) is None
    assert b.feature_to_row(_feature(kov="Viimsi vald")) is None
    assert b.feature_to_row(_feature(use="   ")) is None
    # Unknown codes are kept RAW (classification lives in the scorer +
    # web layer, where unknown stays NULL — the harvester never judges).
    assert b.feature_to_row(_feature(use="mystiline-kood-9")) is not None
    f = _feature()
    f["geometry"] = {"type": "Point", "coordinates": [24.7, 59.43]}
    assert b.feature_to_row(f) is None  # polygons only
    f = _feature()
    f["geometry"] = {"type": "Polygon", "coordinates": [[[24.7, 59.43]]]}
    assert b.feature_to_row(f) is None  # degenerate ring
    assert b.feature_to_row({"junk": True}) is None
    assert b.feature_to_row(None) is None


def test_feature_to_row_multipolygon_outer_rings():
    f = _feature()
    f["geometry"] = {"type": "MultiPolygon",
                     "coordinates": [SQUARE, SQUARE]}
    row = b.feature_to_row(f)
    assert row is not None and row["rings"] == SQUARE + SQUARE


def test_parse_feature_collection_skips_junk():
    body = json.dumps({"type": "FeatureCollection",
                       "features": [_feature(),
                                    _feature(stage="algatatud"),
                                    {"junk": 1}]}).encode()
    rows = b.parse_feature_collection(body)
    assert len(rows) == 1 and rows[0]["plan_id"] == "DP-001"
    assert b.parse_feature_collection(b"{nope") == []
    assert b.parse_feature_collection(b"[1,2]") == []


def test_harvest_no_endpoint_makes_no_requests(tmp_path):
    # Dated negative as an explicit code path: bulk_url None performs no
    # request and writes no sidecar (monkeypatched opener would explode).
    import urllib.request
    def _boom(*a, **k):
        raise AssertionError("network must not be touched")
    old = urllib.request.urlopen
    urllib.request.urlopen = _boom
    try:
        assert b.harvest(str(tmp_path), bulk_url=None) is None
        assert not os.path.exists(os.path.join(str(tmp_path), "plank",
                                               "areas.json"))
    finally:
        urllib.request.urlopen = old


def test_harvest_cache_hit_makes_no_request(tmp_path):
    plank = os.path.join(str(tmp_path), "plank")
    os.makedirs(plank)
    dest = os.path.join(plank, "areas.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump([], fh)
    import urllib.request
    def _boom(*a, **k):
        raise AssertionError("cache hit must not request")
    old = urllib.request.urlopen
    urllib.request.urlopen = _boom
    try:
        assert b.harvest(str(tmp_path), bulk_url="https://example.invalid") == dest
    finally:
        urllib.request.urlopen = old


def test_use_bands_drift():
    # First-cut bands mirrored in three places (builder + scorer + web);
    # changing one without the others is a drift bug.
    assert b.USE_BANDS == {"residential": 80, "mixed": 60, "commercial": 35,
                           "restricted": 20}
    assert b.DECREE_STAGE == "kehtestatud"
    scorer = open(SCORER_PATH, encoding="utf-8").read()
    assert ('USE_BANDS = {"residential": 80, "mixed": 60, "commercial": 35,\n'
            '             "restricted": 20}') in scorer
    assert 'DECREE_STAGE = "kehtestatud"' in scorer
    ts = open(TS_PATH, encoding="utf-8").read()
    assert "residential: 80" in ts
    assert "mixed: 60" in ts
    assert "commercial: 35" in ts
    assert "restricted: 20" in ts
    assert 'PLANKTPR_DECREE_STAGE = "kehtestatud"' in ts
    assert "sigma: 0.5" in ts
