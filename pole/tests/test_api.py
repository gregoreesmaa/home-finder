"""Hermetic tests for the harvest-pole read API (issue #676).

The API reads built/*.json from its own directory; tests point BUILT_DIR at
a tmp dir with fixtures, so no network and no Pi are involved.
"""

import contextlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".."))

import api  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

FIXTURE = {"vintage": "2026-09-18", "counts": {"total": 2}, "points": []}

MEDRE_EMPTY = {"vintage": "2026-09-16", "linkage_rate": 0, "points": []}
MEDRE_FULL = {"vintage": "2026-09-16", "linkage_rate": 0.9847,
              "points": [{"lat": 59.43, "lon": 24.75, "slice": "gp"}]}


def _client(tmp_path, missing=(), medre=None):
    built = tmp_path / "built"
    (built / "fixit").mkdir(parents=True, exist_ok=True)
    if "fixit" not in missing:
        (built / "fixit" / "fixit-points.json").write_text(
            json.dumps(FIXTURE), encoding="utf-8")
    if medre is not None:
        (built / "medre").mkdir(parents=True, exist_ok=True)
        (built / "medre" / "medre-points.json").write_text(
            json.dumps(medre), encoding="utf-8")
    api.BUILT_DIR = str(built)
    return TestClient(api.app)


def test_health_reports_readiness(tmp_path):
    c = _client(tmp_path)
    body = c.get("/health").json()
    assert body["ok"] is True
    assert body["datasets"]["fixit"] is True
    assert body["datasets"]["delay"] is False  # no fixture written


def test_datasets_lists_five(tmp_path):
    c = _client(tmp_path)
    names = sorted(d["name"] for d in c.get("/v1/datasets").json()["datasets"])
    assert names == ["datex-cameras", "datex-counters", "datex-restrictions",
                     "datex-srti", "datex-truckpark", "datex-weather",
                     "delay", "fixit", "incidents", "medre", "mobile",
                     # OUTAGE-HOOK (#729): live-outage sidecar joins the pole.
                     "outage",
                     # OUTAGE-RELIABILITY-HOOK (#780): observed-reliability
                     # table joins the pole (honest 503 until first build).
                     "outage-reliability", "poi",
                     # TOMTOM-HOOK (#782): sheds + incidents join the pole
                     # (honest 503s until the first keyed builds).
                     "sheds",
                     # SKIS-HOOK (#692): seasonal ski tracks join the pole.
                     "skis",
                     # VIIRS-HOOK (#719): brightness-proxy grid joins the pole.
                     "viirs"]


def test_dataset_serves_bytes_and_freshness(tmp_path):
    c = _client(tmp_path)
    r = c.get("/v1/fixit")
    assert r.status_code == 200
    assert r.json() == FIXTURE
    assert "X-Pole-Built-At" in r.headers


def test_missing_build_is_honest_503(tmp_path):
    c = _client(tmp_path, missing=("fixit",))
    assert c.get("/v1/fixit").status_code == 503


def test_outage_reliability_missing_build_is_honest_503(tmp_path):
    # Issue #780: no reliability table until the first pole build.
    c = _client(tmp_path)
    assert c.get("/health").json()["datasets"]["outage-reliability"] is False
    assert c.get("/v1/outage-reliability").status_code == 503


def test_outage_reliability_serves_table(tmp_path):
    # Issue #780: the built reliability table serves with freshness.
    table = {"built_at": "2026-09-20T12:00:00+00:00", "window_days": 28,
             "metric": "vaadeldud töökindlus", "n_obs_total": 3,
             "areas": {"Tallinn": {"n_obs": 3, "fault_obs": 1}}}
    rel_dir = tmp_path / "built" / "outage"
    rel_dir.mkdir(parents=True)
    (rel_dir / "reliability.json").write_text(
        json.dumps(table), encoding="utf-8")
    c = _client(tmp_path)
    assert c.get("/health").json()["datasets"]["outage-reliability"] is True
    r = c.get("/v1/outage-reliability")
    assert r.status_code == 200
    assert r.json()["window_days"] == 28
    assert "X-Pole-Built-At" in r.headers


def test_unknown_dataset_is_404(tmp_path):
    c = _client(tmp_path)
    assert c.get("/v1/nope").status_code == 404


