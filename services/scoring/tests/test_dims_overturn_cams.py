"""Overturn #238 (G7 CAMS / EGT-radon / KIK): hermetic fixture tests.

No network, no snapshot, no live registry: extracts are inline fixture
dicts/strings, fetch paths use tmp_path + file:// URLs only. Run from
repo root:
  python3 -m pytest services/scoring/tests/test_dims_overturn_cams.py -q

The module itself makes no network calls while no gated result URL is
supplied (dated negatives 2026-09-13, see dims_overturn_cams docstring
and docs/overturn_cams.md); the tests pin the None contracts, the
coarse-raster band shapes on fixtures, the Estonian honesty markers
(scored: hinnang + jame, never EI OLE; NULL: hinnang + EI OLE + the
concrete buyer-side check), the dated verdict / re-check note, and the
registry/aggregator coverage.
"""

import json
import os

import pytest

import dims_overturn_cams as C
from dims_overturn_cams import (
    OVERTURN_CAMS_DIMS,
    RECHECK_AFTER,
    VERDICT_DATE,
    cache_is_fresh,
    dim_allergens_cams,
    dim_harvest_cams,
    dim_invasive_cams,
    dim_kik_sites_cams,
    dim_leadpipes_cams,
    dim_pests_cams,
    dim_radon_aesth_cams,
    dim_radon_grid_cams,
    fetch_cams_snapshot,
    parse_kik_sites,
    parse_radon_grid,
    score_overturn_cams,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "industrial", "lat": 59.4382, "lon": 24.7536}]

#: Fixture radon grid: one cell per class near Tallinn (offsets in
#: degrees latitude; 0.01 deg ~= 1.1 km), one unknown label, one
#: broken row. Clearly synthetic, schema per module docstring.
GRID = [
    {"cell_id": "N59E24-korge", "klass": "korge",
     "lat": 59.4372, "lon": 24.7536},
    {"cell_id": "N59E24-normaalne", "klass": "normaalne",
     "lat": 59.4417, "lon": 24.7536},  # ~500 m north
    {"cell_id": "N59E24-madal", "klass": "madal",
     "lat": 59.4872, "lon": 24.7536},  # ~5.6 km north
    {"cell_id": "N59E24-tundmatu", "klass": "ebamäärane",
     "lat": 59.4372, "lon": 24.7536},
    {"cell_id": "N59E24-katki", "klass": "madal"},
]

#: Fixture KIK extract: doorstep / mid / far / beyond-window sites plus
#: a broken row. Clearly synthetic, schema per module docstring.
KIK = [
    {"site_id": "KIK-1", "name": "Ukse-esine jääkreostus",
     "lat": 59.4372, "lon": 24.7536},
    {"site_id": "KIK-2", "name": "Keskmine jääkreostus",
     "lat": 59.4402, "lon": 24.7536},  # ~330 m north
    {"site_id": "KIK-3", "name": "Kauge jääkreostus",
     "lat": 59.4452, "lon": 24.7536},  # ~890 m north
    {"site_id": "KIK-4", "name": "Akkapiiri jääkreostus",
     "lat": 59.4522, "lon": 24.7536},  # ~1.7 km north
    {"site_id": "KIK-5", "name": "Koordinaatideta",
     "lat": None, "lon": None},
]


# ---------------------------------------------------------------------------
# p66 radon grid leg: coarse-class bands on fixtures, NULLs fail closed.
# ---------------------------------------------------------------------------

def test_radon_grid_bands_follow_class_not_distance():
    # Nearest cell to TALLINN is the korge cell at zero distance; the
    # unknown-label cell at the same spot must NOT win over it -- the
    # reader finds the nearest well-formed row, the scorer fails the
    # unknown label closed only when IT is nearest.
    v, _ = dim_radon_grid_cams(TALLINN, GRID)
    assert v == 25


def test_radon_grid_normal_and_low_cells():
    v, _ = dim_radon_grid_cams((59.4417, 24.7536),
                               [c for c in GRID
                                if c["cell_id"] == "N59E24-normaalne"])
    assert v == 60
    v, _ = dim_radon_grid_cams((59.4872, 24.7536),
                               [c for c in GRID
                                if c["cell_id"] == "N59E24-madal"])
    assert v == 80


