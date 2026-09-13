"""P4 Maa-LiDAR dims (issues #247 demo + #331 coverage): hermetic tests.

No network: every fixture is a synthetic in-memory listing/artefact (plain
dicts — no scraped data, no bulk downloads). fetch_cached is covered only on
its cache-hit path; freshness/expiry uses tmp_path. The live probes are manual
DoD evidence (pasted in the PR + docs/p4_maa_lidar.md), not unit runs.
"""

import os

import dims_p4_maa_lidar as p4
from dims_p4_maa_lidar import (
    ENCLOSURE_TRAPPED,
    GLIMPSE_WIDE_DEG,
    P4_MAA_LIDAR_DIMS,
    TTL_DAYS,
    cache_path,
    dim_backyard_weather,
    dim_courtyard_trap,
    dim_darkness_shading,
    dim_engineering_geology,
    dim_glimpse_view,
    dim_overheat_shading,
    dim_roof_income,
    enclosure_index,
    fetch_cached,
    is_fresh,
    lod2_url,
    parse_dtm_xyz,
    parse_lod2_summary,
    score_p4_maa_lidar,
    usable_roof_kwp,
)

# Synthetic Tallinn fixtures (invented numbers, never scraped data).
RICH_LIDAR = {
    "parcel_id": "78408:408:0123",
    "vintage": "2026-04",
    "dem": {"parcel_m": 11.2, "surround_median_m": 11.4,
            "roughness_m": 0.2, "sink_m": 0.1},
    "enclosure": {"courtyard": True, "index": 1.6,
                  "wall_h_m": 16.0, "courtyard_w_m": 10.0},
    "shading": {"open_sky": 0.25, "south_open": False},
    "view_fan": {"sea_sliver_deg": 4.5, "oldtown_sliver_deg": 0.0,
                 "computed_floor": 5},
    "roof": {"facets": [
        {"area_m2": 40.0, "tilt_deg": 30.0, "azimuth_deg": 180.0,
         "shaded_share": 0.1},
        {"area_m2": 40.0, "tilt_deg": 30.0, "azimuth_deg": 0.0,
         "shaded_share": 0.1},
    ], "flat_m2": 0.0},
}

FLOOR5 = {"floor": 5, "top_floor": False, "address": "Pirita tee 20, Tallinn"}


def lidar(**kw):
    import copy
    out = copy.deepcopy(RICH_LIDAR)
    out.update(kw)
    return out


def listing(**kw):
    base = dict(FLOOR5)
    base.update(kw)
    return base


ALL_FNS = [fn for _, _, fn in P4_MAA_LIDAR_DIMS]
EXPECTED_KEYS = ["glimpse_view", "eng_geology", "backyard_weather",
                 "overheat_shading", "darkness_shading", "roof_income",
                 "courtyard_trap"]
EXPECTED_PNUMS = ["P4-041", "P4-016", "P4-031", "P4-034", "P4-035", "P4-036",
                  "P4-056"]


# ---------------------------------------------------------------------------
# Ingestion plumbing: URLs, TTLs, cache-hit fetch, freshness.
# ---------------------------------------------------------------------------

def test_lod2_url_builds_tallinn_citygml_pattern():
    url = lod2_url("Tallinn", "citygml")
    assert "hooned_lod2" in url and "Tallinn-citygml.zip" in url
    assert url.startswith("https://geoportaal.maaruum.ee/")


def test_ttl_stated_annual_for_both_bulks():
    assert TTL_DAYS == {"lod2_bulk": 365, "dtm_bulk": 365}


def test_fetch_cached_cache_hit_performs_no_request(tmp_path):
    dest = cache_path(str(tmp_path), "tallinn-lod2.zip")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as fh:
        fh.write(b"fake-zip-bytes")
    got = fetch_cached("https://example.invalid/huge.zip", str(tmp_path),
                       "tallinn-lod2.zip", ttl_days=365)
    assert got == dest
    with open(dest, "rb") as fh:
        assert fh.read() == b"fake-zip-bytes"


def test_is_fresh_expiry(tmp_path):
    import datetime as dt
    f = tmp_path / "bulk.zip"
    f.write_bytes(b"x")
    assert is_fresh(str(f), 365) is True
    assert is_fresh(str(f), 365,
                    now=dt.datetime.now(tz=dt.timezone.utc)
                    + dt.timedelta(days=400)) is False
    assert is_fresh(str(tmp_path / "missing.zip"), 365) is False


# ---------------------------------------------------------------------------
# Pure parsers + geometry helpers.
# ---------------------------------------------------------------------------

DTM_XYZ = "659100 6477100 11.2\n659101 6477100 11.4\n659102 6477100 bad\n\nx y\n"


def test_parse_dtm_xyz_stats_and_bad_row_skip():
    stats = parse_dtm_xyz(DTM_XYZ)
    assert stats["n"] == 2
    assert stats["min_m"] == 11.2
    assert stats["max_m"] == 11.4
    assert abs(stats["mean_m"] - 11.3) < 1e-9


