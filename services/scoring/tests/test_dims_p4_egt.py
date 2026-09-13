"""P4 EGT dims (issues #288 + #361): hermetic tests.

No network: no EGT bulk endpoint exists (2026-09-13 dated verdict,
see dims_p4_egt docstring), so every test runs on fixture row-dicts
and hand-built POIs. The polite fetcher is covered via a stubbed
urlopen (cache-hit performs no request; no-endpoint and
transport-error paths return None and cache nothing); scorers are
proven network-free by running them with urlopen stubbed to raise.
"""

import json
import urllib.request

import dims_p4_egt as p4e
import pytest
from dims_p4_egt import (
    CACHE_FILENAME,
    CLASS_WINDOW_M,
    EGT_BULK_URL,
    EGT_TTL_S,
    EGT_UA,
    KLASS_SCORES,
    NO_TIMETABLE,
    P4_EGT_DIMS,
    QUARRY_FAR_M,
    QUARRY_FAR_SCORE,
    QUARRY_NEAR_M,
    QUARRY_NEAR_SCORE,
    classes_to_pois,
    dim_karjaar_egt,
    dim_pinnas_klass_egt,
    fetch_egt_snapshot,
    parse_egt_snapshot,
    quarries_to_pois,
    score_p4_egt,
    snapshot_to_pois,
)

# Tallinn centre: hand-built POIs sit ~57 m east unless stated
# (0.001 deg lon ~= 57 m at 59.44 N; 0.001 deg lat ~= 111 m).
TALLINN = (59.4372, 24.7536)


def mkclass(lat=59.4372, lon=24.7546, klass="turvas", class_id="EGT-C1",
            name="Pääsküla raba serv"):
    return {"class_id": class_id, "name": name, "klass": klass,
            "lat": lat, "lon": lon}


def mkquarry(lat=59.4372, lon=24.7546, quarry_id="EGT-Q1",
             name="Maardu paekivi"):
    return {"quarry_id": quarry_id, "name": name,
            "lat": lat, "lon": lon}


def class_pois(*rows):
    return snapshot_to_pois({"classes": list(rows), "quarries": []})


def quarry_pois(*rows):
    return snapshot_to_pois({"classes": [], "quarries": list(rows)})


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
# Ingestion contract: TTL, UA, dated verdict, cache behaviour.
# ---------------------------------------------------------------------------

def test_ttl_is_annual_and_bulk_url_is_dated_negative():
    assert EGT_TTL_S == 365 * 24 * 3600
    assert EGT_BULK_URL is None
    assert "home-finder" in EGT_UA and "no scrape" in EGT_UA


def test_fetch_cache_hit_performs_no_request(tmp_path, monkeypatch):
    dest = tmp_path / CACHE_FILENAME
    dest.write_text('{"classes": [], "quarries": []}', encoding="utf-8")
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    assert fetch_egt_snapshot(str(tmp_path)) == str(dest)


def test_fetch_no_endpoint_performs_no_request(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    assert fetch_egt_snapshot(str(tmp_path)) is None
    assert not (tmp_path / CACHE_FILENAME).exists()


def test_fetch_transport_error_caches_nothing(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise OSError("network down")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert fetch_egt_snapshot(str(tmp_path),
                              bulk_url="https://example.invalid/egt.json") is None
    assert not (tmp_path / CACHE_FILENAME).exists()


def test_fetch_non_json_body_caches_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: _FakeResp(b"<html>hai</html>",
                                                 ctype="text/html"))
    assert fetch_egt_snapshot(str(tmp_path),
                              bulk_url="https://example.invalid/egt.json") is None
    assert not (tmp_path / CACHE_FILENAME).exists()


def test_fetch_json_body_is_stored(tmp_path, monkeypatch):
    body = b'{"classes": [], "quarries": []}'
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: _FakeResp(body))
    got = fetch_egt_snapshot(str(tmp_path),
                             bulk_url="https://example.invalid/egt.json")
    assert got == str(tmp_path / CACHE_FILENAME)
    assert json.loads(open(got, encoding="utf-8").read()) == {
        "classes": [], "quarries": []}


def test_parse_missing_garbage_and_nondict_are_unknown(tmp_path):
    assert parse_egt_snapshot(str(tmp_path / "nope.json")) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{oops", encoding="utf-8")
    assert parse_egt_snapshot(str(bad)) is None
    lst = tmp_path / "list.json"
    lst.write_text("[1, 2]", encoding="utf-8")
    assert parse_egt_snapshot(str(lst)) is None


def test_parse_keeps_tables_and_skips_nondict_rows(tmp_path):
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps(
        {"classes": [mkclass(), "junk", 42],
         "quarries": [mkquarry(), None]}), encoding="utf-8")
    parsed = parse_egt_snapshot(str(snap))
    assert len(parsed["classes"]) == 1 and len(parsed["quarries"]) == 1
    assert snapshot_to_pois(None) == []
    assert snapshot_to_pois({"classes": "junk"}) == []