def test_medre_empty_points_is_honest_503(tmp_path):
    # Issue #765: Step-1 linkage report (points []) must not serve.
    c = _client(tmp_path, medre=MEDRE_EMPTY)
    assert c.get("/health").json()["datasets"]["medre"] is False
    assert c.get("/v1/medre").status_code == 503


def test_medre_joined_points_serve(tmp_path):
    c = _client(tmp_path, medre=MEDRE_FULL)
    assert c.get("/health").json()["datasets"]["medre"] is True
    r = c.get("/v1/medre")
    assert r.status_code == 200
    assert len(r.json()["points"]) == 1


def test_unlisted_empty_points_still_serve(tmp_path):
    # Honest-empty scope guard: fixit points [] keeps serving 200.
    c = _client(tmp_path)
    assert c.get("/v1/fixit").status_code == 200


def _write_built(tmp_path, rel, body):
    target = tmp_path / "built" / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(body), encoding="utf-8")


@contextlib.contextmanager
def _client_with_state(tmp_path, state_files=(), wrapper_files=(),
                       guard_lines=(), sync_body=None, mtimes=None):
    # Issue #806: point both BUILT_DIR and STATE_DIR at tmp fixtures.
    import time
    _client(tmp_path)  # fixit fixture dirs under tmp built/
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    for name, text in state_files:
        (state / name).write_text(text, encoding="utf-8")
    wdir = state / "wrapper-status"
    wdir.mkdir(exist_ok=True)
    for name, body in wrapper_files:
        (wdir / (name + ".json")).write_text(
            json.dumps(body), encoding="utf-8")
    if guard_lines:
        (state / "guard-restarts.jsonl").write_text(
            "\n".join(guard_lines) + "\n", encoding="utf-8")
    if sync_body is not None:
        (state / "sync-status.json").write_text(
            json.dumps(sync_body), encoding="utf-8")
    for rel, age_s in (mtimes or {}).items():
        old = time.time() - age_s
        os.utime(str(tmp_path / "built" / rel), (old, old))
    old_built, old_state = api.BUILT_DIR, api.STATE_DIR
    api.BUILT_DIR = str(tmp_path / "built")
    api.STATE_DIR = str(state)
    try:
        yield TestClient(api.app)
    finally:
        api.BUILT_DIR, api.STATE_DIR = old_built, old_state


def test_health_exposes_deployed_sha(tmp_path):
    # Issue #806: /health carries the pole-sync deployment identity.
    with _client_with_state(
            tmp_path,
            state_files=[("deployed-sha.txt", "abc123\n"),
                         ("deployed-at.txt",
                          "2026-09-20T12:00:00+00:00\n")]) as c:
        body = c.get("/health").json()
        assert body["deployed_sha"] == "abc123"
        assert body["deployed_at"] == "2026-09-20T12:00:00+00:00"


def test_health_deployed_unknown_without_state(tmp_path):
    # Repo checkout / fresh pole: nulls, never faked data.
    with _client_with_state(tmp_path) as c:
        body = c.get("/health").json()
        assert body["deployed_sha"] is None
        assert body["deployed_at"] is None


def test_errors_empty_without_state(tmp_path):
    with _client_with_state(tmp_path) as c:
        body = c.get("/v1/errors").json()
        assert body["guard_restarts"] == []
        assert body["wrappers"] == {}
        assert body["sync"] is None
        assert body["deployed_sha"] is None


def test_errors_reports_wrappers_guard_sync(tmp_path):
    with _client_with_state(
            tmp_path,
            wrapper_files=[("outage", {"job": "outage", "rc": 1,
                                       "at": "2026-09-20T12:00:00+00:00"}),
                           ("poi", {"job": "poi", "rc": 0,
                                    "at": "2026-09-20T12:05:00+00:00"})],
            guard_lines=['{"at": "2026-09-20T11:00:00+00:00", '
                         '"event": "guard-restart"}',
                         "not-json, skipped"],
            sync_body={"rc": 0, "at": "2026-09-20T10:00:00+00:00",
                       "sha": "abc123", "ref": "refs/heads/main"}) as c:
        body = c.get("/v1/errors").json()
        assert body["wrappers"]["outage"]["rc"] == 1
        assert body["wrappers"]["poi"]["rc"] == 0
        assert body["guard_restarts"] == [
            {"at": "2026-09-20T11:00:00+00:00", "event": "guard-restart"}]
        assert body["sync"]["rc"] == 0


