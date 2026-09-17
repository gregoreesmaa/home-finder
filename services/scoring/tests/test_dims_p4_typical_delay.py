"""P4 typical traffic-delay dims (issue #557): hermetic tests.

No network: the delay table is harvested by a future sampler cron,
so every test runs on fixture gps.txt snapshots and hand-built
delay cells. The snapshot fetcher is covered via a stubbed urlopen
(cache-hit performs no request; transport errors and short bodies
return None and cache nothing); scorers are proven network-free by
running them with urlopen stubbed to raise. The table schema
(corridor grain, hour bands, no school-holiday split), the delay
bands, and the NULL-missing rule (never a free-flow assumption)
are pinned here. Live jams are explicitly out - nothing here polls.
"""

import urllib.error

import dims_p4_typical_delay as p4y
import pytest
from dims_p4_typical_delay import (
    CORRIDORS,
    CORRIDOR_WINDOW_M,
    MAP_BANDS,
    WORST_BAND,
    GPS_SNAPSHOT_URL,
    SAMPLER_MIN_INTERVAL_S,
    TABLE_MIN_SAMPLES,
    aggregate_snapshots,
    build_delay_table,
    corridor_midpoint,
    corridor_of,
    dim_commute_delay,
    fetch_gps_snapshot,
    hour_band,
    load_shape_corridors,
    muu_baselines,
    parse_gps_txt,
    score_p4_delay,
    strip_ribbon,
    table_to_pois,
    track_segments,
)

# Tallinn centre: hand-built delay cells sit ~57 m east unless stated.
TALLINN = (59.4372, 24.7536)


def mkcell(factor=1.2, hour_band="hommikune tipp", n=40,
           corridor="Laagna", lat=59.4372, lon=24.7546):
    return {"kind": "delaycell_p4", "lat": lat, "lon": lon,
            "factor": factor, "hour_band": hour_band, "n": n,
            "corridor": corridor}


# Fixture gps.txt in the live field shape (CORRECTED 2026-09-17
# against the real feed: vtype,line,LONx1e6,LATx1e6,speed,heading,
# vehicle -- the catalogue had lat/lon swapped and the old parser
# read zero live rows; last line mirrors a real 10-field row).
GPS_FIXTURE = """2,15,24754600,59437200,18.5,90,1234,
2,15,24754700,59437300,,90,1235,
3,2,24754000,59437000,22.0,180,501,
7,5,24755000,59438000,15.0,999,77,
1,3,24754500,59437100,12.0,270,310,Z
9,15,24754600,59437200,18.5,90,9999,
2,15,xxx,59437200,18.5,90,1236,
2,15,24754600,59437200,999.0,90,1237,
garbage line
2,15,24754600,59437200,0.0,90,1238,
2,1,24841420,59519450,,240,1009,Z,33,Viimsi
"""


