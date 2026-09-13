"""Overturn dims for issue #236 (PLANK/TPR per-parcel joins + p274 partial).

Hermetic: every test runs on hand-built parcel rows and fixture snapshot
files under tmp_path. The polite fetcher is covered via a stubbed urlopen
(cache-hit performs no request; the no-endpoint dated-negative path
returns None and caches nothing); the scorers are proven network-free by
running them with urlopen stubbed to raise.
"""

import json
import urllib.request

import dims_overturn_planktpr as overturn
import pytest
from dims_overturn_planktpr import (
    CACHE_FILENAME,
    CEILING_BANDS,
    DECREE_STAGE,
    NO_RESTRICTION_SCORE,
    OVERTURN_BULK_URL,
    OVERTURN_PLANKTPR_DIMS,
    OVERTURN_TTL_S,
    OVERTURN_UA,
    PLANK_WFS_URL,
    RECHECK_AFTER,
    RESTRICTION_PRESENT_SCORE,
    TALLINN_KOVS,
    TPR_INDEX_URL,
    USE_BANDS,
    VERDICT_DATE,
    classify_use,
    dim_airrights_ceiling,
    dim_rentrestr_decree,
    dim_zoning_use,
    fetch_overturn_snapshot,
    parcels_to_index,
    parse_overturn_snapshot,
    score_overturn_planktpr,
    snapshot_to_index,
)


def mkrow(parcel_id="78408:408:0123", kov="Tallinn",
          designated_use="elamumaa", use_stage="kehtestatud",
          max_height_m=12.0, rental_restriction=False,
          decree_ref="Tallinna LV määrus 99"):
    return {"parcel_id": parcel_id, "kov": kov,
            "designated_use": designated_use, "use_stage": use_stage,
            "max_height_m": max_height_m,
            "rental_restriction": rental_restriction,
            "decree_ref": decree_ref}


def index(*rows):
    return snapshot_to_index({"parcels": list(rows)})


def raise_urlopen(*a, **k):
    raise AssertionError("network touched in hermetic test")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", raise_urlopen)


KID = "78408:408:0123"

# ---------------------------------------------------------------------------
# Contract: no open bulk endpoint (dated negative is a code path).
# ---------------------------------------------------------------------------

def test_no_bulk_endpoint_yet():
    assert OVERTURN_BULK_URL is None
    assert PLANK_WFS_URL == "https://planeeringud.ee/geoserver/wfs"
    assert TPR_INDEX_URL == "https://tpr.tallinn.ee/"
    assert OVERTURN_TTL_S == 14 * 24 * 3600  # bi-weekly planning ticket
    assert "home-finder" in OVERTURN_UA
    assert DECREE_STAGE == "kehtestatud"
    assert CACHE_FILENAME == "overturn-planktpr-snapshot.json"


def test_verdict_is_dated_with_recheck_note():
    assert VERDICT_DATE == "2026-09-13"
    assert RECHECK_AFTER == "2027-03-13"
    assert RECHECK_AFTER > VERDICT_DATE


def test_fetch_cache_hit_performs_no_request(tmp_path):
    dest = tmp_path / CACHE_FILENAME
    dest.write_text(json.dumps({"parcels": []}), encoding="utf-8")
    assert fetch_overturn_snapshot(str(tmp_path)) == str(dest)


def test_fetch_without_endpoint_returns_none_and_caches_nothing(tmp_path):
    assert fetch_overturn_snapshot(str(tmp_path)) is None
    assert list(tmp_path.iterdir()) == []


def test_fetch_with_bulk_url_uses_ua_and_caches_json_only(monkeypatch, tmp_path):
    seen = {}

    class Resp:
        status = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"parcels": []}'

    def fake_open(req, timeout=30):
        seen["ua"] = req.get_header("User-agent")
        seen["url"] = req.full_url
        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    got = fetch_overturn_snapshot(str(tmp_path),
                                  bulk_url="https://example.ee/bulk.json")
    assert got == str(tmp_path / CACHE_FILENAME)
    assert seen["url"] == "https://example.ee/bulk.json"
    assert "home-finder" in seen["ua"]
    assert json.loads((tmp_path / CACHE_FILENAME).read_text("utf-8")) == {
        "parcels": []}


