"""Tests for batch_b10c_utility.py (Group 10 batch-C utility raster builders).

Hermetic: hand-made fixture geojson + synthetic graphs only, never the
network and never the real snapshot PBF. Run:
python3 -m pytest scripts/build/test_batch_b10c.py -q
"""

import base64
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import walk_raster as wr  # noqa: E402
from batch_b10c_utility import (  # noqa: E402
    LAYER_DEFAULTS,
    LAYER_PRED,
    build_points_layer,
    dedupe_points,
    is_broadcast,
    is_telecom,
    is_wastepoint,
    is_waterpoint,
)
from walk_graph import Graph, hav_km, key_of  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "batch_b10c_demo.geojson")


def test_predicates_match_verified_snapshot_tags():
    # Confirmed telecom only: generic/church towers excluded (p52's own).
    assert is_telecom({"man_made": "mast", "tower:type": "communication"})
    assert is_telecom({"man_made": "communications_tower"})
    assert not is_telecom({"man_made": "tower", "tourism": "viewpoint"})
    assert not is_telecom({"man_made": "mast"})
    assert not is_telecom(None)
    # Broadcast wins over telecom on dual-tagged masts (scorer parity).
    assert is_broadcast({"man_made": "mast", "communication:television": "yes"})
    assert not is_telecom({"man_made": "mast", "communication:television": "yes"})
    assert is_broadcast({"man_made": "antenna"})
    assert is_broadcast({"communication:radio": "yes"})
    assert not is_broadcast({"man_made": "mast", "tower:type": "communication"})
    assert not is_broadcast(None)
    # Water: wells, springs, taps.
    assert is_waterpoint({"man_made": "water_well"})
    assert is_waterpoint({"natural": "spring"})
    assert is_waterpoint({"amenity": "drinking_water"})
    assert not is_waterpoint({"amenity": "waste_disposal"})
    assert not is_waterpoint(None)
    # Waste: collection points, never litter bins or plants.
    assert is_wastepoint({"amenity": "waste_disposal"})
    assert is_wastepoint({"amenity": "recycling"})
    assert not is_wastepoint({"amenity": "waste_basket"})
    assert not is_wastepoint({"man_made": "wastewater_plant"})
    assert not is_wastepoint(None)


def test_resolve_fixture_counts_per_predicate():
    # Fixture: 2 telecom (mast + comms tower), 1 broadcast mast, 1 antenna,
    # 3 water points, 1 waste_disposal + 1 way-mapped recycling polygon,
    # 1 waste basket (excluded), 1 church tower (excluded), 1 street.
    assert len(wr.resolve_pois(FIXTURE, is_telecom)[0]) == 2
    assert len(wr.resolve_pois(FIXTURE, is_broadcast)[0]) == 2
    assert len(wr.resolve_pois(FIXTURE, is_waterpoint)[0]) == 3
    # The recycling polygon centroids (way-mapped collection points are
    # the rule, not the exception — node-only would drop them, PR #118).
    assert len(wr.resolve_pois(FIXTURE, is_wastepoint)[0]) == 2
    assert len(wr.resolve_pois(FIXTURE, LAYER_PRED["redundancy"])[0]) == 2


def test_dedupe_points_merges_colocated_only():
    feats = [(24.7, 59.43, 1.0), (24.70001, 59.43001, 1.0), (24.71, 59.44, 1.0)]
    out = dedupe_points(feats)
    assert len(out) == 2


def test_calibration_matches_ts_contract():
    # Locked with BATCH10C_BONUS / BATCH10C_DECAY in layers_batch10c.ts
    # (BONUS is the single source of halves — the old HALVES dict is
    # gone). Parse the TS source and fail on drift either direction.
    assert LAYER_DEFAULTS == {
        "water": {"sigma": 0.5, "half": 1, "kind": "area"},
        "waste": {"sigma": 0.3, "half": 6, "kind": "area"},
        "fiber": {"sigma": 0.3, "half": 50, "kind": "area"},
        "mobile": {"sigma": 1.0, "half": None, "kind": "cover"},
    }
    ts = open(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "apps", "web", "lib", "layers_batch10c.ts",
        ),
        encoding="utf-8",
    ).read()
    assert "BATCH10C_HALVES" not in ts, "HALVES dict must stay deleted"
    m = re.search(r"BATCH10C_DECAY[^=]*=\s*\{(.*?)\};", ts, re.S)
    assert m, "DECAY block not found"
    b = re.search(r"BATCH10C_BONUS[^=]*=\s*\{(.*?)\};", ts, re.S)
    assert b, "BONUS block not found"
    for layer, vals in LAYER_DEFAULTS.items():
        mm = re.search(layer + r":\s*([\d.]+)", m.group(1))
        assert mm, "%s missing from DECAY" % layer
        assert float(mm.group(1)) == vals["sigma"]
        bm = re.search(layer + r":\s*\{\s*kind:\s*\"(\w+)\"", b.group(1))
        assert bm, "%s missing from BONUS" % layer
        assert bm.group(1) == vals["kind"], layer
        if vals["kind"] == "area":
            hm = re.search(layer + r":\s*\{[^}]*half:\s*([\d.]+)", b.group(1))
            assert hm and float(hm.group(1)) == vals["half"], layer
        else:
            assert "half" not in re.search(
                layer + r":\s*\{[^}]*\}", b.group(1)).group(0), layer


