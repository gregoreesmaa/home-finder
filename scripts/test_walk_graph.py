"""Hermetic tests for walk_graph.py (no PBF needed; tiny fixtures). Run:
python3 -m pytest scripts/test_walk_graph.py -q
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from walk_graph import (  # noqa: E402
    SnapIndex,
    build_graph,
    car_ok,
    components,
    dijkstra,
    foot_ok,
    key_of,
    load_graph,
    lonlat_of,
    save_graph,
)


def _write_geojson(feats):
    f = tempfile.NamedTemporaryFile("w", suffix=".geojson", delete=False)
    f.write('{"type":"FeatureCollection","features":[\n')
    for feat in feats:
        f.write(json.dumps(feat) + ",\n")
    f.write("]}\n")
    f.close()
    return f.name


def _line(coords, props):
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "LineString", "coordinates": coords},
    }


def test_key_roundtrip_with_negatives():
    for lon, lat in [(24.75, 59.44), (-0.12, 51.5), (0.0, 0.0)]:
        x, y = lonlat_of(key_of(lon, lat))
        assert abs(x - lon) < 1e-7 and abs(y - lat) < 1e-7


def test_profile_tag_matrix():
    assert foot_ok({"highway": "footway"})
    assert foot_ok({"highway": "residential"})
    assert foot_ok({"highway": "trunk"})  # sidewalks assumed; errs Euclidean
    assert foot_ok({"railway": "platform"})
    assert foot_ok({"public_transport": "platform"})
    assert not foot_ok({"highway": "footway", "foot": "no"})
    assert not foot_ok({"highway": "residential", "access": "no"})
    assert not foot_ok({"highway": "motorway"})
    assert foot_ok({"highway": "residential", "access": "private"})  # private ignored
    assert car_ok({"highway": "primary"})
    assert car_ok({"highway": "service"})
    assert car_ok({"highway": "motorway"})
    assert not car_ok({"highway": "footway"})
    assert not car_ok({"highway": "residential", "access": "no"})


def test_railway_severs_until_bridge_connects():
    # Two east-west streets 200 m apart; a railway runs between them but is
    # NOT part of the walk graph (no highway tag) -- severance is automatic.
    # A bridge way shares endpoint nodes with both streets: only it joins.
    # Junctions are shared vertices (as in OSM): the bridge meets each
    # street at an explicit common node.
    south = [[24.70, 59.4400], [24.705, 59.4400], [24.71, 59.4400]]
    north = [[24.70, 59.4418], [24.705, 59.4418], [24.71, 59.4418]]
    bridge = [[24.705, 59.4400], [24.705, 59.4409], [24.705, 59.4418]]
    props = {"highway": "residential"}
    p = _write_geojson([_line(south, props), _line(north, props)])
    try:
        g, stats = build_graph(p, "foot")
        assert stats["kept"] == 2
        assert len(components(g)) == 2  # severed
        a, b = key_of(24.70, 59.44), key_of(24.70, 59.4418)
        assert a in g.adj and b in g.adj
        assert b not in dijkstra(g, a, 5.0)  # unreachable within 5 km
    finally:
        os.unlink(p)
    p = _write_geojson([_line(south, props), _line(north, props), _line(bridge, props)])
    try:
        g, _ = build_graph(p, "foot")
        assert len(components(g)) == 1  # bridge reconnects
        a, b = key_of(24.70, 59.44), key_of(24.70, 59.4418)
        d = dijkstra(g, a, 5.0)[b]
        # Detour via bridge ~0.7 km, far above the 0.2 km Euclidean gap.
        assert d > 0.5, d
    finally:
        os.unlink(p)


def test_car_respects_oneway_foot_ignores_it():
    line = [[24.70, 59.44], [24.71, 59.44]]
    props = {"highway": "residential", "oneway": "yes"}
    p = _write_geojson([_line(line, props)])
    try:
        gf, _ = build_graph(p, "foot")
        gc, _ = build_graph(p, "car")
        a, b = key_of(24.70, 59.44), key_of(24.71, 59.44)
        assert b in dijkstra(gf, a, 5.0) and a in dijkstra(gf, b, 5.0)
        assert b in dijkstra(gc, a, 5.0)
        assert a not in dijkstra(gc, b, 5.0)  # oneway blocks return
    finally:
        os.unlink(p)


def test_plaza_ring_and_save_load_roundtrip():
    plaza = {
        "type": "Feature",
        "properties": {"highway": "pedestrian"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[24.70, 59.44], [24.71, 59.44], [24.71, 59.45], [24.70, 59.44]]],
        },
    }
    p = _write_geojson([plaza])
    q = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
    try:
        g, stats = build_graph(p, "foot")
        assert stats["kept"] == 1
        a = key_of(24.70, 59.44)
        before = dijkstra(g, a, 5.0)
        assert len(before) == 3  # outer ring walkable
        save_graph(g, q)
        g2 = load_graph(q)
        after = dijkstra(g2, a, 5.0)
        assert set(after) == set(before)
        for k in before:
            assert abs(after[k] - before[k]) < 0.002  # meter rounding only
    finally:
        os.unlink(p)
        os.unlink(q)


def test_snap_index_finds_near_vertex():
    line = [[24.70, 59.44], [24.71, 59.44]]
    p = _write_geojson([_line(line, {"highway": "path"})])
    try:
        g, _ = build_graph(p, "foot")
        idx = SnapIndex(g)
        k, d = idx.nearest(24.7001, 59.4401, 0.5)
        assert k is not None and d < 0.05
        k, _ = idx.nearest(25.0, 59.0, 0.5)
        assert k is None  # too far: isolated, caller falls back
    finally:
        os.unlink(p)
