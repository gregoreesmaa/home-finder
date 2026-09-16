"""Hermetic tests for scripts/build/batch_stateland.py (issue #615).

Covers ONLY the pure sidecar projection — the WFS harvest is a polite
one-off (custom UA, paced, /tmp-only) and is never called here
(AGENTS.md section 7.6). Scorer math is pinned in
test_dims_p4_riigimaa.py (reused, never re-tested here).
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_stateland import (  # noqa: E402
    build_sidecar,
    parse_auction_collection,
    parse_deadline,
    parse_katri_collection,
    to_sidecar,
)

from datetime import date  # noqa: E402

KATRI_GEOJSON = json.dumps({
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature",
         "properties": {"katastritunnus": "78401:101:0123", "nimetus": None,
                        "vara_liik": "MAA", "riigivara_valitseja": "Kliimaministeerium",
                        "fid": "a.1"},
         "geometry": {"type": "Polygon", "coordinates": [[
             [24.74, 59.43], [24.75, 59.43], [24.75, 59.44],
             [24.74, 59.44], [24.74, 59.43]]]}},
        {"type": "Feature",
         "properties": {"katastritunnus": None, "fid": "a.2"},
         "geometry": {"type": "Point", "coordinates": [24.74, 59.43]}},
    ],
})

AUCTION_GEOJSON = json.dumps({
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature",
         "properties": {"id": 3244621, "purpose": "Müük",
                        "status": "Avaldatud",
                        "offer_deadline": "17.09.2026 kell 10:00",
                        "url": "https://riigimaaoksjon.ee/public/auction/1/object/2"},
         "geometry": {"type": "Polygon", "coordinates": [[
             [24.76, 59.43], [24.77, 59.43], [24.77, 59.44],
             [24.76, 59.44], [24.76, 59.43]]]}},
        {"type": "Feature",
         "properties": {"id": 111, "purpose": "Müük",
                        "status": "Avaldatud",
                        "offer_deadline": "01.01.2020 kell 10:00",
                        "url": "https://example.com/old"},
         "geometry": {"type": "Polygon", "coordinates": [[
             [24.76, 59.43], [24.77, 59.43], [24.77, 59.44],
             [24.76, 59.44], [24.76, 59.43]]]}},
        {"type": "Feature",
         "properties": {"id": 112, "purpose": "Rent",
                        "status": "Tühistatud",
                        "offer_deadline": "22.10.2026 kell 10:00",
                        "url": "https://example.com/cancelled"},
         "geometry": {"type": "Polygon", "coordinates": [[
             [24.76, 59.43], [24.77, 59.43], [24.77, 59.44],
             [24.76, 59.44], [24.76, 59.43]]]}},
    ],
})

TODAY = date(2026, 9, 16)


def test_parse_deadline():
    assert parse_deadline("17.09.2026 kell 10:00") == date(2026, 9, 17)
    assert parse_deadline("") is None
    assert parse_deadline(None) is None
    assert parse_deadline("homme") is None


def test_parse_katri_keeps_polygons_skips_points():
    zones = parse_katri_collection(KATRI_GEOJSON)
    assert zones is not None
    assert len(zones) == 1
    assert zones[0]["cls"] == "state"
    assert zones[0]["tunnus"] == "78401:101:0123"
    assert zones[0]["valitseja"] == "Kliimaministeerium"
    assert len(zones[0]["polys"][0]) >= 4


def test_parse_katri_unknown_on_garbage():
    assert parse_katri_collection("not json") is None
    assert parse_katri_collection("") is None


def test_parse_auction_keeps_only_live_published():
    zones = parse_auction_collection(AUCTION_GEOJSON, TODAY)
    assert zones is not None
    assert len(zones) == 1
    assert zones[0]["cls"] == "auction"
    assert zones[0]["deadline"] == "17.09.2026"
    assert zones[0]["purpose"] == "Müük"
    assert zones[0]["url"].startswith("https://riigimaaoksjon.ee/")


def test_sidecar_rows_carry_geojson_lonlat_rings():
    zones = ((parse_katri_collection(KATRI_GEOJSON) or [])
             + (parse_auction_collection(AUCTION_GEOJSON, TODAY) or []))
    rows = to_sidecar(zones)
    assert len(rows) == 2
    state, auction = rows
    assert state["cls"] == "state" and "tunnus" in state
    assert auction["cls"] == "auction" and "deadline" in auction
    lon, lat = state["r"][0][0]
    assert (lon, lat) == (24.74, 59.43)
    b = state["b"]
    assert b[0] <= lon <= b[2] and b[1] <= lat <= b[3]


def test_build_sidecar_writes_counts_and_attribution(tmp_path):
    katri = tmp_path / "katri.json"
    katri.write_text(KATRI_GEOJSON, encoding="utf-8")
    auction = tmp_path / "auction.json"
    auction.write_text(AUCTION_GEOJSON, encoding="utf-8")
    snap = tmp_path / "snap"
    stats = build_sidecar({"katri": [str(katri)], "auction": str(auction)},
                          str(snap))
    assert stats["ok"] is True
    assert stats["zones"] == 2
    assert stats["by_cls"] == {"state": 1, "auction": 1}
    assert "Maa- ja Ruumiamet" in stats["attribution"]
    dest = snap / "stateland" / "stateland-areas.json"
    rows = json.loads(dest.read_text(encoding="utf-8"))
    assert len(rows) == 2


def test_build_sidecar_refuses_without_input(tmp_path):
    stats = build_sidecar({"katri": [str(tmp_path / "missing.json")],
                           "auction": None}, str(tmp_path / "s"))
    assert stats["ok"] is False
    assert not (tmp_path / "s" / "stateland" / "stateland-areas.json").exists()
