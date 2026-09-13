"""P4 street-imagery dims (issues #303 demo + #372 coverage): hermetic tests.

No network: every fixture is a synthetic in-memory listing/streetimg
record (plain dicts — no scraped data). fetch_cached/fetch_mapillary are
covered only on the cache-hit path plus transport-error-raises;
freshness/expiry uses tmp_path. The live probes are manual DoD evidence
(pasted in the PR + docs/p4_streetimg.md), not unit runs.
"""

import os
import time
import urllib.error

import dims_p4_streetimg as p4
from dims_p4_streetimg import (
    P4_STREETIMG_DIMS,
    TTL_DAYS,
    build_radius_search_url,
    cache_path,
    dim_streetimg_arrival,
    dim_streetimg_block,
    dim_streetimg_photo_forensics,
    is_fresh,
    parse_image_search,
    score_p4_streetimg,
)

TODAY = "2026-09-13"

ALL_FNS = [fn for _, _, fn in P4_STREETIMG_DIMS]
EXPECTED_KEYS = ["block_observer", "photo_forensics", "arrival_sequence"]
EXPECTED_PNUMS = ["P4-029", "P4-022", "P4-040"]


def listing(**kw):
    base = {"address": "Tartu mnt 25-12, Tallinn",
            "exif_daylight_ok": True, "photo_room_count": 3,
            "ehr_room_count": 3}
    base.update(kw)
    return base


def frame(**kw):
    base = {"image_id": "123", "captured_at": "2026-06-01",
            "creator": "keegi", "distance_m": 25.0,
            "source": "mapillary", "quality_score": 0.8,
            "thumb_url": "https://example.invalid/t.jpg"}
    base.update(kw)
    return base


def streetimg(**kw):
    base = {"images": [frame()], "facade_ok": True, "street_issues": [],
            "sidewalk_ok": True, "duplicate_hashes": 0,
            "exif_daylight_ok": True,
            "arrival_frames": [frame(distance_m=120.0)],
            "arrival_lit_ok": True, "arrival_footway_ok": True}
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# Ingestion helpers: cache path, freshness, polite fetch, URL, parsing.
# ---------------------------------------------------------------------------

def test_cache_path_and_freshness_hermetic(tmp_path):
    p = cache_path(str(tmp_path), "caps.json")
    assert p == os.path.join(str(tmp_path), p4.CACHE_SUBDIR, "caps.json")
    assert is_fresh(p, 30) is False  # missing file is never fresh
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        fh.write("{}")
    assert is_fresh(p, 30) is True
    old = time.time() - 40 * 86400
    os.utime(p, (old, old))
    assert is_fresh(p, 30) is False


def test_ttl_values_imagery_monthly_terms_annual():
    assert TTL_DAYS == {"mapillary_images": 30, "terms_reverify": 365}


def test_fetch_cached_cache_hit_never_touches_network(tmp_path):
    p = cache_path(str(tmp_path), "dev.html")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as fh:
        fh.write(b"cached")
    assert p4.fetch_cached("http://127.0.0.1:9/nope", str(tmp_path),
                           "dev.html", 30) == p
    assert p4.fetch_mapillary("http://127.0.0.1:9/nope", "DUMMY",
                              str(tmp_path), "dev.html", 30) == p


def test_fetch_transport_error_raises_and_caches_nothing(
        tmp_path, monkeypatch):
    def _fail(*a, **k):
        raise urllib.error.URLError("unreachable")

    monkeypatch.setattr("urllib.request.urlopen", _fail)
    for call in (lambda: p4.fetch_cached("http://127.0.0.1:9/nope",
                                         str(tmp_path), "a.json", 30),
                 lambda: p4.fetch_mapillary("http://127.0.0.1:9/nope",
                                            "DUMMY", str(tmp_path),
                                            "b.json", 30)):
        try:
            call()
        except urllib.error.URLError:
            pass
        else:
            raise AssertionError("transport error must raise, never cache")
    assert not os.path.exists(cache_path(str(tmp_path), "a.json"))
    assert not os.path.exists(cache_path(str(tmp_path), "b.json"))


def test_radius_search_url_shape_and_ceiling_clamps():
    url = build_radius_search_url(59.4372, 24.7536)
    assert url.startswith("https://graph.mapillary.com/images?")
    assert "lat=59.437200" in url and "lng=24.753600" in url
    assert "radius=50" in url and "fields=id,captured_at" in url
    assert "access_token" not in url  # token added at fetch, never in URLs
    big = build_radius_search_url(59.4372, 24.7536, radius_m=5000,
                                  limit=5000)
    assert "radius=50" in big and "limit=100" in big


