"""Walk-graph scorer legs for pedestrian-access layers (issue #814).

Follow-up to the #808 audit finding (map = foot-graph walk rasters,
scorer = bird-flight haversine): the migrated legs route the
foot-graph sidecar (services/scoring/walk_access.py) when a graph is
injected, else the legacy bird-flight path.

* walk_access unit tests (bands, cutoff, graph, routing, fallback).
* Parity identity: at nominal detour (route == haversine * WALK_DETOUR)
  the walk score equals the legacy score on every migrated band table.
* Per-leg walk tests with a fixture graph, one per migrated family.
* Legacy equivalence: graph=None output is bit-identical (incl. far
  POIs beyond any window), and an unroutable graph falls back to
  exactly the legacy output.

No network: fixture graphs only, never the real snapshot sidecar.
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from livability import _band  # noqa: E402
from walk_access import (  # noqa: E402
    ROUTE_CANDIDATES,
    SNAP_MAX_M,
    WALK_DETOUR,
    WALK_TAG,
    FootGraph,
    bands_for,
    count_within_walk_m,
    load_foot_graph,
    nearest_walk_m,
    walk_bands,
    walk_cutoff,
    walk_dist_m,
)

TALLINN = (59.4372, 24.7536)  # (lat, lon)


def _hav(lat1, lon1, lat2, lon2):
    r = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (lat1, lon1, lat2, lon2))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(
        (lo2 - lo1) / 2
    ) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _poi(kind, lat, lon, **extra):
    d = {"kind": kind, "lat": lat, "lon": lon}
    d.update(extra)
    return d


def line_graph(*lonlats, step_m=None):
    """FootGraph chain through [lon, lat] nodes; explicit weights.

    Edge weights default to the haversine span (detour 1.0 corridor);
    pass step_m to force an exact per-hop weight instead.
    """
    g = FootGraph()
    for lon, lat in lonlats:
        g.nodes.append((lon, lat))
    for i in range(len(lonlats) - 1):
        (lon1, lat1), (lon2, lat2) = lonlats[i], lonlats[i + 1]
        w = step_m if step_m is not None else _hav(lat1, lon1, lat2, lon2)
        g.add_edge(i, i + 1, w)
    return g


def detour_graph(origin, plat, plon, factor=WALK_DETOUR):
    """Two-node graph whose route is haversine * factor exactly.

    Nodes sit exactly on the origin/POI (snap 0 m); the single edge
    weighs hav * factor. Lets legs prove the parity identity: at
    nominal detour the walk score equals the legacy score.
    """
    g = FootGraph()
    g.nodes.append((origin[1], origin[0]))
    g.nodes.append((plon, plat))
    g.add_edge(0, 1, _hav(origin[0], origin[1], plat, plon) * factor)
    return g


def far_graph():
    """Graph whose nodes are nowhere near Tallinn (snap always misses)."""
    g = FootGraph()
    g.nodes.append((0.0, 0.0))
    g.nodes.append((0.001, 0.0))
    g.add_edge(0, 1, 100.0)
    return g


# ---------------------------------------------------------------------------
# walk_access units
# ---------------------------------------------------------------------------


def test_walk_bands_rescale_and_inf_passthrough():
    assert walk_bands([(300, 100), (600, 85), (float("inf"), 10)]) == [
        (390, 100),
        (780, 85),
        (float("inf"), 10),
    ]
    # Integer-valued edges that stay integral come back as ints.
    assert walk_bands([(500, 80)], factor=1.2) == [(600, 80)]
    # Non-integral stays float.
    assert walk_bands([(301, 100)]) == [(391.3, 100)]


def test_walk_cutoff_and_bands_for():
    assert walk_cutoff(1000.0) == 1300.0
    legacy = [(300, 100), (600, 85)]
    assert bands_for("walk", legacy) == walk_bands(legacy)
    assert bands_for("haversine", legacy) is legacy
    assert bands_for("anything-else", legacy) is legacy


def test_parity_identity_bands():
    """h * factor on rescaled bands == h on legacy bands (all tables)."""
    tables = [
        [(300, 100), (600, 85), (1000, 70), (1500, 50), (2500, 30)],
        [(400, 100), (800, 80), (1200, 60)],
        [(800, 100), (1500, 80), (2000, 60)],
        [(50, 20), (150, 40), (300, 60), (600, 80), (float("inf"), 95)],
        [(0.5, 80), (1.0, 65), (2.0, 50)],
        [(300, 85), (600, 70), (1000, 55)],
    ]
    for bands in tables:
        scaled = walk_bands(bands)
        for h in (10.0, 250.0, 450.0, 900.0, 1400.0, 1900.0, 2400.0):
            if h > bands[-1][0] and bands[-1][0] != float("inf"):
                continue
            assert _band(h * WALK_DETOUR, scaled) == _band(h, bands)


def test_foot_graph_route_and_cutoff():
    g = line_graph((24.75, 59.44), (24.751, 59.44), (24.752, 59.44))
    assert g.route_m(0, 0, 10000.0) == 0.0
    full = g.route_m(0, 2, 10000.0)
    assert full is not None and full > 0
    assert g.route_m(0, 2, full - 0.01) is None  # over cutoff
    assert g.route_m(0, 2, full) == full  # at cutoff
    assert len(g) == 3


def test_foot_graph_disconnected_and_bad_edges():
    g = FootGraph()
    g.nodes.append((24.75, 59.44))
    g.nodes.append((24.751, 59.44))
    assert g.route_m(0, 1, 10000.0) is None  # no edge
    g.add_edge(0, 0, 50.0)  # self-loop ignored
    g.add_edge(0, 1, -5.0)  # non-positive ignored
    g.add_edge(0, 1, 0.0)  # non-positive ignored
    assert g.route_m(0, 1, 10000.0) is None
    g.add_edge(0, 1, 60.0)
    assert g.route_m(0, 1, 10000.0) == 60.0


def test_snap_miss_and_shortest_path_choice():
    g = FootGraph()
    assert g.snap_m(24.75, 59.44) is None  # empty graph
    g.nodes.append((24.75, 59.44))
    g.nodes.append((24.76, 59.44))  # ~570 m east
    hit = g.snap_m(24.75, 59.44)
    assert hit is not None and hit[0] == 0 and hit[1] < 1.0
    assert g.snap_m(0.0, 0.0) is None  # beyond SNAP_MAX_M
    # Shortest path prefers the cheap two-hop over the dear direct edge.
    g.add_edge(0, 1, 1000.0)
    g.nodes.append((24.755, 59.4405))
    g.add_edge(0, 2, 100.0)
    g.add_edge(2, 1, 100.0)
    assert g.route_m(0, 1, 10000.0) == 200.0


def test_load_foot_graph_contract(tmp_path):
    assert load_foot_graph(str(tmp_path / "missing.json")) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert load_foot_graph(str(bad)) is None
    wrong = tmp_path / "wrong.json"
    wrong.write_text(json.dumps({"nodes": [], "nope": []}), encoding="utf-8")
    assert load_foot_graph(str(wrong)) is None
    ok = tmp_path / "graph.json"
    ok.write_text(
        json.dumps(
            {"nodes": [[24.75, 59.44], [24.751, 59.44]],
             "edges": [[0, 1, 60.0], [1, 9, 5.0], [0, 0, 5.0]]}
        ),
        encoding="utf-8",
    )
    g = load_foot_graph(str(ok))
    assert g is not None and len(g) == 2
    assert g.route_m(0, 1, 10000.0) == 60.0  # bad edges skipped
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"nodes": [], "edges": []}), encoding="utf-8")
    assert load_foot_graph(str(empty)) is None


def test_nearest_walk_m_legacy_equivalence_beyond_window():
    """graph=None returns the global minimum even beyond the window."""
    pois = [_poi("school", TALLINN[0] + 0.03, TALLINN[1])]  # ~3.3 km
    m, method = nearest_walk_m(TALLINN, pois, {"school"}, 500.0, None)
    assert method == "haversine"
    assert m == _hav(TALLINN[0], TALLINN[1], TALLINN[0] + 0.03, TALLINN[1])
    assert nearest_walk_m(TALLINN, [], {"school"}, 500.0, None) == (None, "haversine")
    # Garbage POIs never crash and never win.
    junk = [{"kind": "school"}, {"kind": "school", "lat": None, "lon": 1.0},
            {"kind": "school", "lat": True, "lon": 1.0},
            {"kind": "school", "lat": "x", "lon": "y"}, {"nope": 1}]
    assert nearest_walk_m(TALLINN, junk, {"school"}, 500.0, None) == (None, "haversine")


def test_nearest_walk_m_routes_and_falls_back():
    plat, plon = TALLINN[0] + 0.001, TALLINN[1]  # ~111 m north
    pois = [_poi("school", plat, plon)]
    g = line_graph((TALLINN[1], TALLINN[0]), (plon, plat))
    m, method = nearest_walk_m(TALLINN, pois, {"school"}, 1500.0, g)
    assert method == "walk"
    assert m == _hav(TALLINN[0], TALLINN[1], plat, plon)
    # Unroutable graph (snap miss) falls back to the legacy measurement.
    m2, method2 = nearest_walk_m(TALLINN, pois, {"school"}, 1500.0, far_graph())
    m0, method0 = nearest_walk_m(TALLINN, pois, {"school"}, 1500.0, None)
    assert (m2, method2) == (m0, method0)


def test_nearest_walk_m_picks_best_route_not_best_haversine():
    """Two POIs: nearer-haversine is off-graph (snap miss), farther routes."""
    near = _poi("school", TALLINN[0] + 0.0036, TALLINN[1])  # ~400 m north
    far_lat, far_lon = TALLINN[0], TALLINN[1] + 0.0105  # ~600 m east
    far = _poi("school", far_lat, far_lon)
    # Nodes sit exactly on origin + far POI: near is >300 m from both.
    g = line_graph((TALLINN[1], TALLINN[0]), (far_lon, far_lat))
    m, method = nearest_walk_m(TALLINN, [near, far], {"school"}, 1500.0, g)
    assert method == "walk"
    assert m == _hav(TALLINN[0], TALLINN[1], far_lat, far_lon)


def test_count_within_walk_m_paths():
    p1 = _poi("bus_stop", TALLINN[0] + 0.001, TALLINN[1])  # ~111 m
    p2 = _poi("bus_stop", TALLINN[0] + 0.01, TALLINN[1])  # ~1.1 km
    assert count_within_walk_m(TALLINN, [p1, p2], {"bus_stop"}, 500.0, None) == (1, "haversine")
    g = line_graph((TALLINN[1], TALLINN[0]),
                   (TALLINN[1], TALLINN[0] + 0.001),
                   (TALLINN[1], TALLINN[0] + 0.01))
    n, method = count_within_walk_m(TALLINN, [p1, p2], {"bus_stop"}, 500.0, g)
    assert method == "walk" and n == 1  # 1.1 km routes beyond 650 m
    n2, method2 = count_within_walk_m(TALLINN, [p1, p2], {"bus_stop"}, 500.0, far_graph())
    assert (n2, method2) == (1, "haversine")


def test_walk_dist_m_snap_miss_is_none():
    g = line_graph((24.75, 59.44), (24.751, 59.44))
    assert walk_dist_m(g, TALLINN, 59.44, 24.7505, 5000.0) is None
    assert ROUTE_CANDIDATES >= 1 and SNAP_MAX_M > 0


# ---------------------------------------------------------------------------
# Per-leg migration tests (one per migrated family)
# ---------------------------------------------------------------------------

from dims_group06 import (  # noqa: E402
    dim_commission,
    dim_heritage_district,
    score_group06,
)
from dims_group06b import (  # noqa: E402
    dim_antiques,
    dim_plaster_craft,
    dim_woodfire,
    score_group06b,
)
from dims_group10b import dim_emergency  # noqa: E402
from dims_group10c import dim_waste, dim_water  # noqa: E402
from dims_group11 import (  # noqa: E402
    dim_forage,
    dim_medical_special,
    dim_rec_special,
    dim_school_bus,
    score_group11,
)
from dims_group11b import (  # noqa: E402
    dim_alley,
    dim_letterbox,
    dim_postal,
    dim_trail_privacy,
    dim_worship,
    score_group11 as score_group11b,
)
from dims_group11c import score_group11c  # noqa: E402
from dims_group11d import score_group11d  # noqa: E402
from dims_group12 import dim_commute  # noqa: E402
from dims_p4_ehis_map import dim_school_proximity  # noqa: E402
from dims_p4_medre import dim_gp_open_status, dim_gp_proximity  # noqa: E402
from dims_p4_peatus import (  # noqa: E402
    dim_delights_access,
    dim_third_places,
    score_p4_peatus,
)
from dims_p4_poi import dim_poi_library  # noqa: E402
from dims_p4_sportreg import dim_sport_hall, dim_ujulad_pool  # noqa: E402
from livability import (  # noqa: E402
    dim_green,
    dim_schools,
    dim_services,
    dim_transit,
    enrich_row,
)


def corridor_to(plat, plon):
    """Detour-1.0 corridor graph from TALLINN to (plat, plon)."""
    return line_graph((TALLINN[1], TALLINN[0]), (plon, plat))


def test_livability_access_legs_walk():
    plat, plon = TALLINN[0] + 0.002, TALLINN[1]  # ~222 m
    g = corridor_to(plat, plon)
    for fn, kind in ((dim_schools, "school"), (dim_green, "park"),
                     (dim_services, "supermarket")):
        v0, r0 = fn(TALLINN, [_poi(kind, plat, plon)])
        v1, r1 = fn(TALLINN, [_poi(kind, plat, plon)], g)
        assert (v0, v1) == (100, 100)
        assert WALK_TAG in r1 and WALK_TAG not in r0
    # Transit counts: a stop at 600 m is outside the 500 m haversine
    # radius but inside the 650 m walk radius (recalibration by design).
    stop = _poi("bus_stop", TALLINN[0] + 0.0054, TALLINN[1])  # ~600 m
    g2 = corridor_to(TALLINN[0] + 0.0054, TALLINN[1])
    assert dim_transit(TALLINN, [stop])[0] == 35
    v, r = dim_transit(TALLINN, [stop], g2)
    assert v == 60 and WALK_TAG in r
    # enrich_row routes the access legs through.
    geo = {"lat": TALLINN[0], "lon": TALLINN[1],
           "pois": [_poi("school", plat, plon)]}
    _, reasons, dims = enrich_row("x", "Harju", geo=geo, graph=g)
    assert dims["schools"] == 100 and any(WALK_TAG in x for x in reasons)


def test_group11_walk_and_parity():
    plat, plon = TALLINN[0] + 0.002, TALLINN[1]
    g = corridor_to(plat, plon)
    v, r = dim_rec_special(TALLINN, [_poi("rec_special", plat, plon)], g)
    assert v == 100 and WALK_TAG in r
    v, r = dim_forage(TALLINN, [_poi("forest", plat, plon)], g)
    assert v == 100 and WALK_TAG in r
    v, r = dim_school_bus(
        TALLINN, [_poi("school", plat, plon),
                  _poi("bus_stop", plat, plon)], g)
    assert v == 100 and WALK_TAG in r
    # Parity at nominal detour: walk score == legacy score.
    dlat = 0.004  # ~445 m
    pois = [_poi("rec_special", TALLINN[0] + dlat, TALLINN[1])]
    dg = detour_graph(TALLINN, TALLINN[0] + dlat, TALLINN[1])
    assert (dim_rec_special(TALLINN, pois, dg)[0]
            == dim_rec_special(TALLINN, pois)[0] == 100)
    dims, _ = score_group11(
        TALLINN, [_poi("school", plat, plon), _poi("bus_stop", plat, plon)], g)
    assert dims["school_bus"] == 100


def test_group11b_walk_and_inverted_parity():
    plat, plon = TALLINN[0] + 0.002, TALLINN[1]  # ~222 m
    g = corridor_to(plat, plon)
    v, r = dim_letterbox(TALLINN, [_poi("letter_box", plat, plon)], g)
    assert v == 100 and WALK_TAG in r
    v, r = dim_postal(TALLINN, [_poi("post_office", plat, plon)], g)
    assert v == 100 and WALK_TAG in r
    v, r = dim_alley(TALLINN, [_poi("alley", plat, plon)], g)
    assert v == 70 and WALK_TAG in r
    v, r = dim_worship(TALLINN, [_poi("worship", plat, plon)], g)
    assert v == 100 and WALK_TAG in r
    # Inverted trail privacy keeps its shape on the rescaled bands:
    # 222 m hav -> 60; nominal-detour walk (289 m) -> 60.
    tpoi = [_poi("trail", TALLINN[0] + 0.002, TALLINN[1])]
    assert dim_trail_privacy(TALLINN, tpoi)[0] == 60
    tg = detour_graph(TALLINN, TALLINN[0] + 0.002, TALLINN[1])
    v, r = dim_trail_privacy(TALLINN, tpoi, tg)
    assert v == 60 and WALK_TAG in r
    out = score_group11b(TALLINN, [_poi("letter_box", plat, plon)], g)
    assert out["letterbox"] == 100
    assert score_group11c(TALLINN, [_poi("worship", plat, plon)], g)["worship"] == 100
    assert score_group11d(TALLINN, [_poi("letter_box", plat, plon)], g)["letterbox"] == 100


def test_group06_counts_walk():
    p1 = _poi("heritage", TALLINN[0] + 0.002, TALLINN[1])
    p2 = _poi("heritage", TALLINN[0] + 0.004, TALLINN[1])
    g = line_graph((TALLINN[1], TALLINN[0]),
                   (TALLINN[1], TALLINN[0] + 0.002),
                   (TALLINN[1], TALLINN[0] + 0.004))
    v, r = dim_heritage_district(TALLINN, [p1, p2], g)
    assert v == 65 and WALK_TAG in r and "~1040 m" in r
    v, r = dim_commission(TALLINN, [p1, p2], g)
    assert v == 55 and WALK_TAG in r
    out = score_group06(TALLINN, [p1], g)
    assert out["heritage_district"] == 45 and out["tax_credits"] is None


def test_group06b_walk():
    plat, plon = TALLINN[0] + 0.002, TALLINN[1]
    g = corridor_to(plat, plon)
    v, r = dim_plaster_craft(TALLINN, [_poi("plasterbld", plat, plon)], g)
    assert v == 50 and WALK_TAG in r and "~650 m" in r
    v, r = dim_antiques(TALLINN, [_poi("antiqueshop", plat, plon)], g)
    assert v == 1 and WALK_TAG in r
    # Antiques gate: 1.9 km routes inside the 2.6 km walk gate -> 1.
    # A 1.5-detour graph cannot route 2.85 km past the 2.6 km cutoff,
    # so it falls back to the legacy measurement (1.9 km -> 1):
    # fallback output is identical to no-graph output by design.
    alat = TALLINN[0] + 0.0171  # ~1.9 km
    ag = corridor_to(alat, TALLINN[1])
    assert dim_antiques(TALLINN, [_poi("antiqueshop", alat, TALLINN[1])])[0] == 1
    assert dim_antiques(TALLINN, [_poi("antiqueshop", alat, TALLINN[1])], ag)[0] == 1
    bg = detour_graph(TALLINN, alat, TALLINN[1], factor=1.5)
    assert dim_antiques(TALLINN, [_poi("antiqueshop", alat, TALLINN[1])], bg) == \
        dim_antiques(TALLINN, [_poi("antiqueshop", alat, TALLINN[1])])
    # Woodfire inversion parity at nominal detour: 100 m hav -> 40,
    # 130 m walk -> 40.
    wpoi = [_poi("woodbld", TALLINN[0] + 0.0009, TALLINN[1])]
    assert dim_woodfire(TALLINN, wpoi)[0] == 40
    wg = detour_graph(TALLINN, TALLINN[0] + 0.0009, TALLINN[1])
    v, r = dim_woodfire(TALLINN, wpoi, wg)
    assert v == 40 and WALK_TAG in r
    out = score_group06b(TALLINN, [_poi("woodbld", plat, plon)], g)
    assert out["woodfire"] == 60 and out["settling"] is None


def test_group10_emergency_water_waste_walk():
    plat, plon = TALLINN[0] + 0.002, TALLINN[1]  # ~222 m
    g = corridor_to(plat, plon)
    v, r = dim_emergency(TALLINN, [_poi("emergency", plat, plon)], g)
    assert v == 100 and WALK_TAG in r
    v, r = dim_water(TALLINN, [_poi("waterpoint", plat, plon)], g)
    assert v == 100 and WALK_TAG in r
    v, r = dim_waste(TALLINN, [_poi("wastepoint", plat, plon)], g)
    assert v == 100 and WALK_TAG in r


def test_group12_commute_walk_minutes():
    stop = _poi("stop_wday", TALLINN[0] + 0.001, TALLINN[1], deps=500)
    g = corridor_to(TALLINN[0] + 0.001, TALLINN[1])
    v0, r0 = dim_commute(TALLINN, [stop])
    v1, r1 = dim_commute(TALLINN, [stop], g)
    # Corridor detour is 1.0: routed metres == haversine, so the minutes
    # model (unchanged table) scores identically; only the reason marks
    # the measured walk leg.
    assert v1 == v0 and v1 is not None
    assert WALK_TAG in r1 and WALK_TAG not in r0


def test_peatus_delights_walk_bands_and_selection():
    plat, plon = TALLINN[0] + 0.0045, TALLINN[1]  # ~500 m
    stop = {"kind": "stop_p4", "lat": plat, "lon": plon,
            "deps_wed": 100, "deps_eve": 10, "deps_sat": 30}
    g = corridor_to(plat, plon)
    v, r = dim_delights_access(TALLINN, [stop], g)
    assert v == 85 and "marsruut" in r and "linnulennult" not in r
    # Nominal-detour parity: 500 m hav -> 85; 650 m walk -> 85.
    dg = detour_graph(TALLINN, plat, plon)
    assert dim_delights_access(TALLINN, [stop], dg)[0] == \
        dim_delights_access(TALLINN, [stop])[0] == 85
    v, r = dim_third_places(TALLINN, [stop], g)
    assert v == 80 and WALK_TAG in r
    out = score_p4_peatus(TALLINN, [stop], g)
    assert out["delights_access"] == 85 and out["third_places"] == 80


def test_dbands_slices_walk():
    plat = TALLINN[0] + 0.0036  # ~0.40 km
    g = corridor_to(plat, TALLINN[1])
    hall = _poi("sport_hall", plat, TALLINN[1], name="Hall")
    v, r = dim_sport_hall(TALLINN, [hall], g)
    assert v == 80 and "jalgsikäik" in r and "linnulennult" not in r
    # Nominal-detour parity: 0.40 km hav -> 80; 0.52 km walk -> 80.
    dg = detour_graph(TALLINN, plat, TALLINN[1])
    assert dim_sport_hall(TALLINN, [hall], dg)[0] == \
        dim_sport_hall(TALLINN, [hall])[0] == 80
    uj = _poi("ujulad_pool", plat, TALLINN[1], name="U",
              inspected="2026-01-01")
    v, r = dim_ujulad_pool(TALLINN, [uj], g)
    assert v == 80 and "2026-01-01" in r
    school = _poi("ehis_school", plat, TALLINN[1], name="Kool")
    assert dim_school_proximity(TALLINN, [school], g)[0] == 80
    gp = _poi("medre_gp", plat, TALLINN[1], address="A")
    assert dim_gp_proximity(TALLINN, [gp], g)[0] == 80
    assert dim_gp_open_status(TALLINN, [gp])[0] is None


def test_poi_long_tail_walk():
    v, r = dim_poi_library(TALLINN, 500.0)
    assert v == 70 and WALK_TAG not in r
    v, r = dim_poi_library(TALLINN, 650.0, walk=True)
    assert v == 70 and WALK_TAG in r
    # Nominal-detour parity: 500 hav -> 70; 650 walk -> 70.
    assert dim_poi_library(TALLINN, 500.0)[0] == \
        dim_poi_library(TALLINN, 650.0, walk=True)[0]
    assert dim_poi_library(TALLINN, 1100.0)[0] is None
    assert dim_poi_library(TALLINN, 1100.0, walk=True)[0] == 55


def test_fallback_is_exactly_legacy():
    """Unroutable graph output == no-graph output (score AND reason)."""
    fg = far_graph()
    plat, plon = TALLINN[0] + 0.002, TALLINN[1]
    cases = [
        (dim_schools, [_poi("school", plat, plon)]),
        (dim_transit, [_poi("bus_stop", plat, plon)]),
        (dim_green, [_poi("park", plat, plon)]),
        (dim_services, [_poi("supermarket", plat, plon)]),
        (dim_rec_special, [_poi("rec_special", plat, plon)]),
        (dim_school_bus, [_poi("school", plat, plon)]),
        (dim_medical_special, [_poi("hospital", plat, plon)]),
        (dim_forage, [_poi("forest", plat, plon)]),
        (dim_letterbox, [_poi("letter_box", plat, plon)]),
        (dim_alley, [_poi("alley", plat, plon)]),
        (dim_trail_privacy, [_poi("trail", plat, plon)]),
        (dim_postal, [_poi("post_office", plat, plon)]),
        (dim_worship, [_poi("worship", plat, plon)]),
        (dim_heritage_district, [_poi("heritage", plat, plon)]),
        (dim_commission, [_poi("heritage", plat, plon)]),
        (dim_plaster_craft, [_poi("plasterbld", plat, plon)]),
        (dim_antiques, [_poi("antiqueshop", plat, plon)]),
        (dim_woodfire, [_poi("woodbld", plat, plon)]),
        (dim_emergency, [_poi("emergency", plat, plon)]),
        (dim_water, [_poi("waterpoint", plat, plon)]),
        (dim_waste, [_poi("wastepoint", plat, plon)]),
    ]
    for fn, pois in cases:
        assert fn(TALLINN, pois, fg) == fn(TALLINN, pois), fn.__name__
    stop = _poi("stop_wday", plat, plon, deps=500)
    assert dim_commute(TALLINN, [stop], fg) == dim_commute(TALLINN, [stop])
    p4 = {"kind": "stop_p4", "lat": plat, "lon": plon,
          "deps_wed": 100, "deps_eve": 20, "deps_sat": 30}
    assert dim_delights_access(TALLINN, [p4], fg) == dim_delights_access(TALLINN, [p4])
    assert dim_third_places(TALLINN, [p4], fg) == dim_third_places(TALLINN, [p4])
    hall = _poi("sport_hall", plat, plon, name="H")
    assert dim_sport_hall(TALLINN, [hall], fg) == dim_sport_hall(TALLINN, [hall])
    assert dim_poi_library(TALLINN, 500.0, walk=False) == dim_poi_library(TALLINN, 500.0)