def test_parse_dtm_xyz_empty_stays_unscored():
    assert parse_dtm_xyz("") == {"n": 0, "min_m": None,
                                 "mean_m": None, "max_m": None}


CITYGML_FIX = """<?xml version="1.0" encoding="UTF-8"?>
<CityModel xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
           xmlns:gml="http://www.opengis.net/gml">
  <cityObjectMember><bldg:Building gml:id="B1">
    <bldg:measuredHeight uom="m">16.5</bldg:measuredHeight>
    <bldg:storeysAboveGround>5</bldg:storeysAboveGround>
  </bldg:Building></cityObjectMember>
  <cityObjectMember><bldg:Building gml:id="B2">
    <bldg:measuredHeight uom="m">9.0</bldg:measuredHeight>
  </bldg:Building></cityObjectMember>
</CityModel>"""


def test_parse_lod2_summary_counts_and_heights():
    out = parse_lod2_summary(CITYGML_FIX)
    assert out["n_buildings"] == 2
    assert out["heights_m"] == [16.5, 9.0]
    assert out["storeys"] == [5]


def test_parse_lod2_summary_rejects_garbage():
    try:
        parse_lod2_summary("<not xml at all")
    except ValueError as exc:
        assert "ei parsinud" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_enclosure_index_ratio_and_trapped_threshold():
    assert enclosure_index(16.0, 10.0) == 1.6
    assert 16.0 / 10.0 >= ENCLOSURE_TRAPPED
    assert enclosure_index(None, 10.0) is None
    assert enclosure_index(16.0, 0.0) is None
    assert enclosure_index(16.0, -5.0) is None


def test_usable_roof_kwp_rules():
    facets = [
        {"area_m2": 40.0, "tilt_deg": 30.0, "shaded_share": 0.1},  # counts
        {"area_m2": 40.0, "tilt_deg": 5.0, "shaded_share": 0.0},  # too flat
        {"area_m2": 40.0, "tilt_deg": 30.0, "shaded_share": 0.8},  # shaded
        {"area_m2": 40.0, "tilt_deg": "x", "shaded_share": 0.0},  # malformed
    ]
    usable, kwp = usable_roof_kwp(facets)
    assert usable == 40.0
    assert abs(kwp - 5.0) < 1e-9
    usable2, kwp2 = usable_roof_kwp([], flat_m2=100.0, flat_shaded=0.2)
    assert usable2 == 70.0  # 0.7 racking factor
    assert abs(kwp2 - 8.75) < 1e-9


# ---------------------------------------------------------------------------
# Demo dim P4-041: glimpse view classes.
# ---------------------------------------------------------------------------

def test_glimpse_wide_sliver_scores_85():
    v, reason = dim_glimpse_view(listing(), lidar())
    assert v == 85
    assert "4.5" in reason and "hinnang" in reason
    assert "EI OLE" in reason  # price-premium leg named missing


def test_glimpse_thin_sliver_scores_70():
    li = lidar(view_fan={"sea_sliver_deg": 1.2, "oldtown_sliver_deg": 0.0})
    v, _ = dim_glimpse_view(listing(), li)
    assert v == 70


def test_glimpse_oldtown_sliver_counts():
    li = lidar(view_fan={"sea_sliver_deg": 0.0, "oldtown_sliver_deg": 5.0})
    v, reason = dim_glimpse_view(listing(), li)
    assert v == 85
    assert "5.0" in reason


def test_glimpse_no_view_baseline_45():
    li = lidar(view_fan={"sea_sliver_deg": 0.0, "oldtown_sliver_deg": 0.0})
    v, reason = dim_glimpse_view(listing(), li)
    assert v == 45
    assert "võrdlusbaas" in reason


def test_glimpse_null_without_floor_or_fan():
    v, reason = dim_glimpse_view({}, lidar())
    assert v is None and "EI OLE" in reason and "Korrust" in reason
    v, reason = dim_glimpse_view(listing(), None)
    assert v is None and "EI OLE" in reason and "vaatelehtri" in reason
    v, reason = dim_glimpse_view(listing(), {"dem": {}})
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# Coverage dims: scored paths.
# ---------------------------------------------------------------------------

def test_eng_geology_quiet_scores_60_anomaly_40():
    v, reason = dim_engineering_geology(listing(), lidar())
    assert v == 60
    assert "EGT" in reason and "EI OLE" in reason
    li = lidar(dem={"sink_m": 0.8, "roughness_m": 0.2})
    v, reason = dim_engineering_geology(listing(), li)
    assert v == 40
    assert "vajumikahtluse" in reason
    li = lidar(dem={"sink_m": 0.0, "roughness_m": 1.5})
    v, _ = dim_engineering_geology(listing(), li)
    assert v == 40