def test_radon_grid_low_cap_never_clean():
    v, reason = dim_radon_grid_cams((59.4872, 24.7536),
                                    [c for c in GRID
                                     if c["cell_id"] == "N59E24-madal"])
    assert v == 80
    assert v != 100
    assert "mõõtmine" in reason


def test_radon_grid_nulls_fail_closed():
    far = (59.5872, 24.7536)  # ~16.7 km north of every fixture cell
    for origin, cells in [(None, GRID), (TALLINN, None), (TALLINN, []),
                          (far, GRID),
                          (TALLINN, [{"cell_id": "x", "klass": "ebamäärane",
                                      "lat": 59.4372, "lon": 24.7536}]),
                          (TALLINN, [{"cell_id": "y", "klass": "madal"}])]:
        v, reason = dim_radon_grid_cams(origin, cells)
        assert v is None
        assert "EI OLE" in reason


def test_radon_scored_reason_markers():
    _, reason = dim_radon_grid_cams(TALLINN, GRID)
    assert "hinnang" in reason
    assert "jäme" in reason
    assert "EI OLE" not in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason


# ---------------------------------------------------------------------------
# p204 KIK leg: confirmed-site bands mirror dim_brownsoil, capped.
# ---------------------------------------------------------------------------

def test_kik_bands_mirror_brownsoil_with_cap():
    # Single doorstep site; origins step north: 0 m / ~330 m /
    # ~890 m / ~1.7 km / ~2.8 km (0.01 deg lat ~= 1.1 km).
    one = [KIK[0]]
    assert dim_kik_sites_cams(TALLINN, one)[0] == 30
    assert dim_kik_sites_cams((59.4402, 24.7536), one)[0] == 55
    assert dim_kik_sites_cams((59.4452, 24.7536), one)[0] == 75
    assert dim_kik_sites_cams((59.4522, 24.7536), one)[0] == 80
    v, reason = dim_kik_sites_cams((59.4622, 24.7536), one)
    assert v is None
    assert "EI OLE" in reason
    # Full fixture list at TALLINN: the doorstep site wins.
    assert dim_kik_sites_cams(TALLINN, KIK)[0] == 30


def test_kik_beyond_window_is_unknown_never_clean():
    v, reason = dim_kik_sites_cams((59.5872, 24.7536), KIK)
    assert v is None
    assert "EI OLE" in reason
    assert "puhasta" not in reason and "puhas" not in reason


def test_kik_nulls_and_broken_rows():
    for origin, kik in [(None, KIK), (TALLINN, None), (TALLINN, []),
                        (TALLINN, [{"site_id": "z"}])]:
        v, reason = dim_kik_sites_cams(origin, kik)
        assert v is None
        assert "EI OLE" in reason


def test_kik_scored_reason_cross_references_sibling():
    v, reason = dim_kik_sites_cams(TALLINN, KIK)
    assert v == 30
    assert "hinnang" in reason
    assert "EI OLE" not in reason
    assert "p189" in reason


# ---------------------------------------------------------------------------
# Pure-NULL legs: every input stays None with buyer-side pointers.
# ---------------------------------------------------------------------------

NULL_FNS = (dim_pests_cams, dim_allergens_cams, dim_invasive_cams,
            dim_harvest_cams, dim_leadpipes_cams, dim_radon_aesth_cams)


def test_pure_null_legs_always_none():
    for fn in NULL_FNS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, reason = fn(origin, pois)
            assert v is None
            assert "hinnang" in reason
            assert "EI OLE" in reason
            assert "ära feigi" in reason


def test_null_reasons_point_at_concrete_checks():
    assert "müüjalt" in dim_pests_cams(TALLINN, POIS)[1]
    assert "aerobioloogiline" in dim_allergens_cams(TALLINN, POIS)[1]
    assert "haljas" in dim_allergens_cams(TALLINN, POIS)[1]
    assert "p409" in dim_harvest_cams(TALLINN, POIS)[1]
    assert "0,13%" in dim_leadpipes_cams(TALLINN, POIS)[1]
    assert "Terviseameti" in dim_radon_aesth_cams(TALLINN, POIS)[1]


def test_null_reasons_stay_param_scoped():
    # No leg may claim a sibling slice or invent the refused proxy.
    blob = " ".join(fn(TALLINN, POIS)[1] for fn in NULL_FNS)
    assert "postkast" not in blob.lower()
    assert "kaugküte" not in blob.lower()
    assert "CAMS" not in blob  # transport lives in the fetcher, not reasons


