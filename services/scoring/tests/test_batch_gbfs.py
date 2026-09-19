"""Tests for scripts/build/batch_gbfs.py (issue #688).

Hermetic: urlopen is stubbed, no network anywhere. Pins the GBFS
parse/join machinery on hand-written fixtures (two Tartu-style
stations), the honest refusal without a verified feed, and 429=stop.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_gbfs import (  # noqa: E402
    FEEDS,
    build_table,
    fetch_json,
    main,
    parse_discovery,
)

FIXTURE_INFO = {
    "data": {
        "stations": [
            {"station_id": "tartu-001", "name": "Raekoja plats",
             "lat": 58.3806, "lon": 26.7225, "capacity": 20},
            {"station_id": "tartu-002", "name": "Turuhoone",
             "lat": 58.3778, "lon": 26.7311, "capacity": 15},
        ]
    }
}

FIXTURE_STATUS = {
    "data": {
        "stations": [
            {"station_id": "tartu-001", "num_bikes_available": 7,
             "num_docks_available": 13, "is_renting": 1,
             "is_returning": 1},
            {"station_id": "tartu-002", "num_bikes_available": 0,
             "num_docks_available": 15, "is_renting": 1,
             "is_returning": 1},
        ]
    }
}

FIXTURE_DISCOVERY = {
    "data": {
        "feeds": [
            {"name": "station_information",
             "url": "https://example.invalid/station_information.json"},
            {"name": "station_status",
             "url": "https://example.invalid/station_status.json"},
        ]
    }
}


def fixture_gbfs():
    return FIXTURE_INFO, FIXTURE_STATUS


def test_builds_station_table_from_fixture():
    from batch_gbfs import build_table
    table = build_table(*fixture_gbfs())
    assert table["counts"]["total"] == 2


def test_status_join_and_counts():
    table = build_table(FIXTURE_INFO, FIXTURE_STATUS)
    pts = {p["station_id"]: p for p in table["points"]}
    assert pts["tartu-001"]["bikes"] == 7
    assert pts["tartu-001"]["docks"] == 13
    assert pts["tartu-002"]["bikes"] == 0
    assert table["counts"]["with_bikes"] == 1
    assert table["counts"]["total"] == 2


def test_status_without_info_is_dropped():
    table = build_table({"data": {"stations": []}}, FIXTURE_STATUS)
    assert table == {"points": [], "counts": {"total": 0, "with_bikes": 0}}


def test_no_verified_feeds_pinned():
    # 2026-09-19 probe verdict: no keyless GBFS for Tallinn or Tartu,
    # so the harvester ships with an empty feed table and refuses
    # --pull until an operator verifies a URL (never faked).
    assert FEEDS == {}


def test_pull_refuses_without_discovery(tmp_path, capsys):
    rc = main(["--pull", "--cache-dir", str(tmp_path)])
    assert rc == 2
    assert "keeldun" in capsys.readouterr().err


def test_build_from_fixture_files(tmp_path, capsys):
    info = tmp_path / "info.json"
    status = tmp_path / "status.json"
    info.write_text(json.dumps(FIXTURE_INFO), encoding="utf-8")
    status.write_text(json.dumps(FIXTURE_STATUS), encoding="utf-8")
    rc = main(["--build", "--cache-dir", str(tmp_path),
               "--info", str(info), "--status", str(status)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"total": 2, "with_bikes": 1}


def test_parse_discovery_finds_feeds():
    feeds = parse_discovery(FIXTURE_DISCOVERY)
    assert feeds["station_information"] == \
        "https://example.invalid/station_information.json"
    assert feeds["station_status"] == \
        "https://example.invalid/station_status.json"


class _Resp:
    status = 200

    def __init__(self, body: bytes, status: int = 200):
        self._body = body
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_429_is_stop_signal(monkeypatch, tmp_path):
    import urllib.request

    def _fake(req, timeout=30):
        return _Resp(b"{}", status=429)

    monkeypatch.setattr(urllib.request, "urlopen", _fake)
    assert fetch_json("https://example.invalid/gbfs.json",
                      str(tmp_path), "probe.json") is None
    assert list(tmp_path.iterdir()) == []
