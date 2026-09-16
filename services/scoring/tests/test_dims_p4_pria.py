"""P4 PRIA field-block dims (issue #299, single-param demo): hermetic tests.

No network: the WFS field-block snapshot is pulled by the polite
fetcher (covered via a stubbed urlopen: cache-hit performs no
request; transport errors, oversize and non-JSON bodies cache
nothing); every scorer/index test runs on hand-built snapshot
dicts that mirror the live WFS schema (2026-09-16 dig, see
dims_p4_pria docstring), plus tmp-file roundtrips. The scorer is
proven network-free by running it with urlopen stubbed to raise.
"""

import json
import urllib.request

import dims_p4_pria as pria
import pytest
from dims_p4_pria import (
    BUFFER_BANDS,
    CACHE_FILENAME,
    MAX_BYTES,
    PRIA_BBOX,
    PRIA_LAYER,
    PRIA_PROPS,
    PRIA_TTL_S,
    PRIA_UA,
    PRIA_WFS,
    P4_PRIA_DIMS,
    dim_pollupuhver_pria,
    fetch_pria_snapshot,
    nearest_block,
    parse_pria_snapshot,
    score_p4_pria,
)

FETCHED_AT = 1789516800  # 2026-09-16 00:00:00 UTC

# Tallinn centre; the near/far squares sit ~110 m east / ~2 km west.
TALLINN = (59.4372, 24.7536)


def sq(clon, clat, half=0.0005):
    """Closed square ring (lon-first, live order) around a centre."""
    return [[clon - half, clat - half], [clon + half, clat - half],
            [clon + half, clat + half], [clon - half, clat + half],
            [clon - half, clat - half]]


def mkblock(bid="66147216628", ring=None, landuse="Põllukultuurid",
            crop="nisu", parish="Harku vald", area_ha=1.06,
            modified="2025-09-12T13:02:06Z"):
    return {"id": bid, "area_ha": area_ha, "landuse": landuse,
            "crop": crop, "county": "Harju maakond", "parish": parish,
            "modified": modified,
            "polys": [ring if ring is not None else sq(24.7555, 59.4372)]}


def snap(blocks, fetched_at=FETCHED_AT, count=None):
    blocks = list(blocks)
    return {"fetched_at": fetched_at,
            "count": len(blocks) if count is None else count,
            "blocks": blocks}


NEAR = snap([mkblock()])  # ~110 m east of TALLINN
FAR = snap([mkblock(bid="9", ring=sq(24.72, 59.4372),
                    landuse="Püsirohumaa", crop="?",
                    parish="Rae vald")])


def raise_urlopen(*a, **k):
    raise AssertionError("network touched in hermetic test")


# ---------------------------------------------------------------------------
# Contract: keyless WFS download path (dig evidence is a code path).
# ---------------------------------------------------------------------------

def test_ingestion_contract_consts():
    assert PRIA_WFS == "https://kls.pria.ee/geoserver/pria_avalik/wfs"
    assert PRIA_LAYER == "pria_avalik:pria_massiivid"
    assert PRIA_BBOX == (24.55, 59.35, 24.95, 59.52)  # lon,lat (validated)
    for prop in ("xy_id", "pindala", "massiivi_maakasutus", "kultuur",
                 "maakond", "vald", "viimase_muutmise_aeg"):
        assert prop in PRIA_PROPS
    assert PRIA_TTL_S == 24 * 3600  # accrualPeriodicity DAILY
    assert MAX_BYTES == 8 * 1024 * 1024
    assert "home-finder" in PRIA_UA
    assert BUFFER_BANDS == [(50, 30), (200, 55), (float("inf"), 80)]


# ---------------------------------------------------------------------------
# P4-024 spray-drift buffer bands.
# ---------------------------------------------------------------------------

def test_near_block_scores_caution_never_zero():
    v, reason = dim_pollupuhver_pria(TALLINN, NEAR)
    assert v == 55
    assert "hinnang" in reason
    assert "66147216628" in reason and "Harku vald" in reason
    assert "Põllukultuurid" in reason and "nisu" in reason
    assert "2026-09-16" in reason  # snapshot date stated, not hidden


def test_adjacent_and_inside_score_low_never_zero():
    inside = snap([mkblock(ring=sq(24.7536, 59.4372, half=0.002))])
    v, reason = dim_pollupuhver_pria(TALLINN, inside)
    assert v == 30 and "külgneb" in reason
    edge = snap([mkblock(ring=sq(24.7536, 59.4372, half=0.0002))])
    assert dim_pollupuhver_pria(TALLINN, edge)[0] == 30


def test_clear_fringe_scores_high_never_100():
    v, reason = dim_pollupuhver_pria(TALLINN, FAR)
    assert v == 80
    assert "selge" in reason and "Rae vald" in reason


