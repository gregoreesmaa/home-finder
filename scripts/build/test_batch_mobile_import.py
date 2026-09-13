"""Tests for batch_mobile_import.py (OpenCellID Estonia import).

Hermetic: inline rows only, never the network. Run:
python3 -m pytest scripts/build/test_batch_mobile_import.py -q
"""

import gzip
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from batch_mobile_import import OPERATORS, import_csv, parse_row


def test_parse_row_keeps_lte_with_operator_and_range():
    p = parse_row(["LTE", "248", "2", "2021", "256274198", "0",
                   "24.6606", "59.4264", "822", "27", "1",
                   "1458560497", "1752693844", "0"])
    assert p == {"lon": 24.6606, "lat": 59.4264,
                 "tags": {"radio": "LTE", "operaator": "Elisa",
                          "ulatus_m": "822"}}


def test_parse_row_drops_thin_measurements():
    base = ["LTE", "248", "2", "2021", "1", "0",
            "24.7", "59.43", "822", "27", "1", "1", "2", "0"]
    assert parse_row(base) is not None
    thin = list(base)
    thin[9] = "2"  # only 2 fixes: unreliable footprint
    assert parse_row(thin) is None
    zero = list(base)
    zero[8] = "0"  # zero range: no footprint
    assert parse_row(zero) is None


def test_parse_row_drops_non_broadband_wrong_mcc_junk_coords():
    assert parse_row(["GSM", "248", "2", "31", "55754", "0",
                      "25.5788", "59.5486", "16499", "36", "1",
                      "1453764830", "1747482611", "0"]) is None
    assert parse_row(["UMTS", "248", "1", "5", "9", "0",
                      "24.7", "59.43", "500", "3", "1",
                      "1", "2", "0"]) is None
    assert parse_row(["LTE", "247", "2", "2021", "1", "0",
                      "24.7", "59.43", "822", "27", "1",
                      "1", "2", "0"]) is None
    assert parse_row(["LTE", "248", "2", "2021", "1", "0",
                      "71.6", "3.0", "822", "27", "1",
                      "1", "2", "0"]) is None  # ocean junk
    assert parse_row(["LTE", "248"]) is None  # short row
    assert parse_row(["LTE", "248", "2", "2021", "1", "0",
                      "x", "59.43", "822", "27", "1",
                      "1", "2", "0"]) is None


def test_parse_row_unknown_operator_stays_honest():
    p = parse_row(["LTE", "248", "9", "2021", "1", "0",
                   "24.7", "59.43", "822", "27", "1", "1", "2", "0"])
    assert p is not None and p["tags"]["operaator"] == "teadmata"


def test_operators_cover_all_snapshot_mncs():
    assert set(OPERATORS) == {"1", "2", "3"}


def test_import_csv_dedupes_and_reads_gz(tmp_path):
    rows = [
        "LTE,248,1,1,1,0,24.700000,59.430000,500,10,1,1,2,0",
        "LTE,248,1,1,1,0,24.700000,59.430000,500,10,1,1,2,0",
        "LTE,248,3,1,2,0,24.700000,59.430000,500,10,1,1,2,0",
        "GSM,248,2,31,55754,0,25.5788,59.5486,16499,36,1,1,2,0",
    ]
    gz = str(tmp_path / "t.csv.gz")
    with gzip.open(gz, "wt", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")
    pts = import_csv(gz)
    # Exact twin merged; same coords different operator kept; GSM dropped.
    assert len(pts) == 2
    assert {p["tags"]["operaator"] for p in pts} == {"Telia", "Tele2"}
