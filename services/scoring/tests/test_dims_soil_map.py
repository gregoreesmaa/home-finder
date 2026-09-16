"""Hermetic unit tests for the soil/garden suitability dim (issue #535).

No network, no snapshot: all POIs are synthetic. Run from repo root:
  python3 -m pytest services/scoring/tests/test_dims_soil_map.py -q
"""

import os

import dims_soil_map as S
from dims_soil_map import dim_soil_suitability, fetch_cached

# Viimsi reference origin (rural-parcel phenomenon, not Tallinn gradient).
VIIMSI = (59.5120, 24.8380)
# Kesklinn reference origin (city soil: disturbed fill, map not valid).
KESKLINN = (59.4372, 24.7536)


def poi(kind, origin, metres_north, **extra):
    """Synthetic POI `metres_north` metres north of `origin`."""
    p = {"kind": kind, "lat": origin[0] + metres_north / 111320.0,
         "lon": origin[1]}
    p.update(extra)
    return p


def soil(origin, metres_north, family, code="sl", urban=False):
    return poi("soil_parcel", origin, metres_north, family=family,
               code=code, urban=urban)


def test_none_when_missing():
    assert dim_soil_suitability(None, [])[0] is None
    assert dim_soil_suitability(VIIMSI, None)[0] is None
    assert dim_soil_suitability(None, None)[0] is None


def test_family_bands():
    # Memoir-calibrated mapping table, pinned end to end.
    assert dim_soil_suitability(
        VIIMSI, [soil(VIIMSI, 100, "saviliiv")])[0] == 85
    assert dim_soil_suitability(
        VIIMSI, [soil(VIIMSI, 100, "liiv", code="l")])[0] == 70
    assert dim_soil_suitability(
        VIIMSI, [soil(VIIMSI, 100, "liivsavi", code="ls2")])[0] == 65
    assert dim_soil_suitability(
        VIIMSI, [soil(VIIMSI, 100, "leede", code="LP")])[0] == 55
    assert dim_soil_suitability(
        VIIMSI, [soil(VIIMSI, 100, "paepealne", code="Kh")])[0] == 50
    assert dim_soil_suitability(
        VIIMSI, [soil(VIIMSI, 100, "savi", code="s")])[0] == 40
    assert dim_soil_suitability(
        VIIMSI, [soil(VIIMSI, 100, "glei", code="G")])[0] == 30
    assert dim_soil_suitability(
        VIIMSI, [soil(VIIMSI, 100, "turvas", code="t3")])[0] == 25
    # Raw code is named in the reason (traceable to the šifr).
    _, reason = dim_soil_suitability(VIIMSI, [soil(VIIMSI, 100, "turvas")])
    assert "sl" in reason and "hinnang" in reason


def test_null_in_cities():
    # A Kesklinn parcel with an urban-flagged join scores None, never 0.
    score, reason = dim_soil_suitability(
        KESKLINN, [soil(KESKLINN, 50, "saviliiv", urban=True)])
    assert score is None
    assert "EI OLE" in reason
    assert score != 0
    # Urban flag on a rural parcel also NULLs (mask is authoritative).
    assert dim_soil_suitability(
        VIIMSI, [soil(VIIMSI, 50, "saviliiv", urban=True)])[0] is None


def test_null_beyond_window_and_unknown():
    # NOTE: poi() places ~0.1% short, so beyond-window uses 400 m.
    score, reason = dim_soil_suitability(VIIMSI, [soil(VIIMSI, 400, "sl")])
    assert score is None
    assert "EI OLE" in reason
    assert dim_soil_suitability(VIIMSI, [])[0] is None
    # Unknown/missing family is never guessed — NULL, not a default band.
    for bad in ("chernozem", "", None, 42):
        s, r = dim_soil_suitability(VIIMSI, [soil(VIIMSI, 100, bad)])
        assert s is None, bad
        assert "EI OLE" in r, bad
    # Malformed POIs are skipped, never faked.
    junk = [{"kind": "soil_parcel"},
            {"kind": "soil_parcel", "lat": None, "lon": None},
            {"kind": "soil_parcel", "lat": True, "lon": 24.8}]
    assert dim_soil_suitability(VIIMSI, junk)[0] is None


def test_honesty_labels():
    for origin, pois in ((None, None), (VIIMSI, None), (VIIMSI, []),
                         (VIIMSI, [soil(VIIMSI, 100, "savi")]),
                         (KESKLINN, [soil(KESKLINN, 50, "sl", urban=True)]),
                         (VIIMSI, [soil(VIIMSI, 400, "sl")])):
        _, reason = dim_soil_suitability(origin, pois)
        low = reason.lower()
        assert "hinnang" in low or "ei ole" in low, reason
        # No agronomic-yield claims, no contamination claims.
        for unit in ("t/ha", "saagikus", "saaste", "reostus"):
            assert unit not in reason, reason


def test_scores_within_bounds():
    for fam in S.SOIL_BANDS:
        score, _ = dim_soil_suitability(VIIMSI, [soil(VIIMSI, 100, fam)])
        assert score is not None and 0 <= score <= 100


def test_probe_constants():
    # Dated probe evidence pinned: feature type, CRS, counts, memoir cite.
    assert S.WFS_TYPE_NAME == "SO_pinnas:SO.SoilBody"
    assert "SO_pinnas" in S.WFS_CAPABILITIES_URL
    assert S.HARJUMAA_WINDOW_HITS == 86474
    assert S.TALLINN_BBOX_HITS == 2226
    assert "Tabel 1" in S.MEMOIR_CITE
    assert S.SOIL_DIM == "soil_suitability"
    # Eight mapped families, all bands inside 0..100.
    assert len(S.SOIL_BANDS) == 8
    assert all(0 <= v <= 100 for v in S.SOIL_BANDS.values())


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
