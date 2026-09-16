"""P4 EHIS school-proximity dims (issue #530): hermetic tests.

No network: probe evidence lives in docs/p4_ehis_map.md (checked
2026-09-16, both bulk endpoints HTTP 200). Fixtures below mirror the real
feed shape (L-EST97 <koordinaatX/Y>, <tyyp>, <staatus>); tests pin the
type classifier, the join + drop counts, the L-EST97 projection sanity
(Tallinn lands on Tallinn), the distance bands, and NULL-beyond.
"""

import dims_p4_ehis_map as ehis
from dims_p4_ehis_map import (
    P4_EHIS_MAP_DIMS,
    dim_hobby_proximity,
    dim_kindergarten_proximity,
    dim_school_proximity,
    lest97_to_wgs84,
    parse_hooned_xml,
    parse_oppeasutused_xml,
    score_p4_ehis_map,
    type_slice,
)

# Tallinn centre-ish origin; POIs placed ~300 m / ~800 m / ~1.5 km away.
TALLINN = (59.4372, 24.7536)
SCHOOL_POIS = [
    {"kind": "ehis_school", "lat": 59.4390, "lon": 24.7560, "name": "Koolihoone"},
    {"kind": "ehis_kindergarten", "lat": 59.4440, "lon": 24.7600, "name": "Lasteaed"},
    {"kind": "ehis_hobby", "lat": 59.4500, "lon": 24.7700, "name": "Huvikool"},
]

OPPE_FIXTURE = """<avaAndmedResponse><body><oppeasutused>
<oppeasutus><koolId>1</koolId><tyyp>põhikool või gümnaasium</tyyp>
<staatus>Registreeritud</staatus></oppeasutus>
<oppeasutus><koolId>2</koolId><tyyp>lasteaed</tyyp>
<staatus>Registreeritud</staatus></oppeasutus>
<oppeasutus><koolId>3</koolId><tyyp>huvikool</tyyp>
<staatus>Registreeritud</staatus></oppeasutus>
<oppeasutus><koolId>4</koolId><tyyp>põhikool või gümnaasium</tyyp>
<staatus>Suletud</staatus></oppeasutus>
<oppeasutus><koolId>5</koolId><tyyp>täienduskoolitusasutus</tyyp>
<staatus>Registreeritud</staatus></oppeasutus>
</oppeasutused></body></avaAndmedResponse>"""

# Real L-EST97 coords from the 2026-09-16 probe (Nõmme tee 49, Kristiine).
HOONED_FIXTURE = """<avaAndmedResponse><body>
<kool><oppeasutusId>1</oppeasutusId><hooned><hoone>
<nimetus>koolihoone</nimetus><ehrKood>101021077</ehrKood>
<adsOid>EE00640694</adsOid>
<aadress>Harju maakond, Tallinn, Kristiine linnaosa, Nõmme tee 49</aadress>
<peahoone>jah</peahoone><muudetud>09.09.2021</muudetud>
<adsAdrId>2120867</adsAdrId>
<koordinaatX>6586642.22</koordinaatX><koordinaatY>540867.94</koordinaatY>
</hoone></hooned></kool>
<kool><oppeasutusId>2</oppeasutusId><hooned><hoone>
<nimetus>lasteaiahoone</nimetus>
<aadress>Harju maakond, Tallinn, Kristiine linnaosa, Kännu tn 67</aadress>
<koordinaatX>6585876.70</koordinaatX><koordinaatY>540286.30</koordinaatY>
</hoone></hooned></kool>
<kool><oppeasutusId>4</oppeasutusId><hooned><hoone>
<nimetus>suletud kool</nimetus>
<koordinaatX>6586642.22</koordinaatX><koordinaatY>540867.94</koordinaatY>
</hoone></hooned></kool>
<kool><oppeasutusId>5</oppeasutusId><hooned><hoone>
<nimetus>täienduskeskus</nimetus>
<koordinaatX>6586642.22</koordinaatX><koordinaatY>540867.94</koordinaatY>
</hoone></hooned></kool>
<kool><oppeasutusId>1</oppeasutusId><hooned><hoone>
<nimetus>koordinaadita abihoone</nimetus>
</hoone></hooned></kool>
</body></avaAndmedResponse>"""