def write_gps(tmp_path):
    p = tmp_path / "gps.txt"
    p.write_text(GPS_FIXTURE, encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# Sampler fetcher: cadence guard + honest errors. No network.
# ---------------------------------------------------------------------------

def test_sampler_constants():
    assert GPS_SNAPSHOT_URL == "https://transport.tallinn.ee/gps.txt"
    assert SAMPLER_MIN_INTERVAL_S == 60  # polite 60 s+ cadence
    assert TABLE_MIN_SAMPLES == 20
    assert CORRIDOR_WINDOW_M == 500.0


def test_fetch_cache_hit_makes_no_request(tmp_path, monkeypatch):
    dest = tmp_path / "gps.txt"
    dest.write_bytes(b"x" * 600)

    def _boom(*a, **k):
        raise AssertionError("network used on cache hit")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert fetch_gps_snapshot(str(tmp_path), "gps.txt") == str(dest)


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
    assert fetch_gps_snapshot(str(tmp_path), "gps.txt",
                              min_interval_s=0) is None
    assert not (tmp_path / "gps.txt").exists()


def test_fetch_short_body_is_not_cached_as_data(tmp_path, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: _FakeResp(b"empty", 200))
    assert fetch_gps_snapshot(str(tmp_path), "gps.txt",
                              min_interval_s=0) is None
    assert not (tmp_path / "gps.txt").exists()


def test_scorers_never_touch_network(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("scorer used the network")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    dim_commute_delay(TALLINN, [mkcell()], 8)
    score_p4_delay(TALLINN, [mkcell()], 8)


# ---------------------------------------------------------------------------
# Offline readers on the live field shape.
# ---------------------------------------------------------------------------

def test_parse_reads_positions_and_speeds(tmp_path):
    rows = parse_gps_txt(write_gps(tmp_path))
    by_veh = {r["vehicle"]: r for r in rows}
    assert by_veh["1234"]["lat"] == pytest.approx(59.4372)
    assert by_veh["1234"]["lon"] == pytest.approx(24.7546)
    assert by_veh["1234"]["speed"] == pytest.approx(18.5)
    assert by_veh["1235"]["speed"] is None  # empty speed stays None
    assert by_veh["501"]["vtype"] == 3  # tram kept with flag
    # garbage rows dropped: bad vtype 9, bad lat. Overspeed 999 and
    # zero speed keep the row with an unusable speed (None / 0.0 -
    # dropped at aggregation, like the empty-speed row 1235).
    assert "9999" not in by_veh and "1236" not in by_veh
    assert by_veh["1237"]["speed"] is None
    assert by_veh["1238"]["speed"] == pytest.approx(0.0)
    # Live 10-field row: lon/lat order, destination ignored, kept.
    assert by_veh["1009"]["lat"] == pytest.approx(59.51945)
    assert by_veh["1009"]["lon"] == pytest.approx(24.84142)
    assert by_veh["1009"]["speed"] is None  # feed carries no speeds


def test_aggregate_keeps_road_vehicles_and_drops_thin_cells():
    samples = ([{"vtype": 2, "lat": 59.43, "lon": 24.75, "speed": 20.0,
                 "hour": 8}] * 25
               + [{"vtype": 2, "lat": 59.43, "lon": 24.75, "speed": 10.0,
                   "hour": 12}] * 3  # thin midday cell: dropped
               + [{"vtype": 3, "lat": 59.43, "lon": 24.75, "speed": 22.0,
                   "hour": 8}] * 30  # trams: not road jams, dropped
               + [{"vtype": 2, "lat": 59.43, "lon": 24.75, "speed": None,
                   "hour": 8}] * 30  # no speed: dropped
               + [{"vtype": 2, "lat": 59.99, "lon": 24.99, "speed": 20.0,
                   "hour": 8}] * 30)  # off-corridor: dropped
    table = aggregate_snapshots(samples, lambda la, lo: "Laagna"
                                if abs(la - 59.43) < 0.01 else None)
    assert list(table) == [("Laagna", "hommikune tipp")]
    assert table[("Laagna", "hommikune tipp")]["n"] == 25
    assert table[("Laagna", "hommikune tipp")]["median_speed"] == \
        pytest.approx(20.0)


def test_hour_bands_pinned():
    assert hour_band(7) == hour_band(9) == "hommikune tipp"
    assert hour_band(10) == hour_band(15) == "keskpäev"
    assert hour_band(16) == hour_band(18) == "õhtune tipp"
    for h in (0, 6, 19, 23):
        assert hour_band(h) == "muu"
    assert len({hour_band(h) for h in range(24)}) == 4  # no holiday split


# ---------------------------------------------------------------------------
# Delay leg: bands + NULL-missing rule pinned.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("factor,expected", [
    (1.0, 75), (1.1, 75), (1.11, 60), (1.3, 60),
    (1.31, 45), (1.6, 45), (1.61, 30), (2.5, 30),
])
def test_delay_factor_bands(factor, expected):
    v, r = dim_commute_delay(TALLINN, [mkcell(factor)], 8)
    assert v == expected, r
    assert "hinnang" in r and "tavaline, mitte reaalajas" in r


def test_missing_hour_or_corridor_is_unknown_never_free_flow():
    # Missing hour/corridor -> NULL, never a free-flow assumption.
    for hour in (None, True, "kaheksa", -1, 24):
        v, r = dim_commute_delay(TALLINN, [mkcell()], hour)
        assert v is None, hour
        assert "EI OLE" in r
    v, r = dim_commute_delay(TALLINN, [mkcell()], 12)  # wrong band
    assert v is None and "EI OLE" in r
    far = mkcell(lat=TALLINN[0], lon=TALLINN[1] + 0.05)  # ~2.9 km
    v, r = dim_commute_delay(TALLINN, [far], 8)
    assert v is None and "EI OLE" in r
    v, r = dim_commute_delay(TALLINN, [], 8)
    assert v is None and "EI OLE" in r


