"""P4 trans dims (issues #275 + #349): hermetic tests.

No network: the accident CSV is open but bulk-pulling it in unit tests
would be impolite, and Tark Tee / noise / teeregister feeds are dated
negatives (see dims_p4_trans docstring) - so every test runs on fixture
row-dicts and hand-built POIs. The polite fetcher is covered via a
stubbed urlopen (cache-hit performs no request; transport errors and
short bodies return None and cache nothing); scorers are proven
network-free by running them with urlopen stubbed to raise. The CSV
reader is proven on the REAL live header (HTTP 206 range peek
2026-09-13, ``;``-delimited, X/Y koordinaat in L-EST97).
"""

import urllib.error

import dims_p4_trans as p4t
import pytest
from dims_p4_trans import (
    ACCIDENTS_CSV_URL,
    ACCIDENTS_META_URL,
    ACCIDENTS_TTL_S,
    BLACKSPOT_WINDOW_M,
    P4_TRANS_DIMS,
    TARKTEE_TTL_S,
    accident_pois_from_points,
    accident_severity,
    dim_accident_blackspots,
    dim_dread_egress,
    dim_fixit_response,
    dim_horrors_events,
    dim_noise_zone_trans,
    dim_policy_restrictions,
    dim_quarry_trucks,
    dim_winter_road_class,
    fetch_cached,
    parse_accidents_csv,
    score_p4_trans,
    tallinn_accidents,
)

# Tallinn centre: hand-built POIs sit ~57 m east unless stated.
TALLINN = (59.4372, 24.7536)


def mkpoi(kind, lat=59.4372, lon=24.7546, **kw):
    poi = {"kind": kind, "lat": lat, "lon": lon}
    poi.update(kw)
    return poi


def accpoi(**kw):
    base = {"dead": 0, "injured": 1, "sev": 1, "year": 2024}
    base.update(kw)
    return mkpoi("accident_p4", **base)


def full_pois():
    return [
        accpoi(),
        mkpoi("roadclass_p4", maint_class="1"),
        mkpoi("noisezone_p4", zone="õppus"),
        mkpoi("fixithex_p4", rate=0.9, n=20),
        mkpoi("restriction_p4", restriction="piirang"),
        mkpoi("egress_p4", exits=2),
        mkpoi("eventtraffic_p4", days_per_year=2),
        mkpoi("truckroute_p4"),
    ]


ALL_FNS = [dim_accident_blackspots, dim_winter_road_class,
           dim_noise_zone_trans, dim_fixit_response,
           dim_policy_restrictions, dim_dread_egress,
           dim_horrors_events, dim_quarry_trucks]

# Real live header (first 15 columns carry the fields the reader uses;
# trailing columns parse as None - DictReader tolerates short rows).
CSV_HEADER = ("Juhtumi nr;Toimumisaeg;Isikuid;Hukkunuid;Sõidukeid;"
              "Vigastatuid;Aadress;Tänav;Maja nr;Ristuv tänav;Tee nr;"
              "Tee km;Maakond;Omavalitsus;Asustusüksus;Asula;"
              "Liiklusõnnetuse liik;X koordinaat;Y koordinaat")
TALLINN_ROW = ("2302110069111;2011-03-23 19:00:00;2;0;1;1;"
               " Harju maakond Tallinn Põhja-Tallinna linnaosa Sepa tn;"
               "Sepa tn;;;;;Harju maakond;Tallinn;"
               "Põhja-Tallinna linnaosa;JAH;Ühesõidukiõnnetus;;")
HARJU_ROW = ("2101250159501;2025-09-07 21:25:00;2;0;1;1;"
             " Harju maakond Jõelähtme vald;TALLINN - NARVA;;;1;27.0;"
             "Harju maakond;Jõelähtme vald;Ruu küla;EI;Muu;6589196.459;"
             "568050.8757")