def test_backyard_weather_frost_pocket_45_else_60():
    v, _ = dim_backyard_weather(listing(), lidar())
    assert v == 60
    li = lidar(dem={"parcel_m": 9.5, "surround_median_m": 11.0})
    v, reason = dim_backyard_weather(listing(), li)
    assert v == 45
    assert "külmakoti" in reason and "EI OLE" in reason


def test_overheat_shade_cools_exposed_top_floor_capped():
    v, reason = dim_overheat_shading(listing(), lidar())
    assert v == 65  # open_sky 0.25 deep shade
    assert "EI OLE" in reason
    li = lidar(shading={"open_sky": 0.8, "south_open": True})
    v, _ = dim_overheat_shading(listing(top_floor=True), li)
    assert v == 40  # capped, never lower on geometry alone
    v, _ = dim_overheat_shading(listing(), li)
    assert v == 55  # neutral middle


def test_darkness_bands_capped_at_65():
    assert dim_darkness_shading(listing(), lidar())[0] == 35
    li = lidar(shading={"open_sky": 0.45})
    assert dim_darkness_shading(listing(), li)[0] == 50
    li = lidar(shading={"open_sky": 0.9})
    v, reason = dim_darkness_shading(listing(), li)
    assert v == 65
    assert "EI OLE" in reason


def test_roof_income_kwp_bands_and_empty_roof():
    v, reason = dim_roof_income(listing(), lidar())
    assert v == 75  # 80 m2 -> 10 kWp
    assert "kWp" in reason and "EI OLE" in reason
    li = lidar(roof={"facets": [
        {"area_m2": 16.0, "tilt_deg": 30.0, "shaded_share": 0.0}]})
    assert dim_roof_income(listing(), li)[0] == 60  # 2 kWp
    li = lidar(roof={"facets": [
        {"area_m2": 8.0, "tilt_deg": 30.0, "shaded_share": 0.0}]})
    assert dim_roof_income(listing(), li)[0] == 50  # 1 kWp
    li = lidar(roof={"facets": [
        {"area_m2": 40.0, "tilt_deg": 5.0, "shaded_share": 0.0}]})
    v, reason = dim_roof_income(listing(), li)
    assert v == 40
    assert "EI OLE" in reason


def test_courtyard_trap_bands_and_open_parcel():
    v, reason = dim_courtyard_trap(listing(), lidar())
    assert v == 35  # index 1.6 trapped
    assert "1.6" in reason and "EI OLE" in reason
    li = lidar(enclosure={"courtyard": True, "index": 0.7})
    assert dim_courtyard_trap(listing(), li)[0] == 55
    li = lidar(enclosure={"courtyard": False})
    v, reason = dim_courtyard_trap(listing(), li)
    assert v == 70
    assert "EI OLE" in reason


# ---------------------------------------------------------------------------
# NULL contract: every dim NULLs without its artefact leg.
# ---------------------------------------------------------------------------

def test_all_seven_dims_null_without_lidar():
    for fn in ALL_FNS:
        v, reason = fn(listing(), None)
        assert v is None, fn.__name__
        assert "EI OLE" in reason, fn.__name__
        assert "hinnang" in reason, fn.__name__


def test_all_reasons_carry_honesty_markers():
    for fn in ALL_FNS:
        _, reason = fn(listing(), None)
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_malformed_legs_null_without_crash():
    bad = {"dem": {"sink_m": "x", "roughness_m": "y"},
           "shading": {}, "view_fan": {"sea_sliver_deg": "x"},
           "roof": None, "enclosure": {"courtyard": True}}
    assert dim_engineering_geology(listing(), bad)[0] is None
    assert dim_backyard_weather(listing(), bad)[0] is None
    assert dim_overheat_shading(listing(), bad)[0] is None
    assert dim_darkness_shading(listing(), bad)[0] is None
    assert dim_glimpse_view(listing(), bad)[0] is None
    assert dim_courtyard_trap(listing(), bad)[0] is None
    assert dim_roof_income(listing(), {})[0] is None


# ---------------------------------------------------------------------------
# Registry + aggregator.
# ---------------------------------------------------------------------------

def test_registry_and_aggregator_cover_all_seven():
    assert [k for k, _, _ in P4_MAA_LIDAR_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_MAA_LIDAR_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_MAA_LIDAR_DIMS}) == 7
    assert GLIMPSE_WIDE_DEG == 3.0
    out = score_p4_maa_lidar(listing(), lidar())
    assert out == {"glimpse_view": 85, "eng_geology": 60,
                   "backyard_weather": 60, "overheat_shading": 65,
                   "darkness_shading": 35, "roof_income": 75,
                   "courtyard_trap": 35}
    nulls = score_p4_maa_lidar(listing(), None)
    assert nulls == {k: None for k in EXPECTED_KEYS}
    assert p4.P4_MAA_LIDAR_DIMS is P4_MAA_LIDAR_DIMS

