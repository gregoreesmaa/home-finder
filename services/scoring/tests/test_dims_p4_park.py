"""P4 park dims (issues #279 demo + #353 coverage): hermetic tests.

No network: every fixture is a synthetic in-memory parcel/parking dict
(invented zone keys, never scraped data). fetch_park is covered on its
cache-hit path (stub opener that raises) and its error paths (None, no
file written); freshness uses tmp_path. The live probes are manual DoD
evidence (pasted in the PR + docs/p4_park.md), not unit runs.
"""

import dims_p4_park as p4
from dims_p4_park import (
    EXPOSURE_BAND,
    GUEST_BAND,
    P4_PARK_DIMS,
    REGIME_BAND,
    TTL_PARK_DAYS,
    ZONES,
    cache_path,
    default_snapshot,
    dim_guest_parking,
    dim_parking_regime,
    dim_zone_cost,
    fetch_park,
    is_fresh,
    normalise_zone,
    parcel_id,
    score_p4_park,
    zone_facts,
)

KID = "78401:101:0123"


def parcel(**kw):
    base = {"katastritunnus": KID}
    base.update(kw)
    return base


def parking(tsoon):
    return {"tsoon": tsoon}


FREE = parking(None)
KESKLINN = parking("kesklinn")
SUDALINN = parking("südalinn")
VANALINN = parking("vanalinn")
PIRITA = parking("pirita")

ALL_FNS = (dim_parking_regime, dim_zone_cost, dim_guest_parking)


# -- helpers ---------------------------------------------------------------

def test_parcel_id_trims_and_rejects_blank():
    assert parcel_id(parcel(katastritunnus=" 78401:101:0123 ")) == KID
    assert parcel_id(None) is None
    assert parcel_id({}) is None
    assert parcel_id(parcel(katastritunnus="   ")) is None


def test_normalise_zone_case_and_whitespace():
    assert normalise_zone("  Kesklinn ") == "kesklinn"
    assert normalise_zone("VANALINN") == "vanalinn"
    assert normalise_zone(None) is None
    assert normalise_zone("   ") == "teadmata"


def test_snapshot_zones_match_live_four():
    snap = default_snapshot()
    assert snap["fetched"] == "2026-09-13"
    assert len(snap["sources"]) == 2
    assert set(snap["zones"]) == set(ZONES) == {
        "kesklinn", "südalinn", "vanalinn", "pirita"}


def test_snapshot_zone_facts_carry_verified_fees():
    snap = default_snapshot()
    assert snap["zones"]["vanalinn"]["tasu_min"] == "0,10 EUR/min"
    assert snap["zones"]["südalinn"]["tasu_min"] == "0,08 EUR/min"
    assert snap["zones"]["kesklinn"]["tasu_min"] == "0,025 EUR/min"
    assert snap["zones"]["pirita"]["tasu_min"] == "0,01 EUR/min"
    assert "24/7" in snap["zones"]["südalinn"]["aeg"]
    assert "P tasuta" in snap["zones"]["kesklinn"]["aeg"]


def test_zone_facts_free_area_and_unknown():
    snap = default_snapshot()
    free = zone_facts(snap, None)
    assert free["tasu_min"] == "0 EUR/min"
    assert zone_facts(snap, "kesklinn")["perioodipilet"] == "150 EUR"
    assert zone_facts(snap, "tsoon-a") is None
    assert zone_facts(None, "kesklinn") is None
    assert zone_facts({}, "kesklinn") is None


def test_bands_follow_verified_fee_ladder():
    by_fee = ["vanalinn", "südalinn", "kesklinn", "pirita", None]
    for band in (REGIME_BAND, EXPOSURE_BAND):
        assert [band[z] for z in by_fee] == sorted(
            band[z] for z in by_fee), band
    # Guest band orders by Saturday-19:00 COST, not the fee ladder:
    # kesklinn is free at Sat 19:00 (paid only till 15:00) while Pirita
    # is seasonally paid then — the documented kesklinn/pirita inversion.
    by_sat19 = ["vanalinn", "südalinn", "pirita", "kesklinn", None]
    assert [GUEST_BAND[z] for z in by_sat19] == sorted(
        GUEST_BAND[z] for z in by_sat19)


