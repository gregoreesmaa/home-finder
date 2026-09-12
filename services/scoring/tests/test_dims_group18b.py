"""Hermetic unit tests for Group 18b environmental-exposure dims (issue #124).

No network, no snapshot: all POIs are synthetic. Run from repo root:
  python3 -m pytest services/scoring/tests/test_dims_group18b.py -q
"""

import dims_group18b as G
from dims_group18b import (
    _count_cells_within_m,
    dim_coolisland,
    dim_darksky,
    kinds_from_tags,
    score_group18b,
)

TALLINN = (59.4372, 24.7536)  # city centre reference origin


def poi(kind, metres_north, lon_off=0.0):
    """Synthetic POI `metres_north` metres north of TALLINN."""
    return {"kind": kind, "lat": TALLINN[0] + metres_north / 111320.0,
            "lon": TALLINN[1] + lon_off}


def test_none_when_missing():
    for fn in (dim_darksky, dim_coolisland):
        assert fn(None, [])[0] is None
        assert fn(TALLINN, None)[0] is None
        assert fn(None, None)[0] is None
    dims, reasons = score_group18b(None, None)
    assert set(dims) == {"darksky", "coolisland"}
    assert all(v is None for v in dims.values())
    assert reasons == []


def test_reasons_honest():
    # proksi/(hinnang) everywhere; magnitudes/Celsius/Bortle nowhere.
    _, reasons = score_group18b(
        TALLINN, [poi("lit_area", 100), poi("building", 100)])
    assert len(reasons) == 2
    for r in reasons:
        assert "proksi" in r
        assert "(hinnang" in r
        for bad in ("magnituud", "Bortle", "°C", "Celsius", "dB"):
            assert bad not in r
    for fn in (dim_darksky, dim_coolisland):
        assert "proksi" in fn(None, None)[1]


def spread(kind, n, step_m=21.0):
    """n POIs on a step_m grid centred at TALLINN (one 20 m cell each)."""
    import math
    side = int(math.ceil(math.sqrt(n)))
    pts = []
    for i in range(n):
        dx = (i % side - side // 2) * step_m
        dy = (i // side - side // 2) * step_m
        pts.append({"kind": kind,
                    "lat": TALLINN[0] + dy / 111320.0,
                    "lon": TALLINN[1] + dx / (111320.0 * math.cos(math.radians(TALLINN[0])))})
    return pts


def test_darksky_density():
    # DARK_HALF = 200 cells/400 m: 200 -> 50 (grids self-check the count).
    for n in (200, 570, 114):
        pts = spread("lit_area", n)
        assert _count_cells_within_m(TALLINN, pts, {"lit_area", "streetlamp"}, 400.0) == n
    assert dim_darksky(TALLINN, spread("lit_area", 200))[0] == 50
    # Street lamps share the kind set.
    assert dim_darksky(TALLINN, spread("streetlamp", 200))[0] == 50
    # Snapshot scale: Balti ~570 cells -> ~26, Nomme ~114 -> ~64.
    assert dim_darksky(TALLINN, spread("lit_area", 570))[0] == 26
    assert dim_darksky(TALLINN, spread("lit_area", 114))[0] == 64
    # Empty 400 m window IS dark evidence (lamp influence is short-range).
    assert dim_darksky(TALLINN, [])[0] == 100
    # Monotone: more lamps never darken.
    prev = 100
    for n in (1, 10, 50, 200, 600):
        s = dim_darksky(TALLINN, spread("lit_area", n))[0]
        assert s <= prev
        prev = s


def test_twin_dedupe():
    # A lit node sitting exactly on a lit way (same 20 m cell) counts once.
    dup = [poi("lit_area", 100), poi("streetlamp", 100)]
    assert _count_cells_within_m(TALLINN, dup, {"lit_area", "streetlamp"}, 400.0) == 1
    assert dim_darksky(TALLINN, dup)[0] == dim_darksky(TALLINN, [poi("lit_area", 100)])[0]
    # ...but two lamps 100 m apart count twice.
    two = [poi("lit_area", 100), poi("lit_area", 200)]
    assert _count_cells_within_m(TALLINN, two, {"lit_area", "streetlamp"}, 400.0) == 2


def test_coolisland_density():
    # COOL_HALF = 50 buildings/250 m: 50 -> 50; absence caps at 90
    # (heat carries past the window, unlike lamplight).
    assert dim_coolisland(TALLINN, [poi("building", 100) for _ in range(50)])[0] == 50
    assert dim_coolisland(TALLINN, [])[0] == 90
    # One nearby shed can never beat an open field (formula caps at 90).
    assert dim_coolisland(TALLINN, [poi("building", 100)])[0] == 90
    # Snapshot scale: Balti ~60 buildings -> 45, Nomme sprawl ~187 -> 21.
    assert dim_coolisland(TALLINN, [poi("building", 100) for _ in range(60)])[0] == 45
    assert dim_coolisland(TALLINN, [poi("building", 100) for _ in range(187)])[0] == 21


def test_coolisland_green_ramp():
    base = dim_coolisland(TALLINN, [poi("building", 100) for _ in range(50)])[0]
    assert base == 50
    # Mapped park next door cools: +8 at 0 m...
    s, reason = dim_coolisland(
        TALLINN, [poi("building", 100) for _ in range(50)] + [poi("park", 10)])
    assert s == 58
    assert "haljasala" in reason
    # ...fading to +0 at 500 m; unmapped green never punishes.
    s2, _ = dim_coolisland(
        TALLINN, [poi("building", 100) for _ in range(50)] + [poi("park", 600)])
    assert s2 == 50
    # Cap: open field + adjacent park reads 98, never above the honest cap.
    s3, _ = dim_coolisland(TALLINN, [poi("forest", 10)])
    assert s3 == 98


def test_kinds_from_tags():
    assert kinds_from_tags({"lit": "yes"}) == "lit_area"
    assert kinds_from_tags({"lit": "no"}) is None
    assert kinds_from_tags({"highway": "street_lamp"}) == "streetlamp"
    # building=* is open vocabulary: any value but "no" counts.
    assert kinds_from_tags({"building": "yes"}) == "building"
    assert kinds_from_tags({"building": "apartments"}) == "building"
    assert kinds_from_tags({"building": "shed"}) == "building"
    assert kinds_from_tags({"building": "no"}) is None
    assert kinds_from_tags({"amenity": "school"}) is None


def test_param_ids():
    assert G.GROUP18B_PARAM_IDS == {"darksky": 63, "coolisland": 181}
    assert set(G.GROUP18B_DIMS) == set(G.GROUP18B_PARAM_IDS)


def test_fragment_uses_nwr():
    # PR #118: lit features and buildings are way-mapped; lamps are nodes.
    assert "nwr[\"lit\"" in G.GROUP18B_OVERPASS_FRAGMENT
    assert "nwr[\"building\"" in G.GROUP18B_OVERPASS_FRAGMENT
    assert "node[\"highway\"=\"street_lamp\"]" in G.GROUP18B_OVERPASS_FRAGMENT