# ---------------------------------------------------------------------------
# Parsers: malformed -> None (unknown), unknown labels kept for the
# scorer to fail closed.
# ---------------------------------------------------------------------------

def test_parse_radon_grid_round_trip_and_rejects():
    doc = parse_radon_grid(json.dumps({"cells": GRID}))
    assert doc is not None and len(doc["cells"]) == 5
    assert parse_radon_grid("not json{{{") is None
    assert parse_radon_grid(json.dumps({"cells": "korge"})) is None
    assert parse_radon_grid(json.dumps({})) is None
    assert parse_radon_grid(json.dumps([1, 2])) is None


def test_parse_kik_sites_round_trip_and_rejects():
    sites = parse_kik_sites(json.dumps({"sites": KIK}))
    assert sites is not None and len(sites) == 5
    assert parse_kik_sites("not json{{{") is None
    assert parse_kik_sites(json.dumps({"sites": {"a": 1}})) is None
    assert parse_kik_sites(json.dumps({})) is None


# ---------------------------------------------------------------------------
# Fetcher: no ticket -> ValueError (never a guessed request); file://
# round-trip + fresh-cache hit perform no network.
# ---------------------------------------------------------------------------

def test_fetch_without_ticket_raises_never_requests(tmp_path):
    with pytest.raises(ValueError):
        fetch_cams_snapshot(str(tmp_path), "cams-pm25", None)


def test_fetch_file_url_round_trip_and_cache_hit(tmp_path):
    src = tmp_path / "src.json"
    src.write_text('{"cells": []}', encoding="utf-8")
    text = fetch_cams_snapshot(str(tmp_path), "cams-pm25",
                               src.as_uri(), ttl_s=180)
    assert json.loads(text) == {"cells": []}
    cached = os.path.join(str(tmp_path), "cams-pm25.json")
    assert os.path.exists(cached)
    # Fresh cache wins: a missing URL must NOT be touched.
    os.remove(str(src))
    assert fetch_cams_snapshot(str(tmp_path), "cams-pm25",
                               "file:///does/not/exist.json",
                               ttl_s=3600) == text
    assert cache_is_fresh(cached, 3600) is True
    assert cache_is_fresh(cached, 0) is False
    assert cache_is_fresh(os.path.join(str(tmp_path), "nope.json"),
                          3600) is False


# ---------------------------------------------------------------------------
# Verdict dates, registry, aggregator.
# ---------------------------------------------------------------------------

def test_verdict_is_dated_with_recheck_note():
    assert VERDICT_DATE == "2026-09-13"
    assert RECHECK_AFTER == "2027-03-13"
    assert RECHECK_AFTER > VERDICT_DATE


def test_registry_covers_all_eight_params():
    assert [k for k, _, _ in OVERTURN_CAMS_DIMS] == [
        "radoon_ruut_cams", "saaste_kik_cams", "kahjur_seire_cams",
        "allergeen_seire_cams", "invasiiv_seire_cams",
        "loikus_seire_cams", "pliitoru_seire_cams",
        "radoon_fassaad_cams"]
    assert [p for _, p, _ in OVERTURN_CAMS_DIMS] == [
        "p66", "p204", "p67", "p137", "p252", "p448", "p471", "p499"]
    assert len({fn for _, _, fn in OVERTURN_CAMS_DIMS}) == 8
    assert C.OVERTURN_CAMS_DIMS is OVERTURN_CAMS_DIMS


def test_aggregator_defaults_all_none_and_scores_fixtures():
    assert score_overturn_cams(None) == {
        "radoon_ruut_cams": None, "saaste_kik_cams": None,
        "kahjur_seire_cams": None, "allergeen_seire_cams": None,
        "invasiiv_seire_cams": None, "loikus_seire_cams": None,
        "pliitoru_seire_cams": None, "radoon_fassaad_cams": None}
    out = score_overturn_cams(TALLINN, POIS, cells=GRID, kik=KIK)
    assert out["radoon_ruut_cams"] == 25
    assert out["saaste_kik_cams"] == 30
    assert out["kahjur_seire_cams"] is None
    assert out["radoon_fassaad_cams"] is None