# -- P4-013 demo -----------------------------------------------------------

def test_p4_013_bands_per_zone():
    assert dim_parking_regime(parcel(), VANALINN)[0] == 35
    assert dim_parking_regime(parcel(), SUDALINN)[0] == 45
    assert dim_parking_regime(parcel(), KESKLINN)[0] == 60
    assert dim_parking_regime(parcel(), PIRITA)[0] == 75
    assert dim_parking_regime(parcel(), FREE)[0] == 80


def test_p4_013_reasons_carry_fee_and_hours():
    _, reason = dim_parking_regime(parcel(), SUDALINN)
    assert "hinnang" in reason
    assert "0,08 EUR/min" in reason and "24/7" in reason
    assert "250 EUR" in reason
    _, reason = dim_parking_regime(parcel(), FREE)
    assert "tasuta ala" in reason


def test_p4_013_null_without_parcel_or_zone_leg():
    for bad_parcel in (None, {}, parcel(katastritunnus=None)):
        v, reason = dim_parking_regime(bad_parcel, KESKLINN)
        assert v is None
        assert "EI OLE" in reason and "Maainfo" in reason
    for bad_parking in (None, {}, {"muu": 1}, parking("teadmata"),
                        parking("   ")):
        v, reason = dim_parking_regime(parcel(), bad_parking)
        assert v is None, repr(bad_parking)
        assert "EI OLE" in reason and "kaardiotsing" in reason


def test_p4_013_unknown_zone_value_is_null():
    v, reason = dim_parking_regime(parcel(), parking("tsoon-A"))
    assert v is None
    assert "EI OLE" in reason and "tsooniotsing" in reason


# -- P4-037 coverage --------------------------------------------------------

def test_p4_037_bands_per_zone():
    assert dim_zone_cost(parcel(), VANALINN)[0] == 30
    assert dim_zone_cost(parcel(), SUDALINN)[0] == 40
    assert dim_zone_cost(parcel(), KESKLINN)[0] == 55
    assert dim_zone_cost(parcel(), PIRITA)[0] == 70
    assert dim_zone_cost(parcel(), FREE)[0] == 80


def test_p4_037_names_missing_halves_not_assumed():
    _, reason = dim_zone_cost(parcel(), SUDALINN)
    assert "hinnang" in reason and "ainult tsooni-kulu pool" in reason
    assert "EMTA" in reason
    assert "ummikumaksu" in reason or "autovaba" in reason


def test_p4_037_null_contract():
    v, reason = dim_zone_cost(None, KESKLINN)
    assert v is None and "EI OLE" in reason
    v, reason = dim_zone_cost(parcel(), None)
    assert v is None and "EI OLE" in reason and "kaardiotsing" in reason
    v, reason = dim_zone_cost(parcel(), parking("B"))
    assert v is None and "EI OLE" in reason


# -- P4-049 coverage --------------------------------------------------------

def test_p4_049_saturday_19_bands():
    assert dim_guest_parking(parcel(), VANALINN)[0] == 35
    assert dim_guest_parking(parcel(), SUDALINN)[0] == 45
    assert dim_guest_parking(parcel(), PIRITA)[0] == 65
    assert dim_guest_parking(parcel(), KESKLINN)[0] == 75
    assert dim_guest_parking(parcel(), FREE)[0] == 80


def test_p4_049_kesklinn_saturday_evening_is_free():
    _, reason = dim_guest_parking(parcel(), KESKLINN)
    assert "laupäeval kell 19" in reason
    assert "8-15" in reason and "tasuta" in reason


def test_p4_049_pirita_states_season_caveat():
    _, reason = dim_guest_parking(parcel(), PIRITA)
    assert "hooajaline" in reason
    assert "15.05-15.09" in reason and "0,01 EUR/min" in reason


def test_p4_049_paid_zones_name_missing_guest_permit():
    for pz in (SUDALINN, VANALINN):
        _, reason = dim_guest_parking(parcel(), pz)
        assert "külalisloa" in reason and "pole" in reason


def test_p4_049_null_contract():
    v, reason = dim_guest_parking(None, KESKLINN)
    assert v is None and "EI OLE" in reason
    v, reason = dim_guest_parking(parcel(), {})
    assert v is None and "EI OLE" in reason and "kaardiotsing" in reason
    v, reason = dim_guest_parking(parcel(), parking("C"))
    assert v is None and "EI OLE" in reason