def test_thin_table_cell_stays_null():
    v, r = dim_commute_delay(TALLINN, [mkcell(n=19)], 8)
    assert v is None and "EI OLE" in r
    v, _ = dim_commute_delay(TALLINN, [mkcell(n=20)], 8)
    assert v is not None


def test_garbage_factors_and_inputs_stay_null():
    for cell in (mkcell(0.9), mkcell("kiire"), mkcell(True),
                 mkcell(float("nan")), mkcell(n="palju"),
                 mkcell(n=True),
                 {"kind": "delaycell_p4", "lat": None, "lon": 24.75},
                 {"kind": "accident_p4", "lat": 59.4372, "lon": 24.7546}):
        v, r = dim_commute_delay(TALLINN, [cell], 8)
        assert v is None, cell
        assert "EI OLE" in r
    for origin, pois in [(None, [mkcell()]), (TALLINN, None),
                         (None, None)]:
        v, r = dim_commute_delay(origin, pois, 8)
        assert v is None, (origin, pois)
        assert "EI OLE" in r


def test_honesty_markers():
    v, r = dim_commute_delay(TALLINN, [mkcell(1.45, "õhtune tipp")], 17)
    assert v == 45
    assert "hinnang" in r and "EI OLE" not in r
    assert "tavaline, mitte reaalajas" in r and "Laagna" in r
    assert "garanteeritud" not in r and "reaalajas ummik" not in r


def test_registry_and_aggregator():
    assert [k for k, _, _ in p4y.P4_DELAY_DIMS] == ["commute_delay"]
    out = score_p4_delay(TALLINN, [mkcell(1.05)], 8)
    assert out == {"commute_delay": 75}
    assert score_p4_delay(None, None, None) == {"commute_delay": None}
    assert score_p4_delay(TALLINN, [mkcell()], None) == {"commute_delay": None}
    assert p4y.P4_DELAY_DIMS is p4y.P4_DELAY_DIMS


# ---------------------------------------------------------------------------
# Issue #629: corridors + vehicle-tracked segments + delay table.
# ---------------------------------------------------------------------------

def test_corridor_table_shape():
    names = [c[0] for c in CORRIDORS]
    assert len(names) == 8 and len(set(names)) == 8
    for name, poly, label in CORRIDORS:
        assert label and len(poly) >= 2
        assert all(len(p) == 2 for p in poly)
        assert corridor_midpoint(name) is not None
    assert corridor_midpoint("olematu") is None


def test_corridor_of_joins_window():
    # Laagna tee midpoint joins; far Tallinn bay does not.
    assert corridor_of(59.435, 24.830) == "Laagna tee"
    assert corridor_of(59.50, 24.60) is None
    assert corridor_of(None, 24.8) is None
    assert corridor_of(True, 24.8) is None


def _fix(vehicle, t, lat, lon):
    return {"vehicle": vehicle, "t": t, "lat": lat, "lon": lon}


def test_track_segments_filters_and_labels():
    # Two fixes 60 s apart on Laagna tee (~1.1 km at 59.4N per 0.02
    # lon... here 300 m in 60 s = 18 km/h, plausible urban bus).
    base = 1_700_000_000
    fixes = [_fix("101", base, 59.435, 24.820),
             _fix("101", base + 60, 59.435, 24.825),
             _fix("102", base, 59.435, 24.820),
             _fix("102", base + 5, 59.435, 24.900),  # teleport: dropped
             _fix("103", base, 59.50, 24.60),
             _fix("103", base + 60, 59.50, 24.61)]  # off-corridor: dropped
    segs = track_segments(fixes)
    assert len(segs) == 1
    s = segs[0]
    assert s["corridor"] == "Laagna tee"
    assert s["speed_kmh"] == pytest.approx(16.8, abs=1.5)
    assert s["hour"] == (base + 60) // 3600 % 24


