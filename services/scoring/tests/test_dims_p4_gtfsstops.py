"""P4 GTFS stop overlay (issue #483): hermetic tests.

No network: every reader/scorer below runs on in-file GTFS fixtures and
OSM rail rows. Pins: window counts (Wed all-day / evening floor /
Saturday), mode mapping incl. route_type-wins conflicts, malformed-row
drops, GTFS points carrying scheduled t but no OSM tags, Elron stations
mapped-only (position + real railway tags, never t), and — the #483 AC —
evening-RIDERSHIP NULLs staying NULL with EI OLE reasons in the
dims_p4_elron / dims_p4_tlt P4-032 slices while the peatus scheduled-
evening leg still scores from deps_eve (schedules are not ridership).
"""

import inspect

import dims_p4_elron as elron_mod
import dims_p4_gtfsstops as gs
import dims_p4_tlt as tlt_mod
from dims_p4_elron import dim_elron_evening_ridership
from dims_p4_peatus import dim_third_places
from dims_p4_tlt import dim_tlt_evening_ridership

TALLINN = (59.4372, 24.7536)

# -- Minimal GTFS fixture: bus line 1 + tram T2, Wed + Sat services. -------

CAL = [
    {"service_id": "W", "monday": "1", "tuesday": "1", "wednesday": "1",
     "thursday": "1", "friday": "1", "saturday": "0", "sunday": "0",
     "start_date": "20260801", "end_date": "20270901"},
    {"service_id": "S", "monday": "0", "tuesday": "0", "wednesday": "0",
     "thursday": "0", "friday": "0", "saturday": "1", "sunday": "0",
     "start_date": "20260801", "end_date": "20270901"},
]

ROUTES = [
    {"route_id": "tallinna-lin_bus_1", "route_short_name": "1",
     "route_long_name": "A - B", "route_desc": "", "route_type": "3",
     "route_url": "", "route_color": "", "route_text_color": "",
     "route_sort_order": "1"},
    {"route_id": "tallinna-lin_tram_T2", "route_short_name": "T2",
     "route_long_name": "C - D", "route_desc": "", "route_type": "900",
     "route_url": "", "route_color": "", "route_text_color": "",
     "route_sort_order": "2"},
    # Conflict fixture: segment says bus, route_type says tram — type wins.
    {"route_id": "tallinna-lin_bus_X", "route_short_name": "X",
     "route_long_name": "E - F", "route_desc": "", "route_type": "900",
     "route_url": "", "route_color": "", "route_text_color": "",
     "route_sort_order": "3"},
]

TRIPS = [
    {"trip_id": "b1", "route_id": "tallinna-lin_bus_1", "service_id": "W",
     "trip_headsign": "B", "direction_id": "0", "block_id": "",
     "shape_id": "", "wheelchair_accessible": "", "block_code": "",
     "vehicle_type": "", "thoreb_id": "", "trip_short_name": ""},
    {"trip_id": "t1", "route_id": "tallinna-lin_tram_T2", "service_id": "W",
     "trip_headsign": "D", "direction_id": "0", "block_id": "",
     "shape_id": "", "wheelchair_accessible": "", "block_code": "",
     "vehicle_type": "", "thoreb_id": "", "trip_short_name": ""},
    {"trip_id": "bS", "route_id": "tallinna-lin_bus_1", "service_id": "S",
     "trip_headsign": "B", "direction_id": "0", "block_id": "",
     "shape_id": "", "wheelchair_accessible": "", "block_code": "",
     "vehicle_type": "", "thoreb_id": "", "trip_short_name": ""},
    {"trip_id": "x1", "route_id": "tallinna-lin_bus_X", "service_id": "W",
     "trip_headsign": "F", "direction_id": "0", "block_id": "",
     "shape_id": "", "wheelchair_accessible": "", "block_code": "",
     "vehicle_type": "", "thoreb_id": "", "trip_short_name": ""},
]

