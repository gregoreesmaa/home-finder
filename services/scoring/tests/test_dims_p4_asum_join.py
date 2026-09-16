"""P4 asum polygon-join kernel (issue #525): hermetic tests.

No network: fetch_polygons_snapshot is never called for a live pull
here (its contract — polite monthly pulls, file cache, TTL,
transport errors raise — is covered via the pure cache_is_fresh
helper, a cache-hit fetch test that performs no GET, and the
typename-None refusal that raises before any network). Parsing,
containment, the join, and medians run on fully synthetic fixtures:
unit-square polygons, never real boundaries.
"""

import json
import os
import re

import dims_p4_asum_join as join
from dims_p4_asum_join import (
    MIN_N,
    cache_is_fresh,
    describe_asum,
    describe_joined_store,
    fetch_polygons_snapshot,
    group_by_asum,
    join_rows_to_polygons,
    parse_polygons_geojson,
    polygon_contains,
)

#: Synthetic two-asum GeoJSON (models the OBSERVED 2026-09-16 wire
#: shape only: FeatureCollection + Polygon/MultiPolygon rings).
#: Never ingested.
SYNTH_GEOJSON = json.dumps({
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature", "id": "asum.1",
         "properties": {"nimi": "Kalamaja"},
         "geometry": {"type": "Polygon", "coordinates": [[
             [0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]]}},
        {"type": "Feature", "id": "asum.2",
         "properties": {"nimi": "Pelgulinn"},
         "geometry": {"type": "MultiPolygon", "coordinates": [[[
             [2.0, 2.0], [3.0, 2.0], [3.0, 3.0], [2.0, 3.0], [2.0, 2.0]]]]}},
    ],
})

POLYS = parse_polygons_geojson(SYNTH_GEOJSON)


def grow(price, area=50.0, lon=0.5, lat=0.5, **over):
    base = {"price": price, "area_m2": area, "lon": lon, "lat": lat}
    base.update(over)
    return base


KALAMAJA_5 = [grow(250000), grow(260000), grow(240000, 60.0),
              grow(300000, 62.0), grow(200000)]


def test_parse_names_polygons():
    assert [p["name"] for p in POLYS] == ["Kalamaja", "Pelgulinn"]
    assert len(POLYS[1]["polys"]) == 1


def test_parse_rejects_garbage():
    for bad in ("not json", '{"a": 1}',
                '{"type": "FeatureCollection"}'):
        try:
            parse_polygons_geojson(bad)
        except ValueError:
            continue
        raise AssertionError("no ValueError for %r" % bad)


def test_containment_inside_outside_boundary():
    assert polygon_contains(0.5, 0.5, POLYS[0]) is True
    assert polygon_contains(5.0, 5.0, POLYS[0]) is False
    assert polygon_contains(0.0, 0.5, POLYS[0]) is True  # boundary in
    assert polygon_contains(2.5, 2.5, POLYS[1]) is True
    assert polygon_contains(0.5, 0.5, POLYS[1]) is False


def test_join_attaches_exact_key_counts_skipped():
    rows = KALAMAJA_5 + [
        grow(999999, lon=9.0, lat=9.0),   # outside every polygon
        {"price": 100000, "area_m2": 50.0},  # coordless
        {"address": "Kalamaja, Telliskivi 49"},  # free text never joins
    ]
    joined, skipped = join_rows_to_polygons(rows, POLYS)
    assert len(joined) == 5
    assert skipped == 3
    assert {r["asum"] for r in joined} == {"Kalamaja"}


def test_join_empty_polygons_joins_nothing():
    joined, skipped = join_rows_to_polygons(KALAMAJA_5, [])
    assert joined == []
    assert skipped == 5


def test_thick_group_pins_exact_median():
    joined, _ = join_rows_to_polygons(KALAMAJA_5, POLYS)
    store = describe_joined_store(joined)
    median, reason = store["Kalamaja"]
    assert round(median, 2) == 4838.71  # 300000/62, middle of five
    assert "hinnang" in reason
    assert "EI OLE" not in reason
    assert "5 liitunud" in reason


def test_thin_group_stays_null_with_n_labeled():
    joined, _ = join_rows_to_polygons(KALAMAJA_5[:2], POLYS)
    store = describe_joined_store(joined)
    median, reason = store["Kalamaja"]
    assert median is None
    assert "EI OLE" in reason
    assert "2 liitunud" in reason


def test_empty_store_is_honest_empty():
    assert describe_joined_store([]) == {}


def test_min_n_parity_three_ways():
    assert MIN_N == 5
    import dims_p4_own_asum as own
    assert own.MIN_N == MIN_N
    for rel in (os.path.join("apps", "web", "lib", "layers_asumedia.ts"),):
        ts = os.path.join(os.path.dirname(__file__), "..", "..", "..", rel)
        src = open(ts, encoding="utf-8").read()
        m = re.search(r"export const ASUMEDIA_MIN_N\s*=\s*(\d+)", src)
        assert m is not None, "ASUMEDIA_MIN_N missing in layers_asumedia.ts"
        assert int(m.group(1)) == MIN_N


def test_fetch_refuses_without_typename_before_network(tmp_path):
    try:
        fetch_polygons_snapshot(cache_dir=str(tmp_path), typename=None)
    except RuntimeError as exc:
        assert "EI OLE" in str(exc)
        return
    raise AssertionError("no RuntimeError for typename=None")


def test_fetch_cache_hit_performs_no_request(tmp_path):
    from dims_p4_asum_join import _cache_path
    dest = _cache_path(str(tmp_path))
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(SYNTH_GEOJSON)
    body, provenance = fetch_polygons_snapshot(
        cache_dir=str(tmp_path), typename="ehak:linnade_piirid")
    assert provenance == "cache"
    assert "Kalamaja" in body
    assert cache_is_fresh(dest) is True


def test_cache_is_fresh_false_when_missing(tmp_path):
    assert cache_is_fresh(str(tmp_path / "nope.json")) is False


def test_module_touches_no_shared_files():
    import inspect
    src = inspect.getsource(join)
    assert "import livability" not in src
    assert "import dims_p4_own_asum" not in src
    assert "from dims_p4_own_asum import" not in src
    assert "WEIGHTS =" not in src
    assert "WEIGHTS[" not in src
