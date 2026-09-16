"""Hermetic tests for scripts/build/batch_seveso.py (issue #613).

Covers ONLY the pure sidecar projection — the weekly CSV pull
(fetch_seveso_snapshot) is never called here (AGENTS.md section 7.6).
Scorer math (classify/project/contain) is pinned in
test_dims_p4_seveso.py (reused, never re-tested here).
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_seveso import (  # noqa: E402
    build_sidecar,
    classify_danger,
    parse_danger_csv,
    to_sidecar,
)

WKT_SQUARE = ("POLYGON ((600000 6590000, 600100 6590000, 600100 6590100, "
              "600000 6590100, 600000 6590000))")

DANGER_CSV = (
    '"WKT";"nimi";"kaitise_id";"aadress";"ohu_tuup"\n'
    '"%s";"Muuga terminal";"12.0";"Harju maakond, Muuga";"Mürgised ained"\n'
    '"%s";"Väo elektrijaam";"13.0";"Harju maakond, Tallinn";"Soojuskiirgus"\n'
    '"BROKEN";"Katkine kirje";"14.0";"Harju maakond";"Soojuskiirgus"\n'
) % (WKT_SQUARE, WKT_SQUARE)


def test_classify_danger_matches_scorer():
    assert classify_danger("Mürgised ained") == "toxic"
    assert classify_danger("Mürgised ained, Soojuskiirgus") == "toxic"
    assert classify_danger("Soojuskiirgus") == "heat"
    assert classify_danger("Ülerõhk") == "overpressure"
    assert classify_danger("midagi muud") == "unknown"
    assert classify_danger(None) == "unknown"


def test_parse_danger_csv_skips_broken_rows():
    zones = parse_danger_csv(DANGER_CSV)
    assert zones is not None
    assert len(zones) == 2
    assert zones[0]["danger"] == "toxic"
    assert zones[0]["aadress"] == "Harju maakond, Muuga"
    assert len(zones[0]["polys"][0]) >= 4


def test_parse_danger_csv_unknown_on_garbage():
    assert parse_danger_csv("not a csv at all") is None
    assert parse_danger_csv("") is None


def test_sidecar_rows_carry_geojson_lonlat_rings():
    rows = to_sidecar(parse_danger_csv(DANGER_CSV))
    assert len(rows) == 2
    row = rows[0]
    assert row["zone_id"] == "12.0"
    assert row["danger_label"] == "Mürgised ained"
    lon, lat = row["r"][0][0]
    assert 23.0 < lon < 29.0 and 57.5 < lat < 60.0
    b = row["b"]
    assert b[0] <= lon <= b[2] and b[1] <= lat <= b[3]


def test_build_sidecar_writes_counts_and_attribution(tmp_path):
    danger = tmp_path / "ohualad.csv"
    danger.write_text(DANGER_CSV, encoding="utf-8")
    snap = tmp_path / "snap"
    stats = build_sidecar(str(danger), str(snap))
    assert stats["ok"] is True
    assert stats["zones"] == 2
    assert stats["harju"] == 2
    assert stats["by_danger"] == {"toxic": 1, "heat": 1}
    assert "Päästeamet" in stats["attribution"]
    dest = snap / "seveso" / "seveso-areas.json"
    rows = json.loads(dest.read_text(encoding="utf-8"))
    assert len(rows) == 2


def test_build_sidecar_refuses_without_input(tmp_path):
    stats = build_sidecar(str(tmp_path / "missing.csv"), str(tmp_path / "s"))
    assert stats["ok"] is False
    assert not (tmp_path / "s" / "seveso" / "seveso-areas.json").exists()
    stats = build_sidecar(None, str(tmp_path / "s"))
    assert stats["ok"] is False
