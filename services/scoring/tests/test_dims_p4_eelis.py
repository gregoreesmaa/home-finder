"""P4 EELIS dims (issues #287 demo + #360 coverage): hermetic tests.

No network: every test runs on fixture row-dicts, hand-built POIs and
fixture GeoJSON. The polite fetcher is covered via a stubbed urlopen
(cache-hit performs no request; all-layers-fail caches nothing; the
stubbed pull writes a real snapshot file); scorers are proven
network-free by running them with urlopen stubbed to raise.
"""

import json
import urllib.request

import dims_p4_eelis as p4e
import pytest
from dims_p4_eelis import (
    CACHE_FILENAME,
    EELIS_TTL_S,
    EELIS_UA,
    EELIS_WFS_URL,
    EMITTER_CLEAR_SCORE,
    EMITTER_FAR_SCORE,
    EMITTER_NEAR_SCORE,
    FELLING_CLEAR_SCORE,
    FELLING_SCORE,
    FLOOD_SCORE,
    HABITAT_CLEAR_SCORE,
    HABITAT_NEAR_SCORE,
    INS_CLEAR_SCORE,
    KAITSE_SCORE,
    P4_EELIS_DIMS,
    PULL_PLAN,
    dim_kindlustus_eelis,
    dim_lohnasektor_eelis,
    dim_maaloodus_eelis,
    dim_rohemuutus_eelis,
    fetch_eelis_snapshot,
    geojson_rows,
    parse_eelis_snapshot,
    score_p4_eelis,
    snapshot_to_pois,
)

# Tallinn centre: hand-built rows sit ~57 m east unless stated
# (0.001 deg lon ~= 57 m at 59.44 N; 0.001 deg lat ~= 111 m).
TALLINN = (59.4372, 24.7536)
FAR = (59.4272, 24.6536)  # ~6 km SW: beyond every window, in-Tallinn


def mkrow(lat=59.4372, lon=24.7546, zone_id="Z1", nimi="Testiala",
          **extra):
    row = {"zone_id": zone_id, "nimi": nimi, "lat": lat, "lon": lon}
    row.update(extra)
    return row


def mkemit(lat=59.4372, lon=24.7546, em_id="E1", nimi="Testallikas",
           liik="puhasti"):
    return {"em_id": em_id, "nimi": nimi, "liik": liik,
            "lat": lat, "lon": lon}


def mkpois(flood=(), kaitse=(), habitat=(), felling=(), emitters=()):
    return snapshot_to_pois({"flood": list(flood),
                             "kaitse": list(kaitse),
                             "habitat": list(habitat),
                             "felling": list(felling),
                             "emitters": list(emitters)})


def mkpoly_fc(nimi="Testiala", ident=1979, lon=24.7546, lat=59.4372,
              extra_props=None):
    props = {"id": ident, "nimi": nimi, "tyyp": "VP"}
    if extra_props:
        props.update(extra_props)
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": props,
         "geometry": {"type": "Polygon", "coordinates": [[
             [lon, lat], [lon + 0.002, lat], [lon + 0.002, lat + 0.002],
             [lon, lat + 0.002], [lon, lat]]]}}]}


def mkpoint_fc(nimi="Testallikas", ident=11, lon=24.7546, lat=59.4372):
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "properties": {"sys_id": ident, "nimi": nimi},
         "geometry": {"type": "Point", "coordinates": [lon, lat]}}]}


class _FakeResp:
    """Minimal urlopen stub (context manager, stdlib-shaped)."""

    def __init__(self, body=b"{}", status=200, ctype="application/json"):
        self._body = body
        self.status = status
        self.headers = {"Content-Type": ctype}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _raise_urlopen(*a, **k):
    raise AssertionError("network touched in a hermetic test")


# ---------------------------------------------------------------------------
# Ingestion contract: TTL, UA, endpoint, cache behaviour.
# ---------------------------------------------------------------------------

def test_ttl_is_annual_and_ua_and_plan():
    assert EELIS_TTL_S == 365 * 24 * 3600
    assert "home-finder" in EELIS_UA and "no scrape" in EELIS_UA
    assert EELIS_WFS_URL.startswith("https://")
    assert len(PULL_PLAN) == 6  # flood/kaitse/habitat/felling + 2 emitters
    tables = [t for t, _, _ in PULL_PLAN]
    assert sorted(tables) == ["emitters", "emitters", "felling",
                              "flood", "habitat", "kaitse"]


