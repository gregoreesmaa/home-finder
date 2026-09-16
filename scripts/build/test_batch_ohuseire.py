"""Fixture tests for scripts/build/batch_ohuseire.py (issue #610).

Hermetic: synthetic PostgREST seirejaamad rows only, never network.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from batch_ohuseire import build_sidecar

FIX_ROWS = json.dumps([
    {"nimi": "Tallinn Rahu", "kesk_x": 540568, "kesk_y": 6590159,
     "seisund": "Kasutusel",
     "sr_programm_nimi": "Välisõhu kvaliteedi seire",
     "ehak_tekst": "Harju maakond, Tallinn, Põhja-Tallinna linnaosa",
     "kkr_kood": "SJA9166000"},
    {"nimi": "Tallinn Õismäe", "kesk_x": 533000, "kesk_y": 6592000,
     "seisund": "Kasutusel",
     "sr_programm_nimi": "Välisõhu kvaliteedi seire linnades",
     "ehak_tekst": "Harju maakond, Tallinn, Haabersti linnaosa",
     "kkr_kood": "SJA9166001"},
    {"nimi": "Vana peatatud", "kesk_x": 540568, "kesk_y": 6590159,
     "seisund": "Peatatud",
     "sr_programm_nimi": "Välisõhu kvaliteedi seire",
     "ehak_tekst": "Harju maakond, Tallinn, Kesklinna linnaosa",
     "kkr_kood": "SJA0000001"},
    {"nimi": "Tartu Raadi", "kesk_x": 660000, "kesk_y": 6475000,
     "seisund": "Kasutusel",
     "sr_programm_nimi": "Välisõhu kvaliteedi seire",
     "ehak_tekst": "Tartu maakond, Tartu linn",
     "kkr_kood": "SJA0000002"},
    {"nimi": "Koordinaadita", "kesk_x": None, "kesk_y": None,
     "seisund": "Kasutusel",
     "sr_programm_nimi": "Välisõhu kvaliteedi seire",
     "ehak_tekst": "Harju maakond, Tallinn, Lasnamäe linnaosa",
     "kkr_kood": "SJA0000003"},
    {"nimi": "Muu programm", "kesk_x": 540568, "kesk_y": 6590159,
     "seisund": "Kasutusel",
     "sr_programm_nimi": "Müra seire",
     "ehak_tekst": "Harju maakond, Tallinn, Kesklinna linnaosa",
     "kkr_kood": "SJA0000004"},
])


def test_build_sidecar_keeps_only_active_tallinn_air(tmp_path):
    out = build_sidecar(FIX_ROWS, str(tmp_path))
    assert out["counts"] == {"stations": 2, "total": 2}
    assert out["vintage"] == "2026-09-16"
    names = sorted(p["name"] for p in out["points"])
    assert names == ["Tallinn Rahu", "Tallinn Õismäe"]
    assert all(set(p) == {"lat", "lon", "name"} for p in out["points"])
    # Rahu projects to Pelgulinn (~1 m honesty, docs/p4_ohuseire.md).
    rahu = next(p for p in out["points"] if p["name"] == "Tallinn Rahu")
    assert abs(rahu["lat"] - 59.44729) < 0.002
    assert abs(rahu["lon"] - 24.71513) < 0.002


def test_skipped_rows_counted_never_silent(tmp_path):
    out = build_sidecar(FIX_ROWS, str(tmp_path))
    assert out["dropped"]["fetched_rows"] == 6
    assert out["dropped"]["parsed_rows"] == 5
    assert out["dropped"]["skipped"] == 3
