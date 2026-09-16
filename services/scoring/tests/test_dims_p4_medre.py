"""P4 medre primary-care dims (issue #532): hermetic tests.

No network: probe evidence lives in docs/p4_medre.md (checked 2026-09-16;
GP bulk 782 nimistu + companies bulk 1572 asutus, both HTTP 200, NO
coordinate or status columns in either). Fixtures mirror the real feed
shapes with SYNTHETIC names (never real GP/patient data); tests pin the
readers (incl. the zero-coords honesty stats), the bands, NULL-beyond,
and the documented-NULL status leg.
"""

import dims_p4_medre as medre
from dims_p4_medre import (
    P4_MEDRE_DIMS,
    dim_gp_clinic_proximity,
    dim_gp_open_status,
    dim_gp_proximity,
    parse_companies_xml,
    parse_nimistud_xml,
    score_p4_medre,
)

TALLINN = (59.4372, 24.7536)
POIS = [
    {"kind": "medre_gp", "lat": 59.4390, "lon": 24.7560,
     "address": "Harju maakond, Keila linn, Tallinna mnt 18"},
    {"kind": "medre_gp_clinic", "lat": 59.4440, "lon": 24.7600,
     "address": "Harju maakond, Tallinn, Mustamae linnaosa, Ehitajate tee 1"},
]

NIMISTUD_FIXTURE = """<nimistud hetk="2026-09-16T02:10:02">
<nimistu><kood>N0001</kood>
<perearst><kood>D00001</kood><eesnimi>MARI</eesnimi><perenimi>METS</perenimi></perearst>
<teeninduspiirkonnad><teeninduspiirkond><nimi>Keila linn</nimi></teeninduspiirkond></teeninduspiirkonnad>
<vastuvott><kohad><koht><adr_id>3651237</adr_id>
<adr_kood>372960000000000CH0000CZ2V00000000</adr_kood>
<adr_tekst>Harju maakond, Keila linn, Tallinna mnt 18</adr_tekst>
</koht></kohad></vastuvott><tootajad/></nimistu>
<nimistu><kood>N0002</kood>
<perearst><kood>D00002</kood><eesnimi>JUHAN</eesnimi><perenimi>KUUSK</perenimi></perearst>
<teeninduspiirkonnad><teeninduspiirkond><nimi>Saue vald</nimi></teeninduspiirkond></teeninduspiirkonnad>
<vastuvott><kohad/></vastuvott><tootajad/></nimistu>
</nimistud>"""

COMPANIES_FIXTURE = """<asutused hetk="2026-09-16T02:05:08">
<asutus><registrikood>10000001</registrikood><nimi>Naitus Perearstikeskus</nimi>
<aadress>Harju maakond, Tallinn, Mustamae linnaosa, Ehitajate tee 1</aadress>
<tegevusload><tegevusluba><tegevusloa_number>L00001</tegevusloa_number>
<loaliik_nimi>Üldarstiabi</loaliik_nimi>
<tegevuskohad><tegevuskoht>
<aadress>Harju maakond, Tallinn, Mustamae linnaosa, Ehitajate tee 1</aadress>
<teenused><teenus><kood>T0001</kood><nimi>uldarstiabi teenus</nimi></teenus></teenused>
</tegevuskoht></tegevuskohad></tegevusluba>
<tegevusluba><tegevusloa_number>L00002</tegevusloa_number>
<loaliik_nimi>Eriarstiabi</loaliik_nimi>
<tegevuskohad><tegevuskoht><aadress>Harju maakond, Tallinn, Ehitajate tee 1</aadress>
</tegevuskoht></tegevuskohad></tegevusluba>
</tegevusload></asutus></asutused>"""


def test_parse_nimistud_extracts_join_refs_and_zero_coords():
    points, stats = parse_nimistud_xml(NIMISTUD_FIXTURE)
    assert stats["nimistu"] == 2
    assert stats["kohad"] == 1
    assert stats["harju_kohad"] == 1
    assert stats["with_coords"] == 0  # feed ships none — AKS join needed
    pt = points[0]
    assert pt["nimistu"] == "N0001"
    assert pt["adr_id"] == "3651237"
    assert pt["address"].startswith("Harju maakond")
    assert pt["piirkonnad"] == ["Keila linn"]


def test_parse_companies_keeps_only_uldarstiabi():
    points, stats = parse_companies_xml(COMPANIES_FIXTURE)
    assert stats["asutus"] == 1
    assert stats["harju_asutus"] == 1
    assert stats["uldarstiabi_kohad"] == 1
    assert stats["other_licences"] == 1  # Eriarstiabi counted, never scored
    assert stats["with_coords"] == 0
    pt = points[0]
    assert pt["licence"] == "L00001"
    assert pt["teenused"] == ["uldarstiabi teenus"]


def test_bands_and_null_beyond_pinned():
    v, reason = dim_gp_proximity(TALLINN, POIS)
    assert v == 80
    assert "AKS-liidetud" in reason and "kvaliteedi" in reason
    v, _ = dim_gp_clinic_proximity(TALLINN, POIS)
    assert v == 65
    far = (59.0, 24.0)
    for fn in (dim_gp_proximity, dim_gp_clinic_proximity):
        v, reason = fn(far, POIS)
        assert v is None
        assert "EI OLE" in reason and "2 km" in reason


def test_missing_origin_and_unjoined_are_null_with_ei_ole():
    v, r = dim_gp_proximity(None, POIS)
    assert v is None and "EI OLE" in r
    v, r = dim_gp_proximity(TALLINN, [{"kind": "cafe", "lat": 59.43, "lon": 24.75}])
    assert v is None and "EI OLE" in r
    assert "AKS" in r  # the join gap is named, never hidden


def test_open_status_is_documented_null_for_every_input():
    for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                         (None, POIS), (TALLINN, None)]:
        v, reason = dim_gp_open_status(origin, pois)
        assert v is None
        assert "EI OLE" in reason
        assert "Tervisekassa" in reason
        assert "kraapimist" in reason or "kraapimine" in reason


def test_registry_and_aggregator_cover_all_three():
    assert [k for k, _, _ in P4_MEDRE_DIMS] == [
        "gp_proximity", "gp_clinic_proximity", "gp_open_status"]
    assert [p for _, p, _ in P4_MEDRE_DIMS] == ["P4-011"] * 3
    out = score_p4_medre(TALLINN, POIS)
    assert out == {"gp_proximity": 80, "gp_clinic_proximity": 65,
                   "gp_open_status": None}
    out = score_p4_medre(None, None)
    assert all(v is None for v in out.values())


def test_reasons_never_claim_quality_or_status():
    for fn in (dim_gp_proximity, dim_gp_clinic_proximity):
        _, reason = fn(TALLINN, POIS)
        assert "garanteeritud" not in reason
        assert "avatud nimistu" not in reason
        assert "mitte kvaliteedi" in reason
