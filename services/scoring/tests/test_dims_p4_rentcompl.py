"""P4 rentcompl dims (issue #294): hermetic tests.

No network: Tallinna short-rental complaints are NOT published as an
open dataset (2026-09-13 dated negative, see dims_p4_rentcompl
docstring), so every test runs on fixture snapshot-dicts and
hand-built hex rosters. The polite fetcher is covered via a stubbed
urlopen (cache-hit performs no request; no-endpoint and
transport-error paths return None and cache nothing); the scorer is
proven network-free by running it with urlopen stubbed to raise.
"""

import json
import urllib.request

import dims_p4_rentcompl as r4c
import pytest
from dims_p4_rentcompl import (
    CACHE_FILENAME,
    NUISANCE_BANDS,
    P4_RENTCOMPL_DIMS,
    RENTCOMPL_BULK_URL,
    RENTCOMPL_TTL_S,
    RENTCOMPL_UA,
    TALLINN_KOVS,
    dim_nuisance_rentcompl_hex,
    fetch_rentcompl_snapshot,
    hex_nuisance_index,
    parse_rentcompl_snapshot,
    score_p4_rentcompl,
)

CALM = "H9-calm-hex"
BUSY = "H9-busy-hex"


def mkrow(hex_id=BUSY, kov="Tallinn", complaint_id="K-1",
          period="2026-08", kind="müra"):
    return {"complaint_id": complaint_id, "hex_id": hex_id, "kov": kov,
            "period": period, "kind": kind}


def snap(hexes=(CALM, BUSY), rows=()):
    return {"hexes": list(hexes), "complaints": list(rows)}


def listing(hex_id=BUSY):
    return {"hex_id": hex_id}


def raise_urlopen(*a, **k):
    raise AssertionError("network touched in hermetic test")


# ---------------------------------------------------------------------------
# Contract: no open bulk endpoint (dated negative is a code path).
# ---------------------------------------------------------------------------

def test_no_bulk_endpoint_yet():
    assert RENTCOMPL_BULK_URL is None
    assert RENTCOMPL_TTL_S == 30 * 24 * 3600  # monthly pull ticket
    assert "home-finder" in RENTCOMPL_UA
    assert TALLINN_KOVS == frozenset({"tallinn", "tallinna linn"})
    assert NUISANCE_BANDS == [(0, 85), (1, 65), (4, 45), (float("inf"), 25)]


# ---------------------------------------------------------------------------
# P4-003 complaints leg: nuisance bands per hex.
# ---------------------------------------------------------------------------

def test_covered_zero_scores_measured_calm_capped():
    v, reason = dim_nuisance_rentcompl_hex(
        listing(CALM), snap(rows=[mkrow()]))
    assert v == 85  # capped: one signal, not a calm guarantee
    assert "hinnang" in reason and CALM in reason and "0" in reason


def test_bands_count_all_rows_in_hex():
    assert dim_nuisance_rentcompl_hex(
        listing(), snap(rows=[mkrow()]))[0] == 65
    assert dim_nuisance_rentcompl_hex(
        listing(), snap(rows=[mkrow(complaint_id="K-1"),
                              mkrow(complaint_id="K-2")]))[0] == 45
    many = [mkrow(complaint_id="K-%d" % i) for i in range(4)]
    assert dim_nuisance_rentcompl_hex(listing(), snap(rows=many))[0] == 45
    crowd = [mkrow(complaint_id="K-%d" % i) for i in range(9)]
    assert dim_nuisance_rentcompl_hex(listing(), snap(rows=crowd))[0] == 25


def test_all_kinds_count_nuisance_is_nuisance():
    rows = [mkrow(complaint_id="M", kind="müra"),
            mkrow(complaint_id="P", kind="prügi"),
            mkrow(complaint_id="U", kind="muu"),
            mkrow(complaint_id="N")]  # kind absent: still a complaint
    v, reason = dim_nuisance_rentcompl_hex(listing(), snap(rows=rows))
    assert v == 45
    assert "hinnang" in reason


def test_neighbour_hex_never_leaks():
    # BUSY's 5 complaints must not touch CALM's measured zero.
    crowd = [mkrow(complaint_id="K-%d" % i) for i in range(5)]
    v, _ = dim_nuisance_rentcompl_hex(listing(CALM), snap(rows=crowd))
    assert v == 85
    v, _ = dim_nuisance_rentcompl_hex(listing(BUSY), snap(rows=crowd))
    assert v == 25


