"""P4 RB dims (issues #281 + #355): hermetic tests.

No network: the RB bulk endpoint does not exist (2026-09-13 dated
negative, see dims_p4_rb docstring), so every test runs on fixture
row-dicts and hand-built POIs with explicit valuation dates. The
polite fetcher is covered via a stubbed urlopen (cache-hit performs
no request; no-endpoint and transport-error paths return None and
cache nothing); scorers are proven network-free by running them with
urlopen stubbed to raise.
"""

import datetime
import json
import urllib.request

import dims_p4_rb as p4r
import pytest
from dims_p4_rb import (
    CACHE_FILENAME,
    CLEAR_SCORE,
    CORRIDOR_WINDOW_M,
    DOORSTEP_WINDOW_M,
    FAR_PRESSURE_SCORE,
    NEAR_PRESSURE_SCORE,
    NUISANCE_WINDOW_M,
    P4_RB_DIMS,
    PHASE_SCORES,
    RB_BULK_URL,
    RB_TTL_S,
    RB_UA,
    corridors_to_pois,
    dim_ehitusfaas_rb,
    dim_koridor_reserv_rb,
    fetch_rb_snapshot,
    parse_rb_snapshot,
    score_p4_rb,
    snapshot_to_pois,
    works_to_pois,
)

# Tallinn centre: hand-built POIs sit ~57 m east unless stated
# (0.001 deg lon ~= 57 m at 59.44 N; 0.001 deg lat ~= 111 m).
TALLINN = (59.4372, 24.7536)
TODAY = "2026-09-13"
NEXT_YEAR = "2027-09-13"
LAST_YEAR = "2025-09-13"


def mkwork(lat=59.4372, lon=24.7546, phase="ehituses", work_id="ULEM-1",
           title="Ülemiste terminal", vfrom="2024-01-01",
           vuntil="2028-12-31"):
    return {"work_id": work_id, "title": title, "phase": phase,
            "lat": lat, "lon": lon,
            "valid_from": vfrom, "valid_until": vuntil}


def mkcorr(lat=59.4372, lon=24.7546, corr_id="RB-K1",
           name="Ülemiste–Lasnamäe lõik"):
    return {"corr_id": corr_id, "name": name, "lat": lat, "lon": lon}


def pois(works=(), corridors=()):
    return snapshot_to_pois({"works": list(works),
                             "corridors": list(corridors)})


def work_pois(*works):
    return pois(works=works)


def corr_pois(*corrs):
    return pois(corridors=corrs)


class _FakeResp:
    """Minimal urlopen stub (context manager, stdlib-shaped)."""

    def __init__(self, body=b"{}", status=200, ctype="application/json"):
        self._body = body
        self.status = status
        self.headers = {"Content-Type": ctype}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _raise_urlopen(*a, **k):
    raise AssertionError("network touched in a hermetic test")


# ---------------------------------------------------------------------------
# Ingestion contract: TTL, UA, dated negative, cache behaviour.
# ---------------------------------------------------------------------------

def test_ttl_is_monthly_and_bulk_url_is_dated_negative():
    assert RB_TTL_S == 30 * 24 * 3600
    assert RB_BULK_URL is None
    assert "home-finder" in RB_UA and "no scrape" in RB_UA


def test_fetch_cache_hit_performs_no_request(tmp_path, monkeypatch):
    dest = tmp_path / CACHE_FILENAME
    dest.write_text('{"works": [], "corridors": []}', encoding="utf-8")
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    assert fetch_rb_snapshot(str(tmp_path)) == str(dest)