STOPS = [
    {"stop_id": "s1", "stop_code": "1-1", "stop_name": "Vabaduse",
     "stop_desc": "", "stop_lat": "59.4330", "stop_lon": "24.7500",
     "stop_url": "", "location_type": "", "parent_station": "",
     "thoreb_id": "1001"},
    {"stop_id": "s2", "stop_code": "2-1", "stop_name": "Balti",
     "stop_desc": "", "stop_lat": "59.4405", "stop_lon": "24.7369",
     "stop_url": "", "location_type": "", "parent_station": "",
     "thoreb_id": "1002"},
    # Malformed: no usable coords — must be skipped, never faked.
    {"stop_id": "bad", "stop_code": "", "stop_name": "Katkine",
     "stop_desc": "", "stop_lat": "", "stop_lon": "24.7",
     "stop_url": "", "location_type": "", "parent_station": "",
     "thoreb_id": ""},
]


def _st(trip, stop, dep):
    return {"trip_id": trip, "stop_id": stop, "departure_time": dep,
            "arrival_time": dep, "stop_sequence": "1"}


STOP_TIMES = [
    _st("b1", "s1", "07:00:00"),
    _st("b1", "s2", "07:10:00"),
    _st("b1", "s1", "19:30:00"),  # evening Wed (bus)
    _st("t1", "s2", "08:00:00"),
    _st("t1", "s2", "20:15:00"),  # evening Wed (tram)
    _st("bS", "s1", "10:00:00"),  # Saturday (bus)
    _st("x1", "s2", "09:00:00"),  # conflict-route trip
    _st("ghost", "s1", "12:00:00"),  # unknown trip — ignored
    _st("b1", "", "12:30:00"),  # missing stop_id — ignored
]

GTFS = {"calendar.txt": CAL, "trips.txt": TRIPS, "stop_times.txt": STOP_TIMES,
        "stops.txt": STOPS, "routes.txt": ROUTES}

ELRON_ROWS = [
    {"lon": 24.7369, "lat": 59.4405,
     "tags": {"railway": "station", "public_transport": "station"}},
    {"lon": 24.7972, "lat": 59.4236,
     "tags": {"railway": "stop", "public_transport": "stop_position"}},
    {"lon": "x", "lat": 59.0},  # junk — dropped
]


def test_services_for_picks_weekday_columns():
    assert gs.services_for(CAL, "wednesday") == {"W"}
    assert gs.services_for(CAL, "saturday") == {"S"}
    assert gs.services_for(CAL, "sunday") == set()


def test_window_counts_wednesday_all_day():
    cnt = gs.window_counts(GTFS, {"W"})
    assert cnt == {"s1": 2, "s2": 4}


def test_window_counts_evening_floor_is_string_safe():
    cnt = gs.window_counts(GTFS, {"W"}, after=gs.EVENING_FROM)
    assert cnt == {"s1": 1, "s2": 1}


def test_window_counts_saturday():
    cnt = gs.window_counts(GTFS, {"S"})
    assert cnt == {"s1": 1}


def test_stop_modes_bus_tram_mixed_and_conflict():
    modes = gs.stop_modes(GTFS)
    assert modes["s1"] == "buss"  # bus only
    assert modes["s2"] == "mitu"  # bus + tram + conflict route
    # route_type wins over the route_id segment on conflict routes:
    only_x = {"trips.txt": [t for t in TRIPS if t["trip_id"] == "x1"],
              "stop_times.txt": [_st("x1", "s9", "09:00:00")],
              "routes.txt": ROUTES}
    assert gs.stop_modes(only_x) == {"s9": "tramm"}


def test_stop_coords_skips_malformed_never_faked():
    coords = gs.stop_coords(STOPS)
    assert set(coords) == {"s1", "s2"}
    assert coords["s1"] == (24.75, 59.433)


