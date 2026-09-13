"""P4 bikes dims (issue #309): hermetic tests.

No network: Tallinna bike-counter counts and MPD aggregates are NOT
published as an open bulk feed (2026-09-13 dated negative, see
dims_p4_bikes docstring), so every test runs on fixture
snapshot-dicts and hand-built hex rosters. The polite fetcher is
covered via a stubbed urlopen (cache-hit performs no request;
no-endpoint and transport-error paths return None and cache nothing);
the scorer is proven network-free by running it with urlopen stubbed
to raise.
"""

import json
import urllib.request

import dims_p4_bikes as b4k
import pytest
from dims_p4_bikes import (
    BIKES_BULK_URL,
    BIKES_TTL_S,
    BIKES_UA,
    CACHE_FILENAME,
    COUNT_KINDS,
    P4_BIKES_DIMS,
    USAGE_BANDS,
    dim_usage_bikes_hex,
    fetch_bikes_snapshot,
    hex_usage_index,
    parse_bikes_snapshot,
    score_p4_bikes,
)

QUIET = "H9-quiet-hex"
LIVELY = "H9-lively-hex"


def mkrow(hex_id=LIVELY, counter_id="C-1", period="2026-08",
          evening_count=12, kind="counter"):
    return {"counter_id": counter_id, "hex_id": hex_id, "period": period,
            "evening_count": evening_count, "kind": kind}


def snap(hexes=(QUIET, LIVELY), rows=()):
    return {"hexes": list(hexes), "counts": list(rows)}


def listing(hex_id=LIVELY):
    return {"hex_id": hex_id}


def raise_urlopen(*a, **k):
    raise AssertionError("network touched in hermetic test")


# ---------------------------------------------------------------------------
# Contract: no open bulk endpoint (dated negative is a code path).
# ---------------------------------------------------------------------------

def test_no_bulk_endpoint_yet():
    assert BIKES_BULK_URL is None
    assert BIKES_TTL_S == 24 * 3600  # daily pull ticket
    assert "home-finder" in BIKES_UA
    assert COUNT_KINDS == frozenset({"counter", "mpd"})
    assert USAGE_BANDS == [(0, 30), (9, 55), (49, 75), (float("inf"), 90)]


# ---------------------------------------------------------------------------
# P4-032 counters+MPD leg: usage bands per hex.
# ---------------------------------------------------------------------------

def test_covered_zero_scores_measured_quiet():
    v, reason = dim_usage_bikes_hex(
        listing(QUIET), snap(rows=[mkrow()]))
    assert v == 30  # measured quiet, low — not lively
    assert "hinnang" in reason and QUIET in reason and "0" in reason


def test_bands_sum_evening_counts_in_hex():
    assert dim_usage_bikes_hex(
        listing(), snap(rows=[mkrow(evening_count=1)]))[0] == 55
    assert dim_usage_bikes_hex(
        listing(), snap(rows=[mkrow(evening_count=9)]))[0] == 55
    assert dim_usage_bikes_hex(
        listing(), snap(rows=[mkrow(evening_count=10)]))[0] == 75
    assert dim_usage_bikes_hex(
        listing(), snap(rows=[mkrow(evening_count=49)]))[0] == 75
    assert dim_usage_bikes_hex(
        listing(), snap(rows=[mkrow(evening_count=50)]))[0] == 90
    many = [mkrow(counter_id="C-%d" % i, evening_count=20)
            for i in range(5)]
    assert dim_usage_bikes_hex(listing(), snap(rows=many))[0] == 90


def test_counter_and_mpd_rows_sum_never_filtered():
    rows = [mkrow(counter_id="C-1", evening_count=6, kind="counter"),
            mkrow(counter_id="M-1", evening_count=6, kind="mpd"),
            mkrow(counter_id="X-1", evening_count=6,
                  kind="future-kind")]  # unknown kind still counts
    v, reason = dim_usage_bikes_hex(listing(), snap(rows=rows))
    assert v == 75  # 6 + 6 + 6 = 18
    assert "hinnang" in reason


