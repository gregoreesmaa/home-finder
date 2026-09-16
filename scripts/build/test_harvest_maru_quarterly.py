"""Hermetic tests for harvest_maru_quarterly.py (issue #514).

Synthetic fixtures only: a hand-made minimal report table and a minimal
form fragment. No network, no snapshot, no MARU data, no scraped dumps.
What is pinned: the KOKKU parser (header-indexed columns, '***' min-5
masking -> None never 0, Estonian number format) and the browser-mirror
control builder (checked-only radios, submit skipped, empty multi-select
omitted, drop-down first-item default).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harvest_maru_quarterly as h

REPORT = """<table>
<tr><th></th><th>Pindala(m2)</th><th>Tehingu summa (eur)</th><th>Pinna&uuml;hiku hind(eur /m2)</th></tr>
<tr><td></td><td>Pindala(m2)</td><td>Arv</td><td>Keskmine</td><td>Kokku</td><td>Minimaalne</td><td>Maksimaalne</td><td>Minimaalne</td><td>Maksimaalne</td><td>Mediaan</td><td>Keskmine</td><td>Standardh&auml;lve</td></tr>
<tr><td>Testvald</td><td>30-40,99</td><td>26</td><td>86,1</td><td>265,25</td><td>100</td><td>900</td><td>1500</td><td>5000</td><td>4&nbsp;038,05</td><td>4100,00</td><td>500,5</td></tr>
<tr><td></td><td>KOKKU</td><td>26</td><td>86,1</td><td>265,25</td><td>100</td><td>900</td><td>1500</td><td>5000</td><td>4&nbsp;038,05</td><td>4100,00</td><td>500,5</td></tr>
<tr><td>Vaikvald</td><td>10-29,99</td><td>2</td><td>***</td><td>***</td><td>***</td><td>***</td><td>***</td><td>***</td><td>***</td><td>***</td><td>***</td></tr>
<tr><td></td><td>KOKKU</td><td>2</td><td>***</td><td>***</td><td>***</td><td>***</td><td>***</td><td>***</td><td>***</td><td>***</td><td>***</td></tr>
</table>"""

FORM = """<form>
<input type="hidden" name="__VIEWSTATE" value="abc" />
<input type="radio" name="RBLAeg" value="0" checked="checked" />
<input type="radio" name="RBLAeg" value="1" />
<input type="checkbox" name="chkAsukoht" />
<input type="text" name="txtAlgus" value="" />
<input type="submit" name="btnTryki" value="Koosta aruanne" />
<select name="DDTrykis"><option value="D">Gen</option><option value="G">Price</option></select>
<select multiple="multiple" name="DDMaakond"><option value="0037">Harju</option></select>
</form>"""


def test_parse_report_kokku_and_masking():
    rows = h.parse_report(REPORT)
    assert len(rows) == 2
    assert rows[0] == {"kov": "Testvald", "deals": 26.0,
                       "median_eur_m2": 4038.05}
    # min-5 masking stays None, never 0 (deals visible, median masked).
    assert rows[1] == {"kov": "Vaikvald", "deals": 2.0,
                       "median_eur_m2": None}


def test_num_estonian_format():
    assert h.num("4&nbsp;038,05".replace("&nbsp;", "\xa0")) == 4038.05
    assert h.num("86,1") == 86.1
    assert h.num("***") is None
    assert h.num("") is None


def test_controls_mirrors_browser():
    f = h.controls(FORM)
    assert f["__VIEWSTATE"] == "abc"
    assert f["RBLAeg"] == "0"  # checked radio only
    assert "chkAsukoht" not in f  # unchecked checkbox omitted
    assert "btnTryki" not in f  # submit skipped
    assert f["DDTrykis"] == "D"  # drop-down defaults to first item
    assert "DDMaakond" not in f  # empty multi-select omitted