def test_fiber_builder_reads_address_json_and_thins_overlay(tmp_path):
    # TTJA import shape: [{lon, lat}] — junk entries skipped, overlay
    # thinned to FIBER_OVERLAY_CAP, raster stamped from the FULL set.
    # Note the honesty floor: ONE covered address scores 100*1/51 < 3,
    # i.e. null — a lone farmhouse is not area coverage; clusters read.
    import batch_b10c_utility as B
    pts = [{"lon": 24.7536 + dx, "lat": 59.4372 + dy}
           for dx, dy in ((0, 0), (0.001, 0), (-0.001, 0),
                          (0, 0.001), (0, -0.001))]
    pts.append({"lon": "x", "lat": 59.44})  # junk, skipped
    fp = tmp_path / "fiber-addrs.json"
    fp.write_text(json.dumps(pts), encoding="utf-8")
    dp = tmp_path / "derived-fiber.json"
    g = _chain(24.70, 2, step=0.0002)
    grid = wr.Grid((24.69, 59.42, 24.79, 59.45))
    score_of, contract = B.build_fiber_layer(
        g, grid, 50, 0.3, str(fp), str(dp))
    assert contract == {"half": 50, "sigma": 0.3}
    k = grid.cell_of(24.7536, 59.4372)
    assert k is not None
    # Five addresses in one kernel: S ~= 4.5 -> 100*4.5/54.5 ~= 8.3.
    assert 5.0 < score_of(k) < 12.0
    sample = json.loads(dp.read_text(encoding="utf-8"))
    assert len(sample) == 5 and all(set(p) == {"lon", "lat", "a"}
                                   for p in sample)


def test_stamp_cover_disc_gradient():
    # Coverage discs, not density blobs: a 1 km measured footprint reads
    # 100 at the centroid, mid values mid-radius, ~0 at the observed
    # edge, and None outside (unknown, never zero). Overlapping discs
    # max-merge — covered is covered, coverage never stacks.
    import batch_b10c_utility as B
    grid = wr.Grid((24.69, 59.42, 24.79, 59.45))
    # Centroids planted exactly on 75 m cell centers, so the middle cell
    # reads exactly 100*(1-0/r) = 100: 1 km disc A + overlapping 0.5 km
    # disc B. Probe longitudes are cell centers east/west on the same row
    # (verified distances: 0.45 / 0.97 / 1.05 km from A).
    A = grid.center_of(grid.cell_of(24.74, 59.435))
    C = grid.center_of(grid.cell_of(24.755, 59.435))
    n = B.stamp_cover(grid, [(A[0], A[1], 1.0), (C[0], C[1], 0.5)])
    assert n == 2
    score_of = B.cover_scores(grid)
    assert score_of(grid.cell_of(*A)) == 100
    # Mid-radius east (0.45 km): 1-0.45/1.0 -> 55 (C reads 25: less).
    assert score_of(grid.cell_of(24.74821149333583, A[1])) == pytest.approx(55, abs=2)
    # West edge (0.97 km, outside C): observed boundary -> 3, kept.
    assert score_of(grid.cell_of(24.7233571478666, A[1])) == pytest.approx(3, abs=2)
    # One cell further west (1.05 km): outside every disc -> unknown.
    assert score_of(grid.cell_of(24.72204902442085, A[1])) is None
    # Far outside: unknown, never zero.
    assert score_of(grid.cell_of(24.70, 59.45)) is None
    # Overlap max-merges (covered is covered): max(63, 10) = 63 — below
    # their sum (73): no stacking.
    assert score_of(grid.cell_of(24.74690336989008, A[1])) == pytest.approx(63, abs=2)


