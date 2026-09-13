"""P4 PLANK dims (issue #251): hermetic tests.

No network: the PLANK national WFS endpoint is gone (2026-09-13 dated
negative, see dims_p4_plank docstring), so every test runs on fixture
row-dicts and hand-built POIs. The polite fetcher is covered via a
stubbed urlopen (cache-hit performs no request; no-endpoint and
transport-error paths return None and cache nothing); the scorer is
proven network-free by running it with urlopen stubbed to raise.
"""

import json
import urllib.request

import dims_p4_plank as p4p
import pytest
from dims_p4_plank import (
    CACHE_FILENAME,
    PIPELINE_STAGE,
    PLANK_BULK_URL,
    PLANK_TTL_S,
    PLANK_UA,
    PLANK_WFS_URL,
    P4_PLANK_DIMS,
    TALLINN_KOVS,
    dim_pipeline_plank_500m,
    fetch_plank_snapshot,
    parse_plank_snapshot,
    plans_to_pois,
    score_p4_plank,
    snapshot_to_pois,
)

# Tallinn centre: hand-built POIs sit ~57 m east unless stated
# (0.001 deg lon ~= 57 m at 59.44 N).
TALLINN = (59.4372, 24.7536)


def mkplan(lat=59.4372, lon=24.7546, stage="menetluses", plan_id="PL-1",
           kov="Tallinn"):
    return {"plan_id": plan_id, "stage": stage, "kov": kov,
            "lat": lat, "lon": lon}


def pois(*plans):
    return snapshot_to_pois({"plans": list(plans)})


def raise_urlopen(*a, **k):
    raise AssertionError("network touched in hermetic test")


# ---------------------------------------------------------------------------
# Contract: no open bulk endpoint (dated negative is a code path).
# ---------------------------------------------------------------------------

def test_no_bulk_endpoint_yet():
    assert PLANK_BULK_URL is None
    assert PLANK_WFS_URL == "https://planeeringud.ee/geoserver/wfs"
    assert PLANK_TTL_S == 7 * 24 * 3600  # weekly pull ticket
    assert "home-finder" in PLANK_UA
    assert PIPELINE_STAGE == "menetluses"


# ---------------------------------------------------------------------------
# P4-006 PLANK leg: pipeline bands.
# ---------------------------------------------------------------------------

def test_pipeline_zero_in_buffer_scores_clear_when_snapshot_has_plans():
    far = mkplan(lon=24.7746, plan_id="PL-FAR")  # ~1.1 km east, in snapshot
    v, reason = dim_pipeline_plank_500m(TALLINN, pois(far))
    assert v == 90
    assert "hinnang" in reason and "0" in reason


def test_pipeline_bands_count_menetluses_only():
    near = dict(lon=24.7546)
    assert dim_pipeline_plank_500m(
        TALLINN, pois(mkplan(**near, plan_id="A")))[0] == 65
    assert dim_pipeline_plank_500m(
        TALLINN, pois(mkplan(**near, plan_id="A"),
                      mkplan(lat=59.4375, plan_id="B")))[0] == 40
    assert dim_pipeline_plank_500m(
        TALLINN, pois(mkplan(**near, plan_id="A"),
                      mkplan(lat=59.4375, plan_id="B"),
                      mkplan(lat=59.4369, plan_id="C"),
                      mkplan(lat=59.4370, plan_id="D")))[0] == 20


def test_pipeline_ignores_other_stages_and_case_folds():
    ps = pois(mkplan(plan_id="K", stage="kehtestatud"),
              mkplan(lat=59.4375, plan_id="I", stage="algatatud"),
              mkplan(lat=59.4369, plan_id="L",
                     stage="kehtetuks tunnistatud"),
              mkplan(lat=59.4370, plan_id="FAR2", stage="menetluses",
                     lon=24.7746))
    v, reason = dim_pipeline_plank_500m(TALLINN, ps)
    assert v == 90  # in-flight labels are NOT counted (conservative)
    assert "hinnang" in reason
    v2, _ = dim_pipeline_plank_500m(
        TALLINN, pois(mkplan(plan_id="M", stage="Menetluses")))
    assert v2 == 65


