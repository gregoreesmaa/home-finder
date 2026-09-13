"""P4 TPR dims (issues #250 + #334): hermetic tests.

No network: the TPR bulk endpoint does not exist (2026-09-13 dated
negative, see dims_p4_tpr docstring), so every test runs on fixture
row-dicts and hand-built POIs. The polite fetcher is covered via a
stubbed urlopen (cache-hit performs no request; no-endpoint and
transport-error paths return None and cache nothing); scorers are
proven network-free by running them with urlopen stubbed to raise.
"""

import json
import urllib.request

import dims_p4_tpr as p4t
import pytest
from dims_p4_tpr import (
    CACHE_FILENAME,
    PIPELINE_STAGE,
    P4_TPR_DIMS,
    TPR_BULK_URL,
    TPR_TTL_S,
    TPR_UA,
    areas_to_pois,
    dim_pipeline_500m,
    dim_tpr_permit_existence,
    dim_tpr_permit_glut,
    fetch_tpr_snapshot,
    parse_tpr_snapshot,
    plans_to_pois,
    score_p4_tpr,
    snapshot_to_pois,
)

# Tallinn centre: hand-built POIs sit ~57 m east unless stated
# (0.001 deg lon ~= 57 m at 59.44 N).
TALLINN = (59.4372, 24.7536)


def mkplan(lat=59.4372, lon=24.7546, stage="menetluses", plan_id="DP-1",
           permits=None, units=None):
    return {"plan_id": plan_id, "stage": stage, "lat": lat, "lon": lon,
            "impl_permits": permits, "impl_units": units}


def mkarea(lat=59.4372, lon=24.7546, code="KESK", pipe=None, done=None):
    return {"area_code": code, "lat": lat, "lon": lon,
            "pipeline_units": pipe, "completions_units": done}


def pois(plans=(), areas=()):
    return snapshot_to_pois({"plans": list(plans), "areas": list(areas)})


def plan_pois(*plans):
    return pois(plans=plans)


def area_pois(*areas):
    return pois(areas=areas)


ALL_FNS = [dim_pipeline_500m, dim_tpr_permit_existence, dim_tpr_permit_glut]


def raise_urlopen(*a, **k):
    raise AssertionError("network touched in hermetic test")


# ---------------------------------------------------------------------------
# Contract: no open bulk endpoint (dated negative is a code path).
# ---------------------------------------------------------------------------

def test_no_bulk_endpoint_yet():
    assert TPR_BULK_URL is None
    assert TPR_TTL_S == 7 * 24 * 3600  # weekly pull ticket
    assert "home-finder" in TPR_UA


# ---------------------------------------------------------------------------
# P4-006: pipeline bands.
# ---------------------------------------------------------------------------

def test_pipeline_zero_in_buffer_scores_clear_when_snapshot_has_plans():
    far = mkplan(lon=24.7746, plan_id="DP-FAR")  # ~1.1 km east, in snapshot
    v, reason = dim_pipeline_500m(TALLINN, plan_pois(far))
    assert v == 90
    assert "hinnang" in reason and "0" in reason


def test_pipeline_bands_count_menetluses_only():
    near = dict(lon=24.7546)
    assert dim_pipeline_500m(
        TALLINN, plan_pois(mkplan(**near, plan_id="A")))[0] == 65
    assert dim_pipeline_500m(
        TALLINN, plan_pois(mkplan(**near, plan_id="A"),
                           mkplan(lat=59.4375, plan_id="B")))[0] == 40
    assert dim_pipeline_500m(
        TALLINN, plan_pois(mkplan(**near, plan_id="A"),
                           mkplan(lat=59.4375, plan_id="B"),
                           mkplan(lat=59.4369, plan_id="C"),
                           mkplan(lat=59.4370, plan_id="D")))[0] == 20