def test_uncovered_hex_stays_null_never_calm():
    v, reason = dim_nuisance_rentcompl_hex(listing("H9-nowhere"), snap())
    assert v is None and "EI OLE" in reason
    # A counted Tallinn row is itself measurement: it self-covers.
    v, reason = dim_nuisance_rentcompl_hex(
        listing("H9-nowhere"), snap(rows=[mkrow(hex_id="H9-nowhere")]))
    assert v == 65 and "hinnang" in reason


def test_missing_hex_id_stays_null():
    for lst in ({}, {"hex_id": ""}, {"hex_id": "  "}, {"hex_id": None},
                {"hex_id": 42}, None):
        v, reason = dim_nuisance_rentcompl_hex(lst, snap())
        assert v is None
        assert "EI OLE" in reason


def test_null_without_snapshot():
    v, reason = dim_nuisance_rentcompl_hex(listing(), None)
    assert v is None and "EI OLE" in reason
    v, reason = dim_nuisance_rentcompl_hex(listing(), "nope")
    assert v is None and "EI OLE" in reason


def test_empty_roster_snapshot_never_scores_clear():
    v, reason = dim_nuisance_rentcompl_hex(listing(), snap(hexes=[]))
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# Tallinn filter: national rows never join a Tallinn hex.
# ---------------------------------------------------------------------------

def test_tallinn_filter_skips_non_tallinn_rows():
    rows = [mkrow(complaint_id="T", kov="Tartu"),
            mkrow(complaint_id="P", kov="Pärnu"),
            mkrow(complaint_id="H", kov="Harjumaa")]
    v, reason = dim_nuisance_rentcompl_hex(listing(), snap(rows=rows))
    assert v == 85  # skipped rows leave a measured zero
    assert "hinnang" in reason


def test_tallinn_filter_accepts_spelling_variants():
    rows = [mkrow(complaint_id="A", kov="Tallinna linn")]
    assert dim_nuisance_rentcompl_hex(listing(), snap(rows=rows))[0] == 65
    rows = [mkrow(complaint_id="B", kov="  TALLINN  ")]
    assert dim_nuisance_rentcompl_hex(listing(), snap(rows=rows))[0] == 65


def test_tallinn_filter_missing_kov_is_unknown_not_tallinn():
    rows = [{"complaint_id": "NOKOV", "hex_id": BUSY}]  # no kov
    v, reason = dim_nuisance_rentcompl_hex(listing(), snap(rows=rows))
    assert v == 85  # kov-less row skipped, covered hex stays measured zero
    assert "hinnang" in reason


def test_hexless_rows_skipped_never_faked():
    rows = [mkrow(hex_id=""), {"complaint_id": "X", "kov": "Tallinn"},
            mkrow(complaint_id="OK")]
    v, _ = dim_nuisance_rentcompl_hex(listing(), snap(rows=rows))
    assert v == 65  # exactly the one well-formed Tallinn row


# ---------------------------------------------------------------------------
# Honesty markers.
# ---------------------------------------------------------------------------

def test_scored_reason_says_hinnang_with_components():
    v, r = dim_nuisance_rentcompl_hex(listing(), snap(rows=[mkrow()]))
    assert v == 65 and "hinnang" in r and BUSY in r
    assert "EI OLE" in r  # sibling legs (KV/Airbnb/REL2021) named, not faked


