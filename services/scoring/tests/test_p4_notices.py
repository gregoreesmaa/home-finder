"""P4 notice-watch dims (issue #550): hermetic tests, fixtures only."""

from datetime import date

import dims_p4_notices as notices
from dims_p4_notices import (
    P4_NOTICES_DIMS,
    P4_NOTICES_PARAM_IDS,
    build_bulk_url,
    cache_is_fresh,
    classify_notice,
    dim_felling_watch,
    dim_notice_watch,
    is_expired,
    linkage_rate,
    score_p4_notices,
)

TALLINN = (59.4372, 24.7536)
TODAY = date(2026, 9, 16)


def _n(pealiik="keskkonnaluba",
       alaliik="kaevandamisloa-menetluse-algatamine",
       published=date(2026, 6, 1), archived=None,
       distance_m=500.0, parcel_linked=True, num="12345"):
    return {"pealiik": pealiik, "alaliik": alaliik, "published": published,
            "archived": archived, "distance_m": distance_m,
            "parcel_linked": parcel_linked, "teate_number": num}


def test_taxonomy_quarry_zoning_cadastre():
    assert classify_notice("keskkonnaluba",
                           "kaevandamisloa-menetluse-algatamine") == "quarry"
    assert classify_notice("keskkonnaluba",
                           "keskkonnaloa-menetluse-algatamise-teade") == "quarry"
    assert classify_notice("planeeringud",
                           "detailplaneeringu-algatamine") == "zoning"
    assert classify_notice("planeeringud",
                           "detailplaneeringu-kehtestamine") == "zoning"
    assert classify_notice("maakatastri-teated",
                           "maakatastri-teade") == "cadastre"
    # Out of scope: enforcement, auctions, felling-rights sale.
    assert classify_notice("keskkonnaluba", "tundmatu-alaliik") is None
    assert classify_notice("pankrot", "pankrotiteade") is None
    assert classify_notice("enapakkumine-myyk",
                           "metsa-raieoiguse-ja-metsamaterjali-myyk") is None


def test_quarry_application_flags_35():
    v, reason = dim_notice_watch(TALLINN, {"notices": [_n()]}, TODAY)
    assert v == 35
    assert "karjääri" in reason
    assert "ei ole heakskiit" in reason


def test_zoning_hearing_flags_55_and_worst_wins():
    zoning = _n(pealiik="planeeringud",
               alaliik="detailplaneeringu-algatamine", distance_m=900.0)
    v, _ = dim_notice_watch(TALLINN, {"notices": [zoning]}, TODAY)
    assert v == 55
    v2, reason2 = dim_notice_watch(
        TALLINN, {"notices": [zoning, _n(distance_m=100.0)]}, TODAY)
    assert v2 == 35  # worst active notice wins
    assert "1000m" in reason2


def test_cadastre_band_500m():
    v, _ = dim_notice_watch(TALLINN, {"notices": [
        _n(pealiik="maakatastri-teated", alaliik="maakatastri-teade",
           distance_m=400.0)]}, TODAY)
    assert v == 60
    v2, _ = dim_notice_watch(TALLINN, {"notices": [
        _n(pealiik="maakatastri-teated", alaliik="maakatastri-teade",
           distance_m=600.0)]}, TODAY)
    assert v2 is None


def test_expired_is_null_never_scored():
    archived = _n(archived=date(2026, 1, 1))
    old = _n(published=date(2024, 1, 1), archived=None)
    for n in (archived, old):
        v, reason = dim_notice_watch(TALLINN, {"notices": [n]}, TODAY)
        assert v is None
        assert "EI OLE" in reason
    assert is_expired(date(2026, 6, 1), None, TODAY) is False
    assert is_expired(date(2026, 6, 1), date(2026, 7, 1), TODAY) is True


def test_unlinked_notices_stay_out_counted():
    v, reason = dim_notice_watch(
        TALLINN, {"notices": [_n(parcel_linked=False)]}, TODAY)
    assert v is None
    assert "1 teadet ilma asukohaseoseta" in reason


def test_no_pull_and_empty_pull():
    v, reason = dim_notice_watch(TALLINN, None, TODAY)
    assert v is None
    assert "EI OLE" in reason
    v2, reason2 = dim_notice_watch(TALLINN, {"notices": []}, TODAY)
    assert v2 == 70  # capped weak-good, never 100
    assert "1000" in reason2


def test_linkage_rate_zero_structured():
    assert linkage_rate([]) == (0, 0)
    assert linkage_rate([_n(parcel_linked=False),
                         _n(parcel_linked=False)]) == (0, 2)
    assert linkage_rate([_n(parcel_linked=True)]) == (1, 1)


def test_felling_leg_always_null():
    for pull in (None, {"notices": []}, {"notices": [_n()]}):
        v, reason = dim_felling_watch(TALLINN, pull)
        assert v is None
        assert "EI OLE" in reason
        assert "metsaregistrisse" in reason


def test_bulk_url_and_cache():
    url = build_bulk_url("keskkonnaamet", "keskkonnaluba",
                         "kaevandamisloa-menetluse-algatamine")
    assert url == ("https://www.ametlikudteadaanded.ee/ee/keskkonnaamet/"
                   "keskkonnaluba/kaevandamisloa-menetluse-algatamine/xml")
    assert build_bulk_url("a", "b") == \
        "https://www.ametlikudteadaanded.ee/ee/a/b/xml"
    assert cache_is_fresh("/nonexistent-xyz-notices") is False


def test_registry_and_rollup():
    assert set(P4_NOTICES_DIMS) == {"notice_watch", "felling_watch"}
    assert P4_NOTICES_PARAM_IDS == {"notice_watch": 550,
                                    "felling_watch": 550}
    assert P4_NOTICES_DIMS["notice_watch"][1] is dim_notice_watch
    assert notices.P4_NOTICES_DIMS is P4_NOTICES_DIMS
    dims, reasons = score_p4_notices(TALLINN, {"notices": [_n()]}, TODAY)
    assert dims == {"notice_watch": 35, "felling_watch": None}
    assert len(reasons) == 1  # NULL dims contribute no reasons
    dims_none, reasons_none = score_p4_notices(TALLINN, None, TODAY)
    assert dims_none == {"notice_watch": None, "felling_watch": None}
    assert reasons_none == []