def test_fetch_cache_hit_performs_no_request(tmp_path, monkeypatch):
    dest = tmp_path / CACHE_FILENAME
    dest.write_text('{"flood": [], "kaitse": []}', encoding="utf-8")
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    assert fetch_eelis_snapshot(str(tmp_path)) == str(dest)


def test_fetch_all_layers_fail_caches_nothing(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise OSError("network down")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert fetch_eelis_snapshot(str(tmp_path)) is None
    assert not (tmp_path / CACHE_FILENAME).exists()


def test_fetch_non_json_body_caches_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: _FakeResp(b"<html>not json</html>",
                                                 ctype="text/html"))
    assert fetch_eelis_snapshot(str(tmp_path)) is None
    assert not (tmp_path / CACHE_FILENAME).exists()


def test_fetch_stubbed_pull_writes_snapshot(tmp_path, monkeypatch):
    def fake_open(req, timeout=30):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "kr_puhasti" in url or "kr_jaakreostus" in url:
            body = mkpoint_fc()
        else:
            body = mkpoly_fc()
        return _FakeResp(json.dumps(body).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    dest = fetch_eelis_snapshot(str(tmp_path))
    assert dest == str(tmp_path / CACHE_FILENAME)
    snap = parse_eelis_snapshot(dest)
    assert snap is not None
    assert len(snap["kaitse"]) == 1 and len(snap["habitat"]) == 1
    assert len(snap["flood"]) == 1 and len(snap["felling"]) == 1
    assert len(snap["emitters"]) == 2  # puhasti + jaakreostus
    liigid = sorted(e["liik"] for e in snap["emitters"])
    assert liigid == ["jaakreostus", "puhasti"]
    assert snap["meta"]["layer_ok"][p4e.LAYER_KAITSE] is True
    pois = snapshot_to_pois(snap)
    assert {p["kind"] for p in pois} == {
        "eelis_flood_p4", "eelis_kaitse_p4", "eelis_habitat_p4",
        "eelis_felling_p4", "eelis_emitter_p4"}


# ---------------------------------------------------------------------------
# Pure converter + snapshot reader.
# ---------------------------------------------------------------------------

def test_geojson_rows_polygon_centroid_and_point():
    rows = geojson_rows(mkpoly_fc(nimi="Kaitse", ident=7))
    assert len(rows) == 1
    assert rows[0]["zone_id"] == "7" and rows[0]["nimi"] == "Kaitse"
    assert rows[0]["tyyp"] == "VP"
    # exterior-ring mean of the 0.002 deg fixture square
    assert rows[1 - 1]["lat"] == pytest.approx(59.4372 + 0.0008)
    assert rows[0]["lon"] == pytest.approx(24.7546 + 0.0008)
    erows = geojson_rows(mkpoint_fc(), id_field="sys_id",
                         extra={"liik": "puhasti"}, id_key="em_id")
    assert erows[0]["em_id"] == "11" and erows[0]["liik"] == "puhasti"
    assert (erows[0]["lat"], erows[0]["lon"]) == pytest.approx(
        (59.4372, 24.7546))


def test_geojson_rows_skips_malformed_never_faked():
    bad = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"nimi": "x"},
         "geometry": {"type": "Polygon", "coordinates": []}},
        {"type": "Feature", "properties": {"nimi": "y"},
         "geometry": {"type": "Point", "coordinates": ["x", None]}},
        {"type": "Feature", "properties": None, "geometry": None},
        "not-a-feature",
        {"type": "Feature",
         "properties": {"nimi": "inf"},
         "geometry": {"type": "Point",
                      "coordinates": [float("inf"), 59.4]}},
    ]}
    assert geojson_rows(bad) == []
    assert geojson_rows({}) == []
    assert geojson_rows(None) == []


def test_parse_snapshot_missing_malformed_and_partial(tmp_path):
    assert parse_eelis_snapshot(str(tmp_path / "nope.json")) is None
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert parse_eelis_snapshot(str(broken)) is None
    partial = tmp_path / "partial.json"
    partial.write_text('{"kaitse": [{"zone_id": "1", "nimi": "K", '
                       '"lat": 59.4, "lon": 24.7}]}', encoding="utf-8")
    snap = parse_eelis_snapshot(str(partial))
    assert snap["flood"] == [] and len(snap["kaitse"]) == 1


