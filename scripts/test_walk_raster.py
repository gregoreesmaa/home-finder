"""Tests for walk_raster.py (feature resolvers, network scoring, contracts).

Mirrors apps/web/lib/server/snapshot.ts + layers.ts scoring numbers; any
divergence here is a bug in one of the two. Run:
python3 -m pytest scripts/test_walk_raster.py -q
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from walk_graph import Graph  # noqa: E402
from walk_raster import (  # noqa: E402
    NOMINAL_AREA,
    multi_source_dist,
    nominal_area,
    resolve_parks,
    resolve_schools,
    saturate,
    school_bonus,
    stop_mode,
)


def test_nominal_area_mirrors_ts():
    assert nominal_area({"leisure": "playground"}) == 0.1
    assert nominal_area({"leisure": "garden"}) == 0.15
    assert nominal_area({"leisure": "park"}) == 2.0
    assert nominal_area({}) == 0.3
    assert nominal_area(None) == 0.3
    assert set(NOMINAL_AREA) == {"playground", "garden", "park"}


def test_stop_mode_mirrors_ts():
    assert stop_mode({"railway": "tram_stop"}) == "tram"
    assert stop_mode({"railway": "station"}) == "train"
    assert stop_mode({"public_transport": "station"}) == "train"
    assert stop_mode({"highway": "bus_stop"}) == "bus"
    assert stop_mode({"public_transport": "platform"}) == "bus"
    assert stop_mode({"amenity": "school"}) is None
    assert stop_mode(None) is None


def _square(cx, cy, half):
    return [[cx - half, cy - half], [cx + half, cy - half],
            [cx + half, cy + half], [cx - half, cy + half]]


def test_resolve_parks_subdivides_drops_nominals():
    # 63 ha polygon, sigma 0.35 -> kernel-adequate ~21 subcells sharing 63 ha.
    areas = [{"b": [24.74, 59.43, 24.76, 59.45], "a": 63.0, "r": [_square(24.75, 59.44, 0.01)]}]
    points = [
        {"lon": 24.75, "lat": 59.44, "tags": {"leisure": "playground"}},  # inside -> dropped
        {"lon": 24.80, "lat": 59.44, "tags": {"leisure": "playground"}},  # nominal 0.1
        {"lon": 24.81, "lat": 59.44, "tags": {"leisure": "garden"}},  # nominal 0.15
    ]
    feats = resolve_parks(points, areas, sigma=0.35)
    subs = [f for f in feats if f[2] > 1.0]
    assert len(subs) > 10  # dense, not the old 25-cap-style 2
    assert abs(sum(f[2] for f in subs) - 63.0) < 0.5
    weights = sorted(f[2] for f in feats)
    assert abs(sum(weights) - 63.25) < 0.5
    assert weights[0] == 0.1 and weights[1] == 0.15


def test_resolve_parks_conserves_sparse_polygons():
    # Thin diagonal strip: few centers land in-ring, but stamped hectares
    # must still total the polygon's area.
    strip = [[24.8, 59.44], [24.9, 59.45], [24.9, 59.448], [24.8, 59.438]]
    areas = [{"b": [24.8, 59.44, 24.9, 59.45], "a": 40.0, "r": [strip]}]
    feats = resolve_parks([], areas, sigma=0.25)
    assert len(feats) > 0
    assert abs(sum(f[2] for f in feats) - 40.0) < 0.5


def test_resolve_parks_tiny_poly_becomes_point():
    areas = [{"b": [24.80, 59.44, 24.8005, 59.4405], "a": 0.2, "r": [_square(24.80025, 59.44025, 0.0002)]}]
    feats = resolve_parks([], areas, sigma=0.35)
    assert len(feats) == 1
    assert abs(feats[0][2] - 0.2) < 1e-9


def test_resolve_schools_passes_tags_through():
    points = [
        {"lon": 24.75, "lat": 59.44, "tags": {"amenity": "school"}},
        {"lon": 24.76, "lat": 59.44, "tags": {"amenity": "kindergarten"}},
        {"lon": 24.77, "lat": 59.44},
    ]
    out = resolve_schools(points)
    assert out[0][2] == "school"
    assert out[1][2] == "kindergarten"
    assert out[2][2] is None


def _chain(x0, n, step=0.001):
    g = Graph()
    for i in range(n - 1):
        from walk_raster import key_of, hav_km
        a, b = key_of(x0 + i * step, 59.44), key_of(x0 + (i + 1) * step, 59.44)
        g.add_edge(a, b, hav_km(x0 + i * step, 59.44, x0 + (i + 1) * step, 59.44))
    return g


def test_multi_source_respects_barriers_and_cutoff():
    from walk_raster import key_of
    g = _chain(24.70, 4)
    east = _chain(24.80, 4)
    for k, v in east.adj.items():
        g.adj.setdefault(k, []).extend(v)
    s_west = key_of(24.70, 59.44)
    s_east = key_of(24.80, 59.44)
    d = multi_source_dist(g, [s_west, s_east], cutoff_km=5.0)
    assert abs(d[s_west] - 0.0) < 1e-9
    assert abs(d[s_east] - 0.0) < 1e-9
    # Two chains never join: a west vertex never sees the east source.
    mid_west = key_of(24.702, 59.44)
    assert mid_west in d and d[mid_west] < 0.3
    # Cutoff binds: nothing beyond it is labeled.
    d2 = multi_source_dist(g, [s_west], cutoff_km=0.05)
    assert s_west in d2 and mid_west not in d2


def _poi_feature(fid, tags, geom):
    return {"type": "Feature", "id": fid, "properties": tags, "geometry": geom}


def _write_geojson(feats):
    import json as _json
    import tempfile as _tf
    f = _tf.NamedTemporaryFile("w", suffix=".geojson", delete=False)
    f.write('{"type":"FeatureCollection","features":[\n')
    for feat in feats:
        f.write(_json.dumps(feat) + ",\n")
    f.write("]}\n")
    f.close()
    return f.name


def _line(coords, props):
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "LineString", "coordinates": coords},
    }


def test_poi_predicates():
    from walk_raster import is_grocery, is_medical
    assert is_grocery({"shop": "supermarket"})
    assert is_grocery({"shop": "convenience"})
    assert is_grocery({"shop": "marketplace"})
    assert not is_grocery({"shop": "clothes"})
    assert not is_grocery({"amenity": "pharmacy"})
    assert is_medical({"amenity": "pharmacy"})
    assert is_medical({"amenity": "doctors"})
    assert is_medical({"amenity": "dentist"})
    # Hospitals/clinics are p124 (specialized), not everyday p20.
    assert not is_medical({"amenity": "hospital"})
    assert not is_medical({"amenity": "clinic"})
    assert not is_medical({"amenity": "restaurant"})


def test_resolve_pois_geometry_and_dedupe():
    from walk_raster import resolve_pois, is_grocery
    feats = [
        _poi_feature("n1", {"shop": "supermarket"}, {"type": "Point", "coordinates": [24.75, 59.44]}),
        _poi_feature("n1", {"shop": "supermarket"}, {"type": "Point", "coordinates": [24.75, 59.44]}),
        _poi_feature("w1", {"shop": "convenience"},
                     {"type": "LineString", "coordinates": [[24.76, 59.44], [24.762, 59.44], [24.764, 59.44]]}),
        _poi_feature("w2", {"shop": "clothes"}, {"type": "Point", "coordinates": [24.77, 59.44]}),
        _poi_feature("r1", {"shop": "supermarket"},
                     {"type": "Polygon", "coordinates": [[[24.78, 59.44], [24.782, 59.44], [24.782, 59.442], [24.78, 59.44]]]}),
    ]
    p = _write_geojson(feats)
    try:
        out, stats = resolve_pois(p, is_grocery)
        assert stats["kept"] == 3  # dup id + clothes dropped
        by_lon = sorted((round(x, 5), round(y, 5), w) for x, y, w in out)
        assert by_lon[0] == (24.75, 59.44, 1.0)  # point as-is
        assert by_lon[1][0] == 24.762  # line midpoint vertex
        assert by_lon[2] == (24.781, 59.441, 1.0)  # polygon bbox center
    finally:
        os.unlink(p)


def test_walkability_counts_true_junctions_only():
    from walk_raster import resolve_walkability
    from walk_graph import Graph, key_of, hav_km
    # Cross through a shared center node (degree 4); arm ends are degree 1.
    g2 = Graph()
    c = key_of(24.705, 59.44)
    for end in [(24.70, 59.44), (24.71, 59.44), (24.705, 59.435), (24.705, 59.445)]:
        g2.add_edge(c, key_of(*end), hav_km(24.705, 59.44, *end))
    # Parallel twin edge must not fake a junction (distinct neighbors!).
    t1, t2 = key_of(24.80, 59.44), key_of(24.81, 59.44)
    g2.add_edge(t1, t2, 0.5)
    g2.add_edge(t1, t2, 0.5)
    out = resolve_walkability(g2)
    assert len(out) == 1
    assert abs(out[0][0] - 24.705) < 1e-9 and out[0][2] == 1.0


def test_ped_km_conserves_length():
    from walk_raster import resolve_length_km, PED_HIGHWAY
    line = [[24.70, 59.44], [24.71, 59.44]]  # 0.01 deg lon @59.44N ~= 0.566 km
    p = _write_geojson([_line(line, {"highway": "footway"}), _line(line, {"highway": "residential"})])
    try:
        out, stats = resolve_length_km(p, PED_HIGHWAY)
        assert stats["kept"] == 1  # residential is street, not ped infra
        assert abs(sum(w for _, _, w in out) - 0.566) < 0.01
    finally:
        os.unlink(p)


def test_scoring_math_matches_ts():
    assert abs(saturate(57, 3) - 95.0) < 0.01  # parks: 100*57/60
    assert abs(saturate(3, 3) - 50.0) < 1e-9
    assert saturate(0, 3) == 0.0
    # schools variety: per 12, cap 36 (mirror bonusSpecFor).
    assert school_bonus(1) == 0
    assert school_bonus(2) == 12
    assert school_bonus(4) == 36
    assert school_bonus(9) == 36


def test_hav_km_scales_degrees_to_km():
    # 0.01 deg lon @59.44N ~= 0.573 km; 0.01 deg lat ~= 1.106 km.
    # Swapped arg order reads these ~2x off (rural N-S stretch).
    from walk_raster import hav_km
    assert hav_km(24.70, 59.44, 24.71, 59.44) == pytest.approx(0.573, abs=0.02)
    assert hav_km(24.70, 59.44, 24.70, 59.45) == pytest.approx(1.106, abs=0.02)


def test_euclid_fill_is_circular():
    # One stop on a 75 m grid: equidistant E and N cells must read the
    # same distance (no N-S stretch).
    from walk_raster import Grid, euclid_nearest_fill
    grid = Grid((24.69, 59.43, 24.71, 59.45))
    out = euclid_nearest_fill(grid, [(24.70, 59.44)], 1.0)
    ke = grid.cell_of(24.70573, 59.44)  # ~0.33 km E
    kn = grid.cell_of(24.70, 59.44297)  # ~0.33 km N
    assert ke is not None and kn is not None
    assert out[ke] == pytest.approx(out[kn], rel=0.05)


def test_stamp_sum_counts_field_once_per_cell():
    # One feature whose Dijkstra tree visits TWO nodes in the same grid
    # cell: the cell must read w*K(min_d) (the field sampled once), not
    # the per-node sum (graph-density inflation).
    import pytest as _pytest
    from walk_raster import Grid, kernel, stamp_sum
    g = _chain(24.70, 2, step=0.0002)  # ~11 m apart: same 75 m cell
    grid = Grid((24.69, 59.43, 24.71, 59.45))
    snapped, euclid = stamp_sum(grid, g, [(24.70, 59.44, 10.0, None)], 0.25, 1.0)
    assert (snapped, euclid) == (1, 0)
    k = grid.cell_of(24.70, 59.44)
    assert k is not None
    assert grid.acc[k] == _pytest.approx(10.0 * kernel(0.0, 0.25))
    assert grid.acc[k] < 15.0  # two-node sum would read ~20