def test_fetch_no_endpoint_performs_no_request(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    assert fetch_rb_snapshot(str(tmp_path)) is None
    assert not (tmp_path / CACHE_FILENAME).exists()


def test_fetch_transport_error_caches_nothing(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise OSError("network down")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert fetch_rb_snapshot(str(tmp_path),
                             bulk_url="https://example.invalid/rb.json") is None
    assert not (tmp_path / CACHE_FILENAME).exists()


def test_fetch_non_json_body_caches_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: _FakeResp(b"<html>hai</html>",
                                                 ctype="text/html"))
    assert fetch_rb_snapshot(str(tmp_path),
                             bulk_url="https://example.invalid/rb.json") is None
    assert not (tmp_path / CACHE_FILENAME).exists()


def test_fetch_json_body_is_stored(tmp_path, monkeypatch):
    body = b'{"works": [], "corridors": []}'
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: _FakeResp(body))
    got = fetch_rb_snapshot(str(tmp_path),
                            bulk_url="https://example.invalid/rb.json")
    assert got == str(tmp_path / CACHE_FILENAME)
    assert json.loads(open(got, encoding="utf-8").read()) == {
        "works": [], "corridors": []}


def test_parse_missing_garbage_and_nondict_are_unknown(tmp_path):
    assert parse_rb_snapshot(str(tmp_path / "nope.json")) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{oops", encoding="utf-8")
    assert parse_rb_snapshot(str(bad)) is None
    lst = tmp_path / "list.json"
    lst.write_text("[1, 2]", encoding="utf-8")
    assert parse_rb_snapshot(str(lst)) is None


def test_parse_keeps_tables_and_skips_nondict_rows(tmp_path):
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps(
        {"works": [mkwork(), "junk", 42],
         "corridors": [mkcorr(), None]}), encoding="utf-8")
    parsed = parse_rb_snapshot(str(snap))
    assert len(parsed["works"]) == 1 and len(parsed["corridors"]) == 1
    assert snapshot_to_pois(None) == []
    assert snapshot_to_pois({"works": "junk"}) == []


def test_readers_drop_coordless_rows_and_normalise():
    pois = works_to_pois([mkwork(), {"work_id": "X", "phase": "ehituses"},
                          {"work_id": "Y", "lat": True, "lon": 24.75,
                           "phase": "ehituses"}])
    assert [p["work_id"] for p in pois] == ["ULEM-1"]
    mixed = works_to_pois([mkwork(phase="  Ehituses ")])[0]
    assert mixed["phase"] == "ehituses"
    assert mixed["valid_until"] == datetime.date(2028, 12, 31)
    nodate = works_to_pois(
        [mkwork(vuntil="millalgi")])[0]
    assert nodate["valid_until"] is None
    cpois = corridors_to_pois([mkcorr(), {"corr_id": "X"}])
    assert [p["corr_id"] for p in cpois] == ["RB-K1"]


# ---------------------------------------------------------------------------
# P4-014 demo: calendar dim with expiry.
# ---------------------------------------------------------------------------

