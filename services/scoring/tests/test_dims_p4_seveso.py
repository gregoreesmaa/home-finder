"""P4 Seveso dims (issue #527): hermetic tests.

No network: parsing runs on synthetic fixture CSV strings, the dim
runs on synthetic snapshots, politeness constants are asserted as
values, and the live pull is env-gated (HF_LIVE_SEVESO=1) so the
default suite never touches the network.
Run: python3 -m pytest services/scoring/tests/test_dims_p4_seveso.py -q
"""

import os

import pytest

import dims_p4_seveso as seveso
from dims_p4_seveso import (
    DANGER_SCORES,
    FALLBACK_RADII_M,
    P4_SEVESO_DIMS,
    SEVESO_CACHE_TTL_S,
    SEVESO_DANGER_CACHE_NAME,
    SEVESO_DANGER_URL,
    SEVESO_POINTS_CACHE_NAME,
    SEVESO_POINTS_URL,
    classify_danger,
    dim_seveso_zone,
    fetch_seveso_snapshot,
    haversine_km,
    lest97_to_wgs84,
    parse_danger_csv,
    parse_points_csv,
    point_in_ring,
    score_p4_seveso,
    summarize_snapshot,
)

TALLINN = (59.4372, 24.7536)
NEAR = (TALLINN[0] + 0.001, TALLINN[1] + 0.001)  # ~130 m away

#: Synthetic square danger polygon (~220 m side) centred on TALLINN,
#: expressed as L-EST97 WKT the way the live register serves it. The
#: numbers are invented for the test (real observed values appear only
#: in docs/p4_seveso.md, never as ingested data).
_SQ = ("POLYGON ((542650 6588930, 542900 6588930, 542900 6589190, "
       "542650 6589190, 542650 6588930))")

POINTS_FIXTURE = (
    '"nimi";"kaitise_id";"aadress";"x_tegevuskoht";"y_tegevuskoht";'
    '"x_ohuallikas";"y_ohuallikas";"kaitise_ohtlikkus";"tegevusala";'
    '"doomino_efekt";"mojutatud_ettevotted";"ohu_tuup";"kemikaalid";'
    '"infovoldik";"lon_ohuallikas";"lat_ohuallikas"\n'
    '"Sünteetiline Keemia OÜ";7.0;"Harju maakond, Tallinn, Lasnamäe";'
    '6593900.0;543000.0;6593910.0;543010.0;"B";"Keemia";"true";"";'
    '"Mürgised ained";"Ammoniaak";"https://example.ee/voldik";'
    '24.7530;59.4370\n'
)


def _danger_fixture(wkt=_SQ, danger="Mürgised ained", domino="true",
                    name="Sünteetiline Keemia OÜ"):
    return (
        '"WKT";"nimi";"kaitise_id";"aadress";"raadius";"x_ohuallikas";'
        '"y_ohuallikas";"lon_ohuallikas";"lat_ohuallikas";'
        '"kaitise_ohtlikkus";"tegevusala";"doomino_efekt";'
        '"mojutatud_ettevotted";"ohu_tuup";"kemikaalid";"infovoldik"\n'
        '"%s";"%s";7.0;"Harju maakond, Tallinn";250.0;'
        '6593910.0;543010.0;24.7530;59.4370;"B";"Keemia";"%s";"";'
        '"%s";"Ammoniaak";"https://example.ee/voldik"\n'
        % (wkt, name, domino, danger)
    )


DANGER = {"areas": parse_danger_csv(_danger_fixture()),
          "points": parse_points_csv(POINTS_FIXTURE),
          "fetched": "2026-09-16",
          "source": "sünteetiline"}


# ---------------------------------------------------------------------------
# Classification + geometry helpers.
# ---------------------------------------------------------------------------

def test_classify_danger_labels_and_binding():
    assert classify_danger("Mürgised ained") == "toxic"
    assert classify_danger("Soojuskiirgus") == "heat"
    assert classify_danger("Ülerõhk") == "overpressure"
    assert classify_danger("Mürgised ained, Soojuskiirgus") == "toxic"
    assert classify_danger("põlemist soodustav") == "combustion"
    assert classify_danger("tundmatu") == "unknown"
    assert classify_danger(None) == "unknown"
    assert classify_danger("") == "unknown"


def test_point_in_ring_square():
    ring = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)]
    assert point_in_ring(0.5, 0.5, ring)
    assert not point_in_ring(2.0, 2.0, ring)
    assert not point_in_ring(0.5, 0.5, [(0.0, 0.0)])
    assert not point_in_ring(0.5, 0.5, [])


