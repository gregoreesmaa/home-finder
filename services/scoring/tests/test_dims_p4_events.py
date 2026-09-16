"""P4 events demo + coverage dims (issues #310, #375): hermetic tests.

No network: the kultuurikava app-API snapshot is pulled by the
polite fetcher (covered via a stubbed urlopen: cache-hit performs
no request; transport errors and non-JSON bodies cache nothing);
every scorer/index test runs on hand-built snapshot dicts that
mirror the live envelope schema (2026-09-16 dig, see
dims_p4_events docstring), plus tmp-file roundtrips. The scorer is
proven network-free by running it with urlopen stubbed to raise.
"""

import json
import urllib.request

import dims_p4_events as events
import pytest
from dims_p4_events import (
    CALM_BANDS,
    CACHE_FILENAME,
    EVENTS_TTL_S,
    EVENTS_UA,
    FETCH_LIMIT,
    KULTUURIKAVA_API,
    KULTUURIKAVA_TOKEN,
    P4_EVENTS_DIMS,
    SNAPSHOT_CITY,
    WINDOW_DAYS,
    dim_events_calendar,
    dim_fireworks_calendar,
    fetch_events_snapshot,
    parse_events_snapshot,
    score_p4_events,
    upcoming_starts,
)

# Fixed "now" for deterministic windows (2026-09-16, the dig date).
FETCHED_AT = 1789516800  # 2026-09-16 00:00:00 UTC
DAY = 86400


def mkev(start_offset_days, dur_days=2, place="Lauluväljak, Tallinn",
         cats=(14453,), eid=1, city="Tallinn", county="Tallinn"):
    return {"id": eid, "name": "Kontsert %d" % eid,
            "start_time": FETCHED_AT + start_offset_days * DAY,
            "end_time": FETCHED_AT + (start_offset_days + dur_days) * DAY,
            "place_name": place, "city": city, "county": county,
            "categories": list(cats)}


def snap(rows=(), fetched_at=FETCHED_AT, total=None):
    rows = list(rows)
    return {"city": SNAPSHOT_CITY, "fetched_at": fetched_at,
            "total": len(rows) if total is None else total,
            "events": rows}


def listing(city=None):
    return {} if city is None else {"city": city}


def raise_urlopen(*a, **k):
    raise AssertionError("network touched in hermetic test")


# ---------------------------------------------------------------------------
# Contract: published anonymous read path (dig evidence is a code path).
# ---------------------------------------------------------------------------

def test_ingestion_contract_consts():
    assert KULTUURIKAVA_API == "https://www.kultuurikava.ee/api/"
    assert len(KULTUURIKAVA_TOKEN) == 40  # published anonymous token
    assert SNAPSHOT_CITY == "tallinn"
    assert EVENTS_TTL_S == 24 * 3600  # daily pull ticket
    assert WINDOW_DAYS == 30
    assert FETCH_LIMIT == 500
    assert "home-finder" in EVENTS_UA
    assert CALM_BANDS == [(0, 85), (9, 70), (49, 55), (199, 40),
                          (float("inf"), 30)]


# ---------------------------------------------------------------------------
# P4-033 city-grain season pulse.
# ---------------------------------------------------------------------------

def test_calm_month_scores_high_never_100():
    v, reason = dim_events_calendar(listing(), snap())
    assert v == 85
    assert "hinnang" in reason and "rahulik kuu" in reason
    assert "2026-09-16" in reason  # fetched_at stated, not hidden


def test_bands_follow_start_counts():
    assert dim_events_calendar(
        listing(), snap([mkev(1, eid=1)]))[0] == 70
    assert dim_events_calendar(
        listing(), snap([mkev(i, eid=i) for i in range(9)]))[0] == 70
    assert dim_events_calendar(
        listing(), snap([mkev(i, eid=i) for i in range(10)]))[0] == 55
    assert dim_events_calendar(
        listing(), snap([mkev(i % 29 + 1, eid=i) for i in range(50)])
    )[0] == 40
    assert dim_events_calendar(
        listing(), snap([mkev(i % 29 + 1, eid=i) for i in range(200)])
    )[0] == 30  # busy festival month: low, never 0


def test_scored_reason_states_window_and_soonest():
    rows = [mkev(5, eid=1), mkev(20, eid=2)]
    v, reason = dim_events_calendar(listing(), snap(rows))
    assert v == 70
    assert "2 algavat üritust" in reason
    assert "2026-09-21" in reason  # soonest start stated
    assert "dims_p4_sadam" in reason and "dims_p4_kesk" in reason