# -- honesty markers across all three --------------------------------------

def test_all_reasons_honest_no_fake_precision():
    for fn in ALL_FNS:
        for pz in (FREE, KESKLINN, SUDALINN, VANALINN, PIRITA):
            _, reason = fn(parcel(), pz)
            assert "hinnang" in reason, (fn.__name__, pz)
        for bad in (None, {}, parking("teadmata"), parking("X")):
            _, reason = fn(parcel(), bad)
            assert "EI OLE" in reason, (fn.__name__, bad)
        _, scored = fn(parcel(), KESKLINN)
        assert "mõõdetud" not in scored and "garanteeritud" not in scored


def test_explicit_zone_key_never_distance_graded():
    # Same parcel id, different explicit zones -> different scores: the
    # zone is a join key, never inferred from coordinates.
    assert (dim_parking_regime(parcel(), KESKLINN)[0]
            != dim_parking_regime(parcel(), VANALINN)[0])
    assert (dim_guest_parking(parcel(), KESKLINN)[0]
            != dim_guest_parking(parcel(), SUDALINN)[0])


# -- registry + aggregator --------------------------------------------------

def test_registry_and_aggregator_cover_all_three():
    assert [k for k, _, _ in P4_PARK_DIMS] == [
        "parking_regime", "zone_cost", "guest_parking"]
    assert [p for _, p, _ in P4_PARK_DIMS] == ["P4-013", "P4-037", "P4-049"]
    assert len({fn for _, _, fn in P4_PARK_DIMS}) == 3
    out = score_p4_park(parcel(), KESKLINN)
    assert out == {"parking_regime": 60, "zone_cost": 55,
                   "guest_parking": 75}
    assert score_p4_park(parcel(), FREE) == {
        "parking_regime": 80, "zone_cost": 80, "guest_parking": 80}
    assert score_p4_park(None, None) == {
        "parking_regime": None, "zone_cost": None,
        "guest_parking": None}
    assert score_p4_park(parcel()) == {
        "parking_regime": None, "zone_cost": None,
        "guest_parking": None}
    assert p4.P4_PARK_DIMS is P4_PARK_DIMS


# -- ingestion: cache-hit + error discipline (no network) -------------------

def test_is_fresh_and_ttl_constant(tmp_path):
    import os
    assert TTL_PARK_DAYS == 365
    dest = cache_path(str(tmp_path), "hub.html")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w") as fh:
        fh.write("<html/>")
    assert is_fresh(dest, 365) is True
    assert is_fresh(str(tmp_path / "missing.html"), 365) is False


def test_fetch_park_cache_hit_never_touches_network(tmp_path, monkeypatch):
    import os
    import urllib.request
    dest = cache_path(str(tmp_path), "hub.html")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w") as fh:
        fh.write("<html/>")

    def _boom(req, timeout=None):
        raise AssertionError("network touched on cache hit")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    assert fetch_park("https://example.invalid/nope", str(tmp_path),
                      "hub.html", 365) == dest


def test_fetch_park_errors_yield_none_and_cache_nothing(tmp_path,
                                                        monkeypatch):
    import urllib.request

    class _Resp:
        status = 500

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"nope"

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp())
    assert fetch_park("https://example.invalid/err", str(tmp_path),
                      "err.html", 365) is None
    import os
    assert not os.path.exists(cache_path(str(tmp_path), "err.html"))

    def _raise(*a, **k):
        raise OSError("down")

    monkeypatch.setattr(urllib.request, "urlopen", _raise)
    assert fetch_park("https://example.invalid/down", str(tmp_path),
                      "down.html", 365) is None
    assert not os.path.exists(cache_path(str(tmp_path), "down.html"))


def test_fetch_park_429_is_stop_signal(tmp_path, monkeypatch):
    import os
    import urllib.request

    class _Resp:
        status = 429

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"slow down"

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp())
    assert fetch_park("https://example.invalid/rl", str(tmp_path),
                      "rl.html", 365) is None
    assert not os.path.exists(cache_path(str(tmp_path), "rl.html"))
