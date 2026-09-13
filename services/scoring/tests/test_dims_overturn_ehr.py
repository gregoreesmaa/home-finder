"""Hermetic unit tests for overturn #234 G2 EHR bulk join.

No network, no snapshot, no live registry: the bulk extract is an inline
fixture string, fetch paths use tmp_path + file:// URLs only. Run from
repo root:
  python3 -m pytest services/scoring/tests/test_dims_overturn_ehr.py -q
"""

import os

import pytest

import dims_overturn_ehr as E
from dims_overturn_ehr import (
    cache_is_fresh,
    dim_accessibility_p30,
    dim_permit_history_p79,
    dim_permit_status_p48,
    dim_sunroom_p495,
    dim_warranty_p154,
    enrich_listing_from_ehr,
    fetch_ehr_bulk,
    index_by_ehr_code,
    parse_ehr_buildings,
    score_overturn_ehr,
)

#: Fixture bulk extract: two joined buildings, one code-less row (skipped),
#: one duplicate code (first row wins).
FIXTURE_CSV = (
    "ehr_code;address;kov;net_area_m2;floors_total;has_lift;elevator_count;"
    "build_year;energy_class;permits_open;permits_finalized;"
    "unpermitted_works;warranty_valid;builder\n"
    "101012345;Telliskivi 60a;Tallinn;2450,5;5;jah;1;2001;C;0;3;ei;jah;Merko\n"
    "101099999;Riia 12;Tartu;980;2;ei;0;1938;;1;0;jah;ei;\n"
    ";Koodita 1;Tallinn;100;1;ei;0;2000;A;0;1;ei;jah;Keegi\n"
    "101012345;Telliskivi DUPLIKAAT;Tallinn;1;1;ei;0;1900;G;9;9;jah;ei;Vale\n"
)

TALLINN = "101012345"
TARTU = "101099999"


@pytest.fixture()
def index():
    return index_by_ehr_code(parse_ehr_buildings(FIXTURE_CSV))


def test_parse_skips_codeless_and_keeps_first_duplicate(index):
    assert set(index) == {TALLINN, TARTU}
    assert index[TALLINN]["address"] == "Telliskivi 60a"
    assert index[TALLINN]["net_area_m2"] == pytest.approx(2450.5)
    assert index[TALLINN]["build_year"] == 2001
    assert index[TALLINN]["has_lift"] is True
    assert index[TALLINN]["permits_finalized"] == 3
    assert index[TALLINN]["unpermitted_works"] is False
    assert index[TALLINN]["warranty_valid"] is True
    assert index[TARTU]["energy_class"] is None  # empty cell -> None
    assert index[TARTU]["builder"] is None


def test_missing_columns_read_as_none():
    recs = parse_ehr_buildings("ehr_code;address\n555;Kuskil\n")
    assert recs[0]["build_year"] is None
    assert recs[0]["has_lift"] is None
    assert recs[0]["address"] == "Kuskil"


def test_all_dims_none_without_record():
    for fn in (dim_accessibility_p30, dim_permit_status_p48,
               dim_permit_history_p79, dim_warranty_p154, dim_sunroom_p495):
        v, reason = fn(None)
        assert v is None
        assert "EHR" in reason
    dims, reasons = score_overturn_ehr(None)
    assert all(v is None for v in dims.values())
    assert reasons == []
    out, prov = enrich_listing_from_ehr({"area_m2": 50}, None)
    assert out == {"area_m2": 50} and prov == {}


def test_enrichment_fills_gaps_listing_wins(index):
    out, prov = enrich_listing_from_ehr({}, index[TALLINN], ref_year=2026)
    assert out["building_net_area_m2"] == pytest.approx(2450.5)
    assert out["build_year"] == 2001
    assert out["building_age_years"] == 25
    assert out["energy_class"] == "C"
    assert prov["build_year"].startswith("EHR")
    # p21 honesty: building area never overwrites the flat's own area.
    assert "area_m2" not in out
    # Listing values win over EHR.
    out2, prov2 = enrich_listing_from_ehr(
        {"energy_class": "B", "build_year": 1999}, index[TALLINN],
        ref_year=2026)
    assert out2["energy_class"] == "B"
    assert out2["build_year"] == 1999
    assert "energy_class" not in prov2 and "build_year" not in prov2
    # Tartu record has no energy class: nothing filled, nothing faked.
    out3, prov3 = enrich_listing_from_ehr({}, index[TARTU], ref_year=2026)
    assert "energy_class" not in out3
    assert out3["build_year"] == 1938
    assert out3["building_age_years"] == 88