def test_build_delay_table_free_flow_and_thin():
    slow = [{"corridor": "Laagna tee", "speed_kmh": 15.0, "hour": 8}] * 25
    free = [{"corridor": "Laagna tee", "speed_kmh": 30.0, "hour": 23}] * 25
    thin = [{"corridor": "Laagna tee", "speed_kmh": 10.0, "hour": 12}] * 3
    nofree = [{"corridor": "Tartu mnt", "speed_kmh": 12.0, "hour": 8}] * 25
    table = build_delay_table(slow + free + thin + nofree)
    assert table[("Laagna tee", "hommikune tipp")]["factor"] == \
        pytest.approx(2.0)
    assert ("Laagna tee", "keskpäev") not in table  # thin: NULL downstream
    assert ("Tartu mnt", "hommikune tipp") not in table  # no free-flow
    assert ("Laagna tee", "muu") not in table  # baseline, not a cell


def test_table_to_pois_shape_feeds_scorer():
    table = {("Laagna tee", "hommikune tipp"):
             {"factor": 1.5, "n": 40, "median_speed": 20.0,
              "free_speed": 30.0}}
    pois = table_to_pois(table)
    assert len(pois) == 1
    p = pois[0]
    assert p["kind"] == "delaycell_p4"
    assert p["corridor"] == "Laagna tee"
    v, _r = dim_commute_delay((p["lat"], p["lon"]), pois, 8)
    assert v == 45  # factor 1.5 -> 45, end to end


def test_muu_baselines_anchor_free_flow():
    segs = ([{"corridor": "Laagna tee", "speed_kmh": 30.0, "hour": 23}] * 25
            + [{"corridor": "Laagna tee", "speed_kmh": 28.0, "hour": 12}] * 10
            + [{"corridor": "Tartu mnt", "speed_kmh": 25.0, "hour": 8}] * 25)
    base = muu_baselines(segs)
    assert set(base) == {"Laagna tee"}  # non-muu + peak-only dropped
    assert base["Laagna tee"]["median"] == pytest.approx(30.0)
    assert base["Laagna tee"]["n"] == 25
    assert set(MAP_BANDS) == {"hommikune tipp", "keskpäev",
                              "õhtune tipp", "muu"}
    assert WORST_BAND == "worst"


# ---------------------------------------------------------------------------
# Issue #667: GTFS shape web + road-following ribbons.
# ---------------------------------------------------------------------------

def _shape_zip(tmp_path):
    """Tiny GTFS vintage: 2 routes, 3 shapes (one dup-name, one broken)."""
    import csv
    import io
    import zipfile

    def _write(zf, name, fieldnames, rows):
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
        zf.writestr(name, buf.getvalue())

    dest = str(tmp_path / "tiny-gtfs.zip")
    with zipfile.ZipFile(dest, "w") as zf:
        _write(zf, "routes.txt",
               ["route_id", "route_short_name", "route_long_name"],
               [{"route_id": "r5", "route_short_name": "5",
                 "route_long_name": "Männiku-Viru"},
                {"route_id": "r8", "route_short_name": "8",
                 "route_long_name": "Õismäe-Äigrumäe"}])
        _write(zf, "trips.txt",
               ["trip_id", "route_id", "shape_id", "trip_headsign"],
               [{"trip_id": "t1", "route_id": "r5", "shape_id": "s1",
                 "trip_headsign": "Männiku"},
                {"trip_id": "t2", "route_id": "r5", "shape_id": "s2",
                 "trip_headsign": "Männiku"},
                {"trip_id": "t3", "route_id": "r8", "shape_id": "s3",
                 "trip_headsign": "Äigrumäe"}])
        _write(zf, "shapes.txt",
               ["shape_id", "shape_pt_lon", "shape_pt_lat",
                "shape_pt_sequence"],
               [{"shape_id": "s1", "shape_pt_lon": "24.70",
                 "shape_pt_lat": "59.40", "shape_pt_sequence": "2"},
                {"shape_id": "s1", "shape_pt_lon": "24.71",
                 "shape_pt_lat": "59.41", "shape_pt_sequence": "1"},
                {"shape_id": "s2", "shape_pt_lon": "24.72",
                 "shape_pt_lat": "59.42", "shape_pt_sequence": "1"},
                {"shape_id": "s2", "shape_pt_lon": "24.73",
                 "shape_pt_lat": "59.43", "shape_pt_sequence": "2"},
                {"shape_id": "s3", "shape_pt_lon": "24.80",
                 "shape_pt_lat": "59.44", "shape_pt_sequence": "1"},
                {"shape_id": "s3", "shape_pt_lon": "bogus",
                 "shape_pt_lat": "59.45", "shape_pt_sequence": "2"},
                {"shape_id": "s4", "shape_pt_lon": "24.90",
                 "shape_pt_lat": "59.50", "shape_pt_sequence": "1"}])
    return dest


