"""Accident-blackspot L-EST97 projection tests (issue #522): hermetic.

No network, no snapshot: the ported lest97_to_wgs84 is pinned against
its oracle (scripts/build/batch_tervise.py, verified <1 mm vs pyproj
there) on the real live shapes from test_batch_accblack.py, and
projected_records() must keep pre-2019 blank-coordinate rows NULL
(skipped + counted, never plotted, never zero-filled).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_accblack as A
import batch_tervise as T

FIXTURE_HEADER = (
    "Juhtumi nr;Toimumisaeg;Isikuid;Hukkunuid;S\u00f5idukeid;Vigastatuid;"
    "Aadress;T\u00e4nav;Maja nr;Ristuv t\u00e4nav;Tee nr;Tee km;Maakond;"
    "Omavalitsus;Asustus\u00fcksus;Asula;X koordinaat;Y koordinaat"
)

# Same real live shapes as test_batch_accblack.py: a 2025 Jõelähtme row
# WITH L-EST97 coords, a 2011 Tallinn row with EMPTY X/Y (pre-2019 blank).
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


def test_transform_parity_with_tervise_oracle():
    # Byte-identical math to batch_tervise.py on the live fixture coord
    # AND on the Pirita control point: agreement far below 1 mm.
    for northing, easting in ((6589196.459, 568050.8757),
                              (6593003.741, 547104.133)):
        lat_a, lon_a = A.lest97_to_wgs84(northing, easting)
        lat_t, lon_t = T.lest97_to_wgs84(northing, easting)
        assert abs(lat_a - lat_t) < 1e-9
        assert abs(lon_a - lon_t) < 1e-9


def test_transform_lands_fixture_in_harju():
    # The 2025 Jõelähtme row must project to Harju county, not to sea.
    lat, lon = A.lest97_to_wgs84(6589196.459, 568050.8757)
    assert 59.3 < lat < 59.6
    assert 24.3 < lon < 25.3


def test_transform_labels_accuracy_and_rejects_nonfinite():
    assert "EPSG:3301" in A.LEST97_ACCURACY_LABEL
    assert A.LEST97_ACCURACY_LABEL == T.LEST97_ACCURACY_LABEL
    with pytest.raises(ValueError):
        A.lest97_to_wgs84(float("nan"), 568050.8757)


def test_projected_records_carry_vintage_and_transform(csv_path):
    rows = A.parse_csv(csv_path)
    recs = A.projected_records(rows)
    assert len(recs) == 1
    rec = recs[0]
    assert rec["projected"] is True
    assert rec["transform"] == A.LEST97_ACCURACY_LABEL
    assert rec["year"] == "2025"
    assert rec["vintage"] == "2025-09-07"
    assert rec["sev"] == 1
    assert 59.3 < rec["lat"] < 59.6
    assert 24.3 < rec["lon"] < 25.3
    # Raw L-EST97 rides along for reviewability.
    assert rec["x_lest"] == pytest.approx(6589196.459)
    assert rec["y_lest"] == pytest.approx(568050.8757)


def test_blank_rows_stay_null_never_plotted(csv_path):
    rows = A.parse_csv(csv_path)
    recs = A.projected_records(rows)
    # The pre-2019 blank-coordinate Tallinn row yields NO point ...
    assert all(r["year"] != "2011" for r in recs)
    # ... but stays counted (NULL, never hidden, never zero-filled).
    with_xy, without_xy = A.split_coords(rows)
    assert len(with_xy) == 1 and len(with_xy) == len(recs)
    assert len(without_xy) == 1
    assert without_xy[0]["Toimumisaeg"] == "2011-03-23 19:00:00"


def test_no_network_imports():
    src = open(os.path.abspath(A.__file__), encoding="utf-8").read()
    for mod in ("urllib", "socket", "http.client", "requests"):
        assert "import %s" % mod not in src
