"""Hermetic unit tests for Group 2 batch-B EHR dims (issue #137).

No network, no snapshot, no EHR registry: inputs are hand-made record
dicts. Run from repo root:
  python3 -m pytest services/scoring/tests/test_dims_group02b.py -q
"""

import dims_group02b as G
from dims_group02b import (
    dim_elevators,
    dim_permit_history,
    dim_sunroom,
    dim_warranties,
    score_group02b,
)


def test_none_without_ehr_record():
    # The whole registry is absent from the snapshot: no record (and no
    # field) may ever score — "Flag NULL; do not fake" (§5.2).
    for fn in (dim_permit_history, dim_warranties, dim_elevators, dim_sunroom):
        assert fn(None)[0] is None
    dims, reasons = score_group02b(None)
    assert dims == {"permit_history": None, "warranties": None,
                    "elevators": None, "sunroom": None}
    assert reasons == []
    dims, reasons = score_group02b({})
    assert all(v is None for v in dims.values())
    assert reasons == []


def test_missing_reasons_cite_absent_ehr_data():
    for fn in (dim_permit_history, dim_warranties, dim_elevators, dim_sunroom):
        _, reason = fn(None)
        assert "EHR" in reason
        assert "puudub" in reason or "puuduvad" in reason


def test_permit_history_bands():
    assert dim_permit_history(3)[0] == 85
    assert dim_permit_history(2)[0] == 85
    assert dim_permit_history(1)[0] == 70
    assert dim_permit_history(0)[0] == 45  # weak history, not a violation
    v, reason = dim_permit_history(2)
    assert "EHR" in reason


def test_warranty_bands():
    assert dim_warranties(True) == (90, "EHR: ehitusgarantii kehtib")
    assert dim_warranties(False) == (50, "EHR: ehitusgarantii on lõppenud")


def test_elevator_bands():
    assert dim_elevators(2)[0] == 95
    assert dim_elevators(1)[0] == 95
    v, reason = dim_elevators(1)
    assert "EHR" in reason and "lift" in reason
    # Measured-from-registry zero: record present, no lift — the one
    # honest zero in this module, still labelled EHR.
    assert dim_elevators(0)[0] == 30
    assert "EHR" in dim_elevators(0)[1]


def test_sunroom_bands():
    assert dim_sunroom(True) == (20, "EHR: kirjas loata ehitis (päikesevarjund/klaasveranda vms)")
    assert dim_sunroom(False) == (85, "EHR: loata ehitisi pole kirjas")


def test_score_group02b_full_record():
    ehr = {"permits_finalized": 2, "warranty_valid": True,
           "elevator_count": 1, "unpermitted_works": False}
    dims, reasons = score_group02b(ehr)
    assert dims == {"permit_history": 85, "warranties": 90,
                    "elevators": 95, "sunroom": 85}
    assert len(reasons) == 4
    assert all("EHR" in r for r in reasons)


def test_score_group02b_partial_record_stays_null_where_unknown():
    dims, reasons = score_group02b({"elevator_count": 0})
    assert dims == {"permit_history": None, "warranties": None,
                    "elevators": 30, "sunroom": None}
    assert reasons == ["EHR: hoones lifti pole kirjas"]


def test_param_ids_cover_batch_b():
    assert G.GROUP02B_PARAM_IDS == {"permit_history": 79, "warranties": 154,
                                   "elevators": 196, "sunroom": 495}
    assert set(G.GROUP02B_DIMS) == set(G.GROUP02B_PARAM_IDS)
