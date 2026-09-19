"""EELIS nature-polygon builder tests (issue #488): hermetic tests.

No network, no snapshot: the parser runs on tiny inline WFS GeoJSON
fixtures (two synthetic zone boxes + one malformed row + one Point
row), the writer on tmp dirs. Coordinates are synthetic fixture boxes
— only the zone NAMES mirror the verdict doc's real samples
(docs/p4_eelis.md); no real register geometry is committed anywhere.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_eelis_poly as G


def feat(nimi, ident, ring_lonlat, extra_props=""):
    ring = ", ".join("[%s, %s]" % (lo, la) for lo, la in ring_lonlat)
    return """{"type": "Feature", "properties": {"id": "%s", "nimi": "%s"%s},
      "geometry": {"type": "Polygon", "coordinates": [[%s]]}}""" % (
        ident, nimi, extra_props, ring)


BOX_A = [[24.83, 59.44], [24.88, 59.44], [24.88, 59.48],
         [24.83, 59.48], [24.83, 59.44]]
BOX_B = [[24.70, 59.41], [24.74, 59.41], [24.74, 59.43],
         [24.70, 59.43], [24.70, 59.41]]

KAITSE = """{"type": "FeatureCollection", "features": [%s, %s,
  {"type": "Feature", "properties": {"nimi": "katkine kirje"},
   "geometry": {"type": "Polygon", "coordinates": [[["oops"]]]}},
  {"type": "Feature", "properties": {"id": "P-1", "nimi": "punktikirje"},
   "geometry": {"type": "Point", "coordinates": [24.75, 59.43]}}
]}""" % (
    feat("Pirita jõeoru maastikukaitseala", "KLO-123", BOX_A,
         ', "tyyp": "maastikukaitseala"'),
    feat("Suur-Emajõgi tagged box", "KLO-124", BOX_B,
         ', "tyyp": "hoiuala"'),
)

NIIDUD = """{"type": "FeatureCollection", "features": [%s]}""" % feat(
    "Fixture niit", "N-7", BOX_B)


def test_parse_valid_zones():
    zones = G.parse_collection(KAITSE, "kaitse", "id", "tyyp")
    assert zones is not None
    # Two valid polygon rows; the malformed row AND the Point row are
    # skipped, never faked (centroids stay scorer-side).
    assert len(zones) == 2
    assert zones[0]["nimi"] == "Pirita jõeoru maastikukaitseala"
    assert zones[0]["zone_id"] == "KLO-123"
    assert zones[0]["lisa"] == "maastikukaitseala"
    assert zones[0]["kiht"] == "kaitse"
    assert len(zones[0]["polys"][0]) == 5


def test_parse_unparseable_is_none():
    assert G.parse_collection("<not json", "kaitse") is None
    assert G.parse_collection('{"features": "nope"}', "kaitse") is None


def test_parse_multipolygon_keeps_all_rings():
    mp = {"type": "FeatureCollection", "features": [{
        "type": "Feature",
        "properties": {"id": "M-1", "nimi": "mitmeosaline"},
        "geometry": {"type": "MultiPolygon", "coordinates": [
            [BOX_A], [BOX_B]]}}]}
    zones = G.parse_collection(json.dumps(mp), "niit", "id", None)
    assert zones is not None and len(zones) == 1
    assert len(zones[0]["polys"]) == 2
    assert zones[0]["lisa"] == ""


def test_sidecar_keeps_lonlat_with_box():
    zones = G.parse_collection(KAITSE, "kaitse", "id", "tyyp")
    rows = G.to_sidecar(zones)
    assert len(rows) == 2
    # Contract keys consumed by layers_eelis.ts isEelisArea (drift pin).
    assert set(rows[0].keys()) == {"kiht", "zone_id", "nimi", "lisa",
                                   "b", "r"}
    ring = rows[0]["r"][0]
    assert ring[0] == [24.83, 59.44]
    assert rows[0]["b"] == [24.83, 59.44, 24.88, 59.48]
    assert rows[1]["b"] == [24.70, 59.41, 24.74, 59.43]


def test_contains_joins_per_parcel():
    zones = G.parse_collection(KAITSE, "kaitse", "id", "tyyp")
    hit = G.contains(zones, 59.46, 24.85)
    assert hit is not None and hit["zone_id"] == "KLO-123"
    # Centre and edge of a polygon join alike (no distance decay, pinned).
    assert G.contains(zones, 59.475, 24.875)["zone_id"] == "KLO-123"
    # Outside every polygon stays NULL (unknown, never "clear").
    assert G.contains(zones, 59.44, 24.75) is None
    assert G.contains(None, 59.46, 24.85) is None


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_build_writes_sidecar_and_stats(tmp_path):
    k = _write(tmp_path, "kaitse.geojson", KAITSE)
    n = _write(tmp_path, "niidud.geojson", NIIDUD)
    snap = tmp_path / "snap"
    stats = G.build_sidecar({"kaitse": k, "niidud": n, "raie": None},
                            str(snap))
    assert stats["ok"] is True
    assert stats["zones"] == 3
    assert stats["tables"] == {"kaitse": 2, "niit": 1}
    assert stats["skipped_tables"] == ["raie"]
    dest = os.path.join(str(snap), "eelis", "eelis-areas.json")
    rows = json.load(open(dest, encoding="utf-8"))
    assert len(rows) == 3
    assert rows[0]["nimi"].startswith("Pirita")


def test_build_missing_table_is_skipped_not_failed(tmp_path):
    n = _write(tmp_path, "niidud.geojson", NIIDUD)
    stats = G.build_sidecar({"kaitse": None, "niidud": n, "raie": None},
                            str(tmp_path / "snap"))
    assert stats["ok"] is True
    assert stats["zones"] == 1


def test_build_unreadable_provided_writes_nothing(tmp_path):
    stats = G.build_sidecar(
        {"kaitse": str(tmp_path / "absent.geojson"), "niidud": None,
         "raie": None}, str(tmp_path / "snap"))
    assert stats["ok"] is False
    assert not os.path.exists(os.path.join(
        str(tmp_path), "snap", "eelis", "eelis-areas.json"))


def test_build_unparseable_provided_writes_nothing(tmp_path):
    bad = _write(tmp_path, "kaitse.geojson", "<not json")
    stats = G.build_sidecar({"kaitse": bad, "niidud": None, "raie": None},
                            str(tmp_path / "snap"))
    assert stats["ok"] is False


def test_raie_row_keeps_lonlat_ring_and_box():
    """#788: a raie-shaped fixture survives parse->sidecar byte-faithful.

    Synthetic offshore-style quad (rounded, NOT register geometry — no
    scraped data committed). Rings stay GeoJSON [lon, lat] end to end
    and the prefilter box stays [minlon, minlat, maxlon, maxlat]
    (ParkOutline precedent); the shape mirrors the deployed Paljassaare
    row (live-WFS-verified 2026-09-20, see issue #788).
    """
    quad = [[24.65, 59.48], [24.66, 59.49], [24.66, 59.48],
            [24.66, 59.47], [24.65, 59.48]]
    text = """{"type": "FeatureCollection", "features": [%s]}""" % feat(
        "Fixture raie", "R-9", quad, ', "aasta": "2024"')
    zones = G.parse_collection(text, "raie", "id", "aasta")
    assert zones is not None and len(zones) == 1
    assert zones[0]["zone_id"] == "R-9"
    assert zones[0]["lisa"] == "2024"
    rows = G.to_sidecar(zones)
    assert len(rows) == 1
    assert rows[0]["r"] == [quad]
    assert rows[0]["b"] == [24.65, 59.47, 24.66, 59.49]


def test_swapped_axes_cannot_pose_as_tallinn():
    """#788: an axis-swapped ring falls outside Estonia, never Tallinn.

    Tallinn window (lon 24.55-24.95, lat 59.35-59.65): swapping the
    fixture above puts lon ~59 / lat ~24, so a CRS ring-order swap in
    the builder can never silently re-ship as in-window data — it
    would read as outside-Estonia junk, and the order pin above fails
    first anyway.
    """
    quad = [[24.65, 59.48], [24.66, 59.49], [24.66, 59.48],
            [24.66, 59.47], [24.65, 59.48]]
    for lon, lat in ([la, lo] for lo, la in quad):
        assert not (24.55 <= lon <= 24.95 and 59.35 <= lat <= 59.65)


def test_builder_is_offline_by_construction():
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "batch_eelis_poly.py"), encoding="utf-8").read()
    for mod in ("urllib", "socket", "http.client", "requests"):
        assert ("import %s" % mod) not in src
