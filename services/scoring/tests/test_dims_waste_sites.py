"""Hermetic unit tests for the waste-site avoidance dim (issue #534).

No network, no snapshot: all POIs are synthetic. Run from repo root:
  python3 -m pytest services/scoring/tests/test_dims_waste_sites.py -q
"""

import os

import dims_waste_sites as W
from dims_waste_sites import dim_waste_site, fetch_cached

TALLINN = (59.4372, 24.7536)  # city centre reference origin


def poi(kind, metres_north, lon_off=0.0, **extra):
    """Synthetic POI `metres_north` metres north of TALLINN."""
    p = {"kind": kind, "lat": TALLINN[0] + metres_north / 111320.0,
         "lon": TALLINN[1] + lon_off}
    p.update(extra)
    return p


def test_none_when_missing():
    assert dim_waste_site(None, [])[0] is None
    assert dim_waste_site(TALLINN, None)[0] is None
    assert dim_waste_site(None, None)[0] is None


def test_bands():
    assert dim_waste_site(TALLINN, [poi("wastesite", 300)])[0] == 35
    assert dim_waste_site(TALLINN, [poi("wastesite", 500)])[0] == 35
    assert dim_waste_site(TALLINN, [poi("wastesite", 800)])[0] == 55
    assert dim_waste_site(TALLINN, [poi("wastesite", 1000)])[0] == 55
    assert dim_waste_site(TALLINN, [poi("wastesite", 1500)])[0] == 70
    assert dim_waste_site(TALLINN, [poi("wastesite", 2000)])[0] == 70


def test_null_beyond_window_never_no_smell():
    # Beyond ~2 km (or no join at all) stays NULL — never "no smell".
    # NOTE: the poi() helper places points with a ~0.1% shortfall, so the
    # just-beyond-window case uses 2200 m to sit truly outside 2000 m.
    for pois in ([], [poi("wastesite", 2200)], [poi("wastesite", 5000)]):
        score, reason = dim_waste_site(TALLINN, pois)
        assert score is None
        assert "EI OLE" in reason
        assert "tuul" in reason and "lõhn" in reason
        assert "lõhna pole" not in reason and "no smell" not in reason.lower()


def test_p54_distinction():
    # p54 collection points (wastepoint) must NOT score as treatment sites.
    pois = [poi("wastepoint", 50), poi("wastepoint", 100)]
    score, reason = dim_waste_site(TALLINN, pois)
    assert score is None
    assert "EI OLE" in reason
    # Malformed sites are skipped, never faked.
    bad = [{"kind": "wastesite"},
           {"kind": "wastesite", "lat": None, "lon": None},
           {"kind": "wastesite", "lat": True, "lon": 24.75}]
    assert dim_waste_site(TALLINN, bad)[0] is None
    # A real site still wins when mixed with collection points.
    mixed = [poi("wastepoint", 20), poi("wastesite", 400)]
    assert dim_waste_site(TALLINN, mixed)[0] == 35


def test_site_type_slice():
    # Harvest-normalised site_type is named in the reason (scorer-only).
    score, reason = dim_waste_site(
        TALLINN, [poi("wastesite", 400, site_type="prügila")])
    assert score == 35
    assert "prügila" in reason
    assert "hinnang" in reason
    # Unknown/absent type still scores off distance alone.
    score2, reason2 = dim_waste_site(TALLINN, [poi("wastesite", 400)])
    assert score2 == 35
    assert "hinnang" in reason2
    # Garbage types are ignored, never crash or fake.
    for junk in ("", "   ", None, 42, ["x"]):
        s, _ = dim_waste_site(TALLINN, [poi("wastesite", 400, site_type=junk)])
        assert s == 35


def test_honesty_labels():
    for origin, pois in ((None, None), (TALLINN, None), (TALLINN, []),
                         (TALLINN, [poi("wastesite", 300)]),
                         (TALLINN, [poi("wastesite", 5000)])):
        _, reason = dim_waste_site(origin, pois)
        low = reason.lower()
        assert "hinnang" in low or "ei ole" in low, reason
        # Forbidden: presenting distance as a measured smell ("kaugus pole
        # mõõdetud lõhn" is honest negation and MUST stay allowed).
        for unit in ("OU/m", "mg/m3", "lõhna pole", "lõhnavaba"):
            assert unit not in reason, reason


def test_scores_within_bounds():
    for pois in ([poi("wastesite", 100)], [poi("wastesite", 900)],
                 [poi("wastesite", 1900)]):
        score, _ = dim_waste_site(TALLINN, pois)
        assert score is not None and 0 <= score <= 100


def test_probe_constants():
    # Dated probe evidence pinned: feature type, CRS, Harjumaa-window hits.
    assert W.WFS_TYPE_NAME == \
        "US_jaatmekaitlus:US.EnvironmentalManagementFacility"
    assert "US_jaatmekaitlus" in W.WFS_CAPABILITIES_URL
    assert W.HARJUMAA_WINDOW_HITS == 1301
    assert W.WASTE_SITES_DIM == "waste_site"


def test_fetch_cached_cache_hit_makes_no_request(tmp_path, monkeypatch):
    cached = tmp_path / "caps.xml"
    cached.write_bytes(b"x" * 5000)
    import time
    fresh = time.time()
    os.utime(str(cached), (fresh, fresh))

    def _boom(*a, **k):
        raise AssertionError("no request on a fresh cache hit")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert fetch_cached("http://example.invalid/x", str(tmp_path),
                        "caps.xml") == str(cached)


def test_fetch_cached_never_caches_errors(tmp_path, monkeypatch):
    import urllib.request

    class _Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"tiny-error-page"

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp())
    assert fetch_cached("http://example.invalid/x", str(tmp_path),
                        "caps.xml") is None
    assert not os.path.exists(str(tmp_path / "caps.xml"))