def test_lest97_projects_into_tallinn_window():
    # Geodetic anchor from the 2026-09-16 probe (docs/p4_seveso.md §1):
    # Haabersti LOV, Järveotsa tee 67, lest (6586373.81, 537276.66).
    # Pins L-EST97 axis order (a northing/easting swap would read
    # lat ~24.x); the full 238-row dual-coordinate oracle (worst
    # 6.1 cm) is recorded in the doc, not ingested here.
    lat, lon = lest97_to_wgs84(6586373.81, 537276.66)
    assert 59.2 < lat < 59.7 and 23.9 < lon < 25.4
    assert abs(lat - 59.414) < 0.001 and abs(lon - 24.656) < 0.001
    with pytest.raises(ValueError):
        lest97_to_wgs84(float("nan"), 543000.0)


def test_haversine_sanity():
    assert haversine_km(TALLINN, TALLINN) == 0.0
    assert 0.1 < haversine_km(TALLINN, NEAR) < 0.2


# ---------------------------------------------------------------------------
# Pure parsers on synthetic fixtures.
# ---------------------------------------------------------------------------

def test_parse_points_prefers_wgs84_and_flags_domino():
    rows = parse_points_csv(POINTS_FIXTURE)
    assert len(rows) == 1
    row = rows[0]
    assert (row["lat"], row["lon"]) == (59.437, 24.753)
    assert row["danger"] == "toxic"
    assert row["domino"] is True
    assert "voldik" in row["leaflet"]
    assert "hinnang" not in row["transform"]  # transform label is projection-only


def test_parse_points_projects_lest97_when_wgs84_missing():
    text = POINTS_FIXTURE.replace("24.7530;59.4370", ";")
    rows = parse_points_csv(text)
    assert len(rows) == 1
    assert 59.2 < rows[0]["lat"] < 59.7
    assert 23.9 < rows[0]["lon"] < 25.4


def test_parse_points_skips_coordinate_less_rows():
    text = POINTS_FIXTURE.replace("24.7530;59.4370", ";").replace(
        "6593910.0;543010.0", ";")
    assert parse_points_csv(text) == []
    assert parse_points_csv("") == []


def test_parse_danger_projects_ring_and_bbox():
    areas = parse_danger_csv(_danger_fixture())
    assert len(areas) == 1
    area = areas[0]
    assert len(area["ring"]) == 5
    la0, lo0, la1, lo1 = area["bbox"]
    assert la0 < TALLINN[0] < la1 and lo0 < TALLINN[1] < lo1
    assert area["danger"] == "toxic" and area["radius_m"] == 250.0


def test_parse_danger_ignores_holes_fail_safe():
    with_hole = (_SQ[:-1] + ", "
                 "(542720 6589030, 542760 6589030, 542760 6589070, "
                 "542720 6589070, 542720 6589030))")
    areas = parse_danger_csv(_danger_fixture(wkt=with_hole))
    assert len(areas) == 1 and len(areas[0]["ring"]) == 5  # outer ring only


def test_parse_danger_skips_broken_wkt():
    assert parse_danger_csv(_danger_fixture(wkt="POLYGON EMPTY")) == []
    assert parse_danger_csv("") == []


def test_summarize_counts_harju():
    summary = summarize_snapshot(POINTS_FIXTURE, _danger_fixture())
    assert summary == {"points": 1, "areas": 1,
                       "harju_points": 1, "harju_areas": 1}


# ---------------------------------------------------------------------------
# Dim: polygons preferred.
# ---------------------------------------------------------------------------

def test_no_origin_is_none():
    v, reason = dim_seveso_zone(None, None, DANGER)
    assert v is None and "EI OLE" in reason and "aadress" in reason


def test_empty_snapshot_is_none_with_markers():
    for snap in (None, {}, {"areas": [], "points": []}):
        v, reason = dim_seveso_zone(TALLINN, None, snap)
        assert v is None, snap
        assert "hinnang" in reason and "EI OLE" in reason


def test_inside_toxic_polygon_scores_20_with_markers():
    v, reason = dim_seveso_zone(TALLINN, None, DANGER)
    assert v == 20
    assert "Sünteetiline Keemia OÜ" in reason
    assert "Mürgised ained" in reason and "doomino" in reason
    assert "infovoldik" in reason and "hinnang" in reason


def test_outside_every_polygon_is_none_never_safe():
    far = (TALLINN[0] + 0.05, TALLINN[1] + 0.05)  # ~5.6 km away
    v, reason = dim_seveso_zone(far, None, DANGER)
    assert v is None
    assert "EI OLE" in reason
    assert "ei ole ohutuse hinnang" in reason  # absence != safety, said aloud
    assert "ohutu paik" not in reason and "ohutus tagatud" not in reason


