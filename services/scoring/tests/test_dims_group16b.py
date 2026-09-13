"""Group 16 macro/finance dims, batch B (issue #206): hermetic tests.

No network: every scorer is NULL-only, so tests assert the None +
Estonian-reason contract on fixture inputs and pin the registry +
aggregator. Market-wide series must never read as an area signal.
"""

import dims_group16b as g16b
from dims_group16b import (
    GROUP16B_DIMS,
    dim_absorption_rate,
    dim_abatement_expiry,
    dim_appraisal_gap,
    dim_assessment_district,
    dim_capital_gains,
    dim_conservation_credits,
    dim_corporate_density,
    dim_demographic_transition,
    dim_eem_loan,
    dim_escrow_buffer,
    dim_exchange_eligibility,
    dim_flood_insurance_caps,
    dim_land_improvement_ratio,
    dim_nuisance_liability,
    dim_pension_liability,
    dim_pmi_threshold,
    dim_price_ceiling,
    dim_shadow_inventory,
    dim_solar_lease_transfer,
    dim_supplemental_tax,
    dim_tourist_influx,
    dim_transfer_fees,
    score_group16b,
)

TALLINN = (59.4372, 24.7536)

ALL_DIMS = [
    dim_nuisance_liability,
    dim_flood_insurance_caps,
    dim_solar_lease_transfer,
    dim_conservation_credits,
    dim_pension_liability,
    dim_exchange_eligibility,
    dim_abatement_expiry,
    dim_transfer_fees,
    dim_appraisal_gap,
    dim_supplemental_tax,
    dim_assessment_district,
    dim_pmi_threshold,
    dim_eem_loan,
    dim_capital_gains,
    dim_escrow_buffer,
    dim_tourist_influx,
    dim_price_ceiling,
    dim_corporate_density,
    dim_shadow_inventory,
    dim_absorption_rate,
    dim_land_improvement_ratio,
    dim_demographic_transition,
]

POIS = [{"kind": "anything", "lat": TALLINN[0] + 0.001, "lon": TALLINN[1]}]


def test_every_dim_is_always_none_with_honest_estonian_reason():
    for fn in ALL_DIMS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, reason = fn(origin, pois)
            assert v is None, fn.__name__
            assert "EI OLE" in reason, fn.__name__
            assert "hinnang" in reason, fn.__name__
            assert "ära feigi" in reason, fn.__name__


def test_deal_fact_dims_name_the_transaction_check():
    for fn in (dim_nuisance_liability, dim_solar_lease_transfer,
               dim_abatement_expiry, dim_transfer_fees, dim_appraisal_gap,
               dim_supplemental_tax, dim_escrow_buffer,
               dim_land_improvement_ratio, dim_price_ceiling):
        _, reason = fn(TALLINN, POIS)
        assert "tehingu" in reason or "kontrolli" in reason, fn.__name__


def test_registry_dims_name_the_missing_registry():
    assert "tariif" in dim_flood_insurance_caps(TALLINN, POIS)[1]
    assert "EMTA" in dim_conservation_credits(TALLINN, POIS)[1]
    assert "KOV" in dim_pension_liability(TALLINN, POIS)[1]
    assert "KOV" in dim_assessment_district(TALLINN, POIS)[1]
    assert "kinnistusraamat" in dim_corporate_density(TALLINN, POIS)[1]
    assert "Maa-amet" in dim_price_ceiling(TALLINN, POIS)[1]


def test_foreign_concept_dims_state_no_estonian_equivalent():
    for fn in (dim_exchange_eligibility, dim_pmi_threshold, dim_eem_loan,
               dim_capital_gains):
        _, reason = fn(TALLINN, POIS)
        assert "USA" in reason, fn.__name__
        assert "Eesti" in reason, fn.__name__


def test_market_wide_dims_never_read_as_area_signal():
    for fn in (dim_tourist_influx, dim_corporate_density,
               dim_shadow_inventory, dim_absorption_rate,
               dim_demographic_transition):
        _, reason = fn(TALLINN, POIS)
        assert "turu-ülene" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__


def test_registry_and_aggregator_cover_all_twentytwo():
    assert [p for _, p, _ in GROUP16B_DIMS] == [
        "p241", "p243", "p249", "p250", "p318", "p363", "p366", "p370",
        "p421", "p422", "p423", "p424", "p425", "p426", "p430", "p444",
        "p481", "p482", "p483", "p484", "p486", "p487",
    ]
    assert len(ALL_DIMS) == 22
    out = score_group16b(TALLINN, POIS)
    assert set(out) == {k for k, _, _ in GROUP16B_DIMS}
    assert all(v is None for v in out.values())
    assert score_group16b(None, None) == out
    assert g16b.GROUP16B_DIMS is GROUP16B_DIMS
