"""Overturn re-check for G6 muinas designations (issue #237): tests.

No network: the eight scorers are down-registry NULLs (2026-09-13
dated-negative verdict, see dims_overturn_muinas docstring) and the
parse/index/lookup join runs on a synthetic fixture extract, so the
tests pin the None contract, the Estonian honesty markers
(hinnang + EI OLE + buyer-side check pointer), the dated verdict /
re-check note, the fixture join contract (exact match, first wins,
unknown class never joins), the graduable-vs-never split, the
registry/aggregator coverage, and key-disjointness from the
untouched siblings (dims_group06, dims_group06b, dims_p4_muinsus).
The module itself makes no network calls.
"""

import inspect

import dims_group06 as g06
import dims_group06b as g06b
import dims_overturn_muinas as overturn
import dims_p4_muinsus as p4muinsus
from dims_overturn_muinas import (
    DESIGNATION_GRADUABLE,
    DESIGNATION_NEVER,
    MUINAS_OVERTURN_DIMS,
    RECHECK_AFTER,
    VERDICT_DATE,
    build_muinas_index,
    dim_asbestos_muinas,
    dim_commission_muinas,
    dim_facade_easements_muinas,
    dim_leadglass_muinas,
    dim_provenance_muinas,
    dim_settling_muinas,
    dim_society_muinas,
    dim_tax_credits_muinas,
    lookup_muinas,
    parse_muinas_row,
    score_overturn_muinas,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "heritage", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [
    dim_tax_credits_muinas,
    dim_facade_easements_muinas,
    dim_commission_muinas,
    dim_leadglass_muinas,
    dim_settling_muinas,
    dim_society_muinas,
    dim_asbestos_muinas,
    dim_provenance_muinas,
]

EXPECTED_KEYS = [
    "tax_credits_muinas",
    "facade_easements_muinas",
    "commission_muinas",
    "leadglass_muinas",
    "settling_muinas",
    "society_muinas",
    "asbestos_muinas",
    "provenance_muinas",
]

EXPECTED_PNUMS = ["p158", "p272", "p320", "p351", "p354", "p355",
                  "p359", "p360"]

# Synthetic fixture extract (NOT a register transcription -- the
# 520ing origin shows no schema; pins the join contract only).
FIXTURE_ROWS = [
    {"building_ref": "Tallinn/Vanalinn/Pikk-12",
     "designation": "mälestis", "register_id": "12345"},
    {"building_ref": "Tallinn/Kalamaja/Kotzebue-9",
     "designation": "miljööala", "register_id": None},
    {"building_ref": "   ", "designation": "mälestis",
     "register_id": "999"},  # blank ref: never joins
    {"building_ref": "Tallinn/Kadriorg/Weizenbergi-1",
     "designation": "loss", "register_id": "7"},  # unknown class
]


def test_all_eight_dims_always_none_for_every_input():
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
        assert "register.muinas.ee" in reason, fn.__name__
        assert "520" in reason, fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_reasons_name_dead_host_and_cousin_scorers_where_honest():
    _, tax = dim_tax_credits_muinas(TALLINN, POIS)
    assert "register.muinsuskaitseamet.ee" in tax
    assert "NXDOMAIN" in tax
    assert "EMTA" in tax
    _, commission = dim_commission_muinas(TALLINN, POIS)
    assert "dims_group06" in commission
    assert "Muinsuskaitseamet" in commission
    _, society = dim_society_muinas(TALLINN, POIS)
    assert "dims_group06b" in society
    _, easements = dim_facade_easements_muinas(TALLINN, POIS)
    assert "kinnistusraamat" in easements.lower()
    _, provenance = dim_provenance_muinas(TALLINN, POIS)
    assert "kinnistusraamat" in provenance.lower()


def test_module_adds_no_network_calls():
    src = inspect.getsource(overturn)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_verdict_is_dated_with_quarterly_recheck_note():
    # A down register is re-probed quarterly (docs/p4_muinsus.md
    # reopening checklist), not semi-annually like a kept-NULL hunt.
    assert VERDICT_DATE == "2026-09-13"
    assert RECHECK_AFTER == "2026-12-13"
    assert RECHECK_AFTER > VERDICT_DATE


def test_parse_accepts_known_classes_rejects_the_rest():
    good = parse_muinas_row(FIXTURE_ROWS[0])
    assert good == {"building_ref": "Tallinn/Vanalinn/Pikk-12",
                    "designation": "mälestis", "register_id": "12345"}
    assert parse_muinas_row(FIXTURE_ROWS[2]) is None  # blank ref
    assert parse_muinas_row(FIXTURE_ROWS[3]) is None  # unknown class
    assert parse_muinas_row(None) is None
    assert parse_muinas_row("Pikk-12") is None
    assert parse_muinas_row({"building_ref": "x"}) is None
    assert parse_muinas_row({"building_ref": "x",
                             "designation": "mälestis",
                             "register_id": 7}) is None


def test_index_skips_gaps_first_record_wins():
    index = build_muinas_index(FIXTURE_ROWS)
    assert sorted(index) == ["Tallinn/Kalamaja/Kotzebue-9",
                             "Tallinn/Vanalinn/Pikk-12"]
    dupes = [FIXTURE_ROWS[0],
             {"building_ref": "Tallinn/Vanalinn/Pikk-12",
              "designation": "kaitsevöönd", "register_id": "z"}]
    assert build_muinas_index(dupes)["Tallinn/Vanalinn/Pikk-12"][
        "designation"] == "mälestis"
    assert build_muinas_index([]) == {}
    assert build_muinas_index(None) == {}


def test_lookup_is_exact_match_only():
    index = build_muinas_index(FIXTURE_ROWS)
    hit = lookup_muinas("Tallinn/Vanalinn/Pikk-12", index)
    assert hit is not None and hit["designation"] == "mälestis"
    assert lookup_muinas("tallinn/vanalinn/pikk-12", index) is None
    assert lookup_muinas("Tallinn/Vanalinn/Pikk", index) is None
    assert lookup_muinas("Tallinn/Kadriorg/Weizenbergi-1", index) is None
    assert lookup_muinas("", index) is None
    assert lookup_muinas("Tallinn/Vanalinn/Pikk-12", {}) is None
    assert lookup_muinas("Tallinn/Vanalinn/Pikk-12", None) is None


def test_graduable_vs_never_split_covers_all_eight_exactly_once():
    assert sorted(DESIGNATION_GRADUABLE) == ["p158", "p320", "p355", "p360"]
    assert sorted(DESIGNATION_NEVER) == ["p272", "p351", "p354", "p359"]
    assert sorted(DESIGNATION_GRADUABLE + DESIGNATION_NEVER) == sorted(
        EXPECTED_PNUMS)


def test_keys_are_disjoint_from_untouched_siblings():
    sibling_keys = {k for k, _, _ in g06.GROUP06_DIMS}
    sibling_keys |= {k for k, _, _ in g06b.GROUP06B_DIMS}
    sibling_keys |= {k for k, _, _ in p4muinsus.P4_MUINSUS_DIMS}
    assert not (set(EXPECTED_KEYS) & sibling_keys)
    assert len({fn for _, _, fn in MUINAS_OVERTURN_DIMS}) == 8


def test_registry_and_aggregator_cover_all_eight():
    assert [k for k, _, _ in MUINAS_OVERTURN_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in MUINAS_OVERTURN_DIMS] == EXPECTED_PNUMS
    assert score_overturn_muinas(TALLINN, POIS) == {
        k: None for k in EXPECTED_KEYS}
    assert score_overturn_muinas(None, None) == {
        k: None for k in EXPECTED_KEYS}
    assert overturn.MUINAS_OVERTURN_DIMS is MUINAS_OVERTURN_DIMS
