"""Tests for scripts/build/batch_skis.py (issue #692).

Hermetic: no network anywhere (there is no machine feed — the
in-season status arrives as an operator-verified file read from the
human tallinn.ee page, never scraped). Pins the exact off-season
empty shape from the issue, the in-season fixture path, and the
honest --pull refusal.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_skis import build_table, main, parse_status  # noqa: E402

# Synthetic in-season example (NOT real coordinates — proves the
# seasonal mechanism only; real rows come from the operator-verified
# winter drop, see docs/p4_skis.md).
FIXTURE_STATUS = {
    "tracks": [
        {"track_id": "pirita-velodroom", "name": "Pirita Velodroomi ring",
         "lat": 59.4711, "lon": 24.8711, "groomed": True,
         "length_km": 3.8},
        {"track_id": "nomme-harku", "name": "Nõmme-Harku suusarada",
         "lat": 59.3899, "lon": 24.6511, "groomed": False,
         "length_km": 7.0},
    ]
}


def test_offseason_is_honestly_empty():
    from batch_skis import build_table
    assert build_table([]) == {"points": [], "season": "off",
                               "counts": {"total": 0}}


def test_inseason_fixture_builds_groomed_points():
    rows = parse_status(FIXTURE_STATUS)
    table = build_table(rows)
    assert table["season"] == "on"
    assert table["counts"]["total"] == 1  # only the groomed track plots
    pt = table["points"][0]
    assert pt["track_id"] == "pirita-velodroom"
    assert pt["lat"] == 59.4711


def test_ungroomed_and_coordless_rows_never_plot():
    rows = parse_status({"tracks": [
        {"track_id": "x", "name": "Hooldamata", "lat": 59.4,
         "lon": 24.7, "groomed": False},
        {"track_id": "y", "name": "Koordinaatideta", "groomed": True},
    ]})
    assert build_table(rows) == {"points": [], "season": "off",
                                 "counts": {"total": 0}}


def test_pull_refuses_without_machine_feed(tmp_path, capsys):
    rc = main(["--pull", "--cache-dir", str(tmp_path)])
    assert rc == 2
    assert "keeldun" in capsys.readouterr().err


def test_build_from_status_file(tmp_path, capsys):
    status = tmp_path / "status.json"
    status.write_text(json.dumps(FIXTURE_STATUS), encoding="utf-8")
    rc = main(["--build", "--cache-dir", str(tmp_path),
               "--status", str(status)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"total": 1, "season": "on"}


def test_build_without_status_is_honestly_empty(tmp_path, capsys):
    rc = main(["--build", "--cache-dir", str(tmp_path)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"total": 0, "season": "off"}


def test_build_out_writes_table_file(tmp_path, capsys):
    status = tmp_path / "status.json"
    status.write_text(json.dumps(FIXTURE_STATUS), encoding="utf-8")
    out_path = str(tmp_path / "table.json")
    rc = main(["--build", "--cache-dir", str(tmp_path),
               "--status", str(status), "--out", out_path])
    assert rc == 0
    table = json.loads((tmp_path / "table.json").read_text(encoding="utf-8"))
    assert table["season"] == "on"
    assert table["counts"] == {"total": 1}
    assert table["points"][0]["track_id"] == "pirita-velodroom"
    assert "built_at" in table