def test_pipeline_beyond_500m_does_not_count():
    ps = pois(mkplan(plan_id="OUT", lon=24.7646),  # ~566 m east
              mkplan(plan_id="FAR", lon=24.7746))
    v, _ = dim_pipeline_plank_500m(TALLINN, ps)
    assert v == 90


def test_pipeline_null_without_snapshot():
    for origin, p in [(None, pois(mkplan())), (TALLINN, None),
                      (None, None)]:
        v, reason = dim_pipeline_plank_500m(origin, p)
        assert v is None
        assert "EI OLE" in reason
    v, reason = dim_pipeline_plank_500m(TALLINN, [])
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# Tallinn filter: national rows never join a Tallinn buffer.
# ---------------------------------------------------------------------------

def test_tallinn_filter_skips_non_tallinn_rows():
    # Tartu + Pärnu menetluses plans next door must not count.
    ps = pois(mkplan(plan_id="TARTU", kov="Tartu"),
              mkplan(lat=59.4375, plan_id="PARNU", kov="Pärnu"),
              mkplan(lat=59.4369, plan_id="TLL", kov="Tallinn",
                     lon=24.7746))  # far Tallinn plan keeps snapshot non-empty
    v, reason = dim_pipeline_plank_500m(TALLINN, ps)
    assert v == 90
    assert "hinnang" in reason


def test_tallinn_filter_accepts_spelling_variants():
    assert dim_pipeline_plank_500m(
        TALLINN, pois(mkplan(plan_id="A", kov="Tallinna linn")))[0] == 65
    assert dim_pipeline_plank_500m(
        TALLINN, pois(mkplan(plan_id="B", kov="  TALLINN  ")))[0] == 65
    assert TALLINN_KOVS == frozenset({"tallinn", "tallinna linn"})


def test_tallinn_filter_missing_kov_is_unknown_not_tallinn():
    row = {"plan_id": "NOKOV", "stage": "menetluses",
           "lat": 59.4372, "lon": 24.7546}  # no kov
    far = mkplan(lon=24.7746, plan_id="FAR")
    v, reason = dim_pipeline_plank_500m(TALLINN, pois(row, far))
    assert v == 90  # kov-less row skipped, far Tallinn plan proves clear
    assert "hinnang" in reason
    # kov-less rows ALONE leave no Tallinn POIs -> NULL, never clear.
    v, reason = dim_pipeline_plank_500m(TALLINN, pois(row))
    assert v is None and "EI OLE" in reason


def test_only_non_tallinn_snapshot_stays_null():
    ps = pois(mkplan(plan_id="T1", kov="Tartu"),
              mkplan(lat=59.4375, plan_id="H1", kov="Harjumaa"))
    v, reason = dim_pipeline_plank_500m(TALLINN, ps)
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# Honesty markers.
# ---------------------------------------------------------------------------

def test_scored_reason_says_hinnang_with_components():
    v, r = dim_pipeline_plank_500m(TALLINN, pois(mkplan(plan_id="PL-9")))
    assert v == 65 and "hinnang" in r and "PL-9" in r