def test_rows_without_coords_stay_out():
    snap = {"kaitse": [{"zone_id": "1", "nimi": "K"},
                       {"zone_id": "2", "nimi": "K2",
                        "lat": True, "lon": 24.7},
                       mkrow()],
            "flood": [], "habitat": [], "felling": [], "emitters": []}
    pois = snapshot_to_pois(snap)
    assert len(pois) == 1 and pois[0]["nimi"] == "Testiala"
    assert snapshot_to_pois(None) == []


# ---------------------------------------------------------------------------
# P4-015 demo: flood tariff beats kaitseala; clear prints flood caveat.
# ---------------------------------------------------------------------------

def test_p4_015_flood_hit_scores_35_with_illiquidity_flag(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    pois = mkpois(flood=[mkrow(nimi="Pirita üleujutusala")],
                  kaitse=[mkrow(lat=FAR[0], lon=FAR[1])])
    v, reason = dim_kindlustus_eelis(TALLINN, pois)
    assert v == FLOOD_SCORE == 35
    assert "hinnang" in reason and "illikviidsuse lipp" in reason
    assert "Pirita üleujutusala" in reason


def test_p4_015_kaitse_hit_scores_55(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    pois = mkpois(kaitse=[mkrow(nimi="Pirita hoiuala", tyyp="HA")])
    v, reason = dim_kindlustus_eelis(TALLINN, pois)
    assert v == KAITSE_SCORE == 55
    assert "hinnang" in reason and "illikviidsuse lipp" in reason


def test_p4_015_clear_prints_flood_empty_caveat():
    far = mkrow(lat=FAR[0], lon=FAR[1])
    v, reason = dim_kindlustus_eelis(TALLINN, mkpois(kaitse=[far]))
    assert v == INS_CLEAR_SCORE == 85
    assert "hinnang" in reason and "EI OLE" in reason
    assert "üleujutuskihis Tallinna kirjeid pole" in reason


def test_p4_015_clear_with_flood_rows_elsewhere():
    far = mkrow(lat=FAR[0], lon=FAR[1])
    v, reason = dim_kindlustus_eelis(
        TALLINN, mkpois(flood=[far], kaitse=[far]))
    assert v == INS_CLEAR_SCORE == 85
    assert "EI OLE" not in reason  # both legs measured


def test_p4_015_null_matrix():
    assert dim_kindlustus_eelis(None, None)[0] is None
    assert dim_kindlustus_eelis(TALLINN, None)[0] is None
    assert dim_kindlustus_eelis(None, [])[0] is None
    v, reason = dim_kindlustus_eelis(TALLINN, [])
    assert v is None and "EI OLE" in reason
    v, reason = dim_kindlustus_eelis(FAR, mkpois(kaitse=[mkrow()]))
    assert v == INS_CLEAR_SCORE  # far listing, zone elsewhere: measured


# ---------------------------------------------------------------------------
# P4-024 coverage: coarse habitat cell, proxy honesty.
# ---------------------------------------------------------------------------

def test_p4_024_near_cell_scores_55_no_species_claim(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    pois = mkpois(habitat=[mkrow(nimi="Stroomi niit")])
    v, reason = dim_maaloodus_eelis(TALLINN, pois)
    assert v == HABITAT_NEAR_SCORE == 55
    assert "hinnang" in reason and "mitte liigiväide" in reason
    assert "Stroomi niit" in reason


def test_p4_024_clear_and_null():
    far = mkrow(lat=FAR[0], lon=FAR[1])
    v, reason = dim_maaloodus_eelis(TALLINN, mkpois(habitat=[far]))
    assert v == HABITAT_CLEAR_SCORE == 80 and "hinnang" in reason
    assert dim_maaloodus_eelis(TALLINN, [])[0] is None
    v, reason = dim_maaloodus_eelis(TALLINN, [])
    assert "EI OLE" in reason
    assert dim_maaloodus_eelis(None, mkpois(habitat=[mkrow()]))[0] is None


# ---------------------------------------------------------------------------
# P4-030 coverage: coarse change flag with register year.
# ---------------------------------------------------------------------------

def test_p4_030_felling_hit_scores_45_with_year(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    pois = mkpois(felling=[mkrow(nimi="Nõmme raie", aasta="2025")])
    v, reason = dim_rohemuutus_eelis(TALLINN, pois)
    assert v == FELLING_SCORE == 45
    assert "hinnang" in reason and "2025" in reason
    assert "mitte satelliidimõõt" in reason


def test_p4_030_missing_year_says_so():
    v, reason = dim_rohemuutus_eelis(TALLINN, mkpois(felling=[mkrow()]))
    assert v == FELLING_SCORE == 45
    assert "EI OLE registriaastat" in reason


def test_p4_030_clear_and_null():
    far = mkrow(lat=FAR[0], lon=FAR[1])
    v, reason = dim_rohemuutus_eelis(TALLINN, mkpois(felling=[far]))
    assert v == FELLING_CLEAR_SCORE == 80 and "hinnang" in reason
    assert dim_rohemuutus_eelis(TALLINN, [])[0] is None
    assert dim_rohemuutus_eelis(None, None)[0] is None


# ---------------------------------------------------------------------------
# P4-053 coverage: sector + distance, never a rose or circle buffer.
# ---------------------------------------------------------------------------

def test_p4_053_doorstep_emitter_scores_40_with_sector(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    # emitter due west of the listing -> listing is "ida" of the source
    pois = mkpois(emitters=[mkemit(lat=59.4372, lon=24.7486,
                                   nimi="Paljassaare puhastaja")])
    v, reason = dim_lohnasektor_eelis(TALLINN, pois)
    assert v == EMITTER_NEAR_SCORE == 40
    assert "mitte tuuleroos" in reason
    assert "tuule sagedust mõõtmata (hinnang)" in reason
    assert "ida" in reason and "puhasti" in reason


def test_p4_053_in_sector_emitter_scores_60():
    # ~1 km north: listing is "lõuna" of the source, inside 1500 m
    pois = mkpois(emitters=[mkemit(lat=59.4462, lon=24.7536,
                                   nimi="Asfalditehas",
                                   liik="jaakreostus")])
    v, reason = dim_lohnasektor_eelis(TALLINN, pois)
    assert v == EMITTER_FAR_SCORE == 60
    assert "lõuna" in reason and "jaakreostus" in reason


def test_p4_053_clear_and_null():
    far = mkemit(lat=FAR[0], lon=FAR[1])
    v, reason = dim_lohnasektor_eelis(TALLINN, mkpois(emitters=[far]))
    assert v == EMITTER_CLEAR_SCORE == 80 and "hinnang" in reason
    assert "mitte tuuleroos" in reason
    v, reason = dim_lohnasektor_eelis(TALLINN, [])
    assert v is None and "EI OLE" in reason
    assert dim_lohnasektor_eelis(None, None)[0] is None


# ---------------------------------------------------------------------------
# Registry + aggregator + honesty markers across all four dims.
# ---------------------------------------------------------------------------

def test_registry_keys_and_pnums():
    assert [k for k, _, _ in P4_EELIS_DIMS] == [
        "kindlustus_eelis", "maaloodus_eelis",
        "rohemuutus_eelis", "lohnasektor_eelis"]
    assert [p for _, p, _ in P4_EELIS_DIMS] == [
        "P4-015", "P4-024", "P4-030", "P4-053"]


def test_score_p4_eelis_aggregates_all_four():
    pois = mkpois(kaitse=[mkrow(lat=FAR[0], lon=FAR[1])],
                  habitat=[mkrow(lat=FAR[0], lon=FAR[1])],
                  felling=[mkrow(lat=FAR[0], lon=FAR[1])],
                  emitters=[mkemit(lat=FAR[0], lon=FAR[1])])
    out = score_p4_eelis(TALLINN, pois)
    assert out == {"kindlustus_eelis": 85, "maaloodus_eelis": 80,
                   "rohemuutus_eelis": 80, "lohnasektor_eelis": 80}
    assert score_p4_eelis(TALLINN, []) == {
        "kindlustus_eelis": None, "maaloodus_eelis": None,
        "rohemuutus_eelis": None, "lohnasektor_eelis": None}


@pytest.mark.parametrize("fn,pois", [
    (dim_kindlustus_eelis, None),
    (dim_maaloodus_eelis, None),
    (dim_rohemuutus_eelis, None),
    (dim_lohnasektor_eelis, None),
])
def test_all_null_reasons_carry_ei_ole(fn, pois):
    _, reason = fn(TALLINN, mkpois() if pois is None else pois)
    assert "EI OLE" in reason, fn.__name__