def test_load_shape_corridors_names_and_order(tmp_path):
    web = load_shape_corridors(_shape_zip(tmp_path))
    names = [c[0] for c in web]
    # s1+s2 share "5 · Männiku": second is deduped; s3 keeps one good
    # point but drops below 2 (out); s4 is a single point (out).
    assert names == ["5 · Männiku", "5 · Männiku (2)"]
    poly = web[0][1]
    assert poly[0] == (24.71, 59.41)  # sequence order, not file order
    assert poly[1] == (24.70, 59.40)
    assert web[0][2] == "Männiku-Viru"


def test_corridor_of_follows_road_not_chord():
    # L-shaped road: the chord midpoint is far from both legs.
    web = (("L-road", ((24.70, 59.40), (24.70, 59.42),
                       (24.72, 59.42)), "test"),)
    assert corridor_of(59.415, 24.701, web) == "L-road"  # on the leg
    assert corridor_of(59.415, 24.715, web) is None  # near chord, off road


def test_corridor_midpoint_middle_vertex():
    web = (("L-road", ((24.70, 59.40), (24.70, 59.42),
                       (24.72, 59.42)), "test"),)
    assert corridor_midpoint("L-road", web) == (24.70, 59.42)
    assert corridor_midpoint("L-road") is None  # not in legacy web


def test_track_segments_labels_shape_web():
    # Viimsi leg: on the shape, ~3.8 km past legacy Narva's endpoint.
    web = (("tee", ((24.815, 59.498), (24.830, 59.502)), "test"),)
    base = 1_700_000_000
    fixes = [_fix("101", base, 59.500, 24.820),
             _fix("101", base + 60, 59.500, 24.825)]
    segs = track_segments(fixes, corridors=web)
    assert len(segs) == 1 and segs[0]["corridor"] == "tee"
    assert track_segments(fixes) == []  # legacy web: off-corridor here


def test_corridor_index_matches_plain_web():
    from dims_p4_typical_delay import _as_index, build_corridor_index
    web = (("tee", ((24.815, 59.498), (24.830, 59.502)), "test"),)
    index = build_corridor_index(web)
    assert _as_index(index) is index  # prebuilt passes through untouched
    assert _as_index(None) is not None
    assert corridor_of(59.500, 24.822, index) == "tee"
    assert corridor_midpoint("tee", index) == (24.830, 59.502)
    assert corridor_midpoint("puudu", index) is None


def test_strip_ribbon_straight_rectangle():
    ring = strip_ribbon([(24.70, 59.40), (24.71, 59.40)], half_m=150.0)
    assert len(ring) == 5 and ring[0] == ring[-1]
    lats = [p[1] for p in ring]
    assert max(lats) - min(lats) == pytest.approx(300 / 111320.0, rel=0.05)
    lons = [p[0] for p in ring]
    assert min(lons) == pytest.approx(24.70) and max(lons) == pytest.approx(
        24.71)


def test_strip_ribbon_follows_elbow_and_degenerate():
    ring = strip_ribbon([(24.70, 59.40), (24.70, 59.42), (24.72, 59.42)],
                        half_m=150.0)
    assert len(ring) == 7 and ring[0] == ring[-1]  # 3+3, closed
    lons = [p[0] for p in ring]
    # elbow vertex (index 1 left / 4 right) straddled roadside, on-map
    assert lons[1] < 24.70 < lons[4]
    assert max(lons) == pytest.approx(24.72)  # end vertex: no overshoot
    assert strip_ribbon([]) == []
    assert strip_ribbon([(24.70, 59.40)]) == []