def test_neighbour_hex_never_leaks():
    crowd = [mkrow(counter_id="C-%d" % i, evening_count=20)
             for i in range(5)]
    v, _ = dim_usage_bikes_hex(listing(QUIET), snap(rows=crowd))
    assert v == 30
    v, _ = dim_usage_bikes_hex(listing(LIVELY), snap(rows=crowd))
    assert v == 90


def test_uncovered_hex_stays_null_never_quiet():
    v, reason = dim_usage_bikes_hex(listing("H9-nowhere"), snap())
    assert v is None and "EI OLE" in reason
    # A counted row is itself measurement: it self-covers.
    v, reason = dim_usage_bikes_hex(
        listing("H9-nowhere"),
        snap(rows=[mkrow(hex_id="H9-nowhere", evening_count=3)]))
    assert v == 55 and "hinnang" in reason


def test_missing_hex_id_stays_null():
    for lst in ({}, {"hex_id": ""}, {"hex_id": "  "}, {"hex_id": None},
                {"hex_id": 42}, None):
        v, reason = dim_usage_bikes_hex(lst, snap())
        assert v is None
        assert "EI OLE" in reason


def test_null_without_snapshot():
    v, reason = dim_usage_bikes_hex(listing(), None)
    assert v is None and "EI OLE" in reason
    v, reason = dim_usage_bikes_hex(listing(), "nope")
    assert v is None and "EI OLE" in reason


def test_empty_roster_snapshot_never_scores_lively():
    v, reason = dim_usage_bikes_hex(listing(), snap(hexes=[]))
    assert v is None and "EI OLE" in reason


def test_malformed_counts_skipped_never_faked():
    rows = [mkrow(evening_count=-4),  # negative: skipped
            mkrow(counter_id="S", evening_count="12"),  # str: skipped
            mkrow(counter_id="B", evening_count=True),  # bool: skipped
            {"counter_id": "N", "hex_id": LIVELY,
             "kind": "counter"},  # absent count: skipped
            {"counter_id": "X", "evening_count": 40},  # hex-less: skipped
            mkrow(counter_id="OK", evening_count=8)]
    v, _ = dim_usage_bikes_hex(listing(), snap(rows=rows))
    assert v == 55  # exactly the one well-formed row


def test_scored_reason_is_usage_not_safety():
    v, r = dim_usage_bikes_hex(listing(), snap(rows=[mkrow()]))
    assert v == 75 and "hinnang" in r and LIVELY in r
    assert "kasutus-mitte-turvalisus" in r
    assert "PPA" in r  # explicitly NOT a source
    assert "EI OLE" in r  # sibling legs named, not faked


