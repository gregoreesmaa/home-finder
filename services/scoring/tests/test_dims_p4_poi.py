"""POI register dims (issue #549): hermetic audit + gate tests.

No network, no snapshot reads: the audit runs on fixture counts, the
gated dims on fixture distances. Run:
python3 -m pytest services/scoring/tests/test_dims_p4_poi.py -q
"""

import dims_p4_poi as poi
from dims_p4_poi import (
    DEDICATED_SPLIT,
    HUVIPUNKT_TYPES,
    LAYER_META,
    LICENCE_OK,
    LONG_TAIL,
    POI_DIMS,
    _score_dist,
    agreement_audit,
    dim_poi_library,
    dim_poi_pharmacy,
    dim_poi_post,
)

TALLINN = (59.4372, 24.7536)


# --- observed capability inventory -------------------------------------------------

def test_type_inventory_matches_live_probe():
    # 98 huvipunkt:* names from the 2026-09-16 GetCapabilities pull.
    assert len(HUVIPUNKT_TYPES) == 98
    for t in ("perearst", "haridusasutus", "raamatukogu", "post",
              "tervisekaubad", "ohtlik_ettevote", "varjumiskoht",
              "bussipeatus", "ujula", "spordihoone"):
        assert t in HUVIPUNKT_TYPES


# --- dedicated-source split: never double-score ---------------------------------------

def test_dedicated_split_covers_all_overlaps():
    for t, owner in (("perearst", "#532"), ("haridusasutus", "#530"),
                     ("spordihoone", "#531"), ("staadion", "#531"),
                     ("ujula", "#531"), ("tenniseplats", "#531"),
                     ("supluskoht", "#531"), ("ohtlik_ettevote", "#527"),
                     ("varjumiskoht", "#528"), ("paastekomando", "#528")):
        assert DEDICATED_SPLIT[t] == owner
        assert t in HUVIPUNKT_TYPES
    for t in LONG_TAIL:
        assert t not in DEDICATED_SPLIT  # long tail scores here


def test_dedicated_types_refuse_to_score():
    s, reason = poi._poi_dim("perearst", TALLINN, 100)
    assert s is None and "#532" in reason and "topeltarvestust" in reason


# --- agreement audit (always live — pure maths on caller counts) ------------------------

def test_agreement_audit_verdicts():
    rows = agreement_audit([
        {"type": "raamatukogu", "osm_n": 20, "reg_n": 45},   # 2.25
        {"type": "post", "osm_n": 40, "reg_n": 42},           # 1.05
        {"type": "bussipeatus", "osm_n": 100, "reg_n": 50},   # 0.5
        {"type": "muuseum", "osm_n": 0, "reg_n": 10},         # no OSM base
        {"type": "kino", "osm_n": None, "reg_n": 5},          # missing
    ])
    by_type = {r["type"]: r for r in rows}
    assert by_type["raamatukogu"]["verdict"] == "register-rikkam"
    assert by_type["raamatukogu"]["ratio"] == 2.25
    assert by_type["post"]["verdict"] == "sarnane"
    assert by_type["bussipeatus"]["verdict"] == "osm-rikkam"
    assert by_type["muuseum"]["verdict"] == "võrdlus puudub"
    assert by_type["kino"]["verdict"] == "võrdlus puudub"


# --- licence gate OPENED 2026-09-16 (issue #612) ----------------------------------------

def test_licence_gate_open_points_live():
    # Dated evidence: WFS GetCapabilities ServiceIdentification Abstract
    # applies the Maa- ja Ruumiamet open spatial-data licence (no
    # per-layer override for the long-tail types).
    assert LICENCE_OK is True
    for fn in (dim_poi_library, dim_poi_post, dim_poi_pharmacy):
        s, reason = fn(TALLINN, 150)
        assert s == 85
        assert "avaandmete-litsents" in reason
        assert "vahekiht" in reason


# --- pure walk bands ----------------------------------------------------------------------------

def test_walk_bands_and_null_beyond():
    assert _score_dist(100) == 85
    assert _score_dist(300) == 85
    assert _score_dist(500) == 70
    assert _score_dist(900) == 55
    assert _score_dist(1001) is None  # NULL-beyond, never "no amenity"
    assert _score_dist(None) is None
    assert _score_dist(-5) is None


def test_live_shape_with_gate_open():
    s, reason = dim_poi_library(TALLINN, 150)
    assert s == 85 and "raamatukogu" in reason and "vahekiht" in reason
    assert dim_poi_post(TALLINN, 5000)[0] is None  # NULL-beyond holds
    assert dim_poi_pharmacy(None, 150)[0] is None


# --- long-tail shortlist --------------------------------------------------------------------------

def test_long_tail_shortlist():
    assert set(LONG_TAIL) == {"raamatukogu", "post", "tervisekaubad"}
    assert all(t in HUVIPUNKT_TYPES for t in LONG_TAIL)


# --- registry wiring ----------------------------------------------------------------------------------

def test_dims_registry():
    assert [k for k, _, _ in POI_DIMS] == [
        "poi_library", "poi_post", "poi_pharmacy"]
    assert set(LAYER_META) == {"poi_library", "poi_post", "poi_pharmacy"}
    assert all("litsents" in m["source"] for m in LAYER_META.values())
