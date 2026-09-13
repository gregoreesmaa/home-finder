"""P4 Maa-subsurface dims (issues #248 demo + #332 coverage): hermetic tests.

No network: every polygon is a synthetic invented square (plain dicts —
never scraped data, never a WFS dump). fetch_cached is covered only on its
cache-hit path; freshness/expiry uses tmp_path. The live probes are manual
DoD evidence (pasted in the PR + docs/p4_maa_subsurface.md), not unit runs.
"""

import os
import time

import dims_p4_maa_subsurface as p4
from dims_p4_maa_subsurface import (
    P4_MAA_SUBSURFACE_DIMS,
    QUARRY_NEAR_KM,
    MAX_FEATURES_PER_REQ,
    cache_path,
    dim_engineering_geology,
    dim_quarry_buffer,
    dim_water_sewer,
    fetch_layer,
    haversine_km,
    is_fresh,
    join_parcel_flags,
    layer_url,
    nearest_vertex_km,
    parse_geojson_features,
    point_in_polygon,
    score_p4_maa_subsurface,
)

# Synthetic Tallinn-fringe fixtures (invented squares, never real polygons).
KARST_SQ = [[24.81, 59.435], [24.83, 59.435], [24.83, 59.445],
            [24.81, 59.445]]
TURVAS_SQ = [[24.62, 59.365], [24.64, 59.365], [24.64, 59.375],
             [24.62, 59.375]]
QUARRY_SQ = [[24.94, 59.47], [24.96, 59.47], [24.96, 59.48],
             [24.94, 59.48]]

KARST_PT = (24.82, 59.44)      # inside KARST_SQ
TURVAS_PT = (24.63, 59.37)     # inside TURVAS_SQ
QUARRY_PT = (24.95, 59.475)    # inside QUARRY_SQ
NEAR_PT = (24.975, 59.475)     # ~1.0 km from the nearest quarry vertex
FAR_PT = (24.80, 59.44)        # well beyond the quarry buffer
OUTSIDE_PT = (24.70, 59.40)    # inside nothing

QUARRIES = [{"nimi": "Maardu paekivi (fiktiivne)", "polygons": [QUARRY_SQ]}]

EXPECTED_KEYS = ["eng_geology", "water_sewer", "quarry_buffer"]
EXPECTED_PNUMS = ["P4-016", "P4-017", "P4-054"]


def parcel(**kw):
    base = {"karst": False, "turvas": False, "alvar": False,
            "kaitseala": False, "vesi": "central", "kanal": "central",
            "lon": OUTSIDE_PT[0], "lat": OUTSIDE_PT[1]}
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# Join core: containment, distance, GeoJSON parsing, layer join.
# ---------------------------------------------------------------------------

def test_point_in_polygon_inside_outside_and_edges():
    assert point_in_polygon(*KARST_PT, KARST_SQ) is True
    assert point_in_polygon(*OUTSIDE_PT, KARST_SQ) is False
    assert point_in_polygon(*TURVAS_PT, KARST_SQ) is False
    # Degenerate rings never flag a parcel.
    assert point_in_polygon(24.82, 59.44, []) is False
    assert point_in_polygon(24.82, 59.44, [[24.82, 59.44]]) is False
    assert point_in_polygon(24.82, 59.44, [[0.0, 0.0], [1.0, 1.0]]) is False


def test_haversine_tallinn_scale():
    # 0.01 deg longitude at Tallinn latitude ~= 0.565 km.
    d = haversine_km(24.75, 59.4372, 24.76, 59.4372)
    assert abs(d - 0.565) < 0.01
    # 0.01 deg latitude ~= 1.112 km anywhere.
    assert abs(haversine_km(24.75, 59.44, 24.75, 59.45) - 1.112) < 0.01
    assert haversine_km(24.75, 59.44, 24.75, 59.44) == 0.0


