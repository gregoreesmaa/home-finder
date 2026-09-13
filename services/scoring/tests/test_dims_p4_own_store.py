"""P4 own-store dims (issues #243 demo + #327 coverage): hermetic tests.

No network: ingestion is pure dict-folding and every scorer reads only the
snapshot record passed in, so all tests run on fixture dicts. Computed dims
(P4-001/022/028/043/046) are pinned to exact scores on fixtures; NULL dims
are pinned to None + Estonian honesty markers (hinnang + EI OLE + missing
source + buyer check) on every input including the empty record.
"""

import dims_p4_own_store as own
from dims_p4_own_store import (
    OWN_STORE_DIMS,
    dim_arrival_sequence,
    dim_bargaining_margin,
    dim_broker_track,
    dim_demand_exhaust,
    dim_dread_removal,
    dim_glimpse,
    dim_heatpump_hum,
    dim_ku_loan,
    dim_micro_comps,
    dim_number_arbitrage,
    dim_overheating,
    dim_permit_existence,
    dim_photo_forensics,
    dim_price_history_dom,
    dim_rent_reality,
    dim_street_imagery,
    dim_taxi_guest,
    dim_turnover_wave,
    dim_woodburn_zone,
    dim_zero_consumption,
    ingest_snapshot,
    merge_sightings,
    score_own_store,
)

ASOF = "2026-09-12"


def snap(**overrides):
    """Tallinn fixture snapshot: kv.ee ad, 12 days of DOM, firm price."""
    base = {
        "id": "12345",
        "source": "kv.ee",
        "source_url": "https://www.kv.ee/12345",
        "address": "Tallinn, Kalamaja, Soo 12-7",
        "price": 250000,
        "area_m2": 55.0,
        "rooms": 3,
        "floor": 4,
        "first_seen": "2026-08-31",
        "last_seen": ASOF,
        "price_history": [{"date": "2026-08-31", "price": 250000}],
        "sources_seen": ["kv.ee"],
        "image_hash": "aa11bb22",
        "photo_count": 12,
        "views": 240,
        "updates": 1,
        "broker": "Uus Maa",
        "text": "Valge korter Kalamajas, rõdu ja parkimiskoht.",
        "relist": False,
        "asof": ASOF,
    }
    base.update(overrides)
    return base


def card(**overrides):
    """One day's polite portal card (ingestion input, not a snapshot)."""
    base = {"id": "12345", "source": "kv.ee",
            "address": "Tallinn, Kalamaja, Soo 12-7", "price": 250000}
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Demo ingestion: first_seen stamping, price-change history, cross-portal merge.
# ---------------------------------------------------------------------------

def test_ingestion_first_sight_stamps_first_seen_and_history():
    store = {}
    entry = ingest_snapshot(store, card(), "2026-08-31")
    assert entry["first_seen"] == "2026-08-31"
    assert entry["last_seen"] == "2026-08-31"
    assert entry["price_history"] == [{"date": "2026-08-31", "price": 250000}]


def test_ingestion_same_price_leaves_history_untouched():
    store = {}
    ingest_snapshot(store, card(), "2026-08-31")
    entry = ingest_snapshot(store, card(), "2026-09-01")
    assert entry["first_seen"] == "2026-08-31"
    assert entry["last_seen"] == "2026-09-01"
    assert entry["price_history"] == [{"date": "2026-08-31", "price": 250000}]


def test_ingestion_price_change_appends_history_point():
    store = {}
    ingest_snapshot(store, card(), "2026-08-31")
    entry = ingest_snapshot(store, card(price=240000), "2026-09-05")
    assert entry["price_history"] == [
        {"date": "2026-08-31", "price": 250000},
        {"date": "2026-09-05", "price": 240000},
    ]