def test_type_slice_pins_slices_from_feed_strings():
    assert type_slice("põhikool või gümnaasium", "Registreeritud") == "school"
    assert type_slice("lasteaed", "Registreeritud") == "kindergarten"
    assert type_slice("koolieelne lasteasutus", "Registreeritud") == "kindergarten"
    assert type_slice("lastehoid", "Registreeritud") == "kindergarten"
    assert type_slice("huvikool", "Registreeritud") == "hobby"
    # Closed, adult/vocational/higher, camps, branches, unknown: never sliced.
    assert type_slice("põhikool või gümnaasium", "Suletud") is None
    for tyyp in ("täienduskoolitusasutus", "kutseõppeasutus", "rakenduskõrgkool",
                 "ülikool", "noortelaager", "filiaal", "Määramata", "", None):
        assert type_slice(tyyp, "Registreeritud") is None, tyyp
    assert type_slice("huvikool", "Suletud") is None


def test_parse_oppeasutused_indexes_five_rows():
    by_id = parse_oppeasutused_xml(OPPE_FIXTURE)
    assert len(by_id) == 5
    assert by_id["1"]["slice"] == "school"
    assert by_id["2"]["slice"] == "kindergarten"
    assert by_id["3"]["slice"] == "hobby"
    assert by_id["4"]["slice"] is None  # Suletud
    assert by_id["5"]["slice"] is None  # adult training


def test_parse_hooned_joins_places_and_counts_drops():
    by_id = parse_oppeasutused_xml(OPPE_FIXTURE)
    pois, stats = parse_hooned_xml(HOONED_FIXTURE, by_id)
    assert stats["rows"] == 5
    assert stats["placed"] == 2
    assert stats["dropped_no_xy"] == 1
    assert stats["dropped_closed"] == 1
    assert stats["dropped_other_type"] == 1
    kinds = sorted(p["kind"] for p in pois)
    assert kinds == ["ehis_kindergarten", "ehis_school"]
    school = next(p for p in pois if p["kind"] == "ehis_school")
    # Nõmme tee 49, Kristiine: projection must land in Tallinn, EHR kept.
    assert 59.3 < school["lat"] < 59.5 and 24.6 < school["lon"] < 24.9
    assert school["ehr"] == "101021077"
    assert "Nõmme tee 49" in school["address"]


def test_lest97_projection_matches_known_tallinn_point():
    # Probe row: Nõmme tee 49 (6586642.22, 540867.94) ~ Kristiine, Tallinn.
    # Verified against pyproj EPSG:3301->EPSG:4326: (59.415698, 24.719748).
    lat, lon = lest97_to_wgs84(6586642.22, 540867.94)
    assert abs(lat - 59.415698) < 0.0005 and abs(lon - 24.719748) < 0.0005


def test_bands_and_null_beyond_pinned():
    # ~300 m -> 80; kinds ~800 m / ~1.5 km away score their own bands.
    v, reason = dim_school_proximity(TALLINN, SCHOOL_POIS)
    assert v == 80
    assert "linnulennult" in reason and "kvaliteedi" in reason
    v, _ = dim_kindergarten_proximity(TALLINN, SCHOOL_POIS)
    assert v == 65
    v, _ = dim_hobby_proximity(TALLINN, SCHOOL_POIS)
    assert v == 50
    # Far away from everything -> NULL, never a "bad school" score.
    far = (59.0, 24.0)
    for fn in (dim_school_proximity, dim_kindergarten_proximity, dim_hobby_proximity):
        v, reason = fn(far, SCHOOL_POIS)
        assert v is None
        assert "EI OLE" in reason and "2 km" in reason


def test_missing_origin_and_missing_kind_are_null_with_ei_ole():
    v, r = dim_school_proximity(None, SCHOOL_POIS)
    assert v is None and "EI OLE" in r
    v, r = dim_school_proximity(TALLINN, [{"kind": "cafe", "lat": 59.43, "lon": 24.75}])
    assert v is None and "EI OLE" in r
    v, r = dim_kindergarten_proximity(TALLINN, None)
    assert v is None and "EI OLE" in r


def test_registry_and_aggregator_cover_all_three():
    assert [k for k, _, _ in P4_EHIS_MAP_DIMS] == [
        "school_proximity", "kindergarten_proximity", "hobby_proximity"]
    assert [p for _, p, _ in P4_EHIS_MAP_DIMS] == ["P4-011"] * 3
    out = score_p4_ehis_map(TALLINN, SCHOOL_POIS)
    assert out == {"school_proximity": 80, "kindergarten_proximity": 65,
                   "hobby_proximity": 50}
    out = score_p4_ehis_map(None, None)
    assert all(v is None for v in out.values())


def test_reasons_never_claim_quality_or_language():
    for fn in (dim_school_proximity, dim_kindergarten_proximity, dim_hobby_proximity):
        _, reason = fn(TALLINN, SCHOOL_POIS)
        assert "garanteeritud" not in reason and "mõõdetud kvaliteet" not in reason
        assert "keele" not in reason.lower()