FATAL_ROW = ("9900000000001;2024-01-05 08:10:00;3;1;2;2;"
             " Harju maakond Tallinn Lasnamäe linnaosa Laagna tee;"
             "Laagna tee;;;;;Harju maakond;Tallinn;"
             "Lasnamäe linnaosa;JAH;Raske;6588000.0;540000.0")


def write_csv(tmp_path):
    p = tmp_path / "lo_2011_2026.csv"
    p.write_text("\n".join([CSV_HEADER, TALLINN_ROW, HARJU_ROW, FATAL_ROW])
                 + "\n", encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# Ingestion: TTL defaults, cache-hit silence, honest errors. No network.
# ---------------------------------------------------------------------------

def test_ttl_and_urls_are_documented_feed():
    assert ACCIDENTS_TTL_S == 30 * 24 * 3600  # portal accrual: MONTHLY
    assert TARKTEE_TTL_S == 24 * 3600
    assert ACCIDENTS_META_URL == (
        "https://andmed.eesti.ee/api/datasets/slug/"
        "inimkannatanutega-liiklusonnetuste-andmed")
    assert "pilv.transpordiamet.ee" in ACCIDENTS_CSV_URL
    assert "lo_2011_2026.csv" in ACCIDENTS_CSV_URL


def test_fetch_cache_hit_makes_no_request(tmp_path, monkeypatch):
    dest = tmp_path / "lo.csv"
    dest.write_bytes(b"x" * 2000)

    def _boom(*a, **k):
        raise AssertionError("network used on cache hit")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert fetch_cached("https://example.invalid/x", str(tmp_path),
                        "lo.csv") == str(dest)


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
                        "lo.csv", ttl_s=0) is None
    assert not (tmp_path / "lo.csv").exists()


def test_fetch_short_body_is_not_cached_as_data(tmp_path, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: _FakeResp(b"error page", 200))
    assert fetch_cached("https://example.invalid/x", str(tmp_path),
                        "lo.csv", ttl_s=0) is None
    assert not (tmp_path / "lo.csv").exists()


def test_fetch_non_200_returns_none_and_caches_nothing(
        tmp_path, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: _FakeResp(b"x" * 2000, 429))
    assert fetch_cached("https://example.invalid/x", str(tmp_path),
                        "lo.csv", ttl_s=0) is None
    assert not (tmp_path / "lo.csv").exists()


def test_scorers_never_touch_network(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("scorer used the network")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    for fn in ALL_FNS:
        fn(TALLINN, full_pois())
    score_p4_trans(TALLINN, full_pois())


# ---------------------------------------------------------------------------
# Offline CSV readers on the real header shape.
# ---------------------------------------------------------------------------

def test_parse_keeps_real_header_and_rows(tmp_path):
    rows = parse_accidents_csv(write_csv(tmp_path))
    assert len(rows) == 3
    assert "Omavalitsus" in rows[0] and "Hukkunuid" in rows[0]
    assert rows[0]["Tänav"] == "Sepa tn"
    assert rows[1]["X koordinaat"] == "6589196.459"  # L-EST97, kept raw


def test_tallinn_filter_keeps_tallinn_drops_jolahtme(tmp_path):
    rows = parse_accidents_csv(write_csv(tmp_path))
    kept = tallinn_accidents(rows)
    assert len(kept) == 2
    assert {r["Omavalitsus"] for r in kept} == {"Tallinn"}


def test_severity_weights_deaths_triple_and_sanitises(tmp_path):
    rows = parse_accidents_csv(write_csv(tmp_path))
    assert accident_severity(rows[0]) == 1  # 0 dead + 1 injured
    assert accident_severity(rows[2]) == 5  # 1 dead + 2 injured
    assert accident_severity({"Hukkunuid": "x", "Vigastatuid": True}) == 0
    assert accident_severity({"Hukkunuid": "-2", "Vigastatuid": None}) == 0


def test_pois_skip_unprojected_and_malformed_points():
    pois = accident_pois_from_points([
        {"lat": 59.43, "lon": 24.75, "dead": 0, "injured": 2, "year": 2024},
        {"lat": None, "lon": 24.75},          # L-EST97 pending: skipped
        {"lon": 24.75},                        # no lat: skipped
        {"lat": True, "lon": 24.75},           # bool: skipped
        {"lat": float("nan"), "lon": 24.75},   # NaN: skipped
    ])
    assert len(pois) == 1
    assert pois[0]["kind"] == "accident_p4" and pois[0]["sev"] == 2


# ---------------------------------------------------------------------------
# P4-012 blackspot bands (severity boundaries pinned).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sev,expected", [
    (1, 65),
    (2, 50), (3, 50),
    (4, 35), (6, 35),
    (7, 20), (25, 20),
])
def test_blackspot_severity_bands(sev, expected):
    v, r = dim_accident_blackspots(TALLINN, [accpoi(sev=sev)])
    assert v == expected, r
    assert "hinnang" in r and "300 m" in r and "päästeaeg" in r


