"""Fixture tests for scripts/build/batch_sport.py (issue #607).

Hermetic: synthetic Spordiregister JSON + ujulad XML only, never network.
"""

import json
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from batch_sport import build_sidecar, parse_ujulad_rows, parse_venue_rows

FIX_JSON = json.dumps([
    {"maakond": "Harjumaa", "ehstaatus": "Spordialases kasutuses",
     "liik": "Võimla, spordihall", "kaart_laius": "59,4374",
     "kaart_pikkus": "24,7454"},
    {"maakond": "Harjumaa", "ehstaatus": "Spordialases kasutuses",
     "liik": "Siseujula, Võimla, spordihall, spordisaal",
     "kaart_laius": 59.43, "kaart_pikkus": 24.73},
    {"maakond": "Harjumaa", "ehstaatus": "Spordialases kasutuses",
     "liik": "Staadion", "kaart_laius": "59.44", "kaart_pikkus": "24.75"},
    {"maakond": "Harjumaa", "ehstaatus": "Spordialases kasutuses",
     "liik": "Muu sportimiseks kasutatav objekt", "kaart_laius": "59.44",
     "kaart_pikkus": "24.75"},
    {"maakond": "Harjumaa", "ehstaatus": "Suletud",
     "liik": "Võimla", "kaart_laius": "59.44", "kaart_pikkus": "24.75"},
    {"maakond": "Harjumaa", "ehstaatus": "Spordialases kasutuses",
     "liik": "Võimla", "kaart_laius": "", "kaart_pikkus": ""},
    {"maakond": "Tartumaa", "ehstaatus": "Spordialases kasutuses",
     "liik": "Võimla", "kaart_laius": "58.38", "kaart_pikkus": "26.72"},
])

FIX_XML = """<ujulad>
  <ujula><nimetus>Endla</nimetus><tyyp>uldkasutatav</tyyp>
    <koordinaadid><koordinaat><x>6592447</x><y>539957</y></koordinaat></koordinaadid>
    <viimane_inspekteerimine>2026-05-01</viimane_inspekteerimine></ujula>
  <ujula><nimetus>Ilma veeta</nimetus><tyyp>kooli</tyyp>
    <koordinaadid><koordinaat><x></x><y></y></koordinaat></koordinaadid></ujula>
</ujulad>"""


def test_venue_slices_and_filters():
    pois, stats = parse_venue_rows(json.loads(FIX_JSON))
    by_slice = {}
    for p in pois:
        by_slice.setdefault(p["slice"], []).append(p)
    # hall: row 1 + row 2 combo; pool: row 2 combo; field: row 3.
    assert len(by_slice.get("hall", [])) == 2
    assert len(by_slice.get("pool", [])) == 1
    assert len(by_slice.get("field", [])) == 1
    assert stats["dropped_other_type"] == 1
    assert stats["dropped_inactive"] == 1
    assert stats["dropped_no_xy"] == 1
    assert stats["dropped_other_county"] == 1
    lat, lon = by_slice["hall"][0]["lat"], by_slice["hall"][0]["lon"]
    assert abs(lat - 59.4374) < 1e-9 and abs(lon - 24.7454) < 1e-9


def test_ujulad_rows_project_and_drop_coordless():
    root = ET.fromstring(FIX_XML)
    pois, stats = parse_ujulad_rows(root)
    assert stats["rows"] == 2
    assert stats["dropped_no_xy"] == 1
    assert len(pois) == 1 and pois[0]["slice"] == "pool"
    # Fixture (x=6592447, y=539957) verified against pyproj 3.6.1
    # EPSG:3301->4326 on 2026-09-16 (agreement to 14 decimals).
    assert abs(pois[0]["lat"] - 59.467887) < 1e-6
    assert abs(pois[0]["lon"] - 24.704780) < 1e-6


def test_build_sidecar_shape(tmp_path):
    out = build_sidecar(json.loads(FIX_JSON), ET.fromstring(FIX_XML),
                         str(tmp_path))
    assert out["counts"]["hall"] == 2
    assert out["counts"]["pool"] == 2  # 1 register combo + 1 ujulad
    assert out["counts"]["field"] == 1
    assert out["vintage"] == "2026-09-16"
    assert all(set(p) == {"lat", "lon", "slice"} for p in out["points"])