def test_mobile_builder_stamps_cover_from_ranges(tmp_path):
    # OpenCellID import shape: [{lon, lat, tags:{radio, operaator,
    # ulatus_m}}] — the RANGE drives the disc; points without one carry
    # no measurement and are skipped, never zero-filled.
    import batch_b10c_utility as B
    grid = wr.Grid((24.69, 59.42, 24.79, 59.45))
    # Elisa centroid planted exactly on a cell center -> that cell is 100.
    A = grid.center_of(grid.cell_of(24.74, 59.435))
    pts = [
        {"lon": A[0], "lat": A[1],
         "tags": {"radio": "LTE", "operaator": "Elisa", "ulatus_m": "1000"}},
        {"lon": 24.76, "lat": 59.44,
         "tags": {"radio": "LTE", "operaator": "Telia", "ulatus_m": "500"}},
        {"lon": 24.70, "lat": 59.43,
         "tags": {"radio": "LTE", "operaator": "Elisa"}},  # no range
        {"lon": "x", "lat": 59.44},  # junk
    ]
    mp = tmp_path / "mobile.json"
    mp.write_text(json.dumps(pts), encoding="utf-8")
    dp = tmp_path / "derived-mobile.json"
    g = _chain(24.70, 2, step=0.0002)
    score_of, contract = B.build_mobile_layer(
        g, grid, None, 1.0, str(mp), str(dp))
    assert contract == {"half": None, "sigma": 1.0}
    assert score_of(grid.cell_of(*A)) == 100
    # The Telia cell center sits <= 53 m off its centroid: >= 89.
    assert score_of(grid.cell_of(24.76, 59.44)) >= 89
    # The no-range site contributes no coverage (unknown, never zero)...
    assert score_of(grid.cell_of(24.70, 59.43)) is None
    assert score_of(grid.cell_of(24.70, 59.45)) is None
    sample = json.loads(dp.read_text(encoding="utf-8"))
    # Overlay dots mark every valid measurement SITE (range or not, tags
    # kept so the client can draw discs); junk never reaches the overlay.
    assert len(sample) == 3
    norange = [p for p in sample if p["lon"] == 24.70][0]
    assert "ulatus_m" not in norange.get("tags", {})
    assert all("ulatus_m" in p["tags"] or p["lon"] == 24.70
               for p in sample)


def _chain(x0, n, step=0.001):
    g = Graph()
    for i in range(n - 1):
        a, b = key_of(x0 + i * step, 59.44), key_of(x0 + (i + 1) * step, 59.44)
        g.add_edge(a, b, hav_km(x0 + i * step, 59.44, x0 + (i + 1) * step, 59.44))
    return g


def test_points_builder_end_to_end_on_synthetic_graph():
    # The way-mapped recycling polygon off the toy graph (Euclidean
    # fallback tier) centroids to one weight-1 source: its cell scores
    # 100*1/(1+6) ~= 14, far cells stay unknown (255), never zero.
    g = _chain(24.70, 2, step=0.0002)  # ~11 m apart: same 75 m cell
    grid = wr.Grid((24.69, 59.42, 24.79, 59.45))
    score_of, contract = build_points_layer(g, grid, 6, 0.3, FIXTURE, "waste")
    assert contract == {"half": 6, "sigma": 0.3}
    k = grid.cell_of(24.7505, 59.4305)
    assert k is not None
    assert score_of(k) == pytest.approx(100.0 / 7.0, abs=2.0)
    raw = wr.score_bytes(grid, score_of)
    assert raw[k] == round(100.0 / 7.0)
    far = grid.cell_of(24.691, 59.449)
    assert far is not None and raw[far] == 255


def test_wire_doc_carries_contract_and_unknown():
    g = _chain(24.70, 2, step=0.0002)
    grid = wr.Grid((24.69, 59.43, 24.71, 59.45))
    score_of, _ = build_points_layer(g, grid, 6, 0.3, FIXTURE, "waste")
    doc = wr.encode_raster(grid, score_of, half=6, sigma=0.3)
    assert doc["half"] == 6 and doc["sigma"] == 0.3
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    raw = base64.b64decode(doc["data"])
    assert len(raw) == grid.cols * grid.rows
    assert 255 in raw  # unknown cells survive encoding


def test_builder_is_hermetic_no_network_imports():
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "batch_b10c_utility.py")).read()
    for mod in ("urllib", "requests", "socket", "http.client", "overpass"):
        assert mod not in src