def test_singular_reason_grammar():
    _, reason = dim_events_calendar(listing(), snap([mkev(3, eid=1)]))
    assert "üks algav üritus" in reason


def test_permanent_exhibition_never_counts_as_pulse():
    # Started years ago, still running: active but not a season start.
    old = mkev(-900, dur_days=2000, eid=7)
    v, reason = dim_events_calendar(listing(), snap([old]))
    assert v == 85 and "rahulik kuu" in reason


def test_window_edges():
    inside = mkev(29, eid=1)  # last included day
    outside = mkev(30, eid=2)  # window end is exclusive
    past = mkev(-1, eid=3)  # already started: not upcoming
    assert upcoming_starts(snap([inside, outside, past])) == [
        FETCHED_AT + 29 * DAY]


def test_malformed_rows_skipped_never_faked():
    rows = [{"id": 1, "name": "x"},  # no start_time
            mkev(2, eid=2),
            {"id": 3, "start_time": "2026-09-20"},  # str: skipped
            {"id": 4, "start_time": True},  # bool: skipped
            {"id": 5, "start_time": -10},  # nonsense: skipped
            "not-a-dict"]
    snapd = {"city": SNAPSHOT_CITY, "fetched_at": FETCHED_AT,
             "total": 99, "events": rows}
    assert upcoming_starts(snapd) == [FETCHED_AT + 2 * DAY]
    v, _ = dim_events_calendar(listing(), snapd)
    assert v == 70  # exactly the one well-formed row


def test_upcoming_starts_unknown_without_snapshot():
    assert upcoming_starts(None) is None
    assert upcoming_starts("nope") is None
    assert upcoming_starts({}) is None
    assert upcoming_starts({"fetched_at": FETCHED_AT}) is None


def test_null_without_snapshot_never_calm():
    for lst in ({}, {"city": "Tallinn"}, None):
        v, reason = dim_events_calendar(lst, None)
        assert v is None and "EI OLE" in reason
        assert "kohapeal" in reason
        assert "dims_p4_sadam" in reason and "dims_p4_kesk" in reason
        assert "mõõdetud" not in reason


def test_non_tallinn_listing_stays_null():
    v, reason = dim_events_calendar({"city": "Tartu"}, snap([mkev(1)]))
    assert v is None and "EI OLE" in reason
    assert "Tartu" in reason


def test_tallinn_spellings_take_calendar():
    rows = [mkev(1, eid=1)]
    for lst in ({}, {"city": "Tallinn"}, {"city": "tallinn"},
                {"city": "Tallinna linn"}, None):
        assert dim_events_calendar(lst, snap(rows))[0] == 70


def test_city_grain_same_value_everywhere_in_tallinn():
    rows = [mkev(i % 10 + 1, eid=i) for i in range(12)]
    a = dim_events_calendar({"asum": "Kesklinn"}, snap(rows))[0]
    b = dim_events_calendar({"asum": "Lasnamäe"}, snap(rows))[0]
    assert (a, b) == (55, 55)  # documented: temporal signal, no venue join


# ---------------------------------------------------------------------------
# P4-047 fireworks leg: documented NULL with dig evidence.
# ---------------------------------------------------------------------------

def test_fireworks_always_none_for_every_input():
    full = snap([mkev(1, eid=1)])
    for lst, snapd in [(listing(), full), (listing(), snap()),
                       (None, None), (listing(), None),
                       ({"city": "Tartu"}, full)]:
        v, _ = dim_fireworks_calendar(lst, snapd)
        assert v is None


def test_fireworks_reason_cites_dig_and_cousins():
    _, reason = dim_fireworks_calendar(listing(), snap([mkev(1)]))
    assert "hinnang" in reason and "EI OLE" in reason
    assert "25 kultuurikategooriat" in reason
    assert "2026-09-16" in reason
    assert "ilutulestiku" in reason
    assert "Päästeamet" in reason
    assert "jaanipäeva" in reason and "aastavahetuse" in reason
    assert "dims_p4_komun" in reason
    assert "dims_p4_kudocs" in reason
    assert "dims_p4_paaste" in reason
    assert "ära feigi" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason


# ---------------------------------------------------------------------------
# Offline readers: envelope parsing, tmp roundtrips.
# ---------------------------------------------------------------------------

def envelope(rows, total=1309):
    return {"code": 1, "message": "Õnnestus",
            "data": {"total": total, "events": rows}}


