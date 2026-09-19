"""Tests for scripts/build/batch_harno.py (issue #687).

Hermetic: no network anywhere (static annual snapshot — the yearly
per-school table arrives as an operator-verified file, never
scraped, never polled). Pins snapshot validation, the quality-band
build, and the honest refusal without a snapshot.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_harno import (  # noqa: E402
    QUALITY_BANDS,
    build_table,
    main,
    quality_band,
    validate_snapshot,
)

# Synthetic annual example (NOT real scores — proves the shape only;
# real rows arrive with the operator-verified yearly drop, see
# docs/p4_harno.md).
FIXTURE_SNAPSHOT = {
    "vintage": "2025",
    "source": "sünteetiline näide (mitte päris hinded)",
    "schools": [
        {"ehis_id": "1234", "name": "Näidisgümnaasium",
         "lat": 59.4370, "lon": 24.7450,
         "avg_estonian": 82.5, "avg_math": 78.0, "avg_foreign": 88.0,
         "n_graduates": 60},
        {"ehis_id": "5678", "name": "Teine kool",
         "lat": 58.3806, "lon": 26.7225,
         "avg_estonian": 64.0, "avg_math": 58.5, "avg_foreign": 70.0,
         "n_graduates": 45},
    ],
}


def test_quality_bands():
    assert quality_band(85.0) == 80
    assert quality_band(75.0) == 70
    assert quality_band(65.0) == 60
    assert quality_band(55.0) == 45
    assert quality_band(40.0) == 30
    assert quality_band(None) is None


def test_builds_school_table_from_fixture():
    table = build_table(FIXTURE_SNAPSHOT["schools"], "2025")
    assert table["counts"]["total"] == 2
    assert table["vintage"] == "2025"
    pts = {p["ehis_id"]: p for p in table["points"]}
    assert pts["1234"]["q"] == 80  # mean(82.5, 78, 88) = 82.8
    assert pts["5678"]["q"] == 60  # mean(64, 58.5, 70) = 64.2


def test_thin_cohorts_and_coordless_never_plot():
    rows = [
        {"ehis_id": "a", "name": "Õhuke", "lat": 59.4, "lon": 24.7,
         "avg_estonian": 90.0, "avg_math": 90.0, "avg_foreign": 90.0,
         "n_graduates": 4},
        {"ehis_id": "b", "name": "Koordinaatideta",
         "avg_estonian": 90.0, "avg_math": 90.0, "avg_foreign": 90.0,
         "n_graduates": 60},
    ]
    assert build_table(rows, "2025") == {"points": [], "vintage": "2025",
                                         "counts": {"total": 0}}


def test_validate_accepts_good_snapshot():
    ok, errs = validate_snapshot(FIXTURE_SNAPSHOT)
    assert ok and errs == []


def test_validate_rejects_bad_snapshot():
    ok, errs = validate_snapshot({"schools": [{"name": "Poolik"}]})
    assert not ok and len(errs) >= 2


def test_build_refuses_without_snapshot(tmp_path, capsys):
    rc = main(["--build", "--cache-dir", str(tmp_path)])
    assert rc == 2
    assert "keeldun" in capsys.readouterr().err


def test_build_from_snapshot_file(tmp_path, capsys):
    snap = tmp_path / "snapshot.json"
    snap.write_text(json.dumps(FIXTURE_SNAPSHOT), encoding="utf-8")
    rc = main(["--build", "--cache-dir", str(tmp_path),
               "--snapshot", str(snap)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"total": 2, "vintage": "2025"}
