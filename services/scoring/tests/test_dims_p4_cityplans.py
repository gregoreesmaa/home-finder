"""P4 cityplans dims (issues #282 + #356): hermetic tests.

No network: the strategic-plans bulk endpoint does not exist
(2026-09-13 dated negative, see dims_p4_cityplans docstring), so every
test runs on fixture row-dicts and hand-built POIs with explicit
valuation dates. The polite fetcher is covered via a stubbed urlopen
(cache-hit performs no request; no-endpoint and transport-error paths
return None and cache nothing); scorers are proven network-free by
running them with urlopen stubbed to raise.
"""

import json
import urllib.request

import dims_p4_cityplans as p4c
import pytest
from dims_p4_cityplans import (
    ARENGUALA_CLEAR_SCORE,
    ARENGUALA_FAR_SCORE,
    ARENGUALA_NEAR_SCORE,
    CACHE_FILENAME,
    CITYPLANS_BULK_URL,
    CITYPLANS_TTL_S,
    CITYPLANS_UA,
    GLUT_HIGH_SCORE,
    P4_CITYPLANS_DIMS,
    PHASE_SCORES,
    POLICY_SCORES,
    TREND_SCORES,
    VAATE_SCORE,
    arengualad_to_pois,
    buildstats_to_pois,
    corridors_to_pois,
    dim_aareala_teenus_cityplans,
    dim_arenguala_cityplans,
    dim_ehitusstat_cityplans,
    dim_investeering_cityplans,
    dim_poliitika_kava_cityplans,
    dim_prognoos_cityplans,
    dim_tramfaas_cityplans,
    dim_vaatekoridor_cityplans,
    fetch_cityplans_snapshot,
    forecasts_to_pois,
    fringe_to_pois,
    investments_to_pois,
    parse_cityplans_snapshot,
    policy_to_pois,
    score_p4_cityplans,
    snapshot_to_pois,
    tramworks_to_pois,
)

# Tallinn centre: hand-built POIs sit ~57 m east unless stated
# (0.001 deg lon ~= 57 m at 59.44 N; 0.001 deg lat ~= 111 m).
TALLINN = (59.4372, 24.7536)
FAR = (59.5000, 24.9000)  # Mustamae-ish, km away from centre fixtures
TODAY = "2026-09-13"


def mktram(lat=59.4372, lon=24.7546, phase="ehituses", work_id="TRAM-VS1",
           title="Vanasadama tramm", vfrom="2024-01-01",
           vuntil="2028-12-31"):
    return {"work_id": work_id, "title": title, "phase": phase,
            "lat": lat, "lon": lon,
            "valid_from": vfrom, "valid_until": vuntil}


def mkareng(lat=59.4372, lon=24.7546, zone_id="UP-K1", kind="arenguala"):
    return {"zone_id": zone_id, "kind": kind, "lat": lat, "lon": lon}


def mkinvest(lat=59.4372, lon=24.7546, area_code="KESK",
             invest=12.5, trend="kasv"):
    return {"area_code": area_code, "lat": lat, "lon": lon,
            "invest_m_eur": invest, "trend": trend}


def mkprog(lat=59.4372, lon=24.7546, area_code="KESK", pop=2.0,
           school="stabiilne"):
    return {"area_code": area_code, "lat": lat, "lon": lon,
            "pop_change_pct": pop, "school_plan": school}


def mkpol(lat=59.4372, lon=24.7546, zone_id="POL-K1",
          kind="tasuline_parkimine"):
    return {"zone_id": zone_id, "kind": kind, "lat": lat, "lon": lon}


def mkvaade(lat=59.4372, lon=24.7546, corr_id="VK-1"):
    return {"corr_id": corr_id, "lat": lat, "lon": lon}


def mkstat(lat=59.4372, lon=24.7546, area_code="KESK", permits=40,
           completions=100):
    return {"area_code": area_code, "lat": lat, "lon": lon,
            "permits_q": permits, "completions_q": completions}


def mkfringe(lat=59.4372, lon=24.7546, settlement="Merivälja",
             shop=True, pharmacy=True, atm=True, bus_cuts=False):
    return {"settlement": settlement, "lat": lat, "lon": lon,
            "shop": shop, "pharmacy": pharmacy, "atm": atm,
            "bus_cuts": bus_cuts}


def pois(**tables):
    return snapshot_to_pois({k: list(v) for k, v in tables.items()})


class _FakeResp:
    """Minimal urlopen stub (context manager, stdlib-shaped)."""

    def __init__(self, body=b"{}", status=200, ctype="application/json"):
        self._body = body
        self.status = status
        self.headers = {"Content-Type": ctype}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _raise_urlopen(*a, **k):
    raise AssertionError("network touched in a hermetic test")


