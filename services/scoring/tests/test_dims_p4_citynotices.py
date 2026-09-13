"""P4 citynotices dims (issues #283 + #357): hermetic tests.

No network: tallinn.ee serves server-rendered CMS HTML (open) but no
keyless machine feed for notice rows (dated negative - see the module
docstring), so every test runs on fixture HTML mirroring the live
shapes observed 2026-09-13 plus hand-built geocoded POIs (street
labels become coordinates only via the documented ADS/Maa-amet step).
The polite fetcher is covered via a stubbed urlopen (cache-hit
performs no request; transport errors and short bodies return None
and cache nothing); scorers are proven network-free by running them
with urlopen stubbed to raise, on a fixed calendar cursor.
"""

import urllib.error

import dims_p4_citynotices as p4c
import pytest
from dims_p4_citynotices import (
    NOTICE_INDEX_URL,
    NOTICES_TTL_S,
    P4_CITYNOTICES_DIMS,
    SNOW_INFO_URL,
    SNOW_TTL_S,
    dim_construction_phase,
    dim_snow_notices,
    fetch_cached,
    parse_ee_daterange,
    parse_notice_detail,
    parse_notice_index,
    parse_snow_info,
    score_p4_citynotices,
)

# Tallinn centre: hand-built POIs sit ~57 m east unless stated.
TALLINN = (59.4372, 24.7536)
# Fixed calendar cursor: every expiry assertion is hermetic.
TODAY = "2026-09-13"

ALL_FNS = [dim_construction_phase, dim_snow_notices]


def mkpoi(kind, lat=59.4372, lon=24.7546, **kw):
    poi = {"kind": kind, "lat": lat, "lon": lon}
    poi.update(kw)
    return poi


def constrpoi(**kw):
    base = {"label": "trammitee", "start": "2026-09-01",
            "end": "2026-09-30"}
    base.update(kw)
    return mkpoi("constr_notice_p4", **base)


def snowpoi(**kw):
    base = {"start": "2026-09-10", "end": "2026-09-20"}
    base.update(kw)
    return mkpoi("snow_notice_p4", **base)


# Fixture listing HTML mirrors the live /et/uudised shape (dated
# /et/uudis/<slug> anchors among noise links).
LISTING_HTML = """<html><body><main>
<a href="/et/uudis/eelinfo-14-20-september">Eelinfo 14. \u2013 20. september</a>
<a href="/et/uudis/eelinfo-7-september-13-september">Eelinfo 7. - 13. september</a>
<a href="/et/teenused-ja-teave/transport-liiklus">Transport</a>
<a href="https://www.tallinn.ee/et/uudiskirjad">Uudiskirjad</a>
</main></body></html>"""

# Fixture detail HTML mirrors the live eelinfo weekday blocks.
DETAIL_HTML = """<html><body><article><h1>Eelinfo 14. \u2013 20. september</h1>
<h2>Teisip\u00e4ev, 15. september</h2>
<p>9.00 liikluskorraldus Kivila tn 19 juures, \u00fcmbers\u00f5it Laagna teelt.</p>
<h2>Kolmap\u00e4ev, 16. september</h2>
<p>10.00 trammitee ehitusplatsi teade: Sepa tn l\u00f5ik suletud.</p>
<script>var x = "Teisip\u00e4ev, 99. september";</script>
</article></body></html>"""

# Fixture snow HTML mirrors /et/lumi (season label + lumekaart link).
SNOW_HTML = """<html><body><main><h1>Talihooldus</h1>
<p>Tallinna t\u00e4navate talihooldus 2025/2026 katab k\u00f5ik linna teed.</p>
<a href="https://gis.tallinn.ee/lumekaart/">Lumekaart</a>
</main></body></html>"""


# ---------------------------------------------------------------------------
# Ingestion: TTL defaults, cache-hit silence, honest errors. No network.
# ---------------------------------------------------------------------------

def test_ttl_and_urls_are_documented_feed():
    assert NOTICES_TTL_S == 7 * 24 * 3600  # weekly eelinfo cadence
    assert SNOW_TTL_S == 30 * 24 * 3600  # seasonal page, autumn refresh
    assert NOTICE_INDEX_URL == (
        "https://www.tallinn.ee/et/uudised?news_heading=7465")
    assert SNOW_INFO_URL == "https://www.tallinn.ee/et/lumi"


