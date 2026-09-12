"""Tests for batch_g11d_leftovers.py (Group 11 leftover-B raster builders).

Hermetic: hand-made fixture geojson + synthetic graphs only, never the
network and never the real snapshot PBF. Run:
python3 -m pytest scripts/build/test_batch_g11d.py -q
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import walk_raster as wr  # noqa: E402
from batch_g11d_leftovers import (  # noqa: E402
    FAR_SCORE,
    G11D_LAYERS,
    LAYER_DEFAULTS,
    _quiet_score_fn,
    build_points_layer,
    build_trailprivacy,
    build_way_layer,
    is_mailbox,
    is_postal,
    land_cells_of,
    quiet_score,
    resolve_service_km,
)
from walk_graph import Graph, hav_km, key_of  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "batch_g11d_demo.geojson")


def test_layers_cover_batch_params():
    assert G11D_LAYERS == ["alley", "mailbox", "postal", "trailprivacy"]
    # p317 is a documented no-map: no builder branch, no calibration.
    assert set(LAYER_DEFAULTS) == set(G11D_LAYERS)


def test_predicates_match_verified_snapshot_tags():
    assert is_mailbox({"amenity": "post_box"})
    assert is_mailbox({"amenity": "letter_box"})
    assert not is_mailbox({"amenity": "post_office"})  # p470, not p346
    assert not is_mailbox({"amenity": "parcel_locker"})
    assert not is_mailbox(None)
    assert is_postal({"amenity": "post_office"})
    assert is_postal({"amenity": "parcel_locker"})
    assert not is_postal({"amenity": "post_box"})
    assert not is_postal(None)


def test_contract_numbers_match_registry():
    # Locked with G11D_BONUS/G11D_DECAY in layers_group11d.ts (contract
    # probe fails on drift).
    assert LAYER_DEFAULTS["mailbox"] == {"sigma": 0.5, "half": 2.5}
    assert LAYER_DEFAULTS["postal"] == {"sigma": 0.8, "half": 12.0}
    assert LAYER_DEFAULTS["alley"] == {"sigma": 0.5, "half": 0.3}
    assert LAYER_DEFAULTS["trailprivacy"]["sigma"] == 0.5
    assert LAYER_DEFAULTS["trailprivacy"]["wire_half"] == 1500


def test_service_km_resolver_filters_key_value_and_conserves_km():
    pts, stats = resolve_service_km(FIXTURE)
    # way/10 + dual-tagged way/14 (service=alley); driveway + paths excluded.
    assert stats["kept"] == 2
    total = sum(w for _, _, w in pts)
    expected = (
        hav_km(24.7, 59.43, 24.701, 59.4305)
        + hav_km(24.701, 59.4305, 24.702, 59.431)
        + hav_km(24.695, 59.422, 24.696, 59.4225)
    )
    assert total == pytest.approx(expected, rel=1e-9)


def test_quiet_score_inverts_and_floors_at_far():
    assert FAR_SCORE == 90
    assert quiet_score(0.0, 1.5) == 90
    assert quiet_score(-2.0, 1.5) == 90
    assert quiet_score(1.5, 1.5) == 50
    assert quiet_score(13.5, 1.5) == pytest.approx(10.0)
    # Barely-touched fringe reads near-perfect, trail-free land reads 90:
    # documented 4-sigma edge, both ends honest (private either way).
    assert quiet_score(0.001, 1.5) > 90


def _toy_graph():
    g = Graph()
    a, b, c = key_of(24.75, 59.4372), key_of(24.752, 59.4375), key_of(24.76, 59.44)
    g.add_edge(a, b, hav_km(24.75, 59.4372, 24.752, 59.4375))
    g.add_edge(b, c, hav_km(24.752, 59.4375, 24.76, 59.44))
    return g


def test_points_layer_stamps_snapshot_tags():
    g = _toy_graph()
    grid = wr.Grid((24.74, 59.43, 24.77, 59.445))
    score_of, contract = build_points_layer(g, grid, 1.5, 0.5, FIXTURE, "mailbox")
    assert contract == {"half": 1.5, "sigma": 0.5}
    k = grid.cell_of(24.75, 59.4372)
    assert score_of(k) is not None and score_of(k) > 50
    # Postal scores the office + locker; the nearer source wins (kernel
    # spillover means the box cell still reads something -- real physics).
    grid2 = wr.Grid((24.74, 59.43, 24.77, 59.445))
    score2, _ = build_points_layer(g, grid2, 4.0, 0.8, FIXTURE, "postal")
    at_office = score2(grid2.cell_of(24.76, 59.44))
    at_boxes = score2(grid2.cell_of(24.75, 59.4372))
    # Two features at half=4 read low-thirties (singletons read low, B1).
    assert at_office is not None and at_office > 30
    assert at_boxes is not None and at_office > at_boxes > 0


def test_way_layer_scores_alley_km_not_driveways():
    g = _toy_graph()
    grid = wr.Grid((24.69, 59.42, 24.71, 59.435))
    score_of, contract = build_way_layer(
        g, grid, 0.5, 0.5, FIXTURE, "alley", resolve_service_km
    )
    assert contract == {"half": 0.5, "sigma": 0.5}
    assert score_of(grid.cell_of(24.701, 59.4305)) is not None
    assert score_of(grid.cell_of(24.711, 59.4305)) is None


def test_path_resolver_keeps_paths_not_footways():
    pts, stats = wr.resolve_length_km(FIXTURE, {"path"})
    # way/12 + dual-tagged way/14 (highway=path); footway excluded.
    assert stats["kept"] == 2
    assert all(abs(lon - 24.6935) > 0.001 for lon, lat, _ in pts)


def _trail_graph():
    g = Graph()
    p, q = key_of(24.691, 59.4205), key_of(24.692, 59.421)
    g.add_edge(p, q, hav_km(24.691, 59.4205, 24.692, 59.421))
    # Far edge: >2 km (4-sigma cutoff) from every path vertex, so its
    # cells stay unstamped and read FAR_SCORE.
    a, b = key_of(24.66, 59.405), key_of(24.661, 59.4055)
    g.add_edge(a, b, hav_km(24.66, 59.405, 24.661, 59.4055))
    return g


def test_trailprivacy_inverts_with_land_mask():
    g = _trail_graph()
    grid = wr.Grid((24.655, 59.40, 24.70, 59.43))
    score_of, contract = build_trailprivacy(g, grid, 1.5, 1500, 0.5, FIXTURE)
    assert contract == {"half": 1500, "sigma": 0.5}
    on_path = score_of(grid.cell_of(24.691, 59.4205))
    assert on_path is not None and on_path < FAR_SCORE
    # Walk-network land without trails reads the honest far value...
    land = land_cells_of(g, grid)
    assert len(land) > 0
    far = [k for k in land if k not in grid.acc]
    assert far, "toy graph must leave unstamped land cells"
    assert all(score_of(k) == FAR_SCORE for k in far)
    # ...while cells the graph never reaches (open water) stay unknown.
    sea = [k for k in range(grid.cols * grid.rows) if k not in land and k not in grid.acc]
    assert sea, "toy grid must leave off-network cells"
    assert all(score_of(k) is None for k in sea)


def _load_county(layer):
    snap = os.environ.get(
        "HF_SNAPSHOT_DIR", os.path.join(os.path.expanduser("~"), "hf-data", "2026-09-12")
    )
    with open(os.path.join(snap, "osm", "%s-walk-raster.json" % layer), encoding="utf-8") as f:
        doc = json.load(f)
    import base64 as _b64

    return doc, _b64.b64decode(doc["data"])


def _serve_nearest(doc, raw, view, cols, rows):
    """Raw-master nearest serve (no hole-fill: the fill would hide the
    artifacts this test hunts)."""
    bb = doc["bbox"]
    out = bytearray(cols * rows)
    for iy in range(rows):
        lat = view[1] + ((iy + 0.5) / rows) * (view[3] - view[1])
        gy = int((lat - bb["minlat"]) / (bb["maxlat"] - bb["minlat"]) * doc["rows"])
        for ix in range(cols):
            lon = view[0] + ((ix + 0.5) / cols) * (view[2] - view[0])
            gx = int((lon - bb["minlon"]) / (bb["maxlon"] - bb["minlon"]) * doc["cols"])
            gx = min(max(gx, 0), doc["cols"] - 1)
            gy = min(max(gy, 0), doc["rows"] - 1)
            out[iy * cols + ix] = raw[gy * doc["cols"] + gx]
    return out


def _speckle(out, cols, rows):
    """Isolated 255 amid known (same definition as test_redgap_255)."""
    n = 0
    for yy in range(1, rows - 1):
        for xx in range(1, cols - 1):
            i = yy * cols + xx
            if out[i] == 255 and all(
                out[(yy + dy) * cols + xx + dx] != 255
                for dy in (-1, 0, 1)
                for dx in (-1, 0, 1)
                if (dx, dy) != (0, 0)
            ):
                n += 1
    return n


def test_dense_tallinn_no_speckle():
    """Speckle rescan (redgap precedent): no isolated unknowns amid
    known over dense Tallinn; trailprivacy's land mask keeps the whole
    city view known."""
    snap = os.environ.get(
        "HF_SNAPSHOT_DIR", os.path.join(os.path.expanduser("~"), "hf-data", "2026-09-12")
    )
    if not os.path.exists(os.path.join(snap, "osm", "mailbox-walk-raster.json")):
        pytest.skip("G11D masters not built in this snapshot")
    view, cols, rows = (24.70, 59.415, 24.77, 59.445), 128, 64
    for layer in G11D_LAYERS:
        doc, raw = _load_county(layer)
        out = _serve_nearest(doc, raw, view, cols, rows)
        assert _speckle(out, cols, rows) == 0, layer
    # trailprivacy's land mask cannot cover off-network city patches
    # (rail yards, the Ülemiste lake shore, industrial parcels): those
    # stay honestly unknown, non-speckled (asserted above), bounded here.
    doc, raw = _load_county("trailprivacy")
    out = _serve_nearest(doc, raw, view, cols, rows)
    assert sum(1 for v in out if v == 255) < 0.10 * cols * rows


def test_derived_points_are_honest_json(tmp_path):
    g = _toy_graph()
    grid = wr.Grid((24.74, 59.43, 24.77, 59.445))
    out = str(tmp_path / "derived-mailbox.json")
    build_points_layer(g, grid, 1.5, 0.5, FIXTURE, "mailbox", derived=out)
    pts = json.load(open(out, encoding="utf-8"))
    # node/1 + node/3 share coords (~20 m dedupe merges them) + node/2.
    assert len(pts) == 2
    for p in pts:
        assert set(p) <= {"lon", "lat", "a"}
        assert p["a"] == 1