# ---------------------------------------------------------------------------
# Ingestion contract: TTL, UA, dated negative, cache behaviour.
# ---------------------------------------------------------------------------

def test_ttl_is_monthly_and_ua_identifies():
    assert CITYPLANS_TTL_S == 30 * 24 * 3600
    assert "home-finder" in CITYPLANS_UA and "30d" in CITYPLANS_UA
    assert CITYPLANS_BULK_URL is None  # dated negative: no requests
    assert CACHE_FILENAME == "cityplans-snapshot.json"


def test_fetch_no_endpoint_returns_none_without_network(tmp_path,
                                                        monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    assert fetch_cityplans_snapshot(str(tmp_path)) is None


def test_fetch_cache_hit_performs_no_request(tmp_path, monkeypatch):
    dest = tmp_path / CACHE_FILENAME
    dest.write_text(json.dumps({"tramworks": []}), encoding="utf-8")
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    assert fetch_cityplans_snapshot(str(tmp_path)) == str(dest)


def test_fetch_transport_error_caches_nothing(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise OSError("down")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    out = fetch_cityplans_snapshot(str(tmp_path), bulk_url="https://x.test/")
    assert out is None
    assert not (tmp_path / CACHE_FILENAME).exists()


def test_fetch_non_json_caches_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: _FakeResp(b"<html>", 200,
                                                 "text/html"))
    out = fetch_cityplans_snapshot(str(tmp_path), bulk_url="https://x.test/")
    assert out is None
    assert not (tmp_path / CACHE_FILENAME).exists()


def test_parse_missing_file_is_none_unknown(tmp_path):
    assert parse_cityplans_snapshot(str(tmp_path / "nope.json")) is None


def test_parse_malformed_rows_skipped(tmp_path):
    snap = {"tramworks": [mktram(), "junk", 42, {"lat": "x"}],
            "arengualad": "notalist",
            "aarealad": [{"settlement": "X"}]}  # no coords -> dropped
    path = tmp_path / "s.json"
    path.write_text(json.dumps(snap), encoding="utf-8")
    parsed = parse_cityplans_snapshot(str(path))
    assert len(parsed["tramworks"]) == 2  # dict rows kept, POI filter later
    assert parsed["arengualad"] == []
    assert len(snapshot_to_pois(parsed)) == 1  # only the valid tram row


def test_snapshot_none_gives_no_pois():
    assert snapshot_to_pois(None) == []
    assert snapshot_to_pois("junk") == []


def test_readers_drop_coordless_rows():
    assert tramworks_to_pois([{"work_id": "X"}]) == []
    assert arengualad_to_pois([{"zone_id": "X"}]) == []
    assert investments_to_pois([{"area_code": "X"}]) == []
    assert forecasts_to_pois([{"area_code": "X"}]) == []
    assert policy_to_pois([{"zone_id": "X"}]) == []
    assert corridors_to_pois([{"corr_id": "X"}]) == []
    assert buildstats_to_pois([{"area_code": "X"}]) == []
    assert fringe_to_pois([{"settlement": "X"}]) == []


# ---------------------------------------------------------------------------
# P4-014 demo: tram calendar dim.
# ---------------------------------------------------------------------------

def test_tram_phases_score_calendar(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    for phase, want in (("ehituses", 35), ("planeerimisel", 55),
                        ("valmis", 75)):
        v, reason = dim_tramfaas_cityplans(
            TALLINN, pois(tramworks=[mktram(phase=phase)]), TODAY)
        assert v == want, phase
        assert "hinnang" in reason and "kehtib kuni" in reason


def test_tram_expired_and_unknown_expiry_stay_null(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    old = pois(tramworks=[mktram(vfrom="2020-01-01",
                                 vuntil="2021-01-01")])
    v, reason = dim_tramfaas_cityplans(TALLINN, old, TODAY)
    assert v is None and "EI OLE" in reason and "aegunud" in reason
    noexp = pois(tramworks=[mktram(vuntil=None)])
    v, reason = dim_tramfaas_cityplans(TALLINN, noexp, TODAY)
    assert v is None and "EI OLE" in reason
    future = pois(tramworks=[mktram(vfrom="2027-01-01",
                                   vuntil="2029-01-01")])
    v, _ = dim_tramfaas_cityplans(TALLINN, future, TODAY)
    assert v is None


def test_tram_unknown_phase_and_empty_stay_null(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    weird = pois(tramworks=[mktram(phase="kosmoselaev")])
    v, reason = dim_tramfaas_cityplans(TALLINN, weird, TODAY)
    assert v is None and "EI OLE" in reason
    v, reason = dim_tramfaas_cityplans(TALLINN, pois(), TODAY)
    assert v is None and "EI OLE" in reason
    v, reason = dim_tramfaas_cityplans(TALLINN,
                                      pois(tramworks=[mktram()]), TODAY)
    # fixture ~57 m away is inside the 800 m window, sanity check it scores
    assert v == 35
    v, reason = dim_tramfaas_cityplans(FAR, pois(tramworks=[mktram()]),
                                       TODAY)
    assert v is None and "EI OLE" in reason  # beyond-window is unknown
    v, reason = dim_tramfaas_cityplans(None, pois(tramworks=[mktram()]),
                                       TODAY)
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# P4-006 coverage: arenguala leg.
# ---------------------------------------------------------------------------

def test_arenguala_bands_and_clear(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    near = pois(arengualad=[mkareng()])  # ~57 m
    v, reason = dim_arenguala_cityplans(TALLINN, near)
    assert v == ARENGUALA_NEAR_SCORE == 50
    assert "hinnang" in reason
    mid = pois(arengualad=[mkareng(lat=59.4402, lon=24.7536)])  # ~330 m N
    v, _ = dim_arenguala_cityplans(TALLINN, mid)
    assert v == ARENGUALA_FAR_SCORE == 65
    v, reason = dim_arenguala_cityplans(FAR, near)
    assert v == ARENGUALA_CLEAR_SCORE == 85  # measured clear
    assert "hinnang" in reason


def test_arenguala_null_contract(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    v, reason = dim_arenguala_cityplans(TALLINN, pois())
    assert v is None and "EI OLE" in reason
    v, reason = dim_arenguala_cityplans(None, pois(arengualad=[mkareng()]))
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# P4-019 coverage: investment-table leg.
# ---------------------------------------------------------------------------

def test_investeering_trend_scores(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    for trend, want in (("kasv", 75), ("stabiilne", 60), ("kahaneb", 40)):
        v, reason = dim_investeering_cityplans(
            TALLINN, pois(investeeringud=[mkinvest(trend=trend)]))
        assert v == want == TREND_SCORES[trend]
        assert "hinnang" in reason and "EMTA-liites" in reason
        assert "12.5" in reason


def test_investeering_incomplete_rows_stay_null(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    v, reason = dim_investeering_cityplans(
        TALLINN, pois(investeeringud=[mkinvest(invest=None)]))
    assert v is None and "EI OLE" in reason
    v, reason = dim_investeering_cityplans(
        TALLINN, pois(investeeringud=[mkinvest(trend="ehk")]))
    assert v is None and "EI OLE" in reason
    v, reason = dim_investeering_cityplans(TALLINN, pois())
    assert v is None and "EI OLE" in reason
    v, reason = dim_investeering_cityplans(
        FAR, pois(investeeringud=[mkinvest()]))
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# P4-025 coverage: forecast leg.
# ---------------------------------------------------------------------------

def test_prognoos_bands_and_school_modulation(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    cases = [("+5%", dict(pop=5.0), 75), ("+2%", dict(pop=2.0), 65),
             ("-1%", dict(pop=-1.0), 50), ("-5%", dict(pop=-5.0), 35)]
    for _label, kw, want in cases:
        v, reason = dim_prognoos_cityplans(
            TALLINN, pois(prognoos=[mkprog(**kw)]))
        assert v == want, _label
        assert "hinnang" in reason and "REL2021-liites" in reason
    v, reason = dim_prognoos_cityplans(
        TALLINN, pois(prognoos=[mkprog(pop=2.0, school="suletakse")]))
    assert v == 55 and "sulgemine" in reason
    v, reason = dim_prognoos_cityplans(
        TALLINN, pois(prognoos=[mkprog(pop=2.0, school="avatakse")]))
    assert v == 70 and "avamine" in reason
    v, _ = dim_prognoos_cityplans(
        TALLINN, pois(prognoos=[mkprog(pop=-9.0, school="suletakse")]))
    assert v == 25  # 35 - 10, above the floor
    v, _ = dim_prognoos_cityplans(
        TALLINN, pois(prognoos=[mkprog(pop=9.0, school="avatakse")]))
    assert v == 80  # 75 + 5 capped


def test_prognoos_null_contract(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    v, reason = dim_prognoos_cityplans(
        TALLINN, pois(prognoos=[mkprog(pop=None)]))
    assert v is None and "EI OLE" in reason
    v, reason = dim_prognoos_cityplans(TALLINN, pois())
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# P4-037 coverage: planned-zone leg.
# ---------------------------------------------------------------------------

def test_poliitika_zones_score_and_arutelu_flagged(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    for kind, want in (("ummikumaks_arutelu", 45), ("autovaba", 50),
                       ("tasuline_parkimine", 60)):
        v, reason = dim_poliitika_kava_cityplans(
            TALLINN, pois(poliitika=[mkpol(kind=kind)]))
        assert v == want == POLICY_SCORES[kind]
        assert "hinnang" in reason and "EMTA-liites" in reason
    v, reason = dim_poliitika_kava_cityplans(
        TALLINN, pois(poliitika=[mkpol(kind="ummikumaks_arutelu")]))
    assert "arutelu, mitte otsus" in reason


def test_poliitika_null_contract(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    v, reason = dim_poliitika_kava_cityplans(
        TALLINN, pois(poliitika=[mkpol(kind="tundmatu")]))
    assert v is None and "EI OLE" in reason
    v, reason = dim_poliitika_kava_cityplans(TALLINN, pois())
    assert v is None and "EI OLE" in reason
    v, reason = dim_poliitika_kava_cityplans(
        FAR, pois(poliitika=[mkpol()]))
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# P4-041 coverage: vaatekoridor leg.
# ---------------------------------------------------------------------------

def test_vaatekoridor_capped_and_no_clear(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    v, reason = dim_vaatekoridor_cityplans(
        TALLINN, pois(vaatekoridorid=[mkvaade()]))
    assert v == VAATE_SCORE == 65
    assert "hinnang" in reason and "ülempiir" in reason
    assert "mitte vaate garantii" in reason
    assert "EHR/AER-liites" in reason
    # absence of a corridor is NOT a clear verdict
    v, reason = dim_vaatekoridor_cityplans(
        FAR, pois(vaatekoridorid=[mkvaade()]))
    assert v is None and "EI OLE" in reason
    v, reason = dim_vaatekoridor_cityplans(TALLINN, pois())
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# P4-050 coverage: ehitusstatistika leg.
# ---------------------------------------------------------------------------

def test_ehitusstat_ratio_bands(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    cases = [("0.4", 40, 100, 80), ("1.0", 100, 100, 60),
             ("2.0", 200, 100, 40), ("3.0", 300, 100, GLUT_HIGH_SCORE)]
    for _label, pipe, done, want in cases:
        v, reason = dim_ehitusstat_cityplans(
            TALLINN, pois(ehitusstat=[mkstat(permits=pipe,
                                            completions=done)]))
        assert v == want, _label
        assert "hinnang" in reason and "linnaosa" in reason


def test_ehitusstat_pipeline_fallbacks_and_gaps(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    v, reason = dim_ehitusstat_cityplans(
        TALLINN, pois(ehitusstat=[mkstat(permits=10, completions=None)]))
    assert v == 70 and "ainult torustik" in reason
    v, reason = dim_ehitusstat_cityplans(
        TALLINN, pois(ehitusstat=[mkstat(permits=40, completions=0)]))
    assert v == 20 and "puhas torustik" in reason
    for pipe, done in ((None, None), (0, 0), (None, 50)):
        v, reason = dim_ehitusstat_cityplans(
            TALLINN, pois(ehitusstat=[mkstat(permits=pipe,
                                            completions=done)]))
        assert v is None, (pipe, done)
        assert "EI OLE" in reason
    v, reason = dim_ehitusstat_cityplans(TALLINN, pois())
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# P4-061 coverage: fringe checklist leg.
# ---------------------------------------------------------------------------

def test_fringe_checklist_bands_and_cut_penalty(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    full = pois(aarealad=[mkfringe()])
    v, reason = dim_aareala_teenus_cityplans(TALLINN, full)
    assert v == 80
    assert "hinnang" in reason and "3/3" in reason
    assert "peatus-liites" in reason
    two = pois(aarealad=[mkfringe(atm=False)])
    v, reason = dim_aareala_teenus_cityplans(TALLINN, two)
    assert v == 60 and "puudu: atm" in reason
    one = pois(aarealad=[mkfringe(shop=True, pharmacy=False, atm=False)])
    v, _ = dim_aareala_teenus_cityplans(TALLINN, one)
    assert v == 40
    none = pois(aarealad=[mkfringe(shop=False, pharmacy=False, atm=False)])
    v, _ = dim_aareala_teenus_cityplans(TALLINN, none)
    assert v == 25
    cut = pois(aarealad=[mkfringe(bus_cuts=True)])
    v, reason = dim_aareala_teenus_cityplans(TALLINN, cut)
    assert v == 70 and "bussikärped" in reason
    bare_cut = pois(aarealad=[mkfringe(shop=False, pharmacy=False,
                                       atm=False, bus_cuts=True)])
    v, _ = dim_aareala_teenus_cityplans(TALLINN, bare_cut)
    assert v == 20  # 25 - 10 floored at 20


def test_fringe_null_contract(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    v, reason = dim_aareala_teenus_cityplans(TALLINN, pois())
    assert v is None and "EI OLE" in reason
    v, reason = dim_aareala_teenus_cityplans(
        FAR, pois(aarealad=[mkfringe()]))

    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# Registry, aggregator, honesty markers across all eight dims.
# ---------------------------------------------------------------------------

def test_registry_keys_and_pnums():
    assert [k for k, _, _ in P4_CITYPLANS_DIMS] == [
        "tramfaas_cityplans", "arenguala_cityplans",
        "investeering_cityplans", "prognoos_cityplans",
        "poliitika_kava_cityplans", "vaatekoridor_cityplans",
        "ehitusstat_cityplans", "aareala_teenus_cityplans",
    ]
    assert [p for _, p, _ in P4_CITYPLANS_DIMS] == [
        "P4-014", "P4-006", "P4-019", "P4-025",
        "P4-037", "P4-041", "P4-050", "P4-061",
    ]
    assert all(key.endswith("_cityplans") for key, _, _ in P4_CITYPLANS_DIMS)


def test_aggregator_wires_all_eight(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    full = pois(tramworks=[mktram()], arengualad=[mkareng()],
                investeeringud=[mkinvest()], prognoos=[mkprog()],
                poliitika=[mkpol()], vaatekoridorid=[mkvaade()],
                ehitusstat=[mkstat()], aarealad=[mkfringe()])
    out = score_p4_cityplans(TALLINN, full, TODAY)
    assert out == {"tramfaas_cityplans": 35, "arenguala_cityplans": 50,
                   "investeering_cityplans": 75, "prognoos_cityplans": 65,
                   "poliitika_kava_cityplans": 60,
                   "vaatekoridor_cityplans": 65,
                   "ehitusstat_cityplans": 80,
                   "aareala_teenus_cityplans": 80}
    empty = score_p4_cityplans(TALLINN, [], TODAY)
    assert all(v is None for v in empty.values()) and len(empty) == 8
    assert set(score_p4_cityplans(None, None)) == set(out)


def test_all_null_reasons_carry_estonian_markers(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    dims = [lambda o, p: dim_tramfaas_cityplans(o, p, TODAY),
            dim_arenguala_cityplans, dim_investeering_cityplans,
            dim_prognoos_cityplans, dim_poliitika_kava_cityplans,
            dim_vaatekoridor_cityplans, dim_ehitusstat_cityplans,
            dim_aareala_teenus_cityplans]
    for fn in dims:
        v, reason = fn(TALLINN, [])
        assert v is None, fn
        assert "EI OLE" in reason, fn
        v, reason = fn(None, None)
        assert v is None, fn
        assert "EI OLE" in reason, fn


def test_scorers_never_touch_network(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    full = pois(tramworks=[mktram()], arengualad=[mkareng()],
                investeeringud=[mkinvest()], prognoos=[mkprog()],
                poliitika=[mkpol()], vaatekoridorid=[mkvaade()],
                ehitusstat=[mkstat()], aarealad=[mkfringe()])
    score_p4_cityplans(TALLINN, full, TODAY)  # raises if network touched


def test_module_docstring_states_pairing_and_sibling_legs():
    doc = p4c.__doc__
    for marker in ("#282", "#356", "dims_p4_rb", "dims_p4_emta",
                   "dims_p4_rel2021", "dims_p4_peatus", "EI OLE",
                   "CITYPLANS_BULK_URL"):
        assert marker in doc, marker
    assert "import livability" not in open(p4c.__file__,
                                           encoding="utf-8").read()


def test_no_forbidden_precision_words_in_reasons(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_urlopen)
    full = pois(tramworks=[mktram()], arengualad=[mkareng()],
                investeeringud=[mkinvest()], prognoos=[mkprog()],
                poliitika=[mkpol()], vaatekoridorid=[mkvaade()],
                ehitusstat=[mkstat()], aarealad=[mkfringe()])
    out = score_p4_cityplans(TALLINN, full, TODAY)
    assert all(v is not None for v in out.values())
    import re

    text = open(p4c.__file__, encoding="utf-8").read()
    scored_reasons = re.findall(r'return score,? \(?["\'](.*?)["\']',
                                text, re.S)
    assert scored_reasons, "expected scored reason strings"
    for reason in scored_reasons:
        assert "mõõdetud" not in reason and "garanteeritud" not in reason