def test_pipeline_ignores_other_stages_and_case_folds():
    ps = plan_pois(mkplan(plan_id="K", stage="kehtestatud"),
                   mkplan(lat=59.4375, plan_id="I", stage="algatatud"),
                   mkplan(lat=59.4369, plan_id="L",
                          stage="kehtetuks tunnistatud"),
                   mkplan(lat=59.4370, plan_id="FAR2", stage="menetluses",
                          lon=24.7746))
    v, reason = dim_pipeline_500m(TALLINN, ps)
    assert v == 90  # in-flight labels are NOT counted (conservative)
    assert "hinnang" in reason
    v2, _ = dim_pipeline_500m(
        TALLINN, plan_pois(mkplan(plan_id="M", stage="Menetluses")))
    assert v2 == 65


def test_pipeline_beyond_500m_does_not_count():
    ps = plan_pois(mkplan(plan_id="OUT", lon=24.7646),  # ~566 m east
                   mkplan(plan_id="FAR", lon=24.7746))
    v, _ = dim_pipeline_500m(TALLINN, ps)
    assert v == 90


def test_pipeline_null_without_snapshot():
    for origin, p in [(None, plan_pois(mkplan())), (TALLINN, None),
                      (None, None)]:
        v, reason = dim_pipeline_500m(origin, p)
        assert v is None
        assert "EI OLE" in reason
    v, reason = dim_pipeline_500m(TALLINN, [])
    assert v is None and "EI OLE" in reason
    v, reason = dim_pipeline_500m(TALLINN, area_pois(mkarea()))
    assert v is None and "EI OLE" in reason  # areas table is not plans


# ---------------------------------------------------------------------------
# P4-005: TPR elluviimine leg, presence-only (75 | None).
# ---------------------------------------------------------------------------

def test_permit_kehtestatud_with_permits_scores_capped():
    ps = plan_pois(mkplan(stage="kehtestatud", permits=3, plan_id="KEH-7"))
    v, reason = dim_tpr_permit_existence(TALLINN, ps)
    assert v == 75
    assert "hinnang" in reason and "EHR-ristkontroll" in reason


def test_permit_missing_link_is_unknown_not_zero():
    # menetluses plan WITH permits: wrong stage for elluviimine evidence
    v, r = dim_tpr_permit_existence(
        TALLINN, plan_pois(mkplan(permits=5, plan_id="MEN")))
    assert v is None and "EI OLE" in r
    # kehtestatud but no permit records
    v, r = dim_tpr_permit_existence(
        TALLINN, plan_pois(mkplan(stage="kehtestatud", plan_id="KEH-0")))
    assert v is None and "EI OLE" in r
    # kehtestatud + permits but beyond the 150 m parcel window
    v, r = dim_tpr_permit_existence(
        TALLINN, plan_pois(mkplan(stage="kehtestatud", permits=2,
                                  lon=24.7586, plan_id="KEH-FAR")))
    assert v is None and "EI OLE" in r
    # no snapshot at all
    v, r = dim_tpr_permit_existence(TALLINN, None)
    assert v is None and "EI OLE" in r
    v, r = dim_tpr_permit_existence(None, plan_pois(mkplan()))
    assert v is None and "EI OLE" in r


# ---------------------------------------------------------------------------
# P4-050: glut ratio, pipeline-only fallback, 0/0 gap.
# ---------------------------------------------------------------------------

def test_glut_ratio_bands():
    assert dim_tpr_permit_glut(
        TALLINN, area_pois(mkarea(pipe=40, done=100)))[0] == 80
    assert dim_tpr_permit_glut(
        TALLINN, area_pois(mkarea(pipe=90, done=100)))[0] == 60
    assert dim_tpr_permit_glut(
        TALLINN, area_pois(mkarea(pipe=150, done=100)))[0] == 40
    assert dim_tpr_permit_glut(
        TALLINN, area_pois(mkarea(pipe=300, done=100)))[0] == 20
    v, reason = dim_tpr_permit_glut(
        TALLINN, area_pois(mkarea(pipe=150, done=100, code="LAS")))
    assert "hinnang" in reason and "LAS" in reason and "1.5" in reason


def test_glut_pipeline_without_completions_is_pure_pipeline():
    v, reason = dim_tpr_permit_glut(
        TALLINN, area_pois(mkarea(pipe=60, done=0)))
    assert v == 20
    assert "hinnang" in reason


