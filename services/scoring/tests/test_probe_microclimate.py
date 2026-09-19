"""Probe guard for #661: verdict is dated and machine-checkable,
plus the no-interpolation guard for the 3-station normals.

Resolved normals module: services/scoring/dims_p4_kliima_stations.py
(there is no dims_kliima_normals module; the kliima scorer precedent is
dims_p4_kliima.py for strategy legs and dims_p4_kliima_stations.py for
the Harku/Pakri/Kuusiku station cells).
"""
from services.scoring.probe_microclimate import MICROCLIMATE_VERDICT


def test_verdict_is_dated_and_explicit():
    assert MICROCLIMATE_VERDICT["checked"] >= "2026-09-19"
    assert MICROCLIMATE_VERDICT["kind"] in ("negative", "positive")
    if MICROCLIMATE_VERDICT["kind"] == "positive":
        assert MICROCLIMATE_VERDICT["follow_up"] is not None


def test_no_interpolation_between_three_stations():
    """The 3-station normals (Harku/Pakri/Kuusiku) must never be interpolated."""
    from services.scoring import dims_p4_kliima_stations as k
    assert getattr(k, "INTERPOLATE_BETWEEN_STATIONS", False) is False
    # Load-bearing half: assignment is winner-takes-nearest (one code,
    # never a blend), and scored reasons say so on the surface.
    assert set(k.HARJUMAA_STATIONS) == {"AJHARK01", "AJPAKR01", "AJKUUS01"}
    assert k.nearest_station((59.4370, 24.7536)) in k.HARJUMAA_STATIONS
    score, reason = k.dim_winter_mildness(
        (59.4370, 24.7536),
        {"AJHARK01": {"frost_days": 100.0},
         "AJPAKR01": {"frost_days": 90.0},
         "AJKUUS01": {"frost_days": 110.0}})
    assert score in (40, 55, 70)
    assert "interpolatsiooni pole" in reason
