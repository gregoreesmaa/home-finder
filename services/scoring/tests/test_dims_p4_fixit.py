"""P4 fix-it channels dims (issues #301 demo + #370 coverage): hermetic tests.

No network: the ask ingestion (fetch_annateada_snapshot) is covered
through cache-hit and stubbed-opener paths that raise if touched;
every dim and reader runs on synthetic fixtures matching the
2026-09-16 ask schema (evidence in docs/p4_fixit.md). No real report
text, contact, or photo is committed — fixtures are synthetic pins.
"""

import json
import os
import urllib.request

import dims_p4_fixit as fixit
from dims_p4_fixit import (
    ANNATEADA_ASK_URL,
    ANNATEADA_CATEGORIES,
    ANNATEADA_PIN_KIND,
    ANNATEADA_TALLINN_BBOX,
    ANNATEADA_TTL_S,
    FIXIT_BANDS,
    FIXIT_MIN_N,
    FIXIT_WINDOW_M,
    P4_FIXIT_DIMS,
    WASTE_BANDS,
    WASTE_CATEGORY,
    WASTE_MIN_N,
    WASTE_WINDOW_M,
    build_annateada_pins,
    dim_fixit_channel_responsiveness,
    dim_rat_icefall_channel_flags,
    fetch_annateada_snapshot,
    parse_annateada_snapshot,
    score_p4_fixit,
    summarize_fixit_window,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [
    dim_fixit_channel_responsiveness,
    dim_rat_icefall_channel_flags,
]

EXPECTED_KEYS = [
    "fixit_channel_responsiveness",
    "rat_icefall_channel_flags",
]

EXPECTED_PNUMS = [
    "P4-026", "P4-062",
]


def test_both_dims_always_none_for_every_input():
    for fn in ALL_FNS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, _ = fn(origin, pois)
            assert v is None, fn.__name__


def test_both_reasons_carry_honesty_markers_and_concrete_check():
    for fn in ALL_FNS:
        _, reason = fn(TALLINN, POIS)
        assert "hinnang" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_p4_026_reason_names_channels_and_scored_cousins():
    _, reason = dim_fixit_channel_responsiveness(TALLINN, POIS)
    # Human intake channels: helpline + report map.
    assert "14410" in reason
    assert "annateada.ee" in reason
    # Split-slice contract: the komun / OSM / arireg legs stay scored
    # where they live — this NULL must name them, not rescore.
    assert "dims_p4_komun" in reason
    assert "dim_fixit_responsiveness" in reason
    assert "dims_p4_osm" in reason
    assert "dim_fixit" in reason
    assert "dims_p4_arireg" in reason
    assert "dim_maintenance_echo" in reason


def test_p4_062_reason_names_join_and_never_addresses():
    _, reason = dim_rat_icefall_channel_flags(TALLINN, POIS)
    # Coverage rides the P4-026 join; hex only, never addresses.
    assert "P4-026" in reason
    assert "kunagi mitte aadressid" in reason
    assert "kohapealsel vaatlusel" in reason
    assert "KÜ" in reason
    # Split-slice contract: paaste / komun / OSM / arireg legs stay
    # scored where they live — named, never re-scored here.
    assert "dims_p4_paaste" in reason
    assert "dims_p4_komun" in reason
    assert "dim_rat_icefall_hex" in reason
    assert "dims_p4_osm" in reason
    assert "dim_rats" in reason
    assert "dims_p4_arireg" in reason
    assert "dim_waste_echo" in reason


def test_rate_vs_flags_shapes_do_not_double_score():
    _, rate_reason = dim_fixit_channel_responsiveness(TALLINN, POIS)
    _, flag_reason = dim_rat_icefall_channel_flags(TALLINN, POIS)
    # Lag rate (P4-026) vs count flags (P4-062): different honest
    # shapes, so the reasons must read differently.
    assert "parandamiskiirus" in rate_reason
    assert "lipud" in flag_reason
    assert rate_reason != flag_reason


def test_registry_and_aggregator_cover_both():
    assert [k for k, _, _ in P4_FIXIT_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_FIXIT_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_FIXIT_DIMS}) == 2
    out = score_p4_fixit(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_fixit(None, None) == {k: None for k in EXPECTED_KEYS}
    assert fixit.P4_FIXIT_DIMS is P4_FIXIT_DIMS


# ---------------------------------------------------------------------------
# Ingestion contract: read-only ask endpoint, stated TTL, polite pull.
# ---------------------------------------------------------------------------

def test_ask_url_is_read_only_and_ttl_is_daily():
    assert ANNATEADA_ASK_URL == "https://annateada.ee/cgi-bin/ask"
    assert "send" not in ANNATEADA_ASK_URL  # write path never touched
    assert ANNATEADA_TTL_S == 24 * 3600
    assert set(ANNATEADA_TALLINN_BBOX) == {"lat0", "lng0", "lat1", "lng1"}
    assert WASTE_CATEGORY == "Heakord"
    assert WASTE_CATEGORY in ANNATEADA_CATEGORIES
    assert FIXIT_WINDOW_M == 500.0 and FIXIT_MIN_N == 5
    assert WASTE_WINDOW_M == 500.0 and WASTE_MIN_N == 5


def _boom(req, timeout=None):
    raise AssertionError("network must not be touched")


def _patch_opener():
    real = urllib.request.urlopen
    urllib.request.urlopen = _boom
    return real


def test_fetch_cache_hit_returns_path_without_request(tmp_path):
    dest = os.path.join(str(tmp_path), "annateada-ask-snapshot.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump({"messages": []}, fh)
    real = _patch_opener()
    try:
        assert fetch_annateada_snapshot(str(tmp_path)) == dest
    finally:
        urllib.request.urlopen = real


def test_fetch_transport_error_returns_none_and_caches_nothing(tmp_path):
    real = _patch_opener()
    try:
        assert fetch_annateada_snapshot(str(tmp_path)) is None
    finally:
        urllib.request.urlopen = real
    assert os.listdir(str(tmp_path)) == []


def test_fetch_posts_tallinn_bbox_and_validates_body(tmp_path):
    seen = {}

    class _Resp:
        status = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b'{"messages": []}'

    def _capture(req, timeout=None):
        seen["url"] = req.full_url
        seen["body"] = json.loads(req.data.decode("utf-8"))
        seen["ua"] = req.get_header("User-agent")
        return _Resp()

    real = urllib.request.urlopen
    urllib.request.urlopen = _capture
    try:
        dest = fetch_annateada_snapshot(str(tmp_path))
    finally:
        urllib.request.urlopen = real
    assert dest is not None and os.path.exists(dest)
    assert seen["url"] == ANNATEADA_ASK_URL
    for key, val in ANNATEADA_TALLINN_BBOX.items():
        assert seen["body"][key] == val
    assert seen["ua"]  # identifying user agent stated


def test_fetch_rejects_non_json_and_missing_messages(tmp_path):
    payloads = [b"<html>not json</html>", b'{"n ontology": 1}',
                b'{"messages": {}}']

    class _Resp:
        status = 200
        headers = {"Content-Type": "application/json"}

        def __init__(self, body):
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return self._body

    for i, payload in enumerate(payloads):
        sub = os.path.join(str(tmp_path), "run%d" % i)
        real = urllib.request.urlopen
        urllib.request.urlopen = lambda req, timeout=None: _Resp(payload)
        try:
            assert fetch_annateada_snapshot(sub) is None
        finally:
            urllib.request.urlopen = real
        assert not os.path.exists(os.path.join(sub, "annateada-ask-snapshot.json"))


# ---------------------------------------------------------------------------
# Offline readers: schema sanitising, human-content minimisation.
# ---------------------------------------------------------------------------

ASK_DOC = {"messages": [
    {"id": "1", "lat": "59.4372", "lng": "24.7536",
     "msg": "reporter free text (dropped)", "dtime": "2026-09-15T10:00:00",
     "ts": "1789500000", "stat": "1", "region": "Tallinn",
     "category": "Teed ja tänavad", "comm": "handler note (dropped)",
     "photo": "https://example.invalid/p.jpg"},
    {"id": "2", "lat": 59.438, "lng": 24.754, "stat": 1,
     "region": "Tallinn", "category": "Heakord", "dtime": "2026-09-14T09:00:00"},
    {"id": "3", "lat": "59.439", "lng": "24.755", "stat": "0",
     "region": "Tallinn", "category": "Valgustus", "dtime": None},
    {"id": "4", "lat": "59.44", "lng": "24.756", "stat": "0",
     "region": "Saue vald", "category": "Heakord"},
    {"id": "5", "lat": "59.44", "lng": "24.756", "stat": "0",
     "region": "Tallinn", "category": "invented-category"},
    {"id": "6", "lat": None, "lng": "24.756", "stat": "0",
     "region": "Tallinn", "category": "Heakord"},
    "not-a-dict",
]}


def _write_doc(tmp_path, doc, name="snap.json"):
    path = os.path.join(str(tmp_path), name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    return path


def test_parse_keeps_minimal_schema_and_drops_human_content(tmp_path):
    recs = parse_annateada_snapshot(_write_doc(tmp_path, ASK_DOC))
    assert len(recs) == 5  # unparseable coords + non-dict skipped
    first = recs[0]
    assert set(first) == {"lat", "lng", "handled", "category", "dtime",
                          "ts", "region"}
    assert first["ts"] == 1789500000  # numeric-string epoch passes
    assert recs[1]["ts"] is None  # missing ts stays None (map drops it)
    assert first["handled"] is True  # stat '1' = green/handled
    assert first["lat"] == 59.4372 and first["lng"] == 24.7536
    assert recs[1]["handled"] is True  # int 1 also handled
    assert recs[2]["handled"] is False  # stat '0' = red/unhandled
    assert recs[2]["dtime"] is None
    assert recs[4]["category"] is None  # unknown taxonomy rejected
    assert "msg" not in first and "comm" not in first and "photo" not in first


def test_parse_bad_inputs_stay_empty(tmp_path):
    assert parse_annateada_snapshot(os.path.join(str(tmp_path), "missing")) == []
    bad = _write_doc(tmp_path, {"nope": 1}, name="bad.json")
    assert parse_annateada_snapshot(bad) == []
    raw = os.path.join(str(tmp_path), "raw.json")
    with open(raw, "w", encoding="utf-8") as fh:
        fh.write("not json{")
    assert parse_annateada_snapshot(raw) == []


def test_build_pins_filters_tallinn_and_marks_handled(tmp_path):
    recs = parse_annateada_snapshot(_write_doc(tmp_path, ASK_DOC))
    pois = build_annateada_pins(recs)
    assert len(pois) == 4  # Saue vald pin filtered
    assert {p["kind"] for p in pois} == {ANNATEADA_PIN_KIND}
    assert [p["handled"] for p in pois] == [1, 1, 0, 0]
    assert all(set(p) == {"kind", "lat", "lon", "handled", "category",
                          "dtime", "ts"} for p in pois)
    assert [p["ts"] for p in pois] == [1789500000, None, None, None]


# ---------------------------------------------------------------------------
# Window joins on synthetic pins (geometry + bands + thin-NULL).
# ---------------------------------------------------------------------------

def _mkpin(dlat, dlng, handled=1, category=None):
    return {"kind": ANNATEADA_PIN_KIND, "lat": TALLINN[0] + dlat,
            "lon": TALLINN[1] + dlng, "handled": handled,
            "category": category, "dtime": "2026-09-15T10:00:00"}


def _rate_pins(n=5, handled_n=4):
    # 0.0005 deg lat ~= 55 m: all n pins sit inside the 500 m window.
    pins = [_mkpin(0.0005 * (i + 1), 0.0, handled=1 if i < handled_n else 0)
            for i in range(n)]
    return pins


def test_p4_026_scores_window_rate_and_thin_stays_null():
    v, reason = dim_fixit_channel_responsiveness(TALLINN, _rate_pins(5, 4))
    assert v == 60  # rate 0.8 -> FIXIT_BANDS (0.8, 60)
    assert "5 annateada-raportit" in reason
    assert "80%" in reason
    v, _ = dim_fixit_channel_responsiveness(TALLINN, _rate_pins(4, 4))
    assert v is None  # n < FIXIT_MIN_N stays NULL, never a thin rate
    v, _ = dim_fixit_channel_responsiveness(TALLINN, _rate_pins(5, 5))
    assert v == 80
    v, _ = dim_fixit_channel_responsiveness(TALLINN, _rate_pins(5, 1))
    assert v == 40


def test_p4_026_ignores_far_pins_and_foreign_kinds():
    pins = _rate_pins(5, 5) + [_mkpin(0.5, 0.5, handled=0)]  # ~55 km away
    pins.append({"kind": "cafe", "lat": TALLINN[0], "lon": TALLINN[1]})
    v, reason = dim_fixit_channel_responsiveness(TALLINN, pins)
    assert v == 80  # far pin + cafe ignored
    assert "5 annateada-raportit" in reason


def test_summarize_returns_none_when_thin():
    assert summarize_fixit_window(TALLINN, _rate_pins(4, 4)) is None
    assert summarize_fixit_window(TALLINN, []) is None
    n, rate = summarize_fixit_window(TALLINN, _rate_pins(6, 3))
    assert (n, rate) == (6, 0.5)


def test_p4_062_flags_waste_counts_and_thin_stays_null():
    waste = [_mkpin(0.0005 * (i + 1), 0.0, handled=0,
                    category=WASTE_CATEGORY) for i in range(5)]
    v, reason = dim_rat_icefall_channel_flags(TALLINN, waste)
    assert v == 55  # 5 Heakord pins -> WASTE_BANDS (9, 55)
    assert "5 Heakord-raportit" in reason
    assert "kunagi mitte aadressid" in reason
    v, _ = dim_rat_icefall_channel_flags(TALLINN, waste[:4])
    assert v is None  # thin window stays NULL
    v, _ = dim_rat_icefall_channel_flags(
        TALLINN, waste + [_mkpin(0.0005, 0.0, handled=1,
                                category=WASTE_CATEGORY) for _ in range(5)])
    assert v == 35  # 10 pins -> (inf, 35)


def test_p4_062_ignores_non_waste_categories():
    pins = [_mkpin(0.0005 * (i + 1), 0.0, handled=0,
                   category="Teed ja tänavad") for i in range(6)]
    v, _ = dim_rat_icefall_channel_flags(TALLINN, pins)
    assert v is None  # no Heakord pins -> no flag, never a rescore


def test_aggregator_scores_joined_pins():
    # Both dims read the SAME pins differently (rate vs count flag —
    # no double-scoring): 5 handled + 5 unhandled waste pins in one
    # window -> rate 0.5 -> 40 (<= boundary, trans precedent), waste
    # flag n=5 -> 55.
    pins = _rate_pins(5, 5) + [_mkpin(0.0005 * (i + 1), 0.0005,
                                     handled=0, category=WASTE_CATEGORY)
                               for i in range(5)]
    out = score_p4_fixit(TALLINN, pins)
    assert out == {"fixit_channel_responsiveness": 40,
                   "rat_icefall_channel_flags": 55}


def test_bands_mirror_trans_precedent():
    assert FIXIT_BANDS == [(0.5, 40), (0.8, 60), (float("inf"), 80)]
    assert WASTE_BANDS == [(9, 55), (float("inf"), 35)]
