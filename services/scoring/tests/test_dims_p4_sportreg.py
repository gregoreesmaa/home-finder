"""P4 sport-proximity dims (issue #531): hermetic tests.

No network: probe evidence lives in docs/p4_sportreg.md (checked
2026-09-16; Spordiregister JSON 4157 venues + vtiav ujulad XML 226 rows,
both HTTP 200). Fixtures mirror the real feed shapes; tests pin the
liik slicer (incl. combo venues), the readers + drop counts, the bands,
and NULL-beyond.
"""

import json

import dims_p4_sportreg as sportreg
from dims_p4_sportreg import (
    P4_SPORTREG_DIMS,
    dim_sport_field,
    dim_sport_hall,
    dim_sport_pool,
    dim_ujulad_pool,
    parse_spordiehitised_json,
    parse_ujulad_xml,
    score_p4_sportreg,
    venue_slices,
)

TALLINN = (59.4372, 24.7536)
POIS = [
    {"kind": "sport_hall", "lat": 59.4390, "lon": 24.7560, "name": "Hall"},
    {"kind": "sport_field", "lat": 59.4440, "lon": 24.7600, "name": "Valjak"},
    {"kind": "sport_pool", "lat": 59.4500, "lon": 24.7700, "name": "Ujula"},
    {"kind": "ujulad_pool", "lat": 59.4390, "lon": 24.7560, "name": "T-ujula",
     "inspected": "18.10.2023"},
]

SPORT_FIXTURE = json.dumps([
    {"rajatisnimi": "Hall", "liik": "Võimla, spordihall, spordisaal",
     "ehstaatus": "Spordialases kasutuses", "kaart_laius": "59.4390",
     "kaart_pikkus": "24.7560", "aadress": "Tallinn", "maakond": "Harjumaa"},
    {"rajatisnimi": "Combo", "liik": "Siseujula, Võimla, spordihall, spordisaal",
     "ehstaatus": "Spordialases kasutuses", "kaart_laius": 59.44,
     "kaart_pikkus": 24.76, "aadress": "Tallinn", "maakond": "Harjumaa"},
    {"rajatisnimi": "Staadion", "liik": "Staadion, Välispalliväljak",
     "ehstaatus": "Spordialases kasutuses", "kaart_laius": "59.45",
     "kaart_pikkus": "24.77", "aadress": "Tallinn", "maakond": "Harjumaa"},
    {"rajatisnimi": "Abihoone", "liik": "Spordi abihoone",
     "ehstaatus": "Spordialases kasutuses", "kaart_laius": "59.45",
     "kaart_pikkus": "24.77", "aadress": "Tallinn", "maakond": "Harjumaa"},
    {"rajatisnimi": "Suletud", "liik": "Võimla, spordihall, spordisaal",
     "ehstaatus": "Suletud", "kaart_laius": "59.45",
     "kaart_pikkus": "24.77", "aadress": "Tallinn", "maakond": "Harjumaa"},
    {"rajatisnimi": "Koordita", "liik": "Staadion",
     "ehstaatus": "Spordialases kasutuses", "kaart_laius": "",
     "kaart_pikkus": "", "aadress": "Tallinn", "maakond": "Harjumaa"},
])

UJULAD_FIXTURE = """<ujulad><ujula><id>171</id><nimetus>Adeli Terviseklubi</nimetus>
<aadress>Endla tn 4, 10142 Kesklinna linnaosa, Tallinn</aadress>
<koordinaadid><koordinaat><x>6588305.000</x><y>541794.000</y></koordinaat></koordinaadid>
<tyyp>tervishoiuasutus</tyyp><viimane_inspekteerimine>19.04.2023</viimane_inspekteerimine>
</ujula><ujula><id>999</id><nimetus>Koordita ujula</nimetus>
<aadress>Tallinn</aadress><tyyp>üldkasutatav</tyyp>
</ujula></ujulad>"""