def test_overlapping_polygons_score_worst():
    heat = parse_danger_csv(_danger_fixture(danger="Soojuskiirgus",
                                            domino="false", name="Teine OÜ"))
    snap = dict(DANGER, areas=DANGER["areas"] + heat)
    v, reason = dim_seveso_zone(TALLINN, None, snap)
    assert v == 20  # toxic leg binds, not the 35 heat leg
    assert "Sünteetiline Keemia OÜ" in reason


def test_band_scores_by_type():
    for label, expected in (("Soojuskiirgus", 35), ("Ülerõhk", 35),
                            ("põlemist soodustav", 50), ("tundmatu", 30)):
        snap = {"areas": parse_danger_csv(_danger_fixture(danger=label)),
                "points": [], "fetched": "sünteetiline"}
        assert dim_seveso_zone(TALLINN, None, snap)[0] == expected, label


# ---------------------------------------------------------------------------
# Dim: point fallback (polygons absent only).
# ---------------------------------------------------------------------------

def test_point_fallback_inside_and_outside():
    snap = {"areas": [], "points": DANGER["points"], "fetched": "sünteetiline"}
    v, reason = dim_seveso_zone(NEAR, None, snap)
    assert v == 20 and "punktipuhver" in reason
    far = (TALLINN[0] + 0.05, TALLINN[1] + 0.05)
    v2, reason2 = dim_seveso_zone(far, None, snap)
    assert v2 is None and "EI OLE" in reason2


def test_polygons_preferred_over_points():
    # NEAR is inside the polygon AND inside the point buffer: the
    # polygon reason (ohualas) must win over the fallback wording.
    v, reason = dim_seveso_zone(NEAR, None, DANGER)
    assert v == 20 and "ohualas" in reason and "punktipuhver" not in reason


# ---------------------------------------------------------------------------
# Registry, rollup, constants, politeness, live gate.
# ---------------------------------------------------------------------------

def test_band_constants_pinned():
    assert DANGER_SCORES == {"toxic": 20, "heat": 35, "overpressure": 35,
                             "combustion": 50, "unknown": 30}
    assert FALLBACK_RADII_M == {"toxic": 350.0, "heat": 180.0,
                                "overpressure": 110.0, "combustion": 200.0,
                                "unknown": 200.0}


def test_all_none_reasons_carry_honesty_markers():
    for snap in (None, {}, {"areas": [], "points": []}):
        _, reason = dim_seveso_zone(TALLINN, None, snap)
        assert "hinnang" in reason and "EI OLE" in reason
        assert "garanteeritud" not in reason and "mõõdetud" not in reason
    _, outside = dim_seveso_zone((TALLINN[0] + 0.05, TALLINN[1] + 0.05),
                                 None, DANGER)
    assert "EI OLE" in outside


def test_registry_and_rollup_shape():
    assert [k for k, _, _ in P4_SEVESO_DIMS] == ["seveso_zone"]
    dims, reasons = score_p4_seveso(TALLINN, None, DANGER)
    assert dims == {"seveso_zone": 20} and len(reasons) == 1
    empty, no_reasons = score_p4_seveso(TALLINN, None, None)
    assert empty == {"seveso_zone": None} and no_reasons == []
    assert seveso.P4_SEVESO_DIMS is P4_SEVESO_DIMS


def test_politeness_contract_as_values():
    assert SEVESO_POINTS_URL == "https://opendata.smit.ee/gis/ohtlikud_kaitised.csv"
    assert SEVESO_DANGER_URL == (
        "https://opendata.smit.ee/gis/ohtlikud_kaitised_ohualad.csv")
    assert SEVESO_CACHE_TTL_S == 7 * 86400  # weekly per publisher cadence
    assert "home-finder" in seveso.SEVESO_USER_AGENT
    assert SEVESO_POINTS_CACHE_NAME.endswith(".csv")
    assert SEVESO_DANGER_CACHE_NAME.endswith(".csv")


@pytest.mark.skipif(not os.environ.get("HF_LIVE_SEVESO"),
                    reason="live network only with HF_LIVE_SEVESO=1")
def test_live_snapshot_pull_explicit_flag_only(tmp_path):
    snapshot, provenance = fetch_seveso_snapshot(cache_dir=str(tmp_path))
    assert snapshot["points"] and snapshot["areas"]
    assert provenance in ("live", "cache")