def test_band_edges():
    # ~50 m north of centre: adjacent side; ~210 m: clear side.
    adj = snap([mkblock(ring=sq(24.7536, 59.4372 + 0.00045, half=1e-5))])
    assert dim_pollupuhver_pria(TALLINN, adj)[0] == 30
    clr = snap([mkblock(ring=sq(24.7536, 59.4372 + 0.0019, half=1e-5))])
    assert dim_pollupuhver_pria(TALLINN, clr)[0] == 80


def test_scored_reason_names_cousins_and_checks():
    _, reason = dim_pollupuhver_pria(TALLINN, NEAR)
    # Scored reasons trace to the joined block (cousins named, crop
    # recorded-not-scored); the full buyer-side checks live in the
    # NULL reasons (pinned below).
    assert "dims_p4_kaur" in reason and "dim_tervis_kaur" in reason
    assert "dims_p4_eelis" in reason and "dim_maaloodus_eelis" in reason
    assert "kirjas, mitte hinnatud" in reason
    assert "ära feigi" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason
    _, null_reason = dim_pollupuhver_pria(TALLINN, None)
    assert "kohapealsel vaatlusel" in null_reason
    assert "pritsimisriba" in null_reason
    assert "farmilõhna" in null_reason
    assert "pritsimisgraafikut" in null_reason
    assert "dims_p4_tervise" in null_reason
    assert "dim_country_health_nuisances" in null_reason
    assert "dims_p4_komun" in null_reason
    assert "dim_farm_odour_cells" in null_reason


def test_null_without_origin_never_scores():
    for origin in (None, "nope", (59.4,), (59.4, 24.7, 1.0),
                   ("59.4", "24.7"), (True, 24.7)):
        v, reason = dim_pollupuhver_pria(origin, NEAR)
        assert v is None and "EI OLE" in reason


def test_null_without_snapshot_never_clear():
    for snapd in (None, "nope", {}, {"blocks": []},
                  {"fetched_at": FETCHED_AT, "blocks": []},
                  {"fetched_at": FETCHED_AT, "blocks": [{"id": "x"}]}):
        v, reason = dim_pollupuhver_pria(TALLINN, snapd)
        assert v is None and "EI OLE" in reason
        assert "pritsimisgraafikut" in reason


def test_outside_snapshot_bbox_stays_null_never_clear():
    # Tartu: the Tallinn-fringe snapshot says nothing about local
    # fields — a far "nearest" block must not score "clear".
    v, reason = dim_pollupuhver_pria((58.3776, 26.7290), NEAR)
    assert v is None and "EI OLE" in reason
    assert "katvust" in reason


def test_nearest_block_picks_closest():
    both = snap([mkblock(bid="far", ring=sq(24.72, 59.4372)),
                 mkblock(bid="near", ring=sq(24.7555, 59.4372))])
    dist_m, block = nearest_block(TALLINN, both)
    assert block["id"] == "near" and 50 < dist_m < 200
    assert nearest_block(TALLINN, None) is None
    assert nearest_block(TALLINN, {}) is None


def test_swapped_axis_features_rejected_never_faked(tmp_path):
    # lat-first impostor (the WFS returns lon-first; a swapped feed
    # must not silently score the Gulf of Finland as fields).
    bad = {"type": "FeatureCollection", "totalFeatures": 1,
           "features": [{"type": "Feature", "id": "pria_massiivid.1",
                         "geometry": {"type": "MultiPolygon",
                                      "coordinates": [[[[59.4372, 24.7536],
                                                        [59.4382, 24.7536],
                                                        [59.4382, 24.7546],
                                                        [59.4372, 24.7546],
                                                        [59.4372, 24.7536]
                                                        ]]]},
                         "properties": {"xy_id": "1"}}]}
    fp = tmp_path / "swap.json"
    fp.write_text(json.dumps(bad), encoding="utf-8")
    assert parse_pria_snapshot(str(fp)) is None
    v, reason = dim_pollupuhver_pria(TALLINN, None)
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# Offline readers: live-schema parsing, tmp roundtrips.
# ---------------------------------------------------------------------------

def live_like_collection():
    return {"type": "FeatureCollection", "totalFeatures": 429,
            "features": [
                {"type": "Feature", "id": "pria_massiivid.52656942185",
                 "geometry": {"type": "MultiPolygon",
                              "coordinates": [[[[24.46309028, 59.26175676],
                                                [24.46281238, 59.26190626],
                                                [24.46263791, 59.26044148],
                                                [24.46309028, 59.26175676]
                                                ]]]},
                 "geometry_name": "geometry",
                 "properties": {"xy_id": "52656942185", "pindala": 1.06,
                                "massiivi_maakasutus": "Põllukultuurid",
                                "kultuur": "aedmaasikad avamaal või madala "
                                           "katte all",
                                "kultuur2": None, "maakond": "Harju maakond",
                                "vald": "Saue vald",
                                "viimase_muutmise_aeg":
                                    "2025-09-12T13:02:06Z"}},
                {"type": "Feature", "id": "pria_massiivid.2",
                 "geometry": {"type": "Point",  # wrong type: skipped
                              "coordinates": [24.7, 59.4]},
                 "properties": {"xy_id": "2"}},
                {"type": "Feature", "id": "pria_massiivid.3",
                 "geometry": None,  # no geometry: skipped
                 "properties": {"xy_id": "3"}},
            ]}