def test_null_reason_carries_ei_ole_and_no_fake_precision():
    _, reason = dim_usage_bikes_hex(listing(), None)
    assert "EI OLE" in reason
    assert "kohapealsel vaatlusel" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_scorer_never_touches_network(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", raise_urlopen)
    full = snap(rows=[mkrow()])
    dim_usage_bikes_hex(listing(), full)
    dim_usage_bikes_hex(listing("H9-nowhere"), full)
    dim_usage_bikes_hex({}, None)
    hex_usage_index(full)


# ---------------------------------------------------------------------------
# Offline readers: malformed skipped, missing file None.
# ---------------------------------------------------------------------------

FIXTURE = {
    "hexes": [QUIET, LIVELY, 42, "  "],
    "counts": [
        {"counter_id": "C-1", "hex_id": LIVELY, "period": "2026-08",
         "evening_count": 12, "kind": "counter"},
        {"counter_id": "M-1", "hex_id": LIVELY, "period": "2026-08",
         "evening_count": 7, "kind": "mpd"},
        {"counter_id": "NEG", "hex_id": LIVELY, "evening_count": -5,
         "kind": "counter"},  # skipped: negative
        {"counter_id": "STR", "hex_id": LIVELY, "evening_count": "9",
         "kind": "counter"},  # skipped: non-int
        {"counter_id": "NOHEX", "evening_count": 40},  # no hex: skipped
        {"counter_id": "BOOL", "hex_id": LIVELY, "evening_count": True,
         "kind": "counter"},  # skipped: bool is not a count
    ],
}


def test_index_seeds_covered_zero_and_skips_garbage():
    idx = hex_usage_index(FIXTURE)
    assert idx == {QUIET: 0, LIVELY: 19}  # 12 + 7
    assert hex_usage_index(None) is None
    assert hex_usage_index("nope") is None
    assert hex_usage_index({}) == {}
    assert hex_usage_index({"hexes": "nope"}) == {}
    assert hex_usage_index(
        {"hexes": [QUIET], "counts": "nope"}) == {QUIET: 0}


def test_fixture_end_to_end_shape():
    v, reason = dim_usage_bikes_hex(listing(LIVELY), FIXTURE)
    assert v == 75  # 12 counter + 7 MPD evening counts in the hex
    assert "hinnang" in reason
    v, _ = dim_usage_bikes_hex(listing(QUIET), FIXTURE)
    assert v == 30


def test_parse_snapshot_roundtrip_and_missing(tmp_path):
    fp = tmp_path / "snap.json"
    fp.write_text(json.dumps(FIXTURE), encoding="utf-8")
    snapd = parse_bikes_snapshot(str(fp))
    assert snapd is not None and len(snapd["counts"]) == 6
    assert snapd["hexes"] == [QUIET, LIVELY]  # non-str roster dropped
    assert parse_bikes_snapshot(str(tmp_path / "absent.json")) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert parse_bikes_snapshot(str(bad)) is None
    lst = tmp_path / "list.json"
    lst.write_text("[1,2]", encoding="utf-8")
    assert parse_bikes_snapshot(str(lst)) is None


# ---------------------------------------------------------------------------
# Polite fetcher: cache hit = no request; no endpoint = no request.
# ---------------------------------------------------------------------------

def test_fetch_cache_hit_performs_no_request(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", raise_urlopen)
    dest = tmp_path / CACHE_FILENAME
    dest.write_text("{}", encoding="utf-8")
    assert fetch_bikes_snapshot(str(tmp_path)) == str(dest)


def test_fetch_without_endpoint_performs_no_request(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", raise_urlopen)
    assert fetch_bikes_snapshot(str(tmp_path), bulk_url=None) is None
    assert not (tmp_path / CACHE_FILENAME).exists()  # errors cache nothing


def test_fetch_transport_error_caches_nothing(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise OSError("network down")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    url = "https://example.invalid/bikes.json"
    assert fetch_bikes_snapshot(str(tmp_path), bulk_url=url) is None
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
    assert fetch_bikes_snapshot(
        str(tmp_path), bulk_url="https://example.invalid/x") is None
    assert not (tmp_path / CACHE_FILENAME).exists()


def test_fetch_stores_json_snapshot(tmp_path, monkeypatch):
    body = json.dumps({"hexes": [], "counts": []}).encode()

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
    got = fetch_bikes_snapshot(
        str(tmp_path), bulk_url="https://example.invalid/bikes.json")
    assert got == str(tmp_path / CACHE_FILENAME)
    assert parse_bikes_snapshot(got) == {"hexes": [], "counts": []}


# ---------------------------------------------------------------------------
# Registry + aggregator.
# ---------------------------------------------------------------------------

def test_registry_and_aggregator_cover_single_param():
    assert [(k, p) for k, p, _ in P4_BIKES_DIMS] == [
        ("usage_bikes_hex", "P4-032"),
    ]
    full = snap(rows=[mkrow()])
    assert score_p4_bikes(listing(), full) == {"usage_bikes_hex": 75}
    calm = snap()
    assert score_p4_bikes(listing(QUIET), calm) == {"usage_bikes_hex": 30}
    assert score_p4_bikes(listing(), None) == {"usage_bikes_hex": None}
    assert b4k.P4_BIKES_DIMS is P4_BIKES_DIMS
