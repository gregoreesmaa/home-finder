"""Hermetic tests for scripts/build/batch_poi.py (issue #612).

Covers ONLY the pure parser/sidecar builder -- the network pull
(fetch_cached) is never called here (AGENTS.md section 7.6).
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_poi import (  # noqa: E402
    POI_LICENCE,
    POI_TYPES,
    build_sidecar,
    parse_features,
)


FIXTURE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/fes/2.0"
    xmlns:huvipunkt="maaruum.huvipunkt" xmlns:gml="http://www.opengis.net/gml/3.2">
  <huvipunkt:raamatukogu gml:id="raamatukogu.1">
    <huvipunkt:pikkus>24.745400</huvipunkt:pikkus>
    <huvipunkt:laius>59.437400</huvipunkt:laius>
    <huvipunkt:nimi>Secret Library (never committed)</huvipunkt:nimi>
    <huvipunkt:aadress>Secret Street 1 (never committed)</huvipunkt:aadress>
    <huvipunkt:grupp>raamatukogu</huvipunkt:grupp>
    <huvipunkt:alamgrupp>rahvaraamatukogu</huvipunkt:alamgrupp>
    <huvipunkt:allikas>Eesti Rahvusraamatukogu</huvipunkt:allikas>
    <huvipunkt:andmeseis>03.11.2025</huvipunkt:andmeseis>
  </huvipunkt:raamatukogu>
  <huvipunkt:raamatukogu gml:id="raamatukogu.2">
    <huvipunkt:pikkus></huvipunkt:pikkus>
    <huvipunkt:laius></huvipunkt:laius>
    <huvipunkt:alamgrupp>teadus- ja erialaraamatukogu</huvipunkt:alamgrupp>
    <huvipunkt:allikas>Eesti Rahvusraamatukogu</huvipunkt:allikas>
    <huvipunkt:andmeseis>17.11.2025</huvipunkt:andmeseis>
  </huvipunkt:raamatukogu>
  <huvipunkt:raamatukogu gml:id="raamatukogu.3">
    <huvipunkt:pikkus>12.0</huvipunkt:pikkus>
    <huvipunkt:laius>55.0</huvipunkt:laius>
    <huvipunkt:alamgrupp>rahvaraamatukogu</huvipunkt:alamgrupp>
    <huvipunkt:allikas>Eesti Rahvusraamatukogu</huvipunkt:allikas>
    <huvipunkt:andmeseis>03.11.2025</huvipunkt:andmeseis>
  </huvipunkt:raamatukogu>
</wfs:FeatureCollection>
"""


def _write_fixture(tmp_path):
    path = tmp_path / "harju-raamatukogu.xml"
    path.write_text(FIXTURE_XML, encoding="utf-8")
    return str(path)


def test_parse_plots_coordinated_drops_rest(tmp_path):
    points, stats = parse_features(_write_fixture(tmp_path),
                                   "raamatukogu", "library")
    assert stats["features"] == 3
    assert stats["plotted"] == 1
    # Empty coords + far-outside-Estonia coords both drop, counted.
    assert stats["dropped_no_coord"] == 2
    assert points == [{"lat": 59.4374, "lon": 24.7454, "slice": "library"}]


def test_parse_builds_staleness_tables(tmp_path):
    # Feed-level tallies cover dropped features too (upstream vintage,
    # not the map).
    _, stats = parse_features(_write_fixture(tmp_path),
                              "raamatukogu", "library")
    assert stats["stamps"] == {"03.11.2025": 2, "17.11.2025": 1}
    assert stats["sources"] == {"Eesti Rahvusraamatukogu": 3}
    assert stats["subgroups"] == {"rahvaraamatukogu": 2,
                                  "teadus- ja erialaraamatukogu": 1}


def test_parse_never_emits_names_or_addresses(tmp_path):
    points, _ = parse_features(_write_fixture(tmp_path),
                               "raamatukogu", "library")
    blob = json.dumps(points, ensure_ascii=False)
    assert "Secret" not in blob
    assert "nimi" not in blob and "aadress" not in blob


def test_build_sidecar_stamps_licence(tmp_path):
    points = [{"lat": 59.4374, "lon": 24.7454, "slice": "library"}]
    per_type = {"library": {"features": 3, "plotted": 1,
                            "dropped_no_coord": 2}}
    doc = build_sidecar(points, per_type, "2026-09-16", str(tmp_path))
    assert doc["licence"] == POI_LICENCE
    assert "maaamet.ee/avaandmete-litsents" in doc["licence"]
    assert doc["vintage"] == "2026-09-16"
    on_disk = json.load(open(tmp_path / "poi" / "poi-points.json",
                             encoding="utf-8"))
    assert on_disk["points"] == points
    assert on_disk["counts"] == per_type


def test_harvest_types_are_long_tail_only():
    # Dedicated #527/#528/#530/#531/#532 types are never pulled here
    # (scorer DEDICATED_SPLIT owns the refusal; the harvest mirrors
    # LONG_TAIL so the two cannot drift).
    import dims_p4_poi as poi

    harvested = {t for t, _ in POI_TYPES}
    assert harvested == set(poi.LONG_TAIL)
    assert not (harvested & set(poi.DEDICATED_SPLIT))