def test_p4_014_phases_score_with_expiry_in_reason(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    for phase, want in (("ehituses", 35), ("planeerimisel", 55),
                        ("valmis", 75)):
        v, reason = dim_ehitusfaas_rb(
            TALLINN, work_pois(mkwork(phase=phase)), TODAY)
        assert v == want == PHASE_SCORES[phase], phase
        assert "hinnang" in reason and "kehtib kuni 2028-12-31" in reason
        assert "Ülemiste terminal" in reason


def test_p4_014_expired_timetable_stays_null(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    v, reason = dim_ehitusfaas_rb(
        TALLINN, work_pois(mkwork(vuntil=LAST_YEAR)), TODAY)
    assert v is None
    assert "EI OLE" in reason and "aegunud" in reason


def test_p4_014_unknown_expiry_and_future_work_stay_null():
    v, reason = dim_ehitusfaas_rb(
        TALLINN, work_pois(mkwork(vuntil=None)), TODAY)
    assert v is None and "EI OLE" in reason
    v, reason = dim_ehitusfaas_rb(
        TALLINN, work_pois(mkwork(vfrom=NEXT_YEAR)), TODAY)
    assert v is None and "EI OLE" in reason


def test_p4_014_unknown_phase_label_stays_null():
    v, reason = dim_ehitusfaas_rb(
        TALLINN, work_pois(mkwork(phase="peatatud?")), TODAY)
    assert v is None
    assert "EI OLE" in reason and "kontrollimata silt" in reason


def test_p4_014_missing_join_stays_null():
    assert dim_ehitusfaas_rb(None, work_pois(mkwork()), TODAY)[0] is None
    assert dim_ehitusfaas_rb(TALLINN, None, TODAY)[0] is None
    v, reason = dim_ehitusfaas_rb(TALLINN, [], TODAY)
    assert v is None and "EI OLE" in reason
    far = work_pois(mkwork(lat=59.4372 + 0.020, lon=24.7536))  # ~2.2 km
    v, reason = dim_ehitusfaas_rb(TALLINN, far, TODAY)
    assert v is None and "EI OLE" in reason and "800 m" in reason


def test_p4_014_nearest_live_work_wins():
    near_stale = mkwork(lat=59.4372, lon=24.7546, work_id="VANA",
                        phase="ehituses", vuntil=LAST_YEAR)
    far_live = mkwork(lat=59.4372, lon=24.7566, work_id="UUS",  # ~170 m
                      phase="planeerimisel")
    v, reason = dim_ehitusfaas_rb(
        TALLINN, work_pois(near_stale, far_live), TODAY)
    assert v == 55 and "UUS" in reason


def test_p4_014_bad_today_raises():
    with pytest.raises(ValueError):
        dim_ehitusfaas_rb(TALLINN, work_pois(mkwork()), "eile")


# ---------------------------------------------------------------------------
# P4-006 coverage: corridor-reservation leg.
# ---------------------------------------------------------------------------

def test_p4_006_corridor_bands_and_clear(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    v, reason = dim_koridor_reserv_rb(TALLINN, corr_pois(mkcorr()))
    assert v == NEAR_PRESSURE_SCORE == 30
    assert "hinnang" in reason and "ukse ees" in reason
    mid = corr_pois(mkcorr(lat=59.4372, lon=24.7586))  # ~285 m
    v, reason = dim_koridor_reserv_rb(TALLINN, mid)
    assert v == FAR_PRESSURE_SCORE == 55
    assert "hinnang" in reason and "500 m" in reason
    far = corr_pois(mkcorr(lat=59.4372 + 0.020, lon=24.7536))  # ~2.2 km
    v, reason = dim_koridor_reserv_rb(TALLINN, far)
    assert v == CLEAR_SCORE == 85
    assert "hinnang" in reason and "pole" in reason


def test_p4_006_missing_join_stays_null():
    assert dim_koridor_reserv_rb(None, corr_pois(mkcorr()))[0] is None
    assert dim_koridor_reserv_rb(TALLINN, None)[0] is None
    v, reason = dim_koridor_reserv_rb(TALLINN, [])
    assert v is None and "EI OLE" in reason
    v, reason = dim_koridor_reserv_rb(TALLINN, work_pois(mkwork()))
    assert v is None and "EI OLE" in reason  # works are not corridors


def test_windows_match_parameters4_shapes():
    assert NUISANCE_WINDOW_M == 800.0
    assert CORRIDOR_WINDOW_M == 500.0
    assert DOORSTEP_WINDOW_M == 150.0


# ---------------------------------------------------------------------------
# Registry + aggregator.
# ---------------------------------------------------------------------------

def test_registry_and_aggregator_cover_both_params():
    assert [k for k, _, _ in P4_RB_DIMS] == ["ehitusfaas_rb",
                                             "koridor_reserv_rb"]
    assert [p for _, p, _ in P4_RB_DIMS] == ["P4-014", "P4-006"]
    full = pois(works=[mkwork(phase="valmis")], corridors=[mkcorr()])
    out = score_p4_rb(TALLINN, full, TODAY)
    assert out == {"ehitusfaas_rb": 75, "koridor_reserv_rb": 30}
    assert score_p4_rb(None, None, TODAY) == {"ehitusfaas_rb": None,
                                              "koridor_reserv_rb": None}
    assert score_p4_rb(TALLINN, [], TODAY) == {"ehitusfaas_rb": None,
                                               "koridor_reserv_rb": None}
    assert p4r.P4_RB_DIMS is P4_RB_DIMS
