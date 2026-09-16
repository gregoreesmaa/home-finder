"""P4 kitsendus dims (issue #543): hermetic tests.

No network: both scorers are licence-gated NULLs (2026-09-16 verdict, see
dims_p4_kitsendus docstring), so the tests pin the None contract, the
Estonian honesty markers (hinnang + EI OLE + kinnistusraamat/notar buyer
check), the NULL-outside shape (never "clean title"), the offline join
helper on fixtures, the band-table helper, and the registry/aggregator
coverage. The module itself makes no network calls (pinned by source
inspection).
"""

import inspect

import dims_p4_kitsendus as kitsendus
from dims_p4_kitsendus import (
    BAN_SCORES,
    CONDITIONED_SCORES,
    P4_KITSENDUS_DIMS,
    _band_for_zone,
    dim_restriction_zone,
    dim_utility_corridor,
    join_zone_flags,
    point_in_polygon,
    score_p4_kitsendus,
)

# Kalamaja parcel + a ban polygon around it + a conditioned one next door.
PARCEL = {"lon": 24.7380, "lat": 59.4480, "tunnus": "78408:408:0120"}
BAN_ZONE = {"attrs": {"voond_liik_id_vaartus": "ehituskeeld",
                      "nimi": "Veekogu ehituskeeluvöönd",
                      "reegel": "ehitamine keelatud"},
            "polygons": [[[24.7370, 59.4475], [24.7390, 59.4475],
                           [24.7390, 59.4485], [24.7370, 59.4485]]]}
COND_ZONE = {"attrs": {"voond_liik_id_vaartus": "tingimuslik-kooskõlastus",
                       "nimi": "Muinsuskaitse tingimuslik vöönd"},
             "polygons": [[[24.7400, 59.4490], [24.7420, 59.4490],
                            [24.7420, 59.4500], [24.7400, 59.4500]]]}
FAR_PARCEL = {"lon": 24.8000, "lat": 59.4600}


def test_both_dims_always_none_for_every_input():
    for fn, arg in [(dim_restriction_zone, [BAN_ZONE]),
                    (dim_utility_corridor, [BAN_ZONE])]:
        for parcel, zones in [(PARCEL, arg), (PARCEL, []),
                              (FAR_PARCEL, arg), (None, None),
                              (PARCEL, None), ({}, arg)]:
            v, _ = fn(parcel, zones)
            assert v is None, (fn.__name__, parcel, zones)


def test_inside_ban_zone_still_none_with_licence_gate_named():
    v, reason = dim_restriction_zone(PARCEL, [BAN_ZONE])
    assert v is None
    assert "litsentsi EI OLE" in reason
    assert "Veekogu ehituskeeluvöönd" in reason
    assert "skoor 20 ootab litsentsi" in reason
    assert "kinnistusraamatust" in reason
    assert "ära feigi" in reason


def test_outside_every_polygon_is_unknown_never_clean_title():
    v, reason = dim_restriction_zone(FAR_PARCEL, [BAN_ZONE, COND_ZONE])
    assert v is None
    assert "teadmata" in reason
    assert "mitte puhas" in reason
    assert "kinnistusraamatust" in reason
    assert "puhas omand" not in reason.replace("mitte puhas omand", "")


def test_unknown_zone_type_scores_no_band():
    unknown = {"attrs": {"voond_liik_id_vaartus": "midagi-uut-xyz",
                         "nimi": "Tundmatu vöönd"},
               "polygons": BAN_ZONE["polygons"]}
    v, reason = dim_restriction_zone(PARCEL, [unknown])
    assert v is None
    assert "tundmatu liigiga" in reason
    assert _band_for_zone({"voond_liik_id_vaartus": "midagi-uut-xyz"}) is None


def test_band_table_reviewable_values():
    assert _band_for_zone({"voond_liik_id_vaartus": "ehituskeeld"}) == 20
    assert _band_for_zone({"voond_liik_id_vaartus": "EHITUSKEELUVÖÖND"}) == 20
    assert _band_for_zone({"voond_liik_id_vaartus": "tagasilöök 30m"}) == 35
    assert _band_for_zone({"voond_liik_id_vaartus": "tingimuslik"}) == 50
    assert _band_for_zone({"voond_liik_id_vaartus": "teavitus"}) == 65
    assert _band_for_zone({}) is None
    assert min(BAN_SCORES.values()) >= 20
    assert max(BAN_SCORES.values()) <= 35
    assert min(CONDITIONED_SCORES.values()) >= 50
    assert max(CONDITIONED_SCORES.values()) <= 65


def test_join_helper_containment_and_degenerate_rings():
    assert join_zone_flags(24.7380, 59.4480, [BAN_ZONE]) == [
        BAN_ZONE["attrs"]]
    assert join_zone_flags(24.8000, 59.4600, [BAN_ZONE]) == []
    broken = {"attrs": {"nimi": "katki"}, "polygons": [[[0.0, 0.0]]]}
    assert join_zone_flags(0.0, 0.0, [broken]) == []
    assert point_in_polygon(24.7380, 59.4480, BAN_ZONE["polygons"][0]) is True
    assert point_in_polygon(24.8000, 59.4600, BAN_ZONE["polygons"][0]) is False


def test_utility_leg_names_network_operators():
    v, reason = dim_utility_corridor(FAR_PARCEL, [BAN_ZONE])
    assert v is None
    assert "Elektrilevi" in reason
    assert "kinnistusraamatust" in reason
    v, reason = dim_utility_corridor(PARCEL, [BAN_ZONE])
    assert v is None
    assert "võrguettevõtjalt" in reason
    v, reason = dim_utility_corridor(PARCEL, None)
    assert v is None
    assert "EI OLE" in reason


def test_missing_parcel_coordinate_is_honest_null():
    for fn in (dim_restriction_zone, dim_utility_corridor):
        v, reason = fn({}, [BAN_ZONE])
        assert v is None
        assert "koordinaati EI OLE" in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(kitsendus)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_registry_and_aggregator():
    assert [k for k, _ in P4_KITSENDUS_DIMS] == [
        "restriction_zone", "utility_corridor"]
    assert score_p4_kitsendus(PARCEL, [BAN_ZONE], [COND_ZONE]) == {
        "restriction_zone": None, "utility_corridor": None}
    assert score_p4_kitsendus(None) == {
        "restriction_zone": None, "utility_corridor": None}
