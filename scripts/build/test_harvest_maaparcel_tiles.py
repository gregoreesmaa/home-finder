"""Tests for scripts/build/harvest_maaparcel_tiles.py (issue #520).

Hermetic: tile planning, URL shape, merge/dedupe, and the harvest
loop run against stub fetchers only — no network, no snapshot. The
live WFS contract (base URL, WFS 2.0.0, count=100, lon-lat bbox) is
the production scorer's (dims_overturn_maa.py::layer_url); the
maintainer validates the shape with --probe (1 GET) before a full run.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from harvest_maaparcel_tiles import (  # noqa: E402
    COUNT_PER_TILE,
    PARCEL_TYPENAME,
    STOP,
    TALLINN_BBOX,
    WFS_BASE,
    count_features,
    harvest,
    merge_features,
    merge_only,
    plan_tiles,
    probe,
    subdivide,
    tile_url,
    valid_tile_body,
)


def _feat(tunnus, lon=24.75, lat=59.433):
    return {"type": "Feature",
            "properties": {"tunnus": tunnus, "omvorm": "Eraomand"},
            "geometry": {"type": "Polygon",
                         "coordinates": [[[lon, lat], [lon + 0.001, lat],
                                          [lon + 0.001, lat + 0.001],
                                          [lon, lat + 0.001],
                                          [lon, lat]]]}}


def _body(*tunnused):
    return json.dumps({"type": "FeatureCollection",
                       "features": [_feat(t) for t in tunnused]}).encode()


def test_plan_tiles_covers_bbox_gapless():
    tiles = plan_tiles([24.5, 59.35, 24.9, 59.5])
    assert len(tiles) == 20 * 15  # 0.02 x 0.01 windows
    assert tiles[0][:2] == [24.5, 59.35]
    assert tiles[-1][2:] == [24.9, 59.5]
    for t in tiles:  # every tile within span, edges tile continuously
        assert 0 < t[2] - t[0] <= 0.02 + 1e-12
        assert 0 < t[3] - t[1] <= 0.01 + 1e-12
    lons = sorted({(t[0], t[2]) for t in tiles})
    assert lons[0][0] == 24.5 and lons[-1][1] == 24.9
    for (_, a), (b, _) in zip(lons, lons[1:]):
        assert a == b  # no gaps, no overlaps


def test_tile_url_uses_scorer_contract():
    url = tile_url([24.74, 59.428, 24.76, 59.438])
    assert url.startswith(WFS_BASE)
    assert "version=2.0.0" in url
    assert "typeName=%s" % PARCEL_TYPENAME in url
    assert "count=%d" % COUNT_PER_TILE in url
    assert COUNT_PER_TILE <= 100  # politeness cap never raised
    assert "outputFormat=application/json" in url
    assert "bbox=24.74,59.428,24.76,59.438,EPSG:4326" in url


def test_subdivide_covers_parent_exactly():
    kids = subdivide([24.74, 59.428, 24.76, 59.438])
    assert len(kids) == 4
    assert min(k[0] for k in kids) == 24.74
    assert max(k[2] for k in kids) == 24.76
    assert min(k[1] for k in kids) == 59.428
    assert max(k[3] for k in kids) == 59.438


def test_count_features_rejects_junk_never_data():
    assert count_features(_body("a:1", "a:2")) == 2
    assert count_features(b"<html>error</html>") is None
    assert count_features(b"") is None
    assert valid_tile_body(_body("a:1")) is True
    assert valid_tile_body(b"tiny") is False
    assert valid_tile_body(b"<html>" + b"x" * 500) is False


def test_merge_dedupes_by_tunnus_counts_the_rest():
    a = {"type": "FeatureCollection",
         "features": [_feat("a:1"), _feat("a:2"),
                      {"type": "Feature", "properties": {},
                       "geometry": None}]}
    b = {"type": "FeatureCollection",
         "features": [_feat("a:2"), _feat("a:3")]}
    merged, stats = merge_features([a, b])
    assert stats["parcels"] == 3  # a:1, a:2, a:3
    assert stats["duplicates"] == 1  # a:2 twice (subdivision overlap)
    assert stats["untunnused"] == 1  # kept, builder skips it
    assert len(merged) == 4
    assert merge_features([{}, {"features": None}])[1]["parcels"] == 0


def test_harvest_pulls_tiles_merges_and_manifests(tmp_path):
    cache = str(tmp_path)
    seen_urls = []

    def fake_fetch(url):
        seen_urls.append(url)
        assert "count=100" in url  # cap rides every request
        return _body("t:%d" % len(seen_urls))

    m = harvest(cache, bbox=[24.74, 59.428, 24.76, 59.438],
                ttl_s=10 ** 9, fetcher=fake_fetch, sleeper=lambda s: None)
    assert m["stopped"] is False
    assert m["tiles_planned"] == 1
    assert m["merge"]["parcels"] == 1
    assert os.path.exists(os.path.join(cache, "kk_ky_tallinn_merged.json"))
    assert os.path.exists(os.path.join(cache, "harvest_manifest.json"))
    # Resume: fresh caches win, no new requests.
    m2 = harvest(cache, bbox=[24.74, 59.428, 24.76, 59.438],
                 ttl_s=10 ** 9, fetcher=fake_fetch, sleeper=lambda s: None)
    assert len(seen_urls) == 1
    assert m2["tiles"][0]["status"] == "cached"


def test_harvest_subdivides_full_tiles_never_raises_count(tmp_path):
    calls = []

    def fake_fetch(url):
        calls.append(url)
        if "count=" in url:
            assert "count=100" in url
        # Parent tile full -> children sparse (unique tunnus per child).
        if "bbox=24.74,59.428,24.76,59.438,EPSG:4326" in url:
            return _body(*["p:%d" % i for i in range(100)])
        return _body("kid:%d" % len(calls))

    m = harvest(tmp_path, bbox=[24.74, 59.428, 24.76, 59.438],
                ttl_s=0, fetcher=fake_fetch, sleeper=lambda s: None)
    statuses = [t["status"] for t in m["tiles"]]
    assert "subdivided" in statuses
    assert m["merge"]["parcels"] == 4  # 4 sparse children
    assert all("count=100" in u for u in calls)


def test_harvest_flags_truncated_at_minimum_span(tmp_path):
    def fake_fetch(url):
        return _body(*["d:%d" % i for i in range(100)])

    m = harvest(tmp_path, bbox=[24.75, 59.433, 24.751, 59.434],
                ttl_s=0, fetcher=fake_fetch, sleeper=lambda s: None)
    assert any(t.get("truncated") for t in m["tiles"])
    # Honest partial: flagged in-manifest, still merged, never silent.
    assert m["merge"]["features"] >= 100


def test_harvest_stops_on_429_keeps_partial(tmp_path):
    calls = []

    def fake_fetch(url):
        calls.append(url)
        if len(calls) == 1:
            return _body("first:1")
        return STOP

    m = harvest(tmp_path, bbox=[24.5, 59.35, 24.54, 59.37],
                ttl_s=0, fetcher=fake_fetch, sleeper=lambda s: None)
    assert m["stopped"] is True
    assert len(calls) == 2  # no retry, no further tiles
    assert m["merge"]["parcels"] == 1  # partial kept, honestly flagged


def test_harvest_errors_never_cached_continues(tmp_path):
    def fake_fetch(url):
        return None  # transport error

    m = harvest(tmp_path, bbox=[24.74, 59.428, 24.76, 59.438],
                ttl_s=0, fetcher=fake_fetch, sleeper=lambda s: None)
    assert m["tiles"][0]["status"] == "error"
    assert m["merge"]["parcels"] == 0
    assert not os.path.exists(
        os.path.join(tmp_path, "kk_ky_tallinn_merged.json"))
    assert os.listdir(tmp_path) == ["harvest_manifest.json"]


def test_merge_only_rebuilds_offline(tmp_path):
    (tmp_path / "tile_a.geojson").write_bytes(_body("m:1", "m:2"))
    (tmp_path / "tile_b.geojson").write_bytes(_body("m:2", "m:3"))
    stats = merge_only(str(tmp_path))
    assert stats["parcels"] == 3 and stats["duplicates"] == 1


def test_probe_single_get_shape(tmp_path):
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return _body("probe:1")

    rep = probe(fetcher=fake_fetch)
    assert len(calls) == 1  # exactly one GET
    assert "count=1" in calls[0]
    assert rep["features"] == 1 and rep["valid"] is True
    assert probe(fetcher=lambda u: STOP)["observed"] == "HTTP-429-STOP"


def test_no_urllib_outside_fetch_helper():
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "harvest_maaparcel_tiles.py"), encoding="utf-8").read()
    assert src.count("urlopen") == 1  # single GET site, 429-aware
    assert "requests" not in src
