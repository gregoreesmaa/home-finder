"""Tests for scripts/build/batch_maaparcel_kataster.py (issue #491).

Hermetic: synthetic inline fixtures only, no network, no snapshot files.
The live #491 harvest is join-proven separately (5/100 parcels touched by
the real KKIS sample, omvorm 54/42/2/2 -- see docs/overturn_maa.md).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from batch_maaparcel_kataster import (  # noqa: E402
    bbox_lonlat,
    build_sidecar,
    classify,
    clean_ring,
    touches,
)

SQUARE = [[24.74, 59.43], [24.75, 59.43], [24.75, 59.44], [24.74, 59.44],
          [24.74, 59.43]]

STRIP = [[24.744, 59.434], [24.746, 59.434], [24.746, 59.4345],
         [24.744, 59.4345], [24.744, 59.434]]


def parcel(tunnus="78401:107:0760", omvorm="Eraomand", ring=None,
           extra_props=None):
    props = {"tunnus": tunnus, "omvorm": omvorm, "siht1": "ELAMUMAA",
             "pindala": 1281, "l_aadress": "Roosikrantsi tn 4c"}
    if extra_props:
        props.update(extra_props)
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "Polygon", "coordinates": [ring or SQUARE]}}


def kkis_feature(name="Isiklik kasutusõigus", ring=None):
    return {"type": "Feature",
            "properties": {"nimi": name, "klass": "TKTV", "reegel": None},
            "geometry": {"type": "MultiPolygon",
                         "coordinates": [[ring or STRIP]]}}


def test_classify_folds_unknown_omvorm_to_muu():
    assert classify("Eraomand") == "era"
    assert classify("Munitsipaalomand") == "muni"
    assert classify("Riigiomand") == "riik"
    # Live fourth class + NULL fold to muu (documented judgment).
    assert classify("Avalik-õiguslik omand") == "muu"
    assert classify(None) == "muu"
    assert classify(7) == "muu"


def test_clean_ring_rejects_garbage_never_faked():
    assert clean_ring(SQUARE) is not None
    assert clean_ring([[24.7, 59.4]] * 2) is None  # too few
    assert clean_ring([[24.7]] * 4) is None  # ragged
    assert clean_ring([[999.0, 59.4]] * 4) is None  # implausible lon
    assert clean_ring("nope") is None
    assert clean_ring([[float("nan"), 59.4]] * 4) is None


def test_touches_catches_strip_centroid_misses():
    # STRIP sits fully inside SQUARE but holds no centroid of any
    # realistic parcel split: vertex-either-way still touches.
    big = [(24.7, 59.4), (24.8, 59.4), (24.8, 59.5), (24.7, 59.5)]
    assert touches(big, [[(x, y) for x, y in STRIP]]) is True
    far = [(25.7, 59.4), (25.8, 59.4), (25.8, 59.5), (25.7, 59.5)]
    assert touches(far, [[(x, y) for x, y in STRIP]]) is False


def test_build_sidecar_row_shape_and_kkis_join():
    rows = build_sidecar(
        {"features": [parcel()]},
        {"features": [kkis_feature()]})
    assert len(rows) == 1
    row = rows[0]
    assert row["tunnus"] == "78401:107:0760"
    assert row["cls"] == "era"
    assert row["omvorm"] == "Eraomand"
    assert row["siht1"] == "ELAMUMAA"
    assert row["pindala"] == 1281
    assert row["kkis"] == 1  # STRIP lies inside SQUARE
    assert row["b"] == [24.74, 59.43, 24.75, 59.44]
    assert row["r"] == [SQUARE]


def test_build_sidecar_kkis_none_means_unknown_never_zero():
    rows = build_sidecar({"features": [parcel()]}, None)
    assert rows[0]["kkis"] is None


def test_build_sidecar_skips_malformed_never_faked():
    bad_geom = parcel(tunnus="a:1")
    bad_geom["geometry"] = {"type": "Point", "coordinates": [24.7, 59.4]}
    no_tunnus = parcel()
    del no_tunnus["properties"]["tunnus"]
    no_props = parcel(tunnus="b:2")
    no_props["properties"] = None
    rows = build_sidecar(
        {"features": [bad_geom, no_tunnus, no_props, parcel(),
                       None, 7, "x"]},
        {"features": []})
    assert [r["tunnus"] for r in rows] == ["78401:107:0760"]
    assert rows[0]["kkis"] == 0  # empty KKIS cache searched: zero hits


def test_build_sidecar_unparseable_doc_yields_no_rows():
    assert build_sidecar({}, {"features": []}) == []
    assert build_sidecar({"features": None}, None) == []
    assert build_sidecar({"features": "nope"}, None) == []


def test_bbox_lonlat_prefilter_box():
    assert bbox_lonlat([[(24.7, 59.4), (24.8, 59.42)]]) == \
        [24.7, 59.4, 24.8, 59.42]
