"""P4 Elektrilevi dims (issues #264 demo + #344 coverage): hermetic tests.

No network: all five scorers are unpublished-feed NULLs (2026-09-13
dated-negative verdict, see dims_p4_elektrilevi docstring), so the
tests pin the None contract, the Estonian honesty markers (hinnang
+ EI OLE + buyer-side check pointer), and the registry/aggregator
coverage. The module itself makes no network calls.
"""

import dims_p4_elektrilevi as elvi
from dims_p4_elektrilevi import (
    P4_ELEKTRILEVI_DIMS,
    dim_backup_feed,
    dim_power_reliability,
    dim_roof_export,
    dim_tariff_zone,
    dim_zero_consumption,
    score_p4_elektrilevi,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [dim_power_reliability, dim_tariff_zone, dim_roof_export,
           dim_backup_feed, dim_zero_consumption]

EXPECTED_KEYS = ["power_reliability", "tariff_zone", "roof_export",
                 "backup_feed", "zero_consumption"]
EXPECTED_PNUMS = ["P4-009", "P4-008", "P4-036", "P4-046", "P4-051"]


def test_all_five_dims_always_none_for_every_input():
    for fn in ALL_FNS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, _ = fn(origin, pois)
            assert v is None, fn.__name__


def test_all_reasons_carry_honesty_markers_and_buyer_side_pointer():
    for fn in ALL_FNS:
        _, reason = fn(TALLINN, POIS)
        assert "hinnang" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__
        assert any(marker in reason for marker in (
            "rikkekaardilt", "netikaardilt", "Konkurentsiameti",
            "Eleringi", "EHR", "KÜ-lt", "kohapeal")), fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_power_reliability_names_feeder_gap_and_live_checks():
    _, reason = dim_power_reliability(TALLINN, POIS)
    assert "SAIDI" in reason
    assert "rikkekaart" in reason and "netikaardilt" in reason


def test_tariff_zone_names_price_list_without_zone_join():
    _, reason = dim_tariff_zone(TALLINN, POIS)
    assert "hinnakiri" in reason
    assert "tsooni" in reason
    assert "majandusaasta aruandest" in reason


def test_roof_export_names_gated_map_and_elering_terms():
    _, reason = dim_roof_export(TALLINN, POIS)
    assert "liitumiskaardi" in reason
    assert "Eleringi" in reason and "EHR" in reason


def test_backup_feed_names_redundancy_without_published_info():
    _, reason = dim_backup_feed(TALLINN, POIS)
    assert "Varutoite" in reason
    assert "kamin" in reason and "linnavesi" in reason


def test_zero_consumption_stays_hex_only_never_addresses():
    _, reason = dim_zero_consumption(TALLINN, POIS)
    assert "hex" in reason
    assert "mitte kunagi aadressid" in reason
    assert "remondifondi" in reason and "REL2021" in reason


def test_registry_and_aggregator_cover_all_five():
    assert [k for k, _, _ in P4_ELEKTRILEVI_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_ELEKTRILEVI_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_ELEKTRILEVI_DIMS}) == 5
    out = score_p4_elektrilevi(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_elektrilevi(None, None) == {k: None for k in EXPECTED_KEYS}
    assert elvi.P4_ELEKTRILEVI_DIMS is P4_ELEKTRILEVI_DIMS