def test_fetch_cache_hit_makes_no_request(tmp_path, monkeypatch):
    dest = tmp_path / "index.html"
    dest.write_bytes(b"x" * 2000)

    def _boom(*a, **k):
        raise AssertionError("network used on cache hit")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert fetch_cached("https://example.invalid/x", str(tmp_path),
                        "index.html") == str(dest)


class _FakeResp:
    def __init__(self, body, status=200):
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._body


def test_fetch_transport_error_returns_none_and_caches_nothing(
        tmp_path, monkeypatch):
    def _fail(*a, **k):
        raise urllib.error.URLError("down")

    monkeypatch.setattr("urllib.request.urlopen", _fail)
    assert fetch_cached("https://example.invalid/x", str(tmp_path),
                        "index.html", ttl_s=0) is None
    assert not (tmp_path / "index.html").exists()


def test_fetch_short_body_is_not_cached_as_data(tmp_path, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: _FakeResp(b"error page", 200))
    assert fetch_cached("https://example.invalid/x", str(tmp_path),
                        "index.html", ttl_s=0) is None
    assert not (tmp_path / "index.html").exists()


def test_fetch_non_200_returns_none_and_caches_nothing(
        tmp_path, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: _FakeResp(b"x" * 2000, 429))
    assert fetch_cached("https://example.invalid/x", str(tmp_path),
                        "index.html", ttl_s=0) is None
    assert not (tmp_path / "index.html").exists()


