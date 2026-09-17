"""Hermetic tests for scripts/build/batch_noisemap.py (issue #625).

No network: synthetic GML members only. Pins the N,E axis swap, the
confirmed MYRAKLASS int domain ('45','50','55',… — the old "55-59"
guess fails closed), dedupe-relevant keys, and the missing-cache
builds-nothing rule.
"""

import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_noisemap import (  # noqa: E402
    _cell_boxes,
    _dp_simplify,
    build,
    parse_feature_member,
)

GML = """<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:ms="http://mapserver.gis.umn.edu/mapserver">
<wfs:member><ms:myra22_strat_sum_oopaev gml:id="myra22_strat_sum_oopaev.7"><ms:ID>63</ms:ID><ms:YLDKLASS>strat</ms:YLDKLASS><ms:MYRALIIK>sum</ms:MYRALIIK><ms:MYRAINDEKS>Lden</ms:MYRAINDEKS><ms:MYRAKLASS>%s</ms:MYRAKLASS><ms:AEG>2022</ms:AEG>
<ms:msGeometry><gml:Polygon><gml:exterior><gml:LinearRing><gml:posList>%s</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon></ms:msGeometry>
</ms:myra22_strat_sum_oopaev></wfs:member></wfs:FeatureCollection>"""

# N,E pairs around Tallinn (E ~545000, N ~6590000).
RING_NE = ("6590000 545000 6590000 545100 6590100 545100 "
           "6590100 545000 6590000 545000")


def _member(klass="55", ring=RING_NE):
    root = ET.fromstring(GML % (klass, ring))
    return root.find("{http://www.opengis.net/wfs/2.0}member")


def test_parse_swaps_ne_to_en():
    p = parse_feature_member(_member())
    assert p is not None
    # Identity is the member gml:id (ms:ID is a category code, shared).
    assert p["fid"] == "myra22_strat_sum_oopaev.7"
    assert p["band_db"] == 55
    ring = p["rings_3301"][0]
    assert ring[0] == (545000.0, 6590000.0)


def test_parse_rejects_range_guess_shape():
    # The old "55-59" assumption was wrong (real domain: plain ints);
    # unparseable bands fail closed.
    assert parse_feature_member(_member(klass="55-59")) is None
    assert parse_feature_member(_member(klass=">65")) is None
    assert parse_feature_member(_member(klass="")) is None


def test_parse_rejects_degenerate_ring():
    assert parse_feature_member(_member(ring="1 2 3 4")) is None


def test_dp_simplify_keeps_shape():
    ring = [(float(x), 6590000.0) for x in range(0, 101, 5)]
    ring = [(x, y) for x, y in ring] + [(100.0, 6590100.0), (0.0, 6590100.0),
                                        (0.0, 6590000.0)]
    simp = _dp_simplify(ring, 5.0)
    assert len(simp) < len(ring)
    assert simp[0] == ring[0] and simp[-1] == ring[-1]


def test_dp_simplify_closed_ring_survives():
    # Regression: a degenerate seed segment (closed ring endpoints
    # coincide) kept every distance at zero and collapsed 10k-vertex
    # rings to 2 points. A closed square must stay closed with >= 4.
    sq = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0),
          (0.0, 0.0)]
    simp = _dp_simplify(sq, 5.0)
    assert len(simp) >= 4
    assert simp[0] == simp[-1] == (0.0, 0.0)


def test_cells_cover_keep_window():
    boxes = _cell_boxes(10.0)
    assert len(boxes) == 14 * 9
    e0, n0, e1, n1 = boxes[0][1]
    assert (e0, n0) == (478000.0, 6533000.0)
    ee0, nn0, ee1, nn1 = boxes[-1][1]
    assert (ee1, nn1) == (614000.0, 6622000.0)


def test_build_without_cache_writes_nothing(tmp_path, capsys):
    rc = build(str(tmp_path / "snap"))
    assert rc == 1
    assert "NOTHING" in capsys.readouterr().out
    assert not (tmp_path / "snap" / "noise" / "noise-areas.json").exists()


def test_build_preserves_tiny_but_valid_rings(tmp_path):
    # A 1 m triangle is small but valid: DP must pass it through
    # intact (never "simplify" real geometry into guard-rejectable
    # slivers) — the degenerate-seed collapse is the pinned bug.
    import json
    from batch_noisemap import build as _build
    legdir = tmp_path / "snap" / "noise" / "cache" / "Lden"
    legdir.mkdir(parents=True)
    tiny = ("6590000 545000 6590000 545001 6590001 545000 "
            "6590000 545000")
    doc = (GML % ("55", RING_NE)).replace(
        "</wfs:FeatureCollection>",
        "<wfs:member><ms:myra22_strat_sum_oopaev "
        "xmlns:ms=\"http://mapserver.gis.umn.edu/mapserver\" "
        "xmlns:gml=\"http://www.opengis.net/gml/3.2\" "
        "gml:id=\"x.1\"><ms:ID>63</ms:ID><ms:MYRAKLASS>55</ms:MYRAKLASS>"
        "<ms:msGeometry><gml:Polygon><gml:exterior><gml:LinearRing>"
        "<gml:posList>" + tiny + "</gml:posList></gml:LinearRing>"
        "</gml:exterior></gml:Polygon></ms:msGeometry>"
        "</ms:myra22_strat_sum_oopaev></wfs:member></wfs:FeatureCollection>")
    (legdir / "cell-000.xml").write_text(doc)
    rc = _build(str(tmp_path / "snap"))
    assert rc == 0
    side = json.load(open(str(tmp_path / "snap" / "noise" / "noise-areas.json")))
    assert len(side["areas"]) == 2
    assert side["stats"].get("slivers", 0) == 0


def test_build_dedupes_identical_members_across_cells(tmp_path):
    # Members carry no per-polygon id (gml:id repeats per category):
    # the same source polygon in two cells must collapse to one row.
    import json
    from batch_noisemap import build as _build
    legdir = tmp_path / "snap" / "noise" / "cache" / "Lden"
    legdir.mkdir(parents=True)
    doc = GML % ("55", RING_NE)
    (legdir / "cell-000.xml").write_text(doc)
    (legdir / "cell-001.xml").write_text(doc)
    rc = _build(str(tmp_path / "snap"))
    assert rc == 0
    side = json.load(open(str(tmp_path / "snap" / "noise" / "noise-areas.json")))
    assert len(side["areas"]) == 1
    assert side["stats"]["dupes"] == 1
