"""P4 shelters dims (issue #528): hermetic tests.

No network: parsing runs on synthetic fixture CSV strings, the dim
runs on synthetic snapshots, politeness constants are asserted as
values, and the live pull is env-gated (HF_LIVE_SHELTERS=1) so the
default suite never touches the network.
Run: python3 -m pytest services/scoring/tests/test_dims_p4_shelters.py -q
"""

import os

import pytest

import dims_p4_shelters as shelters
from dims_p4_shelters import (
    LEST97_E_MAX,
    LEST97_E_MIN,
    LEST97_N_MAX,
    LEST97_N_MIN,
    P4_SHELTERS_DIMS,
    SHELTERS_CACHE_NAME,
    SHELTERS_CACHE_TTL_S,
    SHELTERS_URL,
    SHELTER_BANDS,
    SHELTER_CAP,
    dim_shelter_proximity,
    fetch_shelters_snapshot,
    has_lest97,
    haversine_km,
    lest97_to_wgs84,
    parse_shelters_csv,
    score_p4_shelters,
    summarize_snapshot,
)

TALLINN = (59.4372, 24.7536)

#: Synthetic register payload (invented lest values near Tallinn; real
#: observed values appear only in docs/p4_shelters.md, never ingested).
CSV_FIXTURE = (
    '"id";"nimi";"aadress";"lest_x";"lest_y"\n'
    '"SYN1";"Sünteetiline Varjend";"Harju maakond, Tallinn, Kesklinn";'
    '"6589061";"543000"\n'
    '"SYN2";"Kauge Sünteetiline";"Harju maakond, Saue vald";'
    '"6585000";"530000"\n'
    '"SYN3";"Koordinaadita";"Harju maakond, Tallinn";"";""\n'
)


def _point(lat, lon, name="Sünteetiline Varjend"):
    return {"id": "SYN", "name": name,
            "address": "Harju maakond, Tallinn",
            "lat": lat, "lon": lon,
            "transform": "sünteetiline"}


def _snap(points, fetched="2026-09-16"):
    return {"points": points, "fetched": fetched, "source": "sünteetiline"}


# ---------------------------------------------------------------------------
# Helpers + projection.
# ---------------------------------------------------------------------------

def test_haversine_sanity():
    assert haversine_km(TALLINN, TALLINN) == 0.0
    assert 0.2 < haversine_km(TALLINN, (TALLINN[0] + 0.002, TALLINN[1])) < 0.3


def test_has_lest97_gate_rejects_wgs84_scale():
    assert has_lest97("6589061", "543000")
    assert not has_lest97("59.4372", "24.7536")  # WGS84 mixup rejected
    assert not has_lest97("", "")
    assert not has_lest97(None, None)
    assert not has_lest97("määramata", "543000")
    assert (LEST97_N_MIN, LEST97_N_MAX) == (6360000.0, 6655000.0)
    assert (LEST97_E_MIN, LEST97_E_MAX) == (330000.0, 740000.0)


def test_lest97_projects_into_tallinn_window():
    # Same ported transform as #527 (dual-coordinate oracle there:
    # 238 rows, 6.1 cm worst-case). Invented lest input; asserts the
    # Tallinn window (axis-order guard) plus regression values.
    lat, lon = lest97_to_wgs84(6589061.0, 543000.0)
    assert 59.2 < lat < 59.7 and 23.9 < lon < 25.4
    assert abs(lat - 59.4372) < 0.001 and abs(lon - 24.7578) < 0.001
    with pytest.raises(ValueError):
        lest97_to_wgs84(float("inf"), 543000.0)


# ---------------------------------------------------------------------------
# Pure parser on the synthetic fixture.
# ---------------------------------------------------------------------------

def test_parse_projects_and_skips_coordinate_less():
    points = parse_shelters_csv(CSV_FIXTURE)
    assert len(points) == 2  # SYN3 skipped, counted below
    first = points[0]
    assert first["id"] == "SYN1" and first["name"] == "Sünteetiline Varjend"
    assert "Tallinn" in first["address"]
    assert 59.2 < first["lat"] < 59.7 and 23.9 < first["lon"] < 25.4
    assert parse_shelters_csv("") == []


def test_summarize_counts():
    assert summarize_snapshot(CSV_FIXTURE) == {
        "rows": 3, "points": 2, "skipped": 1, "tallinn": 1, "harju": 2}


# ---------------------------------------------------------------------------
# Dim bands (projection-free: exact lat/lon points).
# ---------------------------------------------------------------------------

def _moved(north_m=0.0, east_m=0.0):
    # ~1° lat = 111 320 m; ~1° lon at Tallinn = 57 100 m.
    return (TALLINN[0] + north_m / 111320.0,
            TALLINN[1] + east_m / 57100.0)


