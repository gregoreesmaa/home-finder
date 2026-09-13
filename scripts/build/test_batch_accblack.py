"""Transpordiamet accident-blackspot reader tests (issue #490): hermetic.

No network, no snapshot: the reader runs on a tiny inline fixture CSV
whose two data rows copy REAL live shapes (a 2025 row WITH L-EST97
X/Y, a 2011 row with EMPTY X/Y — observed 2026-09-13), and the TS
verdict drift guard parses the checked-in layers_accblack.ts.
"""

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_accblack as G

FIXTURE_HEADER = (
    "Juhtumi nr;Toimumisaeg;Isikuid;Hukkunuid;S\u00f5idukeid;Vigastatuid;"
    "Aadress;T\u00e4nav;Maja nr;Ristuv t\u00e4nav;Tee nr;Tee km;Maakond;"
    "Omavalitsus;Asustus\u00fcksus;Asula;X koordinaat;Y koordinaat"
)

# Real live shapes (values observed 2026-09-13, addresses trimmed):
# a 2025 Harju row WITH L-EST97 coords, a 2011 Tallinn row WITHOUT.
FIXTURE_ROWS = [
    "2101250159501;2025-09-07 21:25:00;2;0;1;1;;;;;;;Harju maakond;"
    "J\u00f5el\u00e4htme vald;;;6589196.459;568050.8757",
    "2302110069111;2011-03-23 19:00:00;2;0;1;1;;;;;;;Harju maakond;"
    "Tallinn;P\u00f5hja-Tallinna linnaosa;;;",
]


@pytest.fixture()
def csv_path(tmp_path):
    p = tmp_path / "lo_mini.csv"
    p.write_text(FIXTURE_HEADER + "\n" + "\n".join(FIXTURE_ROWS) + "\n",
                 encoding="utf-8")
    return str(p)


def test_parse_and_split_counts_empty_xy(csv_path):
    rows = G.parse_csv(csv_path)
    assert len(rows) == 2
    with_xy, without_xy = G.split_coords(rows)
    assert len(with_xy) == 1
    assert len(without_xy) == 1
    # The empty-xy row is counted, never hidden or faked.
    assert without_xy[0]["Toimumisaeg"] == "2011-03-23 19:00:00"


def test_lest97_gate_rejects_wgs84_scale_and_garbage():
    assert G.has_lest97({"X koordinaat": "6589196.459",
                         "Y koordinaat": "568050.8757"}) is True
    # WGS84 degrees are NOT L-EST97 metres (never plotted as such).
    assert G.has_lest97({"X koordinaat": "59.4374",
                         "Y koordinaat": "24.7454"}) is False
    assert G.has_lest97({"X koordinaat": "", "Y koordinaat": ""}) is False
    assert G.has_lest97({"X koordinaat": None,
                         "Y koordinaat": None}) is False


def test_tallinn_filter_and_severity(csv_path):
    rows = G.parse_csv(csv_path)
    tall = G.tallinn_rows(rows)
    assert len(tall) == 1
    assert tall[0]["Omavalitsus"] == "Tallinn"
    assert G.severity(rows[0]) == 1  # 3*0 dead + 1 injured
    assert G.severity({"Hukkunuid": "1", "Vigastatuid": "2"}) == 5
    assert G.severity({"Hukkunuid": "x", "Vigastatuid": None}) == 0


def test_measured_records_keep_raw_xy_unprojected(csv_path):
    rows = G.parse_csv(csv_path)
    recs = G.measured_records(rows)
    assert len(recs) == 1
    rec = recs[0]
    assert rec["x_lest"] == pytest.approx(6589196.459)
    assert rec["y_lest"] == pytest.approx(568050.8757)
    assert rec["sev"] == 1
    assert rec["year"] == "2025"
    # No WGS84 lat/lon is emitted — projection is the reopen step.
    assert "lat" not in rec and "lon" not in rec
    assert rec["projected"] is False


def test_summarize_counts_everything(csv_path):
    s = G.summarize(G.parse_csv(csv_path))
    assert s == {"rows": 2, "with_xy": 1, "empty_xy": 1,
                 "tallinn": 1, "tallinn_xy": 0}


def test_ts_verdict_drift_guard():
    ts = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "..", "..", "apps", "web", "lib", "layers_accblack.ts")
    src = open(ts, encoding="utf-8").read()
    assert 'date: "%s"' % G.PROBE_DATE in src
    assert "csvBytes: %d" % G.PROBE_CSV_BYTES in src
    assert "headerCols: %d" % G.PROBE_HEADER_COLS in src
    assert "ACCBLACK_WINDOW_M = %d" % G.ACCBLACK_WINDOW_M in src
    assert "accblack: 0.3" in src
    assert "P4-012" in src


def test_no_network_imports():
    src = open(os.path.abspath(G.__file__), encoding="utf-8").read()
    for mod in ("urllib", "socket", "http.client", "requests"):
        assert "import %s" % mod not in src
