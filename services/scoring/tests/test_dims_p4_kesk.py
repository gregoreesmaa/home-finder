"""P4 kesk dims (issues #291 demo + #364 coverage): hermetic tests.

No network: the KOTKAS avaandmed feed is open but serves none of the
four legs (no water-abstraction / hunting-notice / mining-permit /
blast-schedule / solid-fuel subtype, linnaosa free-text geography —
2026-09-13 dated-partial verdict, see dims_p4_kesk docstring), so all
four scorers are NULL and the tests pin the None contract, the
Estonian honesty markers (hinnang + EI OLE + buyer-side check
pointer), the per-param missing-input naming, and the
registry/aggregator coverage. The module itself makes no network
calls (pinned by source inspection).
"""

import inspect

import dims_p4_kesk as kesk
from dims_p4_kesk import (
    P4_KESK_DIMS,
    dim_hunting_notices,
    dim_quarry_blast,
    dim_water_permit_reality,
    dim_woodburning_zones,
    score_p4_kesk,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "water", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [dim_water_permit_reality, dim_hunting_notices,
           dim_quarry_blast, dim_woodburning_zones]

EXPECTED_KEYS = ["kesk_water_permit", "kesk_hunting_notices",
                 "kesk_quarry_blast", "kesk_woodburning_zones"]
EXPECTED_PNUMS = ["P4-017", "P4-033", "P4-054", "P4-059"]


def test_all_four_dims_always_none_for_every_input():
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
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_demo_param_names_missing_subtype_and_water_checks():
    _, reason = dim_water_permit_reality(TALLINN, POIS)
    assert "KL/KKL" in reason
    assert "Tallinna Vee" in reason
    assert "Terviseameti joogivee seiret" in reason


def test_hunting_slice_names_human_page_and_missing_dataset():
    _, reason = dim_hunting_notices(TALLINN, POIS)
    assert "inimloetav HTML" in reason
    assert "jahiteadete andmestikku pole" in reason
    assert "Kaitseväe" in reason


def test_quarry_slice_names_missing_dates_and_sibling_register():
    _, reason = dim_quarry_blast(TALLINN, POIS)
    assert "lõhkamiste ajagraafikut" in reason
    assert "Maa-ameti maardlate registrit" in reason
    assert "Maardu/Harku" in reason


def test_woodburning_slice_names_missing_zone_layer():
    _, reason = dim_woodburning_zones(TALLINN, POIS)
    assert "tsoonikihti" in reason
    assert "Tallinna Keskkonnaameti" in reason
    assert "EHR kütte liiki" in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(kesk)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_registry_and_aggregator_cover_all_four():
    assert [k for k, _, _ in P4_KESK_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_KESK_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_KESK_DIMS}) == 4
    out = score_p4_kesk(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_kesk(None, None) == {k: None for k in EXPECTED_KEYS}
    assert kesk.P4_KESK_DIMS is P4_KESK_DIMS