def test_overlay_points_gtfs_leg():
    coords = gs.stop_coords(STOPS)
    pts, stats = gs.overlay_points(coords, {"s1": 3, "s2": 4},
                                   {"s1": "buss", "s2": "mitu"}, [])
    by_lon = {p["lon"]: p for p in pts}
    assert by_lon[24.75]["t"] == 3
    assert by_lon[24.7369]["t"] == 4
    # GTFS points carry no OSM tags (unverified mapping is not claimed)...
    assert all("tags" not in p for p in pts)
    # ...and no ridership keys anywhere (GTFS static has no occupancy).
    assert all(set(p) <= {"lon", "lat", "t", "tags"} for p in pts)
    assert stats["gtfs_stops"] == 2
    assert stats["gtfs_with_wed"] == 2
    assert stats["elron_mapped"] == 0
    assert stats["total"] == 2


def test_overlay_points_missing_wednesday_stays_unknown_not_zero():
    coords = gs.stop_coords(STOPS)
    pts, stats = gs.overlay_points(coords, {"s1": 3}, {"s1": "buss"}, [])
    by_lon = {p["lon"]: p for p in pts}
    assert "t" not in by_lon[24.7369]  # unknown, never a faked 0
    assert stats["gtfs_with_wed"] == 1


def test_overlay_points_elron_mapped_only():
    pts, stats = gs.overlay_points({}, {}, {}, ELRON_ROWS)
    assert len(pts) == 2
    assert stats["elron_mapped"] == 2
    assert stats["total"] == 2
    for p in pts:
        # Mapped position only: real railway tags, never a t count.
        assert "t" not in p
        assert p["tags"]["railway"] in ("station", "stop")
    modes = {p["tags"]["railway"] for p in pts}
    assert modes == {"station", "stop"}


def test_module_adds_no_network_calls():
    src = inspect.getsource(gs)
    for marker in ("urlopen", "httpx", "requests.get", "urllib", "socket"):
        assert marker not in src


# -- #483 AC: evening RIDERSHIP stays NULL with EI OLE reasons. -------------

OVERLAY_POIS = [
    {"kind": "stop_p4", "lat": 59.433, "lon": 24.75, "deps_wed": 120,
     "deps_prev": None, "deps_eve": 14, "deps_sat": 60},
    {"lon": 24.7369, "lat": 59.4405,
     "tags": {"railway": "station", "public_transport": "station"}},
]


def test_elron_evening_ridership_null_with_ei_ole():
    for origin, pois in [(TALLINN, OVERLAY_POIS), (TALLINN, []),
                         (None, None), (TALLINN, None)]:
        v, reason = dim_elron_evening_ridership(origin, pois)
        assert v is None
        assert "EI OLE" in reason
        assert "hinnang" in reason


def test_tlt_evening_ridership_null_with_ei_ole():
    for origin, pois in [(TALLINN, OVERLAY_POIS), (TALLINN, []),
                         (None, None), (TALLINN, None)]:
        v, reason = dim_tlt_evening_ridership(origin, pois)
        assert v is None
        assert "EI OLE" in reason
        assert "hinnang" in reason


def test_ridership_nulls_name_usage_not_safety():
    # P4-032 is a usage proxy, never a safety verdict (PPA explicitly
    # NOT a source) — pinned on both operator slices.
    for fn in (dim_elron_evening_ridership, dim_tlt_evening_ridership):
        _, reason = fn(TALLINN, OVERLAY_POIS)
        assert "kasutus" in reason


def test_scheduled_evening_still_scores_ridership_does_not():
    # The distinction the overlay is built on: scheduled evening
    # departures (deps_eve from GTFS) score the access leg, while
    # ridership (occupancy, unpublished) stays NULL on both slices.
    v, reason = dim_third_places(
        TALLINN, [{"kind": "stop_p4", "lat": 59.433, "lon": 24.75,
                   "deps_eve": 14}])
    assert v is not None and 0 <= v <= 100
    assert "hinnang" in reason
    v, reason = dim_third_places(
        TALLINN, [{"kind": "stop_p4", "lat": 59.433, "lon": 24.75}])
    assert v is None
    assert "EI OLE" in reason


def test_sibling_modules_add_no_network_calls():
    for mod in (elron_mod, tlt_mod):
        src = inspect.getsource(mod)
        assert "urlopen" not in src
        assert "urllib" not in src