def test_parse_geojson_keeps_polygons_skips_rest():
    doc = {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "properties": {"kood": "K1", "nimi": "Karstiala"},
         "geometry": {"type": "Polygon", "coordinates": [KARST_SQ]}},
        {"type": "Feature", "properties": {"nimi": "Mitmik"},
         "geometry": {"type": "MultiPolygon",
                      "coordinates": [[TURVAS_SQ], [QUARRY_SQ]]}},
        {"type": "Feature", "properties": {"nimi": "Punktikaev"},
         "geometry": {"type": "Point", "coordinates": [24.75, 59.44]}},
        {"type": "Feature", "properties": {},
         "geometry": {"type": "Polygon", "coordinates": []}},
        {"type": "Feature", "properties": {}},
    ]}
    feats = parse_geojson_features(doc)
    assert len(feats) == 2  # point + broken + missing geometry skipped
    assert feats[0]["attrs"]["kood"] == "K1"
    assert feats[0]["polygons"] == [KARST_SQ]
    assert feats[1]["polygons"] == [TURVAS_SQ, QUARRY_SQ]
    assert parse_geojson_features({}) == []
    assert parse_geojson_features(None) == []


def test_join_parcel_flags_containment_only():
    layers = {"karst": [{"attrs": {"nimi": "K"}, "polygons": [KARST_SQ]}],
              "turvas": [{"attrs": {"nimi": "T"}, "polygons": [TURVAS_SQ]}]}
    hit = join_parcel_flags(*KARST_PT, layers)
    assert [f["nimi"] for f in hit["karst"]] == ["K"]
    assert "turvas" not in hit
    assert join_parcel_flags(*OUTSIDE_PT, layers) == {}
    assert join_parcel_flags(*KARST_PT, {}) == {}


def test_nearest_vertex_coarse_proxy():
    d = nearest_vertex_km(*NEAR_PT, [QUARRY_SQ])
    assert d is not None and d <= QUARRY_NEAR_KM
    assert nearest_vertex_km(*FAR_PT, [QUARRY_SQ]) > QUARRY_NEAR_KM
    assert nearest_vertex_km(24.95, 59.475, []) is None
    assert nearest_vertex_km(24.95, 59.475, [[]]) is None


# ---------------------------------------------------------------------------
# Ingestion helpers: cache, freshness, layer URL politeness.
# ---------------------------------------------------------------------------

def test_cache_path_and_freshness_hermetic(tmp_path):
    p = cache_path(str(tmp_path), "karst.geojson")
    assert p == os.path.join(str(tmp_path), p4.CACHE_SUBDIR, "karst.geojson")
    assert is_fresh(p, 365) is False  # missing file is never fresh
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        fh.write("{}")
    assert is_fresh(p, 365) is True
    old = time.time() - 400 * 86400
    os.utime(p, (old, old))
    assert is_fresh(p, 365) is False


def test_fetch_cached_cache_hit_never_touches_network(tmp_path):
    p = cache_path(str(tmp_path), "karst.geojson")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as fh:
        fh.write(b"cached")
    # Unreachable URL + fresh cache: must return without raising.
    assert p4.fetch_cached("http://127.0.0.1:9/nope", str(tmp_path),
                           "karst.geojson", 365) == p


def test_layer_url_stays_within_politeness_cap():
    url = layer_url("maaamet:geol_hydrogeoloogia_allikadkarstivormid_"
                    "karstivali")
    assert "count=%d" % MAX_FEATURES_PER_REQ in url
    assert MAX_FEATURES_PER_REQ == 100
    assert "outputFormat=application/json" in url
    assert "srsName=EPSG:4326" in url
    boxed = layer_url("etak:e_307_turbavali_a",
                      (24.5, 59.3, 25.0, 59.6))
    assert "bbox=24.5,59.3,25.0,59.6,EPSG:4326" in boxed
    try:
        fetch_layer("tundmatu-kiht", "/tmp")
    except KeyError:
        pass
    else:
        raise AssertionError("unknown join name must raise KeyError")


# ---------------------------------------------------------------------------
# P4-016 demo dim: engineering-geology bands + NULLs.
# ---------------------------------------------------------------------------