def test_parse_image_search_fixture_payload():
    payload = {"data": [
        {"id": "111", "captured_at": 1780000000000,
         "creator_username": "tallinnlane", "quality_score": 0.9,
         "thumb_1024_url": "https://example.invalid/a.jpg"},
        {"id": "222", "captured_at": "halb",
         "creator_username": "keegi"},
        {"captured_at": 1780000000000},  # no id -> skipped
        "praht",
    ]}
    recs = parse_image_search(payload)
    assert len(recs) == 2
    assert recs[0]["image_id"] == "111"
    assert recs[0]["captured_at"] == "2026-05-28"  # ms epoch -> date
    assert recs[0]["creator"] == "tallinnlane"
    assert recs[0]["source"] == "mapillary"
    assert recs[0]["distance_m"] is None  # caller adds its own haversine
    assert recs[1]["captured_at"] is None  # bad date stays missing
    assert recs[1]["quality_score"] is None
    assert parse_image_search({}) == []
    assert parse_image_search({"data": "praht"}) == []
    assert parse_image_search(None) == []


def test_scorers_never_touch_network(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("scorer used the network")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    lst, sti = listing(), streetimg()
    for fn in ALL_FNS:
        fn(lst, sti, TODAY)
    score_p4_streetimg(lst, sti, TODAY)


# ---------------------------------------------------------------------------
# P4-029 block observer (demo): bands + NULL contract.
# ---------------------------------------------------------------------------

def test_p29_null_when_no_frame():
    for sti in ({}, {"images": []}, {"images": "praht"}):
        v, reason = dim_streetimg_block(listing(), sti, TODAY)
        assert v is None
        assert "EI OLE" in reason and "hinnang" in reason


def test_p29_issues_score_40_with_date_and_source():
    sti = streetimg(street_issues=["praht", "vrakk"])
    v, reason = dim_streetimg_block(listing(), sti, TODAY)
    assert v == 40
    assert "praht, vrakk" in reason and "2026-06-01" in reason
    assert "Mapillary" in reason and "hinnang" in reason


def test_p29_bad_facade_without_issue_list_scores_40():
    sti = streetimg(facade_ok=False)
    v, reason = dim_streetimg_block(listing(), sti, TODAY)
    assert v == 40
    assert "fassaad" in reason


def test_p29_sidewalk_only_doubt_scores_55():
    sti = streetimg(sidewalk_ok=False)
    v, reason = dim_streetimg_block(listing(), sti, TODAY)
    assert v == 55
    assert "kõnnitee-kahtlus" in reason


def test_p29_stale_clean_photo_capped_at_60():
    sti = streetimg(images=[frame(captured_at="2023-01-01")])
    v, reason = dim_streetimg_block(listing(), sti, TODAY)
    assert v == 60
    assert "vananenud" in reason


def test_p29_undated_clean_photo_capped_at_65():
    sti = streetimg(images=[frame(captured_at=None)])
    v, reason = dim_streetimg_block(listing(), sti, TODAY)
    assert v == 65
    assert "kuupäevata" in reason


def test_p29_fresh_clean_scores_75_and_names_kartaview():
    sti = streetimg(images=[frame(source="kartaview")])
    v, reason = dim_streetimg_block(listing(), sti, TODAY)
    assert v == 75
    assert "KartaView" in reason and "2026-06-01" in reason


# ---------------------------------------------------------------------------
# P4-022 photo forensics (coverage): flag counting + NULL contract.
# ---------------------------------------------------------------------------

def bare_listing():
    """Listing with every P4-022 join leg missing (NULL-contract input)."""
    return listing(exif_daylight_ok=None, photo_room_count=None,
                   ehr_room_count=None)


def test_p22_null_when_no_leg():
    v, reason = dim_streetimg_photo_forensics(bare_listing(), {}, TODAY)
    assert v is None
    assert "EI OLE" in reason and "hinnang" in reason


def test_p22_two_flags_score_30():
    sti = streetimg(facade_ok=False, street_issues=["praht"],
                    duplicate_hashes=2)
    v, reason = dim_streetimg_photo_forensics(listing(), sti, TODAY)
    assert v == 30
    assert "tänavakaader näitab: praht" in reason
    assert "duplikaat/relist (2)" in reason


def test_p22_single_flag_scores_55():
    sti = streetimg(duplicate_hashes=1)
    v, reason = dim_streetimg_photo_forensics(listing(), sti, TODAY)
    assert v == 55
    assert "duplikaat/relist (1)" in reason


def test_p22_daylight_and_room_mismatch_are_flags():
    sti = streetimg(images=[], duplicate_hashes=0)
    v, _ = dim_streetimg_photo_forensics(
        listing(exif_daylight_ok=False), sti, TODAY)
    assert v == 55
    v, reason = dim_streetimg_photo_forensics(
        listing(photo_room_count=2), streetimg(images=[]), TODAY)
    assert v == 55
    assert "tubade arvu lõhe (2 fotol vs 3 EHR-is)" in reason


def test_p22_clean_multi_leg_scores_80_with_frame_date():
    v, reason = dim_streetimg_photo_forensics(listing(), streetimg(),
                                              TODAY)
    assert v == 80
    assert "4 jalga puhtad" in reason
    assert "Mapillary fassaaditõde 2026-06-01" in reason


def test_p22_clean_without_imagery_scores_80_without_date():
    sti = {"duplicate_hashes": 0, "exif_daylight_ok": True}
    v, reason = dim_streetimg_photo_forensics(listing(), sti, TODAY)
    assert v == 80
    assert "kuupäevata" not in reason and "fassaaditõde" not in reason


# ---------------------------------------------------------------------------
# P4-040 arrival sequence (coverage): window rule + bands + framing.
# ---------------------------------------------------------------------------

def test_p40_null_when_no_arrival_frames():
    for sti in ({}, {"arrival_frames": []}, {"images": [frame()]}):
        v, reason = dim_streetimg_arrival(listing(), sti, TODAY)
        assert v is None
        assert "EI OLE" in reason and "hinnang" in reason


def test_p40_null_when_anchor_beyond_200m_or_distanceless():
    sti = streetimg(arrival_frames=[frame(distance_m=250.0)])
    v, reason = dim_streetimg_arrival(listing(), sti, TODAY)
    assert v is None
    assert "200 m" in reason
    sti = streetimg(arrival_frames=[frame(distance_m=None)])
    v, reason = dim_streetimg_arrival(listing(), sti, TODAY)
    assert v is None
    assert "kaugusega" in reason


def test_p40_weak_lamp_or_footway_scores_45():
    sti = streetimg(arrival_lit_ok=False)
    v, reason = dim_streetimg_arrival(listing(), sti, TODAY)
    assert v == 45
    assert "pime lõik" in reason
    assert "tipu-lõpu" in reason and "mitte ohutusväide" in reason
    sti = streetimg(arrival_footway_ok=False)
    v, reason = dim_streetimg_arrival(listing(), sti, TODAY)
    assert v == 45
    assert "jälgtee" in reason or "kõnnitee" in reason


def test_p40_stale_or_undated_clean_caps_at_60():
    sti = streetimg(
        arrival_frames=[frame(distance_m=120.0,
                              captured_at="2023-01-01")])
    v, reason = dim_streetimg_arrival(listing(), sti, TODAY)
    assert v == 60
    assert "vananenud" in reason
    sti = streetimg(arrival_frames=[frame(distance_m=120.0,
                                          captured_at=None)])
    v, reason = dim_streetimg_arrival(listing(), sti, TODAY)
    assert v == 60
    assert "kuupäevata" in reason


def test_p40_fresh_clean_scores_70_with_date_and_framing():
    v, reason = dim_streetimg_arrival(listing(), streetimg(), TODAY)
    assert v == 70
    assert "2026-06-01" in reason
    assert "tipu-lõpu" in reason
    assert "PPA/Päästeametit ei kasutata" in reason


# ---------------------------------------------------------------------------
# Honesty invariant + registry.
# ---------------------------------------------------------------------------

def test_all_null_reasons_carry_honesty_markers():
    for _, _, fn in P4_STREETIMG_DIMS:
        v, reason = fn(bare_listing(), {}, TODAY)
        assert v is None
        assert "EI OLE" in reason
        assert "hinnang" in reason


def test_scored_reasons_carry_hinnang_but_never_ei_ole():
    scored = [
        dim_streetimg_block(listing(), streetimg(), TODAY),
        dim_streetimg_photo_forensics(listing(), streetimg(), TODAY),
        dim_streetimg_arrival(listing(), streetimg(), TODAY),
        dim_streetimg_block(
            listing(), streetimg(street_issues=["praht"]), TODAY),
        dim_streetimg_photo_forensics(
            listing(), streetimg(duplicate_hashes=3), TODAY),
        dim_streetimg_arrival(
            listing(), streetimg(arrival_lit_ok=False), TODAY),
    ]
    for v, reason in scored:
        assert v is not None
        assert "hinnang" in reason
        assert "EI OLE" not in reason
        assert "mõõdetud" not in reason
        assert "garanteeritud" not in reason


def test_registry_and_aggregator_cover_all_three():
    assert [k for k, _, _ in P4_STREETIMG_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_STREETIMG_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_STREETIMG_DIMS}) == 3
    assert p4.P4_STREETIMG_DIMS is P4_STREETIMG_DIMS
    out = score_p4_streetimg(bare_listing(), {}, TODAY)
    assert out == {k: None for k in EXPECTED_KEYS}
    rich = streetimg()
    out = score_p4_streetimg(listing(), rich, TODAY)
    assert out == {"block_observer": 75, "photo_forensics": 80,
                   "arrival_sequence": 70}
    assert (score_p4_streetimg(listing(), rich, TODAY)["block_observer"]
            == 75)