def test_blackspot_sums_severity_across_buffer():
    pois = [accpoi(sev=2), accpoi(sev=2, lon=24.7556)]  # both ~in 300 m
    v, r = dim_accident_blackspots(TALLINN, pois)
    assert v == 35, r  # sev 4
    assert "2 kannatanutega" in r


def test_blackspot_empty_buffer_is_unknown_not_safe():
    # Judgment call pinned: the register holds casualty accidents only.
    v, r = dim_accident_blackspots(TALLINN, [])
    assert v is None
    assert "EI OLE" in r and "ohutushinnang" in r and "ainult" in r
    rural = accpoi(lat=TALLINN[0], lon=TALLINN[1] + 0.05)  # ~2.9 km out
    v, r = dim_accident_blackspots(TALLINN, [rural])
    assert v is None and "EI OLE" in r


def test_blackspot_window_boundary():
    assert BLACKSPOT_WINDOW_M == 300.0


# ---------------------------------------------------------------------------
# Coverage params: bands + NULLs.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cls,expected", [
    ("1", 85), ("2", 65), ("3", 45), ("4", 30),
])
def test_winter_class_bands(cls, expected):
    v, r = dim_winter_road_class(
        TALLINN, [mkpoi("roadclass_p4", maint_class=cls)])
    assert v == expected, r
    assert "hinnang" in r and "hooldusklass %s" % cls in r


@pytest.mark.parametrize("zone,expected", [
    ("lennumüra", 35), ("õppus", 50), ("sadam", 60),
])
def test_noise_zone_bands_from_label_only(zone, expected):
    v, r = dim_noise_zone_trans(TALLINN, [mkpoi("noisezone_p4", zone=zone)])
    assert v == expected, r
    assert "hinnang" in r and "kaugusgradient" in r


def test_noise_sadam_measured_function_replaces_fixture():
    # Row-for-row (#627): a sadam row WITH a joined register function
    # scores from the function bands, not the flat fixture 60.
    v, r = dim_noise_zone_trans(TALLINN, [mkpoi("noisezone_p4", zone="sadam",
                                                function=1)])
    assert v == 45, r
    assert "M\u00d5\u00d5DETUD" in r
    v, r = dim_noise_zone_trans(TALLINN, [mkpoi("noisezone_p4", zone="sadam",
                                                function=2)])
    assert v == 70, r


def test_noise_sadam_without_function_keeps_fixture():
    v, r = dim_noise_zone_trans(TALLINN, [mkpoi("noisezone_p4",
                                                zone="sadam")])
    assert v == 60, r
    assert "M\u00d5\u00d5DETUD" not in r


def test_noise_score_ignores_distance_inside_window():
    near = [mkpoi("noisezone_p4", zone="õppus")]
    far = [mkpoi("noisezone_p4", lat=TALLINN[0] + 0.008,  # ~890 m
                 lon=TALLINN[1], zone="õppus")]
    assert dim_noise_zone_trans(TALLINN, near)[0] == 50
    assert dim_noise_zone_trans(TALLINN, far)[0] == 50  # label, not gradient


