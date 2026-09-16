"""P4 renovation-grant dims (issue #538): hermetic tests.

No network: fetch_grants_xlsx is never called here (its contract --
single polite GET, file cache, TTL, transport errors raise -- is
covered via the pure cache_is_fresh helper). The stdlib XLSX reader is
tested against a SYNTHETIC publisher-shape workbook built in tmp_path
(real 15-column layout observed 2026-09-16, invented rows only --
never a real pull). Every dim runs on fixture records through the
join shapes: EHR hit -> bands, address fallback -> bands with the
weaker-join marker, no match -> NULL with EI OLE + KU check.
"""

import zipfile

import dims_p4_recongrant as rg
from dims_p4_recongrant import (
    GRANTS_TTL_DAYS,
    P4_RECONGRANT_DIMS,
    build_grants_index,
    cache_is_fresh,
    dim_recongrant,
    normalise_address,
    parse_grants_xlsx,
    score_p4_recongrant,
)

HEADER = ["Jrk nr", "Programmperiood", "Meede", "Taotlusvoor", "Aadress",
          "Maakond", "KOV", "Projekti rahastamise kp",
          "Projekti lõpetamise kp", "Projekti seisund",
          "Ehitusregistrikood ", "Projekti kogumaksumus", "Toetus",
          "Hoone pindala", "Korterite arv"]