def test_scorers_never_touch_network(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("scorer used the network")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    pois = [constrpoi(), snowpoi()]
    for fn in ALL_FNS:
        fn(TALLINN, pois, TODAY)
    score_p4_citynotices(TALLINN, pois, TODAY)


# ---------------------------------------------------------------------------
# Offline readers on the observed live shapes.
# ---------------------------------------------------------------------------

def test_parse_index_keeps_notice_slugs_drops_noise():
    items = parse_notice_index(LISTING_HTML)
    assert [i["slug"] for i in items] == [
        "eelinfo-14-20-september", "eelinfo-7-september-13-september"]
    assert items[0]["url"] == "/et/uudis/eelinfo-14-20-september"
    assert "september" in items[0]["title"]
    assert parse_notice_index("<html><body>no links</body></html>") == []


def test_parse_detail_keeps_weekday_blocks_skips_script():
    entries = parse_notice_detail(DETAIL_HTML)
    assert len(entries) == 2
    assert entries[0]["weekday"] == "Teisip\u00e4ev"
    assert entries[0]["date_label"] == "15. september"
    assert "Kivila tn 19" in entries[0]["text"]
    assert entries[1]["weekday"] == "Kolmap\u00e4ev"
    assert "Sepa tn" in entries[1]["text"]
    # The script-embedded fake heading must not leak in.
    assert all("99." not in e["date_label"] for e in entries)


@pytest.mark.parametrize("label,year,expected", [
    ("14. \u2013 20. september", 2026, ("2026-09-14", "2026-09-20")),
    ("7. - 13. september", 2026, ("2026-09-07", "2026-09-13")),
    ("15. september", 2026, ("2026-09-15", "2026-09-15")),
    ("24.-30. august", 2026, ("2026-08-24", "2026-08-30")),
    ("15. smarch", 2026, (None, None)),  # unknown month: never guessed
    ("september", 2026, (None, None)),  # dayless label: never guessed
    ("31. september", 2026, (None, None)),  # impossible date
    ("20. - 14. september", 2026, (None, None)),  # reversed range
    ("", 2026, (None, None)),
])
def test_daterange_parses_or_refuses(label, year, expected):
    assert parse_ee_daterange(label, year) == expected


def test_parse_snow_info_reports_season_window_only():
    info = parse_snow_info(SNOW_HTML)
    assert info == {"season": "2025/2026",
                    "lumekaart_url": "https://gis.tallinn.ee/lumekaart/"}
    # No season published -> Nones, never a guessed winter.
    assert parse_snow_info("<html><body>lumi</body></html>") == {
        "season": None, "lumekaart_url": None}


# ---------------------------------------------------------------------------
# P4-014 construction-phase calendar (expiry boundaries pinned).
# ---------------------------------------------------------------------------

def test_constr_active_scores_flat_with_expiry():
    v, r = dim_construction_phase(TALLINN, [constrpoi()], TODAY)
    assert v == 45, r
    assert "hinnang" in r and "500 m" in r
    assert "2026-09-30" in r and "trammitee" in r


def test_constr_multiple_active_count_and_latest_expiry():
    pois = [constrpoi(end="2026-09-20"),
            constrpoi(label="raudtee", start="2026-09-10",
                      end="2026-10-05", lon=24.7556)]
    v, r = dim_construction_phase(TALLINN, pois, TODAY)
    assert v == 45, r
    assert "2 kehtivat" in r and "2026-10-05" in r


def test_constr_far_buffer_is_unknown_not_quiet():
    rural = constrpoi(lat=TALLINN[0], lon=TALLINN[1] + 0.05)  # ~2.9 km
    v, r = dim_construction_phase(TALLINN, [rural], TODAY)
    assert v is None
    assert "EI OLE" in r and "m\u00f5\u00f5detud vaikus" in r


def test_constr_expired_stays_null_not_quiet():
    v, r = dim_construction_phase(
        TALLINN, [constrpoi(start="2026-08-01", end="2026-08-31")], TODAY)
    assert v is None
    assert "EI OLE" in r and "aegunud" in r


def test_constr_future_stays_null_with_start_date():
    v, r = dim_construction_phase(
        TALLINN, [constrpoi(start="2026-10-01", end="2026-12-01")], TODAY)
    assert v is None
    assert "EI OLE" in r and "2026-10-01" in r
    assert "premium" not in r  # no premium faked from a plan


def test_constr_dateless_and_malformed_stay_null():
    for poi in (constrpoi(start=None, end=None),
                constrpoi(start="varsti", end="hiljem"),
                constrpoi(start="2026-09-01", end=None)):
        v, r = dim_construction_phase(TALLINN, [poi], TODAY)
        assert v is None, r
        assert "EI OLE" in r and "kuup\u00e4evata" in r


def test_constr_missing_input_and_bad_points_stay_null():
    v, r = dim_construction_phase(None, [constrpoi()], TODAY)
    assert v is None and "EI OLE" in r
    v, r = dim_construction_phase(TALLINN, None, TODAY)
    assert v is None and "EI OLE" in r
    bad = [mkpoi("constr_notice_p4", lat=None, lon=24.75,
                 start="2026-09-01", end="2026-09-30"),
           mkpoi("snow_notice_p4", start="2026-09-01",
                 end="2026-09-30")]  # wrong kind: ignored
    v, r = dim_construction_phase(TALLINN, bad, TODAY)
    assert v is None and "EI OLE" in r


# ---------------------------------------------------------------------------
# P4-018 snow-notice calendar (same expiry contract, own POI kind).
# ---------------------------------------------------------------------------

def test_snow_active_scores_flat_with_expiry():
    v, r = dim_snow_notices(TALLINN, [snowpoi()], TODAY)
    assert v == 45, r
    assert "hinnang" in r and "500 m" in r and "2026-09-20" in r


def test_snow_expired_future_and_empty_stay_null():
    v, r = dim_snow_notices(
        TALLINN, [snowpoi(start="2026-01-05", end="2026-01-06")], TODAY)
    assert v is None
    assert "EI OLE" in r and "hooaeg" in r
    v, r = dim_snow_notices(
        TALLINN, [snowpoi(start="2026-12-01", end="2026-12-02")], TODAY)
    assert v is None
    assert "EI OLE" in r and "2026-12-01" in r
    v, r = dim_snow_notices(TALLINN, [], TODAY)
    assert v is None
    assert "EI OLE" in r and "lumetu" in r  # unknown, never "trap"
    v, r = dim_snow_notices(None, None, TODAY)
    assert v is None and "EI OLE" in r


def test_snow_ignores_constr_kind_and_vice_versa():
    v, _ = dim_snow_notices(TALLINN, [constrpoi()], TODAY)
    assert v is None
    v, _ = dim_construction_phase(TALLINN, [snowpoi()], TODAY)
    assert v is None


def test_registry_and_aggregator_cover_both():
    assert [k for k, _, _ in P4_CITYNOTICES_DIMS] == [
        "constr_phase", "snow_notices"]
    assert [p for _, p, _ in P4_CITYNOTICES_DIMS] == ["P4-014", "P4-018"]
    assert len({fn for _, _, fn in P4_CITYNOTICES_DIMS}) == 2
    out = score_p4_citynotices(TALLINN, [constrpoi(), snowpoi()], TODAY)
    assert out == {"constr_phase": 45, "snow_notices": 45}
    assert score_p4_citynotices(TALLINN, [], TODAY) == {
        "constr_phase": None, "snow_notices": None}
    assert score_p4_citynotices(None, None, TODAY) == {
        "constr_phase": None, "snow_notices": None}
    assert p4c.P4_CITYNOTICES_DIMS is P4_CITYNOTICES_DIMS