def test_glut_zero_zero_is_gap_not_balance():
    v, reason = dim_tpr_permit_glut(
        TALLINN, area_pois(mkarea(pipe=0, done=0)))
    assert v is None and "EI OLE" in reason


def test_glut_pipeline_only_fallback_flagged():
    v, reason = dim_tpr_permit_glut(
        TALLINN, area_pois(mkarea(pipe=120)))
    assert v == 45
    assert "ainult torustik" in reason and "hinnang" in reason
    v, _ = dim_tpr_permit_glut(TALLINN, area_pois(mkarea(pipe=0)))
    assert v == 85  # measured zero pipeline scores, low-glut signal


def test_glut_null_without_area_row():
    v, r = dim_tpr_permit_glut(TALLINN, None)
    assert v is None and "EI OLE" in r
    v, r = dim_tpr_permit_glut(None, area_pois(mkarea(pipe=1, done=1)))
    assert v is None and "EI OLE" in r
    v, r = dim_tpr_permit_glut(TALLINN, plan_pois(mkplan()))
    assert v is None and "EI OLE" in r  # plans table is not areas
    v, r = dim_tpr_permit_glut(
        TALLINN, area_pois(mkarea(pipe=None, done=None)))
    assert v is None and "EI OLE" in r
    v, r = dim_tpr_permit_glut(
        TALLINN, area_pois(mkarea(lat=59.45, lon=24.80, pipe=5, done=5)))
    assert v is None and "EI OLE" in r  # outside the 1 km window


# ---------------------------------------------------------------------------
# Honesty markers across all three dims.
# ---------------------------------------------------------------------------

def test_scored_reasons_say_hinnang_with_components():
    v, r = dim_pipeline_500m(TALLINN, plan_pois(mkplan(plan_id="DP-9")))
    assert v == 65 and "hinnang" in r and "DP-9" in r
    v, r = dim_tpr_permit_existence(
        TALLINN, plan_pois(mkplan(stage="kehtestatud", permits=2,
                                  plan_id="KEH-2")))
    assert v == 75 and "hinnang" in r
    v, r = dim_tpr_permit_glut(
        TALLINN, area_pois(mkarea(pipe=10, done=100)))
    assert v == 80 and "hinnang" in r


def test_null_reasons_carry_ei_ole_and_no_fake_precision():
    cases = [(dim_pipeline_500m, (TALLINN, None)),
             (dim_tpr_permit_existence, (TALLINN, [])),
             (dim_tpr_permit_glut, (TALLINN, []))]
    for fn, args in cases:
        _, reason = fn(*args)
        assert "EI OLE" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason, \
            fn.__name__