def test_merge_unions_sources_and_histories_deterministically():
    kv = {"id": "1", "source": "kv.ee", "address": "Tallinn, Soo 12",
          "first_seen": "2026-08-31", "last_seen": "2026-09-10",
          "price_history": [{"date": "2026-08-31", "price": 250000}],
          "sources_seen": ["kv.ee"], "image_hash": "aa11", "broker": "Uus Maa"}
    c24 = {"id": "9", "source": "city24.ee", "address": "Tallinn, Soo 12",
           "first_seen": "2026-09-02", "last_seen": "2026-09-12",
           "price_history": [{"date": "2026-09-02", "price": 240000}],
           "sources_seen": ["city24.ee"], "views": 500}
    merged = merge_sightings([c24, kv])
    assert merged["sources_seen"] == ["city24.ee", "kv.ee"]
    assert merged["first_seen"] == "2026-08-31"
    assert merged["last_seen"] == "2026-09-12"
    assert merged["price_history"] == [
        {"date": "2026-08-31", "price": 250000},
        {"date": "2026-09-02", "price": 240000},
    ]
    assert merged["image_hash"] == "aa11"  # first-non-None in (source, id) order
    assert merged["views"] == 500
    assert merge_sightings([kv, c24]) == merged  # order-independent


# ---------------------------------------------------------------------------
# P4-001 demo: DOM + drop mapping on fixtures.
# ---------------------------------------------------------------------------

def test_p4001_fresh_firm_price_scores_40():
    v, reason = dim_price_history_dom(snap())  # DOM 12, no drops
    assert v == 40
    assert "hinnang" in reason


def test_p4001_single_drop_scores_65():
    s = snap(price=240000,
             price_history=[{"date": "2026-08-31", "price": 250000},
                            {"date": "2026-09-05", "price": 240000}])
    v, _ = dim_price_history_dom(s)
    assert v == 65


def test_p4001_two_drops_scores_80():
    s = snap(price=230000,
             price_history=[{"date": "2026-08-31", "price": 250000},
                            {"date": "2026-09-03", "price": 240000},
                            {"date": "2026-09-08", "price": 230000}])
    v, reason = dim_price_history_dom(s)
    assert v == 80
    assert "steal" in reason


def test_p4001_big_single_cut_scores_80():
    s = snap(price=220000,
             price_history=[{"date": "2026-08-31", "price": 250000}])
    v, _ = dim_price_history_dom(s)  # 12% peak-to-current cut
    assert v == 80


def test_p4001_stale_thresholds_without_drops():
    v, _ = dim_price_history_dom(snap(first_seen="2026-08-01"))  # DOM 42
    assert v == 55
    v, _ = dim_price_history_dom(snap(first_seen="2026-06-01"))  # DOM 103
    assert v == 65


def test_p4001_missing_first_seen_is_none_with_estonian_reason():
    v, reason = dim_price_history_dom(snap(first_seen=None))
    assert v is None
    assert "EI OLE" in reason and "hinnang" in reason
    v, _ = dim_price_history_dom({})
    assert v is None
    v, reason = dim_price_history_dom(snap(first_seen="not-a-date"))
    assert v is None
    assert "EI OLE" in reason


def test_p4001_asof_falls_back_to_last_seen():
    s = snap(asof=None)  # last_seen 2026-09-12 still gives DOM 12
    v, _ = dim_price_history_dom(s)
    assert v == 40
    v, reason = dim_price_history_dom(snap(asof=None, last_seen=None))
    assert v is None
    assert "EI OLE" in reason


# ---------------------------------------------------------------------------
# Computed coverage: P4-022 / P4-028 / P4-043 / P4-046 on fixtures.
# ---------------------------------------------------------------------------

def test_p4022_cross_portal_duplicate_flags_30():
    v, reason = dim_photo_forensics(
        snap(sources_seen=["city24.ee", "kv.ee"]))
    assert v == 30
    assert "hinnang" in reason


def test_p4022_unique_trail_scores_75_and_missing_hash_is_none():
    v, _ = dim_photo_forensics(snap())
    assert v == 75
    v, reason = dim_photo_forensics(snap(image_hash=None))
    assert v is None
    assert "EI OLE" in reason and "hinnang" in reason


def test_p4022_zero_photos_scores_45():
    v, reason = dim_photo_forensics(snap(photo_count=0))
    assert v == 45
    assert "hinnang" in reason


def test_p4028_hot_listing_scores_30():
    v, reason = dim_demand_exhaust(snap(views=900))  # 75/day over DOM 12
    assert v == 30
    assert "hinnang" in reason


