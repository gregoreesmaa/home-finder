"""P4 density dims (issue #554): hermetic tests.

No network: the WFS is open but bulk-pulling it in unit tests would
be impolite, so every test runs on fixture GML (live schema shape:
cell id, person count, notApplicable special value, 2024 reference
period) and hand-built POIs. The polite fetcher is covered via a
stubbed urlopen (cache-hit performs no request; transport errors
and short bodies return None and cache nothing); scorers are proven
network-free by running them with urlopen stubbed to raise. The GML
reader is proven on the REAL live field names (probed 2026-09-16).
"""

import urllib.error

import dims_p4_density as p4d
import pytest
from dims_p4_density import (
    CELL_WINDOW_M,
    DENSITY_TTL_S,
    DENSITY_WFS_URL,
    P4_DENSITY_DIMS,
    cell_character,
    density_cells_from_values,
    dim_quiet_delight,
    dim_services_viability,
    dim_urbanist_delight,
    fetch_cached,
    parse_density_gml,
    score_p4_density,
)

# Tallinn centre: hand-built cells sit ~57 m east unless stated.
TALLINN = (59.4372, 24.7536)


def mkcell(value=244, lat=59.4372, lon=24.7546, **kw):
    poi = {"kind": "densitycell_p4", "lat": lat, "lon": lon,
           "value": value, "cell_id": "S-10049"}
    poi.update(kw)
    return poi


ALL_FNS = [dim_urbanist_delight, dim_quiet_delight, dim_services_viability]

# Fixture GML in the live schema shape (field names probed 2026-09-16;
# values mirror the live Harjumaa pull: counts + masked 0-squares).
GML_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
 xmlns:PD_rahvastikutihedus="ee.stat.pd-stat-rahvastikutihedus1x1km">
