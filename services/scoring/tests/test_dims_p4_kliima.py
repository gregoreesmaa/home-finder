"""P4 kliima demo + coverage dims (issues #319, #378): hermetic tests.

No network: this module stages no fetch/parse helpers (dated-negative
verdict — scraping the strategy PDFs would be fake progress), so there
is nothing live to call here. Every dim is exercised across fixture
Tallinn linnaosa origins (plus missing origin and POI variants) to
prove the honest shape: NULL everywhere, never a faked district
gradient, with Estonian honesty markers and actionable pointers at
the sibling legs that DO score.
"""

import dims_p4_kliima as kliima
from dims_p4_kliima import (
    P4_KLIIMA_DIMS,
    dim_heating_zones,
    dim_renovation_targets,
    score_p4_kliima,
)

# ---------------------------------------------------------------------------
# Fixtures: Tallinn linnaosa centroids (inputs only — no gradient is
# scored from them) plus POI variants.
# ---------------------------------------------------------------------------

LINNAOSAD = {
    "Kesklinn": (59.4370, 24.7536),
    "Lasnamäe": (59.4437, 24.8074),
    "Põhja-Tallinn": (59.4565, 24.7013),
    "Nõmme": (59.3896, 24.6774),
    "Pirita": (59.4694, 24.8219),
    "Haabersti": (59.4270, 24.6537),
    "Kristiine": (59.4229, 24.7078),
    "Mustamäe": (59.4068, 24.6883),
}

POIS_VARIANTS = (None, [], [{"kind": "stove_shop", "lat": 59.4370,
                             "lon": 24.7536}])

EXPECTED_KEYS = [
    "kliima_renovation_targets",
    "kliima_heating_zones",
]

EXPECTED_PNUMS = ["P4-010", "P4-059"]


# ---------------------------------------------------------------------------
# Honest shape: NULL for EVERY input, never a district gradient.
# ---------------------------------------------------------------------------

def test_renovation_targets_null_in_every_linnaosa():
    seen_reasons = set()
    for name, origin in LINNAOSAD.items():
        for pois in POIS_VARIANTS:
            v, reason = dim_renovation_targets(origin, pois)
            assert v is None, name
            assert "EI OLE" in reason, name
            assert "hinnang" in reason, name
            seen_reasons.add(reason)
    # One stable verdict, not per-district fiction.
    assert len(seen_reasons) == 1


def test_heating_zones_null_in_every_linnaosa():
    seen_reasons = set()
    for name, origin in LINNAOSAD.items():
        for pois in POIS_VARIANTS:
            v, reason = dim_heating_zones(origin, pois)
            assert v is None, name
            assert "EI OLE" in reason, name
            assert "hinnang" in reason, name
            seen_reasons.add(reason)
    assert len(seen_reasons) == 1


def test_null_for_missing_origin():
    v, reason = dim_renovation_targets(None, None)
    assert v is None and "EI OLE" in reason
    v, reason = dim_heating_zones(None, None)
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# Actionable pointers: each NULL names the sibling leg that scores.
# ---------------------------------------------------------------------------

def test_renovation_targets_points_at_eis_register():
    _, reason = dim_renovation_targets(LINNAOSAD["Kesklinn"], None)
    assert "EIS" in reason
    assert "KÜ" in reason


def test_heating_zones_points_at_rule_and_stove_checks():
    _, reason = dim_heating_zones(LINNAOSAD["Nõmme"], None)
    assert "EHR" in reason
    assert "Päästeamet" in reason
    assert "Keskkonnaamet" in reason


# ---------------------------------------------------------------------------
# Registry + aggregator cover both.
# ---------------------------------------------------------------------------

def test_registry_and_aggregator_cover_both():
    assert [k for k, _, _ in P4_KLIIMA_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_KLIIMA_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_KLIIMA_DIMS}) == 2
    for origin in list(LINNAOSAD.values()) + [None]:
        out = score_p4_kliima(origin, None)
        assert set(out) == set(EXPECTED_KEYS)
        assert out == {k: None for k in EXPECTED_KEYS}
    assert kliima.P4_KLIIMA_DIMS is P4_KLIIMA_DIMS
