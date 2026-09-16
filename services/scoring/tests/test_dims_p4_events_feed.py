"""P4 events-feed dims (issue #540): hermetic tests.

No network: fetch_events_feed is never called here (its contract --
single polite GET, file cache, TTL, transport errors raise -- is
covered via the pure cache_is_fresh helper). Parsing/aggregation run
on SYNTHETIC feed-shape JSON (real 21-key layout observed 2026-09-16,
invented venues only -- never a real pull). Bands, the joined-0
calm-vs-NULL distinction, and the horrors-leg NULL are pinned.
"""

import json

import dims_p4_events_feed as feed
from dims_p4_events_feed import (
    EVENTS_TTL_DAYS,
    P4_EVENTS_FEED_DIMS,
    VENUE_ADDRESSES,
    build_venue_calendar,
    cache_is_fresh,
    dim_culture_evenings,
    dim_horrors_crowds,
    normalise_venue,
    parse_event_date,
    parse_events_feed,
    score_p4_events_feed,
)

FEED_ITEM = {
    "id": 1, "name": "Etendus", "name_en": "Show",
    "date": "2026/09/16 19:00:00 +0300",
    "buy_ticket_url": "https://example.invalid/buy",
    "info_url": "https://example.invalid/info",
    "organizer_name": "Testiteater", "event_id": 9,
    "updated_at": "2026/08/27 01:17:46 +0300",
    "category": "Teater", "free_seat_count": 80,
    "full_description": "<p>...</p>", "full_description_plain": "...",
    "image_url": "", "thumb_image_url": "", "state": "on_sale",
    "location_venue_id": "7", "location_venue_name": "Testi Maja",
    "location_venue_hall_name": "suur saal",
    "location_address_address": "Testi tn 1",
    "location_address_city": "Tallinn",
}


def _item(**over):
    item = dict(FEED_ITEM)
    item.update(over)
    return item


def test_parse_keeps_real_shape_and_skips_venueless():
    text = json.dumps([_item(),
                       _item(location_venue_name="  ",
                             date="2026/09/17 12:00:00 +0300"),
                       _item(location_venue_name="Kino",
                             date="not-a-date"),
                       {"id": "junk"},
                       _item(location_venue_name="Matinee",
                             date="2026/09/17 14:00:00 +0300")])
    rows = parse_events_feed(text)
    assert len(rows) == 3  # venueless + non-dict skipped
    assert rows[0]["venue_key"] == "testi maja"
    assert rows[0]["evening"] is True
    assert rows[1]["evening"] is None  # undated: no day claim
    assert rows[2]["evening"] is False  # matinee
    assert parse_events_feed("not json") == []
    assert parse_events_feed('{"a": 1}') == []


def test_parse_event_date_honours_offset():
    moment = parse_event_date("2026/09/16 19:00:00 +0300")
    assert moment is not None and moment.hour == 19
    assert parse_event_date("2026-09-16") is None
    assert parse_event_date(None) is None  # type: ignore[arg-type]


def test_normalise_venue_merges_only_observed_spellings():
    # Dupes observed 2026-09-16 merge ...
    assert normalise_venue("Eesti Draamateater.") == "eesti draamateater"
    assert normalise_venue("Tallinn, Mere Kultuurikeskus") == \
        "mere kultuurikeskus"
    assert normalise_venue("Mere Kultuurikeskus, Tallinn") == \
        "mere kultuurikeskus"
    assert normalise_venue("Tallinn, Mere kultuurikeskus") == \
        "mere kultuurikeskus"
    # ... anything else stays split (no fuzzy merge).
    assert normalise_venue("Kumu Auditoorium, Tallinn") == \
        "kumu auditoorium"
    assert normalise_venue("Kumu Auditoorium") == "kumu auditoorium"
    assert normalise_venue("Theatrumi saal") != "kumu auditoorium"


def test_calendar_counts_distinct_days_not_rows():
    text = json.dumps([
        _item(date="2026/09/16 19:00:00 +0300"),   # day 1 eve
        _item(date="2026/09/16 14:00:00 +0300"),   # day 1 matinee
        _item(date="2026/09/17 20:00:00 +0300"),   # day 2 eve
        _item(date="not-a-date"),                  # no day claim
    ])
    calendar = build_venue_calendar(parse_events_feed(text))
    cell = calendar["testi maja"]
    assert cell["event_days"] == 2
    assert cell["evening_days"] == 2
    assert cell["events"] == 4
    assert cell["categories"] == ["Teater"]


def test_bands_and_joined_zero_vs_null():
    calendar = {
        "vaikne": {"event_days": 0, "evening_days": 0, "events": 0,
                   "categories": []},
        "rahulik": {"event_days": 5, "evening_days": 4, "events": 5,
                    "categories": ["Teater"]},
        "tihe": {"event_days": 14, "evening_days": 14, "events": 14,
                 "categories": ["Teater"]},
    }
    v, reason = dim_culture_evenings("vaikne", calendar)
    assert v == 80  # joined 0 is real calm, not NULL
    assert "30 paeva aknas" in reason  # window named (annual sample)
    assert "tasuta" in reason  # ticketed-only legend marker
    assert dim_culture_evenings("rahulik", calendar)[0] == 60
    assert dim_culture_evenings("tihe", calendar)[0] == 40
    # Missing join stays NULL (p4_trans precedent).
    for key, cal in [(None, calendar), ("tundmatu", calendar),
                     ("vaikne", None), ("vaikne", {})]:
        v, reason = dim_culture_evenings(key, cal)
        assert v is None
        assert "EI OLE" in reason


def test_horrors_leg_is_always_null():
    calendar = {"lauluväljak": {"event_days": 30, "evening_days": 30,
                                "events": 30, "categories": ["Festival"]}}
    for key, cal in [("lauluväljak", calendar), (None, None),
                     (None, calendar)]:
        v, reason = dim_horrors_crowds(key, cal)
        assert v is None
        assert "EI OLE" in reason
        assert "dims_p4_trans" in reason  # sibling leg named


def test_venue_table_has_no_guessed_coords():
    assert len(VENUE_ADDRESSES) >= 8  # Tallinn physical venues observed
    for key, row in VENUE_ADDRESSES.items():
        assert row["lat"] is None and row["lon"] is None  # never guessed
        assert row["address"]  # feed's own address string kept
        assert key == normalise_venue(key)  # keys pre-normalised


def test_registry_and_rollup():
    assert set(P4_EVENTS_FEED_DIMS) == {"culture_evenings",
                                       "horrors_crowds"}
    assert P4_EVENTS_FEED_DIMS["culture_evenings"][1] is dim_culture_evenings
    assert P4_EVENTS_FEED_DIMS["horrors_crowds"][1] is dim_horrors_crowds
    assert feed.P4_EVENTS_FEED_DIMS is P4_EVENTS_FEED_DIMS
    calendar = {"v": {"event_days": 2, "evening_days": 2, "events": 2,
                      "categories": []}}
    dims, reasons = score_p4_events_feed("v", calendar)
    assert dims == {"culture_evenings": 60, "horrors_crowds": None}
    assert len(reasons) == 1  # NULL dims contribute no reasons


def test_annual_ttl_and_cache(tmp_path):
    assert EVENTS_TTL_DAYS == 365  # annual harvest is plenty
    assert cache_is_fresh(str(tmp_path / "missing.json")) is False