def test_venue_slices_pins_feed_liik_values():
    assert venue_slices("Võimla, spordihall, spordisaal",
                        "Spordialases kasutuses") == ["hall"]
    assert venue_slices("Siseujula", "Spordialases kasutuses") == ["pool"]
    assert venue_slices("Siseujula, Võimla, spordihall, spordisaal",
                        "Spordialases kasutuses") == ["pool", "hall"]
    assert venue_slices("Staadion, Välispalliväljak",
                        "Spordialases kasutuses") == ["field"]
    assert venue_slices("Sportliku liikumise püsirada",
                        "Spordialases kasutuses") == ["field"]
    # Unsliced kinds, inactive venues, garbage: never scored.
    for liik in ("Muu sportimiseks kasutatav objekt", "Spordi abihoone",
                 "Muu hoones asuv spordiobjekt", "", None):
        assert venue_slices(liik, "Spordialases kasutuses") == [], liik
    assert venue_slices("Võimla, spordihall, spordisaal", "Suletud") == []
    assert venue_slices("Staadion", None) == []


def test_parse_sport_json_places_and_counts_drops():
    pois, stats = parse_spordiehitised_json(SPORT_FIXTURE)
    assert stats["rows"] == 6
    assert stats["dropped_other_type"] == 1  # abihoone
    assert stats["dropped_inactive"] == 1  # suletud
    assert stats["dropped_no_xy"] == 1  # koordita
    assert stats["placed"] == 4  # hall + combo x2 + staadion
    kinds = sorted(p["kind"] for p in pois)
    assert kinds == ["sport_field", "sport_hall", "sport_hall", "sport_pool"]
    combo_pool = next(p for p in pois if p["kind"] == "sport_pool")
    assert combo_pool["name"] == "Combo" and combo_pool["lat"] == 59.44


def test_parse_ujulad_projects_and_counts_drops():
    pois, stats = parse_ujulad_xml(UJULAD_FIXTURE)
    assert stats == {"rows": 2, "placed": 1, "dropped_no_xy": 1}
    pool = pois[0]
    assert pool["kind"] == "ujulad_pool"
    # Endla tn 4, Tallinn (pyproj EPSG:3301->EPSG:4326: 59.430533, 24.736377).
    assert abs(pool["lat"] - 59.430533) < 0.0005
    assert abs(pool["lon"] - 24.736377) < 0.0005
    assert pool["inspected"] == "19.04.2023"


def test_bands_and_null_beyond_pinned():
    assert dim_sport_hall(TALLINN, POIS)[0] == 80
    assert dim_sport_field(TALLINN, POIS)[0] == 65
    assert dim_sport_pool(TALLINN, POIS)[0] == 50
    assert dim_ujulad_pool(TALLINN, POIS)[0] == 80
    v, reason = dim_ujulad_pool(TALLINN, POIS)
    assert "18.10.2023" in reason  # inspection vintage cited, never graded
    far = (59.0, 24.0)
    for fn in (dim_sport_hall, dim_sport_field, dim_sport_pool, dim_ujulad_pool):
        v, reason = fn(far, POIS)
        assert v is None
        assert "EI OLE" in reason and "2 km" in reason


def test_missing_origin_and_missing_kind_are_null_with_ei_ole():
    v, r = dim_sport_hall(None, POIS)
    assert v is None and "EI OLE" in r
    v, r = dim_sport_pool(TALLINN, [{"kind": "cafe", "lat": 59.43, "lon": 24.75}])
    assert v is None and "EI OLE" in r


def test_registry_and_aggregator_cover_all_four():
    assert [k for k, _, _ in P4_SPORTREG_DIMS] == [
        "sport_hall", "sport_field", "sport_pool", "ujulad_pool"]
    assert [p for _, p, _ in P4_SPORTREG_DIMS] == ["P4-048"] * 4
    out = score_p4_sportreg(TALLINN, POIS)
    assert out == {"sport_hall": 80, "sport_field": 65, "sport_pool": 50,
                   "ujulad_pool": 80}
    out = score_p4_sportreg(None, None)
    assert all(v is None for v in out.values())


def test_reasons_name_buyer_checks_not_hours_or_prices():
    for fn in (dim_sport_hall, dim_sport_field, dim_sport_pool, dim_ujulad_pool):
        _, reason = fn(TALLINN, POIS)
        assert "linnulennult" in reason
        assert "lahtiolekuajad" in reason or "ajakava" in reason
        assert "garanteeritud" not in reason
