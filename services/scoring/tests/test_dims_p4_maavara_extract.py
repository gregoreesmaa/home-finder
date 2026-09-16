"""P4 maavara-extract dims (issue #545): hermetic tests.

No network: all fixtures are hand-built (attribute NAMES mirror the
2026-09-16 live schema -- ME_OLEK/LOA_LOPP/KAEVANDAJA/U_ALA_NIMI -- but
every value is invented). Tests pin inside/near/outside bands, the
active-permit rule (unknown/expired never scores as a quarry), the
exploration watch-flag cap (never a quarry penalty), LOA_LOPP parsing,
NULL-outside, and registry/aggregator coverage. The module itself makes
no network calls (pinned by source inspection).
"""

import datetime as _dt
import inspect

import dims_p4_maavara_extract as extract
from dims_p4_maavara_extract import (
    EXPLORATION_WATCH,
    EXTRACTION_INSIDE,
    EXTRACTION_NEAR,
    EXTRACTION_NEAR_KM,
    P4_MAAVARA_EXTRACT_DIMS,
    dim_exploration_watch,
    dim_extraction_proximity,
    parse_loa_lopp,
    score_p4_maavara_extract,
)

TODAY = _dt.date(2026, 9, 16)

ACTIVE_QUARRY = {
    "polygons": [[[24.7000, 59.4000], [24.7100, 59.4000],
                   [24.7100, 59.4100], [24.7000, 59.4100]]],
    "NIMETUS": "Harku lubjakivikarjäär",
    "ME_OLEK": "aktiivne",
    "STAATUS": "K",
    "LOA_NUMBER": "L.MK/123456",
    "LOA_LOPP": "20401216",
    "KAEVANDAJA": "OÜ Paemurd",
    "MAAVARA": "lubjakivi",
}
EXPIRED_QUARRY = dict(ACTIVE_QUARRY, LOA_LOPP="20200101")
UNKNOWN_QUARRY = dict(ACTIVE_QUARRY, ME_OLEK="selgitamisel")
NO_OLEK_QUARRY = {k: v for k, v in ACTIVE_QUARRY.items()
                  if k != "ME_OLEK"}
LIVE_EXPLORATION = {
    "polygons": [[[24.7200, 59.4200], [24.7300, 59.4200],
                   [24.7300, 59.4300], [24.7200, 59.4300]]],
    "U_ALA_NIMI": "Harku uuringuala",
    "U_ALA_OLEK": "aktiivne",
    "LOA_NR": "U-789",
    "LOA_LOPP": "20281216",
    "MAAVARAD": "lubjakivi",
}
DEAD_EXPLORATION = dict(LIVE_EXPLORATION, U_ALA_OLEK="lõppenud",
                        LOA_LOPP="20200101")

INSIDE = {"lon": 24.7050, "lat": 59.4050}
NEAR = {"lon": 24.7150, "lat": 59.4050}  # ~0.3-0.9 km east of the edge
FAR = {"lon": 24.8000, "lat": 59.4600}
IN_UU = {"lon": 24.7250, "lat": 59.4250}


def test_inside_active_extraction_scores_low_with_permit_trail():
    v, reason = dim_extraction_proximity(INSIDE, [ACTIVE_QUARRY], TODAY)
    assert v == EXTRACTION_INSIDE == 25
    assert "Harku lubjakivikarjäär" in reason
    assert "L.MK/123456" in reason
    assert "OÜ Paemurd" in reason
    assert "ajagraafiku jalga EI OLE" in reason
    assert "Keskkonnaamet/KOTKAS" in reason


def test_near_band_is_coarse_and_labelled():
    v, reason = dim_extraction_proximity(NEAR, [ACTIVE_QUARRY], TODAY)
    assert v == EXTRACTION_NEAR == 45
    assert "jäme tipp-kauguse hinnang" in reason
    assert EXTRACTION_NEAR_KM == 2.0


def test_outside_is_unknown_never_quiet():
    v, reason = dim_extraction_proximity(FAR, [ACTIVE_QUARRY], TODAY)
    assert v is None
    assert "EI OLE" in reason
    assert "ei tõesta vaikust" in reason
    assert "ära feigi" in reason


def test_expired_unknown_and_missing_status_never_score_as_quarry():
    for q in (EXPIRED_QUARRY, UNKNOWN_QUARRY, NO_OLEK_QUARRY):
        v, reason = dim_extraction_proximity(INSIDE, [q], TODAY)
        assert v is None, q.get("ME_OLEK", "no-olek")
        assert "EI OLE teada" in reason or "EI OLE" in reason
    # Expired permit is skipped even though the parcel is inside.
    v, reason = dim_extraction_proximity(INSIDE, [EXPIRED_QUARRY], TODAY)
    assert "aegunud" in reason


def test_empty_layer_and_bad_parcel_are_honest_nulls():
    v, r1 = dim_extraction_proximity(INSIDE, [], TODAY)
    assert v is None and "maeeraldis_aktiivne" in r1
    v, r2 = dim_extraction_proximity(INSIDE, None, TODAY)
    assert v is None
    v, r3 = dim_extraction_proximity({}, [ACTIVE_QUARRY], TODAY)
    assert v is None and "koordinaati EI OLE" in r3


def test_exploration_inside_is_capped_dated_watch():
    v, reason = dim_exploration_watch(IN_UU, [LIVE_EXPLORATION], TODAY)
    assert v == EXPLORATION_WATCH == 55
    assert "Harku uuringuala" in reason
    assert "EI OLE kaevandusluba" in reason
    assert "Keskkonnaamet" in reason
    assert "ära feigi" in reason


def test_exploration_never_scores_as_quarry():
    v, reason = dim_exploration_watch(IN_UU, [LIVE_EXPLORATION], TODAY)
    assert v is not None and v > EXTRACTION_INSIDE
    assert v > EXTRACTION_NEAR or v == 55


def test_dead_exploration_and_outside_are_null():
    v, reason = dim_exploration_watch(IN_UU, [DEAD_EXPLORATION], TODAY)
    assert v is None
    assert "EI OLE teada" in reason
    v, reason = dim_exploration_watch(FAR, [LIVE_EXPLORATION], TODAY)
    assert v is None
    assert "mitte karjäärivabaks" in reason


def test_loa_lopp_parser_shapes():
    assert parse_loa_lopp("20401216") == _dt.date(2040, 12, 16)
    assert parse_loa_lopp("20200101") == _dt.date(2020, 1, 1)
    assert parse_loa_lopp("") is None
    assert parse_loa_lopp(None) is None
    assert parse_loa_lopp("17.09.2026") is None
    assert parse_loa_lopp("20261301") is None
    assert parse_loa_lopp(True) is None


def test_module_adds_no_network_calls():
    src = inspect.getsource(extract)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_registry_and_aggregator():
    assert [k for k, _ in P4_MAAVARA_EXTRACT_DIMS] == [
        "extraction_proximity", "exploration_watch"]
    assert score_p4_maavara_extract(INSIDE, [ACTIVE_QUARRY],
                                    [LIVE_EXPLORATION], TODAY) == {
        "extraction_proximity": 25, "exploration_watch": None}
    # IN_UU sits ~1.9 km from the quarry vertex: near-band 45 applies too.
    assert score_p4_maavara_extract(IN_UU, [ACTIVE_QUARRY],
                                    [LIVE_EXPLORATION], TODAY) == {
        "extraction_proximity": 45, "exploration_watch": 55}
    assert score_p4_maavara_extract(FAR, [ACTIVE_QUARRY],
                                    [LIVE_EXPLORATION], TODAY) == {
        "extraction_proximity": None, "exploration_watch": None}
