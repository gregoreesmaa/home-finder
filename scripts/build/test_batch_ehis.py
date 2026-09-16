"""Fixture tests for scripts/build/batch_ehis.py (issue #608).

Hermetic: synthetic EHIS oppeasutused + hooned XML only, never network.
"""

import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from batch_ehis import build_sidecar, parse_hooned_rows, parse_type_map

FIX_OPPE = """<oppeasutused>
  <oppeasutus><koolId>101</koolId><tyyp>Põhikool või gümnaasium</tyyp><staatus>Registreeritud</staatus></oppeasutus>
  <oppeasutus><koolId>102</koolId><tyyp>Lasteaed</tyyp><staatus>Registreeritud</staatus></oppeasutus>
  <oppeasutus><koolId>103</koolId><tyyp>Huvikool</tyyp><staatus>Registreeritud</staatus></oppeasutus>
  <oppeasutus><koolId>104</koolId><tyyp>Põhikool või gümnaasium</tyyp><staatus>Suletud</staatus></oppeasutus>
  <oppeasutus><koolId>105</koolId><tyyp>Täienduskoolitusasutus</tyyp><staatus>Registreeritud</staatus></oppeasutus>
</oppeasutused>"""

FIX_HOONED = """<hooned>
  <kool><oppeasutusId>101</oppeasutusId><hooned><hoone>
    <aadress>Harju maakond, Tallinn, Endla tn 4</aadress>
    <koordinaatX>6592287</koordinaatX><koordinaatY>539957</koordinaatY>
  </hoone></hooned></kool>
  <kool><oppeasutusId>102</oppeasutusId><hooned><hoone>
    <aadress>Harju maakond, Tallinn, Sõle tn 1</aadress>
    <koordinaatX>6592800</koordinaatX><koordinaatY>538000</koordinaatY>
  </hoone></hooned></kool>
  <kool><oppeasutusId>103</oppeasutusId><hooned><hoone>
    <aadress>Harju maakond, Tallinn, Kooli tn 2</aadress>
    <koordinaatX>6592500</koordinaatX><koordinaatY>539000</koordinaatY>
  </hoone></hooned></kool>
  <kool><oppeasutusId>104</oppeasutusId><hooned><hoone>
    <aadress>Harju maakond, Tallinn, Vana tee 1</aadress>
    <koordinaatX>6592500</koordinaatX><koordinaatY>539000</koordinaatY>
  </hoone></hooned></kool>
  <kool><oppeasutusId>105</oppeasutusId><hooned><hoone>
    <aadress>Harju maakond, Tallinn, Täienduse 1</aadress>
    <koordinaatX>6592500</koordinaatX><koordinaatY>539000</koordinaatY>
  </hoone></hooned></kool>
  <kool><oppeasutusId>101</oppeasutusId><hooned><hoone>
    <aadress>Tartu maakond, Tartu, Kooli tn 1</aadress>
    <koordinaatX>6470000</koordinaatX><koordinaatY>660000</koordinaatY>
  </hoone></hooned></kool>
  <kool><oppeasutusId>101</oppeasutusId><hooned><hoone>
    <aadress>Harju maakond, Tallinn, Ilma koordinaatideta</aadress>
  </hoone></hooned></kool>
</hooned>"""


def test_type_map_slices_and_drops():
    type_by_id = parse_type_map(ET.fromstring(FIX_OPPE))
    assert type_by_id["101"]["slice"] == "school"
    assert type_by_id["102"]["slice"] == "kindergarten"
    assert type_by_id["103"]["slice"] == "hobby"
    assert type_by_id["104"] == {"tyyp": "Põhikool või gümnaasium",
                                 "status": "Suletud", "slice": None}
    assert type_by_id["105"]["slice"] is None  # adult training, unsliced


def test_hooned_join_filters():
    type_by_id = parse_type_map(ET.fromstring(FIX_OPPE))
    pois, stats = parse_hooned_rows(ET.fromstring(FIX_HOONED), type_by_id)
    by_slice = {}
    for p in pois:
        by_slice.setdefault(p["slice"], []).append(p)
    assert sorted(by_slice) == ["hobby", "kindergarten", "school"]
    assert stats["dropped_closed"] == 1
    assert stats["dropped_other_type"] == 1
    assert stats["dropped_other_county"] == 1
    assert stats["dropped_no_xy"] == 1
    # Tallinn rows project to Tallinn (Harju window, ~1 m honesty).
    assert 59.3 < by_slice["school"][0]["lat"] < 59.6
    assert 24.5 < by_slice["school"][0]["lon"] < 25.0


def test_build_sidecar_shape(tmp_path):
    out = build_sidecar(ET.fromstring(FIX_OPPE), ET.fromstring(FIX_HOONED),
                        str(tmp_path))
    assert out["counts"] == {"school": 1, "kindergarten": 1, "hobby": 1,
                             "total": 3}
    assert out["vintage"] == "2026-09-16"
    assert all(set(p) == {"lat", "lon", "slice"} for p in out["points"])
