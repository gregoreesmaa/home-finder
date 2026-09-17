"""Hermetic tests for scripts/build/batch_delay_sampler.py (issue #629).

No network, no snapshot files: pulls run against stubbed urlopen,
builds run on synthetic timestamped gps.txt snapshots. The live feed
layout (lon-first, 10 fields, no speeds) is pinned in
test_dims_p4_typical_delay.py against the real 2026-09-17 snapshot.
"""

import io
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


def _shape_vintage(snap):
    """Tiny GTFS vintage (all 5 validation tables + 2 shapes)."""
    import csv
    import zipfile

    def _write(zf, name, fieldnames, rows):
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
        zf.writestr(name, buf.getvalue())

    dest = os.path.join(snap, "tiny.zip")
    with zipfile.ZipFile(dest, "w") as zf:
        for name, fields in (
                ("calendar.txt", ["service_id", "monday"]),
                ("stop_times.txt", ["trip_id", "stop_id"]),
                ("stops.txt", ["stop_id", "stop_lat", "stop_lon"]),
                ("routes.txt", ["route_id", "route_short_name",
                                "route_long_name"]),
                ("trips.txt", ["trip_id", "route_id", "shape_id",
                               "trip_headsign"]),
                ("shapes.txt", ["shape_id", "shape_pt_lon",
                                "shape_pt_lat", "shape_pt_sequence"])):
            rows = []
            if name == "routes.txt":
                rows = [{"route_id": "r5", "route_short_name": "5",
                         "route_long_name": "Männiku-Viru"}]
            elif name == "stops.txt":
                # two far-off stops: joined (None) but never counted
                rows = [{"stop_id": "a", "stop_lat": "59.700",
                         "stop_lon": "25.500"},
                        {"stop_id": "b", "stop_lat": "59.701",
                         "stop_lon": "25.501"}]
            elif name == "trips.txt":
                rows = [{"trip_id": "t1", "route_id": "r5",
                         "shape_id": "s1", "trip_headsign": "Männiku"},
                        {"trip_id": "t2", "route_id": "r5",
                         "shape_id": "s2", "trip_headsign": "Viru"}]
            elif name == "shapes.txt":
                rows = [{"shape_id": "s1", "shape_pt_lon": "24.795",
                         "shape_pt_lat": "59.423", "shape_pt_sequence": "1"},
                        {"shape_id": "s1", "shape_pt_lon": "24.830",
                         "shape_pt_lat": "59.435", "shape_pt_sequence": "2"},
                        {"shape_id": "s1", "shape_pt_lon": "24.865",
                         "shape_pt_lat": "59.448", "shape_pt_sequence": "3"},
                        {"shape_id": "s2", "shape_pt_lon": "24.900",
                         "shape_pt_lat": "59.500", "shape_pt_sequence": "1"},
                        {"shape_id": "s2", "shape_pt_lon": "24.950",
                         "shape_pt_lat": "59.520", "shape_pt_sequence": "2"}]
            _write(zf, name, fields, rows)
    return "tiny.zip"


def test_validation_joins_once_per_stop(tmp_path, monkeypatch):
    """Validation cost is O(stops), never O(corridors x stops) (#667:
    the naive nesting stalled the 196-shape build at ~1 s/stop)."""
    import batch_delay_sampler as bds

    calls = []

    real = bds.corridor_of

    def _counting(lat, lon, corridors=None):
        calls.append(1)
        return real(lat, lon, corridors)

    monkeypatch.setattr(bds, "corridor_of", _counting)
    cache = str(tmp_path / "cache")
    snap = str(tmp_path / "snap")
    os.makedirs(cache)
    os.makedirs(snap)
    doc = bds.build(cache, snap, vintage=_shape_vintage(snap))
    assert doc["stats"]["corridors"] == 2
    # two stops joined exactly once each; both off-web, counts stay 0
    assert len(calls) == 2
    assert all(a["gtfs"]["weekday_stops_nearby"] == 0
               for a in doc["areas"])


def test_build_shape_web_ribbons(tmp_path):
    """Shape corridors render road-following bands (#667)."""
    cache = str(tmp_path / "cache")
    snap = str(tmp_path / "snap")
    os.makedirs(cache)
    os.makedirs(snap)
    midnight = time.mktime(time.strptime("2026-09-17", "%Y-%m-%d"))
    _run(cache, midnight + 8 * 3600)
    _run(cache, midnight + 23 * 3600)
    doc = build(cache, snap, vintage=_shape_vintage(snap))
    assert doc["stats"]["corridors"] == 2
    assert len(doc["areas"]) == 2  # every shape renders a band
    names = sorted(a["corridor"] for a in doc["areas"])
    assert names == ["5 · Männiku", "5 · Viru"]
    s1 = [a for a in doc["areas"]
          if a["corridor"] == "5 · Männiku"][0]
    assert s1["factors"]["hommikune tipp"] == pytest.approx(1.0)
    assert s1["factors"]["muu"] == pytest.approx(1.0)
    assert s1["gtfs"]["weekday_stops_nearby"] == 0  # no stops in fixture
    ring = s1["r"][0]
    assert len(ring) > 4 and ring[0] == ring[-1]  # ribbon, not a quad
    lons = [p[0] for p in ring]
    assert min(lons) < 24.795 and max(lons) > 24.865  # follows the road
    s2 = [a for a in doc["areas"] if a["corridor"] == "5 · Viru"][0]
    assert s2["factors"]["worst"] is None  # unmeasured stays NULL


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
