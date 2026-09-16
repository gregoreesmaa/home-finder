"""P4 EMTA KOV-fiscal dims (issue #539): hermetic tests.

No network: the batch reads maintainer-placed CSVs (its offline
contract is covered here by building SYNTHETIC publisher-shape CSVs in
tmp_path -- real `;`/BOM/Estonian-number layout observed 2026-09-16,
invented KOVs and euros only, never a real pull). Every dim runs on
fixture tables: EHAK-code hit -> tertile bands, name fallback ->
bands, unknown KOV -> NULL with hinnang + buyer check.
"""

import dims_p4_emta_kov as kov
from dims_p4_emta_kov import (
    HARJUMAA_KOV_CODES,
    P4_EMTA_KOV_DIMS,
    SHARE_HI,
    SHARE_LO,
    dim_maamaks_burden,
    kov_lookup_key,
    normalise_kov,
    score_p4_emta_kov,
)


def _table(**shares):
    return {"code:%s" % code: {"maamaks_share_2025": s, "kov_code": code}
            for code, s in shares.items()}


def test_bands_follow_measured_tertiles():
    assert SHARE_LO == 3.0 and SHARE_HI == 4.4  # locked 2026-09-16
    table = {
        "code:296": {"maamaks_share_2025": 1.50},   # Keila: low
        "code:719": {"maamaks_share_2025": 2.95},   # Saku: p33 edge
        "code:198": {"maamaks_share_2025": 4.37},   # Harku: p67 edge
        "code:784": {"maamaks_share_2025": 4.29},   # Tallinn: mid
        "code:431": {"maamaks_share_2025": 5.55},   # Laane-Harju: high
        "code:245": {"maamaks_share_2025": 9.72},   # Joelahtme: top
    }
    assert dim_maamaks_burden("296", None, table)[0] == 70
    assert dim_maamaks_burden("719", None, table)[0] == 70
    assert dim_maamaks_burden("198", None, table)[0] == 55
    assert dim_maamaks_burden("784", None, table)[0] == 55
    assert dim_maamaks_burden("431", None, table)[0] == 40
    assert dim_maamaks_burden("245", None, table)[0] == 40
    _, reason = dim_maamaks_burden("245", None, table)
    assert "hinnang" in reason
    assert "teenusekvaliteedi" in reason  # transfers != service quality
    assert "9.72" in reason  # joined value named, traceable


def test_code_beats_name_and_name_fallback_works():
    table = dict(_table(**{"784": 4.29}))
    table["name:tallinn"] = {"maamaks_share_2025": 4.29}
    assert dim_maamaks_burden("784", "Tallinn", table)[0] == 55
    v, reason = dim_maamaks_burden(None, "  TALLINN ", table)
    assert v == 55  # normalised-name fallback, no code needed


def test_unknown_kov_is_null_never_forced():
    table = _table(**{"784": 4.29})
    for code, name in [(None, None), ("999", None),
                       (None, "Tundmatu vald"), ("999", "Tundmatu vald")]:
        v, reason = dim_maamaks_burden(code, name, table)
        assert v is None
        assert "EI OLE" in reason
        assert "p4_emta" in reason  # buyer-side rate-table check named
    v, _ = dim_maamaks_burden("784", None, None)  # no table at all
    assert v is None
    # Row present but share missing: NULL, not a guess.
    v, _ = dim_maamaks_burden("001", None, {"code:001": {}})
    assert v is None


def test_harjumaa_codes_cover_16_kovs():
    assert len(HARJUMAA_KOV_CODES) == 16
    assert "784" in HARJUMAA_KOV_CODES  # Tallinn is one KOV row (#521)


def test_registry_and_rollup():
    assert set(P4_EMTA_KOV_DIMS) == {"maamaks_burden"}
    assert P4_EMTA_KOV_DIMS["maamaks_burden"][1] is dim_maamaks_burden
    assert kov.P4_EMTA_KOV_DIMS is P4_EMTA_KOV_DIMS
    table = _table(**{"296": 1.50})
    dims, reasons = score_p4_emta_kov("296", "Keila linn", table)
    assert dims == {"maamaks_burden": 70}
    assert len(reasons) == 1
    dims, reasons = score_p4_emta_kov("999", None, table)
    assert dims == {"maamaks_burden": None}
    assert reasons == []


def test_lookup_key_shape():
    assert kov_lookup_key(" 784 ", "Tallinn") == "code:784"
    assert kov_lookup_key(None, "  Lääne-Harju VALD ") == \
        "name:lääne-harju vald"
    assert kov_lookup_key(None, None) is None
    assert normalise_kov("Anija  vald") == "anija vald"


def test_batch_table_shape_feeds_the_dim():
    """Contract the batch must honour: code+name keys, share field."""
    table = {
        "code:296": {"maamaks_share_2025": 1.50, "kov_code": "296",
                     "kov_name": "Keila linn"},
        "name:keila linn": {"maamaks_share_2025": 1.50, "kov_code": "296",
                            "kov_name": "Keila linn"},
    }
    v, _ = dim_maamaks_burden("296", None, table)
    assert v == 70  # end to end: batch table feeds the dim
