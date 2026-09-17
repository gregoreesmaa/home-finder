"""Hermetic tests for scripts/build/batch_delay_sampler.py (issue #629).

No network, no snapshot files: pulls run against stubbed urlopen,
builds run on synthetic timestamped gps.txt snapshots. The live feed
layout (lon-first, 10 fields, no speeds) is pinned in
test_dims_p4_typical_delay.py against the real 2026-09-17 snapshot.
"""

import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_delay_sampler import (  # noqa: E402
    build,
    main,
    pull,
)

GPS_ROW = "2,1,24841420,59519450,,240,1009,Z,33,Viimsi\n"


def _snap(cache, stamp, lon, lat):
    """One synthetic pull: one bus fix (live 10-field layout)."""
    p = os.path.join(cache, "gps-%d.txt" % stamp)
    with open(p, "w", encoding="utf-8") as f:
        f.write("2,1,%d,%d,,240,1009,Z,33,Siht\n" % (lon, lat))
    return p


def _run(cache, t0, n=25, step=120):
    """n pulls 120 s apart stepping ALONG Laagna tee (~170 m/step)."""
    lon, lat = 24800000, 59425000
    for k in range(n):
        _snap(cache, t0 + k * step, lon + k * 2600, lat + k * 870)


def test_pull_writes_timestamped_snapshot(tmp_path, monkeypatch):
    from dims_p4_typical_delay import GPS_SNAPSHOT_URL

    seen = {}

    class _Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"x" * 600

    def _fake(req, timeout=None):
        seen["url"] = req.full_url
        assert "home-finder" in req.headers.get("User-agent", "")
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", _fake)
    dest = pull(str(tmp_path))
    assert seen["url"] == GPS_SNAPSHOT_URL
    assert os.path.basename(dest).startswith("gps-")
    assert os.path.getsize(dest) == 600


def test_build_offline_table_and_sidecar(tmp_path):
    cache = str(tmp_path / "cache")
    snap = str(tmp_path / "snap")
    os.makedirs(cache)
    # Morning-peak + off-peak runs: peak cells join a free-flow median.
    # Local-midnight anchored: deterministic in ANY host TZ (the
    # sampler stamps Tallinn wall-clock hours).
    midnight = time.mktime(time.strptime("2026-09-17", "%Y-%m-%d"))
    _run(cache, midnight + 8 * 3600)
    _run(cache, midnight + 23 * 3600)
    doc = build(cache, snap, vintage=None)
    assert doc["stats"]["fixes"] == 50
    assert doc["stats"]["segments"] == 48
    assert doc["stats"]["cells"] >= 1
    assert len(doc["areas"]) == 8  # every corridor renders a band
    assert os.path.exists(os.path.join(snap, "delay",
                                       "delay-corridors.json"))
    # Per-band factors for the 5 map layers; muu anchors at 1.0.
    assert set(doc["areas"][0]["factors"]) == {
        "hommikune tipp", "keskpäev", "õhtune tipp", "muu", "worst"}
    laagna = [a for a in doc["areas"] if a["corridor"] == "Laagna tee"][0]
    assert laagna["factors"]["hommikune tipp"] == pytest.approx(1.0)
    assert laagna["factors"]["muu"] == pytest.approx(1.0)
    assert laagna["factors"]["worst"] == pytest.approx(1.0)
    for area in doc["areas"]:
        assert "r" in area and area["rep"] is not None
        assert area["b"][0] < area["b"][2]


def test_main_needs_snap_for_build(tmp_path):
    try:
        main(["--build", "--cache-dir", str(tmp_path)])
    except SystemExit as exc:
        assert exc.code != 0
    else:
        raise AssertionError("--build without --snap did not fail")


def test_main_pull_and_build_flags(tmp_path, monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("network used")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    rc = main(["--build", "--cache-dir", str(tmp_path / "c"),
               "--snap", str(tmp_path / "s")])
    assert rc == 0  # empty cache builds an empty (honest) table
    doc = json.loads(open(os.path.join(str(tmp_path / "s"), "delay",
                                       "delay-corridors.json")).read())
    assert doc["stats"]["cells"] == 0
    assert doc["pois"] == []
