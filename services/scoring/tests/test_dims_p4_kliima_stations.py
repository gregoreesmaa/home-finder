"""P4 microclimate-cell dims (issue #541): hermetic tests.

No network: fetch_climate_rows is never called here (its contract --
single polite GETs, file cache, TTL, transport errors raise -- is
covered via the pure cache_is_fresh + build_climate_url helpers).
Nearest-station assignment runs on the REAL probed coords; ranking
runs on SYNTHETIC 1991-2020 normals fixtures (invented numbers in the
real join shape -- never a real pull). NULL rules (>=2 joined cells
required, no interpolation) are pinned.
"""

import dims_p4_kliima_stations as kli
from dims_p4_kliima_stations import (
    CLIMATE_TTL_DAYS,
    HARJUMAA_STATIONS,
    NORMALS_END,
    NORMALS_START,
    P4_KLIIMA_STATIONS_DIMS,
    build_climate_url,
    cache_is_fresh,
    dim_wetness,
    dim_winter_mildness,
    nearest_station,
    score_p4_kliima_stations,
)

TALLINN = (59.4372, 24.7536)      # nearest: Harku
PALDISKI = (59.3127, 24.0543)     # nearest: Pakri
KOHILA = (59.1637, 24.7483)       # nearest: Kuusiku (south)
LOKSA = (59.5778, 25.7396)        # east corner: nearest of the three

CELLS = {
    "AJHARK01": {"frost_days": 100.0, "precip_mm": 700.0},
    "AJPAKR01": {"frost_days": 95.0, "precip_mm": 650.0},
    "AJKUUS01": {"frost_days": 115.0, "precip_mm": 750.0},
}


def test_station_roster_is_three_usable_cells():
    assert set(HARJUMAA_STATIONS) == {"AJHARK01", "AJPAKR01", "AJKUUS01"}
    assert NORMALS_START == 1991 and NORMALS_END == 2020  # WMO window


def test_nearest_station_uses_probed_coords():
    assert nearest_station(TALLINN) == "AJHARK01"
    assert nearest_station(PALDISKI) == "AJPAKR01"
    assert nearest_station(KOHILA) == "AJKUUS01"
    # Eastern corner falls to the nearest of the three (coarse, named).
    assert nearest_station(LOKSA) in HARJUMAA_STATIONS
    assert nearest_station(None) is None


def test_winter_rank_mildest_70_middle_55_harshest_40():
    assert dim_winter_mildness(PALDISKI, CELLS)[0] == 70   # 95 mildest
    assert dim_winter_mildness(TALLINN, CELLS)[0] == 55    # 100 middle
    assert dim_winter_mildness(KOHILA, CELLS)[0] == 40     # 115 harshest
    _, reason = dim_winter_mildness(PALDISKI, CELLS)
    assert "Pakri" in reason  # station named (coarseness visible)
    assert "1991" in reason and "2020" in reason  # window stated
    assert "interpolatsiooni pole" in reason  # no-interpolation legend


def test_wetness_rank_driest_70_wettest_40():
    assert dim_wetness(PALDISKI, CELLS)[0] == 70   # 650 driest
    assert dim_wetness(TALLINN, CELLS)[0] == 55    # 700 middle
    assert dim_wetness(KOHILA, CELLS)[0] == 40     # 750 wettest
    _, reason = dim_wetness(KOHILA, CELLS)
    assert "kuivem" in reason


def test_ties_share_the_better_band_and_two_cells_score_70_40():
    tied = {"AJHARK01": {"frost_days": 100.0},
            "AJPAKR01": {"frost_days": 100.0},
            "AJKUUS01": {"frost_days": 120.0}}
    assert dim_winter_mildness(TALLINN, tied)[0] == 70
    assert dim_winter_mildness(PALDISKI, tied)[0] == 70
    pair = {"AJHARK01": {"frost_days": 100.0},
            "AJPAKR01": {"frost_days": 90.0}}
    assert dim_winter_mildness(TALLINN, pair)[0] == 40
    assert dim_winter_mildness(PALDISKI, pair)[0] == 70


def test_single_cell_or_missing_join_is_null():
    solo = {"AJHARK01": {"frost_days": 100.0, "precip_mm": 700.0}}
    for origin, cells in [(TALLINN, solo), (TALLINN, None),
                          (TALLINN, {}), (None, CELLS),
                          (None, None)]:
        for dim in (dim_winter_mildness, dim_wetness):
            v, reason = dim(origin, cells)
            assert v is None
            assert "EI OLE" in reason
    # Nearest cell present but its indicator missing: NULL, not a guess.
    gap = {"AJHARK01": {"precip_mm": 700.0},
           "AJPAKR01": {"frost_days": 95.0, "precip_mm": 650.0}}
    v, _ = dim_winter_mildness(TALLINN, gap)
    assert v is None
    v, _ = dim_wetness(TALLINN, gap)
    assert v == 40  # wetness join complete, two cells: worse is 40


def test_registry_and_rollup():
    assert set(P4_KLIIMA_STATIONS_DIMS) == {"winter_mildness", "wetness"}
    assert P4_KLIIMA_STATIONS_DIMS["winter_mildness"][1] is dim_winter_mildness
    assert P4_KLIIMA_STATIONS_DIMS["wetness"][1] is dim_wetness
    assert kli.P4_KLIIMA_STATIONS_DIMS is P4_KLIIMA_STATIONS_DIMS
    dims, reasons = score_p4_kliima_stations(TALLINN, CELLS)
    assert dims == {"winter_mildness": 55, "wetness": 55}
    assert len(reasons) == 2
    dims, reasons = score_p4_kliima_stations(None, None)
    assert dims == {"winter_mildness": None, "wetness": None}
    assert reasons == []


def test_fetch_helpers_are_pure():
    assert CLIMATE_TTL_DAYS == 365  # CONT feed: annual harvest
    url = build_climate_url("f_kliima_kuu",
                            {"aasta": "eq.2023", "kuu": "eq.12"})
    assert url == ("https://keskkonnaandmed.envir.ee/f_kliima_kuu?"
                   "aasta=eq.2023&kuu=eq.12")  # confirmed probe pattern
    assert cache_is_fresh("/nonexistent/kliima.json") is False