def test_p4028_stale_listing_scores_75():
    v, _ = dim_demand_exhaust(  # 2/day over DOM 42
        snap(views=84, first_seen="2026-08-01"))
    assert v == 75


def test_p4028_reposted_listing_scores_65_and_quiet_scores_55():
    v, _ = dim_demand_exhaust(snap(views=None, updates=4))
    assert v == 65
    v, _ = dim_demand_exhaust(snap(views=None, updates=1))
    assert v == 55


def test_p4028_missing_counters_is_none():
    v, reason = dim_demand_exhaust(snap(views=None, updates=None))
    assert v is None
    assert "EI OLE" in reason and "hinnang" in reason


def test_p4043_floor_13_scores_70_others_none():
    v, reason = dim_number_arbitrage(snap(floor=13))
    assert v == 70
    assert "hinnang" in reason and "garantii" in reason
    v, _ = dim_number_arbitrage(snap(floor="13"))  # card strings accepted
    assert v == 70
    v, reason = dim_number_arbitrage(snap(floor=4))
    assert v is None
    assert "EI OLE" in reason
    v, _ = dim_number_arbitrage(snap(floor=None))
    assert v is None


def test_p4046_redundancy_keywords_score_stepwise():
    v, reason = dim_dread_removal(
        snap(text="Kaminaga elutuba, puurkaev hoovis, varuväljapääs tagant."))
    assert v == 85
    assert "hinnang" in reason and "kuulutuse väide" in reason
    v, _ = dim_dread_removal(snap(text="Kaminaga elutuba, kaugküte."))
    assert v == 55
    v, _ = dim_dread_removal(snap())  # no keywords in base text
    assert v == 40


def test_p4046_missing_text_is_none():
    v, reason = dim_dread_removal(snap(text=None))
    assert v is None
    assert "EI OLE" in reason and "hinnang" in reason


# ---------------------------------------------------------------------------
# NULL coverage: every other param stays None with an honest Estonian reason.
# ---------------------------------------------------------------------------

NULL_FNS = [
    dim_micro_comps,
    dim_rent_reality,
    dim_permit_existence,
    dim_ku_loan,
    dim_broker_track,
    dim_street_imagery,
    dim_overheating,
    dim_bargaining_margin,
    dim_arrival_sequence,
    dim_glimpse,
    dim_taxi_guest,
    dim_zero_consumption,
    dim_turnover_wave,
    dim_heatpump_hum,
    dim_woodburn_zone,
]

EXPECTED_SOURCES = {
    "dim_micro_comps": "Maa-ameti tehingute",
    "dim_rent_reality": "KV üüri-mediaane",
    "dim_permit_existence": "EHR",
    "dim_ku_loan": "e-Äriregister",
    "dim_broker_track": "ristportaali",
    "dim_street_imagery": "Mapillary",
    "dim_overheating": "EHR",
    "dim_bargaining_margin": "Maa-ameti",
    "dim_arrival_sequence": "Mapillary",
    "dim_glimpse": "LiDAR",
    "dim_taxi_guest": "ADS-proovi",
    "dim_zero_consumption": "Elektrilevi",
    "dim_turnover_wave": "tehingu-",
    "dim_heatpump_hum": "EHR",
    "dim_woodburn_zone": "EHR",
}


def test_all_null_dims_none_for_every_input():
    for fn in NULL_FNS:
        for s in (snap(), snap(broker=None, text=None, views=None,
                               image_hash=None, floor=None), {}):
            v, _ = fn(s)
            assert v is None, fn.__name__


def test_all_null_reasons_carry_honesty_markers_and_missing_source():
    for fn in NULL_FNS:
        _, reason = fn(snap())
        assert "hinnang" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__
        assert EXPECTED_SOURCES[fn.__name__] in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason
        assert "ära feigi" in reason or "kontrolli" in reason or "küsi" in reason


def test_p4007_notes_remondifond_mention_without_scoring_it():
    _, plain = dim_ku_loan(snap())
    assert "eelarvet" in plain
    _, noted = dim_ku_loan(snap(text="Remondifond 50 €/kuu, küte kaugküte."))
    assert "mainib remondifondi" in noted
    assert "ära feigi tekstist finantsi" in noted