def test_null_reason_carries_ei_ole_and_no_fake_precision():
    _, reason = dim_nuisance_rentcompl_hex(listing(), None)
    assert "EI OLE" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_scorer_never_touches_network(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", raise_urlopen)
    full = snap(rows=[mkrow()])
    dim_nuisance_rentcompl_hex(listing(), full)
    dim_nuisance_rentcompl_hex(listing("H9-nowhere"), full)
    dim_nuisance_rentcompl_hex({}, None)
    hex_nuisance_index(full)


# ---------------------------------------------------------------------------
# Offline readers: malformed skipped, missing file None.
# ---------------------------------------------------------------------------

FIXTURE = {
    "hexes": [CALM, BUSY, 42, "  "],
    "complaints": [
        {"complaint_id": "K-1", "hex_id": BUSY, "kov": "Tallinn",
         "period": "2026-08", "kind": "müra"},
        {"complaint_id": "K-2", "hex_id": BUSY, "kov": "Tallinna linn",
         "period": "2026-07", "kind": "prügi"},
        {"complaint_id": "T-1", "hex_id": BUSY, "kov": "Tartu",
         "period": "2026-08", "kind": "müra"},  # skipped: Tallinn filter
        {"complaint_id": "NOKOV", "hex_id": BUSY,
         "period": "2026-08"},  # skipped: unknown municipality
        {"complaint_id": "NOHEX", "kov": "Tallinn"},  # no hex: skipped
        {"complaint_id": "BOOL", "hex_id": True, "kov": "Tallinn"},
    ],
}


def test_index_seeds_covered_zero_and_skips_garbage():
    idx = hex_nuisance_index(FIXTURE)
    assert idx == {CALM: 0, BUSY: 2}
    assert hex_nuisance_index(None) is None
    assert hex_nuisance_index("nope") is None
    assert hex_nuisance_index({}) == {}
    assert hex_nuisance_index({"hexes": "nope"}) == {}
    assert hex_nuisance_index(
        {"hexes": [CALM], "complaints": "nope"}) == {CALM: 0}


def test_fixture_end_to_end_shape():
    v, reason = dim_nuisance_rentcompl_hex(listing(BUSY), FIXTURE)
    assert v == 45  # K-1 + K-2 Tallinn rows in the hex
    assert "hinnang" in reason
    v, _ = dim_nuisance_rentcompl_hex(listing(CALM), FIXTURE)
    assert v == 85


def test_parse_snapshot_roundtrip_and_missing(tmp_path):
    fp = tmp_path / "snap.json"
    fp.write_text(json.dumps(FIXTURE), encoding="utf-8")
    snapd = parse_rentcompl_snapshot(str(fp))
    assert snapd is not None and len(snapd["complaints"]) == 6
    assert snapd["hexes"] == [CALM, BUSY]  # non-str roster entries dropped
    assert parse_rentcompl_snapshot(str(tmp_path / "absent.json")) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert parse_rentcompl_snapshot(str(bad)) is None
    lst = tmp_path / "list.json"
    lst.write_text("[1,2]", encoding="utf-8")
    assert parse_rentcompl_snapshot(str(lst)) is None


# ---------------------------------------------------------------------------
# Polite fetcher: cache hit = no request; no endpoint = no request.
# ---------------------------------------------------------------------------

def test_fetch_cache_hit_performs_no_request(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", raise_urlopen)
    dest = tmp_path / CACHE_FILENAME
    dest.write_text("{}", encoding="utf-8")
    assert fetch_rentcompl_snapshot(str(tmp_path)) == str(dest)


def test_fetch_without_endpoint_performs_no_request(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", raise_urlopen)
    assert fetch_rentcompl_snapshot(str(tmp_path), bulk_url=None) is None
    assert not (tmp_path / CACHE_FILENAME).exists()  # errors cache nothing


def test_fetch_transport_error_caches_nothing(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise OSError("network down")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    url = "https://example.invalid/rentcompl.json"
    assert fetch_rentcompl_snapshot(str(tmp_path), bulk_url=url) is None
    assert not (tmp_path / CACHE_FILENAME).exists()


def test_fetch_rejects_non_json_body(tmp_path, monkeypatch):
    class Resp:
        status = 200
        headers = {"Content-Type": "text/html"}

        def read(self):
            return b"<html>register</html>"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: Resp())
    assert fetch_rentcompl_snapshot(
        str(tmp_path), bulk_url="https://example.invalid/x") is None
    assert not (tmp_path / CACHE_FILENAME).exists()


def test_fetch_stores_json_snapshot(tmp_path, monkeypatch):
    body = json.dumps({"hexes": [], "complaints": []}).encode()

    class Resp:
        status = 200
        headers = {"Content-Type": "application/json"}

        def read(self):
            return body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: Resp())
    got = fetch_rentcompl_snapshot(
        str(tmp_path), bulk_url="https://example.invalid/rentcompl.json")
    assert got == str(tmp_path / CACHE_FILENAME)
    assert parse_rentcompl_snapshot(got) == {"hexes": [], "complaints": []}


# ---------------------------------------------------------------------------
# Registry + aggregator.
# ---------------------------------------------------------------------------

def test_registry_and_aggregator_cover_single_param():
    assert [(k, p) for k, p, _ in P4_RENTCOMPL_DIMS] == [
        ("nuisance_rentcompl_hex", "P4-003"),
    ]
    full = snap(rows=[mkrow()])
    assert score_p4_rentcompl(listing(), full) == {"nuisance_rentcompl_hex": 65}
    calm = snap()
    assert score_p4_rentcompl(listing(CALM), calm) == {
        "nuisance_rentcompl_hex": 85}
    assert score_p4_rentcompl(listing(), None) == {
        "nuisance_rentcompl_hex": None}
    assert r4c.P4_RENTCOMPL_DIMS is P4_RENTCOMPL_DIMS
