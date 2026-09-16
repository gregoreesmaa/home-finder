"""P4 riigimaa dims (issue #544): hermetic tests.

No network: all fixtures are hand-built (shapes mirror the 2026-09-16
live bytes -- Avaldatud status, "17.09.2026 kell 10:00" deadline shape,
KATRI attribute names -- but every value is invented). Tests pin the
assurance bands + cap, the flat dated auction flag, expiry handling
(expired/unknown auctions never score), NULL-outside, the 50 m adjacency
rule, the forest heuristic, deadline parsing, and registry/aggregator
coverage. The module itself makes no network calls (pinned by source
inspection).
"""

import datetime as _dt
import inspect

import dims_p4_riigimaa as riigimaa
from dims_p4_riigimaa import (
    ADJACENCY_M,
    AUCTION_FLAG,
    FOREST_ASSURANCE,
    OTHER_ASSURANCE,
    P4_RIIGIMAA_DIMS,
    dim_auction_warning,
    dim_state_land_adjacency,
    parse_offer_deadline,
    score_p4_riigimaa,
)

TODAY = _dt.date(2026, 9, 16)

# Listing at Telliskivi; state forest parcel edge ~30 m east; auction
# parcel overlapping the listing; far auction past the buffer.
FOREST_PARCEL = {
    "polygons": [[[24.7516, 59.4398], [24.7526, 59.4398],
                   [24.7526, 59.4408], [24.7516, 59.4408]]],
    "katastritunnus": "78408:501:0001",
    "vara_liik": "metsamaa",
    "riigivara_valitseja": "RMK",
    "nimetus": "Riigimets Telliskivi taga",
}
FIELD_PARCEL = {
    "polygons": [[[24.7540, 59.4390], [24.7545, 59.4390],
                   [24.7545, 59.4395], [24.7540, 59.4395]]],
    "katastritunnus": "78408:501:0002",
    "vara_liik": "haritav maa",
    "riigivara_valitseja": "Maa- ja Ruumiamet",
    "nimetus": "Riigipõld",
}
ACTIVE_AUCTION = {
    "polygons": [[[24.7510, 59.4395], [24.7520, 59.4395],
                   [24.7520, 59.4405], [24.7510, 59.4405]]],
    "offer_deadline": "17.10.2026 kell 10:00",
    "status": "Avaldatud",
    "purpose": "Müük",
    "obj_id": 3244621,
    "url": "https://riigimaaoksjon.ee/public/auction/1/object/3244621",
}
RENT_AUCTION = dict(ACTIVE_AUCTION, purpose="Rent",
                    obj_id=999, offer_deadline="29.09.2026 kell 11:00")
EXPIRED_AUCTION = dict(ACTIVE_AUCTION, offer_deadline="17.08.2026 kell 10:00")
SOLD_AUCTION = dict(ACTIVE_AUCTION, status="Müüdud")
MYSTERY_AUCTION = dict(ACTIVE_AUCTION, offer_deadline="peagi")
# ~30 m from the forest parcel's west edge, inside the auction polygon.
LISTING = (59.4400, 24.7515)
FAR = (59.4500, 24.8000)


def test_forest_neighbour_scores_capped_assurance():
    v, reason = dim_state_land_adjacency(LISTING, [FOREST_PARCEL])
    assert v == FOREST_ASSURANCE == 70
    assert "riigimets" in reason
    assert "78408:501:0001" in reason
    assert "lagi 70" in reason
    assert "omand võib muutuda" in reason
    assert "CC BY 4.0" in reason


def test_other_state_land_scores_lower_assurance():
    v, reason = dim_state_land_adjacency((59.4392, 24.7542), [FIELD_PARCEL])
    assert v == OTHER_ASSURANCE == 60
    assert "muu riigimaa" in reason


def test_outside_buffer_is_unknown_never_clean():
    v, reason = dim_state_land_adjacency(FAR, [FOREST_PARCEL, FIELD_PARCEL])
    assert v is None
    assert "<= 50 m" in reason
    assert "EI OLE teada" in reason
    assert "ära feigi" in reason


def test_missing_layer_and_bad_origin_are_honest_nulls():
    v, r1 = dim_state_land_adjacency(LISTING, None)
    assert v is None and "EI OLE KATRI" in r1
    v, r2 = dim_state_land_adjacency(LISTING, [])
    assert v is None and "EI OLE laetud" in r2
    v, r3 = dim_state_land_adjacency(None, [FOREST_PARCEL])
    assert v is None


def test_active_auction_flags_flat_with_date_and_id():
    v, reason = dim_auction_warning(LISTING, [ACTIVE_AUCTION], TODAY)
    assert v == AUCTION_FLAG == 40
    assert "2026-10-17" in reason
    assert "3244621" in reason
    assert "Müük" in reason
    assert "riigimaaoksjon.ee" in reason
    assert "KOV" in reason


def test_rent_auction_also_flags_with_purpose_named():
    v, reason = dim_auction_warning(LISTING, [RENT_AUCTION], TODAY)
    assert v == 40
    assert "Rent" in reason


def test_expired_sold_and_unknown_auctions_never_score():
    for auc in (EXPIRED_AUCTION, SOLD_AUCTION, MYSTERY_AUCTION):
        v, reason = dim_auction_warning(LISTING, [auc], TODAY)
        assert v is None, auc
        assert "EI OLE teada" in reason
    v, reason = dim_auction_warning(LISTING, [EXPIRED_AUCTION,
                                              SOLD_AUCTION], TODAY)
    assert v is None
    assert "2 aegunud/tundmatu oksjonit eiratud" in reason


def test_deadline_on_today_still_counts_expired_yesterday_not():
    today_auc = dict(ACTIVE_AUCTION, offer_deadline="16.09.2026 kell 10:00")
    v, _ = dim_auction_warning(LISTING, [today_auc], TODAY)
    assert v == 40
    yday_auc = dict(ACTIVE_AUCTION, offer_deadline="15.09.2026 kell 10:00")
    v, _ = dim_auction_warning(LISTING, [yday_auc], TODAY)
    assert v is None


def test_no_active_auction_nearby_is_unknown():
    v, reason = dim_auction_warning(FAR, [ACTIVE_AUCTION], TODAY)
    assert v is None
    assert "EI OLE teada" in reason


def test_deadline_parser_shapes():
    assert parse_offer_deadline("17.09.2026 kell 10:00") == _dt.date(2026, 9, 17)
    assert parse_offer_deadline("1.1.2027 kell 9:00") == _dt.date(2027, 1, 1)
    assert parse_offer_deadline("peagi") is None
    assert parse_offer_deadline(None) is None
    assert parse_offer_deadline("99.99.2026 kell 10:00") is None


def test_adjacency_rule_documented_constant():
    assert ADJACENCY_M == 50.0


def test_module_adds_no_network_calls():
    src = inspect.getsource(riigimaa)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_registry_and_aggregator():
    assert [k for k, _ in P4_RIIGIMAA_DIMS] == [
        "state_land_adjacency", "auction_warning"]
    assert score_p4_riigimaa(LISTING, [FOREST_PARCEL],
                             [ACTIVE_AUCTION], TODAY) == {
        "state_land_adjacency": 70, "auction_warning": 40}
    assert score_p4_riigimaa(FAR, [FOREST_PARCEL],
                             [ACTIVE_AUCTION], TODAY) == {
        "state_land_adjacency": None, "auction_warning": None}
    assert score_p4_riigimaa(None, None, None, TODAY) == {
        "state_land_adjacency": None, "auction_warning": None}