def test_fetch_rejects_non_json_without_caching(monkeypatch, tmp_path):
    class Resp:
        status = 200
        headers = {"Content-Type": "text/html"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"<html>spa shell</html>"

    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=30: Resp())
    assert fetch_overturn_snapshot(str(tmp_path),
                                   bulk_url="https://example.ee/spa") is None
    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# Offline readers: parse + Tallinn-filtered exact index.
# ---------------------------------------------------------------------------

def test_parse_missing_file_is_unknown_not_empty():
    assert parse_overturn_snapshot("/tmp/hf236-no-such-file.json") is None
    assert snapshot_to_index(None) == {}


def test_parse_snapshot_file_roundtrip(tmp_path):
    path = tmp_path / "snap.json"
    path.write_text(json.dumps({"parcels": [mkrow(), "junk", 42]}),
                    encoding="utf-8")
    snap = parse_overturn_snapshot(str(path))
    assert snap is not None and len(snap["parcels"]) == 1
    assert snapshot_to_index(snap) == {KID: snap["parcels"][0]}


def test_index_skips_non_tallinn_and_unkeyed_rows():
    idx = index(mkrow(),
                mkrow(parcel_id="  ", kov="Tallinn"),
                mkrow(parcel_id="TARTU-1", kov="Tartu"),
                mkrow(parcel_id="NOKOV-1", kov=None),
                mkrow(parcel_id="TLN-2", kov="Tallinna linn"),
                mkrow(parcel_id="TLN-3", kov="  TALLINN  "))
    assert set(idx) == {KID, "TLN-2", "TLN-3"}


def test_index_join_key_is_whitespace_collapsed():
    idx = index(mkrow(parcel_id="78408:408:0123"))
    assert dim_zoning_use("  78408:408:0123  ", idx)[0] == 80


# ---------------------------------------------------------------------------
# Shared join guard: missing join is unknown, never good.
# ---------------------------------------------------------------------------

def test_missing_parcel_id_stays_null_for_all_dims():
    idx = index(mkrow())
    for fn in (dim_zoning_use, dim_rentrestr_decree, dim_airrights_ceiling):
        for bad in (None, "", "   "):
            v, reason = fn(bad, idx)
            assert v is None
            assert "EI OLE" in reason and "hinnang puudub" in reason


def test_missing_snapshot_and_missing_row_stay_null():
    row_idx = index(mkrow())
    for fn in (dim_zoning_use, dim_rentrestr_decree, dim_airrights_ceiling):
        v, r_none = fn(KID, None)
        assert v is None and "hetktõmmis" in r_none and "EI OLE" in r_none
        v, r_absent = fn("78408:408:9999", row_idx)
        assert v is None and "EI OLE" in r_absent


# ---------------------------------------------------------------------------
# p47: designated-use bands + decree-only discipline.
# ---------------------------------------------------------------------------

def test_zoning_bands_first_cut():
    assert USE_BANDS == {"residential": 80, "mixed": 60, "commercial": 35,
                         "restricted": 20}
    assert dim_zoning_use(KID, index(mkrow(designated_use="elamumaa")))[0] == 80
    assert dim_zoning_use(
        KID, index(mkrow(designated_use="Segafunktsiooniga elamu")))[0] == 60
    assert dim_zoning_use(KID, index(mkrow(designated_use="ärimaa")))[0] == 35
    assert dim_zoning_use(
        KID, index(mkrow(designated_use="Tootmismaa")))[0] == 20


def test_zoning_folds_diacritics_and_case():
    assert classify_use("ÄRIMAA") == "commercial"
    assert classify_use("arimaa") == "commercial"
    assert classify_use("  Elamumaa  ") == "residential"
    assert classify_use("SEGAAHOONESTUSALA") == "mixed"


