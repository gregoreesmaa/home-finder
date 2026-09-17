"""Hermetic tests for scripts/build/batch_buildings.py (issue #621).

No network, no snapshot files: inline CityGML fixtures only.
"""

import base64
import math
import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_buildings import (  # noqa: E402
    DST_BBOX,
    DST_COLS,
    DST_ROWS,
    MUNIS,
    build_sidecar,
    fill_rings,
    height_class,
    main,
    parse_zip,
)

GML_HEAD = """<?xml version="1.0" encoding="UTF-8"?>
<core:CityModel xmlns:core="http://www.opengis.net/citygml/2.0" xmlns:bldg="http://www.opengis.net/citygml/building/2.0" xmlns:gen="http://www.opengis.net/citygml/generics/2.0" xmlns:gml="http://www.opengis.net/gml">
"""

GML_TAIL = "</core:CityModel>\n"


def building_xml(height, year, rings_neh):
    """One LoD1 block: walls (spanning z) + flat roof at h.

    rings_neh: list of (kind, [(n, e), ...]) with kind exterior/interior.
    Wall quads span 0..h; roof lies at h. Coordinates are (N, E) axis
    order per EPSG:3301 — the axis trap is the point of the test.
    """
    polys = ""
    for kind, ring in rings_neh:
        pts = " ".join("%f %f %f" % (n, e, height) for n, e in ring)
        polys += ("<gml:Polygon><gml:%s><gml:LinearRing><gml:posList>%s"
                  "</gml:posList></gml:LinearRing></gml:%s></gml:Polygon>") % (kind, pts, kind)
    # one wall quad (z spans 0..h — never roof)
    n0, e0 = rings_neh[0][1][0]
    n1, e1 = rings_neh[0][1][1]
    wall = "%f %f 0 %f %f 0 %f %f %f %f %f %f" % (n0, e0, n1, e1, n1, e1, height, n0, e0, height)
    polys += ("<gml:Polygon><gml:exterior><gml:LinearRing><gml:posList>%s"
              "</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon>") % wall
    return ("""<core:cityObjectMember><bldg:Building gml:id="b1">
<gen:stringAttribute name="lod1_muutmisaeg"><gen:value>%s-03-06</gen:value></gen:stringAttribute>
<bldg:measuredHeight uom="m">%s</bldg:measuredHeight>
<bldg:lod1MultiSurface><gml:MultiSurface>%s</gml:MultiSurface></bldg:lod1MultiSurface>
</bldg:Building></core:cityObjectMember>""") % (year, height, polys)


def write_zip(tmp_path, name, members):
    p = str(tmp_path / name)
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn, body in members:
            zf.writestr(fn, body)
    return p


def tallinn_square():
    # ~24.75E 59.44N in EPSG:3301 (N, E): a 100x100 m block.
    return [("exterior", [(6589200.0, 542500.0), (6589200.0, 542600.0),
                          (6589300.0, 542600.0), (6589300.0, 542500.0),
                          (6589200.0, 542500.0)])]


def test_height_class_bins_and_edges():
    assert height_class(None) == 0
    assert height_class(float("nan")) == 0
    assert height_class(-12.8) == 0  # underground part, never a shed
    assert height_class(0.0) == 1
    assert height_class(2.99) == 1
    assert height_class(3.0) == 2
    assert height_class(5.99) == 2
    assert height_class(6.0) == 3
    assert height_class(11.99) == 3
    assert height_class(12.0) == 4
    assert height_class(24.99) == 4
    assert height_class(25.0) == 5
    assert height_class(90.0) == 5


def test_axis_order_northing_easting(tmp_path):
    # The GML envelope reads N E; a naive (E, N) read lands at lon 72
    # (caught live on the Tallinn file). Rings must land in Harju.
    gml = GML_HEAD + building_xml(11.5, "2025", tallinn_square()) + GML_TAIL
    p = write_zip(tmp_path, "t.zip", [("t.gml", gml)])
    buildings, _ = parse_zip(p)
    assert len(buildings) == 1
    h, year, rings = buildings[0]
    assert h == 11.5
    assert year == "2025"
    assert len(rings) == 1
    for lon, lat in rings[0]:
        assert 23.0 < lon < 26.5, lon
        assert 58.5 < lat < 60.0, lat


