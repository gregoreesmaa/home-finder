"""Maa-amet WFS overturn dims (issue #235): hermetic tests.

No network: every parcel/polygon is a synthetic invented fixture (plain
dicts -- never scraped data, never a WFS dump). fetch_cached is covered
only on its cache-hit path; freshness/expiry uses tmp_path. The live
probes are manual DoD evidence (pasted in the PR + docs/overturn_maa.md),
not unit runs. Fixture WFS XML (DescribeFeatureType / GetCapabilities
shapes) pins the field-contract parsers.
"""

import os

import dims_overturn_maa as maa
from dims_overturn_maa import (
    MAX_FEATURES_PER_REQ,
    MINERAL_NEAR_KM,
    OVERTURN_LAYERS,
    OVERTURN_MAA_DIMS,
    OVERTURN_MAA_PARAM_IDS,
    RECHECK_AFTER,
    VERDICT_DATE,
    cache_path,
    dim_boundary_markers,
    dim_easement_burden,
    dim_ground_lease_hint,
    dim_lot_size_parcel,
    dim_mineral_rights_hint,
    dim_mineral_severance_hint,
    dim_soil_boniteet,
    fetch_layer,
    haversine_km,
    is_fresh,
    layer_url,
    nearest_vertex_km,
    normalise_mullaklass,
    normalise_omvorm,
    parcel_id,
    parcel_point,
    parse_describe_featuretype_fields,
    point_in_polygon,
    score_overturn_maa,
    wfs_typenames,
)

# Synthetic fixtures (invented Tallinn-fringe squares, never real parcels).
DEPOSIT_SQ = [[24.94, 59.47], [24.96, 59.47], [24.96, 59.48],
              [24.94, 59.48]]
INSIDE_PT = (24.95, 59.475)    # inside DEPOSIT_SQ
NEAR_PT = (24.975, 59.475)     # ~0.85 km east of the nearest vertex
FAR_PT = (24.75, 59.44)        # well beyond the mineral buffer

QUARRIES = [{"nimi": "Paldiski paekivi (fiktiivne)", "polygons": [DEPOSIT_SQ]}]

EXPECTED_KEYS = ["lot_size_parcel", "soil_boniteet", "easement_burden",
                 "boundary_markers", "mineral_rights_hint",
                 "mineral_severance_hint", "ground_lease_hint"]
EXPECTED_PNUMS = ["p29", "p68", "p71", "p75", "p76", "p229", "p364"]


def parcel(**kw):
    base = {"tunnus": "65301:001:0001", "pindala": 1008.0,
            "omvorm": "Eraomand", "siht1": "ELAMUMAA",
            "lon": FAR_PT[0], "lat": FAR_PT[1],
            "mullaklass": "hea", "markers": 4}
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# Contract: registry, verdict dates, politeness cap.
# ---------------------------------------------------------------------------

def test_registry_keys_and_param_ids():
    assert [k for k, _, _ in OVERTURN_MAA_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in OVERTURN_MAA_DIMS] == EXPECTED_PNUMS
    assert [OVERTURN_MAA_PARAM_IDS[k] for k in EXPECTED_KEYS] == \
        [29, 68, 71, 75, 76, 229, 364]
    assert VERDICT_DATE == "2026-09-13"
    assert RECHECK_AFTER > VERDICT_DATE


def test_layers_and_politeness_cap():
    assert OVERTURN_LAYERS["parcels"] == "kataster:ky_kehtiv"
    assert OVERTURN_LAYERS["soil_boniteet"] == "veeveeb:mullad_boniteet"
    assert OVERTURN_LAYERS["maardla_leviala"] == \
        "maaamet:maavarad_gbmv_levialad"
    assert MAX_FEATURES_PER_REQ == 100
    url = layer_url("parcels", bbox=(24.7, 59.4, 24.8, 59.45))
    assert "count=100" in url
    assert "typeName=kataster:ky_kehtiv" in url
    assert "bbox=24.7,59.4,24.8,59.45,EPSG:4326" in url


def test_fetch_layer_cache_hit_only(tmp_path):
    dest = os.path.join(str(tmp_path), maa.CACHE_SUBDIR, "parcels.geojson")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write('{"type":"FeatureCollection","features":[]}')
    assert fetch_layer("parcels", str(tmp_path)) == dest
    assert is_fresh(dest, 30)


def test_cache_path_and_freshness(tmp_path):
    missing = cache_path(str(tmp_path), "x.geojson")
    assert not is_fresh(missing, 30)


# ---------------------------------------------------------------------------
# Fixture WFS XML: DescribeFeatureType field contract + caps layer search.
# ---------------------------------------------------------------------------