def test_null_reason_carries_ei_ole_and_no_fake_precision():
    _, reason = dim_pipeline_plank_500m(TALLINN, None)
    assert "EI OLE" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_scorer_never_touches_network(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", raise_urlopen)
    full = pois(mkplan())
    dim_pipeline_plank_500m(TALLINN, full)
    dim_pipeline_plank_500m(TALLINN, [])
    dim_pipeline_plank_500m(None, None)


# ---------------------------------------------------------------------------
# Offline readers: malformed + non-Tallinn rows skipped, missing file None.
# ---------------------------------------------------------------------------

FIXTURE = {
    "plans": [
        {"plan_id": "PL-1", "stage": "menetluses", "kov": "Tallinn",
         "lat": 59.4372, "lon": 24.7546},
        {"plan_id": "PL-2", "stage": "menetluses", "kov": "Tallinna linn",
         "lat": 59.4375, "lon": 24.7546},
        {"plan_id": "TARTU", "stage": "menetluses", "kov": "Tartu",
         "lat": 59.4372, "lon": 24.7546},  # skipped: Tallinn filter
        {"plan_id": "NOKOV", "stage": "menetluses",
         "lat": 59.4372, "lon": 24.7546},  # skipped: unknown municipality
        {"plan_id": "BAD", "stage": "menetluses",
         "kov": "Tallinn"},  # no coords: skipped
        {"plan_id": "BOOL", "stage": "kehtestatud", "kov": "Tallinn",
         "lat": True, "lon": 24.7546},  # skipped
    ],
}


def test_readers_skip_malformed_and_non_tallinn_never_fake():
    ps = snapshot_to_pois(FIXTURE)
    assert {p["plan_id"] for p in ps} == {"PL-1", "PL-2"}
    assert all(p["kind"] == "plan_plank" for p in ps)
    assert snapshot_to_pois(None) == []
    assert snapshot_to_pois({"plans": "nope"}) == []


def test_fixture_end_to_end_shape():
    ps = snapshot_to_pois(FIXTURE)
    v, reason = dim_pipeline_plank_500m(TALLINN, ps)
    assert v == 40  # PL-1 + PL-2 menetluses in buffer
    assert "hinnang" in reason


def test_parse_snapshot_roundtrip_and_missing(tmp_path):
    fp = tmp_path / "snap.json"
    fp.write_text(json.dumps(FIXTURE), encoding="utf-8")
    snap = parse_plank_snapshot(str(fp))
    assert snap is not None and len(snap["plans"]) == 6
    assert parse_plank_snapshot(str(tmp_path / "absent.json")) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert parse_plank_snapshot(str(bad)) is None
    lst = tmp_path / "list.json"
    lst.write_text("[1,2]", encoding="utf-8")
    assert parse_plank_snapshot(str(lst)) is None


# ---------------------------------------------------------------------------
# Polite fetcher: cache hit = no request; no endpoint = no request.
# ---------------------------------------------------------------------------

def test_fetch_cache_hit_performs_no_request(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", raise_urlopen)
    dest = tmp_path / CACHE_FILENAME
    dest.write_text("{}", encoding="utf-8")
    assert fetch_plank_snapshot(str(tmp_path)) == str(dest)


def test_fetch_without_endpoint_performs_no_request(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", raise_urlopen)
    assert fetch_plank_snapshot(str(tmp_path), bulk_url=None) is None
    assert not (tmp_path / CACHE_FILENAME).exists()  # errors cache nothing


def test_fetch_transport_error_caches_nothing(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise OSError("network down")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    url = "https://example.invalid/plank.json"
    assert fetch_plank_snapshot(str(tmp_path), bulk_url=url) is None
    assert not (tmp_path / CACHE_FILENAME).exists()


def test_fetch_rejects_non_json_body(tmp_path, monkeypatch):
    class Resp:
        status = 200
        headers = {"Content-Type": "text/html"}

        def read(self):
            return b"<html>register</html>"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: Resp())
    assert fetch_plank_snapshot(
        str(tmp_path), bulk_url="https://example.invalid/x") is None
    assert not (tmp_path / CACHE_FILENAME).exists()


def test_fetch_stores_json_snapshot(tmp_path, monkeypatch):
    body = json.dumps({"plans": []}).encode()

    class Resp:
        status = 200
        headers = {"Content-Type": "application/json"}

        def read(self):
            return body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: Resp())
    got = fetch_plank_snapshot(str(tmp_path),
                               bulk_url="https://example.invalid/plank.json")
    assert got == str(tmp_path / CACHE_FILENAME)
    assert parse_plank_snapshot(got) == {"plans": []}


# ---------------------------------------------------------------------------
# Registry + aggregator.
# ---------------------------------------------------------------------------

def test_registry_and_aggregator_cover_single_param():
    assert [(k, p) for k, p, _ in P4_PLANK_DIMS] == [
        ("pipeline_plank_500m", "P4-006"),
    ]
    full = pois(mkplan())
    assert score_p4_plank(TALLINN, full) == {"pipeline_plank_500m": 65}
    far = pois(mkplan(lon=24.7746, plan_id="FAR"))
    assert score_p4_plank(TALLINN, far) == {"pipeline_plank_500m": 90}
    assert score_p4_plank(None, None) == {"pipeline_plank_500m": None}
    assert p4p.P4_PLANK_DIMS is P4_PLANK_DIMS