@pytest.mark.parametrize("rate,expected", [
    (0.0, 40), (0.5, 40), (0.51, 60), (0.8, 60), (0.81, 80), (1.0, 80),
])
def test_fixit_rate_bands(rate, expected):
    v, r = dim_fixit_response(
        TALLINN, [mkpoi("fixithex_p4", rate=rate, n=20)])
    assert v == expected, r
    assert "hinnang" in r and "%" in r


def test_fixit_thin_hex_stays_null():
    for poi in (mkpoi("fixithex_p4", rate=0.95, n=4),
                mkpoi("fixithex_p4", rate=0.95, n=0),
                mkpoi("fixithex_p4", rate=0.95),          # n missing
                mkpoi("fixithex_p4", n=20),               # rate missing
                mkpoi("fixithex_p4", rate=True, n=20),    # bool not a rate
                mkpoi("fixithex_p4", rate="hea", n=20)):  # garbage
        v, r = dim_fixit_response(TALLINN, [poi])
        assert v is None, poi
        assert "EI OLE" in r


@pytest.mark.parametrize("kind,expected", [
    ("sulgemine", 45), ("piirang", 55), ("tasuline", 60),
])
def test_restriction_kind_bands(kind, expected):
    v, r = dim_policy_restrictions(
        TALLINN, [mkpoi("restriction_p4", restriction=kind)])
    assert v == expected, r
    assert "hinnang" in r and kind in r


@pytest.mark.parametrize("exits,expected", [
    (0, 30), (1, 55), (2, 85), (3, 85),
])
def test_egress_bands(exits, expected):
    v, r = dim_dread_egress(TALLINN, [mkpoi("egress_p4", exits=exits)])
    assert v == expected, r
    assert "hinnang" in r


@pytest.mark.parametrize("days,expected", [
    (0, 80), (1, 60), (5, 60), (6, 40), (30, 40),
])
def test_event_calendar_bands(days, expected):
    # Joined 0 is a real calm signal (calendars are exhaustive lists).
    v, r = dim_horrors_events(
        TALLINN, [mkpoi("eventtraffic_p4", days_per_year=days)])
    assert v == expected, r
    assert "hinnang" in r and "kalendriliidestus" in r


def test_truck_route_is_flat_exposure_inside_buffer():
    near = [mkpoi("truckroute_p4")]
    edge = [mkpoi("truckroute_p4", lat=TALLINN[0] + 0.008,  # ~890 m
                  lon=TALLINN[1])]
    for pois in (near, edge):
        v, r = dim_quarry_trucks(TALLINN, pois)
        assert v == 45, r
        assert "hinnang" in r and "ajagraafik liidestamata" in r
    far = [mkpoi("truckroute_p4", lat=TALLINN[0], lon=TALLINN[1] + 0.05)]
    v, r = dim_quarry_trucks(TALLINN, far)
    assert v is None and "EI OLE" in r


def test_label_dims_null_on_unknown_or_garbage_label():
    cases = [
        (dim_winter_road_class, "roadclass_p4", "maint_class"),
        (dim_noise_zone_trans, "noisezone_p4", "zone"),
        (dim_policy_restrictions, "restriction_p4", "restriction"),
    ]
    for fn, kind, field in cases:
        for poi in (mkpoi(kind), mkpoi(kind, **{field: "bogus"}),
                    mkpoi(kind, **{field: 2}), mkpoi(kind, **{field: True})):
            v, r = fn(TALLINN, [poi])
            assert v is None, (fn.__name__, poi)
            assert "EI OLE" in r, fn.__name__


def test_count_dims_null_on_garbage_counts():
    for poi in (mkpoi("egress_p4", exits=-1),
                mkpoi("egress_p4", exits="kaks"),
                mkpoi("egress_p4", exits=True),
                mkpoi("eventtraffic_p4", days_per_year=-3),
                mkpoi("eventtraffic_p4", days_per_year="palju")):
        fn = (dim_dread_egress if poi["kind"] == "egress_p4"
              else dim_horrors_events)
        v, r = fn(TALLINN, [poi])
        assert v is None, poi
        assert "EI OLE" in r