<PD_rahvastikutihedus:PD.StatisticalDistribution>
<PD_rahvastikutihedus:inspireid_identifier_localid>S-10040</PD_rahvastikutihedus:inspireid_identifier_localid>
<PD_rahvastikutihedus:domain_characterstring>demography</PD_rahvastikutihedus:domain_characterstring>
<PD_rahvastikutihedus:measurementmethod_xlink_title>count</PD_rahvastikutihedus:measurementmethod_xlink_title>
<PD_rahvastikutihedus:measurementunit_uom>person</PD_rahvastikutihedus:measurementunit_uom>
<PD_rahvastikutihedus:periodofreference_xlink_title>1.1.2024 - 31.12.2024</PD_rahvastikutihedus:periodofreference_xlink_title>
<PD_rahvastikutihedus:value_statisticalvalue_value>11</PD_rahvastikutihedus:value_statisticalvalue_value>
</PD_rahvastikutihedus:PD.StatisticalDistribution>
<PD_rahvastikutihedus:PD.StatisticalDistribution>
<PD_rahvastikutihedus:inspireid_identifier_localid>S-10043</PD_rahvastikutihedus:inspireid_identifier_localid>
<PD_rahvastikutihedus:measurementunit_uom>person</PD_rahvastikutihedus:measurementunit_uom>
<PD_rahvastikutihedus:periodofreference_xlink_title>1.1.2024 - 31.12.2024</PD_rahvastikutihedus:periodofreference_xlink_title>
<PD_rahvastikutihedus:value_statisticalvalue_value>0</PD_rahvastikutihedus:value_statisticalvalue_value>
<PD_rahvastikutihedus:value_statisticalvalue_specialvalue_xlink_href>https://inspire.ec.europa.eu/codelist/SpecialValue/notApplicable</PD_rahvastikutihedus:value_statisticalvalue_specialvalue_xlink_href>
<PD_rahvastikutihedus:value_statisticalvalue_specialvalue_xlink_title>notApplicable</PD_rahvastikutihedus:value_statisticalvalue_specialvalue_xlink_title>
</PD_rahvastikutihedus:PD.StatisticalDistribution>
<PD_rahvastikutihedus:PD.StatisticalDistribution>
<PD_rahvastikutihedus:inspireid_identifier_localid>S-10049</PD_rahvastikutihedus:inspireid_identifier_localid>
<PD_rahvastikutihedus:measurementunit_uom>person</PD_rahvastikutihedus:measurementunit_uom>
<PD_rahvastikutihedus:periodofreference_xlink_title>1.1.2024 - 31.12.2024</PD_rahvastikutihedus:periodofreference_xlink_title>
<PD_rahvastikutihedus:value_statisticalvalue_value>244</PD_rahvastikutihedus:value_statisticalvalue_value>
</PD_rahvastikutihedus:PD.StatisticalDistribution>
</wfs:FeatureCollection>
"""


def write_gml(tmp_path):
    p = tmp_path / "density.gml"
    p.write_text(GML_FIXTURE, encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# Ingestion: TTL default, cache-hit silence, honest errors. No network.
# ---------------------------------------------------------------------------

def test_ttl_and_url_are_documented_feed():
    assert DENSITY_TTL_S == 365 * 24 * 3600  # INSPIRE PD series: ANNUAL
    assert "inspire.geoportaal.ee" in DENSITY_WFS_URL
    assert "typeNames=" in DENSITY_WFS_URL  # WFS 2.0 plural (probed)


def test_fetch_cache_hit_makes_no_request(tmp_path, monkeypatch):
    dest = tmp_path / "density.gml"
    dest.write_bytes(b"x" * 5000)

    def _boom(*a, **k):
        raise AssertionError("network used on cache hit")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert fetch_cached("https://example.invalid/x", str(tmp_path),
                        "density.gml") == str(dest)


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
                        "density.gml", ttl_s=0) is None
    assert not (tmp_path / "density.gml").exists()


def test_fetch_short_body_is_not_cached_as_data(tmp_path, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: _FakeResp(b"error page", 200))
    assert fetch_cached("https://example.invalid/x", str(tmp_path),
                        "density.gml", ttl_s=0) is None
    assert not (tmp_path / "density.gml").exists()


def test_fetch_non_200_returns_none_and_caches_nothing(
        tmp_path, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: _FakeResp(b"x" * 5000, 429))
    assert fetch_cached("https://example.invalid/x", str(tmp_path),
                        "density.gml", ttl_s=0) is None
    assert not (tmp_path / "density.gml").exists()


def test_scorers_never_touch_network(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("scorer used the network")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    for fn in ALL_FNS:
        fn(TALLINN, [mkcell()])
    score_p4_density(TALLINN, [mkcell()])


# ---------------------------------------------------------------------------
# Offline GML reader on the live schema shape.
# ---------------------------------------------------------------------------

def test_parse_reads_counts_and_periods(tmp_path):
    cells = parse_density_gml(write_gml(tmp_path))
    assert len(cells) == 3
    by_id = {c["cell_id"]: c for c in cells}
    assert by_id["S-10040"]["value"] == 11
    assert by_id["S-10040"]["masked"] is False
    assert by_id["S-10040"]["period"] == "1.1.2024 - 31.12.2024"
    assert by_id["S-10049"]["value"] == 244


def test_parse_converts_masked_zero_to_none(tmp_path):
    # Load-bearing: squares with <4 inhabitants read 0 on the wire
    # WITH the notApplicable flag - the reader converts to None so
    # no scorer can ever score a masked square as empty land.
    cells = parse_density_gml(write_gml(tmp_path))
    masked = {c["cell_id"]: c for c in cells}["S-10043"]
    assert masked["masked"] is True
    assert masked["value"] is None


def test_pois_skip_malformed_points():
    pois = density_cells_from_values([
        {"lat": 59.43, "lon": 24.75, "value": 100, "cell_id": "S-1"},
        {"lat": None, "lon": 24.75, "value": 100},  # skipped
        {"lon": 24.75, "value": 100},               # skipped
        {"lat": True, "lon": 24.75, "value": 100},  # skipped
        {"lat": float("nan"), "lon": 24.75, "value": 100},  # skipped
        {"lat": 59.43, "lon": 24.75, "value": -5},  # skipped
        {"lat": 59.43, "lon": 24.75, "value": True},  # skipped
    ])
    assert len(pois) == 1
    assert pois[0]["kind"] == "densitycell_p4"


# ---------------------------------------------------------------------------
# Character overlay labels (no score field).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (None, "maskeeritud hajaasustus"),
    (0, "rahulik hajaasustus"),
    (50, "rahulik hajaasustus"),
    (51, "aarelinn"),
    (500, "aarelinn"),
    (501, "eeslinn"),
    (2000, "eeslinn"),
    (2001, "linnaline"),
    (6000, "linnaline"),
    (6001, "tihe suda"),
    (15000, "tihe suda"),
])
def test_character_bands(value, expected):
    assert cell_character(value) == expected


# ---------------------------------------------------------------------------
# Taste legs: bands + masked-zero rule pinned.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (10, 30), (50, 30), (51, 45), (500, 45), (501, 60),
    (2000, 60), (2001, 70), (6000, 70), (6001, 75), (20000, 75),
])
def test_urbanist_bands_capped(value, expected):
    v, r = dim_urbanist_delight(TALLINN, [mkcell(value)])
    assert v == expected, r
    assert "hinnang" in r and "lakke 75" in r and "2024" in r


@pytest.mark.parametrize("value,expected", [
    (10, 80), (50, 80), (51, 65), (500, 65), (501, 50),
    (2000, 50), (2001, 35), (6000, 35), (6001, 25), (20000, 25),
])
def test_quiet_bands_capped(value, expected):
    v, r = dim_quiet_delight(TALLINN, [mkcell(value)])
    assert v == expected, r
    assert "hinnang" in r and "lakke 80" in r and "2024" in r


@pytest.mark.parametrize("value,expected", [
    (10, 30), (500, 45), (2000, 60), (6000, 70), (20000, 70),
])
def test_viability_floor_bands(value, expected):
    v, r = dim_services_viability(TALLINN, [mkcell(value)])
    assert v == expected, r
    assert "hinnang" in r and "elujõud" in r and "kvaliteet" in r


def test_masked_square_scores_none_never_zero():
    # Masked-zero rule pinned: a masked rural square scores None on
    # every leg, never 0/100.
    for fn in ALL_FNS:
        v, r = fn(TALLINN, [mkcell(None)])
        assert v is None, fn.__name__
        assert "maskeeritud" in r or "EI OLE" in r, fn.__name__


def test_window_boundary():
    assert CELL_WINDOW_M == 750.0
    far = mkcell(5000, lat=TALLINN[0], lon=TALLINN[1] + 0.05)  # ~2.9 km
    for fn in ALL_FNS:
        v, r = fn(TALLINN, [far])
        assert v is None, fn.__name__
        assert "EI OLE" in r


def test_dims_ignore_other_kinds():
    other = {"kind": "accident_p4", "lat": 59.4372, "lon": 24.7546}
    for fn in ALL_FNS:
        v, r = fn(TALLINN, [other])
        assert v is None, fn.__name__
        assert "EI OLE" in r


def test_all_null_for_missing_inputs_and_malformed_pois():
    bad_pois = [[{"kind": "cafe", "lat": 59.4372, "lon": 24.7546}],
                [{"kind": "densitycell_p4"}],
                [{"kind": "densitycell_p4", "lat": None, "lon": 24.75}],
                [{"kind": "densitycell_p4", "lat": 59.43, "lon": "x"}]]
    for fn in ALL_FNS:
        for origin, pois in [(None, [mkcell()]), (TALLINN, None),
                             (None, None)] + [(TALLINN, p) for p in bad_pois]:
            v, r = fn(origin, pois)
            assert v is None, (fn.__name__, origin, pois)
            assert "EI OLE" in r, fn.__name__


def test_honesty_markers():
    for fn in ALL_FNS:
        _, r = fn(TALLINN, [])
        assert "EI OLE" in r, fn.__name__
    for fn in ALL_FNS:
        v, r = fn(TALLINN, [mkcell(3000)])
        assert v is not None
        assert "hinnang" in r and "EI OLE" not in r, fn.__name__
        assert "2024" in r  # vintage rides in every scored reason


def test_registry_and_aggregator_cover_all_three():
    assert [k for k, _, _ in P4_DENSITY_DIMS] == [
        "urbanist_delight", "quiet_delight", "services_viability"]
    assert len({fn for _, _, fn in P4_DENSITY_DIMS}) == 3
    out = score_p4_density(TALLINN, [mkcell(3000)])
    assert out == {"urbanist_delight": 70, "quiet_delight": 35,
                   "services_viability": 70}
    assert score_p4_density(None, None) == {
        k: None for k, _, _ in P4_DENSITY_DIMS}
    assert p4d.P4_DENSITY_DIMS is P4_DENSITY_DIMS
