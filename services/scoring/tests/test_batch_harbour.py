"""Hermetic tests for scripts/build/batch_harbour.py (issue #627).

No network: synthetic WFS members + inline register rows. Pins the
N,E axis swap, the publicId join, the function-enum gate, and the
builds-nothing rules.
"""

import os
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_harbour import (  # noqa: E402
    FUNCTION_LABEL,
    build,
    main,
    parse_nodes,
    read_ais_cells,
)


def _ais_zip(path, shp_name="ais_2024_density.shp", rlen=119,
             pleasure=b"53", all_n=b"100"):
    """One-cell synthetic AIS zip (3301 centroid near Pirita)."""
    content = struct.pack("<i", 5) + struct.pack(
        "<4d", 546000.0, 6592000.0, 546500.0, 6592500.0)
    rwords = len(content) // 2
    shp = (b"\x00" * 100 + struct.pack(">2i", 1, rwords) + content)
    hlen = 32
    rec = bytearray(b" " * rlen)
    rec[1:11] = all_n.ljust(10, b" ")[:10]
    rec[41:51] = pleasure.ljust(10, b" ")[:10]
    dbf = (b"\x03\x19\x09\x11" + struct.pack("<IHH", 1, hlen, rlen)
           + b"\x00" * (hlen - 12) + bytes(rec))
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(shp_name, shp)
        zf.writestr(shp_name[:-4] + ".dbf", dbf)
    return str(path)


def test_read_ais_cells_parses_synthetic_zip(tmp_path):
    zp = _ais_zip(tmp_path / "ais.zip")
    cells = read_ais_cells(zp)
    assert len(cells) == 1
    assert cells[0]["pleasure"] == 53
    assert cells[0]["all"] == 100
    assert 24.55 <= cells[0]["lon"] <= 25.10
    assert 59.35 <= cells[0]["lat"] <= 59.55


def test_read_ais_cells_missing_vintage_fails_clean(tmp_path):
    zp = _ais_zip(tmp_path / "ais.zip", shp_name="ais_2023_density.shp")
    with pytest.raises(ValueError, match="no 2024 .shp"):
        read_ais_cells(zp)


def test_read_ais_cells_record_drift_fails_loud(tmp_path):
    zp = _ais_zip(tmp_path / "ais.zip", rlen=100)
    with pytest.raises(ValueError, match="record-length drift"):
        read_ais_cells(zp)

WFS = """<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:TN_sadam="urn:x">
<wfs:member><TN_sadam:PortNode gml:id="n1"><TN_sadam:gml_id>EE-PIR_168</TN_sadam:gml_id><TN_sadam:spellingofname_text xmlns:TN_sadam="urn:x">PIRITA SADAM</TN_sadam:spellingofname_text><TN_sadam:geom><gml:Point srsName="x"><gml:pos>6592572.0 546582.0</gml:pos></gml:Point></TN_sadam:geom></TN_sadam:PortNode></wfs:member>
<wfs:member><TN_sadam:PortNode gml:id="n2"><TN_sadam:gml_id>EE-XXX_166</TN_sadam:gml_id><TN_sadam:spellingofname_text xmlns:TN_sadam="urn:x">VANASADAM</TN_sadam:spellingofname_text><TN_sadam:geom><gml:Point srsName="x"><gml:pos>6593000.0 540000.0</gml:pos></gml:Point></TN_sadam:geom></TN_sadam:PortNode></wfs:member>
</wfs:FeatureCollection>"""

PORTS = [
    {"publicId": 168, "name": "PIRITA SADAM", "portFunction": 2,
     "address": "Purje tn 13"},
    {"publicId": 166, "name": "VANASADAM", "portFunction": 1,
     "address": "Sadama tn 25"},
    {"publicId": 999, "name": "GHOST SADAM", "portFunction": 2,
     "address": "Nowhere"},
    {"publicId": 168, "name": "BAD FN", "portFunction": 9,
     "address": "Nowhere"},
]


def test_parse_nodes_swaps_ne_and_keys_public_id():
    nodes = parse_nodes(WFS.encode())
    assert set(nodes) == {"168", "166"}
    # 3301 (E 546582, N 6592572) -> Tallinn lon/lat, not swapped.
    assert 24.5 < nodes["168"]["lon"] < 25.0
    assert 59.3 < nodes["168"]["lat"] < 59.6


def test_build_joins_and_gates():
    doc = build(PORTS, parse_nodes(WFS.encode()), [])
    assert doc["stats"] == {"ports": 2, "unplaced": 2, "cells": 0}
    by_id = {p["harbour_id"]: p for p in doc["ports"]}
    assert by_id["port-168"]["function_label"] == FUNCTION_LABEL[2]
    assert by_id["port-166"]["function"] == 1
    # Ghost (no node) and bad-function rows count unplaced, never join.


def test_main_writes_nothing_without_ports(tmp_path, capsys):
    (tmp_path / "empty.json").write_text("[]")
    rc = main(["--ports-json", str(tmp_path / "empty.json"),
               "--nodes-xml", str(tmp_path / "empty.json"),
               "--snap", str(tmp_path / "snap")])
    assert rc == 1
    assert "NOTHING" in capsys.readouterr().out