def test_p30_lift_and_walkup_bands(index):
    assert dim_accessibility_p30(index[TALLINN])[0] == 100  # EHR lift
    assert dim_accessibility_p30(index[TALLINN], {"floor": 5})[0] == 100
    # Tartu: no lift; ground floor reads 100, walk-ups decay by listing floor.
    assert dim_accessibility_p30(index[TARTU], {"floor": 1})[0] == 100
    assert dim_accessibility_p30(index[TARTU], {"floor": 3})[0] == 60
    assert dim_accessibility_p30(index[TARTU], {"floor": 9})[0] == 25
    # No floor anywhere: NULL, never a guess.
    v, reason = dim_accessibility_p30(index[TARTU])
    assert v is None and "EI OLE" in reason
    # Lift unknown on both sides + floor above ground: NULL (no assuming).
    no_lift = dict(index[TARTU], has_lift=None, elevator_count=None)
    v2, _ = dim_accessibility_p30(no_lift, {"floor": 2})
    assert v2 is None


def test_p48_bands(index):
    assert dim_permit_status_p48(index[TALLINN])[0] == 100  # 0 open / 3 done
    # Tartu fixture carries unpermitted_works=jah AND 1 open permit: the
    # recorded violation dominates the open-permit flag.
    assert dim_permit_status_p48(index[TARTU])[0] == 0
    open_only = dict(index[TARTU], unpermitted_works=False)
    assert dim_permit_status_p48(open_only)[0] == 20  # 1 open
    # Present-but-empty record: NULL, never "clean" (predates digital).
    empty = dict(index[TARTU], permits_open=0, permits_finalized=0,
                 unpermitted_works=False)
    v, reason = dim_permit_status_p48(empty)
    assert v is None and "EI OLE" in reason


def test_p79_p154_p495_bands(index):
    assert dim_permit_history_p79(index[TALLINN])[0] == 85
    assert dim_permit_history_p79(index[TARTU])[0] == 45  # weak, not violation
    assert dim_permit_history_p79({})[0] is None
    assert dim_warranty_p154(index[TALLINN]) == (
        90, "EHR hulgilaadung: ehitusgarantii kehtib")
    assert dim_warranty_p154(index[TARTU])[0] == 50
    # Warranty never derived from age: year present, field absent -> NULL.
    assert dim_warranty_p154({"ehr_code": "X", "build_year": 2024})[0] is None
    assert dim_sunroom_p495(index[TALLINN])[0] == 85
    assert dim_sunroom_p495(index[TARTU])[0] == 20
    assert dim_sunroom_p495({})[0] is None


def test_score_overturn_ehr_joined_and_reasons(index):
    dims, reasons = score_overturn_ehr(index[TARTU], {"floor": 3})
    assert dims == {"accessibility_p30": 60, "permit_status_p48": 0,
                    "permit_history_p79": 45, "warranty_p154": 50,
                    "sunroom_p495": 20}
    assert reasons and all("EHR" in r for r in reasons)


def test_cache_freshness_uses_ttl(tmp_path):
    f = tmp_path / "ehr-bulk-buildings.csv"
    f.write_text("ehr_code\n1\n", encoding="utf-8")
    now = os.path.getmtime(str(f))
    assert cache_is_fresh(str(f), ttl_days=30, now=now + 29 * 86400)
    assert not cache_is_fresh(str(f), ttl_days=30, now=now + 31 * 86400)
    assert not cache_is_fresh(str(tmp_path / "missing.csv"))


def test_fetch_uses_fresh_cache_without_network(tmp_path):
    f = tmp_path / "ehr-bulk-buildings.csv"
    f.write_text("ehr_code\n7\n", encoding="utf-8")
    # Fresh cache + no URL: must NOT raise, must NOT touch network.
    assert fetch_ehr_bulk("buildings", None,
                          cache_dir=str(tmp_path)) == "ehr_code\n7\n"


def test_fetch_empty_url_raises_without_guessing(tmp_path):
    with pytest.raises(ValueError):
        fetch_ehr_bulk("buildings", None, cache_dir=str(tmp_path))


def test_fetch_file_url_writes_cache_and_parses(tmp_path):
    src = tmp_path / "src.csv"
    src.write_text(FIXTURE_CSV, encoding="utf-8")
    text = fetch_ehr_bulk("buildings", src.as_uri(),
                          cache_dir=str(tmp_path / "cache"))
    assert len(parse_ehr_buildings(text)) == 3  # dup kept pre-index
    # Second call is served from cache even if the source disappears.
    src.unlink()
    assert fetch_ehr_bulk("buildings", src.as_uri(),
                          cache_dir=str(tmp_path / "cache")) == text


def test_fetch_transport_error_raises_and_skips_cache(tmp_path):
    missing = tmp_path / "nope.csv"
    with pytest.raises(Exception):
        fetch_ehr_bulk("buildings", missing.as_uri(),
                       cache_dir=str(tmp_path / "cache"))
    assert not os.path.exists(
        os.path.join(str(tmp_path / "cache"), "ehr-bulk-buildings.csv"))


def test_ttl_constant_matches_spec():
    # parameters3.md §5.2: quarterly bulk, 30-day per-code cache TTL.
    assert E.EHR_TTL_DAYS == 30
