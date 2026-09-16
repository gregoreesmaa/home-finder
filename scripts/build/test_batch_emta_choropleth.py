"""Hermetic tests for batch_emta_choropleth.py (issue #539).

Synthetic fixtures only: no network, no EMTA data. Publisher-shape
CSVs (real `;`/BOM/Estonian-number layout observed 2026-09-16,
invented KOVs and euros only) are built in tmp_path; the join math,
the inner-join drop rule, and the CLI are pinned here.
"""

import json

import batch_emta_choropleth as b

MONTHS = ["Jaanuar", "Veebruar", "Märts", "Aprill", "Mai", "Juuni",
          "Juuli", "August", "September", "Oktoober", "November",
          "Detsember"]


def _csv_text(rows):
    header = ";".join(["Kood", ""] + ["2026", "2025"] * 12
                      + ["2026", "2025"])
    lines = [";Fake title;;;;",
             ";" + ";".join([""] + [m for pair in zip(MONTHS, MONTHS)
                                    for m in pair] + ["Kokku"]) + ";",
             header]
    for code, name, vals in rows:
        lines.append(";".join([code, name] + vals))
    return "\ufeff" + "\r\n".join(lines) + "\r\n"


def _vals(kokku_prev, jan_this="1 000", jan_prev="900"):
    row = []
    for a, c in [(jan_this, jan_prev)] + [("0", "0")] * 11:
        row += [a, c]
    return row + ["5 000", kokku_prev]


def _write(tmp_path, tulumaks_rows, maamaks_rows):
    t_path = tmp_path / "tulumaks.csv"
    m_path = tmp_path / "maamaks.csv"
    t_path.write_text(_csv_text(tulumaks_rows), encoding="utf-8")
    m_path.write_text(_csv_text(maamaks_rows), encoding="utf-8")
    return str(t_path), str(m_path)


def test_parse_eur_handles_estonian_numbers():
    assert b.parse_eur("1 242") == 1242.0
    assert b.parse_eur("508154.93") == 508154.93
    assert b.parse_eur("") is None
    assert b.parse_eur(None) is None
    assert b.parse_eur("Kokku") is None  # header text never a number


def test_build_joins_inner_and_computes_share(tmp_path):
    t_path, m_path = _write(
        tmp_path,
        [("296", "Keila linn", _vals("17 099 932")),
         ("999", "OnlyT", _vals("1 000"))],
        [("296", "Keila linn", _vals("260 145")),
         ("888", "OnlyM", _vals("50"))])
    table = b.build_kov_table(t_path, m_path)
    # Inner join: one-sided KOVs dropped, never forced.
    assert "code:296" in table and "name:keila linn" in table
    assert "code:999" not in table and "code:888" not in table
    share = table["code:296"]["maamaks_share_2025"]
    assert abs(share - 260145 / (260145 + 17099932) * 100) < 1e-9
    assert table["code:296"]["maamaks_ytd_trend_pct"] > 0  # context only
    assert table["code:296"]["kov_name"] == "Keila linn"
    assert table["_meta"]["source"].startswith("EMTA avaandmed")


def test_sparse_rows_stay_unmapped_not_zero(tmp_path):
    t_path, m_path = _write(tmp_path, [("001", "Sparse vald",
                                        _vals("", "0", "0"))],
                            [("001", "Sparse vald",
                              _vals("", "0", "0"))])
    table = b.build_kov_table(t_path, m_path)
    assert "maamaks_share_2025" not in table["code:001"]
    assert "maamaks_ytd_trend_pct" not in table["code:001"]


def test_cli_writes_json_table(tmp_path, capsys):
    t_path, m_path = _write(tmp_path,
                            [("296", "Keila linn", _vals("17 099 932"))],
                            [("296", "Keila linn", _vals("260 145"))])
    out = str(tmp_path / "kov.json")
    b.main(["--tulumaks", t_path, "--maamaks", m_path, "--out", out])
    assert "kovs=1" in capsys.readouterr().out
    assert json.load(open(out, encoding="utf-8"))["code:296"][  # noqa: PTH123
        "maamaks_share_2025"] > 0


def test_normalise_kov_matches_scorer():
    assert b.normalise_kov("  Lääne-Harju VALD ") == "lääne-harju vald"