def test_no_origin_is_none():
    v, reason = dim_shelter_proximity(None, None, _snap([_point(*TALLINN)]))
    assert v is None and "EI OLE" in reason and "aadress" in reason


def test_empty_snapshot_is_none_with_markers():
    for snap in (None, {}, {"points": []}):
        v, reason = dim_shelter_proximity(TALLINN, None, snap)
        assert v is None, snap
        assert "hinnang" in reason and "EI OLE" in reason


def test_bands_and_cap():
    assert dim_shelter_proximity(
        TALLINN, None, _snap([_point(*_moved(300))]))[0] == 80
    assert dim_shelter_proximity(
        TALLINN, None, _snap([_point(*_moved(800))]))[0] == 65
    assert dim_shelter_proximity(
        TALLINN, None, _snap([_point(*_moved(1500))]))[0] == 50


def test_never_above_cap_even_at_doorstep():
    v, reason = dim_shelter_proximity(TALLINN, None, _snap([_point(*TALLINN)]))
    assert v == 80 == SHELTER_CAP
    assert "ülempiir 80" in reason and "garantii" in reason
    assert "72 h" in reason and "igapäevakasutust pole" in reason


def test_reason_names_shelter_and_snapshot_date():
    v, reason = dim_shelter_proximity(
        TALLINN, None, _snap([_point(*_moved(300), name="Sünteetiline Varjend")],
                             fetched="2026-09-16"))
    assert v == 80
    assert "Sünteetiline Varjend" in reason and "2026-09-16" in reason
    assert "linnulennult" in reason  # no routing claims


def test_beyond_2km_is_none_never_unsafe():
    v, reason = dim_shelter_proximity(
        TALLINN, None, _snap([_point(*_moved(5000))]))
    assert v is None
    assert "EI OLE" in reason
    assert "ebaturvalisuse hinnang" in reason or "ei ole" in reason
    assert "ohutu paik" not in reason and "ebaturvaline" not in reason


def test_nearest_wins():
    snap = _snap([_point(*_moved(1500), name="Kauge"),
                  _point(*_moved(300), name="Lähedane")])
    v, reason = dim_shelter_proximity(TALLINN, None, snap)
    assert v == 80 and "Lähedane" in reason


# ---------------------------------------------------------------------------
# Registry, rollup, constants, politeness, live gate.
# ---------------------------------------------------------------------------

def test_band_constants_pinned():
    assert SHELTER_BANDS == ((500.0, 80), (1000.0, 65), (2000.0, 50))
    assert SHELTER_CAP == 80


def test_all_none_reasons_carry_honesty_markers():
    for snap in (None, {}, {"points": []}):
        _, reason = dim_shelter_proximity(TALLINN, None, snap)
        assert "hinnang" in reason and "EI OLE" in reason
        assert "garanteeritud" not in reason and "mõõdetud" not in reason
    _, far = dim_shelter_proximity(TALLINN, None, _snap([_point(*_moved(5000))]))
    assert "EI OLE" in far


def test_registry_and_rollup_shape():
    assert [k for k, _, _ in P4_SHELTERS_DIMS] == ["shelter_proximity"]
    dims, reasons = score_p4_shelters(TALLINN, None, _snap([_point(*_moved(300))]))
    assert dims == {"shelter_proximity": 80} and len(reasons) == 1
    empty, no_reasons = score_p4_shelters(TALLINN, None, None)
    assert empty == {"shelter_proximity": None} and no_reasons == []
    assert shelters.P4_SHELTERS_DIMS is P4_SHELTERS_DIMS


def test_politeness_contract_as_values():
    assert SHELTERS_URL == "https://opendata.smit.ee/gis/varjumiskohad.csv"
    assert SHELTERS_CACHE_TTL_S == 7 * 86400  # weekly per publisher cadence
    assert "home-finder" in shelters.SHELTERS_USER_AGENT
    assert SHELTERS_CACHE_NAME.endswith(".csv")


def test_end_to_end_parse_then_score():
    points = parse_shelters_csv(CSV_FIXTURE)
    v, _ = dim_shelter_proximity(TALLINN, None, _snap(points))
    assert v == 80  # SYN1 projects ~230 m east of the centre


@pytest.mark.skipif(not os.environ.get("HF_LIVE_SHELTERS"),
                    reason="live network only with HF_LIVE_SHELTERS=1")
def test_live_snapshot_pull_explicit_flag_only(tmp_path):
    snapshot, provenance = fetch_shelters_snapshot(cache_dir=str(tmp_path))
    assert snapshot["points"]
    assert provenance in ("live", "cache")