DFT_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:kataster="http://kataster" targetNamespace="http://kataster">
  <xsd:complexType name="ky_kehtivType">
    <xsd:complexContent><xsd:extension base="gml:AbstractFeatureType">
      <xsd:sequence>
        <xsd:element name="geom" type="gml:GeometryPropertyType"/>
        <xsd:element name="tunnus" type="xsd:string"/>
        <xsd:element name="pindala" type="xsd:double"/>
        <xsd:element name="omvorm" type="xsd:string"/>
        <xsd:element name="siht1" type="xsd:string"/>
      </xsd:sequence>
    </xsd:extension></xsd:complexContent>
  </xsd:complexType>
</xsd:schema>"""

CAPS_FIXTURE = """<WFS_Capabilities><FeatureTypeList>
<FeatureType><Name>kataster:ky_kehtiv</Name></FeatureType>
<FeatureType><Name>veeveeb:mullad_boniteet</Name></FeatureType>
</FeatureTypeList></WFS_Capabilities>"""


def test_parse_describe_featuretype_fields_fixture():
    fields = parse_describe_featuretype_fields(DFT_FIXTURE)
    for expected in ("tunnus", "pindala", "omvorm", "siht1"):
        assert expected in fields


def test_parse_describe_featuretype_rejects_garbage():
    try:
        parse_describe_featuretype_fields("<not xml")
    except ValueError as exc:
        assert "ei parsinud" in str(exc)
    else:
        raise AssertionError("garbage XML must raise, never parse")


def test_wfs_typenames_fixture_search():
    names = wfs_typenames(CAPS_FIXTURE)
    assert "kataster:ky_kehtiv" in names
    assert "veeveeb:mullad_boniteet" in names
    assert not [n for n in names if "mullakaart" in n]


# ---------------------------------------------------------------------------
# Pure helpers.
# ---------------------------------------------------------------------------

def test_point_in_polygon_and_degenerate():
    assert point_in_polygon(*INSIDE_PT, DEPOSIT_SQ)
    assert not point_in_polygon(*FAR_PT, DEPOSIT_SQ)
    assert not point_in_polygon(24.95, 59.475, [[24.9, 59.4], [24.9, 59.4]])
    assert not point_in_polygon(24.95, 59.475, [])


def test_haversine_and_nearest_vertex():
    d = haversine_km(24.96, 59.475, 24.975, 59.475)
    assert 0.5 < d < 1.5
    near = nearest_vertex_km(*NEAR_PT, [DEPOSIT_SQ])
    assert near is not None and near <= MINERAL_NEAR_KM
    assert nearest_vertex_km(*FAR_PT, [DEPOSIT_SQ]) is None or \
        nearest_vertex_km(*FAR_PT, [DEPOSIT_SQ]) > MINERAL_NEAR_KM
    assert nearest_vertex_km(24.9, 59.4, []) is None


def test_parcel_id_and_point():
    assert parcel_id(parcel()) == "65301:001:0001"
    assert parcel_id({}) is None
    assert parcel_id(None) is None
    assert parcel_id({"tunnus": "  "}) is None
    assert parcel_point(parcel()) == (FAR_PT[0], FAR_PT[1])
    assert parcel_point({"lon": "x", "lat": 59.4}) is None


def test_normalise_omvorm_and_mullaklass():
    assert normalise_omvorm("Eraomand") == "Eraomand"
    assert normalise_omvorm("Munitsipaalomand") == "Munitsipaalomand"
    assert normalise_omvorm("Riigiomand") == "Riigiomand"
    assert normalise_omvorm("eraomand") is None  # case-sensitive domain
    assert normalise_omvorm(None) is None
    assert normalise_mullaklass("hea") == "hea"
    assert normalise_mullaklass("HALB") == "halb"
    assert normalise_mullaklass("keskmine") is None
    assert normalise_mullaklass(None) is None


# ---------------------------------------------------------------------------
# p29 / p68 / p71 / p75.
# ---------------------------------------------------------------------------

def test_lot_size_parcel_bands_and_nulls():
    v, r = dim_lot_size_parcel(parcel(pindala=1008.0))
    assert v == 80 and "1008 m²" in r and "hinnang" in r
    assert dim_lot_size_parcel(parcel(pindala=300.0))[0] == 45
    assert dim_lot_size_parcel(parcel(pindala=800.0))[0] == 65
    assert dim_lot_size_parcel(parcel(pindala=2000.0))[0] == 80
    v, r = dim_lot_size_parcel(None)
    assert v is None and "EI OLE" in r and "hinnang" in r
    v, r = dim_lot_size_parcel(parcel(pindala=None))
    assert v is None and "EI OLE" in r
    assert dim_lot_size_parcel(parcel(pindala=-5))[0] is None


def test_soil_boniteet_caps_and_nulls():
    v, r = dim_soil_boniteet(parcel(mullaklass="hea"))
    assert v == 65 and "lagi" in r and "EI OLE" in r
    v, r = dim_soil_boniteet(parcel(mullaklass="halb"))
    assert v == 45 and "uuringut" in r
    v, r = dim_soil_boniteet(parcel(mullaklass=None))
    assert v is None and "EI OLE" in r and "hinnang" in r
    v, r = dim_soil_boniteet(parcel(mullaklass="keskmine"))
    assert v is None and "EI OLE" in r
    assert dim_soil_boniteet(None)[0] is None


def test_easement_burden_counts_and_snapshot_rule():
    v, r = dim_easement_burden(parcel(), [])
    assert v == 70 and "EI OLE" in r and "lagi" in r
    v, _ = dim_easement_burden(
        parcel(), [{"nimi": "Odra tn kasutusõigus"}, {"klass": "TKTV"}])
    assert v == 60
    v, r = dim_easement_burden(
        parcel(), [{"nimi": "a"}, {"nimi": "b"}, {"nimi": "c"}])
    assert v == 40 and "EI OLE" in r  # rule-text leg thin, named
    v, r = dim_easement_burden(parcel(), None)
    assert v is None and "EI OLE" in r and "hinnang" in r
    assert dim_easement_burden(None, [])[0] is None


def test_boundary_markers_recorded_not_found():
    v, r = dim_boundary_markers(parcel(markers=4))
    assert v == 65 and "kirjas" in r and "EI OLE" in r
    assert dim_boundary_markers(parcel(markers=2))[0] == 65
    v, r = dim_boundary_markers(parcel(markers=1))
    assert v == 45 and "mõõdistaja" in r
    assert dim_boundary_markers(parcel(markers=0))[0] == 45
    v, r = dim_boundary_markers(parcel(markers=None))
    assert v is None and "EI OLE" in r and "hinnang" in r
    assert dim_boundary_markers(None)[0] is None


# ---------------------------------------------------------------------------
# p76 / p229 / p364.
# ---------------------------------------------------------------------------

def test_mineral_rights_hint_bands():
    v, r = dim_mineral_rights_hint(parcel(lon=INSIDE_PT[0], lat=INSIDE_PT[1]),
                                   QUARRIES)
    assert v == 50 and "EI OLE" in r and "hinnang" in r
    v, r = dim_mineral_rights_hint(parcel(lon=NEAR_PT[0], lat=NEAR_PT[1]),
                                   QUARRIES)
    assert v == 60 and "jäme" in r
    v, r = dim_mineral_rights_hint(parcel(), QUARRIES)
    assert v is None and "EI OLE" in r  # far proves nothing
    v, r = dim_mineral_rights_hint(parcel(), [])
    assert v is None and "EI OLE" in r
    assert dim_mineral_rights_hint({"tunnus": "x"}, QUARRIES)[0] is None


def test_mineral_severance_hint_stricter_than_p76():
    v, r = dim_mineral_severance_hint(
        parcel(lon=INSIDE_PT[0], lat=INSIDE_PT[1]), QUARRIES)
    assert v == 45 and "KAHTLUS" in r and "EI OLE" in r
    # Near-band exists for p76 but NOT for p229: outside is always NULL.
    v, r = dim_mineral_severance_hint(parcel(lon=NEAR_PT[0], lat=NEAR_PT[1]),
                                      QUARRIES)
    assert v is None and "EI OLE" in r
    v, r = dim_mineral_severance_hint(parcel(), QUARRIES)
    assert v is None and "EI OLE" in r
    assert dim_mineral_severance_hint(parcel(), [])[0] is None


def test_ground_lease_hint_ownership_forms():
    v, r = dim_ground_lease_hint(parcel(omvorm="Eraomand"))
    assert v == 70 and "EI OLE" in r and "lagi" in r
    v, r = dim_ground_lease_hint(parcel(omvorm="Munitsipaalomand"))
    assert v == 50 and "hoonestusõiguse" in r and "EI OLE" in r
    v, _ = dim_ground_lease_hint(parcel(omvorm="Riigiomand"))
    assert v == 50
    v, r = dim_ground_lease_hint(parcel(omvorm=None))
    assert v is None and "EI OLE" in r
    v, r = dim_ground_lease_hint(parcel(omvorm="Segalomand"))
    assert v is None and "EI OLE" in r
    assert dim_ground_lease_hint(None)[0] is None


# ---------------------------------------------------------------------------
# Aggregator.
# ---------------------------------------------------------------------------

def test_score_overturn_maa_keys_and_none_semantics():
    out = score_overturn_maa(parcel(), kkis_hits=[], quarries=QUARRIES)
    assert sorted(out.keys()) == sorted(EXPECTED_KEYS)
    assert out["lot_size_parcel"] == 80
    assert out["mineral_rights_hint"] is None  # far parcel: no hint
    out2 = score_overturn_maa(None, kkis_hits=None, quarries=[])
    assert all(v is None for v in out2.values())
    # [] (searched clean) vs None (no snapshot) differ on p71.
    assert score_overturn_maa(parcel(), kkis_hits=[])["easement_burden"] == 70
    assert score_overturn_maa(
        parcel(), kkis_hits=None)["easement_burden"] is None