def test_walls_never_paint_roof_only(tmp_path):
    # A building whose ONLY polygon is a wall quad (z spans 0..h) has
    # no roof plane: rings empty, grid untouched.
    n0, e0 = 6589200.0, 542500.0
    n1, e1 = 6589300.0, 542600.0
    wall = "%f %f 0 %f %f 0 %f %f 11 %f %f 11" % (n0, e0, n1, e1, n1, e1, n0, e0)
    gml = (GML_HEAD +
           '<core:cityObjectMember><bldg:Building gml:id="w">'
           '<bldg:measuredHeight uom="m">11</bldg:measuredHeight>'
           '<bldg:lod1MultiSurface><gml:MultiSurface><gml:Polygon><gml:exterior>'
           '<gml:LinearRing><gml:posList>' + wall + '</gml:posList></gml:LinearRing>'
           '</gml:exterior></gml:Polygon></gml:MultiSurface></bldg:lod1MultiSurface>'
           '</bldg:Building></core:cityObjectMember>' + GML_TAIL)
    p = write_zip(tmp_path, "w.zip", [("w.gml", gml)])
    buildings, _ = parse_zip(p)
    assert buildings[0][2] == []


def test_courtyard_subtracts():
    # Even-odd: donut exterior + interior hole leaves the hole empty.
    grid = [0] * (DST_COLS * DST_ROWS)
    ext = [(24.74, 59.43), (24.76, 59.43), (24.76, 59.45), (24.74, 59.45), (24.74, 59.43)]
    hole = [(24.747, 59.437), (24.753, 59.437), (24.753, 59.443), (24.747, 59.443), (24.747, 59.437)]
    n = fill_rings(grid, [ext, hole], 4)
    assert n > 0
    col = lambda lon: int((lon - DST_BBOX[0]) / (DST_BBOX[2] - DST_BBOX[0]) * DST_COLS)
    row = lambda lat: int((DST_BBOX[3] - lat) / (DST_BBOX[3] - DST_BBOX[1]) * DST_ROWS)
    assert grid[row(59.44) * DST_COLS + col(24.75)] == 0  # courtyard stays missing
    assert grid[row(59.431) * DST_COLS + col(24.741)] == 4  # ring body paints


def test_centroid_splat_paints_subcell_building():
    # A 10 m shed never contains a 128 m cell centre: footprint fill
    # paints nothing, but the centroid splat marks its own cell.
    grid = [0] * (DST_COLS * DST_ROWS)
    shed = [(24.7500, 59.4400), (24.7501, 59.4400), (24.7501, 59.4401),
            (24.7500, 59.4401), (24.7500, 59.4400)]
    n = fill_rings(grid, [shed], 1)
    assert n == 1
    assert sum(1 for c in grid if c == 1) == 1


def test_max_wins_merge():
    grid = [0] * (DST_COLS * DST_ROWS)
    big = [(24.74, 59.43), (24.76, 59.43), (24.76, 59.45), (24.74, 59.45), (24.74, 59.43)]
    fill_rings(grid, [big], 2)
    fill_rings(grid, [big], 5)
    col = int((24.75 - DST_BBOX[0]) / (DST_BBOX[2] - DST_BBOX[0]) * DST_COLS)
    row = int((DST_BBOX[3] - 59.44) / (DST_BBOX[3] - DST_BBOX[1]) * DST_ROWS)
    assert grid[row * DST_COLS + col] == 5
    fill_rings(grid, [big], 2)  # lower class never downgrades
    assert grid[row * DST_COLS + col] == 5


def test_sidecar_shape():
    doc = build_sidecar([0, 2, 5, 0], {"buildings": 2, "years": {"2025": 2}})
    assert doc["cols"] == DST_COLS
    assert doc["unit"] == "class"
    assert list(base64.b64decode(doc["data"])[:4]) == [0, 2, 5, 0]
    assert doc["counts"][2] == 1
    assert "Maa- ja Ruumiamet" in doc["source"]
    assert "MEIE" in doc["bins"] or "bins" in doc


def test_muni_list_is_whole_harju():
    assert len(MUNIS) == 16
    assert "Tallinn" in MUNIS and "Loksa_linn" in MUNIS


def test_missing_zip_skipped_not_fatal(tmp_path, capsys):
    rc = main(["--cache-dir", str(tmp_path), "--snap", str(tmp_path / "snap"),
               "--munis", "Nope_vald"])
    assert rc == 0
    import json
    doc = json.load(open(str(tmp_path / "snap" / "buildings" / "buildings-tint.json")))
    assert doc["stats"]["missing_zips"] == ["Nope_vald"]
    assert doc["counts"] == [DST_COLS * DST_ROWS, 0, 0, 0, 0, 0]