def live_like_rows():
    return [{"id": 16411674, "name": "Paks Margareeta",
             "start_time": FETCHED_AT + 3 * DAY,
             "end_time": FETCHED_AT + 900 * DAY,
             "place_name": "Paks Margareeta, Tallinn",
             "city": "Tallinn", "county": "Tallinn",
             "categories": [14463],
             "isfree": False, "ticketurl": [], "url": "https://x",
             "extra": "ignored"}]


def test_parse_live_envelope_shape(tmp_path):
    fp = tmp_path / "snap.json"
    fp.write_text(json.dumps(envelope(live_like_rows())), encoding="utf-8")
    snapd = parse_events_snapshot(str(fp))
    assert snapd is not None
    assert snapd["city"] == "tallinn" and snapd["total"] == 1309
    assert len(snapd["events"]) == 1
    row = snapd["events"][0]
    assert (row["start_time"], row["place_name"]) == (
        FETCHED_AT + 3 * DAY, "Paks Margareeta, Tallinn")
    assert row["categories"] == [14463]
    assert isinstance(snapd["fetched_at"], int)


def test_parse_missing_and_broken_is_none(tmp_path):
    assert parse_events_snapshot(str(tmp_path / "absent.json")) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert parse_events_snapshot(str(bad)) is None
    lst = tmp_path / "list.json"
    lst.write_text("[1,2]", encoding="utf-8")
    assert parse_events_snapshot(str(lst)) is None
    nodata = tmp_path / "nodata.json"
    nodata.write_text(json.dumps({"code": 1}), encoding="utf-8")
    assert parse_events_snapshot(str(nodata)) is None


def test_fixture_end_to_end_shape():
    rows = [mkev(2, eid=1), mkev(40, eid=2)]  # one inside, one outside
    out = score_p4_events(listing(), snap(rows))
    assert out == {"events_calendar": 70, "fireworks_calendar": None}
    assert score_p4_events(listing(), None) == {
        "events_calendar": None, "fireworks_calendar": None}


def test_scorer_never_touches_network(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", raise_urlopen)
    full = snap([mkev(1, eid=1)])
    dim_events_calendar(listing(), full)
    dim_events_calendar({}, None)
    dim_fireworks_calendar(listing(), full)
    upcoming_starts(full)
    score_p4_events(listing(), full)


# ---------------------------------------------------------------------------
# Polite fetcher: cache hit = no request; errors cache nothing.
# ---------------------------------------------------------------------------

def test_fetch_cache_hit_performs_no_request(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", raise_urlopen)
    dest = tmp_path / CACHE_FILENAME
    dest.write_text("{}", encoding="utf-8")
    assert fetch_events_snapshot(str(tmp_path)) == str(dest)


def test_fetch_transport_error_caches_nothing(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise OSError("network down")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert fetch_events_snapshot(str(tmp_path)) is None
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
    assert fetch_events_snapshot(str(tmp_path)) is None
    assert not (tmp_path / CACHE_FILENAME).exists()


def test_fetch_stores_json_envelope(tmp_path, monkeypatch):
    body = json.dumps(envelope(live_like_rows(), total=1)).encode()

    class Resp:
        status = 200
        headers = {"Content-Type": "application/json"}

        def read(self):
            return body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    seen = {}

    def fake(req, **k):
        seen["url"] = req.full_url
        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    got = fetch_events_snapshot(str(tmp_path))
    assert got == str(tmp_path / CACHE_FILENAME)
    assert "do=events" in seen["url"] and "city=tallinn" in seen["url"]
    snapd = parse_events_snapshot(got)
    assert snapd is not None and len(snapd["events"]) == 1


# ---------------------------------------------------------------------------
# Registry + aggregator.
# ---------------------------------------------------------------------------

def test_registry_and_aggregator_cover_both():
    assert [k for k, _, _ in P4_EVENTS_DIMS] == [
        "events_calendar", "fireworks_calendar"]
    assert [p for _, p, _ in P4_EVENTS_DIMS] == ["P4-033", "P4-047"]
    assert len({fn for _, _, fn in P4_EVENTS_DIMS}) == 2
    full = snap([mkev(1, eid=1)])
    assert score_p4_events(listing(), full) == {
        "events_calendar": 70, "fireworks_calendar": None}
    assert score_p4_events(None, None) == {
        "events_calendar": None, "fireworks_calendar": None}
    assert events.P4_EVENTS_DIMS is P4_EVENTS_DIMS