def test_readers_drop_coordless_rows_and_normalise():
    pois = classes_to_pois([mkclass(), {"class_id": "X", "klass": "karst"},
                            {"class_id": "Y", "lat": True, "lon": 24.75,
                             "klass": "karst"}])
    assert [p["class_id"] for p in pois] == ["EGT-C1"]
    mixed = classes_to_pois([mkclass(klass="  Karst ")])[0]
    assert mixed["klass"] == "karst"
    unknown = classes_to_pois([mkclass(klass="liiv??")])[0]
    assert unknown["klass"] == "liiv??"
    qpois = quarries_to_pois([mkquarry(), {"quarry_id": "X"}])
    assert [p["quarry_id"] for p in qpois] == ["EGT-Q1"]


# ---------------------------------------------------------------------------
# P4-016 demo: EGT-map-class leg.
# ---------------------------------------------------------------------------

def test_p4_016_classes_score_with_coarse_in_reason(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    for klass, want in (("karst", 30), ("turvas", 35),
                        ("alvar", 55), ("kandev", 70)):
        v, reason = dim_pinnas_klass_egt(
            TALLINN, class_pois(mkclass(klass=klass)))
        assert v == want == KLASS_SCORES[klass], klass
        assert "hinnang" in reason and "jäme" in reason
        assert "Pääsküla raba serv" in reason


def test_p4_016_mapped_clean_caps_at_70(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    v, reason = dim_pinnas_klass_egt(
        TALLINN, class_pois(mkclass(klass="kandev")))
    assert v == 70 and "mõõtkavaklass" in reason


def test_p4_016_unknown_klass_label_stays_null():
    v, reason = dim_pinnas_klass_egt(
        TALLINN, class_pois(mkclass(klass="liiv??")))
    assert v is None
    assert "EI OLE" in reason and "kontrollimata silt" in reason


def test_p4_016_missing_join_stays_null():
    assert dim_pinnas_klass_egt(None, class_pois(mkclass()))[0] is None
    assert dim_pinnas_klass_egt(TALLINN, None)[0] is None
    v, reason = dim_pinnas_klass_egt(TALLINN, [])
    assert v is None and "EI OLE" in reason


def test_p4_016_beyond_window_stays_null_not_good():
    far = mkclass(lat=59.4372 + 0.010, lon=24.7546)  # ~1.1 km north
    v, reason = dim_pinnas_klass_egt(TALLINN, class_pois(far))
    assert v is None
    assert "EI OLE" in reason and "teadmata" in reason


# ---------------------------------------------------------------------------
# P4-054 coverage: EGT-deposit leg.
# ---------------------------------------------------------------------------

def test_p4_054_near_and_far_bands_with_timetable_note(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    v, reason = dim_karjaar_egt(TALLINN, quarry_pois(mkquarry()))
    assert v == QUARRY_NEAR_SCORE == 25
    assert "hinnang" in reason and "Maardu paekivi" in reason
    assert "EI OLE" in reason  # timetable leg named even when scoring
    mid = mkquarry(lat=59.4372 + 0.010, lon=24.7546)  # ~1.1 km north
    v, reason = dim_karjaar_egt(TALLINN, quarry_pois(mid))
    assert v == QUARRY_FAR_SCORE == 45
    assert "jäme" in reason and "EI OLE" in reason


def test_p4_054_beyond_window_stays_null_not_quiet():
    far = mkquarry(lat=59.4372 + 0.030, lon=24.7546)  # ~3.3 km north
    v, reason = dim_karjaar_egt(TALLINN, quarry_pois(far))
    assert v is None
    assert "EI OLE" in reason and "teadmata" in reason


def test_p4_054_missing_join_stays_null():
    assert dim_karjaar_egt(None, quarry_pois(mkquarry()))[0] is None
    assert dim_karjaar_egt(TALLINN, None)[0] is None
    v, reason = dim_karjaar_egt(TALLINN, [])
    assert v is None and "EI OLE" in reason


def test_windows_match_documented_contract():
    assert CLASS_WINDOW_M == 500.0
    assert QUARRY_NEAR_M == 500.0
    assert QUARRY_FAR_M == 2000.0
    assert NO_TIMETABLE and "EI OLE" in NO_TIMETABLE


# ---------------------------------------------------------------------------
# Registry + entry point (central follow-up reads P4_EGT_DIMS).
# ---------------------------------------------------------------------------

def test_registry_keys_params_and_entry_point():
    assert [(k, p) for k, p, _ in P4_EGT_DIMS] == [
        ("pinnas_klass_egt", "P4-016"), ("karjaar_egt", "P4-054")]
    out = score_p4_egt(TALLINN,
                       class_pois(mkclass()) + quarry_pois(mkquarry()))
    assert out == {"pinnas_klass_egt": 35, "karjaar_egt": 25}
    assert score_p4_egt(TALLINN, []) == {
        "pinnas_klass_egt": None, "karjaar_egt": None}
    assert score_p4_egt(None, None) == {
        "pinnas_klass_egt": None, "karjaar_egt": None}
    for key, _, fn in P4_EGT_DIMS:
        assert callable(fn)
    assert p4e.EGT_INDEX_URL.startswith("https://")
    assert p4e.EGT_GEOIPORTAAL_URL.startswith("https://")


def test_scorers_never_touch_network(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    dim_pinnas_klass_egt(TALLINN, class_pois(mkclass(klass="alvar")))
    dim_karjaar_egt(TALLINN, quarry_pois(mkquarry()))
    score_p4_egt(TALLINN, [])