def test_p4_016_bands_coarse_only():
    v, r = dim_engineering_geology(parcel(karst=True, turvas=True))
    assert v == 20 and "karst + turvas" in r
    v, _ = dim_engineering_geology(parcel(karst=True))
    assert v == 30
    v, _ = dim_engineering_geology(parcel(turvas=True))
    assert v == 35
    v, r = dim_engineering_geology(parcel(alvar=True))
    assert v == 55 and "alvar" in r
    v, r = dim_engineering_geology(parcel())  # all flags False = clean
    assert v == 70 and "jäme hinnang" in r


def test_p4_016_kaitseala_caps_and_nulls():
    v, r = dim_engineering_geology(parcel(kaitseala=True))
    assert v == 50 and "põhjaveekaitseala" in r
    v, _ = dim_engineering_geology(parcel(karst=True, kaitseala=True))
    assert v == 30  # karst band already below the cap
    v, r = dim_engineering_geology({})
    assert v is None and "EI OLE" in r and "hinnang" in r
    v, r = dim_engineering_geology(parcel(karst="jah"))
    assert v is None and "EI OLE" in r  # fail closed, never clean-70
    v, r = dim_engineering_geology(parcel(turvas=1))
    assert v is None and "EI OLE" in r


# ---------------------------------------------------------------------------
# P4-017 coverage dim: water/sewer bands, caps, NULLs.
# ---------------------------------------------------------------------------

def test_p4_017_bands():
    v, _ = dim_water_sewer(parcel())
    assert v == 85  # central/central
    v, r = dim_water_sewer(parcel(kanal="omapuhasti"))
    assert v == 60 and "omapuhasti" in r
    v, _ = dim_water_sewer(parcel(vesi="puurkaev", kanal="central"))
    assert v == 55
    v, r = dim_water_sewer(parcel(vesi="salvkaev", kanal="omapuhasti"))
    assert v == 45 and "EI OLE" in r  # private-well quality unknown


def test_p4_017_caps_stack():
    v, r = dim_water_sewer(parcel(vesi="puurkaev", kanal="omapuhasti",
                                  kaitseala_piirang=True))
    assert v == 30 and "kaitseala-piirang" in r
    v, r = dim_water_sewer(parcel(kanal="omapuhasti",
                                  liitumiskohustus=True))
    assert v == 40 and "liitumiskohustus" in r
    v, r = dim_water_sewer(parcel(kvaliteet="halb"))
    assert v == 35 and "Terviseamet" in r
    # Duty on a fully connected parcel is not a bill.
    v, _ = dim_water_sewer(parcel(liitumiskohustus=True))
    assert v == 85


def test_p4_017_null_paths_carry_markers():
    v, r = dim_water_sewer({})
    assert v is None and "EI OLE" in r and "hinnang" in r
    v, r = dim_water_sewer(parcel(vesi=None))
    assert v is None and "EI OLE" in r and "vesi" in r
    v, r = dim_water_sewer(parcel(kanal=None))
    assert v is None and "EI OLE" in r and "kanal" in r
    v, r = dim_water_sewer(parcel(vesi="kaev"))
    assert v is None and "EI OLE" in r  # unknown enum fails closed
    v, r = dim_water_sewer(parcel(kvaliteet="teadmata"))
    assert v is None and "EI OLE" in r


# ---------------------------------------------------------------------------
# P4-054 coverage dim: quarry buffer (presence-only scoring).
# ---------------------------------------------------------------------------

def test_p4_054_inside_near_far():
    v, r = dim_quarry_buffer(parcel(lon=QUARRY_PT[0], lat=QUARRY_PT[1]),
                             QUARRIES)
    assert v == 25 and "levialas" in r and "EI OLE" in r  # no timetable leg
    v, r = dim_quarry_buffer(parcel(lon=NEAR_PT[0], lat=NEAR_PT[1]),
                             QUARRIES)
    assert v == 45 and "jäme" in r
    v, r = dim_quarry_buffer(parcel(lon=FAR_PT[0], lat=FAR_PT[1]), QUARRIES)
    assert v is None and "EI OLE" in r  # far is not proof of quiet