def test_errors_staleness_math(tmp_path):
    # Issue #806: stale = ready + older than serve-parity TTL.
    outage = {"pulled_at": "x", "areas": {}}
    (tmp_path / "built" / "outage").mkdir(parents=True, exist_ok=True)
    (tmp_path / "built" / "outage" / "table.json").write_text(
        json.dumps(outage), encoding="utf-8")
    with _client_with_state(tmp_path,
                            mtimes={"outage/table.json": 9999}) as c:
        rows = {d["name"]: d for d in c.get("/v1/errors").json()["datasets"]}
        assert rows["outage"]["stale"] is True  # 9999 s > 300 s TTL
        assert rows["outage"]["ttl_s"] == 300
        assert rows["delay"]["stale"] is False  # not built: stale-never
        assert rows["delay"]["ttl_s"] == 7200
    with _client_with_state(tmp_path,
                            mtimes={"outage/table.json": 60}) as c:
        rows = {d["name"]: d for d in c.get("/v1/errors").json()["datasets"]}
        assert rows["outage"]["stale"] is False


def test_errors_ttl_parity_with_web_constants():
    # Pinned mirrors the watcher trusts: datex == DATEX_TTL_S,
    # outage pair == web OUTAGE_*_TTL_S, sheds/incidents == web TTLs.
    assert api.DATASET_TTL_S["datex-restrictions"] == 24 * 3600
    assert api.DATASET_TTL_S["datex-srti"] == 6 * 3600
    for name in ("datex-weather", "datex-counters", "datex-cameras"):
        assert api.DATASET_TTL_S[name] == 3600
    assert api.DATASET_TTL_S["datex-truckpark"] == 30 * 86400
    assert api.DATASET_TTL_S["outage"] == 300
    assert api.DATASET_TTL_S["outage-reliability"] == 86400
    assert api.DATASET_TTL_S["sheds"] == 7 * 86400
    assert api.DATASET_TTL_S["incidents"] == 6 * 3600
    assert api.DATASET_TTL_S["skis"] is None  # seasonal: never stale
    assert set(api.DATASET_TTL_S) == set(api.DATASETS)


def test_tomtom_tables_missing_builds_are_honest_503(tmp_path):
    # Issue #782: no sheds/incidents tables until the first keyed
    # pole builds (key from pole state/, operator-verified).
    c = _client(tmp_path)
    health = c.get("/health").json()["datasets"]
    assert health["sheds"] is False
    assert health["incidents"] is False
    assert c.get("/v1/sheds").status_code == 503
    assert c.get("/v1/incidents").status_code == 503


def test_tomtom_tables_serve_with_freshness(tmp_path):
    # Issue #782: built tables serve with the X-Pole-Built-At
    # freshness header the map routes enforce TTLs against.
    sheds = {"polygons": [{"hub": "city-center", "budget_s": 900,
                           "band": "rush", "n_points": 3,
                           "ring": [[59.44, 24.75], [59.45, 24.76],
                                    [59.46, 24.75]]}],
             "counts": {"total": 1, "measured": 1, "unmeasured": 0}}
    incidents = {"incidents": [{"incident_id": "i1", "category": 8,
                                "magnitude": 3, "description": "Ummik",
                                "points": [[59.428, 24.78]]}],
                 "fetched_at": 1758326400.0,
                 "counts": {"total": 1, "by_magnitude": {"3": 1}}}
    _write_built(tmp_path, "tomtom-sheds/table.json", sheds)
    _write_built(tmp_path, "tomtom-incidents/table.json", incidents)
    c = _client(tmp_path)
    health = c.get("/health").json()["datasets"]
    assert health["sheds"] is True
    assert health["incidents"] is True
    r = c.get("/v1/sheds")
    assert r.status_code == 200
    assert r.json()["counts"]["measured"] == 1
    assert "X-Pole-Built-At" in r.headers
    r = c.get("/v1/incidents")
    assert r.status_code == 200
    assert r.json()["counts"]["total"] == 1
    assert "X-Pole-Built-At" in r.headers