def test_dims_ignore_other_kinds():
    # Each dim reads only its own POI kind (per-source slices).
    assert dim_winter_road_class(TALLINN, [accpoi()])[0] is None
    assert dim_accident_blackspots(
        TALLINN, [mkpoi("roadclass_p4", maint_class="1")])[0] is None
    assert dim_quarry_trucks(TALLINN, [accpoi()])[0] is None


def test_windows_far_stop_is_unknown_not_bad():
    far = dict(accpoi(), lat=TALLINN[0], lon=TALLINN[1] + 0.05)
    for fn in ALL_FNS:
        v, r = fn(TALLINN, [far])
        assert v is None, fn.__name__
        assert "EI OLE" in r


def test_all_null_for_missing_inputs_and_malformed_pois():
    bad_pois = [[{"kind": "cafe", "lat": 59.4372, "lon": 24.7546}],
                [{"kind": "accident_p4"}], [],
                [{"kind": "roadclass_p4", "lat": None, "lon": 24.75}],
                [{"kind": "noisezone_p4", "lat": 59.43, "lon": "x"}]]
    for fn in ALL_FNS:
        for origin, pois in [(None, full_pois()), (TALLINN, None),
                             (None, None)] + [(TALLINN, p) for p in bad_pois]:
            v, r = fn(origin, pois)
            assert v is None, (fn.__name__, origin, pois)
            assert "EI OLE" in r, fn.__name__


def test_honesty_markers():
    for fn in ALL_FNS:
        _, r = fn(TALLINN, [])
        assert "EI OLE" in r, fn.__name__
        assert "hinnang" not in r or "pole" in r
    scored = [(dim_accident_blackspots, [accpoi()]),
              (dim_winter_road_class,
               [mkpoi("roadclass_p4", maint_class="1")]),
              (dim_noise_zone_trans, [mkpoi("noisezone_p4", zone="sadam")]),
              (dim_fixit_response, [mkpoi("fixithex_p4", rate=0.9, n=20)]),
              (dim_policy_restrictions,
               [mkpoi("restriction_p4", restriction="tasuline")]),
              (dim_dread_egress, [mkpoi("egress_p4", exits=2)]),
              (dim_horrors_events,
               [mkpoi("eventtraffic_p4", days_per_year=0)]),
              (dim_quarry_trucks, [mkpoi("truckroute_p4")])]
    for fn, pois in scored:
        v, r = fn(TALLINN, pois)
        assert v is not None
        assert "hinnang" in r and "EI OLE" not in r, fn.__name__
        assert "garanteeritud" not in r


def test_registry_and_aggregator_cover_all_eight():
    assert [k for k, _, _ in P4_TRANS_DIMS] == [
        "accident_blackspots", "winter_road_class", "noise_zone_trans",
        "fixit_response", "policy_restrictions", "dread_egress",
        "horrors_events", "quarry_trucks"]
    assert [p for _, p, _ in P4_TRANS_DIMS] == [
        "P4-012", "P4-018", "P4-023", "P4-026",
        "P4-037", "P4-046", "P4-047", "P4-054"]
    assert len({fn for _, _, fn in P4_TRANS_DIMS}) == 8
    out = score_p4_trans(TALLINN, full_pois())
    assert out == {"accident_blackspots": 65, "winter_road_class": 85,
                   "noise_zone_trans": 50, "fixit_response": 80,
                   "policy_restrictions": 55, "dread_egress": 85,
                   "horrors_events": 60, "quarry_trucks": 45}
    assert score_p4_trans(None, None) == {
        k: None for k, _, _ in P4_TRANS_DIMS}
    assert p4t.P4_TRANS_DIMS is P4_TRANS_DIMS
