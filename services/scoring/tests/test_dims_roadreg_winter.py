"""Hermetic unit tests for the measured winter-maintenance dim (issue #536).

No network, no snapshot: all POIs are synthetic. Run from repo root:
  python3 -m pytest services/scoring/tests/test_dims_roadreg_winter.py -q
"""

import os

import dims_roadreg_winter as R
from dims_roadreg_winter import (
    audit_surface_against,
    dim_winter_road_class_measured,
    fetch_cached,
    remap_maintenance_class,
)

TALLINN = (59.4372, 24.7536)  # city centre reference origin


def poi(kind, metres_north, lon_off=0.0, **extra):
    """Synthetic POI `metres_north` metres north of TALLINN."""
    p = {"kind": kind, "lat": TALLINN[0] + metres_north / 111320.0,
         "lon": TALLINN[1] + lon_off}
    p.update(extra)
    return p


def winter(metres_north, maint_class, **extra):
    return poi("roadwinter_p4", metres_north, maint_class=maint_class,
               **extra)


def test_none_when_missing():
    assert dim_winter_road_class_measured(None, [])[0] is None
    assert dim_winter_road_class_measured(TALLINN, None)[0] is None
    assert dim_winter_road_class_measured(None, None)[0] is None


def test_bands_match_fixture_shape():
    # P4-018 fixture shape kept exactly: 1→85, 2→65, 3→45, 4→30.
    assert dim_winter_road_class_measured(
        TALLINN, [winter(100, "1")])[0] == 85
    assert dim_winter_road_class_measured(
        TALLINN, [winter(100, "2")])[0] == 65
    assert dim_winter_road_class_measured(
        TALLINN, [winter(100, "3")])[0] == 45
    assert dim_winter_road_class_measured(
        TALLINN, [winter(100, "4")])[0] == 30
    # Measured join says teeregister in the reason (vs. fixture slice).
    _, reason = dim_winter_road_class_measured(TALLINN, [winter(100, "1")])
    assert "teeregister" in reason.lower()
    assert "hinnang" in reason.lower()


def test_null_without_join_never_default_class():
    # NOTE: poi() places ~0.1% short, so beyond-window uses 200 m.
    for pois in ([], [winter(200, "1")], [winter(1000, "2")]):
        score, reason = dim_winter_road_class_measured(TALLINN, pois)
        assert score is None
        assert "EI OLE" in reason


def test_unknown_class_fails_closed():
    # Unseen hoolklt values stay NULL with a remap reason — never guessed.
    for raw in ("A", "talv-1", "0", "5", "", "  ", None, 1, True):
        score, reason = dim_winter_road_class_measured(
            TALLINN, [winter(100, raw)])
        assert score is None, raw
        assert "EI OLE" in reason, raw
    # Whitespace-tolerant on the documented positions.
    assert dim_winter_road_class_measured(
        TALLINN, [winter(100, " 2 ")])[0] == 65


def test_fixture_kind_never_cross_scores():
    # Old fixture kind (dims_p4_trans roadclass_p4) must not score here…
    assert dim_winter_road_class_measured(
        TALLINN, [poi("roadclass_p4", 50, maint_class="1")])[0] is None
    # …and malformed measured POIs are skipped, never faked.
    bad = [{"kind": "roadwinter_p4"},
           {"kind": "roadwinter_p4", "lat": None, "lon": None},
           {"kind": "roadwinter_p4", "lat": True, "lon": 24.75}]
    assert dim_winter_road_class_measured(TALLINN, bad)[0] is None


def test_remap_table():
    assert remap_maintenance_class("1") == "1"
    assert remap_maintenance_class("4") == "4"
    assert remap_maintenance_class(" 3 ") == "3"
    for raw in ("0", "5", "A", "", None, 1, 2.0, True, ["1"]):
        assert remap_maintenance_class(raw) is None, raw


def test_surface_audit():
    verdict, note = audit_surface_against("asfalt", "asfalt")
    assert verdict == "match"
    assert "aus" in note
    verdict, note = audit_surface_against("kruus", "asfalt")
    assert verdict == "mismatch"
    assert "register" in note and "OSM" in note
    # Case/whitespace-tolerant, missing side → unknown (never a verdict).
    assert audit_surface_against("  Kruus ", "kruus")[0] == "match"
    for reg, osm in ((None, "asfalt"), ("kruus", None), (None, None),
                     ("", "asfalt"), (42, "asfalt")):
        verdict, note = audit_surface_against(reg, osm)
        assert verdict == "unknown", (reg, osm)
        assert "EI OLE" in note, (reg, osm)


def test_honesty_labels():
    for origin, pois in ((None, None), (TALLINN, None), (TALLINN, []),
                         (TALLINN, [winter(100, "1")]),
                         (TALLINN, [winter(1000, "1")]),
                         (TALLINN, [winter(100, "A")])):
        _, reason = dim_winter_road_class_measured(origin, pois)
        low = reason.lower()
        assert "hinnang" in low or "ei ole" in low, reason
        # Class is not punctuality; volumes are not claimed.
        for unit in ("sahke", "liiklussagedus", "ööpäevane liiklus"):
            assert unit not in reason, reason


def test_scores_within_bounds():
    for cls in ("1", "2", "3", "4"):
        score, _ = dim_winter_road_class_measured(TALLINN, [winter(80, cls)])
        assert score is not None and 0 <= score <= 100


def test_probe_constants():
    # Dated probe evidence pinned: winter type, code attrs, Harjumaa hits.
    assert R.WFS_WINTER_TYPE == "ms:n_seisund_talvine"
    assert R.WFS_WINTER_CODE_ATTR == "hoolklt_hoolklt_xv"
    assert R.WFS_WINTER_VALUE_ATTR == "hoolklt_hoolklt_val"
    assert R.HARJUMAA_WINTER_HITS == 568
    assert "teeregister.mnt.ee" in R.WFS_CAPABILITIES_URL
    assert "TN_teeregister" in R.WFS_INSPIRE_URL
    assert R.ROADREG_WINTER_DIM == "winter_road_class_measured"
    assert R.WINTER_BANDS == {"1": 85, "2": 65, "3": 45, "4": 30}


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