def test_zoning_restricted_wins_over_housing_stems():
    # A tootmis- prefix is never housing, even with elamu in the string.
    assert classify_use("tootmis- ja elamu segatsoon") == "restricted"
    assert classify_use("ärimaa elamufunktsiooniga") == "mixed"


def test_zoning_non_decree_stage_and_unknown_code_stay_null():
    v, reason = dim_zoning_use(
        KID, index(mkrow(use_stage="menetluses")))
    assert v is None
    assert "EI OLE" in reason and "menetluses" in reason
    v, reason = dim_zoning_use(KID, index(mkrow(use_stage=None)))
    assert v is None and "EI OLE" in reason
    v, reason = dim_zoning_use(
        KID, index(mkrow(designated_use="tundmatu-kood-zzz")))
    assert v is None
    assert "EI OLE" in reason and "tundmatut koodi ei eelda" in reason
    v, reason = dim_zoning_use(KID, index(mkrow(designated_use=None)))
    assert v is None and "EI OLE" in reason


def test_zoning_reason_marks_estimate_and_commercial_financing_flag():
    v, reason = dim_zoning_use(
        KID, index(mkrow(designated_use="elamumaa")), "2026-09-13")
    assert v == 80
    assert "hinnang" in reason and KID in reason
    assert "elamumaa" in reason and "2026-09-13" in reason
    v, reason = dim_zoning_use(KID, index(mkrow(designated_use="ärimaa")))
    assert v == 35
    assert "finantseerimispiiranguid" in reason and "notarilt" in reason


def test_zoning_never_consults_osm_landuse():
    # Fake-precision guard: no OSM tag input exists in the signature and
    # no reason may claim a descriptive-landuse verdict.
    idx = index(mkrow())
    for fn in (dim_zoning_use, dim_rentrestr_decree, dim_airrights_ceiling):
        _, reason = fn(KID, idx)
        assert "landuse" not in reason.lower()
        assert "kirjeldav" not in reason.lower()


# ---------------------------------------------------------------------------
# p74: decree rows only.
# ---------------------------------------------------------------------------

def test_rentrestr_present_names_decree_and_scores_low():
    assert RESTRICTION_PRESENT_SCORE == 30
    v, reason = dim_rentrestr_decree(
        KID, index(mkrow(rental_restriction=True,
                         decree_ref="TLV määrus 12 §3")))
    assert v == 30
    assert "hinnang" in reason and "TLV määrus 12 §3" in reason
    assert "notari kinnitust" in reason


def test_rentrestr_absent_is_measured_clear_capped():
    assert NO_RESTRICTION_SCORE == 80
    v, reason = dim_rentrestr_decree(
        KID, index(mkrow(rental_restriction=False)), "2026-09-13")
    assert v == 80
    assert "hinnang" in reason and "2026-09-13" in reason
    assert "mitte garantii" in reason


def test_rentrestr_unknown_flag_stays_null():
    v, reason = dim_rentrestr_decree(
        KID, index(mkrow(rental_restriction=None)))
    assert v is None
    assert "EI OLE" in reason and "Riigi Teatajat" in reason


# ---------------------------------------------------------------------------
# p274 partial: ceiling proxy with soft caps, never the deed.
# ---------------------------------------------------------------------------

def test_ceiling_bands_stay_inside_soft_caps():
    assert [pts for _, pts in CEILING_BANDS] == [55, 60, 65]
    assert dim_airrights_ceiling(KID, index(mkrow(max_height_m=8.0)))[0] == 55
    assert dim_airrights_ceiling(KID, index(mkrow(max_height_m=9.0)))[0] == 55
    assert dim_airrights_ceiling(KID, index(mkrow(max_height_m=12.0)))[0] == 60
    assert dim_airrights_ceiling(KID, index(mkrow(max_height_m=120.0)))[0] == 65