def test_p4_054_null_paths_carry_markers():
    v, r = dim_quarry_buffer({}, QUARRIES)
    assert v is None and "EI OLE" in r  # no coordinates
    v, r = dim_quarry_buffer(parcel(lon=1.0, lat=2.0), [])
    assert v is None and "EI OLE" in r  # layer not loaded
    v, r = dim_quarry_buffer(parcel(lon=QUARRY_PT[0], lat=QUARRY_PT[1]),
                             [{"nimi": "Tühi", "polygons": []}])
    assert v is None and "EI OLE" in r  # degenerate polygons never flag


# ---------------------------------------------------------------------------
# End-to-end: WFS polygons -> per-parcel join -> three scores (fixtures).
# ---------------------------------------------------------------------------

def test_join_to_score_end_to_end():
    layers = {"karst": [{"attrs": {"nimi": "K"}, "polygons": [KARST_SQ]}],
              "turvas": [{"attrs": {"nimi": "T"}, "polygons": [TURVAS_SQ]}],
              "pohjaveekaitse": []}
    flags = join_parcel_flags(*KARST_PT, layers)
    p = parcel(lon=KARST_PT[0], lat=KARST_PT[1],
               karst="karst" in flags, turvas="turvas" in flags,
               alvar=False, kaitseala="pohjaveekaitse" in flags)
    v, r = dim_engineering_geology(p)
    assert v == 30 and "karst" in r
    clean = join_parcel_flags(*OUTSIDE_PT, layers)
    assert clean == {}
    v, _ = dim_engineering_geology(parcel(karst=False, turvas=False,
                                          alvar=False, kaitseala=False))
    assert v == 70


# ---------------------------------------------------------------------------
# Cross-cutting contracts.
# ---------------------------------------------------------------------------

def test_all_null_reasons_carry_honesty_markers():
    nulls = [
        dim_engineering_geology({}),
        dim_water_sewer({}),
        dim_quarry_buffer({}, QUARRIES),
        dim_quarry_buffer(parcel(lon=1.0, lat=2.0), []),
        dim_engineering_geology(parcel(karst="jah")),
        dim_water_sewer(parcel(vesi="kaev")),
    ]
    assert len(nulls) == 6
    for v, reason in nulls:
        assert v is None
        assert "hinnang" in reason
        assert "EI OLE" in reason
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_all_scored_reasons_say_hinnang_never_measured():
    scored = [
        dim_engineering_geology(parcel(karst=True)),
        dim_engineering_geology(parcel()),
        dim_water_sewer(parcel()),
        dim_water_sewer(parcel(vesi="puurkaev", kanal="omapuhasti")),
        dim_quarry_buffer(parcel(lon=QUARRY_PT[0], lat=QUARRY_PT[1]),
                          QUARRIES),
        dim_quarry_buffer(parcel(lon=NEAR_PT[0], lat=NEAR_PT[1]), QUARRIES),
    ]
    assert len(scored) == 6
    for v, reason in scored:
        assert v is not None and 0 <= v <= 100
        assert "hinnang" in reason
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_registry_and_aggregator_cover_all_three():
    assert [k for k, _, _ in P4_MAA_SUBSURFACE_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_MAA_SUBSURFACE_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_MAA_SUBSURFACE_DIMS}) == 3
    assert QUARRY_NEAR_KM == 2.0
    out = score_p4_maa_subsurface(
        parcel(karst=True, lon=QUARRY_PT[0], lat=QUARRY_PT[1]), QUARRIES)
    assert out == {"eng_geology": 30, "water_sewer": 85, "quarry_buffer": 25}
    thin = score_p4_maa_subsurface({}, [])
    assert thin == {"eng_geology": None, "water_sewer": None,
                    "quarry_buffer": None}
    assert p4.P4_MAA_SUBSURFACE_DIMS is P4_MAA_SUBSURFACE_DIMS
