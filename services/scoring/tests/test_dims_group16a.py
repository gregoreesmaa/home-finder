"""Group 16 macro/finance dims, batch A (issue #205): hermetic tests.

No network: every scorer returns None by contract (registry tables and
national series are not in the OSM snapshot), so the tests pin the None
contract, the Estonian honesty wording, and the registry coverage.
"""

import dims_group16a as g16a
from dims_group16a import GROUP16A_DIMS, score_group16a

TALLINN = (59.4372, 24.7536)

ALL_FNS = [fn for _, _, fn in GROUP16A_DIMS]

EXPECTED_KEYS = [
    "property_taxes", "mortgage_rates", "home_insurance", "closing_costs",
    "down_payment", "historical_appreciation", "resale_appeal",
    "home_insurability", "special_tax_assessment", "municipal_fiscal_health",
    "assumable_mortgages", "contractor_availability", "relocation_incentives",
    "market_liquidity", "tax_reassessment", "seller_concessions",
    "mortgage_portability", "first_time_buyer", "rent_back",
    "opportunity_zones", "title_insurance", "net_metering",
]

EXPECTED_PNOS = [
    "p2", "p6", "p7", "p8", "p9", "p41", "p43", "p70", "p73", "p77",
    "p143", "p147", "p148", "p149", "p151", "p153", "p155", "p156",
    "p157", "p159", "p160", "p185",
]


def test_every_dim_is_none_for_every_input():
    for fn in ALL_FNS:
        for origin, pois in [(TALLINN, []), (TALLINN, None), (None, None),
                             (None, [{"kind": "x", "lat": 59.4, "lon": 24.7}])]:
            v, _ = fn(origin, pois)
            assert v is None, fn.__name__


def test_every_reason_is_honest_estonian():
    for fn in ALL_FNS:
        _, reason = fn(TALLINN, [])
        assert "hinnang" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__
        assert "feigi" in reason, fn.__name__
    joined = " ".join(fn(TALLINN, [])[1] for fn in ALL_FNS)
    assert "garanteeritud" not in joined.lower()


def test_reasons_name_the_missing_registry():
    by_key = {key: fn for key, _, fn in GROUP16A_DIMS}

    def reason(key):
        return by_key[key](TALLINN, [])[1]

    assert "EMTA" in reason("property_taxes") and "KOV" in reason("property_taxes")
    assert "Euribor" in reason("mortgage_rates") and "ECB" in reason("mortgage_rates")
    assert "Maa-amet" in reason("historical_appreciation") and "HH01" in reason(
        "historical_appreciation")
    assert "KK11" in reason("market_liquidity")
    assert "EMTA" in reason("municipal_fiscal_health")
    assert "KredEx" in reason("first_time_buyer")
    assert "Elering" in reason("net_metering")
    assert "kinnistusraamat" in reason("title_insurance").lower()
    assert "Äriregister" in reason("contractor_availability")
    # National series must say they do not vary by place.
    for key in ("mortgage_rates", "first_time_buyer", "net_metering"):
        assert "üleriigili" in reason(key), key  # stem: üleriigiline/-sed


def test_registry_and_aggregator_cover_all_22():
    assert [k for k, _, _ in GROUP16A_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in GROUP16A_DIMS] == EXPECTED_PNOS
    out = score_group16a(TALLINN, [])
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_group16a(None, None) == {k: None for k in EXPECTED_KEYS}
    assert g16a.GROUP16A_DIMS is GROUP16A_DIMS


def test_module_adds_no_network_surface():
    # No Overpass fragment / POI kinds / tag mapping by design: there is
    # no OSM tag that honestly proxies a rate, a tax table or a deal.
    assert not hasattr(g16a, "GROUP16A_OVERPASS_FRAGMENT")
    assert not hasattr(g16a, "GROUP16A_POI_KIND")
    assert not hasattr(g16a, "kinds_from_tags")