def test_parse_live_schema(tmp_path):
    fp = tmp_path / "wfs.json"
    fp.write_text(json.dumps(live_like_collection()), encoding="utf-8")
    snapd = parse_pria_snapshot(str(fp))
    assert snapd is not None
    assert snapd["count"] == 429 and len(snapd["blocks"]) == 1
    block = snapd["blocks"][0]
    assert block["id"] == "52656942185"
    assert block["area_ha"] == 1.06
    assert block["landuse"] == "Põllukultuurid"
    assert "aedmaasikad" in block["crop"]
    assert block["parish"] == "Saue vald"
    assert block["modified"] == "2025-09-12T13:02:06Z"
    assert len(block["polys"]) == 1 and len(block["polys"][0]) == 4
    assert isinstance(snapd["fetched_at"], int)


def test_parse_missing_and_broken_is_none(tmp_path):
    assert parse_pria_snapshot(str(tmp_path / "absent.json")) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert parse_pria_snapshot(str(bad)) is None
    lst = tmp_path / "list.json"
    lst.write_text("[1,2]", encoding="utf-8")
    assert parse_pria_snapshot(str(lst)) is None
    nofeats = tmp_path / "nofeats.json"
    nofeats.write_text(json.dumps({"type": "FeatureCollection"}),
                       encoding="utf-8")
    assert parse_pria_snapshot(str(nofeats)) is None


def test_fixture_end_to_end_shape():
    assert score_p4_pria(TALLINN, NEAR) == {"pollupuhver_pria": 55}
    assert score_p4_pria(TALLINN, FAR) == {"pollupuhver_pria": 80}
    assert score_p4_pria(TALLINN, None) == {"pollupuhver_pria": None}
    assert score_p4_pria(None, NEAR) == {"pollupuhver_pria": None}


def test_scorer_never_touches_network(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", raise_urlopen)
    dim_pollupuhver_pria(TALLINN, NEAR)
    dim_pollupuhver_pria(TALLINN, None)
    dim_pollupuhver_pria(None, NEAR)
    nearest_block(TALLINN, NEAR)
    score_p4_pria(TALLINN, NEAR)


# ---------------------------------------------------------------------------
# Polite fetcher: cache hit = no request; errors cache nothing.
# ---------------------------------------------------------------------------

def test_fetch_cache_hit_performs_no_request(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", raise_urlopen)
    dest = tmp_path / CACHE_FILENAME
    dest.write_text("{}", encoding="utf-8")
    assert fetch_pria_snapshot(str(tmp_path)) == str(dest)


def test_fetch_transport_error_caches_nothing(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise OSError("network down")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert fetch_pria_snapshot(str(tmp_path)) is None
    assert not (tmp_path / CACHE_FILENAME).exists()


def test_fetch_rejects_non_json_body(tmp_path, monkeypatch):
    class Resp:
        status = 200
        headers = {"Content-Type": "text/html"}

        def read(self, *a):
            return b"<html>register</html>"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: Resp())
    assert fetch_pria_snapshot(str(tmp_path)) is None
    assert not (tmp_path / CACHE_FILENAME).exists()


def test_fetch_rejects_oversize_body(tmp_path, monkeypatch):
    class Resp:
        status = 200
        headers = {"Content-Type": "application/json"}

        def read(self, *a):
            return b"x" * (MAX_BYTES + 1)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: Resp())
    assert fetch_pria_snapshot(str(tmp_path)) is None
    assert not (tmp_path / CACHE_FILENAME).exists()


def test_fetch_stores_json_snapshot(tmp_path, monkeypatch):
    body = json.dumps(live_like_collection()).encode()

    class Resp:
        status = 200
        headers = {"Content-Type": "application/json"}

        def read(self, *a):
            return body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    seen = {}

    def fake(req, **k):
        seen["url"] = req.full_url
        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    got = fetch_pria_snapshot(str(tmp_path))
    assert got == str(tmp_path / CACHE_FILENAME)
    assert "GetFeature" in seen["url"]
    assert "pria_avalik" in seen["url"] and "bbox=" in seen["url"]
    snapd = parse_pria_snapshot(got)
    assert snapd is not None and len(snapd["blocks"]) == 1


# ---------------------------------------------------------------------------
# Registry + aggregator.
# ---------------------------------------------------------------------------

def test_registry_and_aggregator_cover_single_param():
    assert [k for k, _, _ in P4_PRIA_DIMS] == ["pollupuhver_pria"]
    assert [p for _, p, _ in P4_PRIA_DIMS] == ["P4-024"]
    assert len({fn for _, _, fn in P4_PRIA_DIMS}) == 1
    assert pria.P4_PRIA_DIMS is P4_PRIA_DIMS
