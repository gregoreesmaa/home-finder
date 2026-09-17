"""Hermetic tests for scripts/build/batch_forest.py (issue #624).

No network, no snapshot files: synthetic SHP/DBF bytes only. Also pins
the true L-EST97 (Lambert Conformal Conic, issue #648) used here.
"""

import os
import struct
import sys
import zipfile
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_canopy import (  # noqa: E402
    lest97_to_lonlat_lcc,
    lonlat_to_lest97_lcc,
)
from batch_forest import (  # noqa: E402
    build_sidecar,
    change_record,
    detection_class,
    main,
    read_dbf,
    read_shp_polygons,
    simplify_ring,
)

BUILT = date(2026, 9, 17)


def test_lcc_round_trip():
    # True L-EST97 (EPSG:3301, LCC 2SP): sub-mm round-trip, pinned so
    # the legacy TM (20-85 m off, issue #648) can never return.
    for lon, lat in [(24.75, 59.44), (23.3, 58.4), (26.0, 59.75)]:
        e, n = lonlat_to_lest97_lcc(lon, lat)
        lo, la = lest97_to_lonlat_lcc(e, n)
        assert abs(lo - lon) < 1e-9
        assert abs(la - lat) < 1e-9


def test_lcc_matches_prj_params():
    # The official distribution .prj says LCC lat0 57.5175538888889,
    # lon0 24, SP1 58, SP2 59.3333333333333, E0 500000, N0 6375000:
    # the central meridian maps E0 exactly at any latitude.
    for lat in (58.0, 59.44, 60.0):
        e, _n = lonlat_to_lest97_lcc(24.0, lat)
        assert abs(e - 500000.0) < 1e-6


def test_detection_class_ages():
    assert detection_class(date(2024, 5, 4), BUILT) == 3
    assert detection_class(date(2023, 9, 17), BUILT) == 3
    assert detection_class(date(2023, 9, 16), BUILT) == 2
    assert detection_class(date(2016, 9, 17), BUILT) == 2
    assert detection_class(date(2016, 9, 16), BUILT) == 1
    assert detection_class(None, BUILT) == 0
    assert detection_class(date(2027, 1, 1), BUILT) == 0  # future, never fresh


def _dbf_bytes(rows):
    fields = [("Pindala", "F", 31), ("Algus", "C", 200), ("Lopp", "C", 200)]
    rlen = 1 + sum(f[2] for f in fields)
    hlen = 32 + 32 * len(fields) + 1
    h = struct.pack("<BBBBIHH20x", 3, 125, 2, 18, len(rows), hlen, rlen)
    for name, typ, fl in fields:
        h += struct.pack("<11scIBB14x", name.encode(), typ.encode(),
                         0, fl, 0)
    h += b"\x0d"
    body = b""
    for area, algus, lopp in rows:
        rec = b" " + ("%*.15f" % (31, area)).encode()
        rec += algus.encode().ljust(200, b"\x00") + lopp.encode().ljust(200, b"\x00")
        body += rec
    return h + body


def _shp_bytes(polys):
    body = b""
    for i, parts in enumerate(polys):
        content = struct.pack("<i", 5)
        xs = [p[0] for part in parts for p in part]
        ys = [p[1] for part in parts for p in part]
        content += struct.pack("<4d", min(xs), min(ys), max(xs), max(ys))
        content += struct.pack("<ii", len(parts), sum(len(p) for p in parts))
        starts = []
        k = 0
        for part in parts:
            starts.append(k)
            k += len(part)
        content += struct.pack("<%di" % len(parts), *starts)
        for part in parts:
            for x, y in part:
                content += struct.unpack("<16s", struct.pack("<2d", x, y))[0]
        body += struct.pack(">ii", i + 1, len(content) // 2) + content
    flen_words = (100 + len(body)) // 2
    head = struct.pack(">7i", 9994, 0, 0, 0, 0, 0, flen_words)
    head += struct.pack("<i", 1000) + struct.pack("<i", 5)
    head += struct.pack("<8d", 0, 0, 0, 0, 0, 0, 0, 0)
    return head + body


def test_shp_dbf_readers():
    ring = [(550000.0, 6552000.0), (550100.0, 6552000.0),
            (550100.0, 6552100.0), (550000.0, 6552100.0),
            (550000.0, 6552000.0)]
    shp = _shp_bytes([[ring]])
    polys = read_shp_polygons(shp)
    assert len(polys) == 1
    (xmin, _ymin, xmax, _ymax), parts = polys[0]
    assert (xmin, xmax) == (550000.0, 550100.0)
    assert parts[0][0] == (550000.0, 6552000.0)
    dbf = _dbf_bytes([(0.6, "2022-06-16", "2024-05-04")])
    rows = read_dbf(dbf)
    assert len(rows) == 1
    assert float(rows[0]["Pindala"].strip()) == 0.6
    assert rows[0]["Lopp"].split(b"\x00")[0] == b"2024-05-04"


def test_simplify_keeps_shape():
    ring = [(float(x), 0.0) for x in range(0, 101, 10)] + [(100.0, 50.0),
            (0.0, 50.0), (0.0, 0.0)]
    out = simplify_ring(ring, 5.0)
    assert out[0] == out[-1]  # stays closed
    assert len(out) < len(ring)
    assert (100.0, 50.0) in out  # corners survive


def test_change_record_projects_lcc():
    ring = [(542500.0, 6589200.0), (542600.0, 6589200.0),
            (542600.0, 6589300.0), (542500.0, 6589300.0),
            (542500.0, 6589200.0)]
    row = change_record("kevad-1", "kevad", date(2022, 6, 16),
                        date(2024, 5, 4), 1.0, [ring], BUILT)
    assert row is not None
    assert row["cls"] == 3
    assert row["b"][0] > 24.6 and row["b"][0] < 24.8  # Tallinn, not lon 72
    assert row["b"][1] > 59.3 and row["b"][1] < 59.5
    assert change_record("x", "kevad", None, None, 1.0, [ring], BUILT) is None


def test_sidecar_and_main(tmp_path):
    ring = [(550000.0, 6552000.0), (550100.0, 6552000.0),
            (550100.0, 6552100.0), (550000.0, 6552100.0),
            (550000.0, 6552000.0)]
    zp = str(tmp_path / "m.zip")
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr("2024_kevad.shp", _shp_bytes([[ring]]))
        zf.writestr("2024_kevad.dbf",
                    _dbf_bytes([(1.0, "2022-06-16", "2024-05-04")]))
    rc = main(["--zip", zp, "--snap", str(tmp_path / "snap")])
    assert rc == 0
    import json
    doc = json.load(open(str(tmp_path / "snap" / "forest" / "forest-areas.json")))
    assert doc["vintage"] == "2024"
    assert doc["stats"]["seasons"] == {"kevad": 1}
    assert len(doc["areas"]) == 1


def test_missing_input_writes_nothing(tmp_path, capsys):
    rc = main(["--zip", str(tmp_path / "nope.zip"), "--snap", str(tmp_path / "snap")])
    assert rc == 1
    assert "NOTHING" in capsys.readouterr().out