def _synthetic_xlsx(path, rows):
    """Write a minimal publisher-shape XLSX (shared strings + numbers)."""
    strings, index = [], {}

    def sid(text):
        if text not in index:
            index[text] = len(strings)
            strings.append(text)
        return index[text]

    def cell(text):
        return ('<c t="s"><v>%d</v></c>' % sid(text))

    sheet_rows = ["<row>%s</row>" % "".join(cell(h) for h in HEADER)]
    for row in rows:
        cells = []
        for val in row:
            if isinstance(val, (int, float)):
                cells.append("<c><v>%s</v></c>" % val)
            else:
                cells.append(cell(val))
        sheet_rows.append("<row>%s</row>" % "".join(cells))
    sheet = ('<?xml version="1.0"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             "<sheetData>%s</sheetData></worksheet>" % "".join(sheet_rows))
    sst = ('<?xml version="1.0"?>'
           '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
           + "".join("<si><t>%s</t></si>" % s for s in strings) + "</sst>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/sharedStrings.xml", sst.encode("utf-8"))
        z.writestr("xl/worksheets/sheet1.xml", sheet.encode("utf-8"))


def _row(seq, status, ehr, county="Harju maakond", kov=" Anija vald",
         funded="07.01.2021", addr=None):
    return [str(seq), "2014-2020", "Energiatõhusus", "Voor",
            addr or ("Harju maakond, Anija vald, Kehra linn, Kooli tn %d" % seq),
            county, kov, funded, "18.11.2021", status, ehr,
            1068133, 508154.93, 2241.6, 24]


def test_parse_reads_publisher_layout_with_trailing_space_ehr_header(tmp_path):
    path = str(tmp_path / "syn.xlsx")
    _synthetic_xlsx(path, [_row(1, "Lõpetatud", "116002151"),
                           _row(2, "Rahastatud", "")])
    recs = parse_grants_xlsx(path)
    assert len(recs) == 2
    assert recs[0]["ehr"] == "116002151"  # trailing-space header mapped
    assert recs[0]["status"] == "Lõpetatud"
    assert recs[0]["grant_eur"] == 508154.93
    assert recs[0]["kov"] == "Anija vald"  # publisher leading space kept raw
    assert recs[1]["ehr"] is None  # empty EHR reads as None, not ""


def test_bands_completed_funded_other():
    idx = build_grants_index([
        {"ehr": "111", "address": "A", "status": "Lõpetatud",
         "funded": "07.01.2021"},
        {"ehr": "222", "address": "B", "status": "Rahastatud",
         "funded": "25.05.2017"},
        {"ehr": "333", "address": "C", "status": "Katkestatud",
         "funded": None},
    ])
    v, reason = dim_recongrant("111", None, idx)
    assert v == 75
    assert "2021" in reason
    assert "kvaliteedihinne" in reason  # grant != quality legend marker
    v, reason = dim_recongrant("222", None, idx)
    assert v == 60
    assert "KÜ-lt" in reason
    v, reason = dim_recongrant("333", None, idx)
    assert v == 50  # matched but unknown status: neutral, named


def test_ehr_beats_address_and_address_marks_weaker_join():
    idx = build_grants_index([
        {"ehr": "111", "address": "Harju maakond, Kehra, Kooli tn 10",
         "status": "Lõpetatud", "funded": "2017"},
    ])
    v, _ = dim_recongrant("111", "Harju maakond, Kehra, Kooli tn 10", idx)
    assert v == 75
    v, reason = dim_recongrant(None, "Harju maakond,  Kehra, kooli TN 10",
                               idx)
    assert v == 75
    assert "nõrgem" in reason  # address fallback names the weaker join


def test_no_match_is_null_never_unrenovated():
    idx = build_grants_index([
        {"ehr": "111", "address": "A", "status": "Lõpetatud",
         "funded": "2021"},
    ])
    for ehr, addr in [(None, None), ("999999999", None),
                      (None, "Tundmatu tn 1"), ("999", "Tundmatu tn 1")]:
        v, reason = dim_recongrant(ehr, addr, idx)
        assert v is None
        assert "EI OLE" in reason
        assert "KÜ" in reason
        # Absence is never presented as "unrenovated": the reason carries
        # the explicit disclaimer instead of a verdict.
        assert "puudumine ei tähenda renoveerimata hoonet" in reason.lower()
    v, reason = dim_recongrant("111", None, None)  # no index at all
    assert v is None
    assert "EI OLE" in reason


def test_join_path_proven_on_25_harjumaa_fixture_rows(tmp_path):
    """Issue acceptance: join path proven on >=20 Harjumaa rows."""
    rows = [_row(i, "Lõpetatud" if i % 2 else "Rahastatud",
                 "11600%04d" % i if i % 3 else "")
            for i in range(1, 26)]
    path = str(tmp_path / "harju.xlsx")
    _synthetic_xlsx(path, rows)
    recs = parse_grants_xlsx(path)
    assert len(recs) == 25
    idx = build_grants_index(recs)
    ehr_hits = sum(1 for r in recs if r["ehr"])
    assert ehr_hits > 0
    scored = 0
    for r in recs:
        v, _ = dim_recongrant(r["ehr"], r["address"], idx)
        assert v in (60, 75)
        scored += 1
    assert scored == 25
    # A building absent from the register stays NULL (incomplete rounds).
    v, _ = dim_recongrant("199999999", "Harju maakond, Tundmatu tn 99", idx)
    assert v is None


def test_registry_and_rollup():
    assert set(P4_RECONGRANT_DIMS) == {"recongrant"}
    assert P4_RECONGRANT_DIMS["recongrant"][1] is dim_recongrant
    assert rg.P4_RECONGRANT_DIMS is P4_RECONGRANT_DIMS
    idx = build_grants_index([{"ehr": "111", "address": "A",
                               "status": "Lõpetatud", "funded": "2021"}])
    dims, reasons = score_p4_recongrant("111", None, idx)
    assert dims == {"recongrant": 75}
    assert len(reasons) == 1
    dims, reasons = score_p4_recongrant(None, None, idx)
    assert dims == {"recongrant": None}
    assert reasons == []  # NULL dims contribute no reasons


def test_cache_helper_and_ttl(tmp_path):
    assert GRANTS_TTL_DAYS == 365  # IRREG feed: annual re-probe at most
    assert cache_is_fresh(str(tmp_path / "missing.xlsx")) is False
    p = tmp_path / "cached.xlsx"
    p.write_bytes(b"fake")
    assert cache_is_fresh(str(p)) is True


def test_normalise_address_is_conservative():
    assert normalise_address("Harju maakond,  Kehra, KOOLI tn 10") == \
        "harju maakond, kehra, kooli tn 10"
