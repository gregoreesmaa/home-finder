"""Hermetic tests for scripts/build/batch_at_notices.py (issue #628).

No network, no snapshot files: the list-HTML parser, tunnus miner,
linkage math, and the offline merge path run on synthetic fixtures.
Every person, company, number, and tunnus here is INVENTED -- never
a real pull (repo hygiene: fixtures only, no scraped dumps).
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_at_notices import (  # noqa: E402
    SLICES,
    TUNNUS_RE,
    build_sidecar,
    linkage_rate,
    main,
    mine_tunnused,
    parse_list_html,
    row_to_record,
    slice_list_url,
)

LIST_HTML = """
<html><body><div class="search-results">
<div class="result pt-3"><div class="row"><div class="col">
<h2 class="mb-2">1. <a href="/avalik/teadaanne?teate_number=9900111">Detailplaneeringu algatamise teade</a></h2>
</div></div>
<div class="result-box"><div class="announcement forceNostyle">
<div class="announcement-header">Detailplaneeringu algatamise teade</div>
<div class="announcement-date">
Avaldamise algus: 15.08.2026<br>
Avaldamise l\u00f5pp: 15.08.2027</div>
<div class="announcement-body">
<div>Planeeringuala kinnistul 78401:107:0760, Tallinn.</div>
</div></div>
<div class="announcement-provider">N\u00e4idiko Linnavalitsus<br>Tail</div>
</div></div>
<div class="result pt-3"><div class="row"><div class="col">
<h2 class="mb-2">2. <a href="/avalik/teadaanne?teate_number=9900222">Detailplaneeringu kehtestamine</a></h2>
</div></div>
<div class="result-box"><div class="announcement forceNostyle">
<div class="announcement-header">Detailplaneeringu kehtestamine</div>
<div class="announcement-date">
Avaldamise algus: 16.08.2026<br>
Avaldamise l\u00f5pp: 16.08.2027</div>
<div class="announcement-body">
<div>Kehtestatud Harjumaal, tunnuseta.</div>
</div></div>
<div class="announcement-provider">N\u00e4idiko Vald<br>Tail</div>
</div></div>
<div class="result pt-3"><div class="row"><div class="col">
<h2 class="mb-2">3. <a href="/avalik/teadaanne?teate_number=9900111">duplikaat (sama number)</a></h2>
</div></div></div>
</div></body></html>
"""

def test_slice_list_url_has_no_date_segments():
    # Date segments serve empty shells anonymously (2026-09-17) --
    # the month window runs client-side on Avaldamise algus.
    assert slice_list_url("planeering") == (
        "https://www.ametlikudteadaanded.ee/ee/-/planeering")
    assert slice_list_url("planeering", "detailplaneering").endswith(
        "/planeering/detailplaneering")


def test_slice_table_shape():
    assert set(SLICES) == {"quarry", "zoning", "cadastre", "felling"}
    for key, spec in SLICES.items():
        assert spec["pealiik"] and spec["dim"] and spec["keywords"]
        assert spec["verified"] is False  # live run proves each slug
    assert SLICES["quarry"]["band"] == 35
    assert SLICES["zoning"]["band"] == 55
    assert SLICES["cadastre"]["band"] == 60
    assert SLICES["felling"]["band"] is None  # stays NULL


def test_parse_list_html_extracts_rows_and_dedupes():
    rows = parse_list_html(LIST_HTML)
    assert [r["number"] for r in rows] == ["9900111", "9900222"]
    first = rows[0]
    assert first["title"] == "Detailplaneeringu algatamise teade"
    assert first["algus"] == "15.08.2026"
    assert first["lopp"] == "15.08.2027"
    assert "78401:107:0760" in first["body"]
    assert "Linnavalitsus" in first["provider"]


def test_row_to_record_keeps_tunnus_only():
    rec = row_to_record(parse_list_html(LIST_HTML)[0], "zoning")
    assert rec["notice_id"] == "9900111"
    assert rec["url"].endswith("?teate_number=9900111")
    assert rec["tunnused"] == ["78401:107:0760"]
    assert rec["archived"] is None  # resolved by harvest, not parse
    # No notice text or person fields persist on the record.
    assert "sisu" not in rec and "body" not in rec


def test_mine_tunnused_finds_all_keeps_order():
    out = mine_tunnused("kinnistul 78401:107:0760, naaber 78401:107:0761",
                        "kordus 78401:107:0760", None, 123)
    assert out == ["78401:107:0760", "78401:107:0761"]
    assert mine_tunnused("tunnuseta tekst", None) == []


def test_tunnus_regex_rejects_times_and_short():
    # "12:30" is only two groups -- no match at all.
    assert TUNNUS_RE.search("algus 12:30") is None
    assert TUNNUS_RE.search("78401:107:0760")[1] == "78401:107:0760"


def test_linkage_rate_math():
    assert linkage_rate([]) == 0.0
    notices = [{"tunnused": ["78401:107:0760"]}, {"tunnused": []},
               {"tunnused": ["1:2:3", "4:5:6"]}, {}]
    assert linkage_rate(notices) == 0.5


def test_build_sidecar_stats_shape():
    notices = [{"notice_id": "9900111", "url": "u", "liik_nimi": "L",
                "avaldatud": "15.08.2026", "archived": False,
                "tunnused": ["78401:107:0760"]},
               {"notice_id": "9900222", "url": "u", "liik_nimi": "L",
                "avaldatud": "16.08.2026", "archived": False,
                "tunnused": []}]
    doc = build_sidecar(notices, 2, "zoning", 2026, 8)
    assert doc["stats"]["listed"] == 2
    assert doc["stats"]["parsed"] == 2
    assert doc["stats"]["linked"] == 1
    assert doc["stats"]["linkage_rate"] == 0.5
    assert doc["slug_verified"] is False
    assert "Ametlikud Teadaanded" in doc["stats"]["attribution"]


def _seed_cache(cache_dir):
    """Prefill the file cache so main(--merge-only) stays offline."""
    from batch_at_notices import _cache_path, slice_list_url
    os.makedirs(cache_dir, exist_ok=True)
    url = slice_list_url("planeering", "-")
    with open(_cache_path(cache_dir, url), "w",
              encoding="utf-8") as f:
        f.write(LIST_HTML)


def test_merge_only_offline_end_to_end(tmp_path):
    cache = str(tmp_path / "cache")
    snap = str(tmp_path / "snap")
    _seed_cache(cache)
    rc = main(["--slice", "zoning", "--year", "2026", "--month", "8",
               "--cache-dir", cache, "--snap", snap, "--merge-only",
               "--pace", "0"])
    assert rc == 0
    doc = json.loads(open(os.path.join(snap, "at",
                                       "at-notices.json")).read())
    assert doc["stats"]["listed"] == 2
    assert doc["stats"]["parsed"] == 2
    assert doc["stats"]["linked"] == 1
    assert doc["stats"]["linkage_rate"] == 0.5
    assert doc["notices"][0]["tunnused"] == ["78401:107:0760"]


def test_merge_only_honours_pealiik_override(tmp_path):
    # Regression: the offline path ignored --pealiik and silently read
    # the slice-default cache (listed=0 instead of the override rows).
    from batch_at_notices import _cache_path, slice_list_url
    cache = str(tmp_path / "cache")
    snap = str(tmp_path / "snap")
    import os as _os
    _os.makedirs(cache, exist_ok=True)
    with open(_cache_path(cache, slice_list_url("advokatuur", "-")),
              "w", encoding="utf-8") as f:
        f.write(LIST_HTML)
    rc = main(["--slice", "zoning", "--pealiik", "advokatuur",
               "--year", "2026", "--month", "8",
               "--cache-dir", cache, "--snap", snap, "--merge-only",
               "--pace", "0"])
    assert rc == 0
    doc = json.loads(open(_os.path.join(snap, "at",
                                        "at-notices.json")).read())
    assert doc["stats"]["parsed"] == 2


def test_merge_only_missing_cache_fails_loud(tmp_path):
    try:
        main(["--slice", "zoning", "--year", "2026", "--month", "8",
              "--cache-dir", str(tmp_path / "empty"),
              "--snap", str(tmp_path / "snap"), "--merge-only",
              "--pace", "0"])
    except RuntimeError as exc:
        assert "offline cache miss" in str(exc)
    else:
        raise AssertionError("missing cache did not raise")