def test_ceiling_sweep_never_escapes_soft_caps():
    idx = index(mkrow())
    for h in (0.5, 3.0, 9.0, 9.1, 25.0, 25.1, 60.0, 300.0):
        v, _ = dim_airrights_ceiling(
            KID, index(mkrow(max_height_m=h)))
        assert v is not None and 55 <= v <= 65
    assert dim_airrights_ceiling(KID, idx)[0] == 60  # fixture default 12.0


def test_ceiling_garbage_and_missing_stay_null():
    for bad in (None, True, False, 0, -3.0, float("nan"),
                float("inf"), "kõrge", [12]):
        v, reason = dim_airrights_ceiling(
            KID, index(mkrow(max_height_m=bad)))
        assert v is None, bad
        assert "EI OLE" in reason


def test_ceiling_reason_disclaims_the_deed():
    v, reason = dim_airrights_ceiling(
        KID, index(mkrow(max_height_m=12.0)), "2026-09-13")
    assert v == 60
    assert "hinnang" in reason and "lagi-proksi" in reason
    assert "lagi ≠ õigus" in reason and "EI OLE tõestatud" in reason
    assert "kinnistusraamatu väljavõtet" in reason
    assert "2026-09-13" in reason and "12.0 m" in reason


# ---------------------------------------------------------------------------
# Registry + aggregator + honesty markers across every path.
# ---------------------------------------------------------------------------

def test_registry_and_aggregator_cover_three_dims():
    assert [k for k, _, _ in OVERTURN_PLANKTPR_DIMS] == [
        "zoning_use_overturn", "rentrestr_decree_overturn",
        "airrights_ceiling_overturn"]
    assert [p for _, p, _ in OVERTURN_PLANKTPR_DIMS] == ["p47", "p74", "p274"]
    assert len({fn for _, _, fn in OVERTURN_PLANKTPR_DIMS}) == 3
    assert overturn.OVERTURN_PLANKTPR_DIMS is OVERTURN_PLANKTPR_DIMS
    idx = index(mkrow())
    assert score_overturn_planktpr(KID, idx) == {
        "zoning_use_overturn": 80, "rentrestr_decree_overturn": 80,
        "airrights_ceiling_overturn": 60}
    assert score_overturn_planktpr(KID, None) == {
        "zoning_use_overturn": None, "rentrestr_decree_overturn": None,
        "airrights_ceiling_overturn": None}
    assert score_overturn_planktpr(None, None) == {
        "zoning_use_overturn": None, "rentrestr_decree_overturn": None,
        "airrights_ceiling_overturn": None}


def test_every_reason_is_honest_estonian():
    idx = index(mkrow(), mkrow(parcel_id="R-RESTRICT",
                               rental_restriction=True,
                               decree_ref="TLV määrus 1"),
                mkrow(parcel_id="U-STAGE", use_stage="algatatud"),
                mkrow(parcel_id="U-CODE", designated_use="zzz-tundmatu"),
                mkrow(parcel_id="U-FLAG", rental_restriction=None),
                mkrow(parcel_id="U-HEIGHT", max_height_m=None))
    scored, nulls = [], []
    for fn, kid in ((dim_zoning_use, KID), (dim_zoning_use, "U-STAGE"),
                    (dim_zoning_use, "U-CODE"),
                    (dim_rentrestr_decree, KID),
                    (dim_rentrestr_decree, "R-RESTRICT"),
                    (dim_rentrestr_decree, "U-FLAG"),
                    (dim_airrights_ceiling, KID),
                    (dim_airrights_ceiling, "U-HEIGHT"),
                    (dim_zoning_use, "MISSING"),
                    (dim_rentrestr_decree, None),
                    (dim_airrights_ceiling, None)):
        v, reason = fn(kid, idx)
        (scored if v is not None else nulls).append(reason)
    assert scored and nulls
    for reason in scored:
        assert "hinnang" in reason
        assert "garanteeritud" not in reason
        assert "mõõdetud puhas" not in reason
    for reason in nulls:
        assert "EI OLE" in reason
        assert "ära feigi" in reason or "kontrolli" in reason