def test_p4021_reason_varies_with_broker_known_vs_unknown():
    _, known = dim_broker_track(snap())
    assert "Uus Maa" in known and "koguneb" in known
    _, unknown = dim_broker_track(snap(broker=None))
    assert "maakleritki" in unknown


def test_p4052_notes_observed_relist_without_scoring_it():
    _, waiting = dim_turnover_wave(snap(relist=True))
    assert "relist-signaal on näha" in waiting
    _, missing = dim_turnover_wave(snap())
    assert "puudub" in missing


def test_p4057_distinguishes_own_unit_from_neighbour_hum():
    _, own_unit = dim_heatpump_hum(snap(text="Küte: õhksoojuspump, ahi toaks."))
    assert "oma seade" in own_unit
    _, neither = dim_heatpump_hum(snap())
    assert "üksi müra ei tõesta" in neither


def test_p4059_notes_stove_asset_without_zoning_it():
    _, noted = dim_woodburn_zone(snap(text="Korteris ahi ja puuküte."))
    assert "vara-inventuur" in noted
    _, plain = dim_woodburn_zone(snap())
    assert "üksi tsooni ei määra" in plain


def test_p4038_names_p4001_to_avoid_double_scoring():
    _, reason = dim_bargaining_margin(snap())
    assert "P4-001" in reason and "topelt" in reason


def test_p4051_is_a_privacy_hard_null():
    _, reason = dim_zero_consumption(snap())
    assert "privaatsuspiir" in reason and "hex" in reason
    _, empty = dim_zero_consumption({})
    assert "privaatsuspiir" in empty


# ---------------------------------------------------------------------------
# Registry + aggregator: all twenty params, one entry point.
# ---------------------------------------------------------------------------

EXPECTED_KEYS = [
    "price_dom", "micro_comps", "rent_reality", "permit_existence", "ku_loan",
    "broker_track", "photo_forensics", "demand_exhaust", "street_imagery",
    "overheating", "bargaining_margin", "arrival_sequence", "glimpse",
    "number_arbitrage", "dread_removal", "taxi_guest", "zero_consumption",
    "turnover_wave", "heatpump_hum", "woodburn_zone",
]

EXPECTED_PNUMS = [
    "P4-001", "P4-002", "P4-003", "P4-005", "P4-007", "P4-021", "P4-022",
    "P4-028", "P4-029", "P4-034", "P4-038", "P4-040", "P4-041", "P4-043",
    "P4-046", "P4-049", "P4-051", "P4-052", "P4-057", "P4-059",
]


def test_registry_and_aggregator_cover_all_twenty():
    assert [k for k, _, _ in OWN_STORE_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in OWN_STORE_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in OWN_STORE_DIMS}) == 20
    assert own.OWN_STORE_DIMS is OWN_STORE_DIMS


def test_aggregator_computes_demo_dims_and_nulls_the_rest():
    out = score_own_store(snap())
    assert out["price_dom"] == 40
    assert out["photo_forensics"] == 75
    assert out["demand_exhaust"] == 55  # 20/day mid-range
    assert out["number_arbitrage"] is None  # floor 4, no residuals
    assert out["dread_removal"] == 40  # text present, no keywords
    for key in ("micro_comps", "rent_reality", "permit_existence", "ku_loan",
                "broker_track", "street_imagery", "overheating",
                "bargaining_margin", "arrival_sequence", "glimpse",
                "taxi_guest", "zero_consumption", "turnover_wave",
                "heatpump_hum", "woodburn_zone"):
        assert out[key] is None, key
    assert score_own_store({})["price_dom"] is None
    assert score_own_store({})["dread_removal"] is None


def test_aggregator_scores_full_featured_snapshot():
    s = snap(floor=13, sources_seen=["city24.ee", "kv.ee"],
             text="Kamin, puurkaev hoovis, varuväljapääs tagant.")
    out = score_own_store(s)
    assert out["photo_forensics"] == 30
    assert out["number_arbitrage"] == 70
    assert out["dread_removal"] == 85
