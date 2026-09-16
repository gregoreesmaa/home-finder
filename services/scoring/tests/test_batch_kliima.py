"""Hermetic tests for scripts/build/batch_kliima.py (issue #611).

Covers ONLY the pure aggregators/ranker -- the network pull
(fetch_cached/harvest) is never called here (AGENTS.md section 7.6).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_kliima import (  # noqa: E402
    aggregate_frost_days,
    aggregate_precip_mm,
    build_extract,
    rank_bands,
    read_cached_pages,
    ts_snippet,
)


def _daily(year, frost_days, total_days=365):
    rows = []
    for day in range(total_days):
        rows.append({"aasta": year, "element_kood": "DTAN",
                     "vaartus": -1.0 if day < frost_days else 2.0})
    return rows


def _monthly(year, complete=True):
    rows = []
    for month in range(1, 13):
        if not complete and month == 2:
            continue
        rows.append({"aasta": year, "kuu": month,
                     "element_kood": "DPREC", "vaartus": 50.0})
    return rows


def test_frost_mean_over_usable_years():
    rows = _daily(1991, 100) + _daily(1992, 120) + _daily(1993, 110)
    # Pad the remaining 27 years with identical 110-frost years.
    for year in range(1994, 2021):
        rows += _daily(year, 110)
    assert aggregate_frost_days(rows) == 110.0


def test_frost_ignores_non_dtan_and_out_of_window():
    rows = _daily(1991, 100)
    rows.append({"aasta": 1991, "element_kood": "DTA08", "vaartus": -50.0})
    rows.append({"aasta": 2021, "element_kood": "DTAN", "vaartus": -1.0})
    for year in range(1992, 2021):
        rows += _daily(year, 100)
    assert aggregate_frost_days(rows) == 100.0


def test_frost_thin_station_is_null():
    # Only 10 usable years (< 24) -> None, never a zero-filled rank.
    rows = []
    for year in range(1991, 2001):
        rows += _daily(year, 100)
    assert aggregate_frost_days(rows) is None


def test_frost_thin_year_does_not_count():
    rows = []
    for year in range(1991, 2021):
        rows += _daily(year, 100, total_days=200 if year == 2000 else 365)
    # 2000 is unusable (< 300 days); the other 29 average 100.
    assert aggregate_frost_days(rows) == 100.0


def test_precip_sums_months_means_years():
    rows = []
    for year in range(1991, 2021):
        rows += _monthly(year)
    assert aggregate_precip_mm(rows) == 600.0


def test_precip_incomplete_year_excluded():
    rows = []
    for year in range(1991, 2021):
        rows += _monthly(year, complete=(year != 2005))
    # 2005 lacks February -> 29 usable years of 600 mm.
    assert aggregate_precip_mm(rows) == 600.0


def test_precip_thin_station_is_null():
    rows = []
    for year in range(1991, 2000):
        rows += _monthly(year)
    assert aggregate_precip_mm(rows) is None


def test_rank_three_cells_bands():
    assert rank_bands({"a": 90.0, "b": 110.0, "c": 130.0}) == {
        "a": 70, "b": 55, "c": 40}


def test_rank_two_cells_no_middle():
    assert rank_bands({"a": 90.0, "b": 130.0}) == {"a": 70, "b": 40}


def test_rank_ties_share_better_band():
    assert rank_bands({"a": 90.0, "b": 90.0, "c": 130.0}) == {
        "a": 70, "b": 70, "c": 55}


def test_rank_single_cell_unrankable():
    assert rank_bands({"a": 90.0}) == {}


def _write_page(tmp_path, template, code, offset, rows):
    import json
    path = tmp_path / (template % (code, offset))
    path.write_text(json.dumps(rows), encoding="utf-8")


def test_cached_pages_stitch_across_full_page(tmp_path):
    # A full 1000-row page continues to offset 1000; a short page ends
    # the stitch (same stop rule as the live harvest pagination).
    page0 = [{"aasta": 1991, "kuu": m, "element_kood": "DPREC",
              "vaartus": 50.0} for m in range(1, 13)] * 83 + [
        {"aasta": 1991, "kuu": 1, "element_kood": "DPREC",
         "vaartus": 50.0}] * 4  # 1000 rows
    assert len(page0) == 1000
    page1 = [{"aasta": 1991, "kuu": 2, "element_kood": "DPREC",
              "vaartus": 50.0}]
    _write_page(tmp_path, "kuu-%s-%d.json", "AJHARK01", 0, page0)
    _write_page(tmp_path, "kuu-%s-%d.json", "AJHARK01", 1000, page1)
    rows = read_cached_pages(str(tmp_path), "kuu-%s-%d.json", "AJHARK01")
    assert len(rows) == 1001
    assert rows[-1] == page1[0]


def test_cached_pages_short_page_stops(tmp_path):
    page0 = [{"aasta": 1991, "kuu": 1, "element_kood": "DPREC",
              "vaartus": 50.0}]
    _write_page(tmp_path, "kuu-%s-%d.json", "AJHARK01", 0, page0)
    rows = read_cached_pages(str(tmp_path), "kuu-%s-%d.json", "AJHARK01")
    assert rows == page0


def test_cached_pages_missing_cache_is_empty(tmp_path):
    assert read_cached_pages(str(tmp_path), "kuu-%s-%d.json",
                             "AJHARK01") == []


def test_ts_snippet_renders_null_bands_as_null():
    # Regression: Python None once leaked into the TS block as
    # `wetBand: None` (invalid TS). Missing bands render as null.
    cells = {
        "AJHARK01": {"name": "Tallinn-Harku", "lat": 59.398122,
                     "lon": 24.60287, "frost_days": 128.6,
                     "precip_mm": 699.9},
        "AJPAKR01": {"name": "Pakri", "lat": 59.3895, "lon": 24.0401,
                     "frost_days": 106.5, "precip_mm": None},
        "AJKUUS01": {"name": "Kuusiku", "lat": 58.9732, "lon": 24.734,
                     "frost_days": 146.5, "precip_mm": 730.1},
    }
    snippet = ts_snippet(build_extract(cells, "2026-09-16"))
    assert "None" not in snippet
    assert "wetBand: null" in snippet
    assert "frostBand: 70" in snippet  # Pakri mildest of three