def test_scorers_never_touch_network(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", raise_urlopen)
    full = pois(plans=[mkplan(stage="kehtestatud", permits=4)],
                areas=[mkarea(pipe=10, done=50)])
    for fn in ALL_FNS:
        fn(TALLINN, full)
        fn(TALLINN, [])
        fn(None, None)


# ---------------------------------------------------------------------------
# Offline readers: malformed rows skipped, missing file is None.
# ---------------------------------------------------------------------------

FIXTURE = {
    "plans": [
        {"plan_id": "DP-1", "stage": "menetluses",
         "lat": 59.4372, "lon": 24.7546,
         "impl_permits": 0, "impl_units": 120},
        {"plan_id": "BAD", "stage": "menetluses"},  # no coords: skipped
        {"plan_id": "BOOL", "stage": "kehtestatud",
         "lat": True, "lon": 24.7546, "impl_permits": 2},  # skipped
        {"plan_id": "NEG", "stage": "kehtestatud",
         "lat": 59.4372, "lon": 24.7546, "impl_permits": -1},  # None count
    ],
    "areas": [
        {"area_code": "KESK", "lat": 59.4372, "lon": 24.7546,
         "pipeline_units": 150, "completions_units": 100},
        {"area_code": "NOLATLON", "pipeline_units": 5},  # skipped
    ],
}


def test_readers_skip_malformed_never_fake():
    ps = snapshot_to_pois(FIXTURE)
    plans = [p for p in ps if p["kind"] == "plan_p4"]
    areas = [p for p in ps if p["kind"] == "tpr_area_p4"]
    assert {p["plan_id"] for p in plans} == {"DP-1", "NEG"}
    neg = next(p for p in plans if p["plan_id"] == "NEG")
    assert neg["impl_permits"] is None  # negative sanitised to unknown
    assert neg["stage"] == "kehtestatud"
    assert [a["area_code"] for a in areas] == ["KESK"]
    assert snapshot_to_pois(None) == []
    assert snapshot_to_pois({"plans": "nope", "areas": None}) == []


def test_fixture_end_to_end_shapes():
    ps = snapshot_to_pois(FIXTURE)
    assert dim_pipeline_500m(TALLINN, ps)[0] == 65  # DP-1 menetluses
    assert dim_tpr_permit_existence(TALLINN, ps)[
        0] is None  # no kehtestatud+permits link
    assert dim_tpr_permit_glut(TALLINN, ps)[0] == 40  # 150/100 = 1.5


def test_parse_snapshot_roundtrip_and_missing(tmp_path):
    fp = tmp_path / "snap.json"
    fp.write_text(json.dumps(FIXTURE), encoding="utf-8")
    snap = parse_tpr_snapshot(str(fp))
    assert snap is not None and len(snap["plans"]) == 4
    assert parse_tpr_snapshot(str(tmp_path / "absent.json")) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert parse_tpr_snapshot(str(bad)) is None
    lst = tmp_path / "list.json"
    lst.write_text("[1,2]", encoding="utf-8")
    assert parse_tpr_snapshot(str(lst)) is None


# ---------------------------------------------------------------------------
# Polite fetcher: cache hit = no request; no endpoint = no request.
# ---------------------------------------------------------------------------

def test_fetch_cache_hit_performs_no_request(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", raise_urlopen)
    dest = tmp_path / CACHE_FILENAME
    dest.write_text("{}", encoding="utf-8")
    assert fetch_tpr_snapshot(str(tmp_path)) == str(dest)


def test_fetch_without_endpoint_performs_no_request(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", raise_urlopen)
    assert fetch_tpr_snapshot(str(tmp_path), bulk_url=None) is None
    assert not (tmp_path / CACHE_FILENAME).exists()  # errors cache nothing


def test_fetch_transport_error_caches_nothing(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise OSError("network down")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    url = "https://example.invalid/tpr.json"
    assert fetch_tpr_snapshot(str(tmp_path), bulk_url=url) is None
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
    assert fetch_tpr_snapshot(
        str(tmp_path), bulk_url="https://example.invalid/x") is None
    assert not (tmp_path / CACHE_FILENAME).exists()


def test_fetch_stores_json_snapshot(tmp_path, monkeypatch):
    body = json.dumps({"plans": [], "areas": []}).encode()

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
    got = fetch_tpr_snapshot(str(tmp_path),
                             bulk_url="https://example.invalid/tpr.json")
    assert got == str(tmp_path / CACHE_FILENAME)
    assert parse_tpr_snapshot(got) == {"plans": [], "areas": []}


# ---------------------------------------------------------------------------
# Registry + aggregator.
# ---------------------------------------------------------------------------

def test_registry_and_aggregator_cover_all_three():
    assert [(k, p) for k, p, _ in P4_TPR_DIMS] == [
        ("pipeline_500m", "P4-006"),
        ("permit_existence_tpr", "P4-005"),
        ("permit_glut_tpr", "P4-050"),
    ]
    assert len({fn for _, _, fn in P4_TPR_DIMS}) == 3
    full = pois(plans=[mkplan(stage="kehtestatud", permits=4)],
                areas=[mkarea(pipe=10, done=50)])
    out = score_p4_tpr(TALLINN, full)
    assert out == {"pipeline_500m": 90, "permit_existence_tpr": 75,
                   "permit_glut_tpr": 80}
    assert score_p4_tpr(None, None) == {"pipeline_500m": None,
                                        "permit_existence_tpr": None,
                                        "permit_glut_tpr": None}
    assert p4t.P4_TPR_DIMS is P4_TPR_DIMS
    assert PIPELINE_STAGE == "menetluses"
